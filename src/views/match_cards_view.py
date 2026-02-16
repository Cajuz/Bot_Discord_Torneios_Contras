import discord
from discord.ui import View, Button, Select
from typing import Optional, List, Dict, Any
from datetime import datetime
from config.channels_config import ChannelsConfig

from utils.logger import logger

class MatchCardView(View):
    """View com cards de partidas para cada valor"""
    
    def __init__(self, channel_service, channel_name: str):
        super().__init__(timeout=None)  # Persistente
        self.channel_service = channel_service
        self.channel_name = channel_name
        self.channel_info = ChannelsConfig.get_channel_info(channel_name)
        
        # Adicionar botões para cada valor
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
        """Definir estilo do botão baseado no valor"""
        if value <= 10:
            return discord.ButtonStyle.secondary
        elif value <= 50:
            return discord.ButtonStyle.primary
        elif value <= 100:
            return discord.ButtonStyle.success
        else:
            return discord.ButtonStyle.danger
    
    def _create_callback(self, bet_value: int):
        """Criar callback para cada botão"""
        async def callback(interaction: discord.Interaction):
            await self._handle_match_creation(interaction, bet_value)
        return callback
    
    async def _handle_match_creation(self, interaction: discord.Interaction, bet_value: int):
        """Processar criação de partida"""
        try:
            user = interaction.user
            
            # Criar modal para coletar informações adicionais (se necessário)
            # Por enquanto, criar partida diretamente
            
            await interaction.response.defer(ephemeral=True)
            
            # Criar partida e tópico
            result = await self.channel_service.create_match_with_thread(
                channel_name=self.channel_name,
                bet_value=bet_value,
                creator=user,
                channel=interaction.channel
            )
            
            if result['success']:
                thread = result['thread']
                match_id = result['match_id']
                
                embed = discord.Embed(
                    title="✅ Partida Criada!",
                    description=(
                        f"Sua partida foi criada com sucesso!\n\n"
                        f"**Valor:** R$ {bet_value},00\n"
                        f"**Canal:** {self.channel_name}\n"
                        f"**Tópico:** {thread.mention}\n"
                        f"**ID:** `{match_id}`"
                    ),
                    color=discord.Color.green()
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Erro ao criar partida: {result.get('error', 'Erro desconhecido')}",
                    ephemeral=True
                )
        
        except Exception as e:
            logger.error(f"Erro ao criar partida: {e}")
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
        
        # Emoji baseado na plataforma
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
                f"2️⃣ Um tópico será criado automaticamente\n"
                f"3️⃣ Um mediador será atribuído à sua partida\n"
                f"4️⃣ Aguarde os outros jogadores entrarem\n"
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
        
        embed.set_footer(text="Selecione um valor abaixo para começar")
        embed.timestamp = datetime.now()
        
        return embed
    
    @staticmethod
    def create_thread_welcome(
        match_id: str,
        bet_value: int,
        channel_name: str,
        mediator_name: str,
        mediator_id: str,
        creator: discord.Member
    ) -> discord.Embed:
        """Criar embed de boas-vindas do tópico"""
        
        embed = discord.Embed(
            title="🎮 Informações da Partida",
            description=f"Partida criada por {creator.mention}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="💰 Valor da Aposta",
            value=f"**R$ {bet_value},00**",
            inline=True
        )
        
        embed.add_field(
            name="📺 Canal",
            value=f"`{channel_name}`",
            inline=True
        )
        
        embed.add_field(
            name="🎯 ID da Partida",
            value=f"`{match_id}`",
            inline=True
        )
        
        embed.add_field(
            name="👨‍⚖️ Mediador",
            value=f"<@{mediator_id}> ({mediator_name})",
            inline=False
        )
        
        embed.add_field(
            name="📊 Status",
            value="🟡 **Aguardando Jogadores**",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Instruções",
            value=(
                "• Use este tópico para se comunicar\n"
                "• O mediador irá coordenar a partida\n"
                "• Aguarde todos os jogadores confirmarem\n"
                "• Boa sorte! 🍀"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"Criada em")
        embed.timestamp = datetime.now()
        
        return embed
