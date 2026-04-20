# channel_service.py
from __future__ import annotations
import discord
from utils.logger import logger

# ── Cargos ────────────────────────────────────────────────
ADM_ROLE_NAME         = "ADM"
CONTROLLER_ROLE_NAME  = "Controller"
SUPPORT_ROLE_NAME     = "Suporte"
ANALYST_ROLE_NAME     = "Analista"
INFLUENCER_ROLE_NAME  = "Influencer"
MEMBER_ROLE_NAME      = "Membro"
SPAM_BLOCK_ROLE_NAME  = "Bloqueado"
VER_TOPICOS_ROLE_NAME = "Ver Tópicos"
MEDIADOR_ROLE_NAME    = "Mediador"

PROTECTED_ROLES = {
    CONTROLLER_ROLE_NAME,
    ANALYST_ROLE_NAME,
    SUPPORT_ROLE_NAME,
    INFLUENCER_ROLE_NAME,
    SPAM_BLOCK_ROLE_NAME,
    VER_TOPICOS_ROLE_NAME,
    ADM_ROLE_NAME,
    MEDIADOR_ROLE_NAME,
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
# PAINEL_SUPORTE_CHANNEL removido (canal deletado)

# ── Canais — MEDIAÇÃO ───────────────────────────────────────────
MEDIADOR_PANEL_CHANNEL     = "painel-mediador"
MEDIADORES_ADMIN_CHANNEL   = "𔽝-mediadores-controle"
MEDIADOR_PIX_CHANNEL       = "❖-cadastra-pix"
RENOVACAO_CHANNEL          = "⟳-renovacao-mediadores"
SOLICITACOES_CHANNEL       = "✉-pedido-mediador"
FATURAMENTO_CHANNEL        = "faturamento-mediadores"
# APROVAR_MEDIADORES_CHANNEL removido (canal deletado)
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
CONVITES_CHANNEL           = "convites"
INFLUENCERS_CHANNEL        = "influencers"
INFLUENCERS_ADMIN_CHANNEL  = "influencers-controle"
CHAT_INFLUENCERS_CHANNEL   = "chat-influencers"
RANKING_CHANNEL            = "ranking"

# ── Canais — ANALYTICS ────────────────────────────────────────────
DASHBOARD_CHANNEL_NAME     = "dashboard-partidas"
DASHBOARD_MEDIADORES       = "dashboard-mediadores"
DASHBOARD_SUPORTE          = "dashboard-suporte"
DASHBOARD_APOSTAS          = "dashboard-apostas"
DASHBOARD_ENTRADAS         = "dashboard-entradas"
DASHBOARD_INFLUENCERS      = "dashboard-influencers"
DASHBOARD_APOSTAS          = "dashboard-apostas"
DASHBOARD_ENTRADAS         = "dashboard-entradas"
# RESULTADOS_CHANNEL removido (canal deletado)

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
INVITE_CHANNEL_NAME          = CONVITES_CHANNEL
INVITE_CHANNEL               = CONVITES_CHANNEL
# Aliases de canais removidos — mantidos apenas como constante de nome para
# referências legadas em outros módulos (não aparecem mais na estrutura)
PAINEL_SUPORTE_CHANNEL       = "painel-suporte"           # canal deletado
APROVAR_MEDIADORES_CHANNEL   = "✔-aprovar-mediadores"     # canal deletado
RESULTADOS_CHANNEL           = "resultados"               # canal deletado
STATUS_BOT_CHANNEL           = CONVITES_CHANNEL           # alias legado → convites

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
        # ✔-aprovar-mediadores removido
    ],
    CATEGORY_MOBILE:   ["📱1x1-mob", "📱2x2-mob", "📱3x3-mob", "📱4x4-mob"],
    CATEGORY_EMULADOR: ["🖥️1x1-emu", "🖥️2x2-emu", "🖥️3x3-emu", "🖥️4x4-emu"],
    CATEGORY_MISTO:    ["🔀4x4-misto", "🔀3x3-misto", "🔀2x2-misto"],
    CATEGORY_SUPORTE: [
        SOLICITAR_SUPORTE_CHANNEL,
        CHAMADOS_CHANNEL_NAME,
        CHAT_SUPORTE_STAFF_CHANNEL,
        SUPORTE_ADMIN_CHANNEL,
        # painel-suporte removido
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
        CONVITES_CHANNEL,
        INFLUENCERS_CHANNEL,
        INFLUENCERS_ADMIN_CHANNEL,
        CHAT_INFLUENCERS_CHANNEL,
        RANKING_CHANNEL,
        # resultados removido
    ],
    CATEGORY_ANALYTICS: [
        DASHBOARD_CHANNEL_NAME, DASHBOARD_MEDIADORES,
        DASHBOARD_SUPORTE, DASHBOARD_INFLUENCERS,
        RESULTADOS_CHANNEL, RANKING_CHANNEL,DASHBOARD_APOSTAS, DASHBOARD_ENTRADAS,
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
}

# ── Canais apenas-leitura para todos (Membro + demais) ────────────────────
READ_ONLY_CHANNELS = {
    REGRAS_CHANNEL, BOAS_VINDAS_CHANNEL,
    AVISOS_CHANNEL,   # todos leem apenas
}

# ── Canais de interação por botão ────────────────────────────────────────
INTERACTION_ONLY_CHANNELS = {
    "📱1x1-mob", "📱2x2-mob", "📱3x3-mob", "📱4x4-mob",
    "🖥️1x1-emu", "🖥️2x2-emu", "🖥️3x3-emu", "🖥️4x4-emu",
    "🔀4x4-misto", "🔀3x3-misto", "🔀2x2-misto",
    SOLICITAR_SUPORTE_CHANNEL,
    SOLICITAR_ANALISE_CHANNEL,   # Controller + ADM apenas (tratado em VIEW_ONLY)
    BLACKLIST_CHANNEL,
    RANKING_CHANNEL,             # Membro interage com botões
}

# ── Canais view-only (só bot/ADM postam) ────────────────────────────────────
CHANNEL_VIEW_ONLY: dict[str, list[str]] = {
    # Analistas
    CASOS_ANALISAR_CHANNEL:     [ANALYST_ROLE_NAME, ADM_ROLE_NAME],
    PAINEL_ANALISTA_CHANNEL:    [ANALYST_ROLE_NAME, ADM_ROLE_NAME],
    HISTORICO_EXPOSED_CHANNEL:  [ANALYST_ROLE_NAME, ADM_ROLE_NAME],

    # Mediação — apenas ADM
    HISTORICO_CHANNEL:          [ADM_ROLE_NAME],
    RENOVACAO_CHANNEL:          [ADM_ROLE_NAME],   # ← só ADM
    SOLICITACOES_CHANNEL:       [ADM_ROLE_NAME],   # ← só ADM

    # Staff
    MEDIADORES_AFKS_CHANNEL:    [CONTROLLER_ROLE_NAME, ADM_ROLE_NAME],
    HEALTH_CHECK_CHANNEL:       [ADM_ROLE_NAME, CONTROLLER_ROLE_NAME],

    # Logs — TODOS apenas ADM
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
}

# ── Canais restritos a ADM apenas (acesso total bloqueado para demais) ────
ADM_ONLY_CHANNELS = {
    CADASTRO_MEDIADOR_CHANNEL,   # só ADM
    MEDIADOR_PIX_CHANNEL,        # só Controller + ADM → ver CHANNEL_PERMISSIONS
    SOLICITAR_ANALISE_CHANNEL,   # só Controller + ADM → ver CHANNEL_PERMISSIONS
}

# ── Canais onde roles podem enviar mensagens ───────────────────────────────
CHANNEL_PERMISSIONS: dict[str, list[str]] = {
    # Suporte
    CHAMADOS_CHANNEL_NAME:      [ADM_ROLE_NAME],                              # só bot + ADM
    SUPORTE_ADMIN_CHANNEL:      [ADM_ROLE_NAME],
    CHAT_SUPORTE_STAFF_CHANNEL: [SUPPORT_ROLE_NAME, CONTROLLER_ROLE_NAME, ADM_ROLE_NAME],

    # Mediação
    MEDIADOR_PANEL_CHANNEL:     [ADM_ROLE_NAME],                              # só bot + ADM
    MEDIADORES_ADMIN_CHANNEL:   [ADM_ROLE_NAME],
    MEDIADOR_PIX_CHANNEL:       [CONTROLLER_ROLE_NAME, ADM_ROLE_NAME],        # Controller + ADM
    CADASTRO_MEDIADOR_CHANNEL:  [ADM_ROLE_NAME],                              # só ADM

    # Analistas
    SOLICITAR_ANALISE_CHANNEL:  [CONTROLLER_ROLE_NAME, ADM_ROLE_NAME],        # Controller + ADM
    ANALISTAS_ADMIN_CHANNEL:    [ADM_ROLE_NAME],
    EXPOSED_CHANNEL_NAME:       [ADM_ROLE_NAME],                              # só bot + ADM
    CHAT_ANALISTAS_CHANNEL:     [ANALYST_ROLE_NAME, ADM_ROLE_NAME],

    # Comunidade
    INFLUENCERS_CHANNEL:        [ADM_ROLE_NAME],                              # só bot + ADM
    INFLUENCERS_ADMIN_CHANNEL:  [ADM_ROLE_NAME],
    CHAT_INFLUENCERS_CHANNEL:   [INFLUENCER_ROLE_NAME, ADM_ROLE_NAME],

    # Informações
    BOAS_VINDAS_CHANNEL:        [],   # só bot
    REGRAS_CHANNEL:             [],   # só bot
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
            # ranking e modos de jogo: Membro interage com botões
            target = member_role or guild.default_role
            overwrites[target] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=False,
                use_application_commands=True,
            )
            if member_role:
                overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=False)

        elif channel_name in READ_ONLY_CHANNELS:
            # regras, boas-vindas, avisos: todos leem, ninguém envia
            target = member_role or guild.default_role
            overwrites[target] = discord.PermissionOverwrite(
                read_messages=True, send_messages=False)
            if member_role:
                overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=False)

        elif channel_name in CHANNEL_VIEW_ONLY:
            viewers = CHANNEL_VIEW_ONLY[channel_name]
            if not viewers:
                target = member_role or guild.default_role
                overwrites[target] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=False)
                if member_role:
                    overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=False)
            else:
                for role_name in viewers:
                    role = roles.get(role_name) or discord.utils.get(guild.roles, name=role_name)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(
                            read_messages=True, send_messages=False)

        else:
            perms = CHANNEL_PERMISSIONS.get(channel_name)
            if perms is None:
                # fallback: Membro só lê
                target = member_role or guild.default_role
                overwrites[target] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=False)
                if member_role:
                    overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=False)
            elif perms == []:
                # só bot posta (ex: regras, boas-vindas)
                if member_role:
                    overwrites[member_role] = discord.PermissionOverwrite(
                        read_messages=True, send_messages=False)
            else:
                for role_name in perms:
                    role = roles.get(role_name) or discord.utils.get(guild.roles, name=role_name)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(
                            read_messages=True, send_messages=True)

        # Bot e ADM sempre têm controle total
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
        }
        if category_name in restricted_cats:
            return {guild.default_role: discord.PermissionOverwrite(
                read_messages=False, send_messages=False)}
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


permission_service = PermissionService()