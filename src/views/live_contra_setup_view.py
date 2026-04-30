"""
live_contra_setup_view.py
View postada no canal #live-contra.

Fluxo:
  1. Influencer clica em "⚔️ Configurar Minha Sala"
     → mensagem ephemeral de confirmação (só ele vê)
  2. Clica em "Confirmar"
     → bot cria APENAS o canal control-contra-<nome> (privado)
     → no canal de controle aparecem os selects de configuração
  3. Influencer configura Plataforma / Tipo / Valor / Regras e clica "Abrir Sala"
     → bot cria o canal público contra-<nome> e registra no banco
  4. Se não configurar nada em 5 minutos
     → canal control-contra-<nome> é excluído automaticamente
"""
from __future__ import annotations
import asyncio
import discord
from discord.ui import View, Button, Select, Modal, TextInput
from models.influencer_live_room import InfluencerLiveRoom
from utils.logger import logger
from utils.datetime_utils import utcnow

THEME_LIVE  = 0xE91E63
SETUP_TTL   = 300  # 5 minutos em segundos


def build_live_contra_embed() -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ Criar Sala — Modo Contra",
        description=(
            "Configure sua sala para receber desafiantes ao vivo.\n\n"
            "**Como funciona:**\n"
            "1️⃣ Clique em **Configurar Minha Sala**\n"
            "2️⃣ Confirme a criação do painel de controle\n"
            "3️⃣ No seu canal privado, defina Plataforma, Tipo, Valor e clique **Abrir Sala**\n\n"
            "O canal público de fila só é criado após você configurar tudo."
        ),
        color=THEME_LIVE,
        timestamp=utcnow(),
    )
    embed.set_footer(text="SOLAR E-SPORTS · Modo Contra · Apenas Influencers")
    return embed


# ══════════════════════════════════════════════════════════════════════════════
# VIEW PRINCIPAL (persistent)
# ══════════════════════════════════════════════════════════════════════════════

class LiveContraSetupView(View):
    """Botão fixo no canal #live-contra. custom_id fixo = persistent."""

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
        role_inf = discord.utils.get(interaction.guild.roles, name="Influencer")
        is_adm   = interaction.user.guild_permissions.administrator
        is_inf   = role_inf and role_inf in interaction.user.roles

        if not (is_adm or is_inf):
            await interaction.response.send_message(
                "❌ Apenas **Influencers** podem criar salas.", ephemeral=True)
            return

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

        embed = discord.Embed(
            title="⚔️ Criar Sala — Confirmar",
            description=(
                "Ao confirmar, o bot irá criar o canal **`control-contra-você`** — "
                "um canal privado só para você e a ADM.\n\n"
                "Dentro dele você define:\n"
                "• **Plataforma** (Mobile / Emulador / Misto)\n"
                "• **Tipo de partida** (1x1, 2x2...)\n"
                "• **Valor de entrada** (R$)\n"
                "• **Regras** *(opcional)*\n\n"
                "O canal público de fila só é criado quando você clicar em **Abrir Sala** "
                "lá dentro.\n\n"
                "⚠️ Se não configurar nada em **5 minutos**, o canal de controle será excluído automaticamente."
            ),
            color=THEME_LIVE,
        )
        await interaction.response.send_message(
            embed=embed,
            view=_ConfirmCreateView(influencer=interaction.user),
            ephemeral=True,
        )


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

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success,
                       custom_id="live_contra_confirm_create")
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.influencer.id:
            await interaction.response.send_message("❌ Esta confirmação não é sua.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        self.stop()

        from services.channel_service import permission_service
        ctrl = await permission_service.create_control_channel(
            guild=interaction.guild,
            influencer=interaction.user,
        )

        setup_view = ContraSetupChannelView(
            influencer=interaction.user,
            ctrl_channel=ctrl,
        )
        embed = _build_setup_embed(interaction.user)
        msg = await ctrl.send(
            content=interaction.user.mention,
            embed=embed,
            view=setup_view,
        )
        setup_view._setup_msg = msg

        asyncio.create_task(
            _auto_delete_if_idle(ctrl, setup_view, interaction.user)
        )

        await interaction.followup.send(
            f"✅ Canal de controle criado: {ctrl.mention}\n"
            f"Você tem **5 minutos** para configurar e abrir a sala.",
            ephemeral=True,
        )
        logger.info(f"[LiveContra] Canal de controle criado — {interaction.user.name}")

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary,
                       custom_id="live_contra_cancel_create")
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.influencer.id:
            await interaction.response.send_message("❌ Esta confirmação não é sua.", ephemeral=True)
            return
        self.stop()
        await interaction.response.edit_message(
            content="❌ Criação cancelada.", embed=None, view=None)


# ══════════════════════════════════════════════════════════════════════════════
# PAINEL DE SETUP NO CANAL DE CONTROLE
# ══════════════════════════════════════════════════════════════════════════════

def _build_setup_embed(
    influencer: discord.Member,
    platform: str | None = None,
    game_mode: str | None = None,
    entry_value: float | None = None,
    custom_rules: str | None = None,
) -> discord.Embed:
    plat = platform   or "—"
    modo = game_mode  or "—"
    val  = f"R$ {entry_value:.2f}" if entry_value else "—"
    reg  = (custom_rules[:50] + "…" if len(custom_rules) > 50 else custom_rules) if custom_rules else "Padrão"

    can_create = platform and game_mode and entry_value
    status = "✅ Pronto! Clique em **Abrir Sala**." if can_create else (
        "⚠️ Faltando: **" + ", ".join(
            (["Plataforma"] if not platform else []) +
            (["Tipo"] if not game_mode else []) +
            (["Valor"] if not entry_value else [])
        ) + "**"
    )

    embed = discord.Embed(
        title="⚔️ Configurar Sala — Painel de Controle",
        description=(
            f"Olá {influencer.mention}! Configure sua sala abaixo.\n"
            f"Você tem **5 minutos** ou o canal será excluído.\n\n"
            f"{status}"
        ),
        color=THEME_LIVE,
    )
    embed.add_field(name="Plataforma", value=f"`{plat}`", inline=True)
    embed.add_field(name="Tipo",       value=f"`{modo}`", inline=True)
    embed.add_field(name="Valor",      value=f"`{val}`",  inline=True)
    embed.add_field(name="Regras",     value=f"`{reg}`",  inline=False)
    embed.set_footer(text="SOLAR E-SPORTS · Modo Contra")
    return embed


class ContraSetupChannelView(View):
    """
    View postada no canal control-contra-<nome> logo após a confirmação.
    Não é persistent — controlada pelo _auto_delete_if_idle.
    """

    def __init__(self, influencer: discord.Member, ctrl_channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.influencer           = influencer
        self.ctrl_channel         = ctrl_channel
        self._setup_msg: discord.Message | None = None
        self._finalized           = False
        self.selected_platform: str | None  = None
        self.selected_game_mode: str | None = None
        self.entry_value: float | None      = None
        self.custom_rules: str | None       = None
        self._build_items()

    def _build_items(self):
        self.clear_items()
        self.add_item(_PlatformSelect(self))
        self.add_item(_GameModeSelect(self))

        valor_btn = Button(
            label="💰 Valor" + (f" ✅ R${self.entry_value:.2f}" if self.entry_value else ""),
            style=discord.ButtonStyle.primary if not self.entry_value else discord.ButtonStyle.secondary,
            custom_id="setup_ctrl_valor",
            row=2,
        )
        valor_btn.callback = self._btn_valor
        self.add_item(valor_btn)

        regras_btn = Button(
            label="📋 Regras" + (" ✅" if self.custom_rules else ""),
            style=discord.ButtonStyle.secondary,
            custom_id="setup_ctrl_regras",
            row=2,
        )
        regras_btn.callback = self._btn_regras
        self.add_item(regras_btn)

        can_create = bool(self.selected_platform and self.selected_game_mode and self.entry_value)
        abrir_btn = Button(
            label="⚔️ Abrir Sala",
            style=discord.ButtonStyle.danger,
            custom_id="setup_ctrl_abrir",
            disabled=not can_create,
            row=3,
        )
        abrir_btn.callback = self._btn_abrir
        self.add_item(abrir_btn)

    async def _update_panel(self, interaction: discord.Interaction):
        """Reconstrói itens e edita a mensagem com embed atualizado."""
        self._build_items()
        embed = _build_setup_embed(
            self.influencer,
            self.selected_platform,
            self.selected_game_mode,
            self.entry_value,
            self.custom_rules,
        )
        if interaction.type == discord.InteractionType.modal_submit:
            # Modal submit: confirmar a interação e editar a mensagem de setup diretamente
            await interaction.response.defer()
            if self._setup_msg:
                await self._setup_msg.edit(embed=embed, view=self)
        else:
            # Select / Button: editar a mensagem que contém o componente
            try:
                await interaction.response.edit_message(embed=embed, view=self)
            except discord.InteractionResponded:
                await interaction.edit_original_response(embed=embed, view=self)

    def _check_owner(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.influencer.id

    async def _btn_valor(self, interaction: discord.Interaction):
        if not self._check_owner(interaction):
            await interaction.response.send_message("❌ Este painel não é seu.", ephemeral=True)
            return
        await interaction.response.send_modal(_ValorModal(self))

    async def _btn_regras(self, interaction: discord.Interaction):
        if not self._check_owner(interaction):
            await interaction.response.send_message("❌ Este painel não é seu.", ephemeral=True)
            return
        await interaction.response.send_modal(_RegrasModal(self))

    async def _btn_abrir(self, interaction: discord.Interaction):
        if not self._check_owner(interaction):
            await interaction.response.send_message("❌ Este painel não é seu.", ephemeral=True)
            return
        if not (self.selected_platform and self.selected_game_mode and self.entry_value):
            await interaction.response.send_message(
                "❌ Preencha Plataforma, Tipo e Valor antes de abrir.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        self._finalized = True
        self.stop()

        from services.influencer_live_room_service import influencer_live_room_service
        result = await influencer_live_room_service.ativar_sala(
            guild=interaction.guild,
            influencer=self.influencer,
            platform=self.selected_platform,
            game_mode=self.selected_game_mode,
            entry_value=self.entry_value,
            custom_rules=self.custom_rules,
            ctrl_channel=self.ctrl_channel,
        )

        if not result["ok"]:
            self._finalized = False
            await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)
            return

        channel = result["channel"]
        embed = discord.Embed(
            title="✅ Sala Aberta!",
            description=(
                f"**Canal público:** {channel.mention}\n"
                f"**Plataforma:** `{self.selected_platform}`\n"
                f"**Tipo:** `{self.selected_game_mode}`\n"
                f"**Valor:** R$ `{self.entry_value:.2f}`\n"
                f"**Regras:** {self.custom_rules or 'Padrão do servidor'}"
            ),
            color=discord.Colour.green(),
        )
        for item in self.children:
            item.disabled = True
        if self._setup_msg:
            try:
                await self._setup_msg.edit(view=self)
            except Exception:
                pass
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(
            f"[LiveContra] Sala aberta — {self.influencer.name} "
            f"{self.selected_platform} {self.selected_game_mode} R${self.entry_value:.2f}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# TIMER DE AUTO-DELETE
# ══════════════════════════════════════════════════════════════════════════════

async def _auto_delete_if_idle(
    ctrl_channel: discord.TextChannel,
    setup_view: ContraSetupChannelView,
    influencer: discord.Member,
):
    await asyncio.sleep(SETUP_TTL)
    if setup_view._finalized:
        return
    try:
        await ctrl_channel.send(
            f"⏰ {influencer.mention} Tempo esgotado! O canal será excluído em 10 segundos "
            "por inatividade."
        )
        await asyncio.sleep(10)
        if not setup_view._finalized:
            await ctrl_channel.delete(reason="Setup não concluído em 5 minutos")
            logger.info(f"[LiveContra] Canal de controle excluído por inatividade — {influencer.name}")
    except Exception as e:
        logger.warning(f"[LiveContra] _auto_delete_if_idle erro: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# SELECTS
# ══════════════════════════════════════════════════════════════════════════════

class _PlatformSelect(Select):
    def __init__(self, parent: ContraSetupChannelView):
        super().__init__(
            placeholder="Selecione a Plataforma...",
            options=[
                discord.SelectOption(label="📱 Mobile",    value="Mobile"),
                discord.SelectOption(label="🖥️ Emulador", value="Emulador"),
                discord.SelectOption(label="🔀 Misto",     value="Misto"),
            ],
            custom_id="setup_ctrl_select_platform",
            row=0,
        )
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if not self.parent._check_owner(interaction):
            await interaction.response.send_message("❌ Este painel não é seu.", ephemeral=True)
            return
        self.parent.selected_platform = self.values[0]
        allowed = InfluencerLiveRoom.MODES_BY_PLATFORM.get(
            self.parent.selected_platform, InfluencerLiveRoom.GAME_MODES)
        if self.parent.selected_game_mode not in allowed:
            self.parent.selected_game_mode = None
        await self.parent._update_panel(interaction)


class _GameModeSelect(Select):
    def __init__(self, parent: ContraSetupChannelView):
        modes = InfluencerLiveRoom.MODES_BY_PLATFORM.get(
            parent.selected_platform, InfluencerLiveRoom.GAME_MODES
        ) if parent.selected_platform else InfluencerLiveRoom.GAME_MODES
        super().__init__(
            placeholder="Selecione o Tipo...",
            options=[discord.SelectOption(label=m, value=m) for m in modes],
            custom_id="setup_ctrl_select_gamemode",
            row=1,
        )
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if not self.parent._check_owner(interaction):
            await interaction.response.send_message("❌ Este painel não é seu.", ephemeral=True)
            return
        self.parent.selected_game_mode = self.values[0]
        await self.parent._update_panel(interaction)


# ══════════════════════════════════════════════════════════════════════════════
# MODAIS
# ══════════════════════════════════════════════════════════════════════════════

class _ValorModal(Modal, title="Valor de Entrada"):
    valor = TextInput(
        label="Valor de entrada (R$)",
        placeholder="Ex: 5.00",
        style=discord.TextStyle.short,
        required=True,
        max_length=10,
    )

    def __init__(self, parent: ContraSetupChannelView):
        super().__init__()
        self._parent = parent
        if parent.entry_value:
            self.valor.default = str(parent.entry_value)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.valor.value.strip().replace(",", ".")
        try:
            val = float(raw)
            if val <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Valor inválido. Digite um número maior que zero. Ex: `5.00`",
                ephemeral=True,
            )
            return
        self._parent.entry_value = val
        await self._parent._update_panel(interaction)


class _RegrasModal(Modal, title="Regras da Sala"):
    regras = TextInput(
        label="Regras customizadas (opcional)",
        placeholder="Ex: Sem rush nos primeiros 30s...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
    )

    def __init__(self, parent: ContraSetupChannelView):
        super().__init__()
        self._parent = parent
        if parent.custom_rules:
            self.regras.default = parent.custom_rules

    async def on_submit(self, interaction: discord.Interaction):
        self._parent.custom_rules = self.regras.value or None
        await self._parent._update_panel(interaction)
