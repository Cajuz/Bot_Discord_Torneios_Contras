import discord
from discord.ui import View, Button
from typing import Optional
from config.rules import ServerRules
from utils.logger import logger


class RulesView(View):
    """View com botões de aceitar/recusar — enviada na DM após entrar no servidor"""

    def __init__(self, onboarding_service, member: discord.Member, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.onboarding_service = onboarding_service
        self.member             = member
        self.message: Optional[discord.Message] = None

    @discord.ui.button(
        label="✅ Aceito as Regras",
        style=discord.ButtonStyle.success,
        custom_id="accept_rules"
    )
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Apenas o novo membro pode aceitar as regras!", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            success = await self.onboarding_service.accept_rules(self.member)

            if success:
                for item in self.children:
                    item.disabled = True
                if self.message:
                    await self.message.edit(view=self)

                welcome_embed = ServerRules.get_welcome_embed(self.member)
                await interaction.followup.send(embed=welcome_embed)
                logger.info(f"Usuário {self.member.name} aceitou as regras via DM")
            else:
                await interaction.followup.send(
                    "❌ Erro ao processar aceitação. Contate um administrador.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Erro ao aceitar regras: {e}")
            await interaction.followup.send(
                "❌ Ocorreu um erro. Tente novamente mais tarde.", ephemeral=True
            )

    @discord.ui.button(
        label="❌ Não Aceito",
        style=discord.ButtonStyle.danger,
        custom_id="decline_rules"
    )
    async def decline_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Esta ação não é para você!", ephemeral=True
            )
            return

        await interaction.response.defer()

        confirmation_view = ConfirmationView(self.onboarding_service, self.member, self)
        msg = await interaction.followup.send(
            embed=ServerRules.get_confirmation_embed(),
            view=confirmation_view,
            ephemeral=True
        )
        confirmation_view.message = msg

    async def on_timeout(self):
        """Tempo esgotado — kicca com result='timeout'"""
        try:
            for item in self.children:
                item.disabled = True
            if self.message:
                try:
                    timeout_embed = discord.Embed(
                        title="⏰ Tempo Esgotado",
                        description=(
                            "Você não aceitou as regras dentro de **5 minutos**.\n"
                            "Você foi removido do servidor automaticamente."
                        ),
                        color=discord.Color.red()
                    )
                    await self.message.edit(embed=timeout_embed, view=self)
                except Exception:
                    pass

            await self.onboarding_service.kick_member(
                self.member,
                reason="Não aceitou as regras dentro do tempo limite (5 min)",
                result='timeout'  # ✅ grava 'timeout' no banco
            )
            logger.warning(f"Usuário {self.member.name} removido por timeout nas regras")
        except Exception as e:
            logger.error(f"Erro no timeout das regras: {e}")


class ConfirmationView(View):
    """View de confirmação quando o membro clica em Não Aceito"""

    def __init__(
        self,
        onboarding_service,
        member: discord.Member,
        parent_view: RulesView,
        timeout: float = 60
    ):
        super().__init__(timeout=timeout)
        self.onboarding_service = onboarding_service
        self.member      = member
        self.parent_view = parent_view
        self.message: Optional[discord.Message] = None

    @discord.ui.button(
        label="📜 Voltar às Regras",
        style=discord.ButtonStyle.primary,
        custom_id="back_to_rules"
    )
    async def back_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Esta ação não é para você!", ephemeral=True
            )
            return

        await interaction.response.defer()

        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

        for item in self.parent_view.children:
            item.disabled = False
        if self.parent_view.message:
            await self.parent_view.message.edit(view=self.parent_view)

        await interaction.followup.send(
            "✅ Voltou para as regras. Leia novamente e decida!", ephemeral=True
        )

    @discord.ui.button(
        label="🚪 Sair do Servidor",
        style=discord.ButtonStyle.danger,
        custom_id="leave_server"
    )
    async def leave_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Esta ação não é para você!", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            await interaction.followup.send(
                "👋 Você foi removido. Esperamos vê-lo novamente no futuro!",
                ephemeral=True
            )
        except Exception:
            pass

        await self.onboarding_service.kick_member(
            self.member,
            reason="Recusou as regras do servidor",
            result='recusado'  # ✅ grava 'recusado' no banco
        )
        logger.info(f"Usuário {self.member.name} recusou as regras e foi removido")

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass
