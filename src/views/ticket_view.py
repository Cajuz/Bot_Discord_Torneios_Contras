# ticket_view.py — Sistema de tickets com SELECT MENU + BUTTON.
from __future__ import annotations
import asyncio
import discord
from typing import Optional

from models.ticket import Ticket
from services.ticket_service import ticket_service, CHAMADOS_CHANNEL_NAME, SUPORTE_ROLE_NAME
from services.channel_service import SOLICITAR_SUPORTE_CHANNEL, CATEGORY_SUPORTE
from utils.logger import logger


THEME_COLOR   = 0xFFD54F
THEME_COLOR_2 = 0xFFA726


CATEGORIAS = ["Bug", "Pagamento", "Dúvida"]


# ─────────────────────────────────────────────
# Helpers de embed
# ─────────────────────────────────────────────

def build_support_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎫 Central de Suporte",
        description=(
            "Selecione a categoria do seu problema no menu abaixo\n"
            "e clique em **Abrir Ticket** para entrar em contato com nossa equipe."
        ),
        color=THEME_COLOR
    )
    embed.add_field(
        name="📂 Categorias",
        value=(
            "• ❖  Pagamento\n"
            "• 💥 Bug\n"
            "• ❓ Dúvida\n"
        ),
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
        Ticket.STATUS_ABERTO:    "🟡 Aberto",
        Ticket.STATUS_PENDENTE:  "🔵 Em atendimento",
        Ticket.STATUS_RESOLVIDO: "✅ Resolvido",
        Ticket.STATUS_FECHADO:   "⛔ Fechado",
    }
    embed = discord.Embed(
        title=f"Ticket {ticket.ticket_id}",
        color=color_map.get(ticket.status, discord.Color.greyple())
    )
    embed.add_field(name="Usuário",   value=f"<@{ticket.discord_id}>",                      inline=True)
    embed.add_field(name="Categoria", value=ticket.categoria,                                inline=True)
    embed.add_field(name="Status",    value=status_label.get(ticket.status, ticket.status),  inline=True)
    embed.add_field(name="Descrição", value=ticket.descricao[:1024],                         inline=False)
    if ticket.atendente_id:
        embed.add_field(name="Atendente", value=f"<@{ticket.atendente_id}>", inline=True)
    ts = ticket.resolved_at or ticket.closed_at
    if ts:
        embed.add_field(name="Encerrado em", value=ts.strftime("%d/%m/%Y %H:%M"), inline=True)
    embed.set_footer(text=f"Aberto em {ticket.created_at.strftime('%d/%m/%Y %H:%M')}")
    return embed


def build_channel_embed(ticket: Ticket, status: str = "aguardando") -> discord.Embed:
    """
    Embed fixo postado dentro do canal suporte-{username}.
    status: 'aguardando' | 'atendimento' | 'resolvido' | 'fechado'
    """
    color_map = {
        "aguardando":  THEME_COLOR,
        "atendimento": THEME_COLOR_2,
        "resolvido":   0x57F287,
        "fechado":     0xED4245,
    }
    status_label = {
        "aguardando":  "🟡 Aguardando atendimento",
        "atendimento": "🔵 Em atendimento",
        "resolvido":   "✅ Resolvido",
        "fechado":     "⛔ Fechado",
    }

    embed = discord.Embed(
        title=f"🎫 Chamado {ticket.ticket_id}",
        color=color_map.get(status, THEME_COLOR)
    )

    embed.add_field(name="Jogador",   value=f"<@{ticket.discord_id}>", inline=True)
    embed.add_field(name="Categoria", value=ticket.categoria,           inline=True)
    embed.add_field(name="Status",    value=status_label[status],       inline=True)

    embed.add_field(name="Descrição", value=ticket.descricao[:500], inline=False)

    if ticket.atendente_id:
        embed.add_field(name="Atendente", value=f"<@{ticket.atendente_id}>", inline=True)

    if status == "aguardando":
        acoes = (
            "◀ **Assumir** — pega o chamado e libera escrita no canal\n"
            "✅ **Concluir** — marca como resolvido e encerra\n"
            "❌ **Fechar** — encerra sem marcar como resolvido"
        )
        embed.add_field(name="⚙️ Ações disponíveis", value=acoes, inline=False)
        embed.set_footer(text="Apenas Suporte/Admin pode usar os botões abaixo.")

    elif status == "atendimento":
        acoes = (
            "✅ **Concluir** — marca como resolvido e encerra\n"
            "❌ **Fechar** — encerra sem marcar como resolvido"
        )
        embed.add_field(name="⚙️ Ações disponíveis", value=acoes, inline=False)
        embed.set_footer(text="Chamado em atendimento — use os botões abaixo para encerrar.")

    else:
        embed.set_footer(text=f"Chamado encerrado — {ticket.ticket_id}")

    return embed


async def post_or_update_card(
    ticket: Ticket,
    guild: discord.Guild,
    bot: discord.Client,
) -> Optional[discord.Message]:
    chamados_channel = discord.utils.get(guild.text_channels, name=CHAMADOS_CHANNEL_NAME)
    if not chamados_channel:
        return None

    embed = build_card_embed(ticket, guild)

    if ticket.card_message_id:
        try:
            old = await chamados_channel.fetch_message(ticket.card_message_id)
            await old.edit(embed=embed, view=None)
            return old
        except discord.NotFound:
            pass

    msg = await chamados_channel.send(embed=embed)
    await ticket_service.save_card_message_id(ticket.ticket_id, msg.id)
    return msg


# ─────────────────────────────────────────────
# Painel principal — SELECT + BUTTON
# ─────────────────────────────────────────────

class TicketPanelView(discord.ui.View):

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
            Ticket.STATUS_ABERTO:    "🟡",
            Ticket.STATUS_PENDENTE:  "🔵",
            Ticket.STATUS_RESOLVIDO: "✅",
            Ticket.STATUS_FECHADO:   "⛔",
        }
        embed = discord.Embed(title="Seus Chamados", color=THEME_COLOR)
        for t in tickets[:10]:
            emoji = status_emoji.get(t.status, "❓")
            embed.add_field(
                name=f"{emoji} `{t.ticket_id}` — {t.categoria}",
                value=(
                    f"Status: {t.status.capitalize()}\n"
                    f"Aberto em: {t.created_at.strftime('%d/%m/%Y %H:%M')}"
                ),
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
# View de abertura — enviada ao usuário após selecionar categoria
# ─────────────────────────────────────────────

class TicketOpenView(discord.ui.View):

    def __init__(self, categoria: str, user: discord.Member):
        super().__init__(timeout=300)
        self.categoria = categoria
        self.user      = user

    async def on_timeout(self):
        pass

    @discord.ui.button(label="Abrir Ticket", style=discord.ButtonStyle.secondary, emoji="🎫")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Este botão não é para você.", ephemeral=True)
            return
        await interaction.response.send_modal(TicketDescricaoModal(self.categoria))


# ─────────────────────────────────────────────
# Modal de descrição
# ─────────────────────────────────────────────

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

        support_ch = await _create_ticket_channel(interaction.guild, interaction.user, ticket)

        if support_ch:
            await ticket_service.save_channel_id(ticket.ticket_id, support_ch.id)
            ticket.channel_id = support_ch.id

            channel_embed = build_channel_embed(ticket, status="aguardando")
            await support_ch.send(
                embed=channel_embed,
                view=TicketChannelView(ticket_id=ticket.ticket_id)
            )

        await post_or_update_card(ticket, interaction.guild, interaction.client)

        await interaction.followup.send(
            f"✅ Chamado `{ticket.ticket_id}` aberto na categoria **{self.categoria}**!\n"
            f"Canal criado: {support_ch.mention if support_ch else '(erro ao criar canal)'}\n"
            "Aguarde um atendente.",
            ephemeral=True
        )


# ─────────────────────────────────────────────
# View do canal do ticket — Assumir + Concluir + Fechar
# ─────────────────────────────────────────────

class TicketChannelView(discord.ui.View):
    """View persistente postada dentro do canal suporte-{username}."""

    def __init__(self, ticket_id: str = "__persistent__"):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    def _is_suporte_or_admin(self, member: discord.Member) -> bool:
        suporte_role = discord.utils.get(member.guild.roles, name=SUPORTE_ROLE_NAME)
        return member.guild_permissions.administrator or (suporte_role and suporte_role in member.roles)

    # ── ◀ Assumir ────────────────────────────────────────────
    @discord.ui.button(
        label="Assumir",
        style=discord.ButtonStyle.secondary,
        custom_id="channel_assume_ticket",
        emoji="◀"
    )
    async def assume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_suporte_or_admin(interaction.user):
            await interaction.response.send_message(
                "Apenas a equipe de Suporte pode assumir chamados.", ephemeral=True
            )
            return

        await interaction.response.defer()

        ticket = await ticket_service.get_ticket_by_channel_id(interaction.channel.id)
        if not ticket:
            await interaction.followup.send("Chamado não encontrado para este canal.", ephemeral=True)
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

        try:
            ow = interaction.channel.overwrites_for(interaction.user)
            ow.send_messages = True
            await interaction.channel.set_permissions(interaction.user, overwrite=ow)
        except Exception as e:
            logger.warning(f"[Ticket] Erro ao dar permissão ao suporte: {e}")

        new_view = _build_post_assume_view(ticket.ticket_id)
        new_embed = build_channel_embed(ticket, status="atendimento")
        await interaction.message.edit(embed=new_embed, view=new_view)

        await post_or_update_card(ticket, interaction.guild, interaction.client)

        await interaction.followup.send(
            f"◀ Você assumiu o chamado `{ticket.ticket_id}`! Pode enviar mensagens neste canal.",
            ephemeral=True
        )

    # ── ✅ Concluir ───────────────────────────────────────────
    @discord.ui.button(
        label="Concluir",
        style=discord.ButtonStyle.success,
        custom_id="channel_resolve_ticket",
        emoji="✅"
    )
    async def resolve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_suporte_or_admin(interaction.user):
            await interaction.response.send_message(
                "Apenas a equipe de Suporte pode concluir chamados.", ephemeral=True
            )
            return

        await interaction.response.defer()

        ticket = await ticket_service.get_ticket_by_channel_id(interaction.channel.id)
        if not ticket:
            await interaction.followup.send("Chamado não encontrado para este canal.", ephemeral=True)
            return

        success, msg, ticket = await ticket_service.resolve_ticket(
            ticket_id=ticket.ticket_id,
            guild_id=interaction.guild.id,
        )
        if not success:
            await interaction.followup.send(f"❌ {msg}", ephemeral=True)
            return

        await post_or_update_card(ticket, interaction.guild, interaction.client)

        player = interaction.guild.get_member(int(ticket.discord_id))
        if player:
            try:
                dm_embed = discord.Embed(
                    title=f"✅ Chamado Resolvido — {ticket.ticket_id}",
                    description=(
                        f"Seu chamado na categoria **{ticket.categoria}** foi marcado como **resolvido**.\n"
                        f"Obrigado por entrar em contato! Se precisar de mais ajuda, abra um novo ticket em `#{SOLICITAR_SUPORTE_CHANNEL}`."
                    ),
                    color=discord.Color.green()
                )
                await player.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        final_embed = build_channel_embed(ticket, status="resolvido")
        await interaction.message.edit(embed=final_embed, view=None)

        await interaction.followup.send(
            f"✅ Chamado `{ticket.ticket_id}` concluído. Canal será deletado em 5 segundos.",
            ephemeral=True
        )

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket {ticket.ticket_id} resolvido.")
        except Exception as e:
            logger.warning(f"[Ticket] Erro ao deletar canal: {e}")

    # ── ❌ Fechar ─────────────────────────────────────────────
    @discord.ui.button(
        label="Fechar",
        style=discord.ButtonStyle.danger,
        custom_id="channel_close_ticket",
        emoji="❌"
    )
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_suporte_or_admin(interaction.user):
            await interaction.response.send_message(
                "Apenas a equipe de Suporte pode fechar chamados.", ephemeral=True
            )
            return

        await interaction.response.defer()

        ticket = await ticket_service.get_ticket_by_channel_id(interaction.channel.id)
        if not ticket:
            await interaction.followup.send("Chamado não encontrado para este canal.", ephemeral=True)
            return

        success, msg, ticket = await ticket_service.close_ticket(
            ticket_id=ticket.ticket_id,
            guild_id=interaction.guild.id,
        )
        if not success:
            await interaction.followup.send(f"❌ {msg}", ephemeral=True)
            return

        await post_or_update_card(ticket, interaction.guild, interaction.client)

        player = interaction.guild.get_member(int(ticket.discord_id))
        if player:
            try:
                dm_embed = discord.Embed(
                    title=f"Chamado Encerrado — {ticket.ticket_id}",
                    description=(
                        f"Seu chamado na categoria **{ticket.categoria}** foi encerrado.\n"
                        f"Se precisar de mais ajuda, abra um novo ticket em `#{SOLICITAR_SUPORTE_CHANNEL}`."
                    ),
                    color=discord.Color.red()
                )
                await player.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        final_embed = build_channel_embed(ticket, status="fechado")
        await interaction.message.edit(embed=final_embed, view=None)

        await interaction.followup.send(
            f"✅ Chamado `{ticket.ticket_id}` fechado. Canal será deletado em 5 segundos.",
            ephemeral=True
        )

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket {ticket.ticket_id} fechado.")
        except Exception as e:
            logger.warning(f"[Ticket] Erro ao deletar canal: {e}")


# ─────────────────────────────────────────────
# View pós-assumir — apenas Concluir + Fechar
# ─────────────────────────────────────────────

def _build_post_assume_view(ticket_id: str) -> discord.ui.View:
    """Retorna View sem o botão Assumir, usada após assumir o chamado."""

    class PostAssumeView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        def _is_suporte_or_admin(self, member: discord.Member) -> bool:
            suporte_role = discord.utils.get(member.guild.roles, name=SUPORTE_ROLE_NAME)
            return member.guild_permissions.administrator or (suporte_role and suporte_role in member.roles)

        @discord.ui.button(
            label="Concluir",
            style=discord.ButtonStyle.success,
            custom_id="channel_resolve_ticket",
            emoji="✅"
        )
        async def resolve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not self._is_suporte_or_admin(interaction.user):
                await interaction.response.send_message(
                    "Apenas a equipe de Suporte pode concluir chamados.", ephemeral=True
                )
                return
            await interaction.response.defer()
            ticket = await ticket_service.get_ticket_by_channel_id(interaction.channel.id)
            if not ticket:
                await interaction.followup.send("Chamado não encontrado.", ephemeral=True)
                return
            success, msg, ticket = await ticket_service.resolve_ticket(
                ticket_id=ticket.ticket_id, guild_id=interaction.guild.id
            )
            if not success:
                await interaction.followup.send(f"❌ {msg}", ephemeral=True)
                return
            await post_or_update_card(ticket, interaction.guild, interaction.client)
            player = interaction.guild.get_member(int(ticket.discord_id))
            if player:
                try:
                    dm_embed = discord.Embed(
                        title=f"✅ Chamado Resolvido — {ticket.ticket_id}",
                        description=(
                            f"Seu chamado na categoria **{ticket.categoria}** foi marcado como **resolvido**.\n"
                            f"Obrigado! Se precisar de mais ajuda, abra um novo ticket em `#{SOLICITAR_SUPORTE_CHANNEL}`."
                        ),
                        color=discord.Color.green()
                    )
                    await player.send(embed=dm_embed)
                except discord.Forbidden:
                    pass
            final_embed = build_channel_embed(ticket, status="resolvido")
            await interaction.message.edit(embed=final_embed, view=None)
            await interaction.followup.send(
                f"✅ Chamado `{ticket.ticket_id}` concluído. Canal será deletado em 5 segundos.",
                ephemeral=True
            )
            await asyncio.sleep(5)
            try:
                await interaction.channel.delete(reason=f"Ticket {ticket.ticket_id} resolvido.")
            except Exception as e:
                logger.warning(f"[Ticket] Erro ao deletar canal: {e}")

        @discord.ui.button(
            label="Fechar",
            style=discord.ButtonStyle.danger,
            custom_id="channel_close_ticket",
            emoji="❌"
        )
        async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not self._is_suporte_or_admin(interaction.user):
                await interaction.response.send_message(
                    "Apenas a equipe de Suporte pode fechar chamados.", ephemeral=True
                )
                return
            await interaction.response.defer()
            ticket = await ticket_service.get_ticket_by_channel_id(interaction.channel.id)
            if not ticket:
                await interaction.followup.send("Chamado não encontrado.", ephemeral=True)
                return
            success, msg, ticket = await ticket_service.close_ticket(
                ticket_id=ticket.ticket_id, guild_id=interaction.guild.id
            )
            if not success:
                await interaction.followup.send(f"❌ {msg}", ephemeral=True)
                return
            await post_or_update_card(ticket, interaction.guild, interaction.client)
            player = interaction.guild.get_member(int(ticket.discord_id))
            if player:
                try:
                    dm_embed = discord.Embed(
                        title=f"Chamado Encerrado — {ticket.ticket_id}",
                        description=(
                            f"Seu chamado na categoria **{ticket.categoria}** foi encerrado.\n"
                            f"Se precisar de mais ajuda, abra um novo ticket em `#{SOLICITAR_SUPORTE_CHANNEL}`."
                        ),
                        color=discord.Color.red()
                    )
                    await player.send(embed=dm_embed)
                except discord.Forbidden:
                    pass
            final_embed = build_channel_embed(ticket, status="fechado")
            await interaction.message.edit(embed=final_embed, view=None)
            await interaction.followup.send(
                f"✅ Chamado `{ticket.ticket_id}` fechado. Canal será deletado em 5 segundos.",
                ephemeral=True
            )
            await asyncio.sleep(5)
            try:
                await interaction.channel.delete(reason=f"Ticket {ticket.ticket_id} fechado.")
            except Exception as e:
                logger.warning(f"[Ticket] Erro ao deletar canal: {e}")

    return PostAssumeView()


# ─────────────────────────────────────────────
# Helper — criar canal suporte-{username}
# ─────────────────────────────────────────────

async def _create_ticket_channel(
    guild: discord.Guild,
    player: discord.Member,
    ticket: Ticket,
) -> Optional[discord.TextChannel]:
    try:
        safe_username = player.name.lower().replace(" ", "-")
        ch_name = f"suporte-{safe_username}"

        category     = discord.utils.get(guild.categories, name=CATEGORY_SUPORTE)
        suporte_role = discord.utils.get(guild.roles, name=SUPORTE_ROLE_NAME)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            player:             discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me:           discord.PermissionOverwrite(
                read_messages=True, send_messages=True,
                manage_messages=True, manage_channels=True
            ),
        }
        if suporte_role:
            overwrites[suporte_role] = discord.PermissionOverwrite(
                read_messages=True, send_messages=False
            )

        ch = await guild.create_text_channel(
            name=ch_name,
            category=category,
            overwrites=overwrites,
            topic=f"Chamado {ticket.ticket_id} — {player.display_name} | {ticket.categoria}"
        )
        logger.info(f"[Ticket] Canal criado: #{ch_name} para ticket {ticket.ticket_id}")
        return ch
    except Exception as e:
        logger.warning(f"[Ticket] Erro ao criar canal do ticket: {e}")
        return None


# ─────────────────────────────────────────────
# Aliases persistentes para main.py
# ─────────────────────────────────────────────

class TicketCardView(discord.ui.View):
    """Alias persistente — mantido para compatibilidade com main.py."""
    def __init__(self, ticket_id: str = "__persistent__"):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id


class SupportCardView(discord.ui.View):
    """Alias persistente — mantido para compatibilidade com main.py. Card sem botões."""
    def __init__(self):
        super().__init__(timeout=None)
