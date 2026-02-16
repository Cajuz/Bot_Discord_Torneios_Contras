import discord
from typing import Optional
from services.match_queue_service import match_queue_service
from config.channels_config import ChannelsConfig
from utils.logger import logger

class MatchQueueView(discord.ui.View):
    """View para os cards de fila de partida"""
    
    def __init__(self, channel_name: str, bet_value: float, max_players: int):
        super().__init__(timeout=None)
        self.channel_name = channel_name
        self.bet_value = bet_value
        self.max_players = max_players
        
        # Adicionar custom_ids únicos
        self.children[0].custom_id = f"gel_normal_{channel_name}_{bet_value}"
        self.children[1].custom_id = f"gel_infinito_{channel_name}_{bet_value}"
        self.children[2].custom_id = f"sair_fila_{channel_name}_{bet_value}"
    
    @discord.ui.button(
        label="🔥 GEL NORMAL",
        style=discord.ButtonStyle.green,
        custom_id="gel_normal"
    )
    async def gel_normal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Botão para entrar na fila de GEL Normal"""
        await self._handle_queue_join(interaction, "normal")
    
    @discord.ui.button(
        label="♾️ GEL INFINITO",
        style=discord.ButtonStyle.blurple,
        custom_id="gel_infinito"
    )
    async def gel_infinito_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Botão para entrar na fila de GEL Infinito"""
        await self._handle_queue_join(interaction, "infinito")
    
    @discord.ui.button(
        label="🚪 SAIR DA FILA",
        style=discord.ButtonStyle.red,
        custom_id="sair_fila"
    )
    async def leave_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Botão para sair de todas as filas deste valor"""
        try:
            # Tentar remover de ambas as filas
            removed_normal, queue_normal = await match_queue_service.remove_player_from_queue(
                self.channel_name,
                self.bet_value,
                "normal",
                interaction.user.id
            )
            
            removed_infinito, queue_infinito = await match_queue_service.remove_player_from_queue(
                self.channel_name,
                self.bet_value,
                "infinito",
                interaction.user.id
            )
            
            if removed_normal or removed_infinito:
                await interaction.response.send_message(
                    "✅ Você saiu da fila!",
                    ephemeral=True
                )
                
                # Atualizar os cards
                if removed_normal and queue_normal:
                    await self._update_queue_card(interaction, "normal", queue_normal)
                if removed_infinito and queue_infinito:
                    await self._update_queue_card(interaction, "infinito", queue_infinito)
            else:
                await interaction.response.send_message(
                    "❌ Você não está em nenhuma fila deste valor.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Erro ao sair da fila: {e}")
            await interaction.response.send_message(
                "❌ Erro ao sair da fila. Tente novamente.",
                ephemeral=True
            )
    
    async def _handle_queue_join(self, interaction: discord.Interaction, gel_type: str):
        """Processar entrada na fila"""
        try:
            success, queue, message = await match_queue_service.add_player_to_queue(
                self.channel_name,
                self.bet_value,
                gel_type,
                self.max_players,
                interaction.user.id
            )
            
            if success:
                if message == "full":
                    # Fila cheia - iniciar timer de confirmação
                    await interaction.response.send_message(
                        "⏰ Fila completa! Iniciando confirmação...",
                        ephemeral=True
                    )
                    
                    await match_queue_service.start_confirmation_timer(
                        queue,
                        interaction.client,
                        interaction.channel
                    )
                else:
                    # Jogador adicionado com sucesso
                    await interaction.response.send_message(
                        f"✅ {message}",
                        ephemeral=True
                    )
                
                # Atualizar o card
                await self._update_queue_card(interaction, gel_type, queue)
            else:
                await interaction.response.send_message(
                    f"❌ {message}",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Erro ao entrar na fila: {e}")
            await interaction.response.send_message(
                "❌ Erro ao entrar na fila. Tente novamente.",
                ephemeral=True
            )
    
    async def _update_queue_card(
        self,
        interaction: discord.Interaction,
        gel_type: str,
        queue
    ):
        """Atualizar o card da fila com informações atualizadas"""
        try:
            # Buscar todas as mensagens com cards neste canal
            # e atualizar a que corresponde a este valor
            
            # Por enquanto, apenas log
            logger.info(f"Fila atualizada: {self.channel_name} R$ {self.bet_value} - {gel_type}: {len(queue.players)}/{queue.max_players}")
            
        except Exception as e:
            logger.error(f"Erro ao atualizar card: {e}")


def create_match_queue_embed(
    channel_name: str,
    bet_value: float,
    max_players: int,
    queue_normal_count: int = 0,
    queue_infinito_count: int = 0
) -> discord.Embed:
    """Criar embed para card de fila de partida"""
    
    # Mapear nome do canal para nome amigável
    channel_display = channel_name.upper()
    if "mob" in channel_name:
        channel_display = channel_name.replace("mob", "Mobile")
    elif "emu" in channel_name:
        channel_display = channel_name.replace("emu", "Emulador")
    elif "misto" in channel_name:
        channel_display = channel_name.replace("misto", "Misto")
    
    embed = discord.Embed(
        title=f"💰 R$ {bet_value:.2f}",
        description=f"**Modo:** {channel_display}\n**Jogadores necessários:** {max_players}",
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name="🔥 GEL NORMAL",
        value=f"Na fila: **{queue_normal_count}/{max_players}** jogadores",
        inline=True
    )
    
    embed.add_field(
        name="♾️ GEL INFINITO",
        value=f"Na fila: **{queue_infinito_count}/{max_players}** jogadores",
        inline=True
    )
    
    embed.set_footer(text="Clique no botão do modo desejado para entrar na fila")
    
    return embed
