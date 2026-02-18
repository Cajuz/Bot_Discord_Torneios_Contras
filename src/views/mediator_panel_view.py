import discord
from discord.ui import View, Button

from services.mediator_queue import mediator_queue
from utils.logger import logger


def create_mediator_panel_embed(info: dict | None = None) -> discord.Embed:
    """
    Criar embed do painel de mediadores (compatível com código antigo).
    info pode ser o resultado de mediator_queue.get_queue_info().
    """
    # Se não passar info, usa default vazio (evita coroutine aqui)
    total_active = info.get("total_active", 0) if info else 0
    in_queue = info.get("in_queue", 0) if info else 0

    embed = discord.Embed(
        title="👨‍⚖️ Painel de Mediadores",
        description="Gerencie sua presença na fila de mediação",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="📊 Status Atual",
        value=(
            f"**Mediadores Ativos:** {total_active}\n"
            f"**Na Fila:** {in_queue}"
        ),
        inline=False
    )

    embed.add_field(
        name="ℹ️ Como Funciona",
        value=(
            "• Clique em **✅ Entrar na Fila** para começar a mediar\n"
            "• Clique em **❌ Sair da Fila** para parar de mediar\n"
            "• Clique em **📊 Ver Fila Completa** para ver todos os mediadores\n"
            "• Apenas membros com cargo **Controller** podem mediar"
        ),
        inline=False
    )

    return embed


class MediatorPanelView(View):
    """View do painel de mediadores"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="✅ Entrar na Fila",
        style=discord.ButtonStyle.green,
        custom_id="mediator_join_queue"
    )
    async def join_queue_button(
        self,
        interaction: discord.Interaction,
        button: Button
    ):
        """Botão para entrar na fila"""
        user_id = interaction.user.id
        
        # Verificar se tem o cargo Controller
        role = discord.utils.get(interaction.guild.roles, name="Controller")
        if not role or role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ Você precisa do cargo **Controller** para entrar na fila de mediadores!",
                ephemeral=True
            )
            return
        
        # Verificar se já está cadastrado
        from config.database import db
        collection = db.get_collection('mediators')
        mediator = await collection.find_one({'user_id': user_id})
        
        # Se não está cadastrado, cadastrar automaticamente
        if not mediator:
            await mediator_queue.register_mediator(
                user_id=user_id,
                username=interaction.user.name,
                guild_id=interaction.guild.id
            )
        
        # Adicionar à fila
        success = await mediator_queue.add_to_queue(user_id)
        
        if success:
            position = await mediator_queue.get_mediator_position(user_id)
            await interaction.response.send_message(
                f"✅ Você entrou na fila de mediadores!\n📊 Sua posição: **{position}º**",
                ephemeral=True
            )
            
            # Atualizar painel
            await self.update_panel(interaction)
        else:
            await interaction.response.send_message(
                "⚠️ Você já está na fila de mediadores!",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="❌ Sair da Fila",
        style=discord.ButtonStyle.red,
        custom_id="mediator_leave_queue"
    )
    async def leave_queue_button(
        self,
        interaction: discord.Interaction,
        button: Button
    ):
        """Botão para sair da fila"""
        user_id = interaction.user.id
        
        success = await mediator_queue.remove_from_queue(user_id)
        
        if success:
            await interaction.response.send_message(
                "✅ Você saiu da fila de mediadores!",
                ephemeral=True
            )
            
            # Atualizar painel
            await self.update_panel(interaction)
        else:
            await interaction.response.send_message(
                "⚠️ Você não está na fila de mediadores!",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="📊 Ver Fila Completa",
        style=discord.ButtonStyle.blurple,
        custom_id="mediator_view_queue"
    )
    async def view_queue_button(
        self,
        interaction: discord.Interaction,
        button: Button
    ):
        """Botão para ver a fila completa"""
        info = await mediator_queue.get_queue_info()
        
        embed = discord.Embed(
            title="📊 Fila de Mediadores",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Estatísticas",
            value=(
                f"**Total Ativos:** {info['total_active']}\n"
                f"**Na Fila:** {info['in_queue']}"
            ),
            inline=False
        )
        
        # Listar mediadores na fila
        if info['queue']:
            queue_list = []
            for i, user_id in enumerate(info['queue'][:10], 1):  # Primeiros 10
                queue_list.append(f"{i}º - <@{user_id}>")
            
            embed.add_field(
                name="📋 Fila Atual",
                value="\n".join(queue_list) if queue_list else "Nenhum mediador na fila",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def update_panel(self, interaction: discord.Interaction):
        """Atualizar painel principal"""
        info = await mediator_queue.get_queue_info()
        
        embed = discord.Embed(
            title="👨‍⚖️ Painel de Mediadores",
            description="Gerencie sua presença na fila de mediação",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="📊 Status Atual",
            value=(
                f"**Mediadores Ativos:** {info['total_active']}\n"
                f"**Na Fila:** {info['in_queue']}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Como Funciona",
            value=(
                "• Clique em **✅ Entrar na Fila** para começar a mediar\n"
                "• Clique em **❌ Sair da Fila** para parar de mediar\n"
                "• Clique em **📊 Ver Fila Completa** para ver todos os mediadores\n"
                "• Apenas membros com cargo **Controller** podem mediar"
            ),
            inline=False
        )
        
        try:
            await interaction.message.edit(embed=embed)
        except:
            pass
