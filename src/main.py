import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime

from views.mediator_panel_view import create_mediator_panel_embed, MediatorPanelView
from views.match_thread_view import MediatorMatchControlView, WinnerSelectView, PrizeConfirmView
from config.database import db
from config.discord_bot import create_discord_bot, start_discord_bot
from services.mediator_queue import mediator_queue
from services.match_service import match_service
from services.match_queue_service import match_queue_service
from config.channels_config import ChannelsConfig
from utils.logger import logger, log_success
from services.channel_service import ChannelService
from services.onboarding_service import OnboardingService
from config.rules import ServerRules

load_dotenv()

bot = create_discord_bot()

onboarding_service = None
channel_service = None


# ==================== EVENTOS DO BOT ====================

@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user}')

    await mediator_queue.initialize()

    for guild in bot.guilds:
        await mediator_queue.sync_mediators_by_role(guild, "Controller")
        print(f"✅ Mediadores sincronizados em {guild.name}")

    from views.match_thread_view import MediatorMatchControlView, WinnerSelectView, PrizeConfirmView
    from views.match_queue_view import MatchQueueView

    bot.add_view(MediatorMatchControlView(match_id="placeholder", mediator_id=0))
    bot.add_view(PrizeConfirmView(match_id="placeholder", winner_players=[], winner_team="blue"))


    print('🚀 Bot pronto!')

@bot.event
async def on_member_join(member: discord.Member):
    try:
        if onboarding_service:
            await onboarding_service.handle_new_member(member)
        else:
            logger.error("Onboarding service não inicializado")
    except Exception as e:
        logger.error(f"Erro no evento on_member_join: {e}")


@bot.event
async def on_member_remove(member: discord.Member):
    try:
        collection = db.get_collection('users')
        await collection.update_one(
            {'discord_id': str(member.id)},
            {'$set': {'is_active': False, 'updated_at': datetime.utcnow()}}  # ✏️ utcnow()
        )
        logger.info(f"Membro {member.name} saiu do servidor")
    except Exception as e:
        logger.error(f"Erro no evento on_member_remove: {e}")


# ==================== COMANDOS ADMINISTRATIVOS ====================
@bot.command(name='atualizarmediadores')
@commands.has_permissions(administrator=True)
async def atualizar_painel_mediadores(ctx):
    """Atualiza o embed do canal painel-mediadores com dados atuais"""
    try:
        guild = ctx.guild

        # Buscar canal
        channel = discord.utils.get(guild.channels, name="painel-mediadores")
        if not channel:
            await ctx.send(
                "❌ Canal #painel-mediadores não encontrado. "
                "Use `!setupmediadores` para criá-lo."
            )
            return

        await ctx.send("🔄 Atualizando painel...")

        # Buscar última mensagem do bot no canal
        bot_message = None
        async for msg in channel.history(limit=20):
            if msg.author == bot.user and msg.embeds:
                bot_message = msg
                break

        # Buscar dados atuais da fila
        info = await mediator_queue.get_queue_info()
        embed = create_mediator_panel_embed(info)
        view  = MediatorPanelView()

        if bot_message:
            # Editar mensagem existente
            await bot_message.edit(embed=embed, view=view)
            await ctx.send(f"✅ Painel atualizado em {channel.mention}!")
        else:
            # Nenhuma mensagem encontrada — criar nova
            await channel.send(embed=embed, view=view)
            await ctx.send(f"✅ Novo painel criado em {channel.mention}!")

    except discord.Forbidden:
        await ctx.send("❌ Sem permissão para acessar o canal #painel-mediadores.")
    except Exception as e:
        logger.error(f"Erro ao atualizar painel de mediadores: {e}")
        await ctx.send(f"❌ Erro ao atualizar painel: {e}")

@bot.command(name='simularfila')
@commands.has_permissions(administrator=True)
async def simular_fila(ctx, channel_name: str = None, bet_value: float = 10.0):
    """
    Simula uma fila cheia com o admin duplicado para testar o fluxo de thread.
    Uso: !simularfila 1x1-mob 10
    """
    try:
        channel_name = channel_name or ctx.channel.name
        valid_channels = [ch["name"] for ch in ChannelsConfig.get_all_channels()]

        if channel_name not in valid_channels:
            await ctx.send(f"❌ Canal inválido. Canais válidos: {', '.join(valid_channels)}")
            return

        channel_info = ChannelsConfig.get_channel_info(channel_name)
        max_players  = channel_info.get('max_players', 2)
        gel_type     = channel_info.get('gel_type', 'normal')

        await ctx.send(
            f"🧪 Simulando fila: `{channel_name}` | R${bet_value} | {max_players} jogadores..."
        )

        # Limpar fila existente para evitar conflito
        queue_key = match_queue_service.get_queue_key(channel_name, bet_value, gel_type)
        if queue_key in match_queue_service.active_queues:
            del match_queue_service.active_queues[queue_key]

        # Adicionar o admin repetido para preencher a fila
        # (em produção cada ID seria único)
        fake_ids = [ctx.author.id] * max_players

        for i, pid in enumerate(fake_ids):
            # Usa IDs fictícios para os "outros" jogadores, exceto o primeiro (você)
            player_id = pid if i == 0 else (ctx.author.id + i)  # IDs falsos
            success, queue, message = await match_queue_service.add_player_to_queue(
                channel_name=channel_name,
                bet_value=bet_value,
                gel_type=gel_type,
                max_players=max_players,
                player_id=player_id
            )

        # Forçar status como se todos confirmaram
        queue.confirmations = list(queue.players)
        await match_queue_service._save_queue(queue)

        # Criar o match diretamente
        await match_queue_service._create_match_from_queue(
            queue=queue,
            bot=bot,
            channel=ctx.channel
        )

        await ctx.send("✅ Simulação iniciada! Verifique a thread criada neste canal.")

    except Exception as e:
        logger.error(f"Erro na simulação: {e}", exc_info=True)
        await ctx.send(f"❌ Erro na simulação: {e}")

@bot.command(name='inspecionar')
@commands.has_permissions(administrator=True)
async def inspecionar_match(ctx, match_id: str):
    """Ver todos os campos de um match no banco"""
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
    info = await mediator_queue.get_queue_info()

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


@bot.command(name='setupcanais')
@commands.has_permissions(administrator=True)
async def setup_canais(ctx):
    if not channel_service:
        await ctx.send("❌ Sistema ainda não foi inicializado completamente.")
        return

    try:
        await ctx.send("⏳ Configurando canais...")
        await channel_service.setup_all_channels(ctx.guild)

        embed = discord.Embed(
            title="✅ Canais Configurados!",
            description="Todos os canais de partidas foram criados e configurados com sucesso!",
            color=discord.Color.green()
        )
        embed.add_field(name="📱 MOBILE",   value="• #1x1-mob\n• #2x2-mob\n• #3x3-mob\n• #4x4-mob", inline=True)
        embed.add_field(name="🖥️ EMULADOR", value="• #1x1-emu\n• #2x2-emu\n• #3x3-emu\n• #4x4-emu", inline=True)
        embed.add_field(name="🔀 MISTO",    value="• #4x4-misto\n• #3x3-misto\n• #2x2-misto",        inline=True)
        embed.add_field(
            name="💰 Valores Disponíveis",
            value="R$ 2 • R$ 5 • R$ 10 • R$ 20 • R$ 50 • R$ 100 • R$ 200",
            inline=False
        )
        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Erro no comando setupcanais: {e}")
        await ctx.send(f"❌ Erro ao configurar canais: {str(e)}")


@bot.command(name='statuscanal')
async def status_canal(ctx, channel_name: str = None):
    if not channel_service:
        await ctx.reply("❌ Sistema ainda não foi inicializado completamente.")
        return

    try:
        if not channel_name:
            channel_name = ctx.channel.name

        stats = await channel_service.get_channel_stats(channel_name)

        embed = discord.Embed(
            title=f"📊 Estatísticas - #{channel_name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Total de Partidas", value=stats['total'],     inline=True)
        embed.add_field(name="Ativas",            value=stats['active'],    inline=True)
        embed.add_field(name="Finalizadas",       value=stats['completed'], inline=True)
        await ctx.reply(embed=embed)

    except Exception as e:
        logger.error(f"Erro no comando statuscanal: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


@bot.command(name='setupverificacao')
@commands.has_permissions(administrator=True)
async def setup_verificacao(ctx, channel: discord.TextChannel, role: discord.Role):
    if not onboarding_service:
        await ctx.reply("❌ Sistema ainda não foi inicializado completamente.")
        return

    try:
        onboarding_service.set_verification_channel(channel.id)
        onboarding_service.set_verified_role(role.id)

        embed = discord.Embed(
            title="✅ Verificação Configurada",
            description=(
                f"**Canal de verificação:** {channel.mention}\n"
                f"**Cargo de verificado:** {role.mention}"
            ),
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)

    except Exception as e:
        logger.error(f"Erro no comando setupverificacao: {e}")
        await ctx.reply(f"❌ Erro ao configurar verificação: {str(e)}")


@bot.command(name='testarregras')
@commands.has_permissions(administrator=True)
async def testar_regras(ctx):
    if not onboarding_service:
        await ctx.reply("❌ Sistema ainda não foi inicializado completamente.")
        return

    try:
        await onboarding_service.handle_new_member(ctx.author)
        await ctx.reply("✅ Sistema de regras testado. Verifique o canal de verificação!")
    except Exception as e:
        logger.error(f"Erro no comando testarregras: {e}")
        await ctx.reply(f"❌ Erro ao testar: {str(e)}")


@bot.command(name='perfil')
async def ver_perfil(ctx, member: discord.Member = None):
    if not onboarding_service:
        await ctx.reply("❌ Sistema ainda não foi inicializado completamente.")
        return

    try:
        target = member or ctx.author
        user = await onboarding_service.get_user_stats(str(target.id))

        if not user:
            await ctx.reply("❌ Usuário não encontrado no sistema")
            return

        embed = discord.Embed(title=f"📊 Perfil de {target.name}", color=discord.Color.blue())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(
            name="Informações Gerais",
            value=(
                f"**Entrou em:** {user.joined_at.strftime('%d/%m/%Y %H:%M')}\n"
                f"**Regras aceitas:** {'✅ Sim' if user.has_accepted_rules else '❌ Não'}"
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
        logger.error(f"Erro no comando perfil: {e}")
        await ctx.reply(f"❌ Erro ao buscar perfil: {str(e)}")


# ==================== COMANDOS DE CARDS ====================

@bot.command(name='atualizarcards')
@commands.has_permissions(administrator=True)
async def atualizar_cards(ctx, canal: discord.TextChannel = None):
    try:
        channel = canal or ctx.channel
        channel_name = channel.name
        valid_channels = [ch["name"] for ch in ChannelsConfig.get_all_channels()]

        if channel_name not in valid_channels:
            await ctx.send(f"❌ {channel.mention} não é um canal de partidas válido!")
            return

        confirm_embed = discord.Embed(
            title="⚠️ Atualizar Cards",
            description=f"Isso vai **deletar** todos os cards antigos em {channel.mention} e criar novos.\n\nDeseja continuar?",
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
                await ctx.send("❌ Operação cancelada.")
                return
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.send("❌ Tempo esgotado. Operação cancelada.")
            return

        await msg.delete()
        status_msg = await ctx.send(f"🔄 Atualizando cards em {channel.mention}...")

        success = await channel_service.setup_queue_cards(ctx.guild, channel)
        if success:
            await status_msg.edit(content=f"✅ Cards atualizados com sucesso em {channel.mention}!")
        else:
            await status_msg.edit(content=f"❌ Erro ao atualizar cards em {channel.mention}")

        logger.info(f"Cards atualizados em {channel.name} por {ctx.author}")

    except Exception as e:
        logger.error(f"Erro ao atualizar cards: {e}")
        await ctx.send(f"❌ Erro ao atualizar cards: {e}")


@bot.command(name='atualizartodos')
@commands.has_permissions(administrator=True)
async def atualizar_todos_cards(ctx):
    try:
        confirm_embed = discord.Embed(
            title="⚠️ Atualizar TODOS os Cards",
            description="Isso vai **deletar** todos os cards antigos em **TODOS** os canais de partida e criar novos.\n\n⚠️ Essa operação pode demorar alguns minutos.\n\nDeseja continuar?",
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
                await ctx.send("❌ Operação cancelada.")
                return
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.send("❌ Tempo esgotado. Operação cancelada.")
            return

        await msg.delete()

        guild = ctx.guild
        valid_channel_names = [ch["name"] for ch in ChannelsConfig.get_all_channels()]
        channels_to_update = [c for c in guild.text_channels if c.name in valid_channel_names]

        if not channels_to_update:
            await ctx.send("❌ Nenhum canal de partida encontrado!")
            return

        status_msg = await ctx.send(f"🔄 Atualizando {len(channels_to_update)} canais...")
        success_count = 0

        for i, channel in enumerate(channels_to_update, 1):
            await status_msg.edit(content=f"🔄 Atualizando canal {i}/{len(channels_to_update)}: {channel.mention}")
            if await channel_service.setup_queue_cards(guild, channel):
                success_count += 1
            await asyncio.sleep(2)

        final_embed = discord.Embed(
            title="✅ Atualização Concluída",
            description=f"Cards atualizados em **{success_count}/{len(channels_to_update)}** canais",
            color=discord.Color.green()
        )
        await status_msg.edit(content=None, embed=final_embed)
        logger.info(f"Todos os cards atualizados por {ctx.author}")

    except Exception as e:
        logger.error(f"Erro ao atualizar todos os cards: {e}")
        await ctx.send(f"❌ Erro ao atualizar cards: {e}")


# ==================== COMANDOS DE PARTIDA (texto) ====================

@bot.command(name='partidas')
async def ver_partidas(ctx):
    """ status e campos do modelo"""
    try:
        matches = await match_service.get_active_matches()

        if not matches:
            await ctx.reply("📭 Nenhuma partida ativa no momento")
            return

        # Mapa de emoji por status
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
            emoji = status_emoji.get(match['status'], '❓')
            players_str = " • ".join(f"<@{pid}>" for pid in match.get('player_ids', []))

            # Link para a thread, se existir
            thread_info = ""
            if match.get('thread_id'):
                thread_info = f"\n🧵 <#{match['thread_id']}>"

            embed.add_field(
                name=f"{emoji} `{match['_id']}` — {match.get('match_type','?')} R${match.get('bet_value',0):.2f}",
                value=(
                    f"👥 {players_str}\n"
                    f"🕵️ <@{match.get('mediator_id','?')}>\n"
                    f"📊 {match['status']}"
                    f"{thread_info}"
                ),
                inline=False
            )

        if len(matches) > 5:
            embed.set_footer(text=f"Mostrando 5 de {len(matches)} partidas")

        await ctx.reply(embed=embed)

    except Exception as e:
        logger.error(f"Erro no comando partidas: {e}")
        await ctx.reply(f"❌ Erro ao buscar partidas: {str(e)}")


@bot.command(name='cancelarpartida')
@commands.has_permissions(administrator=True)  # só admin pode cancelar via comando
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

        # Avisar na thread, se existir
        thread_id = match.get('thread_id')
        if thread_id:
            thread = bot.get_channel(thread_id)
            if thread:
                await thread.send("❌ Esta partida foi cancelada por um administrador.")

        await ctx.reply(embed=embed)

    except Exception as e:
        logger.error(f"Erro no comando cancelarpartida: {e}")
        await ctx.reply(f"❌ Erro ao cancelar partida: {str(e)}")



# Mantidos apenas para uso administrativo emergencial:

@bot.command(name='forcarconcluir')
@commands.has_permissions(administrator=True)
async def forcar_concluir(ctx, match_id: str):
    """Forçar conclusão de uma partida (uso emergencial de admin)"""
    try:
        match = await match_service.complete_match(match_id)
        if not match:
            await ctx.reply("❌ Partida não encontrada.")
            return

        embed = discord.Embed(
            title="✅ Partida Forçada como Concluída",
            description=f"A partida `{match_id}` foi marcada como concluída.",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)

    except Exception as e:
        logger.error(f"Erro no comando forcarconcluir: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


# ==================== COMANDOS DE MEDIADOR ====================

@bot.command(name='setupmediadores')
@commands.has_permissions(administrator=True)
async def setup_mediadores(ctx):
    try:
        guild = ctx.guild

        existing_channel = discord.utils.get(guild.channels, name="painel-mediadores")
        if existing_channel:
            await ctx.send("❌ O canal #painel-mediadores já existe!")
            return

        mediator_role = discord.utils.get(guild.roles, name="Controller")
        if not mediator_role:
            mediator_role = await guild.create_role(
                name="Controller",
                color=discord.Color.blue(),
                mentionable=True
            )
            logger.info("Cargo 'Controller' criado")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            mediator_role:       discord.PermissionOverwrite(read_messages=True, send_messages=False),
            guild.me:            discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel = await guild.create_text_channel(
            name="painel-mediadores",
            overwrites=overwrites,
            topic="Painel de controle para mediadores"
        )

        info = await mediator_queue.get_queue_info()
        embed = create_mediator_panel_embed(info)
        view  = MediatorPanelView()
        await channel.send(embed=embed, view=view)

        success_embed = discord.Embed(
            title="✅ Painel de Mediadores Configurado",
            description=f"Canal {channel.mention} criado com sucesso!",
            color=discord.Color.green()
        )
        success_embed.add_field(name="Cargo criado", value=mediator_role.mention, inline=False)
        success_embed.add_field(
            name="Próximos passos",
            value="1. Dê o cargo @Controller para os mediadores\n2. Eles poderão acessar o painel e gerenciar sua presença na fila",
            inline=False
        )
        await ctx.send(embed=success_embed)

    except discord.Forbidden:
        await ctx.send("❌ Não tenho permissão para criar canais ou cargos!")
    except Exception as e:
        logger.error(f"Erro ao configurar painel de mediadores: {e}")
        await ctx.send(f"❌ Erro ao configurar painel: {e}")


@bot.command(name='addmediador')
async def add_mediador(ctx):
    try:
        mediator = await mediator_queue.add_mediator(str(ctx.author.id), ctx.author.name)
        embed = discord.Embed(
            title="✅ Mediador Adicionado",
            description=f"Você foi adicionado como mediador na posição **{mediator.position}**",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)
    except Exception as e:
        logger.error(f"Erro no comando addmediador: {e}")
        await ctx.reply(f"❌ Erro ao adicionar mediador: {str(e)}")


@bot.command(name='removemediador')
async def remove_mediador(ctx):
    try:
        await mediator_queue.remove_mediador(str(ctx.author.id))
        embed = discord.Embed(
            title="🚫 Mediador Removido",
            description="Você foi removido da fila de mediadores",
            color=discord.Color.orange()
        )
        await ctx.reply(embed=embed)
    except Exception as e:
        logger.error(f"Erro no comando removemediador: {e}")
        await ctx.reply(f"❌ Erro ao remover mediador: {str(e)}")


@bot.command(name='fila')
async def ver_fila(ctx):
    try:
        stats = await mediator_queue.get_queue_stats()

        if stats['total_active'] == 0:
            await ctx.reply("📭 Nenhum mediador ativo na fila")
            return

        embed = discord.Embed(
            title="📋 Fila de Mediadores",
            description=f"Total de mediadores ativos: **{stats['total_active']}**",
            color=discord.Color.blue()
        )
        for m in stats['mediators'][:10]:
            status_emoji = "✅" if m['can_mediate'] else "⏳"
            embed.add_field(
                name=f"{status_emoji} Posição {m['position']} — {m['username']}",
                value=f"Total de partidas: {m['total_matches']}\nPartidas (últimos 8min): {m['matches_in_last_8_min']}/5",
                inline=False
            )

        if stats['total_active'] > 10:
            embed.set_footer(text=f"Mostrando 10 de {stats['total_active']} mediadores")

        await ctx.reply(embed=embed)

    except Exception as e:
        logger.error(f"Erro no comando fila: {e}")
        await ctx.reply(f"❌ Erro ao buscar fila: {str(e)}")


@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(
        title="📚 Comandos Disponíveis",
        color=discord.Color.blue()
    )

    commands_list = [
        # Jogadores
        ("!fila",                     "Ver fila atual de mediadores"),
        ("!perfil [@usuario]",        "Ver perfil de um jogador"),
        ("!statuscanal [nome]",       "Ver estatísticas de um canal"),
        ("!partidas",                 "Ver partidas ativas"),
        # Mediadores
        ("!addmediador",              "Entrar na fila de mediadores"),
        ("!removemediador",           "Sair da fila de mediadores"),
        # Admin
        ("!setupcanais",              "Criar todos os canais de partida (Admin)"),
        ("!atualizarcards [#canal]",  "Atualizar cards de um canal (Admin)"),
        ("!atualizartodos",           "Atualizar cards de todos os canais (Admin)"),
        ("!setupmediadores",          "Criar painel de mediadores (Admin)"),
        ("!sincmediadores",           "Sincronizar mediadores por cargo (Admin)"),
        ("!cancelarpartida <id>",     "Cancelar uma partida (Admin)"),
        ("!forcarconcluir <id>",      "Forçar conclusão de partida (Admin)"),
        ("!setupverificacao",         "Configurar canal de verificação (Admin)"),
    ]

    for cmd, desc in commands_list:
        embed.add_field(name=cmd, value=desc, inline=False)

    # Nota sobre o novo sistema de threads
    embed.add_field(
        name="ℹ️ Como funciona o novo sistema",
        value=(
            "1. Entre na fila clicando em um botão de valor\n"
            "2. Quando a fila encher, confirme a partida\n"
            "3. Uma **thread privada** será criada com times e mediador\n"
            "4. O mediador controla tudo pelos botões dentro da thread"
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

        logger.info("Inicializando sistema de onboarding...")
        onboarding_service = OnboardingService(bot)

        logger.info("Inicializando serviço de canais...")
        channel_service = ChannelService(bot)

        logger.info("Iniciando Discord Bot...")
        await start_discord_bot(bot)

    except KeyboardInterrupt:
        logger.info("Recebido sinal de interrupção...")
    except Exception as e:
        logger.error(f"Erro fatal: {e}", exc_info=True)
    finally:
        logger.info("Encerrando sistema...")
        await db.close()
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
