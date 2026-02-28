import discord
from discord.ui import View, Button
from typing import Optional
from config.rules import ServerRules
from utils.logger import logger


class RulesView(View):
    """
    View com botões de aceitar/recusar — enviada na DM após entrar no servidor.
    is_test=True: não kicca no timeout, apenas edita a mensagem.
    """

    def __init__(
        self,
        onboarding_service,
        member: discord.Member,
        timeout: float = 300,
        is_test: bool = False,
    ):
        super().__init__(timeout=timeout)
        self.onboarding_service = onboarding_service
        self.member             = member
        self.message: Optional[discord.Message] = None
        self.is_test            = is_test
        self._processed         = False  # evita double-processing

    def _member_custom_id(self, action: str) -> str:
        """custom_id único por membro para evitar colisão em onboarding simultâneo"""
        return f"{action}_{self.member.id}"

    # ── Aceitar ──────────────────────────────────────────────────

    @discord.ui.button(
        label="✅ Aceito as Regras",
        style=discord.ButtonStyle.success,
        custom_id="accept_rules"  # sobrescrito em __init__ abaixo
    )
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Apenas o novo membro pode aceitar as regras!", ephemeral=True
            )
            return

        if self._processed:
            await interaction.response.send_message("✅ Já processado!", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            success = await self.onboarding_service.accept_rules(self.member)

            if success:
                self._processed = True
                self.stop()  # ← cancela o timer → on_timeout nunca dispara

                for item in self.children:
                    item.disabled = True
                if self.message:
                    try:
                        await self.message.edit(view=self)
                    except Exception:
                        pass

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

    # ── Recusar ──────────────────────────────────────────────────

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

        if self._processed:
            await interaction.response.send_message("✅ Já processado!", ephemeral=True)
            return

        await interaction.response.defer()

        confirmation_view = ConfirmationView(
            onboarding_service=self.onboarding_service,
            member=self.member,
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
        """
        Timer de 5min esgotado.
        Só kicca se o membro não foi processado ainda e não é teste.
        """
        if self._processed:
            return  # aceitou ou recusou antes do timeout — não faz nada

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
                logger.info(f"[TESTE] Timeout de regras para {self.member.name} — kick ignorado")
                self.onboarding_service.clear_pending(self.member.id)
                return

            await self.onboarding_service.kick_member(
                self.member,
                reason="Não aceitou as regras dentro do tempo limite (5 min)",
                result='timeout'
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
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Esta ação não é para você!", ephemeral=True
            )
            return

        # Só reativa a parent_view se ela ainda não foi processada
        if self.parent_view._processed:
            await interaction.response.send_message(
                "✅ Sua resposta já foi processada.", ephemeral=True
            )
            return

        await interaction.response.defer()
        self.stop()  # para o timer da ConfirmationView

        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

        # Reativa botões da view pai
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
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Esta ação não é para você!", ephemeral=True
            )
            return

        await interaction.response.defer()

        # Marca a parent_view como processada antes de kickar
        self.parent_view._processed = True
        self.parent_view.stop()  # cancela o timer da RulesView pai também
        self.stop()

        try:
            await interaction.followup.send(
                "👋 Você foi removido. Esperamos vê-lo novamente no futuro!",
                ephemeral=True
            )
        except Exception:
            pass

        if self.is_test:
            logger.info(f"[TESTE] {self.member.name} recusou — kick ignorado")
            self.onboarding_service.clear_pending(self.member.id)
            return

        await self.onboarding_service.kick_member(
            self.member,
            reason="Recusou as regras do servidor",
            result='recusado'
        )
        logger.info(f"Usuário {self.member.name} recusou as regras e foi removido")

    # ── Timeout da ConfirmationView ──────────────────────────────

    async def on_timeout(self):
        """
        60s sem resposta na confirmação → reativa a RulesView pai
        para o membro poder aceitar ainda (timer pai ainda está rodando).
        """
        try:
            for item in self.children:
                item.disabled = True
            if self.message:
                try:
                    await self.message.edit(view=self)
                except Exception:
                    pass

            # Se o membro não processou ainda, reativa a parent_view
            if not self.parent_view._processed:
                for item in self.parent_view.children:
                    item.disabled = False
                if self.parent_view.message:
                    try:
                        await self.parent_view.message.edit(view=self.parent_view)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Erro no timeout da ConfirmationView: {e}")
