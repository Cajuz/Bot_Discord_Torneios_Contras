import discord
from typing import Optional
from services.mediator_queue import mediator_queue
from utils.logger import logger

class MediatorPanelView(discord.ui.View):
    """View para o painel de controle dos mediadores"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="✅ Entrar na Fila",
        style=discord.ButtonStyle.green,
        custom_id="mediator_join"
    )
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Botão para entrar na fila de mediadores"""
        try:
            success, message = await mediator_queue.add_mediator(interaction.user.id)
            
            if success:
                await interaction.response.send_message(
                    f"✅ {message}",
                    ephemeral=True
                )
                # Atualizar o card
                await self.update_panel_embed(interaction)
            else:
                await interaction.response.send_message(
                    f"❌ {message}",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Erro ao adicionar mediador: {e}")
            await interaction.response.send_message(
                "❌ Erro ao entrar na fila. Tente novamente.",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="❌ Sair da Fila",
        style=discord.ButtonStyle.red,
        custom_id="mediator_leave"
    )
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Botão para sair da fila de mediadores"""
        try:
            success, message = await mediator_queue.remove_mediator(interaction.user.id)
            
            if success:
                await interaction.response.send_message(
                    f"✅ {message}",
                    ephemeral=True
                )
                # Atualizar o card
                await self.update_panel_embed(interaction)
            else:
                await interaction.response.send_message(
                    f"❌ {message}",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Erro ao remover mediador: {e}")
            await interaction.response.send_message(
                "❌ Erro ao sair da fila. Tente novamente.",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="📊 Ver Fila Completa",
        style=discord.ButtonStyle.blurple,
        custom_id="mediator_list"
    )
    async def list_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Botão para ver a fila completa de mediadores"""
        try:
            mediators = await mediator_queue.get_queue()
            
            if not mediators:
                await interaction.response.send_message(
                    "📋 Não há mediadores na fila no momento.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="📊 Fila de Mediadores",
                description=f"Total: {len(mediators)} mediadores",
                color=discord.Color.blurple()
            )
            
            # Mostrar até 10 primeiros
            for i, mediator in enumerate(mediators[:10], 1):
                status = "✅" if mediator.is_active else "⏳"
                embed.add_field(
                    name=f"{i}º - <@{mediator.discord_id}>",
                    value=f"{status} Partidas: {mediator.total_matches}",
                    inline=False
                )
            
            if len(mediators) > 10:
                embed.set_footer(text=f"+ {len(mediators) - 10} mediadores na fila")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Erro ao listar mediadores: {e}")
            await interaction.response.send_message(
                "❌ Erro ao buscar fila. Tente novamente.",
                ephemeral=True
            )
    
    async def update_panel_embed(self, interaction: discord.Interaction):
        """Atualizar o embed do painel com informações atualizadas"""
        try:
            mediators = await mediator_queue.get_queue()
            
            # Verificar posição do usuário
            user_position = None
            for i, mediator in enumerate(mediators, 1):
                if mediator.discord_id == interaction.user.id:
                    user_position = i
                    break
            
            embed = discord.Embed(
                title="👨‍⚖️ PAINEL DE MEDIADORES",
                description="Use os botões abaixo para gerenciar sua presença na fila de mediadores",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📊 Estatísticas",
                value=f"**Mediadores na fila:** {len(mediators)}",
                inline=False
            )
            
            if user_position:
                embed.add_field(
                    name="🎯 Sua Posição",
                    value=f"**{user_position}º** na fila",
                    inline=False
                )
            
            embed.set_footer(text="Sistema de Mediadores Automático")
            
            # Atualizar a mensagem original
            await interaction.message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Erro ao atualizar painel: {e}")


def create_mediator_panel_embed() -> discord.Embed:
    """Criar embed inicial do painel de mediadores"""
    embed = discord.Embed(
        title="👨‍⚖️ PAINEL DE MEDIADORES",
        description="Use os botões abaixo para gerenciar sua presença na fila de mediadores",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="ℹ️ Como funciona",
        value=(
            "• Clique em **✅ Entrar na Fila** para começar a mediar partidas\n"
            "• Você será notificado quando uma partida for criada\n"
            "• Clique em **❌ Sair da Fila** quando não puder mais mediar\n"
            "• Use **📊 Ver Fila Completa** para ver todos os mediadores"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📊 Estatísticas",
        value="**Mediadores na fila:** 0",
        inline=False
    )
    
    embed.set_footer(text="Sistema de Mediadores Automático")
    
    return embed
