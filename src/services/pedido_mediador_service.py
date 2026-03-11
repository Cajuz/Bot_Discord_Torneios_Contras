import discord
from datetime import datetime
from config.database import db
from models.pedido_mediador import PaymentConfirmation
from services.pedido_mediador_service import PedidoMediadorModal





SOLICITACOES_MEDIADOR_CHANNEL = "solicitacoes-mediador"


# =====================================================
# EMBED DE BENEFÍCIOS
# =====================================================

class PedidomediadorEmbed:

    @staticmethod
    def beneficios():

        embed = discord.Embed(
            title="💼 Torne-se um Mediador",
            description=(
                "Quer ganhar dinheiro ajudando nas negociações do servidor?\n\n"
                "Os mediadores garantem segurança nas transações entre membros "
                "e recebem benefícios exclusivos durante o contrato."
            ),
            color=discord.Color.blue()
        )

        embed.add_field(
            name="✅ Benefícios",
            value=(
                "• Cargo exclusivo de Mediador\n"
                "• Acesso a canais privados\n"
                "• Prioridade nas negociações\n"
                "• Comissão por mediação realizada"
            ),
            inline=False
        )

        embed.add_field(
            name="💰 Ganhos",
            value=(
                "• Possibilidade de ganhos durante o contrato\n"
                "• Receba comissão por cada mediação concluída"
            ),
            inline=False
        )

        embed.add_field(
            name="📅 Plano Disponível",
            value="• Plano semanal",
            inline=False
        )

        embed.set_footer(
            text="Clique no botão abaixo para iniciar o processo."
        )

        return embed





# =====================================================
# VIEW DE PLANOS
# =====================================================

class PedidoMediadorValor(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Plano Semanal - R$50",
        style=discord.ButtonStyle.green
    )
    async def semanal(self, interaction: discord.Interaction, button: discord.ui.Button):

        modal = PedidoMediadorModal("Semanal - R$50")
        await interaction.response.send_modal(modal)


# =====================================================
# VIEW PRINCIPAL
# =====================================================

class PedidoMediadorView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Quero ser mediador",
        style=discord.ButtonStyle.green
    )
    async def pedir(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_message(
            "Escolha um plano:",
            view=PedidoMediadorValor(),
            ephemeral=True
        )


# =====================================================
# VIEW ADMIN
# =====================================================

class PedidoMediadorAdminView(discord.ui.View):

    def __init__(self, plano: str, user_id: int):
        super().__init__(timeout=None)
        self.plano = plano
        self.user_id = user_id

    @discord.ui.button(label="Aprovar", style=discord.ButtonStyle.green)
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):

        guild = interaction.guild
        user = guild.get_member(self.user_id)
        admin = interaction.user

        if not user:

            await interaction.response.send_message(
                "❌ Usuário não encontrado.",
                ephemeral=True
            )
            return

        try:

            await user.send(
                f"✅ Sua solicitação foi **aprovada** por {admin.mention}\n"
                f"Plano escolhido: **{self.plano}**\n\n"
                "Entre em contato com o ADM para enviar o comprovante."
            )

        except discord.Forbidden:
            pass

        await interaction.response.send_message(
            f"✅ Solicitação de {user.mention} aprovada.",
            ephemeral=True
        )

        button.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Recusar", style=discord.ButtonStyle.red)
    async def recusar(self, interaction: discord.Interaction, button: discord.ui.Button):

        guild = interaction.guild
        user = guild.get_member(self.user_id)

        if user:

            try:
                await user.send(
                    "❌ Sua solicitação para ser mediador foi recusada."
                )
            except discord.Forbidden:
                pass

        await interaction.response.send_message(
            "❌ Solicitação recusada.",
            ephemeral=True
        )

        button.disabled = True
        await interaction.message.edit(view=self)





# =====================================================
# GERENCIADOR DE MEDIADORES
# =====================================================

class MediatorManager:

    def __init__(self, db, benefit_days: int = 7):

        self.collection = db.payment_confirmations
        self.benefit_days = benefit_days

    def get_active_mediators(self):

        mediators = self.collection.find(
            {"is_active": {"$ne": False}}
        )

        return [PaymentConfirmation(m) for m in mediators]

    def calculate_days_remaining(self, mediator: PaymentConfirmation):

        reference_date = mediator.role_received_date or mediator.confirmation_date

        if not reference_date:
            return 0

        if isinstance(reference_date, str):
            reference_date = datetime.fromisoformat(reference_date)

        elapsed_days = (datetime.utcnow() - reference_date).days

        remaining_days = self.benefit_days - elapsed_days

        return max(remaining_days, 0)

    def get_mediators_with_days(self):

        mediators = self.get_active_mediators()

        return [

            {
                "username": m.username,
                "discord_id": m.discord_id,
                "days_remaining": self.calculate_days_remaining(m)
            }

            for m in mediators

        ]





