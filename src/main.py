import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime  

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

# Carregar variáveis de ambiente
load_dotenv()

# Criar bot
bot = create_discord_bot()

# Services globais (inicializados em main())
onboarding_service = None
channel_service = None


# ==================== EVENTOS DO BOT ====================

@bot.event
async def on_member_join(member: discord.Member):
    """Evento quando um membro entra no servidor"""
    try:
        if onboarding_service:  # ⭐ VERIFICAR SE EXISTE
            await onboarding_service.handle_new_member(member)
        else:
            logger.error("Onboarding service não inicializado")
    except Exception as e:
        logger.error(f"Erro no evento on_member_join: {e}")


@bot.event
async def on_member_remove(member: discord.Member):
    """Evento quando um membro sai do servidor"""
    try:
        collection = db.get_collection('users')
        await collection.update_one(
            {'discord_id': str(member.id)},
            {'$set': {'is_active': False, 'updated_at': datetime.now()}}
        )
        logger.info(f"Membro {member.name} saiu do servidor")
    except Exception as e:
        logger.error(f"Erro no evento on_member_remove: {e}")


# ==================== COMANDOS ADMINISTRATIVOS ====================

@bot.command(name='setupcanais')
@commands.has_permissions(administrator=True)
async def setup_canais(ctx):
    """Configurar todos os canais de partidas (Admin)"""
    if not channel_service:  # ⭐ VERIFICAR
        await ctx.send("❌ Sistema ainda não foi inicializado completamente.")
        return
        
    try:
        await ctx.send("⏳ Configurando canais... Isso pode levar alguns segundos.")
        
        await channel_service.setup_all_channels(ctx.guild)
        
        embed = discord.Embed(
            title="✅ Canais Configurados!",
            description="Todos os canais de partidas foram criados e configurados com sucesso!",
            color=discord.Color.green()
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
            name="💰 Valores Disponíveis",
            value="R$ 2 • R$ 5 • R$ 10 • R$ 20 • R$ 50 • R$ 100 • R$ 200",
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Erro no comando setupcanais: {e}")
        await ctx.send(f"❌ Erro ao configurar canais: {str(e)}")


@bot.command(name='entrarpartida')
async def entrar_partida(ctx, match_id: str):
    """Entrar em uma partida existente"""
    if not channel_service:  # ⭐ VERIFICAR
        await ctx.reply("❌ Sistema ainda não foi inicializado completamente.")
        return
        
    try:
        result = await channel_service.add_player_to_match(match_id, ctx.author)
        
        if result['success']:
            await ctx.reply("✅ Você entrou na partida!")
        else:
            await ctx.reply(f"❌ {result['error']}")
            
    except Exception as e:
        logger.error(f"Erro no comando entrarpartida: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


@bot.command(name='statuscanal')
async def status_canal(ctx, channel_name: str = None):
    """Ver estatísticas de um canal"""
    if not channel_service:  # ⭐ VERIFICAR
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
        
        embed.add_field(name="Total de Partidas", value=stats['total'], inline=True)
        embed.add_field(name="Ativas", value=stats['active'], inline=True)
        embed.add_field(name="Finalizadas", value=stats['completed'], inline=True)
        
        await ctx.reply(embed=embed)
        
    except Exception as e:
        logger.error(f"Erro no comando statuscanal: {e}")
        await ctx.reply(f"❌ Erro: {str(e)}")


@bot.command(name='setupverificacao')
@commands.has_permissions(administrator=True)
async def setup_verificacao(ctx, channel: discord.TextChannel, role: discord.Role):
    """Configurar canal e cargo de verificação (Admin)"""
    if not onboarding_service:  # ⭐ VERIFICAR
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
    """Testar sistema de regras (Admin)"""
    if not onboarding_service:  # ⭐ VERIFICAR
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
    """Ver perfil de um usuário"""
    if not onboarding_service:  # ⭐ VERIFICAR
        await ctx.reply("❌ Sistema ainda não foi inicializado completamente.")
        return
        
    try:
        target = member or ctx.author
        user = await onboarding_service.get_user_stats(str(target.id))
        
        if not user:
            await ctx.reply("❌ Usuário não encontrado no sistema")
            return
        
        embed = discord.Embed(
            title=f"📊 Perfil de {target.name}",
            color=discord.Color.blue()
        )
        
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
            embed.add_field(
                name="Taxa de Vitória",
                value=f"{winrate:.1f}%",
                inline=False
            )
        
        await ctx.reply(embed=embed)
        
    except Exception as e:
        logger.error(f"Erro no comando perfil: {e}")
        await ctx.reply(f"❌ Erro ao buscar perfil: {str(e)}")


# ==================== COMANDOS DO BOT ====================
@bot.command(name='atualizarcards')
@commands.has_permissions(administrator=True)
async def atualizar_cards(ctx, canal: discord.TextChannel = None):
    """
    Atualizar os cards de um canal para o novo sistema de filas
    Uso: !atualizarcards #1x1-mob
    Ou: !atualizarcards (no canal atual)
    """
    try:
        channel = canal or ctx.channel
        
        # Verificar se é um canal de partidas
        channel_name = channel.name
        valid_channels = [ch["name"] for ch in ChannelsConfig.get_all_channels()]
        
        if channel_name not in valid_channels:
            await ctx.send(f"❌ {channel.mention} não é um canal de partidas válido!")
            return
        
        # Confirmar ação
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
            reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "❌":
                await msg.delete()
                await ctx.send("❌ Operação cancelada.")
                return
            
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.send("❌ Tempo esgotado. Operação cancelada.")
            return
        
        await msg.delete()
        
        # Atualizar cards
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
    """
    Atualizar os cards de TODOS os canais de partida
    Uso: !atualizartodos
    """
    try:
        # Confirmar ação
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
            reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "❌":
                await msg.delete()
                await ctx.send("❌ Operação cancelada.")
                return
            
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.send("❌ Tempo esgotado. Operação cancelada.")
            return
        
        await msg.delete()
        
        # Buscar todos os canais de partida
        guild = ctx.guild
        valid_channel_names = [ch["name"] for ch in ChannelsConfig.get_all_channels()]
        channels_to_update = []
        
        for channel in guild.text_channels:
            if channel.name in valid_channel_names:
                channels_to_update.append(channel)
        
        if not channels_to_update:
            await ctx.send("❌ Nenhum canal de partida encontrado!")
            return
        
        # Atualizar cada canal
        status_msg = await ctx.send(f"🔄 Atualizando {len(channels_to_update)} canais...")
        
        success_count = 0
        for i, channel in enumerate(channels_to_update, 1):
            await status_msg.edit(content=f"🔄 Atualizando canal {i}/{len(channels_to_update)}: {channel.mention}")
            
            if await channel_service.setup_queue_cards(guild, channel):
                success_count += 1
            
            # Aguardar um pouco entre canais para não sobrecarregar
            await asyncio.sleep(2)
        
        # Mensagem final
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

@bot.command(name='setupmediadores')
@commands.has_permissions(administrator=True)
async def setup_mediadores(ctx):
    """
    Criar canal de painel de mediadores
    Uso: !setupmediadores
    """
    try:
        guild = ctx.guild
        
        # Verificar se já existe
        existing_channel = discord.utils.get(guild.channels, name="painel-mediadores")
        if existing_channel:
            await ctx.send("❌ O canal #painel-mediadores já existe!")
            return
        
        # Criar cargo de mediador se não existir
        mediator_role = discord.utils.get(guild.roles, name="Mediador")
        if not mediator_role:
            mediator_role = await guild.create_role(
                name="Mediador",
                color=discord.Color.blue(),
                mentionable=True
            )
            logger.info(f"Cargo 'Mediador' criado")
        
        # Criar canal privado para mediadores
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            mediator_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        channel = await guild.create_text_channel(
            name="painel-mediadores",
            overwrites=overwrites,
            topic="Painel de controle para mediadores"
        )
        
        # Enviar embed e view
        from views.mediator_panel_view import create_mediator_panel_embed, MediatorPanelView
        
        embed = create_mediator_panel_embed()
        view = MediatorPanelView()
        
        await channel.send(embed=embed, view=view)
        
        # Mensagem de sucesso
        success_embed = discord.Embed(
            title="✅ Painel de Mediadores Configurado",
            description=f"Canal {channel.mention} criado com sucesso!",
            color=discord.Color.green()
        )
        
        success_embed.add_field(
            name="Cargo criado",
            value=mediator_role.mention,
            inline=False
        )
        
        success_embed.add_field(
            name="Próximos passos",
            value="1. Dê o cargo @Mediador para os mediadores\n2. Eles poderão acessar o canal e gerenciar sua presença na fila",
            inline=False
        )
        
        await ctx.send(embed=success_embed)
        logger.info(f"Painel de mediadores configurado por {ctx.author}")
        
    except discord.Forbidden:
        await ctx.send("❌ Não tenho permissão para criar canais ou cargos!")
    except Exception as e:
        logger.error(f"Erro ao configurar painel de mediadores: {e}")
        await ctx.send(f"❌ Erro ao configurar painel: {e}")

@bot.command(name='addmediador')
async def add_mediador(ctx):
    """Adicionar usuário como mediador"""
    try:
        user_id = str(ctx.author.id)
        username = ctx.author.name
        
        mediator = await mediator_queue.add_mediator(user_id, username)
        
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
    """Remover usuário da fila de mediadores"""
    try:
        user_id = str(ctx.author.id)
        
        mediator = await mediator_queue.remove_mediador(user_id)
        
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
    """Ver fila de mediadores"""
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
                name=f"{status_emoji} Posição {m['position']} - {m['username']}",
                value=(
                    f"Total de partidas: {m['total_matches']}\n"
                    f"Partidas (últimos 8min): {m['matches_in_last_8_min']}/5"
                ),
                inline=False
            )
        
        if stats['total_active'] > 10:
            embed.set_footer(text=f"Mostrando 10 de {stats['total_active']} mediadores")
        
        await ctx.reply(embed=embed)
        
    except Exception as e:
        logger.error(f"Erro no comando fila: {e}")
        await ctx.reply(f"❌ Erro ao buscar fila: {str(e)}")


@bot.command(name='x1')
async def criar_x1(ctx, member: discord.Member):
    """Criar partida 1v1 com outro jogador"""
    try:
        player1_id = str(ctx.author.id)
        player2_id = str(member.id)
        
        if player1_id == player2_id:
            await ctx.reply("❌ Você não pode criar uma partida contra si mesmo!")
            return
        
        result = await match_service.create_match(player1_id, player2_id)
        match = result['match']
        mediator = result['mediator']
        
        embed = discord.Embed(
            title="🎮 Partida Criada!",
            description="Uma nova partida 1v1 foi criada",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="Jogadores",
            value=f"{ctx.author.mention} **VS** {member.mention}",
            inline=False
        )
        
        embed.add_field(
            name="Mediador",
            value=f"<@{mediator['discord_id']}> (Posição: {mediator['position']})",
            inline=False
        )
        
        embed.add_field(
            name="ID da Partida",
            value=f"`{match._id}`",
            inline=False
        )
        
        embed.set_footer(text="Use !iniciarpartida <id> para iniciar")
        
        await ctx.reply(embed=embed)
        
        # Notificar mediador
        try:
            mediator_user = await bot.fetch_user(int(mediator['discord_id']))
            if mediator_user:
                await mediator_user.send(
                    f"🔔 Você foi selecionado para mediar uma partida!\n"
                    f"Jogadores: {ctx.author.name} vs {member.name}\n"
                    f"ID: `{match._id}`"
                )
        except:
            pass
        
    except Exception as e:
        logger.error(f"Erro no comando x1: {e}")
        await ctx.reply(f"❌ Erro ao criar partida: {str(e)}")


@bot.command(name='iniciarpartida')
async def iniciar_partida(ctx, match_id: str):
    """Iniciar uma partida pendente"""
    try:
        match = await match_service.start_match(match_id)
        
        embed = discord.Embed(
            title="▶️ Partida Iniciada",
            description=f"A partida `{match_id}` foi iniciada!",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)
        
    except Exception as e:
        logger.error(f"Erro no comando iniciarpartida: {e}")
        await ctx.reply(f"❌ Erro ao iniciar partida: {str(e)}")


@bot.command(name='finalizarpartida')
async def finalizar_partida(ctx, match_id: str):
    """Finalizar uma partida"""
    try:
        match = await match_service.complete_match(match_id)
        
        embed = discord.Embed(
            title="✅ Partida Finalizada",
            description=f"A partida `{match_id}` foi finalizada!",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)
        
    except Exception as e:
        logger.error(f"Erro no comando finalizarpartida: {e}")
        await ctx.reply(f"❌ Erro ao finalizar partida: {str(e)}")


@bot.command(name='cancelarpartida')
async def cancelar_partida(ctx, match_id: str):
    """Cancelar uma partida"""
    try:
        match = await match_service.cancel_match(match_id)
        
        embed = discord.Embed(
            title="🚫 Partida Cancelada",
            description=f"A partida `{match_id}` foi cancelada",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed)
        
    except Exception as e:
        logger.error(f"Erro no comando cancelarpartida: {e}")
        await ctx.reply(f"❌ Erro ao cancelar partida: {str(e)}")


@bot.command(name='partidas')
async def ver_partidas(ctx):
    """Ver partidas ativas"""
    try:
        matches = await match_service.get_active_matches()
        
        if not matches:
            await ctx.reply("📭 Nenhuma partida ativa no momento")
            return
        
        embed = discord.Embed(
            title="🎮 Partidas Ativas",
            description=f"Total: **{len(matches)}** partidas",
            color=discord.Color.purple()
        )
        
        for match in matches[:5]:
            status_emoji = "⏳" if match['status'] == 'pending' else "▶️"
            embed.add_field(
                name=f"{status_emoji} Partida `{match['_id']}`",
                value=(
                    f"Jogadores: <@{match['player1']}> vs <@{match['player2']}>\n"
                    f"Mediador: <@{match['mediator_discord_id']}>\n"
                    f"Status: {match['status']}"
                ),
                inline=False
            )
        
        if len(matches) > 5:
            embed.set_footer(text=f"Mostrando 5 de {len(matches)} partidas")
        
        await ctx.reply(embed=embed)
        
    except Exception as e:
        logger.error(f"Erro no comando partidas: {e}")
        await ctx.reply(f"❌ Erro ao buscar partidas: {str(e)}")


@bot.command(name='help')
async def help_command(ctx):
    """Mostrar comandos disponíveis"""
    embed = discord.Embed(
        title="📚 Comandos Disponíveis",
        description="Lista de comandos do sistema de mediadores",
        color=discord.Color.blue()
    )
    
    commands_list = [
        ("!addmediador", "Adicionar-se como mediador"),
        ("!removemediador", "Remover-se da fila de mediadores"),
        ("!fila", "Ver fila atual de mediadores"),
        ("!x1 @usuario", "Criar partida 1v1 com outro jogador"),
        ("!iniciarpartida <id>", "Iniciar uma partida pendente"),
        ("!finalizarpartida <id>", "Finalizar uma partida"),
        ("!cancelarpartida <id>", "Cancelar uma partida"),
        ("!partidas", "Ver partidas ativas"),
        ("!entrarpartida <id>", "Entrar em uma partida"),
        ("!statuscanal [nome]", "Ver estatísticas de um canal"),
        ("!help", "Mostrar esta mensagem")
    ]
    
    for cmd, desc in commands_list:
        embed.add_field(name=cmd, value=desc, inline=False)
    
    await ctx.reply(embed=embed)


# ==================== INICIALIZAÇÃO ====================

async def main():
    """Função principal para inicializar o sistema"""
    global onboarding_service, channel_service
    
    try:
        log_success("🚀 Iniciando sistema de mediadores...")
        
        # 1. Conectar ao MongoDB
        logger.info("Conectando ao MongoDB...")
        await db.connect()
        
        # 2. Inicializar fila de mediadores
        logger.info("Inicializando fila de mediadores...")
        await mediator_queue.initialize()
        
        # 3. Inicializar serviço de onboarding
        logger.info("Inicializando sistema de onboarding...")
        onboarding_service = OnboardingService(bot)
        
        # 4. Inicializar serviço de canais
        logger.info("Inicializando serviço de canais...")
        channel_service = ChannelService(bot)
        
        # 5. Iniciar bot Discord
        logger.info("Iniciando Discord Bot...")
        await start_discord_bot(bot)
        
    except KeyboardInterrupt:
        logger.info("Recebido sinal de interrupção...")
    except Exception as e:
        logger.error(f"Erro fatal: {e}", exc_info=True)
    finally:
        # Cleanup
        logger.info("Encerrando sistema...")
        await db.close()
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
