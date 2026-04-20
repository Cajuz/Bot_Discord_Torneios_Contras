import asyncio
import discord
from discord.ui import View, Button
from typing import Optional
from config.rules import ServerRules
from utils.logger import logger


class RulesView(View):
    """
    View com botões de aceitar/recusar — enviada no canal de verificação in-server.
    is_test=True: não kicka no timeout, apenas edita a mensagem.
    """

    def __init__(
        self,
        onboarding_service=None,
        member: discord.Member = None,
        channel: discord.TextChannel = None,
        timeout: float = 300,
        is_test: bool = False,
    ):
        super().__init__(timeout=timeout)
        self.onboarding_service = onboarding_service
        self.member             = member
        self.channel            = channel   # ← canal de verificação para o CAPTCHA
        self.message: Optional[discord.Message] = None
        self.is_test            = is_test
        self._processed         = False

    # ── Aceitar ──────────────────────────────────────────────────

    @discord.ui.button(
        label="✅ Aceito as Regras",
        style=discord.ButtonStyle.success,
        custom_id="accept_rules"
    )
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        if self.member and interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Apenas o novo membro pode aceitar as regras!", ephemeral=True
            )
            return

        if self._processed:
            await interaction.response.send_message("✅ Já processado!", ephemeral=True)
            return

        await interaction.response.defer()

        self._processed = True
        self.stop()

        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

        captcha_notice = discord.Embed(
            title="📋 Regras Aceitas!",
            description=(
                "Ótimo! Para finalizar seu acesso, você precisará passar por uma "
                "**verificação CAPTCHA**.\n\n"
                "⬇️ O CAPTCHA será enviado logo abaixo..."
            ),
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=captcha_notice)

        # Resolve o canal: usa self.channel (preferencial) ou o canal da interação
        target_channel = self.channel or interaction.channel

        asyncio.create_task(
            self.onboarding_service.run_captcha_flow(
                self.member or interaction.user,
                target_channel,
                is_test=self.is_test,
            )
        )
        member_name = self.member.name if self.member else str(interaction.user)
        logger.info(f"[Onboarding] {member_name} aceitou as regras — CAPTCHA iniciado")

    # ── Recusar ──────────────────────────────────────────────────

    @discord.ui.button(
        label="❌ Não Aceito",
        style=discord.ButtonStyle.danger,
        custom_id="decline_rules"
    )
    async def decline_button(self, interaction: discord.Interaction, button: Button):
        if self.member and interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Esta ação não é para você!", ephemeral=True
            )
            return

        if self._processed:
            await interaction.response.send_message("✅ Já processado!", ephemeral=True)
            return

        await interaction.response.defer()

        confirmation_view = ConfirmationView(
            onboarding_service=self.onboarding_service,
            member=self.member or interaction.user,
            parent_view=self,
            timeout=60,
            is_test=self.is_test,
        )
        msg = await interaction.followup.send(
            embed=ServerRules.get_confirmation_embed(),
            view=confirmation_view,
            ephemeral=True
        )
        confirmation_view.message = msg

    # ── Timeout ──────────────────────────────────────────────────

    async def on_timeout(self):
        if self._processed:
            return

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

            if self.is_test:
                logger.info(f"[TESTE] Timeout de regras para {getattr(self.member, 'name', '?')} — kick ignorado")
                if self.onboarding_service and self.member:
                    self.onboarding_service.clear_pending(self.member.id)
                return

            if self.onboarding_service and self.member:
                await self.onboarding_service.kick_member(
                    self.member,
                    reason="Não aceitou as regras dentro do tempo limite (5 min)",
                    result="timeout"
                )
                logger.warning(f"[Onboarding] {self.member.name} removido por timeout nas regras")

        except Exception as e:
            logger.error(f"[Onboarding] Erro no timeout das regras: {e}")


class ConfirmationView(View):
    """View de confirmação quando o membro clica em Não Aceito"""

    def __init__(
        self,
        onboarding_service=None,
        member: discord.Member = None,
        parent_view: RulesView = None,
        timeout: float = 60,
        is_test: bool = False,
    ):
        super().__init__(timeout=timeout)
        self.onboarding_service = onboarding_service
        self.member             = member
        self.parent_view        = parent_view
        self.message: Optional[discord.Message] = None
        self.is_test            = is_test

    # ── Voltar às regras ─────────────────────────────────────────

    @discord.ui.button(
        label="📜 Voltar às Regras",
        style=discord.ButtonStyle.primary,
        custom_id="back_to_rules"
    )
    async def back_button(self, interaction: discord.Interaction, button: Button):
        if self.member and interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Esta ação não é para você!", ephemeral=True
            )
            return

        if self.parent_view and self.parent_view._processed:
            await interaction.response.send_message(
                "✅ Sua resposta já foi processada.", ephemeral=True
            )
            return

        await interaction.response.defer()
        self.stop()

        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

        if self.parent_view:
            for item in self.parent_view.children:
                item.disabled = False
            if self.parent_view.message:
                try:
                    await self.parent_view.message.edit(view=self.parent_view)
                except Exception:
                    pass

        await interaction.followup.send(
            "📜 Leia as regras novamente e tome sua decisão.", ephemeral=True
        )

    # ── Confirmar saída ──────────────────────────────────────────

    @discord.ui.button(
        label="🚪 Sair do Servidor",
        style=discord.ButtonStyle.danger,
        custom_id="leave_server"
    )
    async def leave_button(self, interaction: discord.Interaction, button: Button):
        if self.member and interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Esta ação não é para você!", ephemeral=True
            )
            return

        await interaction.response.defer()

        if self.parent_view:
            self.parent_view._processed = True
            self.parent_view.stop()
        self.stop()

        try:
            await interaction.followup.send(
                "👋 Você foi removido. Esperamos vê-lo novamente no futuro!",
                ephemeral=True
            )
        except Exception:
            pass

        if self.is_test:
            member_name = getattr(self.member, "name", "?")
            logger.info(f"[TESTE] {member_name} recusou — kick ignorado")
            if self.onboarding_service and self.member:
                self.onboarding_service.clear_pending(self.member.id)
            return

        if self.onboarding_service and self.member:
            await self.onboarding_service.kick_member(
                self.member,
                reason="Recusou as regras do servidor",
                result="recusado"
            )
            logger.info(f"[Onboarding] {self.member.name} recusou as regras e foi removido")

    # ── Timeout da ConfirmationView ──────────────────────────────

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            if self.message:
                try:
                    await self.message.edit(view=self)
                except Exception:
                    pass

            if self.parent_view and not self.parent_view._processed:
                for item in self.parent_view.children:
                    item.disabled = False
                if self.parent_view.message:
                    try:
                        await self.parent_view.message.edit(view=self.parent_view)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"[Onboarding] Erro no timeout da ConfirmationView: {e}")