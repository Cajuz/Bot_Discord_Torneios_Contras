import discord
from discord.ui import View, Button
from typing import Optional, List, Dict
from datetime import datetime
from config.channels_config import ChannelsConfig
from utils.logger import logger


class MatchCardView(View):
    """
    View postada nos canais de jogo com um botão por valor de aposta.
    Cada canal tem sua própria instância com gel_types corretos.
    """

    def __init__(self, channel_name: str):
        super().__init__(timeout=None)
        self.channel_name = channel_name
        self.channel_info = ChannelsConfig.get_channel_info(channel_name)

        for value in ChannelsConfig.BET_VALUES:
            button = Button(
                label=ChannelsConfig.format_bet_value(value),
                style=self._get_button_style(value),
                custom_id=f"queue_{channel_name}_{value}",
                emoji="💰"
            )
            button.callback = self._create_callback(value)
            self.add_item(button)

    def _get_button_style(self, value: float) -> discord.ButtonStyle:
        if value <= 10:
            return discord.ButtonStyle.secondary
        elif value <= 50:
            return discord.ButtonStyle.primary
        elif value <= 100:
            return discord.ButtonStyle.success
        else:
            return discord.ButtonStyle.danger

    def _create_callback(self, bet_value: float):
        async def callback(interaction: discord.Interaction):
            await self._handle_join_queue(interaction, bet_value)
        return callback

    async def _handle_join_queue(self, interaction: discord.Interaction, bet_value: float):
        """
        Adiciona o jogador à fila do canal/valor/gel correto.
        Quando a fila enche, cria o tópico de confirmação automaticamente.
        """
        try:
            from services.match_queue_service import match_queue_service

            await interaction.response.defer(ephemeral=True)

            # gel_type padrão: normal
            # Canais com gel_infinito (1x1-mob) usam sempre "normal" aqui,
            # o botão de "infinito" vem da MatchQueueView separada
            gel_type    = "normal"
            max_players = 2  # sempre 2 — cada lado tem 1 representante

            success, queue, message = await match_queue_service.add_player_to_queue(
                channel_name=self.channel_name,
                bet_value=float(bet_value),
                gel_type=gel_type,
                max_players=max_players,
                player_id=interaction.user.id
            )

            if not success:
                await interaction.followup.send(f"⚠️ {message}", ephemeral=True)
                return

            if message == "full":
                await match_queue_service.start_confirmation_timer(
                    queue=queue,
                    bot=interaction.client,
                    channel=interaction.channel
                )
                await interaction.followup.send(
                    "⚡ Fila completa! Confirme no tópico que foi criado.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(f"✅ {message}", ephemeral=True)

        except Exception as e:
            logger.error(f"Erro ao entrar na fila [{self.channel_name} R${bet_value}]: {e}")
            try:
                await interaction.followup.send(
                    "❌ Erro ao processar. Tente novamente.", ephemeral=True
                )
            except Exception:
                pass
