import discord
from datetime import datetime
from models.pedido_mediador import PaymentConfirmation





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
        

    @discord.ui.button(label="Plano Semanal - R$50", style=discord.ButtonStyle.green)
    async def plano_semanal(self, interaction: discord.Interaction, button: discord.ui.Button):
        from views.quero_ser_mediador_view import PedidoMediadorModal

        await interaction.response.send_modal(PedidoMediadorModal(plano="semanal"))




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
                f"🎉 Sua solicitação para ser **Mediador** foi **aprovada**!\n\n"
                f"👤 Aprovado por: {admin}\n"
                f"📦 Plano escolhido: **{self.plano}**\n\n"
                f"💳 Agora envie o comprovante de pagamento para o administrador{admin.mention}."
            )
        except discord.Forbidden:
            pass


        # DM PARA O ADM
        try:
            await admin.send(
                f"✅ Você aprovou uma solicitação de mediador.\n\n"
                f"👤 Usuário: {user} (`{user.id}`)\n"
                f"📦 Plano: **{self.plano}**"
            )
        except discord.Forbidden:
            pass


        # RESPOSTA NO BOTÃO
        await interaction.response.send_message(
            f"✅ Solicitação de {user.mention} aprovada.",
            ephemeral=True
        )


        # ATUALIZA EMBED NO CANAL
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()

        embed.add_field(
            name="Status",
            value=f"✅ Aprovado por {admin.mention}",
            inline=False
        )

        # DESATIVA BOTÕES
        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)

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
        self.collection = db.get_collection("payment_confirmations")
        self.benefit_days = benefit_days

    async def get_active_mediators(self):
        mediators = []
        cursor = self.collection.find({"confirmation_date": {"$ne": None}})
        async for m in cursor:
            mediators.append(PaymentConfirmation(m))
        return mediators

    def calculate_days_remaining(self, mediator: PaymentConfirmation):
        reference_date = mediator.confirmation_date or mediator.role_received_date
        if not reference_date:
            return 0
        if isinstance(reference_date, str):
            reference_date = datetime.fromisoformat(reference_date)
        elapsed_days = (datetime.utcnow() - reference_date).days
        remaining_days = self.benefit_days - elapsed_days
        return max(remaining_days, 0)

    async def get_mediators_with_days(self):
        mediators = await self.get_active_mediators()
        return [
            {
                "username": m.username,
                "discord_id": m.discord_id,
                "days_remaining": self.calculate_days_remaining(m)
            }
            for m in mediators
        ]





