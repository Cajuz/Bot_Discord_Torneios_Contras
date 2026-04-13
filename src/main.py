# main.py — Ponto de entrada principal do bot X1 Frifas.
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
from views.log_troca_cargo import Troca_cargo

load_dotenv()

from config.database         import db
from config.discord_bot      import create_discord_bot, start_discord_bot, set_bot
from utils.logger             import logger, log_success
from utils.datetime_utils     import utcnow
from utils.retry              import with_retry, on_rate_limit
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
    "cogs.renewal_cog",
    "cogs.thread_pool_cog",
    "cogs.renewal_dashboard_cog",  # Painel de contratos e analytics ADM
]

bot          = create_discord_bot()
_initialized = False

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

    # ── Carrega cogs ────────────────────────────────────────────
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            logger.info(f"[Cog] ✅ {cog}")
        except Exception as e:
            logger.error(f"[Cog] ❌ {cog}: {e}")

    # ── Sincroniza slash commands ───────────────────────────────
    try:
        synced = await bot.tree.sync()
        logger.info(f"[SlashCommands] {len(synced)} comandos sincronizados")
    except Exception as e:
        logger.error(f"[SlashCommands] Erro: {e}")

    # ── Persistent views ──────────────────────────────────────────
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
        from views.blacklist_view          import BlacklistCheckView
        from views.mediator_register_view  import MediatorRegisterView
        from cogs.renewal_dashboard_cog    import ContractPanelView
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
            BlacklistCheckView(),
            MediatorRegisterView(),
            ContractPanelView(),
        ]

        for view in persistent_views:
            try:
                bot.add_view(view)
            except Exception as e:
                logger.warning(f"[views] Erro ao registrar {type(view).__name__}: {e}")

        log_success("[views] Views persistentes registradas")
    except Exception as e:
        logger.error(f"[views] Erro ao importar views: {e}", exc_info=True)

    # ── Invite tracker + rate limit monitor ───────────────────────
    from services.invite_tracker_service     import invite_tracker_service
    from services.rate_limit_monitor_service import rate_limit_monitor
    invite_tracker_service.bot = bot
    rate_limit_monitor.bot     = bot
    for guild in bot.guilds:
        await invite_tracker_service.cache_guild_invites(guild)
    if not rate_limit_monitor.daily_summary.is_running():
        rate_limit_monitor.daily_summary.start()

    # ── Onboarding ────────────────────────────────────────────────
    from services.onboarding_service import OnboardingService
    bot._onboarding_service = OnboardingService(bot)

    # ── Anti-spam ─────────────────────────────────────────────────
    try:
        from services.anti_spam_service import init_anti_spam_service
        init_anti_spam_service(bot)
        logger.info("[AntiSpam] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[AntiSpam] {e}")

    # ── Fila de mediadores ──────────────────────────────────────────
    from services.mediator_queue import mediator_queue
    await mediator_queue.initialize()

    # ── Card service ──────────────────────────────────────────────
    from services.card_service import card_service
    card_service.bot = bot

    # ── Analytics ─────────────────────────────────────────────────
    from services.analytics_service import analytics_service
    analytics_service.start_task(bot)
    logger.info("[Analytics] Dashboards inicializados (atualização a cada hora)")

    # ── AFK service ───────────────────────────────────────────────
    from services.afk_service import afk_service
    afk_service.bot = bot
    if not afk_service.check_queue_afk.is_running():
        afk_service.check_queue_afk.start()
    if not afk_service.check_match_afk.is_running():
        afk_service.check_match_afk.start()
    bot._afk_service = afk_service
    logger.info("[AFK] Serviço inicializado (fila + partida)")

    # ── Thread reuse ──────────────────────────────────────────────
    try:
        from services.thread_reuse_service import init_thread_reuse_service
        init_thread_reuse_service(bot)
        logger.info("[ThreadReuse] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[ThreadReuse] {e}")

    # ── Thread log ────────────────────────────────────────────────
    try:
        from services.thread_log_service import init_thread_log_service
        init_thread_log_service(bot)
        logger.info("[ThreadLog] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[ThreadLog] {e}")

    # ── Health check ──────────────────────────────────────────────
    try:
        from services.health_check_service import (
            init_health_check_service, set_bot_start_time
        )
        init_health_check_service(bot)
        set_bot_start_time(BOT_START_TIME)
        logger.info("[HealthCheck] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[HealthCheck] {e}")

    # ── Analise fila ─────────────────────────────────────────────
    try:
        from services.analise_fila import analise_fila_service
        analise_fila_service.bot = bot
        logger.info("[AnaliseFila] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[AnaliseFila] {e}")

    # ── Restaura membros bloqueados por spam ──────────────────────
    try:
        from services.anti_spam_service import anti_spam_service
        if anti_spam_service:
            for guild in bot.guilds:
                await anti_spam_service.restore_blocked_members(guild)
            logger.info("[AntiSpam] Membros bloqueados restaurados")
    except Exception as e:
        logger.warning(f"[AntiSpam] restore_blocked_members: {e}")

    # ── Sincroniza mediadores por cargo ───────────────────────────
    for guild in bot.guilds:
        try:
            await mediator_queue.sync_mediators_by_role(guild, role_name="Controller")
        except Exception as e:
            logger.warning(f"[on_ready] Sync mediadores: {e}")

    # ── Status rotativo ─────────────────────────────────────────────
    if not set_status.is_running():
        set_status.start()

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


# Instâncias de log (criadas uma vez, fora dos handlers)
_troca_cargo_log = Troca_cargo(bot)
_call_log        = CallLog(bot)
_command_log     = CommandLog(bot)
_delete_log      = MessageDeleteLog(bot)


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """
    1. Loga troca de cargo.
    2. Anti-self-role: se um usuário (sem permissão) se adicionou um cargo
       protegido, o bot remove imediatamente e notifica via DM + log.
    """
    if before.roles == after.roles:
        return

    # ─ Log de troca de cargo ──────────────────────────────────
    try:
        await _troca_cargo_log.send_on_troca_cargo(before, after)
    except Exception as e:
        logger.warning(f"[TrocaCargo] Erro no log: {e}")

    # ─ Anti-self-role ──────────────────────────────────────
    added_roles = set(after.roles) - set(before.roles)
    illegal_adds = {r for r in added_roles if r.name in PROTECTED_ROLES}
    if not illegal_adds:
        return

    try:
        guild    = after.guild
        adm_role = discord.utils.get(guild.roles, name=ADM_ROLE_NAME)

        async for entry in guild.audit_logs(
            limit=5,
            action=discord.AuditLogAction.member_role_update,
        ):
            if entry.target.id != after.id:
                continue
            if entry.user.id == bot.user.id:
                return
            executor_roles = {r.name for r in entry.user.roles}
            if ADM_ROLE_NAME in executor_roles:
                return
            break

        for role in illegal_adds:
            try:
                await after.remove_roles(role, reason="[Anti-self-role] Cargo protegido removido")
                logger.warning(
                    f"[AntiSelfRole] {after} ({after.id}) tentou se auto-atribuir '{role.name}'. Removido."
                )
            except Exception as e:
                logger.error(f"[AntiSelfRole] Falha ao remover '{role.name}' de {after}: {e}")

        role_names = ", ".join(f"**{r.name}**" for r in illegal_adds)
        try:
            await after.send(
                f"⚠️ Olá {after.display_name},\n"
                f"O(s) cargo(s) {role_names} são gerenciados exclusivamente pela administração "
                f"e foram removidos automaticamente.\n"
                f"Se você acredita que isso é um erro, entre em contato com a equipe."
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
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    logger.info(f"[VOICE] Evento detectado: {member}")
    if not before.channel and after.channel:
        await _call_log.on_enter(member, after.channel)
    elif before.channel and not after.channel:
        await _call_log.on_exit(member)


@bot.event
async def on_command(ctx):
    logger.info(f"[COMMAND] Detectado: {ctx.command}")
    args = " ".join(ctx.message.content.split()[1:])
    await _command_log.send_command_log(
        ctx.author, str(ctx.command), args, ctx.channel
    )


@bot.event
async def on_message_delete(message: discord.Message):
    logger.info(f"[DELETE] Detectado: {message.author}")
    if message.author.bot:
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
# Servidor HTTP — health check + webhook EFI
# Sobe SEMPRE para que o healthcheck da plataforma (Railway/Render)
# receba 200 em GET /health mesmo sem WEBHOOK_BASE_URL configurado.
# ─────────────────────────────────────────────────────────────

async def _start_http_server():
    """Inicia o servidor aiohttp.
    - GET /health   → 200 ok  (healthcheck da plataforma)
    - POST /webhook/efi → processa pagamento EFI (só ativo se WEBHOOK_BASE_URL definido)
    """
    try:
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
        app.router.add_get("/health",        health)
        app.router.add_post("/webhook/efi",  efi_webhook)

        port   = int(os.getenv("API_PORT", "8000"))
        runner = web.AppRunner(app)
        await runner.setup()
        site   = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"[HTTP] Servidor iniciado na porta {port} (GET /health ativo)")
    except Exception as e:
        logger.error(f"[HTTP] Falha ao iniciar servidor HTTP: {e}")


# ─────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────

async def main():
    logger.info("Iniciando X1 Frifas Bot...")
    await db.connect()
    log_success("MongoDB conectado!")
    set_bot(bot)

    # HTTP sempre sobe — healthcheck e webhook
    asyncio.create_task(_start_http_server())

    await start_discord_bot(bot)


if __name__ == "__main__":
    asyncio.run(main())
