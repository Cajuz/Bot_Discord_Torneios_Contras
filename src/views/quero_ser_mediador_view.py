import discord

from pymongo import collection
from config.database import db
from models.pedido_mediador import PaymentConfirmation
from datetime import datetime, timedelta
from utils.datetime_utils import utcnow
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
            timestamp=utcnow()
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
            timestamp=utcnow()
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


class PedidoMediadorModal(discord.ui.Modal):
    def __init__(self, plano: str):
        super().__init__(title="Solicitação de Mediador")
        self.plano = plano

        # Se você não quer campos de texto (PIX), o modal pode ser enviado 
        # apenas confirmando um motivo ou algo simples, ou até vazio.
        # Vou deixar um campo de "Observação" opcional, ou você pode remover.
        self.obs = discord.ui.TextInput(
            label="Alguma observação? (Opcional)",
            style=discord.TextStyle.paragraph,
            placeholder="Digite aqui se tiver algo a dizer...",
            required=False,
            max_length=300
        )
        self.add_item(self.obs)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        
        # 1. Criar o Embed para o Administrador
        embed = discord.Embed(
            title="📨 Nova solicitação de Mediador",
            description=f"O usuário deseja se tornar mediador.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="👤 Usuário",
            value=f"{user.mention}\nID: `{user.id}`",
            inline=True
        )
        
        embed.add_field(
            name="📅 Plano",
            value=f"**{self.plano.capitalize()}**",
            inline=True
        )

        if self.obs.value:
            embed.add_field(name="📝 Observação", value=self.obs.value, inline=False)

        embed.set_footer(text="Clique nos botões abaixo para gerenciar.")

        # 2. Enviar para o canal de solicitações
        channel = discord.utils.get(interaction.guild.text_channels, name=SOLICITACOES_MEDIADOR_CHANNEL)

        if channel:
            view_admin = PedidoMediadorAdminView(self.plano, user.id)
            await channel.send(embed=embed, view=view_admin)
            
            # 3. Responder ao usuário
            await interaction.response.send_message(
                "✅ Sua solicitação foi enviada para análise do administrador.",
                ephemeral=True
            )
        else:
            # Caso o canal não seja encontrado pelo nome
            await interaction.response.send_message(
                f"❌ Erro: Canal `#{SOLICITACOES_MEDIADOR_CHANNEL}` não encontrado.",
                ephemeral=True
            )




            
class ActiveMediatorService:

    def __init__(self, db):
        self.db = db
        self.mediator_collection = db.get_collection("mediators")
        self.match_collection = db.get_collection("matches")

    async def get_active_mediators(self) -> List[Mediator]:
        """
        Retorna todos os mediadores ativos, atualizando limite de partidas a cada 8 minutos.
        """
        now = utcnow()
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

class PedidoMediadorValor(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Plano Semanal - R$50", 
        style=discord.ButtonStyle.green,
        custom_id="btn_semanal_mediador" # ID fixo ajuda na persistência
    )
    async def plano_semanal(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Como a classe Modal está logo acima, o botão agora a encontra
        await interaction.response.send_modal(PedidoMediadorModal(plano="semanal"))

# ── Alias para main.py ──────────────────────────────────────────
class PedidoMediadorView(PedidoMediadorAdminView.__bases__[0]):
    """View principal do painel 'Quero ser mediador'."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Quero ser mediador", style=discord.ButtonStyle.success,
                       custom_id="quero_ser_mediador_btn")
    async def pedir(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Escolha um plano:", view=PedidoMediadorValor(), ephemeral=True
        )
