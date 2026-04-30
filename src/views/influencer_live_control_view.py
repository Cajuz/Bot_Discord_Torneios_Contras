"""
influencer_live_control_view.py
View postada no canal control-contra-<influencer>.

FLUXO DE EDIÇÃO COM STAGING:
  - Selects e botões de edição atualizam apenas o embed local (pendente).
  - Nenhum dado é gravado no banco até o usuário clicar em "✅ Atualizar Sala".
  - "🔄 Resetar" descarta as mudanças e recarrega os valores do banco.
  - Ao salvar, o card público (contra-<influencer>) é sincronizado automaticamente.

REGRA DISCORD — OBRIGATÓRIO:
  Toda interação deve ser respondida em até 3 segundos.
  Por isso QUALQUER await de I/O (banco, rede) deve vir DEPOIS do
  defer()/edit_message()/send_modal(). Caso contrário o Discord retorna
  "erro interno" e a interação expira.
"""
from __future__ import annotations
import discord
from discord.ui import View, Button, Modal, TextInput, Select
from models.influencer_live_room import InfluencerLiveRoom
from utils.logger import logger
from utils.datetime_utils import utcnow

THEME_LIVE = 0xE91E63

# ─── Staging cache (em memória) ─────────────────────────────────────────────
_pending: dict[str, dict] = {}  # key: "influencer_id:guild_id"

def _key(influencer_id: int, guild_id: int) -> str:
    return f"{influencer_id}:{guild_id}"


# ════════════════════════════════════════════════════════════════════════════
# EMBED DE CONTROLE
# ════════════════════════════════════════════════════════════════════════════

def build_control_embed(
    room: InfluencerLiveRoom,
    pending: dict | None = None,
) -> discord.Embed:
    status_map = {
        "active":   ("🟢 Aberta",  discord.Colour.green()),
        "paused":   ("⏸️ Pausada", discord.Colour.orange()),
        "inactive": ("🔴 Fechada", discord.Colour.red()),
    }
    status_label, color = status_map.get(room.status, ("❓", discord.Colour.greyple()))

    platform     = pending.get("platform",     room.platform)     if pending else room.platform
    game_mode    = pending.get("game_mode",    room.game_mode)    if pending else room.game_mode
    entry_value  = pending.get("entry_value",  room.entry_value)  if pending else room.entry_value
    custom_rules = pending.get("custom_rules", room.custom_rules) if pending else room.custom_rules

    has_pending  = bool(pending)
    title_suffix = "  ⚠️ *não salvo*" if has_pending else ""

    embed = discord.Embed(
        title=f"🎛️ Painel de Controle — Sua Sala{title_suffix}",
        description=(
            "Ajuste os parâmetros e clique em **✅ Atualizar Sala** para salvar.\n"
            "Use **🔄 Resetar** para descartar as alterações pendentes.\n\n"
            "⚠️ **Desativar** remove ambos os canais e encerra a fila."
        ),
        color=discord.Colour.orange() if has_pending else color,
        timestamp=utcnow(),
    )
    embed.add_field(name="Status",     value=status_label,                      inline=True)
    embed.add_field(name="Plataforma", value=f"`{platform}`",                   inline=True)
    embed.add_field(name="Tipo",       value=f"`{game_mode}`",                  inline=True)
    embed.add_field(name="Valor",      value=f"R$ `{entry_value:.2f}`",         inline=True)
    embed.add_field(name="Fila",       value=f"`{room.queue_size}` jogadores",  inline=True)
    embed.add_field(name="Partidas",   value=f"`{room.total_matches}` realizadas", inline=True)
    if custom_rules:
        embed.add_field(name="Regras", value=custom_rules, inline=False)
    if has_pending:
        embed.add_field(
            name="📝 Alterações pendentes",
            value="\n".join(f"• **{k}**: `{v}`" for k, v in pending.items()),
            inline=False,
        )
    embed.set_footer(
        text=f"SOLAR E-SPORTS · Control · influencer:{room.influencer_id} guild:{room.guild_id}"
    )
    return embed


# ════════════════════════════════════════════════════════════════════════════
# MODAIS  —  defer() SEMPRE na primeira linha antes de qualquer await de I/O
# ════════════════════════════════════════════════════════════════════════════

class _EditValorModal(Modal, title="Atualizar Valor de Entrada"):
    valor = TextInput(
        label="Novo valor (R$)",
        placeholder="Ex: 10.00",
        style=discord.TextStyle.short,
        required=True,
        max_length=10,
    )

    def __init__(self, influencer_id: int, guild_id: int, current: float, control_msg: discord.Message):
        super().__init__()
        self._influencer_id = influencer_id
        self._guild_id      = guild_id
        self._control_msg   = control_msg
        self.valor.default  = str(current) if current else ""

    async def on_submit(self, interaction: discord.Interaction):
        # 1º: validação síncrona (sem I/O)
        raw = self.valor.value.strip().replace(",", ".")
        try:
            val = float(raw)
            if val <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Valor inválido. Ex: `5.00`", ephemeral=True)
            return

        # 2º: responde ao Discord imediatamente (< 3s)
        await interaction.response.defer()

        # 3º: I/O após defer
        k = _key(self._influencer_id, self._guild_id)
        _pending.setdefault(k, {})["entry_value"] = val

        from services.influencer_live_room_service import influencer_live_room_service
        room_result = await influencer_live_room_service.get_room(
            str(self._influencer_id), str(self._guild_id))
        if room_result["ok"]:
            embed = build_control_embed(room_result["room"], _pending.get(k))
            view  = ContraControlView(self._influencer_id, self._guild_id)
            await self._control_msg.edit(embed=embed, view=view)
        else:
            await interaction.followup.send(f"❌ {room_result['msg']}", ephemeral=True)


class _EditRegrasModal(Modal, title="Atualizar Regras da Sala"):
    regras = TextInput(
        label="Regras customizadas",
        placeholder="Ex: Sem rush nos primeiros 30s...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
    )

    def __init__(self, influencer_id: int, guild_id: int, current: str | None, control_msg: discord.Message):
        super().__init__()
        self._influencer_id = influencer_id
        self._guild_id      = guild_id
        self._control_msg   = control_msg
        if current:
            self.regras.default = current

    async def on_submit(self, interaction: discord.Interaction):
        # 1º: responde ao Discord imediatamente (< 3s) — sem I/O antes!
        await interaction.response.defer()

        # 2º: I/O após defer
        k = _key(self._influencer_id, self._guild_id)
        _pending.setdefault(k, {})["custom_rules"] = self.regras.value  # "" = limpar

        from services.influencer_live_room_service import influencer_live_room_service
        room_result = await influencer_live_room_service.get_room(
            str(self._influencer_id), str(self._guild_id))
        if room_result["ok"]:
            embed = build_control_embed(room_result["room"], _pending.get(k))
            view  = ContraControlView(self._influencer_id, self._guild_id)
            await self._control_msg.edit(embed=embed, view=view)
        else:
            await interaction.followup.send(f"❌ {room_result['msg']}", ephemeral=True)


# ════════════════════════════════════════════════════════════════════════════
# HELPER — sincroniza o card público
# ════════════════════════════════════════════════════════════════════════════

async def _sync_public_card(guild: discord.Guild, room: InfluencerLiveRoom):
    try:
        channel = guild.get_channel(int(room.channel_id))
        if not channel:
            return
        from views.influencer_live_view import build_contra_room_embed, ContraRoomView
        from services.influencer_live_queue_service import influencer_live_queue_service
        q = await influencer_live_queue_service.get_fila(
            influencer_id=str(room.influencer_id), guild_id=str(room.guild_id))
        queue_size = len(q["queue"].players) if q["ok"] else room.queue_size
        pub_embed = build_contra_room_embed(room, queue_size=queue_size)
        pub_view  = ContraRoomView(influencer_id=int(room.influencer_id), guild_id=int(room.guild_id))
        async for msg in channel.history(limit=15, oldest_first=True):
            if msg.author == guild.me and msg.embeds:
                await msg.edit(embed=pub_embed, view=pub_view)
                break
    except Exception as e:
        logger.warning(f"[ContraControl] Falha ao sincronizar card público: {e}")


# ════════════════════════════════════════════════════════════════════════════
# VIEW PRINCIPAL DE CONTROLE
# ════════════════════════════════════════════════════════════════════════════

class ContraControlView(View):
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

        btn_valor = Button(label="💰 Editar Valor",  style=discord.ButtonStyle.primary,
                           custom_id=f"ctrl_edit_valor_{uid}",   row=2)
        btn_valor.callback = self._edit_valor
        self.add_item(btn_valor)

        btn_regras = Button(label="📋 Editar Regras", style=discord.ButtonStyle.secondary,
                            custom_id=f"ctrl_edit_regras_{uid}",  row=2)
        btn_regras.callback = self._edit_regras
        self.add_item(btn_regras)

        btn_fila = Button(label="📊 Ver Fila", style=discord.ButtonStyle.secondary,
                          custom_id=f"ctrl_view_queue_{uid}", row=2)
        btn_fila.callback = self._view_queue
        self.add_item(btn_fila)

        btn_salvar = Button(label="✅ Atualizar Sala", style=discord.ButtonStyle.success,
                            custom_id=f"ctrl_salvar_{uid}", row=3)
        btn_salvar.callback = self._salvar
        self.add_item(btn_salvar)

        btn_resetar = Button(label="🔄 Resetar", style=discord.ButtonStyle.secondary,
                             custom_id=f"ctrl_resetar_{uid}", row=3)
        btn_resetar.callback = self._resetar
        self.add_item(btn_resetar)

        btn_desativar = Button(label="🔴 Desativar Fila", style=discord.ButtonStyle.danger,
                               custom_id=f"ctrl_desativar_{uid}", row=4)
        btn_desativar.callback = self._desativar
        self.add_item(btn_desativar)

    def _is_authorized(self, interaction: discord.Interaction) -> bool:
        return (
            interaction.user.id == self.influencer_id
            or interaction.user.guild_permissions.administrator
        )

    # ── Selects ────────────────────────────────────────────────────────────

    async def _select_platform(self, interaction: discord.Interaction):
        if not self._is_authorized(interaction):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        sel = next((c for c in self.children if isinstance(c, Select) and "platform" in c.custom_id), None)
        val = sel.values[0] if sel else None
        if not val:
            await interaction.response.send_message("❌ Selecione uma plataforma.", ephemeral=True)
            return
        # Responde ao Discord ANTES do I/O
        await interaction.response.defer()
        k = _key(self.influencer_id, self.guild_id)
        _pending.setdefault(k, {})["platform"] = val
        await self._rebuild_embed_after_defer(interaction, k)

    async def _select_gamemode(self, interaction: discord.Interaction):
        if not self._is_authorized(interaction):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        sel = next((c for c in self.children if isinstance(c, Select) and "gamemode" in c.custom_id), None)
        val = sel.values[0] if sel else None
        if not val:
            await interaction.response.send_message("❌ Selecione um tipo.", ephemeral=True)
            return
        # Responde ao Discord ANTES do I/O
        await interaction.response.defer()
        k = _key(self.influencer_id, self.guild_id)
        _pending.setdefault(k, {})["game_mode"] = val
        await self._rebuild_embed_after_defer(interaction, k)

    async def _rebuild_embed_after_defer(self, interaction: discord.Interaction, k: str):
        """Chama o banco APÓS defer() e atualiza a mensagem."""
        from services.influencer_live_room_service import influencer_live_room_service
        result = await influencer_live_room_service.get_room(
            str(self.influencer_id), str(self.guild_id))
        if result["ok"]:
            embed = build_control_embed(result["room"], _pending.get(k))
            view  = ContraControlView(self.influencer_id, self.guild_id)
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)

    # ── Botões de modal ─────────────────────────────────────────────────────────

    async def _edit_valor(self, interaction: discord.Interaction):
        if not self._is_authorized(interaction):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        # Usa valor do staging se existir (sem I/O), senão 0.0
        k = _key(self.influencer_id, self.guild_id)
        current = _pending.get(k, {}).get("entry_value", 0.0)
        # send_modal() é a resposta ao Discord — sem await de I/O antes
        await interaction.response.send_modal(
            _EditValorModal(self.influencer_id, self.guild_id, current, interaction.message))

    async def _edit_regras(self, interaction: discord.Interaction):
        if not self._is_authorized(interaction):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        k = _key(self.influencer_id, self.guild_id)
        current = _pending.get(k, {}).get("custom_rules", None)
        # send_modal() é a resposta ao Discord — sem await de I/O antes
        await interaction.response.send_modal(
            _EditRegrasModal(self.influencer_id, self.guild_id, current, interaction.message))

    # ── Atualizar Sala ─────────────────────────────────────────────────────────

    async def _salvar(self, interaction: discord.Interaction):
        if not self._is_authorized(interaction):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        k = _key(self.influencer_id, self.guild_id)
        staged = _pending.get(k, {})
        if not staged:
            await interaction.response.send_message(
                "ℹ️ Nenhuma alteração pendente para salvar.", ephemeral=True)
            return

        # Responde ao Discord ANTES do I/O
        await interaction.response.defer()

        from services.influencer_live_room_service import influencer_live_room_service
        result = await influencer_live_room_service.editar_sala(
            influencer_id=str(self.influencer_id),
            guild_id=str(self.guild_id),
            **staged,
        )
        if not result["ok"]:
            await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)
            return

        _pending.pop(k, None)
        room  = result["room"]
        embed = build_control_embed(room)
        view  = ContraControlView(self.influencer_id, self.guild_id)
        await interaction.edit_original_response(embed=embed, view=view)
        await _sync_public_card(interaction.guild, room)
        logger.info(f"[ContraControl] Sala atualizada por {interaction.user.name} — {staged}")

    # ── Resetar ──────────────────────────────────────────────────────────────

    async def _resetar(self, interaction: discord.Interaction):
        if not self._is_authorized(interaction):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        # Responde ao Discord ANTES do I/O
        await interaction.response.defer()
        k = _key(self.influencer_id, self.guild_id)
        _pending.pop(k, None)
        from services.influencer_live_room_service import influencer_live_room_service
        result = await influencer_live_room_service.get_room(
            str(self.influencer_id), str(self.guild_id))
        if result["ok"]:
            embed = build_control_embed(result["room"])
            view  = ContraControlView(self.influencer_id, self.guild_id)
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)

    # ── Ver Fila ───────────────────────────────────────────────────────────────

    async def _view_queue(self, interaction: discord.Interaction):
        if not self._is_authorized(interaction):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        # Responde ao Discord ANTES do I/O
        await interaction.response.defer(ephemeral=True)
        from services.influencer_live_queue_service import influencer_live_queue_service
        result = await influencer_live_queue_service.get_fila(
            influencer_id=str(self.influencer_id), guild_id=str(self.guild_id))
        if not result["ok"]:
            await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)
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
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── Desativar ─────────────────────────────────────────────────────────────

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
            _pending.pop(_key(self.influencer_id, self.guild_id), None)
        else:
            await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)
        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Operação cancelada.", ephemeral=True)
        self.stop()
