import discord

from pymongo import collection
from config.database import db
from models.pedido_mediador import PaymentConfirmation
from services.pedido_mediador_service import PedidoMediadorAdminView
from datetime import datetime, timedelta
from typing import List, Dict
from models.mediator import Mediator
from models.match import Match
from config.database import db






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
        self.collection = db.get_collection("payment_confirmations")

    async def confirm(self, ctx, membro: discord.Member):

        guild = ctx.guild
        mediator_role = discord.utils.get(guild.roles, name=self.role_name)

        if not mediator_role:
            await ctx.send(f"❌ Cargo `{self.role_name}` não encontrado.")
            return

        await membro.add_roles(
            mediator_role,
            reason=f"Aprovado por {ctx.author}"
        )

        user_doc = await self.collection.find_one(
            {"discord_id": str(membro.id)}
        )

        if user_doc:

            user_model = PaymentConfirmation(user_doc)

            user_model.confirm_payment(
                admin_name=str(ctx.author)
            )

            await self.collection.update_one(
                {"_id": user_model._id},
                {"$set": user_model.to_dict()}
            )

        else:

            new_doc = PaymentConfirmation.create_document(
                discord_id=str(membro.id),
                username=str(membro)
            )

            await self.collection.insert_one(new_doc)

        try:

            await membro.send(
                f"✅ Você foi promovido a **{self.role_name}**"
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
        from services.pedido_mediador_service import MediatorManager

        self.manager = MediatorManager(db, benefit_days)
        self.benefit_days = benefit_days

    async def create_embed(self):

        mediators_list = await self.manager.get_mediators_with_days()

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



import discord
from datetime import datetime

class VerificacaoMediadoresEmbed:

    def __init__(self, db, benefit_days: int = 7):
        from services.pedido_mediador_service import MediatorManager

        self.manager = MediatorManager(db, benefit_days)
        self.benefit_days = benefit_days

    async def create_embed(self):
        mediators = await self.manager.get_mediators_with_days()

        embed = discord.Embed(
            title="📊 Painel de Verificação de Mediadores",
            description=(
                "Aqui será exibido automaticamente o status de todos os mediadores ativos.\n\n"
                "📅 **Atualização automática**\n"
                "Atualiza todos os dias às **00:00 (horário de Brasília)**.\n\n"
                "📋 **Informações exibidas**\n"
                "• Nome do mediador\n"
                "• Dias restantes\n"
                "• Status do benefício"
            ),
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )

        embed.add_field(
            name="👥 Total de Mediadores",
            value=str(len(mediators)),
            inline=False
        )

        if not mediators:
            embed.add_field(
                name="📋 Mediadores",
                value="Nenhum mediador ativo no momento.",
                inline=False
            )
            embed.set_footer(text="Sistema automático de mediadores")
            return embed

        lista = ""
        for m in mediators:
            status = f"{m['days_remaining']} dias restantes" if m["days_remaining"] > 0 else "❌ Benefício expirado"
            lista += f"• **{m['username']}** — {status}\n"

        embed.add_field(name="📋 Mediadores", value=lista, inline=False)
        embed.set_footer(text="Sistema automático de mediadores")
        return embed
    


# =====================================================
# PEDIDO MEDIADOR
# =====================================================


class PedidoMediadorModal(discord.ui.Modal, title="Solicitação de Mediador"):
    def __init__(self, plano: str):
        super().__init__(title="Solicitação de Mediador")

        self.plano = plano

        
        self.add_item(self.chave_pix)

    async def on_submit(self, interaction: discord.Interaction):

        user = interaction.user

        embed = discord.Embed(
            title="📨 Nova solicitação de Mediador",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Usuário",
            value=f"{user.mention}\nID: `{user.id}`",
            inline=False
        )

        embed.set_footer(text="Aguardando aprovação do administrador")

        view = PedidoMediadorAdminView(self.plano, user.id)

        await interaction.response.send_message(
            "✅ Sua solicitação foi enviada para análise do administrador.",
            ephemeral=True
        )

        channel = discord.utils.get(
            interaction.guild.text_channels,
            name=SOLICITACOES_MEDIADOR_CHANNEL
        )

        if channel:
            await channel.send(embed=embed, view=view)

class ActiveMediatorService:

    def __init__(self, db):
        self.db = db
        self.mediator_collection = db.get_collection("mediators")
        self.match_collection = db.get_collection("matches")

    async def get_active_mediators(self) -> List[Mediator]:
        """
        Retorna todos os mediadores ativos, atualizando limite de partidas a cada 8 minutos.
        """
        now = datetime.utcnow()
        docs = await self.mediator_collection.find({"is_active": True}).to_list(length=None)
        mediators = [Mediator(doc) for doc in docs]

        for m in mediators:
            if not m.last_reset_at or m.last_reset_at < now - timedelta(minutes=8):
                m.matches_in_last_8_minutes = 0
                m.last_reset_at = now

        return mediators

    async def get_mediators_with_stats(self) -> List[Dict]:
        """
        Retorna mediadores ativos com estatísticas de partidas.
        Único método centralizado para todos os módulos.
        """
        active_mediators = await self.get_active_mediators()

        match_docs = await self.match_collection.find({
            "status": {"$in": Match.ACTIVE_STATUSES}
        }).to_list(length=None)
        matches = [Match(doc) for doc in match_docs]

        mediator_stats = []

        for m in active_mediators:
            in_queue = sum(1 for mt in matches if mt.mediator_id == m.discord_id and mt.status != Match.STATUS_AGUARDANDO_PREMIO)
            confirmed = sum(1 for mt in matches if mt.mediator_id == m.discord_id and mt.status == Match.STATUS_AGUARDANDO_PREMIO)

            mediator_stats.append({
                "discord_id": m.discord_id,
                "username": m.username,
                "in_queue": in_queue,
                "confirmed": confirmed,
                "total_matches": m.total_matches,
                "can_mediate": m.can_mediate()
            })

        return mediator_stats

    async def count_active_mediators(self) -> int:
        """
        Retorna total de mediadores ativos.
        """
        active = await self.get_active_mediators()
        return len(active)