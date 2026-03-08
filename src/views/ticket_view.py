from __future__ import annotations
import discord
from datetime import datetime
from typing import Optional

from models.ticket import Ticket
from services.ticket_service import ticket_service, CHAMADOS_CHANNEL_NAME, SUPORTE_ROLE_NAME
from utils.logger import logger


# ─────────────────────────────────────────────
# Helpers de embed
# ─────────────────────────────────────────────

def build_card_embed(ticket: Ticket, guild: discord.Guild) -> discord.Embed:
    """Constrói o embed do card em #chamados-suporte"""
    color_map = {
        Ticket.STATUS_ABERTO:    discord.Color.yellow(),
        Ticket.STATUS_PENDENTE:  discord.Color.blue(),
        Ticket.STATUS_RESOLVIDO: discord.Color.green(),
        Ticket.STATUS_FECHADO:   discord.Color.red(),
    }

    status_label_map = {
        Ticket.STATUS_ABERTO:    "🟡 Aberto",
        Ticket.STATUS_PENDENTE:  "🔵 Pendente",
        Ticket.STATUS_RESOLVIDO: "✅ Resolvido",
        Ticket.STATUS_FECHADO:   "⛔ Fechado pelo membro",
    }

    embed = discord.Embed(
        title=f"🎫 Chamado {ticket.ticket_id}",
        color=color_map.get(ticket.status, discord.Color.greyple())
    )
    embed.add_field(
        name="👤 Aberto por",
        value=f"<@{ticket.discord_id}>",
        inline=True
    )
    embed.add_field(
        name="📂 Categoria",
        value=ticket.categoria,
        inline=True
    )
    embed.add_field(
        name="📊 Status",
        value=status_label_map.get(ticket.status, ticket.status),
        inline=True
    )
    embed.add_field(
        name="📝 Descrição",
        value=ticket.descricao[:1024],
        inline=False
    )

    if ticket.atendente_id:
        embed.add_field(
            name="🧑‍💼 Atendente",
            value=f"<@{ticket.atendente_id}>",
            inline=True
        )

    if ticket.resolved_at:
        embed.add_field(
            name="🕐 Resolvido em",
            value=ticket.resolved_at.strftime("%d/%m/%Y às %H:%M"),
            inline=True
        )
    elif ticket.closed_at:
        embed.add_field(
            name="🕐 Fechado em",
            value=ticket.closed_at.strftime("%d/%m/%Y às %H:%M"),
            inline=True
        )

    embed.set_footer(
        text=f"Aberto em {ticket.created_at.strftime('%d/%m/%Y às %H:%M')}"
    )
    return embed


async def post_or_update_card(
    ticket: Ticket,
    guild: discord.Guild,
    bot: discord.Client,
) -> Optional[discord.Message]:
    """
    Apaga o card antigo (se existir) e posta novo card em #chamados-suporte.
    Retorna a nova mensagem.
    """
    chamados_channel = discord.utils.get(guild.text_channels, name=CHAMADOS_CHANNEL_NAME)
    if not chamados_channel:
        logger.error(f"Canal #{CHAMADOS_CHANNEL_NAME} não encontrado.")
        return None

    # Apaga card antigo
    if ticket.card_message_id:
        try:
            old_msg = await chamados_channel.fetch_message(ticket.card_message_id)
            await old_msg.delete()
        except Exception:
            pass

    embed = build_card_embed(ticket, guild)

    # Botão de assumir só aparece se aberto
    view = SupportCardView() if ticket.status == Ticket.STATUS_ABERTO else None

    new_msg = await chamados_channel.send(embed=embed, view=view)
    await ticket_service.save_card_message_id(ticket.ticket_id, new_msg.id)
    return new_msg


# ─────────────────────────────────────────────
# View do card em #chamados-suporte
# ─────────────────────────────────────────────

class SupportCardView(discord.ui.View):
    """
    View persistente do card em #chamados-suporte.
    timeout=None + custom_id fixo → sobrevive ao reinício do bot.
    O ticket é buscado no banco pelo message.id ao clicar.
    """

    def __init__(self):
        super().__init__(timeout=None)  # ← obrigatório para ser persistente

    @discord.ui.button(
        label="✋ Assumir",
        style=discord.ButtonStyle.primary,
        custom_id="assume_ticket_button"  # ← custom_id fixo, não dinâmico
    )
    async def assume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verifica cargo
        suporte_role = discord.utils.get(interaction.guild.roles, name=SUPORTE_ROLE_NAME)
        is_suporte   = suporte_role and suporte_role in interaction.user.roles
        is_admin     = interaction.user.guild_permissions.administrator

        if not is_suporte and not is_admin:
            await interaction.response.send_message(
                "❌ Apenas a equipe de Suporte pode assumir chamados.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        # Busca ticket pelo card_message_id em vez de depender de self.ticket
        ticket = await ticket_service.get_ticket_by_card_message_id(interaction.message.id)

        if not ticket:
            await interaction.followup.send(
                "❌ Chamado não encontrado. Pode ter sido deletado ou já processado.",
                ephemeral=True
            )
            return

        if ticket.status != Ticket.STATUS_ABERTO:
            await interaction.followup.send(
                f"❌ Este chamado já está `{ticket.status}` — não pode ser assumido.",
                ephemeral=True
            )
            return

        success, msg, ticket = await ticket_service.assume_ticket(
            ticket_id=ticket.ticket_id,
            atendente_id=str(interaction.user.id),
            guild_id=interaction.guild.id,
        )

        if not success:
            await interaction.followup.send(f"❌ {msg}", ephemeral=True)
            return

        # Atualiza card
        await post_or_update_card(ticket, interaction.guild, interaction.client)

        # DM para o suporte com detalhes
        membro_mention = f"<@{ticket.discord_id}>"
        dm_embed = discord.Embed(
            title=f"🎫 Chamado Assumido — {ticket.ticket_id}",
            color=discord.Color.blue()
        )
        dm_embed.add_field(name="👤 Membro",    value=membro_mention,   inline=True)
        dm_embed.add_field(name="📂 Categoria", value=ticket.categoria, inline=True)
        dm_embed.add_field(name="📝 Descrição", value=ticket.descricao, inline=False)
        dm_embed.add_field(
            name="📩 Como atender",
            value=(
                f"Entre em contato via **DM pessoal** com {membro_mention}.\n\n"
                f"⚠️ Se a DM estiver bloqueada, mencione {membro_mention} no canal "
                f"`#chat-suporte` pedindo que abra a DM.\n\n"
                f"Quando resolver, use `!concluir_chamado {ticket.ticket_id}` "
                f"em `#chamados-suporte`."
            ),
            inline=False
        )

        try:
            await interaction.user.send(embed=dm_embed)
        except discord.Forbidden:
            chamados = discord.utils.get(interaction.guild.text_channels, name=CHAMADOS_CHANNEL_NAME)
            if chamados:
                await chamados.send(
                    f"⚠️ {interaction.user.mention} sua DM está bloqueada — "
                    f"verifique as configurações para receber instruções dos chamados.",
                    delete_after=30
                )

        await interaction.followup.send(
            f"✅ Chamado `{ticket.ticket_id}` assumido! Verifique sua DM.",
            ephemeral=True
        )



# ─────────────────────────────────────────────
# Modal de abertura de ticket
# ─────────────────────────────────────────────

class TicketModal(discord.ui.Modal, title="Abrir Chamado de Suporte"):

    categoria = discord.ui.TextInput(
        label="Categoria",
        placeholder="Bug | Pagamento | Dúvida | Outro",
        min_length=3,
        max_length=20,
        required=True,
    )

    descricao = discord.ui.TextInput(
        label="Descrição do problema",
        style=discord.TextStyle.paragraph,
        placeholder="Descreva seu problema com o máximo de detalhes...",
        min_length=20,
        max_length=1000,
        required=True,
    )

    def __init__(self, bot: discord.Client):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        categoria_raw  = self.categoria.value.strip().capitalize()
        categorias_val = ["Bug", "Pagamento", "Dúvida", "Outro"]
        categoria      = categoria_raw if categoria_raw in categorias_val else "Outro"

        success, erro, ticket = await ticket_service.create_ticket(
            discord_id=str(interaction.user.id),
            username=interaction.user.display_name,
            guild_id=interaction.guild.id,
            categoria=categoria,
            descricao=self.descricao.value,
        )

        if not success:
            await interaction.followup.send(f"❌ {erro}", ephemeral=True)
            return

        await post_or_update_card(ticket, interaction.guild, self.bot)

        suporte_role = discord.utils.get(interaction.guild.roles, name=SUPORTE_ROLE_NAME)
        chamados     = discord.utils.get(interaction.guild.text_channels, name=CHAMADOS_CHANNEL_NAME)
        if chamados and suporte_role:
            await chamados.send(
                f"{suporte_role.mention} novo chamado de <@{interaction.user.id}>!",
                delete_after=30
            )

        await interaction.followup.send(
            f"✅ Chamado `{ticket.ticket_id}` aberto!\n"
            f"Aguarde um atendente. Você será contatado via **DM**.",
            ephemeral=True
        )


# ─────────────────────────────────────────────
# View do painel fixo em #suporte
# ─────────────────────────────────────────────

class TicketPanelView(discord.ui.View):
    """Card fixo em #suporte com botões Abrir Ticket e Ver Histórico"""

    def __init__(self, bot: discord.Client):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="📋 Abrir Ticket",
        style=discord.ButtonStyle.green,
        custom_id="open_ticket"
    )
    async def open_ticket(self, interaction, button):
        await interaction.response.send_modal(TicketModal(self.bot))

    @discord.ui.button(
        label="📂 Ver Histórico",
        style=discord.ButtonStyle.secondary,
        custom_id="view_history"
    )
    async def view_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        tickets = await ticket_service.get_user_tickets(
            str(interaction.user.id),
            interaction.guild.id
        )

        if not tickets:
            await interaction.followup.send(
                "📭 Nenhum chamado encontrado no seu histórico.",
                ephemeral=True
            )
            return

        status_emoji = {
            Ticket.STATUS_ABERTO:    "🟡",
            Ticket.STATUS_PENDENTE:  "🔵",
            Ticket.STATUS_RESOLVIDO: "✅",
            Ticket.STATUS_FECHADO:   "⛔",
        }

        embed = discord.Embed(
            title="📂 Seus Chamados",
            color=discord.Color.blurple()
        )

        for t in tickets[:10]:
            emoji = status_emoji.get(t.status, "❓")
            embed.add_field(
                name=f"{emoji} `{t.ticket_id}` — {t.categoria}",
                value=(
                    f"**Status:** {t.status.capitalize()}\n"
                    f"**Aberto em:** {t.created_at.strftime('%d/%m/%Y %H:%M')}"
                    + (f"\n**Feche com:** `!fechar_chamado {t.ticket_id}`"
                       if t.status in Ticket.OPEN_STATUSES else "")
                ),
                inline=False
            )

        if len(tickets) > 10:
            embed.set_footer(text=f"Mostrando 10 de {len(tickets)} chamados")

        await interaction.followup.send(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
# Comandos de texto (chamados via main.py)
# ─────────────────────────────────────────────

async def cmd_fechar_chamado(ctx, ticket_id: str):
    """!fechar_chamado <id> — só em #chat-suporte"""
    await ctx.message.delete()

    if ctx.channel.name != "chat-suporte":
        try:
            await ctx.author.send("❌ Use `!fechar_chamado` apenas no canal `#chat-suporte`.")
        except discord.Forbidden:
            pass
        return

    success, msg, ticket = await ticket_service.close_ticket(
        ticket_id=ticket_id,
        discord_id=str(ctx.author.id),
        guild_id=ctx.guild.id,
    )

    if not success:
        try:
            await ctx.author.send(f"❌ {msg}")
        except discord.Forbidden:
            pass
        return

    await post_or_update_card(ticket, ctx.guild, ctx._state._get_client())

    try:
        await ctx.author.send(
            f"✅ Chamado `{ticket_id}` fechado com sucesso."
        )
    except discord.Forbidden:
        pass


async def cmd_concluir_chamado(ctx, ticket_id: str):
    """!concluir_chamado <id> — só em #chat-chamados"""
    await ctx.message.delete()

    if ctx.channel.name != "chat-chamados":
        try:
            await ctx.author.send(
                f"❌ Use `!concluir_chamado` apenas no canal `#chat-chamados`."
            )
        except discord.Forbidden:
            pass
        return

    is_admin = ctx.author.guild_permissions.administrator

    success, msg, ticket = await ticket_service.resolve_ticket(
        ticket_id=ticket_id,
        atendente_id=str(ctx.author.id),
        guild_id=ctx.guild.id,
        is_admin=is_admin,
    )

    if not success:
        try:
            await ctx.author.send(f"❌ {msg}")
        except discord.Forbidden:
            pass
        return

    await post_or_update_card(ticket, ctx.guild, ctx._state._get_client())

    # Notifica o membro via DM
    guild  = ctx.guild
    membro = guild.get_member(int(ticket.discord_id))
    if membro:
        try:
            await membro.send(
                f"✅ Seu chamado `{ticket.ticket_id}` foi resolvido pela equipe de suporte!\n"
                f"Se precisar de mais ajuda, abra um novo chamado em `#suporte`."
            )
        except discord.Forbidden:
            pass

    try:
        await ctx.author.send(
            f"✅ Chamado `{ticket_id}` marcado como resolvido."
        )
    except discord.Forbidden:
        pass
