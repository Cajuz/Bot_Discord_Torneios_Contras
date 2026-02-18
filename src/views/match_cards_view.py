import discord
from discord.ui import View, Button, Select
from typing import Optional, List, Dict, Any
from datetime import datetime
from config.channels_config import ChannelsConfig

from utils.logger import logger


class MatchCardView(View):
    """View com cards de partidas para cada valor"""
    
    def __init__(self, channel_service, channel_name: str):
        super().__init__(timeout=None)
        self.channel_service = channel_service
        self.channel_name = channel_name
        self.channel_info = ChannelsConfig.get_channel_info(channel_name)
        
        for value in ChannelsConfig.BET_VALUES:
            button = Button(
                label=f"R$ {value},00",
                style=self._get_button_style(value),
                custom_id=f"match_{channel_name}_{value}",
                emoji="💰"
            )
            button.callback = self._create_callback(value)
            self.add_item(button)
    
    def _get_button_style(self, value: int) -> discord.ButtonStyle:
        if value <= 10:
            return discord.ButtonStyle.secondary
        elif value <= 50:
            return discord.ButtonStyle.primary
        elif value <= 100:
            return discord.ButtonStyle.success
        else:
            return discord.ButtonStyle.danger
    
    def _create_callback(self, bet_value: int):
        async def callback(interaction: discord.Interaction):
            await self._handle_join_queue(interaction, bet_value)  # ✏️ renomeado
        return callback
    
    async def _handle_join_queue(self, interaction: discord.Interaction, bet_value: int):
        """
        ✏️ Antes criava a partida direto, agora adiciona o jogador à fila.
        A thread só é criada quando a fila encher e todos confirmarem.
        """
        try:
            from services.match_queue_service import match_queue_service

            user = interaction.user
            await interaction.response.defer(ephemeral=True)

            channel_info = self.channel_info
            max_players = channel_info.get('max_players', 2)  # ✏️ respeita o max da config
            gel_type = channel_info.get('gel_type', 'normal')

            success, queue, message = await match_queue_service.add_player_to_queue(
                channel_name=self.channel_name,
                bet_value=float(bet_value),
                gel_type=gel_type,
                max_players=max_players,
                player_id=user.id
            )

            if not success:
                await interaction.followup.send(
                    f"⚠️ {message}",
                    ephemeral=True
                )
                return

            if message == "full":
                # Fila cheia → inicia timer de confirmação (ainda no canal, não na thread)
                await match_queue_service.start_confirmation_timer(
                    queue=queue,
                    bot=interaction.client,
                    channel=interaction.channel
                )
                await interaction.followup.send(
                    "⚡ Fila completa! Confirme a partida na mensagem acima.",
                    ephemeral=True
                )
            else:
                # Ainda aguardando jogadores
                await interaction.followup.send(
                    f"✅ {message}",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Erro ao entrar na fila: {e}")
            try:
                await interaction.followup.send(
                    f"❌ Erro ao processar solicitação: {str(e)}",
                    ephemeral=True
                )
            except:
                pass


class MatchInfoEmbed:
    """Criador de embeds para informações de partidas"""

    @staticmethod
    def create_welcome_card(channel_name: str, channel_info: Dict) -> discord.Embed:
        """Criar card de boas-vindas do canal"""
        match_type = channel_info['type'].value
        platform = channel_info['platform'].value

        platform_emoji = {
            "mob": "📱",
            "emu": "🖥️",
            "misto": "🔀"
        }.get(platform, "🎮")

        embed = discord.Embed(
            title=f"{platform_emoji} {channel_name.upper()}",
            description=(
                f"**Bem-vindo ao canal de partidas {match_type}!**\n\n"
                f"Aqui você pode criar partidas para o modo **{match_type}** "
                f"na plataforma **{platform.upper()}**.\n\n"
                f"**Como funciona:**\n"
                f"1️⃣ Escolha o valor da aposta clicando em um dos botões abaixo\n"
                f"2️⃣ Aguarde outro jogador entrar na mesma fila\n"       # ✏️
                f"3️⃣ Confirme a partida quando solicitado\n"             # ✏️
                f"4️⃣ Um tópico será criado com o mediador atribuído\n"  # ✏️
                f"5️⃣ Boa sorte! 🍀\n\n"
                f"**Valores disponíveis:** R$ 2 a R$ 200"
            ),
            color=discord.Color.gold()
        )

        embed.add_field(
            name="📋 Regras",
            value=(
                "• Respeite os mediadores\n"
                "• Não abandone partidas iniciadas\n"
                "• Jogue de forma honesta\n"
                "• Use o tópico para comunicação"
            ),
            inline=False
        )

        embed.set_footer(text="Selecione um valor abaixo para entrar na fila")  # ✏️
        embed.timestamp = datetime.now()

        return embed

    @staticmethod
    def create_thread_welcome(
        match_id: str,
        bet_value: int,
        channel_name: str,
        mediator_id: int,           # ✏️ era str, agora int (consistente com o resto)
        time_blue: List[int],       # ✏️ novo parâmetro
        time_red: List[int],        # ✏️ novo parâmetro
        player_ids: List[int]       # ✏️ novo parâmetro (lista completa)
    ) -> discord.Embed:
        """
        ✏️ Atualizado para mostrar times e não depender mais de um único criador.
        O mediator_member é mencionado via ID diretamente.
        """

        blue_str = "\n".join(f"• <@{uid}>" for uid in time_blue) or "—"
        red_str  = "\n".join(f"• <@{uid}>" for uid in time_red)  or "—"

        embed = discord.Embed(
            title="⚔️ Partida Criada!",
            description=f"**Modo:** `{channel_name}` | **Valor:** R$ {bet_value},00",
            color=discord.Color.gold()
        )

        embed.add_field(name="🔵 Time Blue", value=blue_str, inline=True)
        embed.add_field(name="🔴 Time Red",  value=red_str,  inline=True)

        embed.add_field(
            name="👨‍⚖️ Mediador",
            value=f"<@{mediator_id}>",
            inline=False
        )

        embed.add_field(
            name="📊 Status",
            value="💰 **Aguardando Pagamento**",   # ✏️ status inicial correto
            inline=False
        )

        embed.add_field(
            name="🎯 ID da Partida",
            value=f"`{match_id}`",
            inline=True
        )

        embed.add_field(
            name="ℹ️ Instruções",
            value=(
                "• Use este tópico para se comunicar\n"
                "• O mediador irá coordenar a partida\n"
                "• Aguarde o mediador confirmar o pagamento\n"
                "• Boa sorte! 🍀"
            ),
            inline=False
        )

        embed.set_footer(text="Criada em")
        embed.timestamp = datetime.now()

        return embed
