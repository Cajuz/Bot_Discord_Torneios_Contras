# main.py

import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime, timezone

from services.thread_log_service import init_thread_log_service
from services.faturamento_mediador import FaturamentoMediadorService, FaturamentoView, RelatorioGeralView
from views.mediator_panel_view import create_mediator_panel_embed, MediatorPanelView
from services.thread_reuse_service import init_thread_reuse_service
from views.match_thread_view import (
    PrizeConfirmView,
    cmd_menu_partida,
    cmd_winner_team,
    cmd_prize,
    cmd_confirmar_pagamento,
    cmd_iniciar_partida,
    cmd_cancelar_match,
)
from views.ticket_view import (
    TicketPanelView,
    SupportCardView,
    cmd_fechar_chamado,
    cmd_concluir_chamado,
)
from config.database import db
from config.discord_bot import create_discord_bot, start_discord_bot
from services.mediator_queue import mediator_queue
from services.match_service import match_service
from services.match_queue_service import match_queue_service
from config.channels_config import ChannelsConfig
from utils.logger import logger, log_success
from services.channel_service import (
    ChannelService,
    AVISOS_CHANNEL_NAME,
    MEDIATOR_ROLE_NAME,
    SUPPORT_ROLE_NAME,
    ADM_ROLE_NAME,
    HEALTH_CHECK_CHANNEL_NAME,       # ← NOVO
    QUEROSERMEDIADOR_CHANNEL,
)
from services.onboarding_service import OnboardingService
from services.mediador_dashboard_service import mediator_dashboard_service
from services.anti_spam_service import AntiSpamService, SPAM_BLOCK_ROLE_NAME
from views.spam_block_card_view import SpamBlockCardView, set_anti_spam_service
from services.channel_service import QUEROSERMEDIADOR_CHANNEL,ATENDIMENTO_CATEGORY,MEDIATOR_CATEGORY

# ── NOVO — Health Check ───────────────────────────────────────────────────────
from services.health_check_service import init_health_check_service, set_bot_start_time
from views.health_check_view import build_overview_embed, HealthCheckView
# ─────────────────────────────────────────────────────────────────────────────
#TESTE
from services.pedido_mediador import PedidomediadorEmbed, PedidoMediadorValor, PedidoMediadorAdminView


load_dotenv()

bot = create_discord_bot()

thread_reuse_service = None
onboarding_service   = None
channel_service      = None
health_check_svc     = None          # ← NOVO
anti_spam_service    = AntiSpamService(bot)
set_anti_spam_service(anti_spam_service)

    


# ==================== EVENTOS ====================


@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user}')
    await mediator_queue.initialize()

    for guild in bot.guilds:
        await mediator_queue.sync_mediators_by_role(guild, MEDIATOR_ROLE_NAME)
        print(f"✅ Mediadores sincronizados em {guild.name}")

        try:
            await anti_spam_service.ensure_role_and_overwrites(guild)
            await anti_spam_service.restore_blocked_members(guild)
        except Exception as e:
            logger.error(f"Erro ao inicializar AntiSpam em {guild.name}: {e}")

    # ── Threads ───────────────────────────────────────────────────────────────
    global thread_reuse_service
    thread_reuse_service = init_thread_reuse_service(bot)
    logger.info("✅ ThreadReuseService inicializado")
    init_thread_log_service(bot)
    logger.info("✅ ThreadLogService inicializado")

    for guild in bot.guilds:
        try:
            result = await thread_reuse_service.validate_pool(guild)
            logger.info(f"Pool validado em {guild.name}: {result}")
        except Exception as e:
            logger.error(f"Erro ao validar pool em {guild.name}: {e}")

    # ── NOVO — Health Check ───────────────────────────────────────────────────
    global health_check_svc
    set_bot_start_time(datetime.now(timezone.utc))
    health_check_svc = init_health_check_service(bot)
    logger.info("✅ HealthCheckService inicializado")
    # ─────────────────────────────────────────────────────────────────────────

    # ── Views persistentes ────────────────────────────────────────────────────
    bot.add_view(PrizeConfirmView(match_id="placeholder", winner_players=[], winner_team="blue"))
    bot.add_view(TicketPanelView(bot))
    bot.add_view(SupportCardView())
    bot.add_view(SpamBlockCardView())

    if not mediator_dashboard_service.daily_update.is_running():
        mediator_dashboard_service.bot = bot
        mediator_dashboard_service.daily_update.start()

    print('🚀 Bot pronto!')


@bot.event
async def on_message(message: discord.Message):
    """
    IMPORTANTE: como temos on_message, precisamos chamar bot.process_commands
    para não quebrar os comandos prefixados (!comando).
    """
    try:
        if anti_spam_service:
            await anti_spam_service.process_message(message)
    except Exception as e:
        logger.error(f"Erro no anti-spam on_message: {e}")
    finally:
        await bot.process_commands(message)


@bot.event
async def on_member_join(member: discord.Member):
    try:
        if anti_spam_service:
            await anti_spam_service.handle_member_join(member)

        if onboarding_service:
            await onboarding_service.handle_new_member(member)
        else:
            logger.error("Onboarding service não inicializado")
    except Exception as e:
        logger.error(f"Erro no on_member_join: {e}")


@bot.event
async def on_member_remove(member: discord.Member):
    try:
        collection = db.get_collection('users')
        await collection.update_one(
            {'discord_id': str(member.id)},
            {'$set': {'is_active': False, 'updated_at': datetime.utcnow()}}
        )
        logger.info(f"Membro {member.name} saiu do servidor")
    except Exception as e:
        logger.error(f"Erro no on_member_remove: {e}")


# ==================== COMANDOS DE MEDIAÇÃO (thread) ====================


@bot.command(name='menu_partida')
async def menu_partida(ctx):
    await cmd_menu_partida(ctx)


@bot.command(name='confirmar_pagamento')
async def confirmar_pagamento(ctx):
    await cmd_confirmar_pagamento(ctx)


@bot.command(name='iniciar_partida')
async def iniciar_partida(ctx):
    await cmd_iniciar_partida(ctx)


@bot.command(name='winner_team')
async def winner_team(ctx, team: str = None):
    if not team:
        try:
            await ctx.author.send("❌ Use: `!winner_team blue` ou `!winner_team red`")
        except discord.Forbidden:
            pass
        await ctx.message.delete()
        return
    await cmd_winner_team(ctx, team)


@bot.command(name='prize')
async def prize(ctx):
    await cmd_prize(ctx)


@bot.command(name='cancelar_match')
async def cancelar_match_cmd(ctx, *, reason: str = None):
    await cmd_cancelar_match(ctx, reason)


# ==================== COMANDOS DE SUPORTE ====================


@bot.command(name='fechar_chamado')
async def fechar_chamado(ctx, ticket_id: str = None):
    if not ticket_id:
        await ctx.message.delete()
        try:
            await ctx.author.send("❌ Use: `!fechar_chamado TKT-00000001`")
        except discord.Forbidden:
            pass
        return
    await cmd_fechar_chamado(ctx, ticket_id)


@bot.command(name='concluir_chamado')
@commands.has_any_role(SUPPORT_ROLE_NAME, ADM_ROLE_NAME)
async def concluir_chamado(ctx, ticket_id: str = None):
    if not ticket_id:
        await ctx.message.delete()
        try:
            await ctx.author.send("❌ Use: `!concluir_chamado TKT-00000001`")
        except discord.Forbidden:
            pass
        return
    await cmd_concluir_chamado(ctx, ticket_id)


@bot.command(name="faturamentos_geral")
@commands.has_permissions(administrator=True) # Recomendado: apenas admins podem ver o geral
async def faturamentos_geral(ctx):
    """Exibe a interface para gerar o relatório de faturamento de todos os mediadores."""
    
    # Criamos um embed simples para apresentar o botão
    embed = discord.Embed(
        title="📊 Central de Faturamento Geral",
        description=(
            "Clique no botão abaixo para processar os dados de todos os mediadores "
            "e gerar o ranking atualizado em formato `.txt`."
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="O processamento pode levar alguns segundos dependendo do volume de dados.")

    # Instancia a view que você já criou
    view = RelatorioGeralView()
    
    await ctx.send(embed=embed, view=view)

# Opcional: Tratamento de erro caso alguém sem permissão use o comando
@faturamentos_geral.error
async def faturamentos_geral_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão para visualizar o faturamento geral.")



# ==================== COMANDOS ADMINISTRATIVOS ====================

@bot.command(name="confirmarmediador")
@commands.has_permissions(administrator=True)
async def confirmarmediador(ctx, membro: discord.Member):
    guild = ctx.guild

    # Pega o cargo de mediador
    mediator_role = discord.utils.get(guild.roles, name=MEDIATOR_ROLE_NAME)
    if not mediator_role:
        await ctx.send(f"❌ Cargo `{MEDIATOR_ROLE_NAME}` não encontrado.")
        return

    # Adiciona o cargo ao usuário
    try:
        await membro.add_roles(mediator_role, reason=f"Aprovado por {ctx.author}")
    except Exception as e:
        await ctx.send(f"❌ Erro ao adicionar cargo: {e}")
        return

    # Envia DM para o usuário
    try:
        await membro.send(
            f"✅ Parabéns! Você foi promovido a **{MEDIATOR_ROLE_NAME}** pelo {ctx.author.mention}.\n"
            "Agora você tem acesso aos canais e privilégios de mediador."
        )
    except discord.Forbidden:
        await ctx.send(f"⚠️ Não foi possível enviar DM para {membro.mention}.")

    await ctx.send(f"✅ {membro.mention} agora é **{MEDIATOR_ROLE_NAME}** e recebeu a DM de confirmação.")

@bot.command(name="faturamento")
@commands.has_permissions(administrator=True)
async def faturamento(ctx, mediador_id: str = None):
    """Comando !faturamento ID"""
    
    # Se não passar ID, usa o ID de quem chamou
    target_id = mediador_id if mediador_id else str(ctx.author.id)
    
    # Busca membro para pegar nome e avatar
    member = ctx.guild.get_member(int(target_id))
    nome = member.display_name if member else "Mediador"
    avatar = member.display_avatar.url if member else ctx.author.display_avatar.url

    service = FaturamentoMediadorService()
    partidas = await service.buscar_partidas_do_banco(target_id)
    
    view = FaturamentoView(service, partidas, target_id, nome, avatar)
    embed = await view.gerar_embed(1) # Padrão Hoje
    
    await ctx.send(embed=embed, view=view)



    

@bot.command(name='setupcanais')
@commands.has_permissions(administrator=True)
async def setup_canais(ctx):
    if not channel_service:
        await ctx.send("❌ Sistema ainda não foi inicializado completamente.")
        return
    try:
        msg = await ctx.send("⏳ Configurando servidor completo... (pode demorar alguns segundos)")
        await channel_service.setup_all_channels(ctx.guild)

        try:
            await anti_spam_service.ensure_role_and_overwrites(ctx.guild)
        except Exception as e:
            logger.error(f"Erro AntiSpam pós-setupcanais: {e}")

        # ── NOVO: posta o health check no canal recém-criado ──────────────
        try:
            hc_channel = discord.utils.get(ctx.guild.text_channels, name=HEALTH_CHECK_CHANNEL_NAME)
            if hc_channel and health_check_svc:
                # Remove painel antigo se existir
                async for old_msg in hc_channel.history(limit=10):
                    if old_msg.author == ctx.guild.me and old_msg.embeds:
                        await old_msg.delete()
                        break
                report   = await health_check_svc.run(
                    guild          = ctx.guild,
                    anti_spam_svc  = anti_spam_service,
                    onboarding_svc = onboarding_service,
                )
                hc_embed = build_overview_embed(report)
                hc_view  = HealthCheckView(
                    report         = report,
                    service        = health_check_svc,
                    guild          = ctx.guild,
                    anti_spam_svc  = anti_spam_service,
                    onboarding_svc = onboarding_service,
                )
                await hc_channel.send(embed=hc_embed, view=hc_view)
                logger.info("Health check postado em #health-check")
        except Exception as e:
            logger.error(f"Erro ao postar health check pós-setup: {e}")
        # ─────────────────────────────────────────────────────────────────

        embed = discord.Embed(
            title="✅ Servidor Configurado!",
            description="Toda a estrutura foi criada/atualizada com sucesso.",
            color=discord.Color.green()
        )
        embed.add_field(name="📈 ANALYTICS",    value="• dashboard-partidas\n• historico-partidas\n• logs-partidas",  inline=True)
        embed.add_field(name="📊 DASHBOARD",    value="• health-check",                                               inline=True)
        embed.add_field(name="🚫 BANS-CONTROL", value="• membros-bloqueados",                                         inline=True)
        embed.add_field(name="ℹ️ INFORMAÇÕES",  value="• 📜regras\n• 📢avisos",                                       inline=True)
        embed.add_field(name="🧑‍⚖️ MEDIADORES", value="• painel-mediadores\n• chat-mediadores",                        inline=True)
        embed.add_field(
            name="🎫 SUPORTE",
            value="• suporte\n• chat-suporte\n• chamados-suporte\n• chat-chamados",
            inline=True
        )
        embed.add_field(name="🎭 Cargos",       value="• Membro\n• Controller\n• Suporte\n• ADM",                     inline=True)
        embed.add_field(
            name="💰 Valores",
            value="R$2 • R$5 • R$10 • R$20 • R$50 • R$100 • R$200",
            inline=False
        )
        embed.set_footer(text="Use !sincmediadores para sincronizar mediadores após o setup.")
        await msg.edit(content=None, embed=embed)

    except Exception as e:
        logger.error(f"Erro no setupcanais: {e}")
        await ctx.send(f"❌ Erro: {str(e)}")

@bot.command(name="testecanal")
@commands.has_permissions(administrator=True)
async def teste_possivel_mediador(ctx):
    try:
        embed = PedidomediadorEmbed.beneficios()

        await ctx.send(
            embed=embed,
            view=PedidoMediadorValor()
        )
    except Exception as e:
        logger.error(f"Erro de teste: {e}")
        await ctx.send(f"❌ Erro: {str(e)}")






@bot.command(name='dashboard')
@commands.has_permissions(administrator=True)
async def dashboard_manual(ctx):
    try:
        await ctx.message.add_reaction("✅")
        dash_channel = await channel_service.ensure_dashboard_channel(ctx.guild)
        if dash_channel:
            await mediator_dashboard_service.update_dashboard_for_channel(dash_channel)
        else:
            await ctx.send("❌ Não foi possível criar/encontrar o canal dashboard-partidas.")
    except Exception as e:
        logger.error(f"Erro no dashboard manual: {e}")
        await ctx.send(f"❌ Erro: {e}")


@bot.command(name='aviso')
@commands.has_permissions(administrator=True)
async def postar_aviso(ctx, *, texto: str = None):
    if not texto:
        await ctx.reply("❌ Use: `!aviso Texto do aviso`")
        return
    try:
        avisos_channel = discord.utils.get(ctx.guild.text_channels, name=AVISOS_CHANNEL_NAME)
        if not avisos_channel:
            await ctx.reply(f"❌ Canal `{AVISOS_CHANNEL_NAME}` não encontrado. Use `!setupcanais`.")
            return

        embed = discord.Embed(
            title="📢 Aviso Oficial",
            description=texto,
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Postado por {ctx.author.display_name}")
        embed.timestamp = datetime.utcnow()

        await avisos_channel.send(content="@everyone", embed=embed)
        await ctx.reply(f"✅ Aviso postado em {avisos_channel.mention}!")

    except discord.Forbidden:
        await ctx.reply("❌ Sem permissão para postar no canal de avisos.")
    except Exception as e:
        logger.error(f"Erro ao postar aviso: {e}")
        await ctx.reply(f"❌ Erro: {e}")


@bot.command(name='atualizarmediadores')
@commands.has_permissions(administrator=True)
async def atualizar_painel_mediadores(ctx):
    try:
        channel = discord.utils.get(ctx.guild.channels, name="painel-mediadores")
        if not channel:
            await ctx.send("❌ Canal #painel-mediadores não encontrado. Use `!setupcanais`.")
            return

        await ctx.send("🔄 Atualizando painel...")

        bot_message = None
        async for msg in channel.history(limit=20):
            if msg.author == bot.user and msg.embeds:
                bot_message = msg
                break

        info  = await mediator_queue.get_queue_info()
        embed = create_mediator_panel_embed(info)
        view  = MediatorPanelView()

        if bot_message:
            await bot_message.edit(embed=embed, view=view)
        else:
            await channel.send(embed=embed, view=view)

        await ctx.send(f"✅ Painel atualizado em {channel.mention}!")

    except discord.Forbidden:
        await ctx.send("❌ Sem permissão para acessar o canal #painel-mediadores.")
    except Exception as e:
        logger.error(f"Erro ao atualizar painel: {e}")
        await ctx.send(f"❌ Erro: {e}")


@bot.command(name='sincmediadores')
@commands.has_permissions(administrator=True)
async def sync_mediators(ctx):
    await ctx.send("🔄 Sincronizando mediadores...")
    await mediator_queue.sync_mediators_by_role(ctx.guild, MEDIATOR_ROLE_NAME)
    info  = await mediator_queue.get_queue_info()
    embed = discord.Embed(
        title="✅ Sincronização Completa",
        description=f"Mediadores sincronizados com o cargo **{MEDIATOR_ROLE_NAME}**",
        color=discord.Color.green()
    )
    embed.add_field(
        name="📊 Estatísticas",
        value=f"**Total Ativos:** {info['total_active']}\n**Na Fila:** {info['in_queue']}",
        inline=False
    )
    await ctx.send(embed=embed)


# ─────────── AntiSpam: comandos ADM ───────────

@bot.command(name='bloquear')
@commands.has_permissions(administrator=True)
async def bloquear_spam(ctx, member: discord.Member = None, *, motivo: str = None):
    if not member:
        await ctx.reply("❌ Use: `!bloquear @usuario [motivo]`")
        return
    try:
        await anti_spam_service.block_member_manual(
            guild=ctx.guild,
            member=member,
            by=ctx.author,
            reason=motivo or "Bloqueio manual por administrador"
        )
        await ctx.reply(f"🚫 {member.mention} foi bloqueado (cargo **{SPAM_BLOCK_ROLE_NAME}**).")
    except Exception as e:
        logger.error(f"Erro no bloquear: {e}")
        await ctx.reply(f"❌ Erro: {e}")


@bot.command(name='desbloquear')
@commands.has_permissions(administrator=True)
async def desbloquear_spam(ctx, member: discord.Member = None):
    if not member:
        await ctx.reply("❌ Use: `!desbloquear @usuario`")
        return
    try:
        await anti_spam_service.unblock_member(ctx.guild, member, by=ctx.author)
        await ctx.reply(f"✅ {member.mention} foi desbloqueado.")
    except Exception as e:
        logger.error(f"Erro no desbloquear: {e}")
        await ctx.reply(f"❌ Erro: {e}")


@bot.command(name='stats')
@commands.has_permissions(administrator=True)
async def stats_onboarding(ctx):
    try:
        col       = db.get_collection('users')
        total     = await col.count_documents({})
        aceitos   = await col.count_documents({'onboarding_result': 'aceito'})
        recusados = await col.count_documents({'onboarding_result': 'recusado'})
        timeout   = await col.count_documents({'onboarding_result': 'timeout'})
        dm_bloq   = await col.count_documents({'onboarding_result': 'dm_bloqueada'})
        pendentes = await col.count_documents({'onboarding_result': 'pendente'})
        bloqueados_spam = await col.count_documents({'spam_blocked': True})
        taxa      = (aceitos / total * 100) if total > 0 else 0.0

        embed = discord.Embed(title="📊 Estatísticas de Onboarding", color=discord.Color.blurple())
        embed.add_field(name="📥 Total",           value=f"**{total}**",           inline=False)
        embed.add_field(name="✅ Aceitaram",       value=f"**{aceitos}**",         inline=True)
        embed.add_field(name="❌ Recusaram",       value=f"**{recusados}**",       inline=True)
        embed.add_field(name="⏰ Timeout",         value=f"**{timeout}**",         inline=True)
        embed.add_field(name="🚫 DM Bloqueada",    value=f"**{dm_bloq}**",         inline=True)
        embed.add_field(name="⏳ Pendentes",       value=f"**{pendentes}**",       inline=True)
        embed.add_field(name="🛑 Bloqueados Spam", value=f"**{bloqueados_spam}**", inline=True)
        embed.add_field(name="📈 Taxa Aceitação",  value=f"**{taxa:.1f}%**",       inline=False)
        embed.set_footer(text="collection: users | MongoDB")
        embed.timestamp = datetime.utcnow()
        await ctx.reply(embed=embed)

    except Exception as e:
        logger.error(f"Erro no stats: {e}")
        await ctx.reply(f"❌ Erro: {e}")


@bot.command(name='testarregras')
@commands.has_permissions(administrator=True)
async def testar_regras(ctx):
    if not onboarding_service:
        await ctx.reply("❌ Sistema ainda não inicializado.")
        return
    try:
        await onboarding_service.handle_new_member(ctx.author, is_test=True)
        await ctx.reply("✅ Teste iniciado! Verifique sua DM.")
    except Exception as e:
        logger.error(f"Erro no testarregras: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


@bot.command(name='simularfila')
@commands.has_permissions(administrator=True)
async def simular_fila(ctx, channel_name: str = None, bet_value: float = 10.0, gel_type: str = "normal"):
    try:
        channel_name = channel_name or ctx.channel.name
        if channel_name not in ChannelsConfig.get_all_channel_names():
            await ctx.send(f"❌ Canal inválido. Válidos: {', '.join(ChannelsConfig.get_all_channel_names())}")
            return

        if gel_type == "infinito" and not ChannelsConfig.has_gel_infinito(channel_name):
            await ctx.send("❌ GEL INFINITO só está disponível para `1x1-mob`.")
            return

        await ctx.send(f"🧪 Simulando: `{channel_name}` | R${bet_value:.2f} | GEL {gel_type.upper()}...")

        queue_key = match_queue_service.get_queue_key(channel_name, bet_value, gel_type)
        match_queue_service.active_queues.pop(queue_key, None)

        queue = None
        for i in range(2):
            player_id = ctx.author.id + i
            success, queue, message = await match_queue_service.add_player_to_queue(
                channel_name=channel_name,
                bet_value=bet_value,
                gel_type=gel_type,
                max_players=2,
                player_id=player_id
            )
            if not success and i == 0:
                await ctx.send(f"❌ Erro: {message}")
                return

        if not queue:
            await ctx.send("❌ Fila não criada.")
            return

        queue.confirmations = list(queue.players)
        await match_queue_service._save_queue(queue)
        await match_queue_service._create_match_from_queue_compat(
            queue=queue, bot=bot, channel=ctx.channel
        )
        await ctx.send("✅ Simulação iniciada! Verifique o tópico criado.")

    except Exception as e:
        logger.error(f"Erro na simulação: {e}", exc_info=True)
        await ctx.send(f"❌ Erro: {e}")


@bot.command(name='inspecionar')
@commands.has_permissions(administrator=True)
async def inspecionar_match(ctx, match_id: str):
    match = await match_service.get_match(match_id)
    if not match:
        await ctx.reply("❌ Match não encontrado.")
        return
    campos = [
        f"**status:** `{match.get('status')}`",
        f"**time_blue:** {match.get('time_blue')}",
        f"**time_red:** {match.get('time_red')}",
        f"**mediator_id:** {match.get('mediator_id')}",
        f"**thread_id:** {match.get('thread_id')}",
        f"**vencedor:** {match.get('vencedor')}",
        f"**pagamento_confirmado:** {match.get('pagamento_confirmado')}",
        f"**premio_entregue_mediador:** {match.get('premio_entregue_mediador')}",
        f"**premio_confirmado_jogador:** {match.get('premio_confirmado_jogador')}",
        f"**cancelled_by:** {match.get('cancelled_by')}",
        f"**cancel_reason:** {match.get('cancel_reason')}",
        f"**created_at:** {match.get('created_at')}",
    ]
    embed = discord.Embed(
        title=f"🔍 Match `{match_id}`",
        description="\n".join(campos),
        color=discord.Color.blurple()
    )
    await ctx.reply(embed=embed)


# ==================== COMANDOS DE CARDS ====================


@bot.command(name='atualizarcards')
@commands.has_permissions(administrator=True)
async def atualizar_cards(ctx, canal: discord.TextChannel = None):
    if not channel_service:
        await ctx.send("❌ Sistema ainda não foi inicializado completamente.")
        return
    try:
        channel      = canal or ctx.channel
        channel_name = channel.name
        if channel_name not in ChannelsConfig.get_all_channel_names():
            await ctx.send(f"❌ {channel.mention} não é um canal de partidas válido!")
            return

        confirm_embed = discord.Embed(
            title="⚠️ Atualizar Cards",
            description=f"Vai **deletar** todos os cards antigos em {channel.mention} e criar novos.\n\nDeseja continuar?",
            color=discord.Color.orange()
        )
        msg = await ctx.send(embed=confirm_embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id

        try:
            reaction, _ = await bot.wait_for('reaction_add', timeout=30.0, check=check)
            if str(reaction.emoji) == "❌":
                await msg.delete()
                await ctx.send("❌ Cancelado.")
                return
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.send("❌ Tempo esgotado.")
            return

        await msg.delete()
        status_msg = await ctx.send(f"🔄 Atualizando cards em {channel.mention}...")
        success    = await channel_service.setup_queue_cards(ctx.guild, channel)
        await status_msg.edit(content=(
            f"✅ Cards atualizados em {channel.mention}!"
            if success else
            f"❌ Erro ao atualizar cards em {channel.mention}"
        ))
    except Exception as e:
        logger.error(f"Erro ao atualizar cards: {e}")
        await ctx.send(f"❌ Erro: {e}")


@bot.command(name='atualizartodos')
@commands.has_permissions(administrator=True)
async def atualizar_todos_cards(ctx):
    if not channel_service:
        await ctx.send("❌ Sistema ainda não foi inicializado completamente.")
        return
    try:
        confirm_embed = discord.Embed(
            title="⚠️ Atualizar TODOS os Cards",
            description="Vai **deletar** todos os cards em **TODOS** os canais.\n\n⚠️ Pode demorar alguns minutos.\n\nDeseja continuar?",
            color=discord.Color.red()
        )
        msg = await ctx.send(embed=confirm_embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id

        try:
            reaction, _ = await bot.wait_for('reaction_add', timeout=30.0, check=check)
            if str(reaction.emoji) == "❌":
                await msg.delete()
                await ctx.send("❌ Cancelado.")
                return
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.send("❌ Tempo esgotado.")
            return

        await msg.delete()
        valid_names        = ChannelsConfig.get_all_channel_names()
        channels_to_update = [c for c in ctx.guild.text_channels if c.name in valid_names]

        if not channels_to_update:
            await ctx.send("❌ Nenhum canal de partida encontrado!")
            return

        status_msg    = await ctx.send(f"🔄 Atualizando {len(channels_to_update)} canais...")
        success_count = 0

        for i, channel in enumerate(channels_to_update, 1):
            await status_msg.edit(content=f"🔄 Canal {i}/{len(channels_to_update)}: {channel.mention}")
            if await channel_service.setup_queue_cards(ctx.guild, channel):
                success_count += 1
            await asyncio.sleep(2)

        await status_msg.edit(
            content=None,
            embed=discord.Embed(
                title="✅ Atualização Concluída",
                description=f"Cards atualizados em **{success_count}/{len(channels_to_update)}** canais",
                color=discord.Color.green()
            )
        )
    except Exception as e:
        logger.error(f"Erro ao atualizar todos os cards: {e}")
        await ctx.send(f"❌ Erro: {e}")


# ==================== HEALTH CHECK ==================== ← NOVO


@bot.command(name='healthcheck')
@commands.has_permissions(administrator=True)
async def health_check(ctx):
    """!healthcheck — exibe o painel de saúde do sistema no canal #health-check"""
    if not health_check_svc:
        await ctx.reply("❌ HealthCheckService não inicializado.")
        return

    # Garante que só seja usado no canal correto
    if ctx.channel.name != HEALTH_CHECK_CHANNEL_NAME:
        hc_channel = discord.utils.get(ctx.guild.text_channels, name=HEALTH_CHECK_CHANNEL_NAME)
        if hc_channel:
            await ctx.reply(
                f"❌ Use este comando em {hc_channel.mention}.",
                delete_after=10
            )
        else:
            await ctx.reply("❌ Canal `#health-check` não encontrado. Use `!setupcanais`.")
        try:
            await ctx.message.delete(delay=10)
        except Exception:
            pass
        return

    msg = await ctx.reply("⏳ Coletando dados do sistema...")

    try:
        report = await health_check_svc.run(
            guild          = ctx.guild,
            anti_spam_svc  = anti_spam_service,
            onboarding_svc = onboarding_service,
        )

        embed = build_overview_embed(report)
        view  = HealthCheckView(
            report         = report,
            service        = health_check_svc,
            guild          = ctx.guild,
            anti_spam_svc  = anti_spam_service,
            onboarding_svc = onboarding_service,
        )

        await msg.edit(content=None, embed=embed, view=view)

    except Exception as e:
        logger.error(f"Erro no healthcheck: {e}", exc_info=True)
        await msg.edit(content=f"❌ Erro ao executar health check: {e}")


# ==================== COMANDOS DE PARTIDA ====================


@bot.command(name='partidas')
async def ver_partidas(ctx):
    try:
        matches = await match_service.get_active_matches()
        if not matches:
            await ctx.reply("📭 Nenhuma partida ativa no momento")
            return
        status_emoji = {
            'aguardando_pagamento': '💰',
            'aguardando_inicio':    '⏳',
            'em_andamento':         '▶️',
            'aguardando_premio':    '🎁',
        }
        embed = discord.Embed(
            title="🎮 Partidas Ativas",
            description=f"Total: **{len(matches)}** partidas",
            color=discord.Color.purple()
        )
        for match in matches[:5]:
            emoji       = status_emoji.get(match['status'], '❓')
            players_str = " • ".join(f"<@{pid}>" for pid in match.get('player_ids', []))
            thread_info = f"\n🧵 <#{match['thread_id']}>" if match.get('thread_id') else ""
            embed.add_field(
                name=f"{emoji} `{match['_id']}` — {match.get('match_type','?')} R${match.get('bet_value',0):.2f}",
                value=f"👥 {players_str}\n🕵️ <@{match.get('mediator_id','?')}>\n📊 {match['status']}{thread_info}",
                inline=False
            )
        if len(matches) > 5:
            embed.set_footer(text=f"Mostrando 5 de {len(matches)} partidas")
        await ctx.reply(embed=embed)
    except Exception as e:
        logger.error(f"Erro no partidas: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


@bot.command(name='cancelarpartida')
@commands.has_permissions(administrator=True)
async def cancelar_partida(ctx, match_id: str, *, reason: str = None):
    try:
        result = await match_service.cancel_match(
            match_id=match_id,
            cancelled_by=ctx.author.id,
            reason=reason or "Cancelado por administrador"
        )
        if not result:
            await ctx.reply("❌ Partida não encontrada ou já finalizada.")
            return

        embed = discord.Embed(
            title="🚫 Partida Cancelada",
            description=f"A partida `{match_id}` foi cancelada por {ctx.author.mention}.",
            color=discord.Color.red()
        )
        if reason:
            embed.add_field(name="Motivo", value=reason, inline=False)

        thread_id = result.get('thread_id')
        if thread_id:
            raw_id = int(thread_id) if isinstance(thread_id, str) else thread_id
            thread = bot.get_channel(raw_id)
            if thread:
                await thread.send(
                    embed=discord.Embed(
                        title="❌ Partida Cancelada por Administrador",
                        description=f"Cancelada por {ctx.author.mention}."
                        + (f"\n**Motivo:** {reason}" if reason else ""),
                        color=discord.Color.red()
                    )
                )
        await ctx.reply(embed=embed)

    except Exception as e:
        logger.error(f"Erro no cancelarpartida: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


@bot.command(name='forcarconcluir')
@commands.has_permissions(administrator=True)
async def forcar_concluir(ctx, match_id: str):
    try:
        result = await match_service.force_complete(match_id, admin_id=ctx.author.id)
        if not result:
            await ctx.reply("❌ Partida não encontrada.")
            return
        embed = discord.Embed(
            title="⚡ Partida Forçada como Finalizada",
            description=f"A partida `{match_id}` foi finalizada por {ctx.author.mention}.",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)
    except Exception as e:
        logger.error(f"Erro no forcarconcluir: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


# ==================== COMANDOS DE MEDIADOR ====================


@bot.command(name='addmediador')
@commands.has_any_role(MEDIATOR_ROLE_NAME, ADM_ROLE_NAME)
async def add_mediador(ctx):
    try:
        mediator = await mediator_queue.add_mediator(str(ctx.author.id), ctx.author.name)
        embed = discord.Embed(
            title="✅ Mediador Adicionado",
            description=f"Você entrou na fila na posição **{mediator.position}**",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)
    except Exception as e:
        logger.error(f"Erro no addmediador: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


@bot.command(name='removemediador')
@commands.has_any_role(MEDIATOR_ROLE_NAME, ADM_ROLE_NAME)
async def remove_mediador(ctx):
    try:
        await mediator_queue.remove_mediador(str(ctx.author.id))
        embed = discord.Embed(
            title="🚫 Mediador Removido",
            description="Você saiu da fila de mediadores",
            color=discord.Color.orange()
        )
        await ctx.reply(embed=embed)
    except Exception as e:
        logger.error(f"Erro no removemediador: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


@bot.command(name='fila')
async def ver_fila(ctx):
    try:
        stats = await mediator_queue.get_queue_stats()
        if stats['total_active'] == 0:
            await ctx.reply("📭 Nenhum mediador ativo na fila")
            return
        embed = discord.Embed(
            title="📋 Fila de Mediadores",
            description=f"Total: **{stats['total_active']}**",
            color=discord.Color.blue()
        )
        for m in stats['mediators'][:10]:
            status_emoji_med = "✅" if m['can_mediate'] else "⏳"
            embed.add_field(
                name=f"{status_emoji_med} Posição {m['position']} — {m['username']}",
                value=f"Total: {m['total_matches']} | Últimos 8min: {m['matches_in_last_8_min']}/5",
                inline=False
            )
        if stats['total_active'] > 10:
            embed.set_footer(text=f"Mostrando 10 de {stats['total_active']}")
        await ctx.reply(embed=embed)
    except Exception as e:
        logger.error(f"Erro no fila: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


# ==================== THREAD POOL ====================


@bot.command(name='threadstatus')
@commands.has_permissions(administrator=True)
async def thread_status(ctx):
    """!threadstatus — status do pool e limite do servidor"""
    from services.thread_reuse_service import thread_reuse_service as trs
    if not trs:
        await ctx.reply("❌ ThreadReuseService não inicializado.")
        return

    health = await trs.get_health(ctx.guild)
    embed  = discord.Embed(
        title="🧵 Status do Sistema de Threads",
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="📦 Pool (disponíveis)",
        value=f"**{health['pool_total']}** threads prontas para reuso",
        inline=False
    )
    embed.add_field(name="⚔️ Em partida agora",  value=f"**{health['active_matches']}**",        inline=True)
    embed.add_field(name="📊 Limite Discord",     value=f"**{health['live_discord']}/1.000**",    inline=True)
    embed.add_field(name="🟢 Margem disponível",  value=f"**{health['margem']}**",                inline=True)

    if health.get('pool_by_channel'):
        lines = []
        for cid, n in health['pool_by_channel'].items():
            ch   = ctx.guild.get_channel(int(cid))
            name = f"#{ch.name}" if ch else cid
            lines.append(f"• `{name}`: {n}")
        embed.add_field(name="📋 Pool por canal", value="\n".join(lines), inline=False)

    if health['margem'] < 100:
        embed.add_field(
            name="⚠️ ATENÇÃO",
            value="Margem abaixo de 100! Use `!preaquecerpool` para garantir threads arquivadas.",
            inline=False
        )
    embed.set_footer(text="Threads arquivadas não contam no limite de 1.000")
    await ctx.reply(embed=embed)


@bot.command(name='preaquecerpool')
@commands.has_permissions(administrator=True)
async def preaquecer_pool(ctx, canal: discord.TextChannel = None, quantidade: int = 3):
    """!preaquecerpool [#canal] [quantidade] — pré-aquece o pool com threads arquivadas"""
    from services.thread_reuse_service import thread_reuse_service as trs
    if not trs:
        await ctx.reply("❌ ThreadReuseService não inicializado.")
        return

    channel = canal or ctx.channel

    if not 1 <= quantidade <= 10:
        await ctx.reply("❌ Quantidade deve ser entre 1 e 10.")
        return

    slow = await trs.check_slow_mode(channel)
    if slow > 0:
        await ctx.reply(
            f"⚠️ Canal `#{channel.name}` tem slow mode de **{slow}s**. "
            f"Pré-aquecimento pode ser mais lento."
        )

    msg     = await ctx.reply(f"⏳ Pré-aquecendo {quantidade} thread(s) em {channel.mention}...")
    created = await trs.preaquecer(channel=channel, quantidade=quantidade)

    embed = discord.Embed(
        title="✅ Pré-aquecimento Concluído",
        description=f"**{created}** thread(s) criadas e arquivadas em {channel.mention}",
        color=discord.Color.green()
    )
    embed.set_footer(text="Threads arquivadas não contam no limite de 1.000 do Discord")
    await msg.edit(content=None, embed=embed)


@bot.command(name='validarpool')
@commands.has_permissions(administrator=True)
async def validar_pool(ctx):
    """!validarpool — remove entradas inválidas do banco de threads"""
    from services.thread_reuse_service import thread_reuse_service as trs
    if not trs:
        await ctx.reply("❌ ThreadReuseService não inicializado.")
        return

    msg    = await ctx.reply("🔍 Validando pool de threads...")
    result = await trs.validate_pool(ctx.guild)

    embed = discord.Embed(
        title="🧹 Pool Validado",
        color=discord.Color.green()
    )
    embed.add_field(name="✅ Threads válidas",    value=str(result.get('valid', 0)),   inline=True)
    embed.add_field(name="🗑️ Entradas removidas", value=str(result.get('removed', 0)), inline=True)
    await msg.edit(content=None, embed=embed)


# ==================== PERFIL E STATUS ====================


@bot.command(name='statuscanal')
async def status_canal(ctx, channel_name: str = None):
    if not channel_service:
        await ctx.reply("❌ Sistema ainda não foi inicializado.")
        return
    try:
        channel_name = channel_name or ctx.channel.name
        stats = await channel_service.get_channel_stats(channel_name)
        embed = discord.Embed(title=f"📊 Estatísticas - #{channel_name}", color=discord.Color.blue())
        embed.add_field(name="Total",       value=stats['total'],     inline=True)
        embed.add_field(name="Ativas",      value=stats['active'],    inline=True)
        embed.add_field(name="Finalizadas", value=stats['completed'], inline=True)
        await ctx.reply(embed=embed)
    except Exception as e:
        logger.error(f"Erro no statuscanal: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


@bot.command(name='perfil')
async def ver_perfil(ctx, member: discord.Member = None):
    if not onboarding_service:
        await ctx.reply("❌ Sistema ainda não inicializado.")
        return
    try:
        target = member or ctx.author
        user   = await onboarding_service.get_user_stats(str(target.id))
        if not user:
            await ctx.reply("❌ Usuário não encontrado no sistema")
            return
        embed = discord.Embed(title=f"📊 Perfil de {target.name}", color=discord.Color.blue())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(
            name="Informações Gerais",
            value=(
                f"**Entrou em:** {user.joined_at.strftime('%d/%m/%Y %H:%M')}\n"
                f"**Regras aceitas:** {'✅ Sim' if user.has_accepted_rules else '❌ Não'}\n"
                f"**Onboarding:** `{user.onboarding_result}`\n"
                f"**Spam bloqueado:** {'🛑 Sim' if getattr(user, 'spam_blocked', False) else '✅ Não'}"
            ),
            inline=False
        )
        embed.add_field(
            name="Estatísticas",
            value=(
                f"**Total de partidas:** {user.total_matches}\n"
                f"**Vitórias:** {user.wins}\n"
                f"**Derrotas:** {user.losses}"
            ),
            inline=False
        )
        if user.total_matches > 0:
            winrate = (user.wins / user.total_matches) * 100
            embed.add_field(name="Taxa de Vitória", value=f"{winrate:.1f}%", inline=False)
        await ctx.reply(embed=embed)
    except Exception as e:
        logger.error(f"Erro no perfil: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


# ==================== HELP ====================


@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(
        title="📚 Comandos para Membros",
        description="Comandos disponíveis para jogadores.",
        color=discord.Color.blue()
    )
    embed.add_field(name="!perfil [@usuario]",  value="Ver perfil e estatísticas",            inline=False)
    embed.add_field(name="!partidas",           value="Ver partidas ativas",                  inline=False)
    embed.add_field(name="!statuscanal [nome]", value="Ver estatísticas de um canal",         inline=False)
    embed.add_field(name="!fila",               value="Ver a fila de mediadores disponíveis", inline=False)
    embed.add_field(
        name="ℹ️ Como jogar",
        value=(
            "1. Entre em um canal de partidas\n"
            "2. Clique no botão da fila\n"
            "3. Confirme sua presença no tópico criado\n"
            "4. Pague ao mediador e jogue!\n"
            "5. Confirme o recebimento do prêmio ao vencer"
        ),
        inline=False
    )
    embed.set_footer(text="Suporte: !help_sup | Mediadores: !help_med | Admins: !help_adm")
    await ctx.reply(embed=embed)


@bot.command(name='help_sup')
@commands.has_any_role(SUPPORT_ROLE_NAME, ADM_ROLE_NAME)
async def help_suporte(ctx):
    embed = discord.Embed(
        title="🎫 Comandos para Suporte",
        description="Comandos exclusivos da equipe de suporte.",
        color=discord.Color.purple()
    )
    embed.add_field(name="━━ 📋 CHAMADOS ━━", value="\u200b", inline=False)
    embed.add_field(
        name="!concluir_chamado <id>",
        value=(
            "Marca um chamado como resolvido.\n"
            "▸ Apenas em `#chamados-suporte`\n"
            "▸ Só o atendente responsável ou ADM pode concluir\n"
            "▸ Mensagem apagada automaticamente"
        ),
        inline=False
    )
    embed.add_field(name="━━ ⚠️ FLUXO ━━", value="\u200b", inline=False)
    embed.add_field(
        name="Como atender um chamado",
        value=(
            "1. Veja o card em `#chamados-suporte`\n"
            "2. Clique em **✋ Assumir** — você recebe os detalhes via DM\n"
            "3. Entre em contato com o membro via **DM pessoal**\n"
            "4. Se DM bloqueada → mencione o membro em `#chat-suporte`\n"
            "5. Resolva o problema\n"
            "6. Use `!concluir_chamado <id>` em `#chamados-suporte`"
        ),
        inline=False
    )
    embed.set_footer(text="Membros: !help | Mediadores: !help_med | Admins: !help_adm")
    await ctx.reply(embed=embed)


@bot.command(name='help_med')
@commands.has_any_role(MEDIATOR_ROLE_NAME, ADM_ROLE_NAME)
async def help_mediador(ctx):
    embed = discord.Embed(
        title="🧑‍⚖️ Comandos para Mediadores",
        description="Use dentro da thread de partida. Sua mensagem é apagada automaticamente.",
        color=discord.Color.blue()
    )
    embed.add_field(name="━━ 🎮 PARTIDA ━━",           value="\u200b", inline=False)
    embed.add_field(name="!menu_partida",               value="Recebe o painel de controle via DM",                     inline=False)
    embed.add_field(name="!confirmar_pagamento",        value="Confirma recebimento dos pagamentos dos jogadores",       inline=False)
    embed.add_field(name="!iniciar_partida",            value="Inicia a partida após confirmar pagamento",               inline=False)
    embed.add_field(name="!winner_team blue|red",       value="Declara o time vencedor",                                 inline=False)
    embed.add_field(name="!prize",                      value="Confirma que o prêmio foi entregue ao vencedor",          inline=False)
    embed.add_field(name="!cancelar_match [motivo]",    value="Cancela a partida da thread atual",                       inline=False)
    embed.add_field(name="━━ 📋 FILA ━━",               value="\u200b", inline=False)
    embed.add_field(name="!addmediador",                value="Entra na fila de mediadores disponíveis",                 inline=False)
    embed.add_field(name="!removemediador",             value="Sai da fila de mediadores",                               inline=False)
    embed.add_field(name="━━ ⚠️ FLUXO OBRIGATÓRIO ━━",  value="\u200b", inline=False)
    embed.add_field(
        name="Ordem dos comandos",
        value=(
            "1. `!confirmar_pagamento`\n"
            "2. `!iniciar_partida`\n"
            "3. `!winner_team blue` ou `red`\n"
            "4. `!prize` → jogador confirma → **Finalizado**"
        ),
        inline=False
    )
    embed.set_footer(text="Membros: !help | Suporte: !help_sup | Admins: !help_adm")
    await ctx.reply(embed=embed)


@bot.command(name='help_adm')
@commands.has_permissions(administrator=True)
async def help_admin(ctx):
    embed = discord.Embed(
        title="👑 Comandos para Administradores",
        description="ADM tem acesso a todos os comandos de mediador e suporte.",
        color=discord.Color.red()
    )
    embed.add_field(name="━━ 🛠️ SETUP ━━",                    value="\u200b", inline=False)
    embed.add_field(name="!setupcanais",                       value="Configura toda estrutura do servidor (canais + cargos)",  inline=False)
    embed.add_field(name="!atualizarcards [#canal]",           value="Recria os cards de um canal específico",                  inline=False)
    embed.add_field(name="!atualizartodos",                    value="Recria os cards de todos os canais de partida",           inline=False)
    embed.add_field(name="!atualizarmediadores",               value="Atualiza o painel no #painel-mediadores",                 inline=False)
    embed.add_field(name="!sincmediadores",                    value="Sincroniza a fila pelo cargo Controller",                 inline=False)
    embed.add_field(name="!dashboard",                         value="Força atualização do dashboard Analytics",                inline=False)
    embed.add_field(name="━━ 🏥 HEALTH CHECK ━━",              value="\u200b", inline=False)  # ← NOVO
    embed.add_field(name="!healthcheck",                       value="Exibe painel de saúde completo do sistema",              inline=False)  # ← NOVO
    embed.add_field(name="━━ 🧵 THREADS ━━",                   value="\u200b", inline=False)
    embed.add_field(name="!threadstatus",                      value="Exibe pool, partidas ativas e limite do servidor",        inline=False)
    embed.add_field(name="!preaquecerpool [#canal] [qtd]",     value="Pré-cria threads arquivadas para evitar limite Discord",  inline=False)
    embed.add_field(name="!validarpool",                       value="Remove entradas inválidas do pool no banco",              inline=False)
    embed.add_field(name="━━ 🎫 SUPORTE ━━",                   value="\u200b", inline=False)
    embed.add_field(name="!concluir_chamado <id>",             value="Conclui qualquer chamado (ADM ignora restrição)",         inline=False)
    embed.add_field(name="━━ 🎮 PARTIDAS ━━",                  value="\u200b", inline=False)
    embed.add_field(name="!cancelarpartida <id> [motivo]",     value="Cancela qualquer partida por ID",                        inline=False)
    embed.add_field(name="!forcarconcluir <id>",               value="Força finalização de qualquer partida",                  inline=False)
    embed.add_field(name="!inspecionar <id>",                  value="Exibe todos os campos da partida no banco",              inline=False)
    embed.add_field(name="!simularfila [canal] [v] [gel]",     value="Simula fila completa para testes",                       inline=False)
    embed.add_field(name="━━ 📊 INFO ━━",                      value="\u200b", inline=False)
    embed.add_field(name="!stats",                             value="Estatísticas de onboarding do servidor",                 inline=False)
    embed.add_field(name="!aviso <texto>",                     value="Posta aviso no #avisos com @everyone",                   inline=False)
    embed.add_field(name="!testarregras",                      value="Testa o fluxo de onboarding via DM (sem kick)",          inline=False)
    embed.add_field(name="!bloquear @user [motivo]",           value="Bloqueia manualmente um membro",                        inline=False)
    embed.add_field(name="!desbloquear @user",                 value="Desbloqueia um membro bloqueado",                       inline=False)
    embed.set_footer(text="Membros: !help | Suporte: !help_sup | Mediadores: !help_med")
    await ctx.reply(embed=embed)


# ==================== INICIALIZAÇÃO ====================


async def main():
    global onboarding_service, channel_service
    try:
        log_success("🚀 Iniciando sistema...")
        await db.connect()
        await mediator_queue.initialize()
        onboarding_service = OnboardingService(bot)
        channel_service    = ChannelService(bot)
        await start_discord_bot(bot)
    except KeyboardInterrupt:
        logger.info("Interrupção recebida...")
    except Exception as e:
        logger.error(f"Erro fatal: {e}", exc_info=True)
    finally:
        logger.info("Encerrando sistema...")
        await db.close()
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
