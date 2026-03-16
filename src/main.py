"""
main.py — Ponto de entrada principal do bot X1 Frifas.
"""
import asyncio
import os
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

from config.database import db
from config.discord_bot import create_discord_bot, start_discord_bot, set_bot
from utils.logger import logger, log_success
from utils.datetime_utils import utcnow
from utils.retry import with_retry, on_rate_limit
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
]

bot = create_discord_bot()
_initialized: bool = False


@on_rate_limit
async def _rate_limit_monitor(endpoint: str, retry_after: float, context: str):
    for guild in bot.guilds:
        ch = discord.utils.get(guild.text_channels, name=RATE_LIMIT_CHANNEL_NAME)
        if ch:
            embed = discord.Embed(title="Rate Limit Detectado", color=0xE74C3C)
            embed.add_field(name="Endpoint",  value=f"`{endpoint}`",         inline=True)
            embed.add_field(name="Aguardar",  value=f"`{retry_after:.1f}s`", inline=True)
            embed.add_field(name="Contexto",  value=context or "—",          inline=False)
            embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
            try:
                await ch.send(embed=embed)
            except Exception:
                pass


@bot.event
async def on_ready():
    global _initialized
    if _initialized:
        logger.warning("[on_ready] Reconexão — pulando reinicialização.")
        return
    _initialized = True

    log_success(f"Bot online: {bot.user} (ID: {bot.user.id})")

    # Carrega cogs
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            logger.info(f"[Cog] ✅ {cog}")
        except Exception as e:
            logger.error(f"[Cog] ❌ {cog}: {e}")

    # Sincroniza slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"[SlashCommands] {len(synced)} comandos sincronizados")
    except Exception as e:
        logger.error(f"[SlashCommands] Erro: {e}")

    # Registra views persistentes
    try:
        from views.ticket_view             import TicketPanelView, TicketCardView
        from views.mediator_panel_view     import MediatorPanelView
        from views.quero_ser_mediador_view import PedidoMediadorView
        from views.spam_block_card_view    import SpamBlockCardView
        from views.match_queue_view        import MatchQueueView
        from views.match_thread_view       import MatchThreadView
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
        from config.channels_config import ChannelsConfig

        persistent_views = [
            TicketPanelView(),
            TicketCardView(ticket_id="__persistent__"),
            MediatorPanelView(),
            PedidoMediadorView(),
            SpamBlockCardView(),
            MatchThreadView(match_id="__persistent__"),
            ExposedPanelView(),
            AnalystCaseView(case_id="__persistent__"),
            AnalystDecisionView(case_id="__persistent__"),
            AnalisePanelView(),
            RenovacaoPanelView(),
            PixPanelView(),
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

        # ✅ MatchQueueView — um por canal+valor para custom_id correto
        for _cat in ChannelsConfig.CATEGORIES.values():
            for _ch in _cat["channels"]:
                for _val in ChannelsConfig.BET_VALUES:
                    try:
                        bot.add_view(MatchQueueView(channel_name=_ch["name"], bet_value=_val))
                    except Exception as e:
                        logger.warning(f"[views] MatchQueueView {_ch['name']} R${_val}: {e}")

        log_success("[views] Views persistentes registradas")
    except Exception as e:
        logger.error(f"[views] Erro ao importar views: {e}")

    # Invite tracker + rate limit monitor
    from services.invite_tracker_service     import invite_tracker_service
    from services.rate_limit_monitor_service import rate_limit_monitor
    invite_tracker_service.bot = bot
    rate_limit_monitor.bot     = bot
    for guild in bot.guilds:
        await invite_tracker_service.cache_guild_invites(guild)
    if not rate_limit_monitor.daily_summary.is_running():
        rate_limit_monitor.daily_summary.start()

    # Onboarding
    from services.onboarding_service import OnboardingService
    bot._onboarding_service = OnboardingService(bot)

    # Fila de mediadores
    from services.mediator_queue import mediator_queue
    await mediator_queue.initialize()

    # Dashboard legado
    from services.mediador_dashboard_service import mediator_dashboard_service
    mediator_dashboard_service.bot = bot
    if not mediator_dashboard_service.daily_update.is_running():
        mediator_dashboard_service.daily_update.start()

    # Card service
    from services.card_service import card_service
    card_service.bot = bot

    # F12 — Analytics service
    from services.analytics_service import analytics_service
    analytics_service.bot = bot
    if not analytics_service.hourly_update.is_running():
        analytics_service.hourly_update.start()
    logger.info("[Analytics] Dashboards inicializados (atualização a cada hora)")

    # F15 — AFK service
    from services.afk_service import afk_service
    afk_service.bot = bot
    if not afk_service.check_queue_afk.is_running():
        afk_service.check_queue_afk.start()
    if not afk_service.check_match_afk.is_running():
        afk_service.check_match_afk.start()
    bot._afk_service = afk_service
    logger.info("[AFK] Serviço inicializado (fila + partida)")

    if not set_status.is_running():
        set_status.start()

    # Thread reuse (R8)
    try:
        from services.thread_reuse_service import init_thread_reuse_service
        init_thread_reuse_service(bot)
        logger.info("[ThreadReuse] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[ThreadReuse] {e}")

    # Analise fila (R8)
    try:
        from services.analise_fila import analise_fila_service
        analise_fila_service.bot = bot
        logger.info("[AnaliseFila] Serviço inicializado")
    except Exception as e:
        logger.warning(f"[AnaliseFila] {e}")

    # Sincroniza mediadores por cargo
    for guild in bot.guilds:
        try:
            await mediator_queue.sync_mediators_by_role(guild, role_name="Controller")
        except Exception as e:
            logger.warning(f"[on_ready] Sync mediadores: {e}")

    # E4 — #status-bot
    asyncio.create_task(_update_status_channel())

    log_success("Bot totalmente inicializado!")


async def _update_status_channel():
    await asyncio.sleep(3)
    for guild in bot.guilds:
        ch = discord.utils.get(guild.text_channels, name=STATUS_BOT_CHANNEL)
        if not ch:
            continue
        embed = discord.Embed(
            title="Status do Sistema",
            description="Todos os sistemas operacionais.",
            color=0x2ECC71
        )
        embed.add_field(name="Bot",   value="🟢 Online",    inline=True)
        embed.add_field(name="Banco", value="🟢 Conectado", inline=True)
        embed.add_field(name="Fila",  value="🟢 Ativa",     inline=True)
        embed.set_footer(text=f"Iniciado em {utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
        try:
            async for msg in ch.history(limit=5):
                if msg.author == guild.me and msg.embeds:
                    await msg.edit(embed=embed)
                    return
            await ch.send(embed=embed)
        except Exception:
            pass


@bot.event
async def on_member_join(member: discord.Member):
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
    error: discord.app_commands.AppCommandError
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


@tasks.loop(minutes=10)
async def set_status():
    import random
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


async def main():
    logger.info("Iniciando X1 Frifas Bot...")
    await db.connect()
    log_success("MongoDB conectado!")
    set_bot(bot)

    if os.getenv("WEBHOOK_BASE_URL", ""):
        asyncio.create_task(_start_webhook_server())
        logger.info("[Webhook] Servidor HTTP iniciado na porta 8000")

    await start_discord_bot(bot)


async def _start_webhook_server():
    try:
        from aiohttp import web

        async def efi_webhook(request: web.Request) -> web.Response:
            try:
                data   = await request.json()
                txid   = data.get("txid") or data.get("txId", "")
                status = data.get("status", "")
                if status == "CONCLUIDA" and txid:
                    from config.database import db
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


if __name__ == "__main__":
    asyncio.run(main())
