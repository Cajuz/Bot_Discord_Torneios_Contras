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
        
        self.children[0].custom_id = f"gel_normal_{channel_name}_{bet_value}"
        self.children[1].custom_id = f"gel_infinito_{channel_name}_{bet_value}"
        self.children[2].custom_id = f"sair_fila_{channel_name}_{bet_value}"
    
    @discord.ui.button(
        label="🔥 GEL NORMAL",
        style=discord.ButtonStyle.green,
        custom_id="gel_normal"
    )
    async def gel_normal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_queue_join(interaction, "normal")
    
    @discord.ui.button(
        label="♾️ GEL INFINITO",
        style=discord.ButtonStyle.blurple,
        custom_id="gel_infinito"
    )
    async def gel_infinito_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_queue_join(interaction, "infinito")
    
    @discord.ui.button(
        label="🚪 SAIR DA FILA",
        style=discord.ButtonStyle.red,
        custom_id="sair_fila"
    )
    async def leave_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            removed_normal, queue_normal = await match_queue_service.remove_player_from_queue(
                self.channel_name, self.bet_value, "normal", interaction.user.id
            )
            removed_infinito, queue_infinito = await match_queue_service.remove_player_from_queue(
                self.channel_name, self.bet_value, "infinito", interaction.user.id
            )
            
            if removed_normal or removed_infinito:
                await interaction.response.send_message("✅ Você saiu da fila!", ephemeral=True)
                
                if removed_normal and queue_normal:
                    await self._update_queue_card(interaction, "normal", queue_normal)
                if removed_infinito and queue_infinito:
                    await self._update_queue_card(interaction, "infinito", queue_infinito)
            else:
                await interaction.response.send_message(
                    "❌ Você não está em nenhuma fila deste valor.", ephemeral=True
                )
        except Exception as e:
            logger.error(f"Erro ao sair da fila: {e}")
            await interaction.response.send_message(
                "❌ Erro ao sair da fila. Tente novamente.", ephemeral=True
            )
    
    async def _handle_queue_join(self, interaction: discord.Interaction, gel_type: str):
        """Processar entrada na fila"""
        try:
            # ✏️ Verificar se jogador já está em outra fila do mesmo canal/valor
            other_gel = "infinito" if gel_type == "normal" else "normal"
            other_queue = await match_queue_service.get_queue_status(
                self.channel_name, self.bet_value, other_gel
            )
            if other_queue and interaction.user.id in other_queue.players:
                await interaction.response.send_message(
                    f"⚠️ Você já está na fila de **GEL {other_gel.upper()}** para este valor. "
                    f"Saia dela primeiro.",
                    ephemeral=True
                )
                return

            success, queue, message = await match_queue_service.add_player_to_queue(
                self.channel_name,
                self.bet_value,
                gel_type,
                self.max_players,
                interaction.user.id
            )
            
            if success:
                if message == "full":
                    # ✏️ Responde primeiro, depois inicia o timer (evita timeout do interaction)
                    await interaction.response.send_message(
                        "⚡ Fila completa! Confirmem a partida na mensagem acima.",
                        ephemeral=True
                    )
                    await match_queue_service.start_confirmation_timer(
                        queue,
                        interaction.client,
                        interaction.channel
                    )
                else:
                    await interaction.response.send_message(f"✅ {message}", ephemeral=True)
                
                await self._update_queue_card(interaction, gel_type, queue)
            else:
                await interaction.response.send_message(f"❌ {message}", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Erro ao entrar na fila: {e}")
            await interaction.response.send_message(
                "❌ Erro ao entrar na fila. Tente novamente.", ephemeral=True
            )
    
    async def _update_queue_card(self, interaction: discord.Interaction, gel_type: str, queue):
        """✏️ Atualizar o embed do card com contagem real das duas filas"""
        try:
            queue_normal = await match_queue_service.get_queue_status(
                self.channel_name, self.bet_value, "normal"
            )
            queue_infinito = await match_queue_service.get_queue_status(
                self.channel_name, self.bet_value, "infinito"
            )

            normal_count   = len(queue_normal.players)   if queue_normal   else 0
            infinito_count = len(queue_infinito.players) if queue_infinito else 0

            embed = create_match_queue_embed(
                channel_name=self.channel_name,
                bet_value=self.bet_value,
                max_players=self.max_players,
                queue_normal_count=normal_count,
                queue_infinito_count=infinito_count
            )

            # ✏️ Edita a mensagem original do card (não envia nova mensagem)
            try:
                await interaction.message.edit(embed=embed, view=self)
            except discord.NotFound:
                pass
            except Exception as e:
                logger.warning(f"Não foi possível atualizar card: {e}")

            logger.info(
                f"Card atualizado: {self.channel_name} R$ {self.bet_value} "
                f"| Normal: {normal_count}/{self.max_players} "
                f"| Infinito: {infinito_count}/{self.max_players}"
            )

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

    channel_display = channel_name.upper()
    if "mob" in channel_name:
        channel_display = channel_name.replace("mob", "Mobile")
    elif "emu" in channel_name:
        channel_display = channel_name.replace("emu", "Emulador")
    elif "misto" in channel_name:
        channel_display = channel_name.replace("misto", "Misto")

    # ✏️ Barra de progresso visual para cada fila
    def progress_bar(current: int, total: int) -> str:
        filled = int((current / total) * 5) if total > 0 else 0
        return "🟩" * filled + "⬜" * (5 - filled)

    embed = discord.Embed(
        title=f"💰 R$ {bet_value:.2f}",
        description=f"**Modo:** {channel_display}\n**Jogadores necessários:** {max_players}",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="🔥 GEL NORMAL",
        value=(
            f"Na fila: **{queue_normal_count}/{max_players}**\n"
            f"{progress_bar(queue_normal_count, max_players)}"  # ✏️
        ),
        inline=True
    )

    embed.add_field(
        name="♾️ GEL INFINITO",
        value=(
            f"Na fila: **{queue_infinito_count}/{max_players}**\n"
            f"{progress_bar(queue_infinito_count, max_players)}"  # ✏️
        ),
        inline=True
    )

    embed.set_footer(text="Clique no modo desejado para entrar na fila")

    return embed
