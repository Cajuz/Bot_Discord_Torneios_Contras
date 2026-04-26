# channel_service.py
from __future__ import annotations
import discord
from utils.logger import logger


# ── Cargos ────────────────────────────────────────────────
ADM_ROLE_NAME              = "ADM"
CONTROLLER_ROLE_NAME       = "Controller"
SUPPORT_ROLE_NAME          = "Suporte"
ANALYST_ROLE_NAME          = "Analista"
INFLUENCER_ROLE_NAME       = "Influencer"
MEMBER_ROLE_NAME           = "Membro"
SPAM_BLOCK_ROLE_NAME       = "Bloqueado"
VER_TOPICOS_ROLE_NAME      = "Ver Tópicos"
MEDIADOR_ROLE_NAME         = "Mediador"
CONTROLLER_LIVE_ROLE_NAME  = "Controller Live"


PROTECTED_ROLES = {
    CONTROLLER_ROLE_NAME,
    ANALYST_ROLE_NAME,
    SUPPORT_ROLE_NAME,
    INFLUENCER_ROLE_NAME,
    SPAM_BLOCK_ROLE_NAME,
    VER_TOPICOS_ROLE_NAME,
    ADM_ROLE_NAME,
    MEDIADOR_ROLE_NAME,
    CONTROLLER_LIVE_ROLE_NAME,
}


ALL_ROLES = [
    MEMBER_ROLE_NAME,
    VER_TOPICOS_ROLE_NAME,
    CONTROLLER_ROLE_NAME,
    ANALYST_ROLE_NAME,
    SUPPORT_ROLE_NAME,
    INFLUENCER_ROLE_NAME,
    SPAM_BLOCK_ROLE_NAME,
    MEDIADOR_ROLE_NAME,
    CONTROLLER_LIVE_ROLE_NAME,
]


# ── Canais — INFORMAÇÕES ─────────────────────────────────────
REGRAS_CHANNEL            = "🗒️-regras"
BOAS_VINDAS_CHANNEL       = "👋-boas-vindas"
AVISOS_CHANNEL            = "🚨-avisos"
GUIA_JOGADOR_CHANNEL      = "🎮-guia-jogador"
GUIA_MEDIADOR_CHANNEL     = "⚡-guia-mediador"
GUIA_SUPORTE_CHANNEL      = "🎫-guia-suporte"
GUIA_ANALISTA_CHANNEL     = "🔍-guia-analista"
BLACKLIST_CHANNEL         = "⊘-blacklist"


# ── Canais — SUPORTE ────────────────────────────────────────────
SOLICITAR_SUPORTE_CHANNEL  = "🎫-solicitar-suporte"
SUPPORT_CHANNEL_NAME       = SOLICITAR_SUPORTE_CHANNEL
CHAT_SUPORTE_STAFF_CHANNEL = "chat-suporte"
CHAMADOS_CHANNEL_NAME      = "chamados-suporte"
SUPORTE_ADMIN_CHANNEL      = "suporte-controle"


# ── Canais — MEDIAÇÃO ───────────────────────────────────────────
MEDIADOR_PANEL_CHANNEL     = "painel-mediador"
MEDIADORES_ADMIN_CHANNEL   = "𔽝-mediadores-controle"
MEDIADOR_PIX_CHANNEL       = "❖-cadastra-pix"
RENOVACAO_CHANNEL          = "⟳-renovacao-mediadores"
SOLICITACOES_CHANNEL       = "✉-pedido-mediador"
FATURAMENTO_CHANNEL        = "faturamento-mediadores"
HISTORICO_CHANNEL          = "historico-partidas"
CADASTRO_MEDIADOR_CHANNEL  = "📝-cadastro-mediador"


# ── Canais — ANALISTAS ────────────────────────────────────────────
SOLICITAR_ANALISE_CHANNEL  = "solicitar-analise"
CASOS_ANALISAR_CHANNEL     = "casos-analisar"
PAINEL_ANALISTA_CHANNEL    = "painel-analista"
ANALYST_QUEUE_CHANNEL      = PAINEL_ANALISTA_CHANNEL
CHAT_ANALISTAS_CHANNEL     = "chat-analistas"
ANALISTAS_ADMIN_CHANNEL    = "analistas-controle"
EXPOSED_CHANNEL_NAME       = "exposed"
HISTORICO_EXPOSED_CHANNEL  = "historico-exposed"


# ── Canais — COMUNIDADE ───────────────────────────────────────────
INFLUENCERS_CHANNEL        = "influencers"
INFLUENCERS_ADMIN_CHANNEL  = "influencers-controle"
CHAT_INFLUENCERS_CHANNEL   = "chat-influencers"
RANKING_CHANNEL            = "ranking"


# ── Canais — ANALYTICS ────────────────────────────────────────────
DASHBOARD_CHANNEL_NAME     = "dashboard-partidas"
DASHBOARD_MEDIADORES       = "dashboard-mediadores"
DASHBOARD_SUPORTE          = "dashboard-suporte"
DASHBOARD_INFLUENCERS      = "dashboard-influencers"
DASHBOARD_APOSTAS          = "dashboard-apostas"
DASHBOARD_ENTRADAS         = "dashboard-entradas"


# ── Canais — STAFF ────────────────────────────────────────────────
RATE_LIMIT_CHANNEL_NAME     = "rate-limit-logs"
MEMBROS_BLOQUEADOS_CHANNEL  = "⊘-membros-bloqueados"
LOGS_PARTIDAS_CHANNEL       = "📝-logs-partidas"
LOGS_MEDIADORES_CHANNEL     = "📝-logs-mediadores"
LOGS_BOT_CHANNEL_NAME       = "📝-logs-bot"
LOGS_PIX_LOG_CHANNEL        = "📝-logs-pix"
LOGS_CALL_CHANNEL           = "📝-logs-call"
LOGS_COMMAND_CHANNEL        = "📝-logs-command"
LOGS_MESSAGE_DELETE_CHANNEL = "📝-logs-message-delete"
LOGS_TROCA_CARGO_CHANNEL    = "📝-logs-troca-cargo"
MEDIADORES_AFKS_CHANNEL     = "mediadores-afks"
HEALTH_CHECK_CHANNEL        = "health-check"
LOGS_TESTS_CHANNEL          = "logs-tests"
LOGS_PAGAMENTOS_CHANNEL     = "logs-pagamentos"


# ── Canais — CONTRAS (Influencer Live) ────────────────────────────
CATEGORY_CONTRAS             = "⚔️| CONTRAS"
MEDIADOR_LIVE_PANEL_CHANNEL  = "painel-mediador-live"
LIVE_CONTRA_CHANNEL          = "live-contra"   # ← canal de criação de sala (só Influencer/ADM)


# ── Aliases legados ────────────────────────────────────────────────
CATEGORY_ANALYTICS_NAME      = "📊 | ANALYTICS"
EXPOSED_CHANNEL              = EXPOSED_CHANNEL_NAME
RATE_LIMIT_CHANNEL           = RATE_LIMIT_CHANNEL_NAME
LOGS_BOT_CHANNEL             = LOGS_BOT_CHANNEL_NAME
GUIDE_PLAYER_CHANNEL         = GUIA_JOGADOR_CHANNEL
GUIDE_MEDIATOR_CHANNEL       = GUIA_MEDIADOR_CHANNEL
GUIDE_SUPPORT_CHANNEL        = GUIA_SUPORTE_CHANNEL
GUIDE_ANALYST_CHANNEL        = GUIA_ANALISTA_CHANNEL
LOGS_CALLS_CHANNEL           = LOGS_CALL_CHANNEL
LOGS_TROCA_PIX_CHANNEL       = LOGS_PIX_LOG_CHANNEL
LOGS_DELETES_CHANNEL         = LOGS_MESSAGE_DELETE_CHANNEL
LOGS_COMANDOS_CHANNEL        = LOGS_COMMAND_CHANNEL
ALERTAS_ADM_CHANNEL          = "alertas-adm"
HISTORICO_CARGOS_CHANNEL     = LOGS_TROCA_CARGO_CHANNEL
CONVITES_CHANNEL             = "convites"
INVITE_CHANNEL_NAME          = CONVITES_CHANNEL
INVITE_CHANNEL               = CONVITES_CHANNEL
STATUS_BOT_CHANNEL           = HEALTH_CHECK_CHANNEL
PAINEL_SUPORTE_CHANNEL       = "painel-suporte"
APROVAR_MEDIADORES_CHANNEL   = "✔-aprovar-mediadores"
RESULTADOS_CHANNEL           = "resultados"


# ── Categorias ──────────────────────────────────────────────────────
CATEGORY_INFORMACOES = "📋 | INFORMAÇÕES"
CATEGORY_MOBILE      = "📱 | MOBILE"
CATEGORY_EMULADOR    = "🖥️ | EMULADOR"
CATEGORY_MISTO       = "🔀 | MISTO"
CATEGORY_SUPORTE     = "🎫 | SUPORTE"
CATEGORY_MEDIACAO    = "⚡ | MEDIAÇÃO"
CATEGORY_ANALISTAS   = "🔍 | ANALISTAS"
CATEGORY_ANALYTICS   = "📊 | ANALYTICS"
CATEGORY_COMUNIDADE  = "🏆 | COMUNIDADE"
CATEGORY_STAFF       = "🔐 | STAFF"
CATEGORY_LOGS        = "📝 | LOGS"


# ── Estrutura de canais por categoria ─────────────────────────────────
CHANNEL_STRUCTURE: dict[str, list[str]] = {
    CATEGORY_INFORMACOES: [
        REGRAS_CHANNEL, BOAS_VINDAS_CHANNEL, AVISOS_CHANNEL,
        GUIA_JOGADOR_CHANNEL, GUIA_MEDIADOR_CHANNEL,
        GUIA_SUPORTE_CHANNEL, GUIA_ANALISTA_CHANNEL,
        BLACKLIST_CHANNEL,
    ],
    CATEGORY_MEDIACAO: [
        MEDIADOR_PANEL_CHANNEL, MEDIADORES_ADMIN_CHANNEL,
        SOLICITACOES_CHANNEL, MEDIADOR_PIX_CHANNEL,
        RENOVACAO_CHANNEL, FATURAMENTO_CHANNEL,
        HISTORICO_CHANNEL,
        CADASTRO_MEDIADOR_CHANNEL,
    ],
    CATEGORY_MOBILE:   ["📱1x1-mob", "📱2x2-mob", "📱3x3-mob", "📱4x4-mob"],
    CATEGORY_EMULADOR: ["🖥️1x1-emu", "🖥️2x2-emu", "🖥️3x3-emu", "🖥️4x4-emu"],
    CATEGORY_MISTO:    ["🔀4x4-misto", "🔀3x3-misto", "🔀2x2-misto"],
    CATEGORY_SUPORTE: [
        SOLICITAR_SUPORTE_CHANNEL,
        CHAMADOS_CHANNEL_NAME,
        CHAT_SUPORTE_STAFF_CHANNEL,
        SUPORTE_ADMIN_CHANNEL,
    ],
    CATEGORY_ANALISTAS: [
        SOLICITAR_ANALISE_CHANNEL,
        CASOS_ANALISAR_CHANNEL,
        PAINEL_ANALISTA_CHANNEL,
        CHAT_ANALISTAS_CHANNEL,
        ANALISTAS_ADMIN_CHANNEL,
        EXPOSED_CHANNEL_NAME,
        HISTORICO_EXPOSED_CHANNEL,
    ],
    CATEGORY_COMUNIDADE: [
        INFLUENCERS_CHANNEL,
        INFLUENCERS_ADMIN_CHANNEL,
        CHAT_INFLUENCERS_CHANNEL,
        RANKING_CHANNEL,
    ],
    CATEGORY_ANALYTICS: [
        DASHBOARD_CHANNEL_NAME, DASHBOARD_MEDIADORES,
        DASHBOARD_SUPORTE, DASHBOARD_INFLUENCERS,
        DASHBOARD_APOSTAS, DASHBOARD_ENTRADAS,
    ],
    CATEGORY_STAFF: [
        RATE_LIMIT_CHANNEL_NAME,
        MEMBROS_BLOQUEADOS_CHANNEL,
        HEALTH_CHECK_CHANNEL,
        MEDIADORES_AFKS_CHANNEL,
    ],
    CATEGORY_LOGS: [
        LOGS_PARTIDAS_CHANNEL, LOGS_MEDIADORES_CHANNEL, LOGS_BOT_CHANNEL_NAME,
        LOGS_COMMAND_CHANNEL, LOGS_MESSAGE_DELETE_CHANNEL, LOGS_PIX_LOG_CHANNEL,
        LOGS_CALL_CHANNEL, LOGS_TROCA_CARGO_CHANNEL,
        ALERTAS_ADM_CHANNEL,
        LOGS_TESTS_CHANNEL,
        LOGS_PAGAMENTOS_CHANNEL,
    ],
    # live-contra  → canal fixo de criação de salas (só Influencer vê)
    # painel-mediador-live → canal fixo Controller Live
    # contra-*     → criados/destruídos dinamicamente
    # control-contra-* → criados/destruídos dinamicamente
    CATEGORY_CONTRAS: [
        LIVE_CONTRA_CHANNEL,
        MEDIADOR_LIVE_PANEL_CHANNEL,
    ],
}


# ── Canais apenas-leitura para todos (Membro + demais) ────────────────────
READ_ONLY_CHANNELS = {
    REGRAS_CHANNEL, BOAS_VINDAS_CHANNEL,
    AVISOS_CHANNEL,
}


# ── Canais de interação por botão ────────────────────────────────────────
INTERACTION_ONLY_CHANNELS = {
    "📱1x1-mob", "📱2x2-mob", "📱3x3-mob", "📱4x4-mob",
    "🖥️1x1-emu", "🖥️2x2-emu", "🖥️3x3-emu", "🖥️4x4-emu",
    "🔀4x4-misto", "🔀3x3-misto", "🔀2x2-misto",
    SOLICITAR_SUPORTE_CHANNEL,
    BLACKLIST_CHANNEL,
    RANKING_CHANNEL,
}


# ── Canais view-only (só bot/ADM postam, cargos listados apenas leem) ─────
CHANNEL_VIEW_ONLY: dict[str, list[str]] = {
    GUIA_JOGADOR_CHANNEL:       [MEMBER_ROLE_NAME, ADM_ROLE_NAME],
    GUIA_MEDIADOR_CHANNEL:      [CONTROLLER_ROLE_NAME, ADM_ROLE_NAME],
    GUIA_SUPORTE_CHANNEL:       [SUPPORT_ROLE_NAME, ADM_ROLE_NAME],
    GUIA_ANALISTA_CHANNEL:      [ANALYST_ROLE_NAME, ADM_ROLE_NAME],
    CASOS_ANALISAR_CHANNEL:     [ANALYST_ROLE_NAME, ADM_ROLE_NAME],
    PAINEL_ANALISTA_CHANNEL:    [ANALYST_ROLE_NAME, ADM_ROLE_NAME],
    HISTORICO_EXPOSED_CHANNEL:  [ANALYST_ROLE_NAME, ADM_ROLE_NAME],
    HISTORICO_CHANNEL:          [ADM_ROLE_NAME],
    RENOVACAO_CHANNEL:          [CONTROLLER_ROLE_NAME, ADM_ROLE_NAME],
    SOLICITACOES_CHANNEL:       [MEMBER_ROLE_NAME, ADM_ROLE_NAME],
    FATURAMENTO_CHANNEL:        [CONTROLLER_ROLE_NAME, ADM_ROLE_NAME],
    MEDIADORES_AFKS_CHANNEL:    [ADM_ROLE_NAME],
    HEALTH_CHECK_CHANNEL:       [ADM_ROLE_NAME],
    LOGS_CALL_CHANNEL:           [ADM_ROLE_NAME],
    LOGS_TROCA_CARGO_CHANNEL:    [ADM_ROLE_NAME],
    LOGS_MESSAGE_DELETE_CHANNEL: [ADM_ROLE_NAME],
    LOGS_COMMAND_CHANNEL:        [ADM_ROLE_NAME],
    LOGS_PIX_LOG_CHANNEL:        [ADM_ROLE_NAME],
    LOGS_PARTIDAS_CHANNEL:       [ADM_ROLE_NAME],
    LOGS_MEDIADORES_CHANNEL:     [ADM_ROLE_NAME],
    LOGS_BOT_CHANNEL_NAME:       [ADM_ROLE_NAME],
    ALERTAS_ADM_CHANNEL:         [ADM_ROLE_NAME],
    LOGS_TESTS_CHANNEL:          [ADM_ROLE_NAME],
    LOGS_PAGAMENTOS_CHANNEL:     [ADM_ROLE_NAME],
    # Contras — painéis fixos
    MEDIADOR_LIVE_PANEL_CHANNEL: [CONTROLLER_LIVE_ROLE_NAME, ADM_ROLE_NAME],
    # live-contra — Influencer interage via botões, não digita
    LIVE_CONTRA_CHANNEL:         [INFLUENCER_ROLE_NAME, ADM_ROLE_NAME],
}


# ── Canais onde roles podem enviar mensagens ───────────────────────────────
CHANNEL_PERMISSIONS: dict[str, list[str]] = {
    CHAMADOS_CHANNEL_NAME:      [SUPPORT_ROLE_NAME, ADM_ROLE_NAME],
    SUPORTE_ADMIN_CHANNEL:      [ADM_ROLE_NAME],
    CHAT_SUPORTE_STAFF_CHANNEL: [SUPPORT_ROLE_NAME, CONTROLLER_ROLE_NAME, ADM_ROLE_NAME],
    MEDIADOR_PANEL_CHANNEL:     [ADM_ROLE_NAME],
    MEDIADORES_ADMIN_CHANNEL:   [ADM_ROLE_NAME],
    MEDIADOR_PIX_CHANNEL:       [CONTROLLER_ROLE_NAME, ADM_ROLE_NAME],
    CADASTRO_MEDIADOR_CHANNEL:  [ADM_ROLE_NAME],
    SOLICITAR_ANALISE_CHANNEL:  [CONTROLLER_ROLE_NAME, ADM_ROLE_NAME],
    ANALISTAS_ADMIN_CHANNEL:    [ADM_ROLE_NAME],
    EXPOSED_CHANNEL_NAME:       [ADM_ROLE_NAME],
    CHAT_ANALISTAS_CHANNEL:     [ANALYST_ROLE_NAME, ADM_ROLE_NAME],
    INFLUENCERS_CHANNEL:        [INFLUENCER_ROLE_NAME, ADM_ROLE_NAME],
    INFLUENCERS_ADMIN_CHANNEL:  [ADM_ROLE_NAME],
    CHAT_INFLUENCERS_CHANNEL:   [INFLUENCER_ROLE_NAME, ADM_ROLE_NAME],
    BOAS_VINDAS_CHANNEL:        [],
    REGRAS_CHANNEL:             [],
}


# ── PermissionService ──────────────────────────────────────────────────────
class PermissionService:

    async def get_channel_overwrites(
        self, guild: discord.Guild, channel_name: str, roles: dict | None = None
    ) -> dict:
        roles       = roles or {r.name: r for r in guild.roles}
        member_role = roles.get(MEMBER_ROLE_NAME)
        overwrites  = {guild.default_role: discord.PermissionOverwrite(read_messages=False)}

        if channel_name in INTERACTION_ONLY_CHANNELS:
            target = member_role or guild.default_role
            overwrites[target] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=False,
                use_application_commands=True,
            )
            if member_role:
                overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=False)

        elif channel_name in READ_ONLY_CHANNELS:
            target = member_role or guild.default_role
            overwrites[target] = discord.PermissionOverwrite(
                read_messages=True, send_messages=False)
            if member_role:
                overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=False)

        elif channel_name in CHANNEL_VIEW_ONLY:
            viewers = CHANNEL_VIEW_ONLY[channel_name]
            for role_name in viewers:
                role = roles.get(role_name) or discord.utils.get(guild.roles, name=role_name)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True, send_messages=False,
                        use_application_commands=True)

        else:
            perms = CHANNEL_PERMISSIONS.get(channel_name)
            if perms is None:
                target = member_role or guild.default_role
                overwrites[target] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=False)
                if member_role:
                    overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=False)
            elif perms == []:
                if member_role:
                    overwrites[member_role] = discord.PermissionOverwrite(
                        read_messages=True, send_messages=False)
            else:
                for role_name in perms:
                    role = roles.get(role_name) or discord.utils.get(guild.roles, name=role_name)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(
                            read_messages=True, send_messages=True)

        overwrites[guild.me] = discord.PermissionOverwrite(
            read_messages=True, send_messages=True, manage_messages=True)
        adm_role = roles.get(ADM_ROLE_NAME) or discord.utils.get(guild.roles, name=ADM_ROLE_NAME)
        if adm_role:
            overwrites[adm_role] = discord.PermissionOverwrite(
                read_messages=True, send_messages=True,
                manage_messages=True, manage_channels=True)

        return overwrites

    async def get_category_overwrites(
        self, guild: discord.Guild, category_name: str, roles: dict | None = None
    ) -> dict:
        roles = roles or {r.name: r for r in guild.roles}
        restricted_cats = {
            CATEGORY_STAFF, CATEGORY_LOGS, CATEGORY_ANALYTICS,
            CATEGORY_ANALISTAS, CATEGORY_MEDIACAO,
            CATEGORY_CONTRAS,
        }
        if category_name in restricted_cats:
            overwrites = {guild.default_role: discord.PermissionOverwrite(
                read_messages=False, send_messages=False)}

            if category_name == CATEGORY_CONTRAS:
                # FIX: use_application_commands=True garante que botões funcionem
                # mesmo com send_messages=False na categoria.

                # Controller Live vê a categoria inteira (painel-mediador-live)
                cl_role = roles.get(CONTROLLER_LIVE_ROLE_NAME) or discord.utils.get(
                    guild.roles, name=CONTROLLER_LIVE_ROLE_NAME)
                if cl_role:
                    overwrites[cl_role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=False,
                        use_application_commands=True,
                    )

                # Influencer vê (live-contra + seus canais control-contra-*)
                inf_role = roles.get(INFLUENCER_ROLE_NAME) or discord.utils.get(
                    guild.roles, name=INFLUENCER_ROLE_NAME)
                if inf_role:
                    overwrites[inf_role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=False,
                        use_application_commands=True,
                    )

                # Membro precisa ver a categoria para acessar canais contra-*
                member_role = roles.get(MEMBER_ROLE_NAME)
                if member_role:
                    overwrites[member_role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=False,
                        use_application_commands=True,
                    )

            return overwrites

        member_role = roles.get(MEMBER_ROLE_NAME)
        base = {guild.default_role: discord.PermissionOverwrite(read_messages=False)}
        if member_role:
            base[member_role] = discord.PermissionOverwrite(read_messages=True)
        return base

    async def add_user_to_channel(
        self, channel: discord.TextChannel, member: discord.Member, can_send: bool = True
    ):
        ow = channel.overwrites_for(member)
        ow.read_messages = True
        ow.send_messages = can_send
        await channel.set_permissions(member, overwrite=ow)

    async def remove_user_from_channel(
        self, channel: discord.TextChannel, member: discord.Member
    ):
        await channel.set_permissions(member, overwrite=None)

    # ── contra-<username> ─────────────────────────────────────────────────

    async def get_contra_channel_overwrites(
        self,
        guild: discord.Guild,
        influencer: discord.Member,
        roles: dict | None = None,
    ) -> dict:
        """
        Permissões para canais contra-<username>.
        Membro → lê + usa botões | Influencer + Controller Live → lê + envia | ADM/Bot → total
        """
        roles      = roles or {r.name: r for r in guild.roles}
        overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False)}

        member_role = roles.get(MEMBER_ROLE_NAME)
        if member_role:
            overwrites[member_role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=False,
                use_application_commands=True,
            )

        overwrites[influencer] = discord.PermissionOverwrite(
            read_messages=True, send_messages=True)

        cl_role = roles.get(CONTROLLER_LIVE_ROLE_NAME) or discord.utils.get(
            guild.roles, name=CONTROLLER_LIVE_ROLE_NAME)
        if cl_role:
            overwrites[cl_role] = discord.PermissionOverwrite(
                read_messages=True, send_messages=True)

        overwrites[guild.me] = discord.PermissionOverwrite(
            read_messages=True, send_messages=True, manage_messages=True)
        adm_role = roles.get(ADM_ROLE_NAME) or discord.utils.get(guild.roles, name=ADM_ROLE_NAME)
        if adm_role:
            overwrites[adm_role] = discord.PermissionOverwrite(
                read_messages=True, send_messages=True,
                manage_messages=True, manage_channels=True)

        return overwrites

    async def create_contra_channel(
        self,
        guild: discord.Guild,
        influencer: discord.Member,
    ) -> discord.TextChannel:
        """Cria o canal contra-<username> na categoria ⚔️| CONTRAS."""
        channel_name = f"contra-{influencer.display_name.lower().replace(' ', '-')}"
        existing     = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            logger.info(f"[ChannelService] Canal já existe: #{channel_name}")
            return existing

        category = discord.utils.get(guild.categories, name=CATEGORY_CONTRAS)
        if not category:
            roles    = {r.name: r for r in guild.roles}
            cat_ow   = await self.get_category_overwrites(guild, CATEGORY_CONTRAS, roles)
            category = await guild.create_category(CATEGORY_CONTRAS, overwrites=cat_ow)

        roles      = {r.name: r for r in guild.roles}
        overwrites = await self.get_contra_channel_overwrites(guild, influencer, roles)
        channel    = await guild.create_text_channel(
            channel_name, category=category, overwrites=overwrites)
        logger.info(f"[ChannelService] Canal contra criado: #{channel_name}")
        return channel

    async def delete_contra_channel(
        self,
        guild: discord.Guild,
        channel_name: str,
    ) -> bool:
        ch = discord.utils.get(guild.text_channels, name=channel_name)
        if not ch:
            logger.warning(f"[ChannelService] Canal não encontrado para deletar: #{channel_name}")
            return False
        await ch.delete(reason="Sala Influencer Live desativada")
        logger.info(f"[ChannelService] Canal contra deletado: #{channel_name}")
        return True

    # ── control-contra-<username> ─────────────────────────────────────────

    async def get_control_channel_overwrites(
        self,
        guild: discord.Guild,
        influencer: discord.Member,
        roles: dict | None = None,
    ) -> dict:
        """
        Permissões para canais control-contra-<username>.
        Apenas o influencer dono, Bot e ADM têm acesso. Mais ninguém.
        """
        roles      = roles or {r.name: r for r in guild.roles}
        overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False)}

        # Só o influencer específico que criou a sala
        overwrites[influencer] = discord.PermissionOverwrite(
            read_messages=True, send_messages=False,
            use_application_commands=True)

        overwrites[guild.me] = discord.PermissionOverwrite(
            read_messages=True, send_messages=True, manage_messages=True)
        adm_role = roles.get(ADM_ROLE_NAME) or discord.utils.get(guild.roles, name=ADM_ROLE_NAME)
        if adm_role:
            overwrites[adm_role] = discord.PermissionOverwrite(
                read_messages=True, send_messages=True,
                manage_messages=True, manage_channels=True)

        return overwrites

    async def create_control_channel(
        self,
        guild: discord.Guild,
        influencer: discord.Member,
    ) -> discord.TextChannel:
        """Cria o canal control-contra-<username> na categoria ⚔️| CONTRAS."""
        channel_name = f"control-contra-{influencer.display_name.lower().replace(' ', '-')}"
        existing     = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            logger.info(f"[ChannelService] Canal já existe: #{channel_name}")
            return existing

        category = discord.utils.get(guild.categories, name=CATEGORY_CONTRAS)
        if not category:
            roles    = {r.name: r for r in guild.roles}
            cat_ow   = await self.get_category_overwrites(guild, CATEGORY_CONTRAS, roles)
            category = await guild.create_category(CATEGORY_CONTRAS, overwrites=cat_ow)

        roles      = {r.name: r for r in guild.roles}
        overwrites = await self.get_control_channel_overwrites(guild, influencer, roles)
        channel    = await guild.create_text_channel(
            channel_name, category=category, overwrites=overwrites)
        logger.info(f"[ChannelService] Canal control-contra criado: #{channel_name}")
        return channel

    async def delete_control_channel(
        self,
        guild: discord.Guild,
        channel_name: str,
    ) -> bool:
        ch = discord.utils.get(guild.text_channels, name=channel_name)
        if not ch:
            logger.warning(f"[ChannelService] Canal não encontrado para deletar: #{channel_name}")
            return False
        await ch.delete(reason="Sala Influencer Live desativada")
        logger.info(f"[ChannelService] Canal control-contra deletado: #{channel_name}")
        return True


permission_service = PermissionService()
