"""
live_contra_setup_view.py
View postada no canal #live-contra.
Permite ao Influencer configurar e criar sua sala no modo contra.

Fluxo:
  1. Influencer seleciona Plataforma (Mobile / Emulador / Misto)
  2. Influencer seleciona Tipo (1x1 / 2x2 / 3x3 / 4x4)
     → opções filtradas por plataforma (Misto não tem 1x1)
  3. Clica em "📋 Regras" → Modal → preenche regras (opcional)
  4. Clica em "💰 Valor"  → Modal → preenche valor de entrada
  5. Botão "⚔️ Criar Sala" é liberado → cria os canais e a sala
"""
from __future__ import annotations
import discord
from discord.ui import View, Select, Button, Modal, TextInput
from models.influencer_live_room import InfluencerLiveRoom
from utils.logger import logger
from utils.datetime_utils import utcnow

THEME_LIVE = 0xE91E63


# ══════════════════════════════════════════════════════════════════════════════
# EMBED DO CANAL live-contra
# ══════════════════════════════════════════════════════════════════════════════

def build_live_contra_embed() -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ Criar Sala — Modo Contra",
        description=(
            "Configure sua sala para receber desafiantes ao vivo.\n\n"
            "**Como funciona:**\n"
            "1️⃣ Selecione a **Plataforma** e o **Tipo** de partida\n"
            "2️⃣ Clique em **Regras** para definir regras customizadas *(opcional)*\n"
            "3️⃣ Clique em **Valor** para definir o valor de entrada *(obrigatório)*\n"
            "4️⃣ Clique em **Criar Sala** para abrir a fila\n\n"
            "Será criado um canal `control-contra-você` *(só você e ADM veem)* "
            "e um canal `contra-você` *(público para membros entrarem na fila)*."
        ),
        color=THEME_LIVE,
        timestamp=utcnow(),
    )
    embed.set_footer(text="SOLAR E-SPORTS · Modo Contra · Apenas Influencers")
    return embed


# ══════════════════════════════════════════════════════════════════════════════
# MODAIS
# ══════════════════════════════════════════════════════════════════════════════

class RegrasModal(Modal, title="Regras da Sala"):
    regras = TextInput(
        label="Regras customizadas",
        placeholder="Ex: Sem rush nos primeiros 30s, mapa aleatório...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Armazena no state da view via custom_id trick — usamos o parent view
        view: LiveContraSetupView = interaction.message  # será resolvido no callback
        await interaction.response.defer()


class ValorModal(Modal, title="Valor de Entrada"):
    valor = TextInput(
        label="Valor de entrada (R$)",
        placeholder="Ex: 5.00",
        style=discord.TextStyle.short,
        required=True,
        max_length=10,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()


# ══════════════════════════════════════════════════════════════════════════════
# VIEW PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class LiveContraSetupView(View):
    """
    Painel fixo no canal #live-contra.
    Estado mantido por instância — cada influencer interage com a mesma
    mensagem mas o bot responde em ephemeral com uma view de sessão.
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
                f"❌ Você já tem uma sala ativa (`{room.platform} · {room.game_mode}`).\n"
                f"Acesse seu canal de controle para gerenciá-la ou desativá-la.",
                ephemeral=True,
            )
            return

        # Abre a view de sessão ephemeral
        session_view = LiveContraSessionView(
            influencer_id=interaction.user.id,
            guild_id=interaction.guild_id,
        )
        embed = discord.Embed(
            title="⚔️ Configurar Sala — Modo Contra",
            description=(
                "Selecione a plataforma e o tipo, depois defina **Valor** "
                "e opcionalmente as **Regras**.\n\n"
                "Quando tudo estiver preenchido, o botão **Criar Sala** será liberado."
            ),
            color=THEME_LIVE,
        )
        await interaction.response.send_message(embed=embed, view=session_view, ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW DE SESSÃO (ephemeral — por influencer)
# ══════════════════════════════════════════════════════════════════════════════

class LiveContraSessionView(View):
    """
    View ephemeral de configuração da sala.
    Mantém estado da seleção até o influencer clicar em Criar.
    """

    def __init__(self, influencer_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.influencer_id = influencer_id
        self.guild_id      = guild_id

        # Estado da sessão
        self.selected_platform: str | None = None
        self.selected_game_mode: str | None = None
        self.entry_value: float | None = None
        self.custom_rules: str | None = None

        # Adiciona os selects
        self.add_item(PlatformSelect())
        self.add_item(GameModeSelect())
        self._refresh_criar_button()

    def _refresh_criar_button(self):
        """Remove e re-adiciona o botão Criar com estado atualizado."""
        # Remove botões existentes (não selects)
        self.children = [c for c in self.children if isinstance(c, Select)]

        can_create = (
            self.selected_platform is not None
            and self.selected_game_mode is not None
            and self.entry_value is not None
        )

        regras_btn = Button(
            label="📋 Regras" + (" ✅" if self.custom_rules is not None else ""),
            style=discord.ButtonStyle.secondary,
            custom_id="session_regras",
            row=2,
        )
        regras_btn.callback = self.btn_regras

        valor_btn = Button(
            label="💰 Valor" + (f" ✅ R${self.entry_value:.2f}" if self.entry_value else ""),
            style=discord.ButtonStyle.primary if self.entry_value is None else discord.ButtonStyle.secondary,
            custom_id="session_valor",
            row=2,
        )
        valor_btn.callback = self.btn_valor

        criar_btn = Button(
            label="⚔️ Criar Sala",
            style=discord.ButtonStyle.danger,
            custom_id="session_criar",
            disabled=not can_create,
            row=3,
        )
        criar_btn.callback = self.btn_criar

        self.add_item(regras_btn)
        self.add_item(valor_btn)
        self.add_item(criar_btn)

    # ── Callbacks dos botões ──────────────────────────────────────────────

    async def btn_regras(self, interaction: discord.Interaction):
        if interaction.user.id != self.influencer_id:
            await interaction.response.send_message("❌ Esta sessão não é sua.", ephemeral=True)
            return

        modal = _RegrasModalSession(session_view=self)
        await interaction.response.send_modal(modal)

    async def btn_valor(self, interaction: discord.Interaction):
        if interaction.user.id != self.influencer_id:
            await interaction.response.send_message("❌ Esta sessão não é sua.", ephemeral=True)
            return

        modal = _ValorModalSession(session_view=self)
        await interaction.response.send_modal(modal)

    async def btn_criar(self, interaction: discord.Interaction):
        if interaction.user.id != self.influencer_id:
            await interaction.response.send_message("❌ Esta sessão não é sua.", ephemeral=True)
            return

        if not self.selected_platform or not self.selected_game_mode or not self.entry_value:
            await interaction.response.send_message(
                "❌ Preencha plataforma, tipo e valor antes de criar.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        from services.influencer_live_room_service import influencer_live_room_service

        result = await influencer_live_room_service.ativar_sala(
            guild=interaction.guild,
            influencer=interaction.user,
            platform=self.selected_platform,
            game_mode=self.selected_game_mode,
            entry_value=self.entry_value,
            custom_rules=self.custom_rules,
        )

        if not result["ok"]:
            await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)
            return

        room    = result["room"]
        channel = result["channel"]
        ctrl    = result["control_channel"]

        embed = discord.Embed(
            title="✅ Sala Criada!",
            description=(
                f"Sua sala foi aberta com sucesso.\n\n"
                f"**Canal público:** {channel.mention}\n"
                f"**Canal de controle:** {ctrl.mention}\n\n"
                f"**Plataforma:** `{room.platform}`\n"
                f"**Tipo:** `{room.game_mode}`\n"
                f"**Valor:** R$ `{room.entry_value:.2f}`\n"
                f"**Regras:** {room.custom_rules or 'Padrão do servidor'}"
            ),
            color=discord.Colour.green(),
        )
        self.stop()
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(
            f"[LiveContra] Sala criada via live-contra — "
            f"{interaction.user.name} {self.selected_platform} {self.selected_game_mode}"
        )

    async def _update_message(self, interaction: discord.Interaction):
        """Atualiza a mensagem ephemeral com o estado atual."""
        self._refresh_criar_button()
        plat = self.selected_platform or "—"
        modo = self.selected_game_mode or "—"
        val  = f"R$ {self.entry_value:.2f}" if self.entry_value else "—"
        reg  = self.custom_rules[:40] + "…" if self.custom_rules and len(self.custom_rules) > 40 else (self.custom_rules or "—")

        embed = discord.Embed(
            title="⚔️ Configurar Sala — Modo Contra",
            color=THEME_LIVE,
        )
        embed.add_field(name="Plataforma", value=f"`{plat}`", inline=True)
        embed.add_field(name="Tipo",       value=f"`{modo}`", inline=True)
        embed.add_field(name="Valor",      value=f"`{val}`",  inline=True)
        embed.add_field(name="Regras",     value=f"`{reg}`",  inline=False)

        can_create = (
            self.selected_platform is not None
            and self.selected_game_mode is not None
            and self.entry_value is not None
        )
        if can_create:
            embed.description = "✅ Tudo pronto! Clique em **Criar Sala** para abrir a fila."
        else:
            missing = []
            if not self.selected_platform:  missing.append("Plataforma")
            if not self.selected_game_mode: missing.append("Tipo")
            if not self.entry_value:        missing.append("Valor")
            embed.description = f"Faltando: **{', '.join(missing)}**"

        await interaction.edit_original_response(embed=embed, view=self)


# ── Selects ───────────────────────────────────────────────────────────────────

class PlatformSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="📱 Mobile",    value="Mobile",   description="Free Fire Mobile"),
            discord.SelectOption(label="🖥️ Emulador", value="Emulador", description="Free Fire Emulador"),
            discord.SelectOption(label="🔀 Misto",     value="Misto",    description="Mobile vs Emulador (sem 1x1)"),
        ]
        super().__init__(
            placeholder="Selecione a Plataforma...",
            options=options,
            custom_id="session_select_platform",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        view: LiveContraSessionView = self.view
        if interaction.user.id != view.influencer_id:
            await interaction.response.send_message("❌ Esta sessão não é sua.", ephemeral=True)
            return

        view.selected_platform = self.values[0]
        # Se o modo selecionado for incompatível com a nova plataforma, limpa
        if view.selected_game_mode:
            allowed = InfluencerLiveRoom.MODES_BY_PLATFORM.get(view.selected_platform, InfluencerLiveRoom.GAME_MODES)
            if view.selected_game_mode not in allowed:
                view.selected_game_mode = None

        # Atualiza as opções do GameModeSelect
        for item in view.children:
            if isinstance(item, GameModeSelect):
                item._update_options(view.selected_platform)
                break

        await view._update_message(interaction)


class GameModeSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Selecione o Tipo...",
            options=self._build_options(None),
            custom_id="session_select_gamemode",
            row=1,
        )

    def _build_options(self, platform: str | None) -> list[discord.SelectOption]:
        if platform:
            modes = InfluencerLiveRoom.MODES_BY_PLATFORM.get(platform, InfluencerLiveRoom.GAME_MODES)
        else:
            modes = InfluencerLiveRoom.GAME_MODES
        return [discord.SelectOption(label=m, value=m) for m in modes]

    def _update_options(self, platform: str | None):
        self.options = self._build_options(platform)

    async def callback(self, interaction: discord.Interaction):
        view: LiveContraSessionView = self.view
        if interaction.user.id != view.influencer_id:
            await interaction.response.send_message("❌ Esta sessão não é sua.", ephemeral=True)
            return

        view.selected_game_mode = self.values[0]
        await view._update_message(interaction)


# ── Modais internos da sessão ─────────────────────────────────────────────────

class _RegrasModalSession(Modal, title="Regras da Sala"):
    regras = TextInput(
        label="Regras customizadas (opcional)",
        placeholder="Ex: Sem rush nos primeiros 30s, mapa aleatório...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
    )

    def __init__(self, session_view: LiveContraSessionView):
        super().__init__()
        self._session = session_view
        if session_view.custom_rules:
            self.regras.default = session_view.custom_rules

    async def on_submit(self, interaction: discord.Interaction):
        self._session.custom_rules = self.regras.value or None
        await self._session._update_message(interaction)


class _ValorModalSession(Modal, title="Valor de Entrada"):
    valor = TextInput(
        label="Valor de entrada (R$)",
        placeholder="Ex: 5.00",
        style=discord.TextStyle.short,
        required=True,
        max_length=10,
    )

    def __init__(self, session_view: LiveContraSessionView):
        super().__init__()
        self._session = session_view
        if session_view.entry_value:
            self.valor.default = str(session_view.entry_value)

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

        self._session.entry_value = val
        await self._session._update_message(interaction)