import discord
from discord.ui import View, Button
from typing import Optional
from config.rules import ServerRules
from utils.logger import logger

class RulesView(View):
    """View com botões para aceitar/recusar regras"""
    
    def __init__(self, onboarding_service, member: discord.Member, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.onboarding_service = onboarding_service
        self.member = member
        self.message: Optional[discord.Message] = None
    
    @discord.ui.button(label="✅ Aceito as Regras", style=discord.ButtonStyle.success, custom_id="accept_rules")
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        """Callback quando usuário aceita as regras"""
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Apenas o novo membro pode aceitar as regras!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Processar aceitação
            success = await self.onboarding_service.accept_rules(self.member)
            
            if success:
                # Desabilitar botões
                for item in self.children:
                    item.disabled = True
                
                # Atualizar mensagem original
                await self.message.edit(view=self)
                
                # Enviar mensagem de boas-vindas
                welcome_embed = ServerRules.get_welcome_embed(self.member)
                await interaction.followup.send(embed=welcome_embed)
                
                logger.info(f"Usuário {self.member.name} aceitou as regras")
            else:
                await interaction.followup.send(
                    "❌ Erro ao processar aceitação. Contate um administrador.",
                    ephemeral=True
                )
        
        except Exception as e:
            logger.error(f"Erro ao aceitar regras: {e}")
            await interaction.followup.send(
                "❌ Ocorreu um erro. Tente novamente mais tarde.",
                ephemeral=True
            )
    
    @discord.ui.button(label="❌ Não Aceito", style=discord.ButtonStyle.danger, custom_id="decline_rules")
    async def decline_button(self, interaction: discord.Interaction, button: Button):
        """Callback quando usuário recusa as regras"""
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Apenas o novo membro pode interagir com este menu!",
                ephemeral=True
            )
            return
        
        # Mostrar confirmação
        await interaction.response.defer()
        
        confirmation_embed = ServerRules.get_confirmation_embed()
        confirmation_view = ConfirmationView(
            self.onboarding_service,
            self.member,
            self
        )
        
        msg = await interaction.followup.send(
            embed=confirmation_embed,
            view=confirmation_view,
            ephemeral=True
        )
        confirmation_view.message = msg
    
    async def on_timeout(self):
        """Callback quando o tempo expira"""
        try:
            # Desabilitar botões
            for item in self.children:
                item.disabled = True
            
            if self.message:
                await self.message.edit(view=self)
            
            # Kickar usuário por timeout
            await self.onboarding_service.kick_member(
                self.member,
                reason="Não aceitou as regras dentro do tempo limite"
            )
            
            logger.warning(f"Usuário {self.member.name} removido por timeout")
        
        except Exception as e:
            logger.error(f"Erro no timeout: {e}")


class ConfirmationView(View):
    """View de confirmação de recusa"""
    
    def __init__(
        self,
        onboarding_service,
        member: discord.Member,
        parent_view: RulesView,
        timeout: float = 60
    ):
        super().__init__(timeout=timeout)
        self.onboarding_service = onboarding_service
        self.member = member
        self.parent_view = parent_view
        self.message: Optional[discord.Message] = None
    
    @discord.ui.button(label="📜 Voltar às Regras", style=discord.ButtonStyle.primary, custom_id="back_to_rules")
    async def back_button(self, interaction: discord.Interaction, button: Button):
        """Voltar para as regras"""
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Esta ação não é para você!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Desabilitar botões desta view
        for item in self.children:
            item.disabled = True
        
        await self.message.edit(view=self)
        
        # Reabilitar botões da view de regras
        for item in self.parent_view.children:
            item.disabled = False
        
        await self.parent_view.message.edit(view=self.parent_view)
        
        await interaction.followup.send(
            "✅ Você voltou para as regras. Leia novamente e decida!",
            ephemeral=True
        )
    
    @discord.ui.button(label="🚪 Sair do Servidor", style=discord.ButtonStyle.danger, custom_id="leave_server")
    async def leave_button(self, interaction: discord.Interaction, button: Button):
        """Expulsar do servidor"""
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Esta ação não é para você!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Kickar usuário
        await self.onboarding_service.kick_member(
            self.member,
            reason="Recusou as regras do servidor"
        )
        
        try:
            await interaction.followup.send(
                "👋 Você foi removido do servidor. Esperamos vê-lo novamente no futuro!",
                ephemeral=True
            )
        except:
            pass  # Usuário já foi kickado
        
        logger.info(f"Usuário {self.member.name} recusou as regras e foi removido")
    
    async def on_timeout(self):
        """Timeout da confirmação - voltar às regras"""
        try:
            for item in self.children:
                item.disabled = True
            
            if self.message:
                await self.message.edit(view=self)
        except:
            pass
