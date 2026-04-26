"""
influencer_live_control_view.py
View postada no canal control-contra-<influencer>.

ARQUITETURA DE PERSISTENT VIEW COM custom_id DINÂMICO:
  - Selects e botões usam custom_id=f"ctrl_*_{influencer_id}".
  - bot.add_view() NÃO funciona para custom_ids dinâmicos (uid=0 no boot
    geraria ctrl_*_0 que nunca coincide com o custom_id real).
  - A reconstrução pós-restart é feita via on_interaction no main.py,
    que extrai o influencer_id do custom_id e consulta o banco.
  - A view NÃO é mais registrada como persistent no boot.
"""
from __future__ import annotations
import discord
from discord.ui import View, Button, Modal, TextInput, Select
from models.influencer_live_room import InfluencerLiveRoom
from utils.logger import logger
from utils.datetime_utils import utcnow

THEME_LIVE = 0xE91E63


# ══════════════════════════════════════════════════════════════════════════════
# EMBED DE CONTROLE
# ══════════════════════════════════════════════════════════════════════════════

def build_control_embed(room: InfluencerLiveRoom) -> discord.Embed:
    status_map = {
        "active":   ("🟢 Aberta",  discord.Colour.green()),
        "paused":   ("⏸️ Pausada", discord.Colour.orange()),
        "inactive": ("🔴 Fechada", discord.Colour.red()),
    }
    status_label, color = status_map.get(room.status, ("❓", discord.Colour.greyple()))

    embed = discord.Embed(
        title="🎛️ Painel de Controle — Sua Sala",
        description=(
            "Use os botões abaixo para atualizar as configurações da sala "
            "ou para desativar a fila.\n\n"
            "⚠️ **Desativar** irá remover ambos os canais e expulsar todos da fila."
        ),
        color=color,
        timestamp=utcnow(),
    )
    embed.add_field(name="Status",      value=status_label,                    inline=True)
    embed.add_field(name="Plataforma",  value=f"`{room.platform}`",            inline=True)
    embed.add_field(name="Tipo",        value=f"`{room.game_mode}`",           inline=True)
    embed.add_field(name="Valor",       value=f"R$ `{room.entry_value:.2f}`",  inline=True)
    embed.add_field(name="Fila",        value=f"`{room.queue_size}` jogadores", inline=True)
    embed.add_field(name="Partidas",    value=f"`{room.total_matches}` realizadas", inline=True)
    if room.custom_rules:
        embed.add_field(name="Regras",  value=room.custom_rules,               inline=False)
    # FIX: IDs no footer para recuperação pós-restart via on_interaction
    embed.set_footer(
        text=f"SOLAR E-SPORTS · Control · influencer:{room.influencer_id} guild:{room.guild_id}"
    )
    return embed


# ══════════════════════════════════════════════════════════════════════════════
# MODAIS
# ══════════════════════════════════════════════════════════════════════════════

class _EditValorModal(Modal, title="Atualizar Valor de Entrada"):
    valor = TextInput(
        label="Novo valor (R$)",
        placeholder="Ex: 10.00",
        style=discord.TextStyle.short,
        required=True,
        max_length=10,
    )

    def __init__(self, influencer_id: int, guild_id: int, current: float):
        super().__init__()
        self._influencer_id = influencer_id
        self._guild_id      = guild_id
        self.valor.default  = str(current)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.valor.value.strip().replace(",", ".")
        try:
            val = float(raw)
            if val <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Valor inválido. Ex: `5.00`", ephemeral=True)
            return
        from services.influencer_live_room_service import influencer_live_room_service
        result = await influencer_live_room_service.editar_sala(
            influencer_id=str(self._influencer_id),
            guild_id=str(self._guild_id),
            entry_value=val,
        )
        if result["ok"]:
            await _refresh_control_panel(interaction, result["room"])
        else:
            await interaction.response.send_message(f"❌ {result['msg']}", ephemeral=True)


class _EditRegrasModal(Modal, title="Atualizar Regras da Sala"):
    regras = TextInput(
        label="Regras customizadas",
        placeholder="Ex: Sem rush nos primeiros 30s...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
    )

    def __init__(self, influencer_id: int, guild_id: int, current: str | None):
        super().__init__()
        self._influencer_id = influencer_id
        self._guild_id      = guild_id
        if current:
            self.regras.default = current

    async def on_submit(self, interaction: discord.Interaction):
        from services.influencer_live_room_service import influencer_live_room_service
        result = await influencer_live_room_service.editar_sala(
            influencer_id=str(self._influencer_id),
            guild_id=str(self._guild_id),
            custom_rules=self.regras.value or None,
        )
        if result["ok"]:
            await _refresh_control_panel(interaction, result["room"])
        else:
            await interaction.response.send_message(f"❌ {result['msg']}", ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════════════════════════════════════════

async def _refresh_control_panel(interaction: discord.Interaction, room: InfluencerLiveRoom):
    embed = build_control_embed(room)
    view  = ContraControlView(influencer_id=room.influencer_id, guild_id=room.guild_id)
    try:
        await interaction.response.edit_message(embed=embed, view=view)
    except discord.InteractionResponded:
        await interaction.edit_original_response(embed=embed, view=view)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW PRINCIPAL DE CONTROLE
# ══════════════════════════════════════════════════════════════════════════════

class ContraControlView(View):
    """
    Painel de controle no canal control-contra-<influencer>.

    custom_id dinâmico: ctrl_*_{influencer_id}
    Reconstruída via on_interaction no main.py pós-restart.
    NÃO registrada via bot.add_view no boot.
    """

    def __init__(self, influencer_id: int | str, guild_id: int | str):
        super().__init__(timeout=None)
        self.influencer_id = int(influencer_id)
        self.guild_id      = int(guild_id)
        uid = self.influencer_id

        plat_select = Select(
            placeholder="🖥️ Alterar Plataforma...",
            custom_id=f"ctrl_select_platform_{uid}",
            options=[
                discord.SelectOption(label="📱 Mobile",    value="Mobile"),
                discord.SelectOption(label="🖥️ Emulador", value="Emulador"),
                discord.SelectOption(label="🔀 Misto",     value="Misto"),
            ],
            row=0,
        )
        plat_select.callback = self._select_platform
        self.add_item(plat_select)

        mode_select = Select(
            placeholder="🎮 Alterar Tipo...",
            custom_id=f"ctrl_select_gamemode_{uid}",
            options=[
                discord.SelectOption(label="1x1", value="1x1"),
                discord.SelectOption(label="2x2", value="2x2"),
                discord.SelectOption(label="3x3", value="3x3"),
                discord.SelectOption(label="4x4", value="4x4"),
            ],
            row=1,
        )
        mode_select.callback = self._select_gamemode
        self.add_item(mode_select)

        btn_valor = Button(
            label="💰 Editar Valor",
            style=discord.ButtonStyle.primary,
            custom_id=f"ctrl_edit_valor_{uid}",
            row=2,
        )
        btn_valor.callback = self._edit_valor
        self.add_item(btn_valor)

        btn_regras = Button(
            label="📋 Editar Regras",
            style=discord.ButtonStyle.secondary,
            custom_id=f"ctrl_edit_regras_{uid}",
            row=2,
        )
        btn_regras.callback = self._edit_regras
        self.add_item(btn_regras)

        btn_fila = Button(
            label="📊 Ver Fila",
            style=discord.ButtonStyle.secondary,
            custom_id=f"ctrl_view_queue_{uid}",
            row=2,
        )
        btn_fila.callback = self._view_queue
        self.add_item(btn_fila)

        btn_desativar = Button(
            label="🔴 Desativar Fila",
            style=discord.ButtonStyle.danger,
            custom_id=f"ctrl_desativar_{uid}",
            row=3,
        )
        btn_desativar.callback = self._desativar
        self.add_item(btn_desativar)

    def _is_authorized(self, interaction: discord.Interaction) -> bool:
        return (
            interaction.user.id == self.influencer_id
            or interaction.user.guild_permissions.administrator
        )

    async def _select_platform(self, interaction: discord.Interaction):
        if not self._is_authorized(interaction):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        select = next((c for c in self.children if isinstance(c, Select) and "platform" in c.custom_id), None)
        new_platform = select.values[0] if select else None
        if not new_platform:
            await interaction.response.send_message("❌ Selecione uma plataforma.", ephemeral=True)
            return
        from services.influencer_live_room_service import influencer_live_room_service
        result = await influencer_live_room_service.editar_sala(
            influencer_id=str(self.influencer_id),
            guild_id=str(self.guild_id),
            platform=new_platform,
        )
        if result["ok"]:
            await _refresh_control_panel(interaction, result["room"])
        else:
            await interaction.response.send_message(f"❌ {result['msg']}", ephemeral=True)

    async def _select_gamemode(self, interaction: discord.Interaction):
        if not self._is_authorized(interaction):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        select = next((c for c in self.children if isinstance(c, Select) and "gamemode" in c.custom_id), None)
        new_mode = select.values[0] if select else None
        if not new_mode:
            await interaction.response.send_message("❌ Selecione um tipo.", ephemeral=True)
            return
        from services.influencer_live_room_service import influencer_live_room_service
        result = await influencer_live_room_service.editar_sala(
            influencer_id=str(self.influencer_id),
            guild_id=str(self.guild_id),
            game_mode=new_mode,
        )
        if result["ok"]:
            await _refresh_control_panel(interaction, result["room"])
        else:
            await interaction.response.send_message(f"❌ {result['msg']}", ephemeral=True)

    async def _edit_valor(self, interaction: discord.Interaction):
        if not self._is_authorized(interaction):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        from services.influencer_live_room_service import influencer_live_room_service
        room_result = await influencer_live_room_service.get_room(
            str(self.influencer_id), str(self.guild_id))
        current = room_result["room"].entry_value if room_result["ok"] else 0.0
        await interaction.response.send_modal(
            _EditValorModal(self.influencer_id, self.guild_id, current))

    async def _edit_regras(self, interaction: discord.Interaction):
        if not self._is_authorized(interaction):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        from services.influencer_live_room_service import influencer_live_room_service
        room_result = await influencer_live_room_service.get_room(
            str(self.influencer_id), str(self.guild_id))
        current = room_result["room"].custom_rules if room_result["ok"] else None
        await interaction.response.send_modal(
            _EditRegrasModal(self.influencer_id, self.guild_id, current))

    async def _view_queue(self, interaction: discord.Interaction):
        if not self._is_authorized(interaction):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        from services.influencer_live_queue_service import influencer_live_queue_service
        result = await influencer_live_queue_service.get_fila(
            influencer_id=str(self.influencer_id),
            guild_id=str(self.guild_id),
        )
        if not result["ok"]:
            await interaction.response.send_message(f"❌ {result['msg']}", ephemeral=True)
            return
        queue   = result["queue"]
        players = queue.players
        embed = discord.Embed(title="📋 Fila Atual — Modo Contra", color=THEME_LIVE, timestamp=utcnow())
        embed.add_field(name="Na fila", value=f"`{len(players)}`", inline=True)
        embed.add_field(name="Status",  value=f"`{queue.status}`", inline=True)
        if players:
            lines = [f"`{i+1}.` <@{pid}>" for i, pid in enumerate(players[:20])]
            embed.add_field(name="Jogadores", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Jogadores", value="Nenhum na fila.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _desativar(self, interaction: discord.Interaction):
        if not self._is_authorized(interaction):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        confirm_view = _ConfirmDesativarView(
            influencer_id=self.influencer_id, guild_id=self.guild_id)
        await interaction.response.send_message(
            "⚠️ **Tem certeza?**\nIsto irá:\n"
            "— Excluir o canal `contra-você`\n"
            "— Excluir este canal `control-contra-você`\n"
            "— Remover todos da fila\n\n"
            "Esta ação **não pode ser desfeita**.",
            view=confirm_view,
            ephemeral=True,
        )


class _ConfirmDesativarView(View):
    def __init__(self, influencer_id: int, guild_id: int):
        super().__init__(timeout=60)
        self.influencer_id = influencer_id
        self.guild_id      = guild_id

    @discord.ui.button(label="✅ Sim, desativar", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_live_room_service import influencer_live_room_service
        member = interaction.guild.get_member(self.influencer_id)
        if not member:
            await interaction.followup.send("❌ Influencer não encontrado no servidor.", ephemeral=True)
            return
        result = await influencer_live_room_service.desativar_sala(
            guild=interaction.guild,
            influencer=member,
            forced_by=interaction.user if interaction.user.id != self.influencer_id else None,
        )
        if result["ok"]:
            await interaction.followup.send(
                "✅ Sala desativada. Canais removidos e fila encerrada.", ephemeral=True)
            logger.info(f"[ContraControl] Sala desativada por {interaction.user.name}")
        else:
            await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)
        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Operação cancelada.", ephemeral=True)
        self.stop()
