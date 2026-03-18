"""
main.py — Ponto de entrada principal do bot X1 Frifas.
"""
from __future__ import annotations
import asyncio
import os
import random
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from views.log_delete import MessageDeleteLog
from views.log_comand import CommandLog
from views.log_call import CallLog

load_dotenv()

from config.database         import db
from config.discord_bot      import create_discord_bot, start_discord_bot, set_bot
from utils.logger             import logger, log_success
from utils.datetime_utils     import utcnow
from utils.retry              import with_retry, on_rate_limit
from services.channel_service import RATE_LIMIT_CHANNEL_NAME, STATUS_BOT_CHANNEL

BOT_START_TIME = datetime.now(timezone.utc)

COGS = [
    "cogs.admin_cog",
    "cogs.mediator_cog",
    "cogs.support_cog",
    "cogs.match_cog",
    "cogs.analyst_cog",
    "cogs.invite_cog",
    "cogs.influencer_cog",
    "cogs.renewal_cog",
    "cogs.thread_pool_cog",
]

bot          = create_discord_bot()
_initialized = False

#---------------------------------------------------------------
#TESTE
#---------------------------------------------------------------
@bot.event
async def on_voice_state_update(member, before, after):
    logger.info(f"[VOICE] {member} mudou de estado")

@bot.event
async def on_message_delete(message):
    logger.info(f"[DELETE] mensagem deletada de {message.author}")

@bot.event
async def on_message(message):
    logger.info(f"[MESSAGE] detectada")
    await bot.process_commands(message)

call_log = CallLog(bot)

@bot.event
async def on_voice_state_update(member, before, after):

    logger.info(f"[VOICE] Evento detectado: {member}")

    # entrou
    if not before.channel and after.channel:
        await call_log.on_enter(member, after.channel)

    # saiu
    elif before.channel and not after.channel:
        await call_log.on_exit(member)

command_log = CommandLog(bot)

@bot.event
async def on_command(ctx):

    logger.info(f"[COMMAND] Detectado: {ctx.command}")

    args = " ".join(ctx.message.content.split()[1:])

    await command_log.send_command_log(
        ctx.author,
        str(ctx.command),
        args,
        ctx.channel
    )

delete_log = MessageDeleteLog(bot)

@bot.event
async def on_message_delete(message):

    # ignora bot
    if message.author.bot:
        return

    await delete_log.send_delete_log(message)



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
# on_ready
# ─────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    global _initialized
    if _initialized:
        logger.warning("[on_ready] Reconexão — pulando reinicialização.")
        return
    _initialized = True

    log_success(f"Bot online: {bot.user} (ID: {bot.user.id})")

    # ── Carrega cogs ──────────────────────────────────────────
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            logger.info(f"[Cog] ✅ {cog}")
        except Exception as e:
            logger.error(f"[Cog] ❌ {cog}: {e}")

    # ── Sincroniza slash commands ─────────────────────────────
    try:
        synced = await bot.tree.sync()
        logger.info(f"[SlashCommands] {len(synced)} comandos sincronizados")
    except Exception as e:
        logger.error(f"[SlashCommands] Erro: {e}")

    # ── Persistent views ──────────────────────────────────────
    try:
        from views.ticket_view             import TicketPanelView, TicketCardView, SupportCardView
        from views.mediator_panel_view     import MediatorPanelView
        from views.quero_ser_mediador_view import PedidoMediadorView
        from views.spam_block_card_view    import SpamBlockCardView
        from views.match_queue_view        import MatchQueueView
        from views.match_thread_view       import MatchThreadView
        from views.health_check_view       import HealthCheckView
        from views.analyst_views           import (
            AnalystCaseView, AnalystDecisionView,
            ExposedPanelView, AnalisePanelView,
        )
        from views.extra_panels            import (
            RenovacaoPanelView, PixPanelView,
            InfluencerMemberView, InfluencerAdminView,
        )
        from views.staff_panels            import (
            MediadorPessoalView, MediadorAdminView,
            AnalistaPessoalView, AnalistaAdminView,
            SuporteAdminView,
        )
        from services.faturamento_mediador import RelatorioGeralView
        from services.match_queue_service  import ConfirmationView

        persistent_views = [
            TicketPanelView(),
            TicketCardView(ticket_id="__persistent__"),
            SupportCardView(),
            MediatorPanelView(),
            PedidoMediadorView(),
            SpamBlockCardView(),
            MatchQueueView(),
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
        ]

        for view in persistent_views:
            try:
                bot.add_view(view)
            except Exception as e:
                logger.warning(f"[views] Erro ao registrar {type(view).__name__}: {e}")

        log_success("[views] Views persistentes registradas")
    except Exception as e:
        logger.error(f"[views] Erro ao importar views: {e}", exc_info=True)

    # ── Invite tracker + rate limit monitor ───────────────────
    from services.invite_tracker_service     import invite_tracker_service
    from services.rate_limit_monitor_service import rate_limit_monitor
    invite_tracker_service.bot = bot
    rate_limit_monitor.bot     = bot
    for guild in bot.guilds:
        await invite_tracker_service.cache_guild_invites(guild)
    if not rate_limit_monitor.daily_summary.is_running():
        rate_limit_monitor.daily_summary.start()

    # ── Onboarding ────────────────────────────────────────────
    from services.onboarding_service import OnboardingService
    bot._onboarding_service = OnboardingService(bot)

    # ── Anti-spam ─────────────────────────────────────────────
    try:
        from services.anti_spam_service import init_anti_spam_service
        init_anti_spam_service(bot)
        logger.info("[AntiSpam] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[AntiSpam] {e}")

    # ── Fila de mediadores ────────────────────────────────────
    from services.mediator_queue import mediator_queue
    await mediator_queue.initialize()

    # ── Dashboard de mediador ─────────────────────────────────
    from services.mediador_dashboard_service import mediator_dashboard_service
    mediator_dashboard_service.start_task(bot)

    # ── Card service ──────────────────────────────────────────
    from services.card_service import card_service
    card_service.bot = bot

    # ── Analytics ─────────────────────────────────────────────
    from services.analytics_service import analytics_service
    analytics_service.start_task(bot)
    logger.info("[Analytics] Dashboards inicializados (atualização a cada hora)")

    # ── AFK service ───────────────────────────────────────────
    from services.afk_service import afk_service
    afk_service.bot = bot
    if not afk_service.check_queue_afk.is_running():
        afk_service.check_queue_afk.start()
    if not afk_service.check_match_afk.is_running():
        afk_service.check_match_afk.start()
    bot._afk_service = afk_service
    logger.info("[AFK] Serviço inicializado (fila + partida)")

    # ── Thread reuse ──────────────────────────────────────────
    try:
        from services.thread_reuse_service import init_thread_reuse_service
        init_thread_reuse_service(bot)
        logger.info("[ThreadReuse] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[ThreadReuse] {e}")

    # ── Thread log ────────────────────────────────────────────
    try:
        from services.thread_log_service import init_thread_log_service
        init_thread_log_service(bot)
        logger.info("[ThreadLog] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[ThreadLog] {e}")

    # ── Health check ──────────────────────────────────────────
    try:
        from services.health_check_service import (
            init_health_check_service, set_bot_start_time
        )
        init_health_check_service(bot)
        set_bot_start_time(BOT_START_TIME)
        logger.info("[HealthCheck] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[HealthCheck] {e}")

    # ── Analise fila ──────────────────────────────────────────
    try:
        from services.analise_fila import analise_fila_service
        analise_fila_service.bot = bot
        logger.info("[AnaliseFila] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[AnaliseFila] {e}")

    # ── Restaura membros bloqueados por spam ──────────────────
    try:
        from services.anti_spam_service import anti_spam_service
        if anti_spam_service:
            for guild in bot.guilds:
                await anti_spam_service.restore_blocked_members(guild)
            logger.info("[AntiSpam] Membros bloqueados restaurados")
    except Exception as e:
        logger.warning(f"[AntiSpam] restore_blocked_members: {e}")

    # ── Sincroniza mediadores por cargo ───────────────────────
    for guild in bot.guilds:
        try:
            await mediator_queue.sync_mediators_by_role(guild, role_name="Controller")
        except Exception as e:
            logger.warning(f"[on_ready] Sync mediadores: {e}")

    # ── Status rotativo ───────────────────────────────────────
    if not set_status.is_running():
        set_status.start()

    log_success("Bot totalmente inicializado!")


# ─────────────────────────────────────────────────────────────
# Eventos
# ─────────────────────────────────────────────────────────────

@bot.event
async def on_member_join(member: discord.Member):
    # Anti-spam: verifica se membro retornou bloqueado
    try:
        from services.anti_spam_service import anti_spam_service
        if anti_spam_service:
            await anti_spam_service.handle_member_join(member)
    except Exception:
        pass

    # Onboarding normal
    svc = getattr(bot, "_onboarding_service", None)
    if svc:
        await svc.handle_new_member(member)


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
async def on_app_command_error(
    interaction: discord.Interaction,
    error: discord.app_commands.AppCommandError,
):
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
        discord.Activity(type=discord.ActivityType.playing,   name="X1 Frifas"),
        discord.Activity(type=discord.ActivityType.listening, name="os mediadores"),
        discord.Activity(type=discord.ActivityType.watching,  name=f"{len(bot.guilds)} servidor(es)"),
    ]
    await bot.change_presence(activity=random.choice(statuses))


@set_status.before_loop
async def before_set_status():
    await bot.wait_until_ready()


# ─────────────────────────────────────────────────────────────
# Webhook server (pagamentos EFI)
# ─────────────────────────────────────────────────────────────

async def _start_webhook_server():
    try:
        from aiohttp import web

        async def efi_webhook(request: web.Request) -> web.Response:
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
        app.router.add_post("/webhook/efi", efi_webhook)
        app.router.add_get("/health", lambda r: web.Response(text="ok"))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("API_PORT", "8000")))
        await site.start()
    except Exception as e:
        logger.error(f"[Webhook] Falha ao iniciar servidor HTTP: {e}")


# ─────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────

async def main():
    logger.info("Iniciando X1 Frifas Bot...")
    await db.connect()
    log_success("MongoDB conectado!")
    set_bot(bot)

    if os.getenv("WEBHOOK_BASE_URL", ""):
        asyncio.create_task(_start_webhook_server())
        logger.info("[Webhook] Servidor HTTP iniciado na porta 8000")

    await start_discord_bot(bot)


if __name__ == "__main__":
    asyncio.run(main())
