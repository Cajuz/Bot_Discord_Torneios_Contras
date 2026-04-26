"""
live_contra_setup_view.py
View postada no canal #live-contra.

Fluxo simplificado:
  1. Influencer clica em "Configurar Minha Sala"
     → mensagem ephemeral de confirmação (só ele vê)
  2. Clica em "Confirmar" → bot cria o canal de controle e sala com valores padrão
     (plataforma/tipo/valor podem ser editados depois no canal de controle)
  3. Clica em "Cancelar" → mensagem some

Valores padrão ao criar:
  - Plataforma: Mobile
  - Tipo: 1x1
  - Valor: R$ 5,00
  (editáveis no canal control-contra-você)
"""
from __future__ import annotations
import discord
from discord.ui import View, Button
from utils.logger import logger
from utils.datetime_utils import utcnow

THEME_LIVE = 0xE91E63


def build_live_contra_embed() -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ Criar Sala — Modo Contra",
        description=(
            "Configure sua sala para receber desafiantes ao vivo.\n\n"
            "**Como funciona:**\n"
            "1️⃣ Clique em **Configurar Minha Sala**\n"
            "2️⃣ Confirme a criação\n"
            "3️⃣ No canal de controle, ajuste **Plataforma**, **Tipo**, **Valor** e **Regras**\n\n"
            "Será criado um canal `control-contra-você` *(só você e ADM veem)* "
            "e um canal `contra-você` *(público para membros entrarem na fila)*."
        ),
        color=THEME_LIVE,
        timestamp=utcnow(),
    )
    embed.set_footer(text="SOLAR E-SPORTS · Modo Contra · Apenas Influencers")
    return embed


# ══════════════════════════════════════════════════════════════════════════════
# VIEW PRINCIPAL (persistent) — botão fixo
# ══════════════════════════════════════════════════════════════════════════════

class LiveContraSetupView(View):
    """
    Painel fixo no canal #live-contra.
    custom_id FIXO = "live_contra_open_session" → ok para persistent view.
    """

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="⚔️ Configurar Minha Sala",
        style=discord.ButtonStyle.danger,
        custom_id="live_contra_open_session",
        emoji="🎮",
        row=0,
    )
    async def open_session(self, interaction: discord.Interaction, button: Button):
        # Verifica permissão
        role_inf = discord.utils.get(interaction.guild.roles, name="Influencer")
        is_adm   = interaction.user.guild_permissions.administrator
        is_inf   = role_inf and role_inf in interaction.user.roles

        if not (is_adm or is_inf):
            await interaction.response.send_message(
                "❌ Apenas **Influencers** podem criar salas.", ephemeral=True)
            return

        # Verifica se já tem sala ativa
        from services.influencer_live_room_service import influencer_live_room_service
        existing = await influencer_live_room_service.get_room(
            influencer_id=str(interaction.user.id),
            guild_id=str(interaction.guild_id),
        )
        if existing["ok"]:
            room = existing["room"]
            await interaction.response.send_message(
                f"❌ Você já tem uma sala ativa (`{room.platform} · {room.game_mode}`)."
                "\nAcesse seu canal de controle para gerenciá-la ou desativá-la.",
                ephemeral=True,
            )
            return

        # Abre confirmação ephemeral
        embed = discord.Embed(
            title="⚔️ Criar Sala — Confirmar",
            description=(
                "Ao confirmar, o bot irá:\n\n"
                "• Criar o canal `contra-você` *(público — membros entram na fila)*\n"
                "• Criar o canal `control-contra-você` *(privado — só você e ADM)*\n\n"
                "**Configurações iniciais (editáveis depois):**\n"
                "`Plataforma:` Mobile\n"
                "`Tipo:` 1x1\n"
                "`Valor:` R$ 5,00\n\n"
                "Você pode alterar tudo isso diretamente no canal de controle."
            ),
            color=THEME_LIVE,
        )
        confirm_view = _ConfirmCreateView(influencer=interaction.user)
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW DE CONFIRMAÇÃO (ephemeral, timeout=60s)
# ══════════════════════════════════════════════════════════════════════════════

class _ConfirmCreateView(View):
    def __init__(self, influencer: discord.Member):
        super().__init__(timeout=60)
        self.influencer = influencer

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(
        label="✅ Confirmar",
        style=discord.ButtonStyle.success,
        custom_id="live_contra_confirm_create",
    )
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.influencer.id:
            await interaction.response.send_message("❌ Esta confirmação não é sua.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        from services.influencer_live_room_service import influencer_live_room_service
        result = await influencer_live_room_service.ativar_sala(
            guild=interaction.guild,
            influencer=interaction.user,
            platform="Mobile",
            game_mode="1x1",
            entry_value=5.00,
        )

        if not result["ok"]:
            await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)
            return

        ctrl = result["control_channel"]
        channel = result["channel"]
        self.stop()
        await interaction.followup.send(
            f"✅ Sala criada!\n"
            f"Canal público: {channel.mention}\n"
            f"Canal de controle: {ctrl.mention}\n\n"
            f"Use o painel em {ctrl.mention} para ajustar plataforma, tipo, valor e regras.",
            ephemeral=True,
        )
        logger.info(f"[LiveContra] Sala criada via confirmação ephemeral — {interaction.user.name}")

    @discord.ui.button(
        label="❌ Cancelar",
        style=discord.ButtonStyle.secondary,
        custom_id="live_contra_cancel_create",
    )
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.influencer.id:
            await interaction.response.send_message("❌ Esta confirmação não é sua.", ephemeral=True)
            return
        self.stop()
        await interaction.response.edit_message(
            content="❌ Criação cancelada.", embed=None, view=None
        )
