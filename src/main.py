# main.py — Ponto de entrada principal do bot X1 Frifas.
from __future__ import annotations
import asyncio
import os
import re
import random
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from views.log_delete import MessageDeleteLog
from views.log_comand import CommandLog
from views.log_call import CallLog
from views.log_troca_cargo import Troca_cargo

load_dotenv()

from config.database         import db
from config.discord_bot      import create_discord_bot, start_discord_bot, set_bot
from utils.logger             import logger, log_success
from utils.datetime_utils     import utcnow
from utils.retry              import on_rate_limit
from services.channel_service import RATE_LIMIT_CHANNEL_NAME, ADM_ROLE_NAME, PROTECTED_ROLES

BOT_START_TIME = datetime.now(timezone.utc)

COGS = [
    "cogs.admin_cog",
    "cogs.mediator_cog",
    "cogs.support_cog",
    "cogs.match_cog",
    "cogs.analyst_cog",
    "cogs.invite_cog",
    "cogs.influencer_cog",
    "cogs.influencer_live_cog",
    "cogs.renewal_cog",
    "cogs.thread_pool_cog",
    "cogs.renewal_dashboard_cog",
    "cogs.alerts_cog",
    "cogs.moderation_cog",
]

bot          = create_discord_bot()
_initialized = False

_troca_cargo_log = None
_call_log        = None
_command_log     = None
_delete_log      = None


# ─────────────────────────────────────────────────────────────
# Servidor HTTP
# ─────────────────────────────────────────────────────────────

async def _start_http_server():
    from aiohttp import web

    async def health(request: web.Request) -> web.Response:
        return web.Response(text="ok", status=200)

    async def efi_webhook(request: web.Request) -> web.Response:
        if not os.getenv("WEBHOOK_BASE_URL", ""):
            return web.Response(status=404)
        try:
            data   = await request.json()
            txid   = data.get("txid") or data.get("txId", "")
            status = data.get("status", "")
            if status == "CONCLUIDA" and txid:
                renewal = await db.get_collection("mediator_renewals").find_one(
                    {"txid": txid})
                if renewal and not renewal.get("confirmed"):
                    from cogs.renewal_cog import _confirm_and_update
                    await _confirm_and_update(
                        interaction=None,
                        txid=txid,
                        mediator_id=renewal["mediator_id"],
                        bot=bot,
                    )
                    logger.info(f"[Webhook] Renovação confirmada: {txid}")
        except Exception as e:
            logger.error(f"[Webhook] Erro: {e}")
        return web.Response(status=200)

    app = web.Application()
    app.router.add_get("/health",       health)
    app.router.add_post("/webhook/efi", efi_webhook)

    port = int(os.getenv("PORT") or os.getenv("API_PORT", "8000"))
    runner = web.AppRunner(app)
    await runner.setup()
    site   = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"[HTTP] Servidor na porta {port} — GET /health ativo")


# ─────────────────────────────────────────────────────────────
# Rate limit monitor
# ─────────────────────────────────────────────────────────────

@on_rate_limit
async def _rate_limit_monitor(endpoint: str, retry_after: float, context: str):
    for guild in bot.guilds:
        ch = discord.utils.get(guild.text_channels, name=RATE_LIMIT_CHANNEL_NAME)
        if ch:
            embed = discord.Embed(title="Rate Limit Detectado", color=0xE74C3C)
            embed.add_field(name="Endpoint", value=f"`{endpoint}`",         inline=True)
            embed.add_field(name="Aguardar", value=f"`{retry_after:.1f}s`", inline=True)
            embed.add_field(name="Contexto", value=context or "—",          inline=False)
            embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
            try:
                await ch.send(embed=embed)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────
# Auto Setup
# ─────────────────────────────────────────────────────────────

async def _auto_setup_canais(guild: discord.Guild):
    try:
        from services.channel_setup_service import channel_setup_service
        channel_setup_service.bot = bot
        result = await channel_setup_service.setup_all(guild)
        log_success(f"[AutoSetup] !setupcanais executado automaticamente: {result}")

        alertas_ch = discord.utils.get(guild.text_channels, name="alertas-adm")
        if alertas_ch:
            embed = discord.Embed(
                title="🔄 Bot reiniciado — Setup automático concluído",
                description=(
                    "O bot foi reiniciado e executou `!setupcanais` automaticamente.\n"
                    "Todos os painéis e cards foram reconstruídos.\n\n"
                    f"**Resultado:** {result or 'OK'}"
                ),
                color=0x2ECC71,
                timestamp=utcnow(),
            )
            embed.set_footer(text="X1 Frifas · Auto-Setup")
            await alertas_ch.send(embed=embed)
    except Exception as e:
        logger.error(f"[AutoSetup] Erro ao executar setupcanais automático: {e}", exc_info=True)
        try:
            alertas_ch = discord.utils.get(guild.text_channels, name="alertas-adm")
            if alertas_ch:
                embed = discord.Embed(
                    title="❌ Bot reiniciado — Erro no setup automático",
                    description=f"```{e}```",
                    color=0xE74C3C,
                    timestamp=utcnow(),
                )
                await alertas_ch.send(embed=embed)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# Índices MongoDB
# ─────────────────────────────────────────────────────────────

async def _ensure_db_indexes():
    _30_dias = 60 * 60 * 24 * 30

    try:
        await db.get_collection("active_threads").create_index(
            "thread_id", unique=True, background=True)
        await db.get_collection("active_threads").create_index(
            "created_at", expireAfterSeconds=_30_dias, background=True)
        await db.get_collection("thread_pool").create_index(
            "thread_id", unique=True, background=True)
        await db.get_collection("thread_pool").create_index(
            "created_at", expireAfterSeconds=_30_dias, background=True)
        await db.get_collection("matches").create_index(
            "thread_id", unique=True, sparse=True, background=True)
        await db.get_collection("matches").create_index(
            "created_at", expireAfterSeconds=_30_dias, background=True)
        await db.get_collection("influencer_live_rooms").create_index(
            [("influencer_id", 1), ("guild_id", 1)], unique=True, background=True)
        await db.get_collection("influencer_live_queues").create_index(
            [("influencer_id", 1), ("guild_id", 1)], unique=True, background=True)
        await db.get_collection("mediator_live_queues").create_index(
            "guild_id", unique=True, background=True)
        logger.info(
            "[DB] Índices garantidos: active_threads, thread_pool, matches(sparse), "
            "influencer_live_rooms, influencer_live_queues, mediator_live_queues "
            "| TTL 30 dias ativo"
        )
    except Exception as e:
        logger.warning(f"[DB] _ensure_db_indexes: {e}")


# ─────────────────────────────────────────────────────────────
# on_interaction — reconstrói views com custom_id dinâmico
# ─────────────────────────────────────────────────────────────

async def _rebuild_dynamic_view(interaction: discord.Interaction) -> bool:
    """
    Reconstrói ContraConfirmView, ContraResultView e ContraControlView
    a partir do custom_id dinâmico quando a view não está registrada
    (pós-restart ou primeira interação após criação).

    Retorna True se a interação foi tratada aqui (não deve continuar o dispatch),
    False se deve seguir o fluxo normal.
    """
    if interaction.type != discord.InteractionType.component:
        return False

    custom_id: str = interaction.data.get("custom_id", "")

    # ── ContraConfirmView: contra_confirm_{match_id} / contra_giveup_{match_id}
    m = re.match(r"^contra_(confirm|giveup)_(.+)$", custom_id)
    if m:
        match_id = m.group(2)
        try:
            from services.match_service import match_service
            from views.influencer_live_match_view import ContraConfirmView

            match_doc = await match_service.get_match(match_id)
            if not match_doc:
                await interaction.response.send_message(
                    "❌ Partida não encontrada.", ephemeral=True)
                return True

            view = ContraConfirmView(
                match_id=match_id,
                challenger_id=int(match_doc.get("challenger_id", 0)),
                influencer_id=int(match_doc.get("influencer_id", 0)),
                guild_id=int(match_doc.get("guild_id", 0)),
                channel=interaction.channel,
            )
            # Deixa a view processar a interação
            await view._dispatch_interaction(interaction, custom_id)
        except Exception as e:
            logger.error(f"[on_interaction] ContraConfirmView rebuild erro: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ Erro interno. Contate um admin.", ephemeral=True)
            except Exception:
                pass
        return True

    # ── ContraResultView: contra_inf_wins_{match_id} / contra_chal_wins_{match_id} / contra_cancel_{match_id}
    m = re.match(r"^contra_(inf_wins|chal_wins|cancel)_(.+)$", custom_id)
    if m:
        match_id = m.group(2)
        try:
            from services.match_service import match_service
            from views.influencer_live_match_view import ContraResultView

            match_doc = await match_service.get_match(match_id)
            if not match_doc:
                await interaction.response.send_message(
                    "❌ Partida não encontrada.", ephemeral=True)
                return True

            view = ContraResultView(
                match_id=match_id,
                influencer_id=int(match_doc.get("influencer_id", 0)),
                challenger_id=int(match_doc.get("challenger_id", 0)),
                guild_id=int(match_doc.get("guild_id", 0)),
            )
            await view._dispatch_interaction(interaction, custom_id)
        except Exception as e:
            logger.error(f"[on_interaction] ContraResultView rebuild erro: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ Erro interno. Contate um admin.", ephemeral=True)
            except Exception:
                pass
        return True

    # ── ContraControlView: ctrl_*_{influencer_id}
    m = re.match(r"^ctrl_(?:select_platform|select_gamemode|edit_valor|edit_regras|view_queue|desativar)_(\d+)$", custom_id)
    if m:
        influencer_id = int(m.group(1))
        try:
            from services.influencer_live_room_service import influencer_live_room_service
            from views.influencer_live_control_view import ContraControlView

            guild_id = str(interaction.guild_id)
            room_result = await influencer_live_room_service.get_room(
                influencer_id=str(influencer_id),
                guild_id=guild_id,
            )
            if not room_result["ok"]:
                await interaction.response.send_message(
                    "❌ Sala não encontrada. Pode ter sido desativada.", ephemeral=True)
                return True

            view = ContraControlView(
                influencer_id=influencer_id,
                guild_id=int(guild_id),
            )
            await view._dispatch_interaction(interaction, custom_id)
        except Exception as e:
            logger.error(f"[on_interaction] ContraControlView rebuild erro: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ Erro interno. Contate um admin.", ephemeral=True)
            except Exception:
                pass
        return True

    return False


@bot.event
async def on_interaction(interaction: discord.Interaction):
    """
    Intercepta interações de componentes com custom_id dinâmico
    antes do dispatch padrão do discord.py.
    Reconstrói a view adequada via _rebuild_dynamic_view.
    """
    if await _rebuild_dynamic_view(interaction):
        return
    # Para todos os outros tipos de interação, deixa o discord.py processar normalmente
    # (slash commands, modais, etc.)
    # NOTA: bot.process_application_commands não existe no discord.py puro;
    # o dispatch de slash/autocomplete é automático pelo bot. Para componentes
    # não tratados acima, o bot já despacha via add_view registrados no boot.


# ─────────────────────────────────────────────────────────────
# on_ready
# ─────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    global _initialized, _troca_cargo_log, _call_log, _command_log, _delete_log

    if _initialized:
        logger.warning("[on_ready] Reconexão — pulando reinicialização.")
        return
    _initialized = True

    _troca_cargo_log = Troca_cargo(bot)
    _call_log        = CallLog(bot)
    _command_log     = CommandLog(bot)
    _delete_log      = MessageDeleteLog(bot)

    guild = bot.guilds[0] if bot.guilds else None
    log_success(f"Bot online: {bot.user} (ID: {bot.user.id})")

    try:
        await _ensure_db_indexes()
    except Exception as e:
        logger.warning(f"[DB] Falha ao garantir índices no on_ready: {e}")

    try:
        synced = await bot.tree.sync()
        logger.info(f"[SlashCommands] {len(synced)} comandos sincronizados")
    except Exception as e:
        logger.error(f"[SlashCommands] Erro: {e}")

    try:
        from views.ticket_view              import TicketPanelView, TicketCardView, SupportCardView, TicketChannelView
        from views.mediator_panel_view      import MediatorPanelView
        from views.quero_ser_mediador_view  import PedidoMediadorView
        from views.spam_block_card_view     import SpamBlockCardView
        from views.match_queue_view         import MatchQueueView
        from views.match_thread_view        import MatchThreadView
        from views.health_check_view        import HealthCheckView
        from views.analyst_views            import (
            AnalystCaseView, AnalystDecisionView,
            ExposedPanelView, AnalisePanelView,
        )
        from views.extra_panels             import (
            RenovacaoPanelView, PixPanelView,
            InfluencerMemberView, InfluencerAdminView,
        )
        from views.staff_panels             import (
            MediadorPessoalView, MediadorAdminView,
            AnalistaPessoalView, AnalistaAdminView,
            SuporteAdminView,
        )
        from views.blacklist_view           import BlacklistCheckView
        from views.mediator_register_view   import MediatorRegisterView
        from views.captcha_button_view      import CaptchaButtonView
        from cogs.renewal_dashboard_cog     import ContractPanelView
        from services.faturamento_mediador  import RelatorioGeralView
        from services.match_queue_service   import ConfirmationView
        from views.rules_view               import RulesView, ConfirmationView as RulesConfirmationView
        # Influencer Live — apenas views com custom_id FIXO
        from views.influencer_live_view       import ContraRoomView, ControllerLivePanelView
        from views.influencer_live_admin_view import InfluencerLiveAdminView
        from views.live_contra_setup_view     import LiveContraSetupView
        # ContraConfirmView, ContraResultView e ContraControlView NÃO são
        # registradas aqui — usam custom_id dinâmico e são reconstruídas
        # via on_interaction/_rebuild_dynamic_view

        persistent_views = [
            TicketPanelView(),
            TicketCardView(ticket_id="__persistent__"),
            TicketChannelView(ticket_id="__persistent__"),
            SupportCardView(),
            MediatorPanelView(),
            PedidoMediadorView(),
            SpamBlockCardView(),
            MatchQueueView(guild=guild),
            MatchThreadView(match_id="__persistent__"),
            ConfirmationView(),
            HealthCheckView(),
            ExposedPanelView(),
            AnalystCaseView(case_id="__persistent__"),
            AnalystDecisionView(case_id="__persistent__"),
            AnalisePanelView(),
            RenovacaoPanelView(),
            PixPanelView(),
            RelatorioGeralView(),
            InfluencerMemberView(),
            InfluencerAdminView(),
            MediadorPessoalView(),
            MediadorAdminView(),
            AnalistaPessoalView(),
            AnalistaAdminView(),
            SuporteAdminView(),
            BlacklistCheckView(),
            MediatorRegisterView(),
            ContractPanelView(),
            RulesView(),
            RulesConfirmationView(),
            # Influencer Live — custom_id FIXO
            ContraRoomView(influencer_id=0, guild_id=0),
            ControllerLivePanelView(),
            InfluencerLiveAdminView(),
            LiveContraSetupView(),
            # CAPTCHA
            CaptchaButtonView,
        ]

        for view in persistent_views:
            try:
                if isinstance(view, type):
                    logger.info(f"[views] Ignorando classe não-instanciável: {view.__name__}")
                    continue
                bot.add_view(view)
            except Exception as e:
                logger.warning(f"[views] Erro ao registrar {type(view).__name__}: {e}")

        log_success("[views] Views persistentes registradas")
    except Exception as e:
        logger.error(f"[views] Erro ao importar views: {e}", exc_info=True)

    from services.invite_tracker_service     import invite_tracker_service
    from services.rate_limit_monitor_service import rate_limit_monitor
    invite_tracker_service.bot = bot
    rate_limit_monitor.bot     = bot
    for guild_item in bot.guilds:
        await invite_tracker_service.cache_guild_invites(guild_item)
    if not rate_limit_monitor.daily_summary.is_running():
        rate_limit_monitor.daily_summary.start()

    from services.onboarding_service import OnboardingService
    bot._onboarding_service = OnboardingService(bot)
    if guild:
        await bot._onboarding_service.restore_state(guild)

    try:
        from services.anti_spam_service import init_anti_spam_service
        init_anti_spam_service(bot)
        logger.info("[AntiSpam] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[AntiSpam] {e}")

    from services.mediator_queue import mediator_queue
    await mediator_queue.initialize()

    from services.card_service import card_service
    card_service.bot = bot

    from services.analytics_service import analytics_service
    analytics_service.start_task(bot)
    logger.info("[Analytics] Dashboards inicializados")

    from services.afk_service import afk_service
    afk_service.bot = bot
    if not afk_service.check_queue_afk.is_running():
        afk_service.check_queue_afk.start()
    if not afk_service.check_match_afk.is_running():
        afk_service.check_match_afk.start()
    bot._afk_service = afk_service
    logger.info("[AFK] Serviço inicializado")

    try:
        from services.thread_reuse_service import init_thread_reuse_service
        svc = init_thread_reuse_service(bot)
        await svc.ensure_indexes()
        logger.info("[ThreadReuse] Serviço inicializado + índices garantidos")
    except Exception as e:
        logger.warning(f"[ThreadReuse] {e}")

    try:
        from services.thread_log_service import init_thread_log_service
        init_thread_log_service(bot)
        logger.info("[ThreadLog] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[ThreadLog] {e}")

    try:
        from services.health_check_service import (
            init_health_check_service, set_bot_start_time
        )
        init_health_check_service(bot)
        set_bot_start_time(BOT_START_TIME)
        logger.info("[HealthCheck] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[HealthCheck] {e}")

    try:
        from services.analise_fila import analise_fila_service
        analise_fila_service.bot = bot
        logger.info("[AnaliseFila] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[AnaliseFila] {e}")

    try:
        from services.anti_spam_service import anti_spam_service
        if anti_spam_service:
            for guild_item in bot.guilds:
                await anti_spam_service.restore_blocked_members(guild_item)
            logger.info("[AntiSpam] Membros bloqueados restaurados")
    except Exception as e:
        logger.warning(f"[AntiSpam] restore_blocked_members: {e}")

    from services.mediator_queue import mediator_queue
    for guild_item in bot.guilds:
        try:
            await mediator_queue.sync_mediators_by_role(guild_item, role_name="Controller")
        except Exception as e:
            logger.warning(f"[on_ready] Sync mediadores: {e}")

    if not set_status.is_running():
        set_status.start()

    try:
        from utils.circuit_breaker import db_circuit_breaker
        db_circuit_breaker.set_bot(bot)
        logger.info("[CircuitBreaker] Bot injetado — notificações em #alertas-adm ativas")
    except Exception as e:
        logger.warning(f"[CircuitBreaker] Erro ao injetar bot: {e}")

    if guild:
        asyncio.create_task(_auto_setup_canais(guild))

    log_success("Bot totalmente inicializado!")


# ─────────────────────────────────────────────────────────────
# Eventos
# ─────────────────────────────────────────────────────────────

@bot.event
async def on_member_join(member: discord.Member):
    try:
        from services.anti_spam_service import anti_spam_service
        if anti_spam_service:
            await anti_spam_service.handle_member_join(member)
    except Exception:
        pass
    svc = getattr(bot, "_onboarding_service", None)
    if svc:
        await svc.handle_new_member(member)


@bot.event
async def on_member_remove(member: discord.Member):
    svc = getattr(bot, "_onboarding_service", None)
    if svc:
        try:
            await svc.handle_member_leave(member)
        except Exception as e:
            logger.warning(f"[on_member_remove] Erro no handle_member_leave: {e}")


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.roles == after.roles:
        return

    try:
        await _troca_cargo_log.send_on_troca_cargo(before, after)
    except Exception as e:
        logger.warning(f"[TrocaCargo] Erro no log: {e}")

    added_roles  = set(after.roles) - set(before.roles)
    illegal_adds = {r for r in added_roles if r.name in PROTECTED_ROLES}
    if not illegal_adds:
        return

    try:
        guild = after.guild

        async for entry in guild.audit_logs(
            limit=5,
            action=discord.AuditLogAction.member_role_update,
        ):
            if entry.target.id != after.id:
                continue
            if entry.user.id == bot.user.id:
                return
            if ADM_ROLE_NAME in {r.name for r in entry.user.roles}:
                return
            break

        for role in illegal_adds:
            try:
                await after.remove_roles(role, reason="[Anti-self-role] Cargo protegido removido")
                logger.warning(f"[AntiSelfRole] {after} tentou se auto-atribuir '{role.name}'. Removido.")
            except Exception as e:
                logger.error(f"[AntiSelfRole] Falha: {e}")

        role_names = ", ".join(f"**{r.name}**" for r in illegal_adds)
        try:
            await after.send(
                f"⚠️ Olá {after.display_name},\n"
                f"O(s) cargo(s) {role_names} são gerenciados pela administração "
                f"e foram removidos automaticamente."
            )
        except discord.Forbidden:
            pass

        from services.channel_service import LOGS_TROCA_CARGO_CHANNEL
        log_ch = discord.utils.get(guild.text_channels, name=LOGS_TROCA_CARGO_CHANNEL)
        if log_ch:
            embed = discord.Embed(
                title="⚠️ Tentativa de Auto-Atribuição de Cargo",
                color=0xE74C3C,
                timestamp=utcnow(),
            )
            embed.add_field(name="Membro",   value=f"{after.mention} (`{after.id}`)", inline=True)
            embed.add_field(name="Cargo(s)", value=role_names,                        inline=True)
            embed.set_footer(text="Bot removeu automaticamente")
            try:
                await log_ch.send(embed=embed)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"[AntiSelfRole] Erro geral: {e}")


@bot.event
async def on_voice_state_update(member, before, after):
    logger.info(f"[VOICE] Evento detectado: {member}")
    if _call_log is None:
        return
    if not before.channel and after.channel:
        await _call_log.on_enter(member, after.channel)
    elif before.channel and not after.channel:
        await _call_log.on_exit(member)


@bot.event
async def on_command(ctx):
    logger.info(f"[COMMAND] Detectado: {ctx.command}")
    if _command_log is None:
        return
    args = " ".join(ctx.message.content.split()[1:])
    await _command_log.send_command_log(ctx.author, str(ctx.command), args, ctx.channel)


@bot.event
async def on_message_delete(message: discord.Message):
    logger.info(f"[DELETE] Detectado: {message.author}")
    if message.author.bot or _delete_log is None:
        return
    await _delete_log.send_delete_log(message)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    afk_svc = getattr(bot, "_afk_service", None)
    if afk_svc and message.guild:
        try:
            from services.mediator_queue import mediator_queue
            if message.author.id in mediator_queue.queue:
                afk_svc.mark_queue_activity(message.author.id)
        except Exception:
            pass
    try:
        from services.anti_spam_service import anti_spam_service
        if anti_spam_service and await anti_spam_service.check_message(message):
            return
    except Exception:
        pass
    await bot.process_commands(message)


@bot.tree.error
async def on_app_command_error(interaction, error):
    msg = "Erro ao executar comando."
    if isinstance(error, discord.app_commands.MissingAnyRole):
        msg = "Você não tem permissão para usar este comando."
    elif isinstance(error, discord.app_commands.MissingPermissions):
        msg = "Permissões insuficientes."
    elif isinstance(error, discord.app_commands.CommandOnCooldown):
        msg = f"Aguarde {error.retry_after:.1f}s para usar novamente."
    logger.error(f"[AppCommandError] {interaction.command}: {error}")
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# Status rotativo
# ─────────────────────────────────────────────────────────────

@tasks.loop(minutes=10)
async def set_status():
    statuses = [
        discord.Activity(type=discord.ActivityType.watching,  name="as filas de partidas"),
        discord.Activity(type=discord.ActivityType.playing,   name="SOLAR E-SPORTS"),
        discord.Activity(type=discord.ActivityType.listening, name="os mediadores"),
        discord.Activity(type=discord.ActivityType.watching,  name=f"{len(bot.guilds)} servidor(es)"),
    ]
    await bot.change_presence(activity=random.choice(statuses))


@set_status.before_loop
async def before_set_status():
    await bot.wait_until_ready()


# ─────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────

async def main():
    logger.info("Iniciando Solar Bot...")
    await db.connect()
    log_success("MongoDB conectado!")
    set_bot(bot)

    for cog in COGS:
        try:
            await bot.load_extension(cog)
            logger.info(f"[Cog] ✅ {cog}")
        except Exception as e:
            logger.error(f"[Cog] ❌ {cog}: {e}")

    await _start_http_server()
    await asyncio.gather(
        start_discord_bot(bot),
        _keep_alive(),
    )


async def _keep_alive():
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
