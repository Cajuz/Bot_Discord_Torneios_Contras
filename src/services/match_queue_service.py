import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import discord
from config.database import db
from models.queue import MatchQueue
from services.mediator_queue import mediator_queue
from services.match_service import match_service
from utils.logger import logger

class MatchQueueService:
    """Serviço para gerenciar filas de partidas"""
    
    def __init__(self):
        self.active_queues: Dict[str, MatchQueue] = {}
        self.queue_cards: Dict[str, int] = {}  # channel_name + bet_value -> message_id
        
    def get_queue_key(self, channel_name: str, bet_value: float, gel_type: str) -> str:
        """Gerar chave única para a fila"""
        return f"{channel_name}_{bet_value}_{gel_type}"
    
    async def get_or_create_queue(
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str,
        max_players: int
    ) -> MatchQueue:
        """Obter ou criar uma fila"""
        queue_key = self.get_queue_key(channel_name, bet_value, gel_type)
        
        # Buscar em memória
        if queue_key in self.active_queues:
            return self.active_queues[queue_key]
        
        # Buscar no banco
        collection = db.get_collection('match_queues')
        queue_data = await collection.find_one({
            "channel_name": channel_name,
            "bet_value": bet_value,
            "gel_type": gel_type,
            "status": "waiting"
        })
        
        if queue_data:
            queue = MatchQueue.from_dict(queue_data)
        else:
            queue = MatchQueue(
                channel_name=channel_name,
                bet_value=bet_value,
                gel_type=gel_type,
                max_players=max_players
            )
            await collection.insert_one(queue.to_dict())
        
        self.active_queues[queue_key] = queue
        return queue
    
    async def add_player_to_queue(
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str,
        max_players: int,
        player_id: int
    ) -> tuple[bool, MatchQueue, str]:
        """
        Adicionar jogador à fila
        Returns: (sucesso, queue, mensagem)
        """
        queue = await self.get_or_create_queue(channel_name, bet_value, gel_type, max_players)
        
        # Verificar se já está na fila
        if player_id in queue.players:
            return False, queue, "Você já está nesta fila!"
        
        # Adicionar jogador
        if queue.add_player(player_id):
            await self._save_queue(queue)
            
            # Verificar se a fila encheu
            if queue.is_full():
                return True, queue, "full"
            
            return True, queue, f"Você entrou na fila! ({len(queue.players)}/{queue.max_players})"
        
        return False, queue, "Fila cheia!"
    
    async def remove_player_from_queue(
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str,
        player_id: int
    ) -> tuple[bool, Optional[MatchQueue]]:
        """Remover jogador da fila"""
        queue_key = self.get_queue_key(channel_name, bet_value, gel_type)
        
        if queue_key not in self.active_queues:
            return False, None
        
        queue = self.active_queues[queue_key]
        
        if queue.remove_player(player_id):
            await self._save_queue(queue)
            return True, queue
        
        return False, None
    
    async def start_confirmation_timer(
        self,
        queue: MatchQueue,
        bot: discord.Client,
        channel: discord.TextChannel
    ):
        """Iniciar timer de confirmação quando a fila encher"""
        queue.status = "confirming"
        queue.expires_at = datetime.utcnow() + timedelta(minutes=1)
        await self._save_queue(queue)
        
        # Criar embed de confirmação
        embed = discord.Embed(
            title="⏰ PARTIDA ENCONTRADA!",
            description=f"**R$ {queue.bet_value:.2f}** - {queue.channel_name.upper()} - {queue.gel_type.upper()}",
            color=discord.Color.orange()
        )
        
        players_text = "\n".join([
            f"• <@{player_id}> ⏳" for player_id in queue.players
        ])
        
        embed.add_field(
            name="Jogadores",
            value=players_text,
            inline=False
        )
        
        embed.add_field(
            name="⏰ Confirme em 60 segundos!",
            value="Clique em ✅ para aceitar",
            inline=False
        )
        
        # Criar view com botões
        view = ConfirmationView(queue, self, bot)
        
        # Mencionar todos os jogadores
        mentions = " ".join([f"<@{player_id}>" for player_id in queue.players])
        message = await channel.send(content=mentions, embed=embed, view=view)
        
        queue.confirmation_message_id = message.id
        await self._save_queue(queue)
        
        # Iniciar contagem regressiva
        asyncio.create_task(self._confirmation_countdown(queue, bot, channel, message, view))
    
    async def _confirmation_countdown(
        self,
        queue: MatchQueue,
        bot: discord.Client,
        channel: discord.TextChannel,
        message: discord.Message,
        view: discord.ui.View
    ):
        """Contagem regressiva para confirmação"""
        for remaining in range(60, 0, -5):
            await asyncio.sleep(5)
            
            # Recarregar queue do banco
            collection = db.get_collection('match_queues')
            queue_data = await collection.find_one({"_id": queue._id})
            if not queue_data:
                return
            
            queue = MatchQueue.from_dict(queue_data)
            
            # Verificar se todos confirmaram
            if queue.all_confirmed():
                await self._create_match_from_queue(queue, bot, channel)
                return
            
            # Atualizar embed com tempo restante
            embed = message.embeds[0]
            
            # Atualizar status dos jogadores
            players_text = "\n".join([
                f"• <@{player_id}> {'✅' if player_id in queue.confirmations else '⏳'}"
                for player_id in queue.players
            ])
            
            embed.set_field_at(0, name="Jogadores", value=players_text, inline=False)
            embed.set_field_at(
                1,
                name=f"⏰ Tempo restante: {remaining}s",
                value="Clique em ✅ para aceitar",
                inline=False
            )
            
            try:
                await message.edit(embed=embed, view=view)
            except:
                pass
        
        # Tempo esgotado
        await self._expire_queue(queue, bot, channel, message)
    
    async def add_confirmation(
        self,
        queue: MatchQueue,
        player_id: int,
        bot: discord.Client,
        channel: discord.TextChannel
    ) -> bool:
        """Adicionar confirmação de jogador"""
        if queue.add_confirmation(player_id):
            await self._save_queue(queue)
            
            # Verificar se todos confirmaram
            if queue.all_confirmed():
                await self._create_match_from_queue(queue, bot, channel)
            
            return True
        
        return False
    
    async def _create_match_from_queue(
        self,
        queue: MatchQueue,
        bot: discord.Client,
        channel: discord.TextChannel
    ):
        """Criar partida a partir da fila confirmada"""
        try:
            # Obter mediador
            mediator = await mediator_queue.get_next_mediator()
            
            if not mediator:
                await channel.send("❌ Não há mediadores disponíveis no momento.")
                await self._expire_queue(queue, bot, channel, None)
                return
            
            # Criar partida
            guild = channel.guild
            match_data = await match_service.create_match(
                guild_id=guild.id,
                channel_id=channel.id,
                player_ids=queue.players,
                mediator_id=mediator.discord_id,
                bet_value=queue.bet_value,
                gel_type=queue.gel_type,
                match_type=queue.channel_name
            )
            
            # Criar tópico
            thread_name = f"Partida R$ {queue.bet_value:.2f} - {queue.gel_type.capitalize()}"
            thread = await channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.public_thread
            )
            
            # Adicionar jogadores e mediador ao tópico
            for player_id in queue.players:
                member = guild.get_member(player_id)
                if member:
                    await thread.add_user(member)
            
            mediator_member = guild.get_member(mediator.discord_id)
            if mediator_member:
                await thread.add_user(mediator_member)
            
            # Mensagem inicial no tópico
            embed = discord.Embed(
                title="🎮 Partida Iniciada!",
                description=f"**Modo:** {queue.channel_name}\n**Valor:** R$ {queue.bet_value:.2f}\n**GEL:** {queue.gel_type.capitalize()}",
                color=discord.Color.green()
            )
            
            players_text = "\n".join([f"• <@{player_id}>" for player_id in queue.players])
            embed.add_field(name="Jogadores", value=players_text, inline=False)
            embed.add_field(name="Mediador", value=f"<@{mediator.discord_id}>", inline=False)
            
            await thread.send(embed=embed)
            
            # Remover fila
            await self._delete_queue(queue)
            
            # Deletar mensagem de confirmação
            if queue.confirmation_message_id:
                try:
                    msg = await channel.fetch_message(queue.confirmation_message_id)
                    await msg.delete()
                except:
                    pass
            
            logger.info(f"Partida criada a partir da fila: {queue.channel_name} R$ {queue.bet_value}")
            
        except Exception as e:
            logger.error(f"Erro ao criar partida da fila: {e}")
            await channel.send(f"❌ Erro ao criar partida: {e}")
    
    async def _expire_queue(
        self,
        queue: MatchQueue,
        bot: discord.Client,
        channel: discord.TextChannel,
        message: Optional[discord.Message]
    ):
        """Expirar fila quando o tempo acaba"""
        queue.status = "expired"
        await self._save_queue(queue)
        
        # Encontrar quem não confirmou
        not_confirmed = [p for p in queue.players if p not in queue.confirmations]
        
        # Mensagem de expiração
        embed = discord.Embed(
            title="❌ Tempo Esgotado",
            description="A partida foi cancelada porque nem todos confirmaram.",
            color=discord.Color.red()
        )
        
        if not_confirmed:
            not_confirmed_text = "\n".join([f"• <@{player_id}>" for player_id in not_confirmed])
            embed.add_field(
                name="Não confirmaram",
                value=not_confirmed_text,
                inline=False
            )
        
        if message:
            await message.edit(embed=embed, view=None)
        else:
            await channel.send(embed=embed)
        
        # Remover fila
        await self._delete_queue(queue)
    
    async def get_queue_status(
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str
    ) -> Optional[MatchQueue]:
        """Obter status de uma fila"""
        queue_key = self.get_queue_key(channel_name, bet_value, gel_type)
        return self.active_queues.get(queue_key)
    
    async def _save_queue(self, queue: MatchQueue):
        """Salvar fila no banco"""
        collection = db.get_collection('match_queues')
        await collection.replace_one(
            {"_id": queue._id},
            queue.to_dict(),
            upsert=True
        )
    
    async def _delete_queue(self, queue: MatchQueue):
        """Deletar fila do banco e memória"""
        collection = db.get_collection('match_queues')
        await collection.delete_one({"_id": queue._id})
        
        queue_key = self.get_queue_key(queue.channel_name, queue.bet_value, queue.gel_type)
        if queue_key in self.active_queues:
            del self.active_queues[queue_key]


# View para confirmação
class ConfirmationView(discord.ui.View):
    def __init__(self, queue: MatchQueue, service: MatchQueueService, bot: discord.Client):
        super().__init__(timeout=None)
        self.queue = queue
        self.service = service
        self.bot = bot
    
    @discord.ui.button(label="✅ ACEITAR", style=discord.ButtonStyle.green, custom_id="confirm_match")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.queue.players:
            await interaction.response.send_message("❌ Você não está nesta partida!", ephemeral=True)
            return
        
        if interaction.user.id in self.queue.confirmations:
            await interaction.response.send_message("✅ Você já confirmou!", ephemeral=True)
            return
        
        await self.service.add_confirmation(
            self.queue,
            interaction.user.id,
            self.bot,
            interaction.channel
        )
        
        await interaction.response.send_message("✅ Confirmado!", ephemeral=True)
    
    @discord.ui.button(label="❌ RECUSAR", style=discord.ButtonStyle.red, custom_id="decline_match")
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.queue.players:
            await interaction.response.send_message("❌ Você não está nesta partida!", ephemeral=True)
            return
        
        await self.service.remove_player_from_queue(
            self.queue.channel_name,
            self.queue.bet_value,
            self.queue.gel_type,
            interaction.user.id
        )
        
        await interaction.response.send_message("❌ Você saiu da fila.", ephemeral=True)
        
        # Cancelar a partida
        await self.service._expire_queue(self.queue, self.bot, interaction.channel, None)


# Instância global
match_queue_service = MatchQueueService()
