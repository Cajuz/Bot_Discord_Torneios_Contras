import discord
from datetime import datetime
from utils.logger import logger
from models.pedido_mediador import PaymentConfirmation
from views.quero_ser_mediador_view import PedidoMediadorValor






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





# =====================================================
# GERENCIADOR DE MEDIADORES
# =====================================================

class MediatorManager:

    def __init__(self, db, mediator_role_name, benefit_days: int = 7):

        self.db = db
        self.mediator_role_name = mediator_role_name
        self.benefit_days = benefit_days

        self.payment_collection = db.get_collection("payment_confirmations")
        self.mediator_collection = db.get_collection("mediators")

    # =========================
    # MEDIADORES ATIVOS
    # =========================

    async def get_active_mediators(self):

        mediators = []

        cursor = self.payment_collection.find({
            "confirmation_date": {"$ne": None},
            "active": True
        })

        async for m in cursor:
            mediators.append(m)

        return mediators

    # =========================
    # CALCULAR DIAS RESTANTES
    # =========================

    def calculate_days_remaining(self, mediator):

        reference_date = mediator.get("confirmation_date") or mediator.get("role_received_date")

        if not reference_date:
            return 0

        if isinstance(reference_date, str):
            reference_date = datetime.fromisoformat(reference_date)

        elapsed_days = (datetime.utcnow() - reference_date).days

        remaining_days = self.benefit_days - elapsed_days

        return max(remaining_days, 0)

    # =========================
    # LISTA DE MEDIADORES + DIAS
    # =========================

    async def get_mediators_with_days(self):

        mediator_list = []

        mediators = await self.get_active_mediators()

        for m in mediators:

            days_remaining = self.calculate_days_remaining(m)

            mediator_list.append({
                "username": m.get("username"),
                "discord_id": m.get("discord_id"),
                "days_remaining": days_remaining
            })

        return mediator_list

    # =========================
    # EXPIRAR MEDIADORES
    # =========================

    async def expire_mediators(self):

        mediators = await self.get_active_mediators()

        for m in mediators:

            days_remaining = self.calculate_days_remaining(m)

            if days_remaining <= 0:

                await self.payment_collection.update_one(
                    {"discord_id": m.get("discord_id")},
                    {"$set": {"active": False}}
                )

                await self.mediator_collection.update_one(
                    {"discord_id": m.get("discord_id")},
                    {"$set": {"is_active": False}}
                )

    # =========================
    # CONTAR MEDIADORES ATIVOS
    # =========================

    async def count_active_mediators(self):

        count = await self.payment_collection.count_documents({
            "active": True
        })

        return count