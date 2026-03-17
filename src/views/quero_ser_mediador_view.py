# quero_ser_mediador_view.py — Painel de candidatura a mediador.
from __future__ import annotations
import discord
from datetime import timedelta

from config.database import db
from utils.datetime_utils import utcnow
from services.channel_service import (
    SOLICITACOES_CHANNEL as SOLICITACOES_MEDIADOR_CHANNEL,
    APROVAR_MEDIADORES_CHANNEL,   # ← NOVO: cards de aprovação vão para cá
)


# ═══════════════════════════════════════════════════════════════
# EMBED — Benefícios (painel público)
# ═══════════════════════════════════════════════════════════════

class PedidomediadorEmbed:

    @staticmethod
    def beneficios() -> discord.Embed:
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
        embed.add_field(name="📅 Plano Disponível", value="• Plano semanal", inline=False)
        embed.set_footer(text="Clique no botão abaixo para iniciar o processo.")
        return embed


# ═══════════════════════════════════════════════════════════════
# EMBED — Relatório de mediadores ativos
# ═══════════════════════════════════════════════════════════════

class MediatorReportEmbed:

    def __init__(self, benefit_days: int = 7):
        from services.pedido_mediador_service import MediatorManager
        self.manager = MediatorManager(db, benefit_days)
        self.benefit_days = benefit_days

    async def create_embed(self) -> discord.Embed:
        mediators_list = await self.manager.get_mediators_with_days()
        embed = discord.Embed(
            title="📋 Relatório de Mediadores Ativos",
            description=f"Dias restantes do plano de {self.benefit_days} dias",
            color=discord.Color.green(),
            timestamp=utcnow()
        )
        if not mediators_list:
            embed.add_field(name="Nenhum mediador ativo", value="—", inline=False)
            return embed
        for m in mediators_list:
            status = (
                f"{m['days_remaining']} dias restantes"
                if m['days_remaining'] > 0
                else "❌ Benefício expirado"
            )
            embed.add_field(name=m["username"], value=status, inline=False)
        return embed


# ═══════════════════════════════════════════════════════════════
# EMBED — Painel de verificação
# ═══════════════════════════════════════════════════════════════

class VerificacaoMediadoresEmbed:

    def __init__(self, benefit_days: int = 7):
        from services.pedido_mediador_service import MediatorManager
        self.manager = MediatorManager(db, benefit_days)
        self.benefit_days = benefit_days

    async def create_embed(self) -> discord.Embed:
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
        embed.add_field(name="👥 Total de Mediadores", value=str(len(mediators)), inline=False)
        if not mediators:
            embed.add_field(name="📋 Mediadores", value="Nenhum mediador ativo no momento.", inline=False)
            embed.set_footer(text="Sistema automático de mediadores")
            return embed
        lista = "\n".join(
            f"• **{m['username']}** — "
            f"{m['days_remaining']} dias restantes" if m["days_remaining"] > 0
            else f"• **{m['username']}** — ❌ Benefício expirado"
            for m in mediators
        )
        embed.add_field(name="📋 Mediadores", value=lista, inline=False)
        embed.set_footer(text="Sistema automático de mediadores")
        return embed


# ═══════════════════════════════════════════════════════════════
# CONFIRMAÇÃO DE MEDIADOR (helper administrativo)
# ═══════════════════════════════════════════════════════════════

class MediatorConfirmation:

    def __init__(self, role_name: str):
        self.role_name  = role_name
        self.collection = db.get_collection("payment_confirmations")

    async def confirm(self, ctx, membro: discord.Member):
        from models.pedido_mediador import PaymentConfirmation
        guild         = ctx.guild
        mediator_role = discord.utils.get(guild.roles, name=self.role_name)
        if not mediator_role:
            await ctx.send(f"❌ Cargo `{self.role_name}` não encontrado.")
            return
        await membro.add_roles(mediator_role, reason=f"Aprovado por {ctx.author}")
        user_doc = await self.collection.find_one({"discord_id": str(membro.id)})
        if user_doc:
            user_model = PaymentConfirmation(user_doc)
            user_model.confirm_payment(admin_name=str(ctx.author))
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
            await membro.send(f"✅ Você foi promovido a **{self.role_name}**")
        except discord.Forbidden:
            pass
        await ctx.send(f"✅ {membro.mention} agora é **{self.role_name}**.")


# ═══════════════════════════════════════════════════════════════
# MODAL — Solicitação de mediador
# ═══════════════════════════════════════════════════════════════

class PedidoMediadorModal(discord.ui.Modal, title="Solicitação de Mediador"):

    obs = discord.ui.TextInput(
        label="Alguma observação? (Opcional)",
        style=discord.TextStyle.paragraph,
        placeholder="Digite aqui se tiver algo a dizer...",
        required=False,
        max_length=300
    )

    def __init__(self, plano: str):
        super().__init__()
        self.plano = plano

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user

        embed = discord.Embed(
            title="📨 Nova solicitação de Mediador",
            description="O usuário deseja se tornar mediador.",
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
        embed.set_footer(text="Clique nos botões abaixo para aprovar ou recusar.")

        # ← ATUALIZADO: card vai para #aprovar-mediadores (era #solicitacoes-mediador)
        channel = discord.utils.get(
            interaction.guild.text_channels, name=APROVAR_MEDIADORES_CHANNEL
        )

        if channel:
            view_admin = PedidoMediadorAdminView(self.plano, user.id)
            await channel.send(embed=embed, view=view_admin)
            await interaction.response.send_message(
                "✅ Sua solicitação foi enviada para análise do administrador.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Erro: Canal `#{APROVAR_MEDIADORES_CHANNEL}` não encontrado.",
                ephemeral=True
            )


# ═══════════════════════════════════════════════════════════════
# VIEW — Seleção de plano (enviada na DM/ephemeral ao candidato)
# ═══════════════════════════════════════════════════════════════

class PedidoMediadorValor(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Plano Semanal - R$50",
        style=discord.ButtonStyle.green,
        custom_id="btn_semanal_mediador"
    )
    async def plano_semanal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PedidoMediadorModal(plano="semanal"))


# ═══════════════════════════════════════════════════════════════
# VIEW — Admin (card de aprovação no #aprovar-mediadores)
# Nota: não é persistente intencionalmente — é criada por solicitação
# e o user_id fica em memória. Após restart, cards antigos não respondem.
# Para persistência total, seria necessário salvar user_id no banco.
# ═══════════════════════════════════════════════════════════════

class PedidoMediadorAdminView(discord.ui.View):

    def __init__(self, plano: str, user_id: int):
        super().__init__(timeout=None)
        self.plano   = plano
        self.user_id = user_id

    @discord.ui.button(label="Aprovar", style=discord.ButtonStyle.green, custom_id="pedido_med_aprovar")
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user  = guild.get_member(self.user_id)
        admin = interaction.user

        if not user:
            await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)
            return

        try:
            await user.send(
                f"🎉 Sua solicitação para ser **Mediador** foi **aprovada**!\n\n"
                f"👤 Aprovado por: {admin}\n"
                f"📦 Plano escolhido: **{self.plano}**\n\n"
                f"💳 Envie o comprovante de pagamento para {admin.mention}."
            )
        except discord.Forbidden:
            pass

        try:
            await admin.send(
                f"✅ Você aprovou uma solicitação de mediador.\n\n"
                f"👤 Usuário: {user} (`{user.id}`)\n"
                f"📦 Plano: **{self.plano}**"
            )
        except discord.Forbidden:
            pass

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(name="Status", value=f"✅ Aprovado por {admin.mention}", inline=False)

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(
            f"✅ Solicitação de {user.mention} aprovada.", ephemeral=True
        )

    @discord.ui.button(label="Recusar", style=discord.ButtonStyle.red, custom_id="pedido_med_recusar")
    async def recusar(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user  = guild.get_member(self.user_id)

        if user:
            try:
                await user.send("❌ Sua solicitação para ser mediador foi recusada.")
            except discord.Forbidden:
                pass

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(view=self)
        await interaction.response.send_message("❌ Solicitação recusada.", ephemeral=True)


# ═══════════════════════════════════════════════════════════════
# VIEW — Painel público "Quero ser mediador" (persistente)
# ═══════════════════════════════════════════════════════════════

class PedidoMediadorView(discord.ui.View):
    """View principal do painel 'Quero ser mediador'."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Quero ser mediador",
        style=discord.ButtonStyle.success,
        custom_id="quero_ser_mediador_btn"
    )
    async def pedir(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Escolha um plano:", view=PedidoMediadorValor(), ephemeral=True
        )
