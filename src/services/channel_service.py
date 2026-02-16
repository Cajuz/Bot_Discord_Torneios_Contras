import discord
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId

from config.database import db
from config.channels_config import ChannelsConfig
from models.match import Match
from services.mediator_queue import mediator_queue
from services.match_queue_service import match_queue_service
from views.match_cards_view import MatchCardView, MatchInfoEmbed
from views.match_queue_view import create_match_queue_embed, MatchQueueView
from utils.logger import logger, log_success


class ChannelService:
    """Serviço de gerenciamento de canais de partidas"""
    
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.active_cards: Dict[str, discord.Message] = {}
    
    async def setup_all_channels(self, guild: discord.Guild):
        """Configurar todos os canais de partidas"""
        try:
            logger.info("Iniciando configuração de canais...")
            
            categories = {}
            
            # Criar/obter categorias
            for category_name, category_data in ChannelsConfig.CATEGORIES.items():
                category = discord.utils.get(guild.categories, name=category_name)
                
                if not category:
                    category = await guild.create_category(name=category_name)
                    logger.info(f"Categoria '{category_name}' criada")
                
                categories[category_name] = category
            
            # Criar/configurar canais
            for category_name, category_data in ChannelsConfig.CATEGORIES.items():
                category = categories[category_name]
                
                for channel_info in category_data["channels"]:
                    channel_name = channel_info["name"]
                    
                    # Verificar se canal existe
                    channel = discord.utils.get(guild.text_channels, name=channel_name)
                    
                    if not channel:
                        # Criar canal
                        channel = await guild.create_text_channel(
                            name=channel_name,
                            category=category,
                            topic=f"Canal de partidas {channel_name.upper()}"
                        )
                        logger.info(f"Canal '#{channel_name}' criado")
                    
                    # Configurar cards de fila no canal
                    await self.setup_queue_cards(guild, channel)
            
            log_success("Todos os canais foram configurados com sucesso!")
            
        except Exception as e:
            logger.error(f"Erro ao configurar canais: {e}")
            raise
    
    async def setup_queue_cards(self, guild: discord.Guild, channel: discord.TextChannel):
        """
        Configurar cards de fila em um canal específico
        Remove cards antigos e cria novos com sistema de filas
        """
        try:
            # Limpar mensagens antigas do bot
            async for message in channel.history(limit=100):
                if message.author == guild.me:
                    try:
                        await message.delete()
                    except:
                        pass
            
            # Obter informações do canal
            channel_name = channel.name
            max_players = ChannelsConfig.get_channel_players(channel_name)
            
            # Criar um card para cada valor
            for bet_value in ChannelsConfig.BET_VALUES:
                # Criar embed
                embed = create_match_queue_embed(
                    channel_name=channel_name,
                    bet_value=bet_value,
                    max_players=max_players,
                    queue_normal_count=0,
                    queue_infinito_count=0
                )
                
                # Criar view com botões
                view = MatchQueueView(
                    channel_name=channel_name,
                    bet_value=bet_value,
                    max_players=max_players
                )
                
                # Enviar card
                message = await channel.send(embed=embed, view=view)
                
                # Salvar referência
                card_key = f"{channel_name}_{bet_value}"
                self.active_cards[card_key] = message
                
                logger.info(f"Card R$ {bet_value} criado em {channel.name}")
                
                # Pequeno delay para não sobrecarregar
                await asyncio.sleep(0.5)
            
            logger.info(f"✅ Cards de fila configurados em {channel.name}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao configurar cards de fila em {channel.name}: {e}")
            return False
    
    async def refresh_queue_card(
        self,
        channel: discord.TextChannel,
        bet_value: float,
        gel_type: str = None
    ):
        """
        Atualizar um card específico com as informações da fila
        """
        try:
            channel_name = channel.name
            max_players = ChannelsConfig.get_channel_players(channel_name)
            
            # Obter contadores de ambas as filas
            queue_normal = await match_queue_service.get_queue_status(
                channel_name, bet_value, "normal"
            )
            queue_infinito = await match_queue_service.get_queue_status(
                channel_name, bet_value, "infinito"
            )
            
            queue_normal_count = len(queue_normal.players) if queue_normal else 0
            queue_infinito_count = len(queue_infinito.players) if queue_infinito else 0
            
            # Criar embed atualizado
            embed = create_match_queue_embed(
                channel_name=channel_name,
                bet_value=bet_value,
                max_players=max_players,
                queue_normal_count=queue_normal_count,
                queue_infinito_count=queue_infinito_count
            )
            
            # Verificar se temos a mensagem salva
            card_key = f"{channel_name}_{bet_value}"
            if card_key in self.active_cards:
                try:
                    message = self.active_cards[card_key]
                    await message.edit(embed=embed)
                    logger.info(f"Card R$ {bet_value} atualizado em {channel.name}")
                    return True
                except:
                    pass
            
            # Se não temos salva, buscar nas mensagens recentes
            async for message in channel.history(limit=50):
                if message.author == channel.guild.me and message.embeds:
                    if f"R$ {bet_value:.2f}" in message.embeds[0].title:
                        await message.edit(embed=embed)
                        # Salvar referência
                        self.active_cards[card_key] = message
                        logger.info(f"Card R$ {bet_value} atualizado em {channel.name}")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erro ao atualizar card: {e}")
            return False
    
    async def _setup_channel_card(
        self,
        channel: discord.TextChannel,
        channel_name: str,
        channel_info: Dict
    ):
        """
        MÉTODO LEGADO - Mantido para compatibilidade
        Use setup_queue_cards() para o novo sistema
        """
        try:
            # Criar embed de boas-vindas
            embed = MatchInfoEmbed.create_welcome_card(channel_name, channel_info)
            
            # Criar view com botões
            view = MatchCardView(self, channel_name)
            
            # Enviar mensagem
            message = await channel.send(embed=embed, view=view)
            
            # Fixar mensagem
            await message.pin()
            
            # Salvar referência
            self.active_cards[channel_name] = message
            
            logger.info(f"Card configurado no canal #{channel_name}")
            
        except Exception as e:
            logger.error(f"Erro ao configurar card do canal #{channel_name}: {e}")
    
    async def create_match_with_thread(
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str,
        creator: discord.Member,
        channel: discord.TextChannel,
        all_player_ids: List[int] = None
    ) -> Dict[str, Any]:
        """
        Criar partida e tópico automaticamente
        Agora com suporte para gel_type e múltiplos jogadores
        """
        try:
            # Obter informações do canal
            max_players = ChannelsConfig.get_channel_players(channel_name)
            
            # Obter mediador
            mediator = await mediator_queue.get_next_mediator()
            
            if not mediator:
                return {'success': False, 'error': 'Não há mediadores disponíveis'}
            
            # Lista de jogadores (da fila ou apenas o criador)
            player_ids = all_player_ids or [creator.id]
            
            # Criar documento de partida no banco
            match_doc = {
                'creator_id': str(creator.id),
                'channel_name': channel_name,
                'match_type': channel_name,
                'bet_value': bet_value,
                'gel_type': gel_type,
                'mediator_id': str(mediator._id),
                'mediator_discord_id': str(mediator.discord_id),
                'status': 'in_progress' if len(player_ids) >= max_players else 'waiting_players',
                'players': [str(pid) for pid in player_ids],
                'max_players': max_players,
                'thread_id': None,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            collection = db.get_collection('matches')
            result = await collection.insert_one(match_doc)
            match_id = str(result.inserted_id)
            
            # Criar tópico
            gel_emoji = "🔥" if gel_type == "normal" else "♾️"
            thread_name = f"{gel_emoji} R$ {bet_value:.0f} | {channel_name.upper()} | {gel_type.capitalize()}"
            
            thread = await channel.create_thread(
                name=thread_name[:100],  # Limite de 100 caracteres
                type=discord.ChannelType.public_thread,
                reason=f"Partida criada - {gel_type}"
            )
            
            # Atualizar match com thread_id
            await collection.update_one(
                {'_id': result.inserted_id},
                {'$set': {'thread_id': str(thread.id)}}
            )
            
            # Adicionar todos os jogadores ao tópico
            for player_id in player_ids:
                try:
                    member = await channel.guild.fetch_member(player_id)
                    await thread.add_user(member)
                except Exception as e:
                    logger.warning(f"Não foi possível adicionar jogador {player_id} ao tópico: {e}")
            
            # Adicionar mediador ao tópico
            try:
                mediator_member = await channel.guild.fetch_member(int(mediator.discord_id))
                await thread.add_user(mediator_member)
            except Exception as e:
                logger.warning(f"Não foi possível adicionar mediador ao tópico: {e}")
            
            # Enviar mensagem de boas-vindas no tópico
            embed = discord.Embed(
                title="🎮 Partida Iniciada!",
                description=f"**Modo:** {channel_name.upper()}\n**Valor:** R$ {bet_value:.2f}\n**GEL:** {gel_type.capitalize()}",
                color=discord.Color.green()
            )
            
            players_text = "\n".join([f"• <@{pid}>" for pid in player_ids])
            embed.add_field(name="Jogadores", value=players_text, inline=False)
            embed.add_field(name="Mediador", value=f"<@{mediator.discord_id}>", inline=False)
            embed.add_field(name="ID da Partida", value=f"`{match_id}`", inline=False)
            
            players_mention = " ".join([f"<@{pid}>" for pid in player_ids])
            
            await thread.send(
                content=f"🔔 {players_mention} | Mediador: <@{mediator.discord_id}>",
                embed=embed
            )
            
            # Notificar mediador
            try:
                mediator_user = await self.bot.fetch_user(int(mediator.discord_id))
                await mediator_user.send(
                    f"🔔 **Nova Partida Atribuída!**\n\n"
                    f"**Tipo:** {channel_name.upper()}\n"
                    f"**Valor:** R$ {bet_value:.2f}\n"
                    f"**GEL:** {gel_type.capitalize()}\n"
                    f"**Jogadores:** {len(player_ids)}/{max_players}\n"
                    f"**Tópico:** {thread.mention}\n"
                    f"**ID:** `{match_id}`"
                )
            except Exception as e:
                logger.warning(f"Não foi possível enviar DM ao mediador: {e}")
            
            log_success(
                f"Partida criada: {channel_name} | R$ {bet_value} | {gel_type} | "
                f"Jogadores: {len(player_ids)}/{max_players} | Mediador: {mediator.username}"
            )
            
            return {
                'success': True,
                'match_id': match_id,
                'thread': thread,
                'mediator': mediator
            }
            
        except Exception as e:
            logger.error(f"Erro ao criar partida: {e}")
            return {'success': False, 'error': str(e)}
    
    async def add_player_to_match(
        self,
        match_id: str,
        player: discord.Member
    ) -> Dict[str, Any]:
        """Adicionar jogador a uma partida"""
        try:
            collection = db.get_collection('matches')
            match_doc = await collection.find_one({'_id': ObjectId(match_id)})
            
            if not match_doc:
                return {'success': False, 'error': 'Partida não encontrada'}
            
            # Verificar se já está na partida
            if str(player.id) in match_doc['players']:
                return {'success': False, 'error': 'Você já está nesta partida'}
            
            # Verificar se partida está cheia
            if len(match_doc['players']) >= match_doc['max_players']:
                return {'success': False, 'error': 'Partida cheia'}
            
            # Adicionar jogador
            await collection.update_one(
                {'_id': ObjectId(match_id)},
                {
                    '$push': {'players': str(player.id)},
                    '$set': {'updated_at': datetime.utcnow()}
                }
            )
            
            # Adicionar ao tópico
            if match_doc.get('thread_id'):
                try:
                    thread = await self.bot.fetch_channel(int(match_doc['thread_id']))
                    await thread.add_user(player)
                    
                    await thread.send(
                        f"✅ {player.mention} entrou na partida! "
                        f"({len(match_doc['players']) + 1}/{match_doc['max_players']})"
                    )
                except Exception as e:
                    logger.warning(f"Não foi possível adicionar jogador ao tópico: {e}")
            
            # Verificar se partida está completa
            if len(match_doc['players']) + 1 >= match_doc['max_players']:
                await self._start_match(match_id)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Erro ao adicionar jogador: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _start_match(self, match_id: str):
        """Iniciar partida quando todos os jogadores entrarem"""
        try:
            collection = db.get_collection('matches')
            
            await collection.update_one(
                {'_id': ObjectId(match_id)},
                {
                    '$set': {
                        'status': 'in_progress',
                        'started_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            match_doc = await collection.find_one({'_id': ObjectId(match_id)})
            
            if match_doc.get('thread_id'):
                thread = await self.bot.fetch_channel(int(match_doc['thread_id']))
                
                embed = discord.Embed(
                    title="🎮 Partida Iniciada!",
                    description="Todos os jogadores estão presentes. Boa sorte!",
                    color=discord.Color.green()
                )
                
                players_mention = " ".join([f"<@{pid}>" for pid in match_doc['players']])
                
                await thread.send(
                    content=f"🔔 {players_mention} <@{match_doc['mediator_discord_id']}>",
                    embed=embed
                )
            
            log_success(f"Partida {match_id} iniciada automaticamente")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar partida: {e}")
    
    async def get_channel_stats(self, channel_name: str) -> Dict[str, Any]:
        """Obter estatísticas de um canal"""
        try:
            collection = db.get_collection('matches')
            
            total = await collection.count_documents({'channel_name': channel_name})
            active = await collection.count_documents({
                'channel_name': channel_name,
                'status': {'$in': ['waiting_players', 'in_progress']}
            })
            completed = await collection.count_documents({
                'channel_name': channel_name,
                'status': 'completed'
            })
            
            return {
                'total': total,
                'active': active,
                'completed': completed
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {'total': 0, 'active': 0, 'completed': 0}


# Instância global (será inicializada no main.py)
channel_service = None
