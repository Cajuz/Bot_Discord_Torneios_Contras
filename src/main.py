import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime
from discord.errors import NotFound 


from views.mediator_panel_view import create_mediator_panel_embed, MediatorPanelView
from views.match_thread_view import (
    PrizeConfirmView,
    MediatorMenuView,
    cmd_menu_partida,
    cmd_winner_team,
    cmd_prize,
    cmd_confirmar_pagamento,
    cmd_iniciar_partida,
    cmd_cancelar_match
)
from config.database import db
from config.discord_bot import create_discord_bot, start_discord_bot
from services.mediator_queue import mediator_queue
from services.match_service import match_service
from services.match_queue_service import match_queue_service
from config.channels_config import ChannelsConfig
from utils.logger import logger, log_success
from services.channel_service import ChannelService, AVISOS_CHANNEL_NAME
from services.onboarding_service import OnboardingService
from services.mediador_dashboard_service import mediator_dashboard_service



load_dotenv()


bot = create_discord_bot()


onboarding_service = None
channel_service    = None



# ==================== EVENTOS ====================


@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user}')
    await mediator_queue.initialize()
    for guild in bot.guilds:
        await mediator_queue.sync_mediators_by_role(guild, "Controller")
        print(f"✅ Mediadores sincronizados em {guild.name}")
    bot.add_view(PrizeConfirmView(match_id="placeholder", winner_players=[], winner_team="blue"))
    if not mediator_dashboard_service.daily_update.is_running():
        mediator_dashboard_service.bot = bot
        mediator_dashboard_service.daily_update.start()
    print('🚀 Bot pronto!')


@bot.event
async def on_member_join(member: discord.Member):
    try:
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

@bot.command(name="dashboard")
async def dashboard_manual(ctx):
    try:
        # 1. Reagir primeiro para mostrar que o bot recebeu o comando
        await ctx.message.add_reaction("✅")
        
        # 2. Chamar o serviço de atualização
        await mediator_dashboard_service.update_dashboard(ctx.bot)
        
    except Exception as e:
        logger.error(f"Erro no comando dashboard manual: {e}")
        await ctx.send(f"❌ Erro ao atualizar dashboards: {e}")
    


@bot.command(name='winner_team')
async def winner_team(ctx, team: str = None):
    if not team:
        await ctx.reply("❌ Use: `!winner_team blue` ou `!winner_team red`")
        return
    await cmd_winner_team(ctx, team)


@bot.command(name='prize')
async def prize(ctx):
    await cmd_prize(ctx)


@bot.command(name='confirmar_pagamento')
async def confirmar_pagamento(ctx):
    await cmd_confirmar_pagamento(ctx)


@bot.command(name='iniciar_partida')
async def iniciar_partida(ctx):
    await cmd_iniciar_partida(ctx)


@bot.command(name='cancelar_match')
async def cancelar_match_cmd(ctx):
    await cmd_cancelar_match(ctx)



# ==================== COMANDOS ADMINISTRATIVOS ====================


@bot.command(name='setupcanais')
@commands.has_permissions(administrator=True)
async def setup_canais(ctx):
    if not channel_service:
        await ctx.send("❌ Sistema ainda não foi inicializado completamente.")
        return
    try:
        msg = await ctx.send("⏳ Configurando servidor completo... (pode demorar alguns segundos)")
        await channel_service.setup_all_channels(ctx.guild)

        embed = discord.Embed(
            title="✅ Servidor Configurado!",
            description="Toda a estrutura foi criada/atualizada com sucesso.",
            color=discord.Color.green()
        )
        embed.add_field(
            name="ℹ️ INFORMAÇÕES",
            value="• 📜regras\n• 📢avisos\n• painel-mediadores",
            inline=True
        )
        embed.add_field(
            name="📱 MOBILE",
            value="• #1x1-mob\n• #2x2-mob\n• #3x3-mob\n• #4x4-mob",
            inline=True
        )
        embed.add_field(
            name="🖥️ EMULADOR",
            value="• #1x1-emu\n• #2x2-emu\n• #3x3-emu\n• #4x4-emu",
            inline=True
        )
        embed.add_field(
            name="🔀 MISTO",
            value="• #4x4-misto\n• #3x3-misto\n• #2x2-misto",
            inline=True
        )
        embed.add_field(
            name="🎭 Cargos",
            value="• Membro (acesso aos canais de jogo)\n• Controller (mediadores)",
            inline=True
        )
        embed.add_field(
            name="💰 Valores",
            value="R$ 2 • R$ 5 • R$ 10 • R$ 20 • R$ 50 • R$ 100 • R$ 200",
            inline=False
        )
        embed.set_footer(text="@everyone bloqueado nos canais de jogo — só Membros acessam")
        await msg.edit(content=None, embed=embed)

    except Exception as e:
        logger.error(f"Erro no setupcanais: {e}")
        await ctx.send(f"❌ Erro: {str(e)}")


@bot.command(name='setupmembro')
@commands.has_permissions(administrator=True)
async def setup_membro(ctx):
    if not onboarding_service:
        await ctx.send("❌ Sistema ainda não inicializado.")
        return
    try:
        await ctx.send("⏳ Configurando cargo e canal de regras...")
        result = await onboarding_service.setup_member_role_and_rules_channel(ctx.guild)

        embed = discord.Embed(
            title="✅ Onboarding Configurado",
            color=discord.Color.green()
        )
        embed.add_field(name="🎭 Cargo",        value=result['role'].mention,    inline=True)
        embed.add_field(name="📜 Canal regras", value=result['channel'].mention, inline=True)
        embed.add_field(
            name="⚠️ Lembre-se",
            value=(
                "Os canais de jogo precisam ter:\n"
                "• `@everyone` → ❌ Ver Canal\n"
                "• `Membro` → ✅ Ver Canal\n\n"
                "Use `!setupcanais` para configurar tudo automaticamente."
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Erro no setupmembro: {e}")
        await ctx.send(f"❌ Erro: {e}")


@bot.command(name='setupmediadores')
@commands.has_permissions(administrator=True)
async def setup_mediadores(ctx):
    try:
        guild         = ctx.guild
        mediator_role = discord.utils.get(guild.roles, name="Controller")
        if not mediator_role:
            mediator_role = await guild.create_role(
                name="Controller",
                color=discord.Color.blue(),
                mentionable=True
            )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            mediator_role:       discord.PermissionOverwrite(read_messages=True, send_messages=False),
            guild.me:            discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel = discord.utils.get(guild.text_channels, name="painel-mediadores")
        if not channel:
            channel = await guild.create_text_channel(
                name="painel-mediadores",
                overwrites=overwrites,
                topic="Painel de controle para mediadores"
            )

        async for msg in channel.history(limit=10):
            if msg.author == bot.user and msg.embeds:
                await msg.delete()
                break

        info  = await mediator_queue.get_queue_info()
        embed = create_mediator_panel_embed(info)
        view  = MediatorPanelView()
        await channel.send(embed=embed, view=view)

        success_embed = discord.Embed(
            title="✅ Painel de Mediadores Atualizado",
            description=f"Canal {channel.mention} pronto!",
            color=discord.Color.green()
        )
        success_embed.add_field(
            name="Próximos passos",
            value="Dê o cargo @Controller para os mediadores.",
            inline=False
        )
        await ctx.send(embed=success_embed)

    except discord.Forbidden:
        await ctx.send("❌ Sem permissão para criar canais ou cargos!")
    except Exception as e:
        logger.error(f"Erro no setupmediadores: {e}")
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
            await ctx.reply(
                f"❌ Canal `{AVISOS_CHANNEL_NAME}` não encontrado. "
                f"Use `!setupcanais` para criá-lo."
            )
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
        guild   = ctx.guild
        channel = discord.utils.get(guild.channels, name="painel-mediadores")
        if not channel:
            await ctx.send("❌ Canal #painel-mediadores não encontrado. Use `!setupmediadores`.")
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
            await ctx.send(f"✅ Painel atualizado em {channel.mention}!")
        else:
            await channel.send(embed=embed, view=view)
            await ctx.send(f"✅ Novo painel criado em {channel.mention}!")

    except discord.Forbidden:
        await ctx.send("❌ Sem permissão para acessar o canal #painel-mediadores.")
    except Exception as e:
        logger.error(f"Erro ao atualizar painel: {e}")
        await ctx.send(f"❌ Erro: {e}")


@bot.command(name='simularfila')
@commands.has_permissions(administrator=True)
async def simular_fila(ctx, channel_name: str = None, bet_value: float = 10.0, gel_type: str = "normal"):
    """Uso: !simularfila 1x1-mob 10 normal"""
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
        if queue_key in match_queue_service.active_queues:
            del match_queue_service.active_queues[queue_key]

        queue = None
        for i in range(2):
            player_id = ctx.author.id if i == 0 else ctx.author.id + i
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
        f"**status:** {match.get('status')}",
        f"**time_blue:** {match.get('time_blue')}",
        f"**time_red:** {match.get('time_red')}",
        f"**mediator_id:** {match.get('mediator_id')}",
        f"**thread_id:** {match.get('thread_id')}",
        f"**vencedor:** {match.get('vencedor')}",
        f"**pagamento_confirmado:** {match.get('pagamento_confirmado')}",
        f"**premio_entregue_mediador:** {match.get('premio_entregue_mediador')}",
        f"**premio_confirmado_jogador:** {match.get('premio_confirmado_jogador')}",
    ]
    embed = discord.Embed(
        title=f"🔍 Match `{match_id}`",
        description="\n".join(campos),
        color=discord.Color.blurple()
    )
    await ctx.reply(embed=embed)


@bot.command(name='sincmediadores')
@commands.has_permissions(administrator=True)
async def sync_mediators(ctx):
    await ctx.send("🔄 Sincronizando mediadores...")
    await mediator_queue.sync_mediators_by_role(ctx.guild, "Controller")
    info  = await mediator_queue.get_queue_info()
    embed = discord.Embed(
        title="✅ Sincronização Completa",
        description="Mediadores sincronizados com o cargo **Controller**",
        color=discord.Color.green()
    )
    embed.add_field(
        name="📊 Estatísticas",
        value=f"**Total Ativos:** {info['total_active']}\n**Na Fila:** {info['in_queue']}",
        inline=False
    )
    await ctx.send(embed=embed)


@bot.command(name='statuscanal')
async def status_canal(ctx, channel_name: str = None):
    if not channel_service:
        await ctx.reply("❌ Sistema ainda não foi inicializado.")
        return
    try:
        channel_name = channel_name or ctx.channel.name
        stats = await channel_service.get_channel_stats(channel_name)
        embed = discord.Embed(
            title=f"📊 Estatísticas - #{channel_name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Total",       value=stats['total'],     inline=True)
        embed.add_field(name="Ativas",      value=stats['active'],    inline=True)
        embed.add_field(name="Finalizadas", value=stats['completed'], inline=True)
        await ctx.reply(embed=embed)
    except Exception as e:
        logger.error(f"Erro no statuscanal: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


@bot.command(name='setupverificacao')
@commands.has_permissions(administrator=True)
async def setup_verificacao(ctx, channel: discord.TextChannel, role: discord.Role):
    if not onboarding_service:
        await ctx.reply("❌ Sistema ainda não inicializado.")
        return
    try:
        onboarding_service.set_verification_channel(channel.id)
        onboarding_service.set_verified_role(role.id)
        embed = discord.Embed(
            title="✅ Verificação Configurada",
            description=f"**Canal:** {channel.mention}\n**Cargo:** {role.mention}",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)
    except Exception as e:
        logger.error(f"Erro no setupverificacao: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


@bot.command(name='testarregras')
@commands.has_permissions(administrator=True)
async def testar_regras(ctx):
    if not onboarding_service:
        await ctx.reply("❌ Sistema ainda não inicializado.")
        return
    try:
        await onboarding_service.handle_new_member(ctx.author)
        await ctx.reply("✅ Sistema de regras testado! Verifique sua DM.")
    except Exception as e:
        logger.error(f"Erro no testarregras: {e}")
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
                f"**Onboarding:** `{user.onboarding_result}`"  # ✅ novo
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



# ==================== COMANDOS DE CARDS ====================


@bot.command(name='atualizarcards')
@commands.has_permissions(administrator=True)
async def atualizar_cards(ctx, canal: discord.TextChannel = None):
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
        success = await channel_service.setup_queue_cards(ctx.guild, channel)
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

        final_embed = discord.Embed(
            title="✅ Atualização Concluída",
            description=f"Cards atualizados em **{success_count}/{len(channels_to_update)}** canais",
            color=discord.Color.green()
        )
        await status_msg.edit(content=None, embed=final_embed)
    except Exception as e:
        logger.error(f"Erro ao atualizar todos os cards: {e}")
        await ctx.send(f"❌ Erro: {e}")



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
            'aguardando_resultado': '🏆',
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
async def cancelar_partida(ctx, match_id: str):
    try:
        match = await match_service.cancel_match(match_id)
        if not match:
            await ctx.reply("❌ Partida não encontrada.")
            return
        embed = discord.Embed(
            title="🚫 Partida Cancelada",
            description=f"A partida `{match_id}` foi cancelada.",
            color=discord.Color.red()
        )
        thread_id = match.get('thread_id')
        if thread_id:
            thread = bot.get_channel(thread_id)
            if thread:
                await thread.send("❌ Esta partida foi cancelada por um administrador.")
        await ctx.reply(embed=embed)
    except Exception as e:
        logger.error(f"Erro no cancelarpartida: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


@bot.command(name='forcarconcluir')
@commands.has_permissions(administrator=True)
async def forcar_concluir(ctx, match_id: str):
    try:
        match = await match_service.complete_match(match_id)
        if not match:
            await ctx.reply("❌ Partida não encontrada.")
            return
        embed = discord.Embed(
            title="✅ Partida Forçada como Concluída",
            description=f"A partida `{match_id}` foi concluída.",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)
    except Exception as e:
        logger.error(f"Erro no forcarconcluir: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")



# ==================== COMANDOS DE MEDIADOR ====================


@bot.command(name='addmediador')
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
            status_emoji = "✅" if m['can_mediate'] else "⏳"
            embed.add_field(
                name=f"{status_emoji} Posição {m['position']} — {m['username']}",
                value=f"Total: {m['total_matches']} | Últimos 8min: {m['matches_in_last_8_min']}/5",
                inline=False
            )
        if stats['total_active'] > 10:
            embed.set_footer(text=f"Mostrando 10 de {stats['total_active']}")
        await ctx.reply(embed=embed)
    except Exception as e:
        logger.error(f"Erro no fila: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


# ==================== STATS DE ONBOARDING ====================  ✅ novo


@bot.command(name='stats')
@commands.has_permissions(administrator=True)
async def stats_onboarding(ctx):
    """Estatísticas de onboarding — quantas pessoas tentaram, aceitaram, recusaram etc."""
    try:
        collection = db.get_collection('users')

        total     = await collection.count_documents({})
        aceitos   = await collection.count_documents({'onboarding_result': 'aceito'})
        recusados = await collection.count_documents({'onboarding_result': 'recusado'})
        timeout   = await collection.count_documents({'onboarding_result': 'timeout'})
        dm_bloq   = await collection.count_documents({'onboarding_result': 'dm_bloqueada'})
        pendentes = await collection.count_documents({'onboarding_result': 'pendente'})

        taxa = (aceitos / total * 100) if total > 0 else 0.0

        embed = discord.Embed(
            title="📊 Estatísticas de Onboarding",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="📥 Total de Tentativas",
            value=f"**{total}** pessoas entraram no servidor",
            inline=False
        )
        embed.add_field(name="✅ Aceitaram",    value=f"**{aceitos}**",   inline=True)
        embed.add_field(name="❌ Recusaram",    value=f"**{recusados}**", inline=True)
        embed.add_field(name="⏰ Timeout",      value=f"**{timeout}**",   inline=True)
        embed.add_field(name="🚫 DM Bloqueada", value=f"**{dm_bloq}**",   inline=True)
        embed.add_field(name="⏳ Pendentes",    value=f"**{pendentes}**", inline=True)
        embed.add_field(
            name="📈 Taxa de Aceitação",
            value=f"**{taxa:.1f}%**",
            inline=False
        )
        embed.set_footer(text="collection: users | MongoDB")
        embed.timestamp = datetime.utcnow()

        await ctx.reply(embed=embed)

    except Exception as e:
        logger.error(f"Erro no stats: {e}")
        await ctx.reply(f"❌ Erro: {e}")


# ==================== HELP ====================


@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(title="📚 Comandos Disponíveis", color=discord.Color.blue())
    commands_list = [
        ("!fila",                          "Ver fila de mediadores"),
        ("!perfil [@usuario]",             "Ver perfil de um jogador"),
        ("!statuscanal [nome]",            "Ver estatísticas de um canal"),
        ("!partidas",                      "Ver partidas ativas"),
        ("!stats",                         "Estatísticas de onboarding (Admin)"),  # ✅ novo
        ("!menu_partida",                  "Painel de controle (mediador, na thread)"),
        ("!confirmar_pagamento",           "Confirma pagamento (mediador, na thread)"),
        ("!iniciar_partida",               "Inicia a partida (mediador, na thread)"),
        ("!winner_team blue|red",          "Declara vencedor (mediador, na thread)"),
        ("!prize",                         "Confirma entrega do prêmio (mediador, na thread)"),
        ("!cancelar_match",                "Cancela a partida (mediador/admin, na thread)"),
        ("!addmediador",                   "Entrar na fila de mediadores"),
        ("!removemediador",                "Sair da fila de mediadores"),
        ("!setupcanais",                   "Configura servidor completo (Admin)"),
        ("!setupmembro",                   "Cria cargo Membro e canal de regras (Admin)"),
        ("!setupmediadores",               "Recria painel de mediadores (Admin)"),
        ("!aviso <texto>",                 "Posta aviso no #📢avisos (Admin)"),
        ("!atualizarcards [#canal]",       "Atualiza cards de um canal (Admin)"),
        ("!atualizartodos",                "Atualiza todos os cards (Admin)"),
        ("!atualizarmediadores",           "Atualiza painel de mediadores (Admin)"),
        ("!sincmediadores",                "Sincroniza mediadores por cargo (Admin)"),
        ("!cancelarpartida <id>",          "Cancela partida por ID (Admin)"),
        ("!forcarconcluir <id>",           "Força conclusão de partida (Admin)"),
        ("!inspecionar <id>",              "Inspeciona partida no banco (Admin)"),
        ("!simularfila [canal] [v] [gel]", "Simula fila para testes (Admin)"),
        ("!setupverificacao",              "Configura verificação manual (Admin)"),
        ("!testarregras",                  "Testa envio de regras na DM (Admin)"),
    ]
    for cmd, desc in commands_list:
        embed.add_field(name=cmd, value=desc, inline=False)
    embed.add_field(
        name="ℹ️ Fluxo da Partida",
        value=(
            "1. Entre na fila pelo botão no canal\n"
            "2. Tópico criado — 5 min para confirmar\n"
            "3. Todos confirmam → mediador entra no tópico\n"
            "4. Times, mediador, pagamento e prêmio exibidos\n"
            "5. Mediador usa `!menu_partida` para controlar\n"
            "6. Vencedor confirma recebimento do prêmio"
        ),
        inline=False
    )
    await ctx.reply(embed=embed)



# ==================== INICIALIZAÇÃO ====================


async def main():
    global onboarding_service, channel_service
    try:
        log_success("🚀 Iniciando sistema...")
        logger.info("Conectando ao MongoDB...")
        await db.connect()
        logger.info("Inicializando fila de mediadores...")
        await mediator_queue.initialize()
        logger.info("Inicializando onboarding...")
        onboarding_service = OnboardingService(bot)
        logger.info("Inicializando serviço de canais...")
        channel_service = ChannelService(bot)
        logger.info("Iniciando Discord Bot...")
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
