import discord
from datetime import datetime
from config.database import db
from models.pedido_mediador import PaymentConfirmation
from src.services.pedido_mediador_service import MediatorManager


SOLICITACOES_MEDIADOR_CHANNEL = "solicitacoes-mediador"


# =====================================================
# MODAL DE SOLICITAÇÃO
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
# CONFIRMAÇÃO DE MEDIADOR
# =====================================================


class MediatorConfirmation:

    def __init__(self, db, role_name: str):

        self.db = db
        self.role_name = role_name
        self.collection = db.payment_confirmations

    async def confirm(self, ctx, membro: discord.Member, pix_key: str):

        guild = ctx.guild

        mediator_role = discord.utils.get(guild.roles, name=self.role_name)

        if not mediator_role:

            await ctx.send(
                f"❌ Cargo `{self.role_name}` não encontrado."
            )
            return

        await membro.add_roles(
            mediator_role,
            reason=f"Aprovado por {ctx.author}"
        )

        user_doc = self.collection.find_one(
            {"discord_id": str(membro.id)}
        )

        if user_doc:

            user_model = PaymentConfirmation(user_doc)

            user_model.confirm_payment(
                admin_name=str(ctx.author),
                pix_key=pix_key
            )

            self.collection.update_one(
                {"_id": user_model._id},
                {"$set": user_model.to_dict()}
            )

        else:

            new_doc = PaymentConfirmation.create_document(
                discord_id=str(membro.id),
                username=str(membro),
                pix_key=pix_key
            )

            self.collection.insert_one(new_doc)

        try:

            await membro.send(
                f"✅ Você foi promovido a **{self.role_name}**\n"
                f"💳 Chave PIX registrada: `{pix_key}`"
            )

        except discord.Forbidden:
            pass

        await ctx.send(
            f"✅ {membro.mention} agora é **{self.role_name}**."
        )


# =====================================================
# EMBED RELATÓRIO
# =====================================================


class MediatorReportEmbed:

    def __init__(self, db, benefit_days: int = 7):

        self.manager = MediatorManager(db, benefit_days)
        self.benefit_days = benefit_days

    def create_embed(self):

        mediators_list = self.manager.get_mediators_with_days()

        embed = discord.Embed(
            title="📋 Relatório de Mediadores Ativos",
            description=f"Dias restantes do plano de {self.benefit_days} dias",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )

        if not mediators_list:

            embed.add_field(
                name="Nenhum mediador ativo",
                value="—",
                inline=False
            )

            return embed

        for m in mediators_list:

            status = (
                f"{m['days_remaining']} dias restantes"
                if m['days_remaining'] > 0
                else "❌ Benefício expirado"
            )

            embed.add_field(
                name=m["username"],
                value=status,
                inline=False
            )

        return embed
    

# =====================================================
# EMBED PAINEL
# =====================================================


class VerificacaoMediadoresEmbed:

    @staticmethod
    def painel():

        embed = discord.Embed(
            title="📊 Painel de Verificação de Mediadores",
            description="Aqui será exibido automaticamente o status de todos os mediadores ativos.",
            color=discord.Color.green()
        )

        embed.add_field(
            name="📅 Atualização automática",
            value="Atualiza todos os dias à **00:00 (horário de Brasília)**.",
            inline=False
        )

        embed.add_field(
            name="📋 Informações exibidas",
            value=(
                "• Nome do mediador\n"
                "• Dias restantes\n"
                "• Status do benefício"
            ),
            inline=False
        )

        embed.set_footer(
            text="Sistema automático de mediadores"
        )

        return embed