"""
ticket_view.py — Sistema de tickets com SELECT MENU + BUTTON (roadmap).
Substitui o modal direto por: select categoria → botão abrir → confirmação.
"""
from __future__ import annotations
import discord
from datetime import datetime
from typing import Optional

from models.ticket import Ticket
from services.ticket_service import ticket_service, CHAMADOS_CHANNEL_NAME, SUPORTE_ROLE_NAME
from utils.logger import logger

# Cor tema
THEME_COLOR = 0xFFD54F
THEME_COLOR_2 = 0xFFA726

CATEGORIAS = ["Bug", "Pagamento", "Dúvida", "Conta", "Partida", "Outro"]


# ─────────────────────────────────────────────
# Helpers de embed
# ─────────────────────────────────────────────

def build_support_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Suporte",
        description=(
            "Selecione a categoria do seu problema no menu abaixo\n"
            "e clique em **Abrir Ticket** para entrar em contato com nossa equipe."
        ),
        color=THEME_COLOR
    )
    embed.add_field(
        name="Categorias",
        value="\n".join(f"• {c}" for c in CATEGORIAS),
        inline=False
    )
    embed.set_footer(text="Responderemos o mais breve possível")
    return embed


def build_card_embed(ticket: Ticket, guild: discord.Guild) -> discord.Embed:
    color_map = {
        Ticket.STATUS_ABERTO:    discord.Color.from_rgb(255, 213, 79),
        Ticket.STATUS_PENDENTE:  discord.Color.from_rgb(255, 167, 38),
        Ticket.STATUS_RESOLVIDO: discord.Color.green(),
        Ticket.STATUS_FECHADO:   discord.Color.red(),
    }
    status_label = {
        Ticket.STATUS_ABERTO:    "Aberto",
        Ticket.STATUS_PENDENTE:  "Em atendimento",
        Ticket.STATUS_RESOLVIDO: "Resolvido",
        Ticket.STATUS_FECHADO:   "Fechado",
    }
    embed = discord.Embed(
        title=f"Ticket {ticket.ticket_id}",
        color=color_map.get(ticket.status, discord.Color.greyple())
    )
    embed.add_field(name="Usuário",    value=f"<@{ticket.discord_id}>",                   inline=True)
    embed.add_field(name="Categoria",  value=ticket.categoria,                             inline=True)
    embed.add_field(name="Status",     value=status_label.get(ticket.status, ticket.status), inline=True)
    embed.add_field(name="Descrição",  value=ticket.descricao[:1024],                     inline=False)
    if ticket.atendente_id:
        embed.add_field(name="Atendente", value=f"<@{ticket.atendente_id}>",              inline=True)
    ts = ticket.resolved_at or ticket.closed_at
    if ts:
        embed.add_field(name="Encerrado em", value=ts.strftime("%d/%m/%Y %H:%M"),         inline=True)
    embed.set_footer(text=f"Aberto em {ticket.created_at.strftime('%d/%m/%Y %H:%M')}")
    return embed


async def post_or_update_card(
    ticket: Ticket,
    guild: discord.Guild,
    bot: discord.Client,
) -> Optional[discord.Message]:
    chamados_channel = discord.utils.get(guild.text_channels, name=CHAMADOS_CHANNEL_NAME)
    if not chamados_channel:
        return None

    if ticket.card_message_id:
        try:
            old = await chamados_channel.fetch_message(ticket.card_message_id)
            await old.delete()
        except Exception:
            pass

    embed = build_card_embed(ticket, guild)
    view  = SupportCardView() if ticket.status == Ticket.STATUS_ABERTO else None
    msg   = await chamados_channel.send(embed=embed, view=view)
    await ticket_service.save_card_message_id(ticket.ticket_id, msg.id)
    return msg


# ─────────────────────────────────────────────
# Painel principal — SELECT + BUTTON
# ─────────────────────────────────────────────

class TicketPanelView(discord.ui.View):
    """Painel fixo em #chat-suporte — select de categoria + botão abrir."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        cls=discord.ui.Select,
        placeholder="Selecione a categoria do problema...",
        custom_id="ticket_category_select",
        options=[
            discord.SelectOption(label=c, value=c, emoji="📋")
            for c in CATEGORIAS
        ]
    )
    async def select_categoria(self, interaction: discord.Interaction, select: discord.ui.Select):
        # Apenas confirma seleção — o usuário ainda precisa clicar em Abrir
        await interaction.response.send_message(
            f"Categoria selecionada: **{select.values[0]}**\n"
            "Agora descreva brevemente o problema e clique em **Abrir Ticket**.",
            ephemeral=True,
            view=TicketOpenView(select.values[0], interaction.user)
        )

    @discord.ui.button(
        label="Ver Histórico",
        style=discord.ButtonStyle.secondary,
        custom_id="view_ticket_history",
        emoji="📂"
    )
    async def view_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        tickets = await ticket_service.get_user_tickets(str(interaction.user.id), interaction.guild.id)
        if not tickets:
            await interaction.followup.send("Nenhum chamado encontrado no seu histórico.", ephemeral=True)
            return

        status_emoji = {
            Ticket.STATUS_ABERTO: "🟡", Ticket.STATUS_PENDENTE: "🔵",
            Ticket.STATUS_RESOLVIDO: "✅", Ticket.STATUS_FECHADO: "⛔",
        }
        embed = discord.Embed(title="Seus Chamados", color=THEME_COLOR)
        for t in tickets[:10]:
            emoji = status_emoji.get(t.status, "❓")
            embed.add_field(
                name=f"{emoji} `{t.ticket_id}` — {t.categoria}",
                value=(
                    f"Status: {t.status.capitalize()}\n"
                    f"Aberto em: {t.created_at.strftime('%d/%m/%Y %H:%M')}"
                    + (f"\nFechar: `!fechar_chamado {t.ticket_id}`" if t.status in Ticket.OPEN_STATUSES else "")
                ),
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)


class TicketOpenView(discord.ui.View):
    """View enviada após seleção de categoria — mostra botão Abrir Ticket."""

    def __init__(self, categoria: str, user: discord.Member):
        super().__init__(timeout=120)
        self.categoria = categoria
        self.user      = user

    @discord.ui.button(label="Abrir Ticket", style=discord.ButtonStyle.success, emoji="🎫")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Este botão não é para você.", ephemeral=True)
            return
        await interaction.response.send_modal(TicketDescricaoModal(self.categoria))


class TicketDescricaoModal(discord.ui.Modal, title="Descreva o problema"):
    descricao = discord.ui.TextInput(
        label="Descrição",
        style=discord.TextStyle.paragraph,
        placeholder="Descreva com detalhes o seu problema...",
        min_length=20,
        max_length=1000,
        required=True,
    )

    def __init__(self, categoria: str):
        super().__init__()
        self.categoria = categoria

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        success, erro, ticket = await ticket_service.create_ticket(
            discord_id=str(interaction.user.id),
            username=interaction.user.display_name,
            guild_id=interaction.guild.id,
            categoria=self.categoria,
            descricao=self.descricao.value,
        )

        if not success:
            await interaction.followup.send(f"❌ {erro}", ephemeral=True)
            return

        await post_or_update_card(ticket, interaction.guild, interaction.client)

        suporte_role = discord.utils.get(interaction.guild.roles, name=SUPORTE_ROLE_NAME)
        chamados     = discord.utils.get(interaction.guild.text_channels, name=CHAMADOS_CHANNEL_NAME)
        if chamados and suporte_role:
            await chamados.send(
                f"{suporte_role.mention} novo chamado de <@{interaction.user.id}>!",
                delete_after=30
            )

        await interaction.followup.send(
            f"✅ Chamado `{ticket.ticket_id}` aberto!\n"
            "Aguarde um atendente. Você será contatado em breve.",
            ephemeral=True
        )


# ─────────────────────────────────────────────
# Card de chamado
# ─────────────────────────────────────────────

class SupportCardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Assumir", style=discord.ButtonStyle.primary,
                       custom_id="assume_ticket_button", emoji="✋")
    async def assume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        suporte_role = discord.utils.get(interaction.guild.roles, name=SUPORTE_ROLE_NAME)
        is_suporte   = suporte_role and suporte_role in interaction.user.roles
        is_admin     = interaction.user.guild_permissions.administrator

        if not is_suporte and not is_admin:
            await interaction.response.send_message(
                "Apenas a equipe de Suporte pode assumir chamados.", ephemeral=True
            )
            return

        await interaction.response.defer()
        ticket = await ticket_service.get_ticket_by_card_message_id(interaction.message.id)
        if not ticket:
            await interaction.followup.send("Chamado não encontrado.", ephemeral=True)
            return

        if ticket.status != Ticket.STATUS_ABERTO:
            await interaction.followup.send(
                f"Este chamado já está `{ticket.status}`.", ephemeral=True
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

        await post_or_update_card(ticket, interaction.guild, interaction.client)

        # Tenta adicionar jogador ao canal privado do suporte
        await _add_player_to_support_channel(interaction.guild, interaction.user, ticket)

        # DM para o suporte
        dm_embed = discord.Embed(
            title=f"Chamado Assumido — {ticket.ticket_id}", color=THEME_COLOR
        )
        dm_embed.add_field(name="Usuário",    value=f"<@{ticket.discord_id}>",    inline=True)
        dm_embed.add_field(name="Categoria",  value=ticket.categoria,             inline=True)
        dm_embed.add_field(name="Descrição",  value=ticket.descricao[:512],       inline=False)
        dm_embed.add_field(
            name="Como atender",
            value=(
                f"O jogador foi adicionado ao seu canal privado de suporte.\n"
                f"Quando resolver, use `!concluir_chamado {ticket.ticket_id}`."
            ),
            inline=False
        )
        try:
            await interaction.user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        await interaction.followup.send(
            f"✅ Chamado `{ticket.ticket_id}` assumido!", ephemeral=True
        )


async def _add_player_to_support_channel(
    guild: discord.Guild,
    support_member: discord.Member,
    ticket: Ticket
):
    """Adiciona o jogador ao canal privado do agente de suporte."""
    try:
        support_ch = discord.utils.get(
            guild.text_channels,
            name=f"support-{support_member.name.lower()}"
        )
        if not support_ch:
            return

        player = guild.get_member(int(ticket.discord_id))
        if player:
            ow = support_ch.overwrites_for(player)
            ow.read_messages  = True
            ow.send_messages  = True
            await support_ch.set_permissions(player, overwrite=ow)
            await support_ch.send(
                f"{player.mention} foi adicionado para atendimento do chamado `{ticket.ticket_id}`.",
                delete_after=5
            )
    except Exception as e:
        logger.warning(f"[Ticket] Erro ao adicionar ao canal de suporte: {e}")


# ─────────────────────────────────────────────
# TicketCardView — compatibilidade com main.py
# ─────────────────────────────────────────────

class TicketCardView(discord.ui.View):
    """Alias persistente — usado no on_ready para registro."""
    def __init__(self, ticket_id: str = "__persistent__"):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id


# ─────────────────────────────────────────────
# Comandos de texto
# ─────────────────────────────────────────────

async def cmd_fechar_chamado(ctx, ticket_id: str):
    await ctx.message.delete()
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
        await ctx.author.send(f"✅ Chamado `{ticket_id}` fechado.")
    except discord.Forbidden:
        pass


async def cmd_concluir_chamado(ctx, ticket_id: str):
    await ctx.message.delete()
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

    # Remove o jogador do canal privado de suporte
    try:
        support_ch = discord.utils.get(
            ctx.guild.text_channels,
            name=f"support-{ctx.author.name.lower()}"
        )
        if support_ch:
            player = ctx.guild.get_member(int(ticket.discord_id))
            if player:
                await support_ch.set_permissions(player, overwrite=None)
    except Exception:
        pass

    guild  = ctx.guild
    membro = guild.get_member(int(ticket.discord_id))
    if membro:
        try:
            await membro.send(
                f"✅ Seu chamado `{ticket.ticket_id}` foi resolvido!\n"
                "Se precisar de mais ajuda, abra um novo ticket em `#chat-suporte`."
            )
        except discord.Forbidden:
            pass
