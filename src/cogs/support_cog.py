"""
SupportCog — Sistema de suporte com canal privado por ticket.
"""
from __future__ import annotations
import re
import discord
from discord.ext import commands
from discord import app_commands

from services.channel_service import CATEGORY_SUPORTE
from services.ticket_service import ticket_service, SUPORTE_ROLE_NAME
from utils.logger import logger

THEME_COLOR = 0xFFD54F


def _sanitize_channel_name(name: str) -> str:
    """Remove caracteres inválidos para nomes de canal do Discord."""
    sanitized = re.sub(r"[^a-z0-9\-]", "", name.lower().replace(" ", "-"))
    return sanitized[:80] or "user"


class SupportCog(commands.Cog, name="Suporte"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── !chamado ──────────────────────────────────────────────────

    @commands.command(name="chamado")
    async def chamado(self, ctx: commands.Context):
        tickets = await ticket_service.get_user_tickets(str(ctx.author.id), ctx.guild.id)
        abertos = [t for t in tickets if t.status in ("aberto", "pendente")]
        if not abertos:
            await ctx.reply("Você não tem chamados abertos no momento.")
            return
        embed = discord.Embed(title="Chamados Abertos", color=THEME_COLOR)
        for t in abertos[:10]:
            embed.add_field(
                name=f"`{t.ticket_id}` — {t.categoria}",
                value=t.descricao[:80] + ("..." if len(t.descricao) > 80 else ""),
                inline=False
            )
        await ctx.reply(embed=embed)

    # ── /rc — renomear canal do ticket ────────────────────────────

    @app_commands.command(name="rc", description="Renomeia o canal do ticket com um prefixo de contexto")
    @app_commands.describe(prefixo="Prefixo descritivo, ex: problema_pix")
    @app_commands.checks.has_any_role("Support", "Admin")
    async def rc(self, interaction: discord.Interaction, prefixo: str):
        """
        Renomeia o canal atual (deve ser chamado de dentro de um canal suporte-*)
        para suporte-{prefixo}-{username_do_jogador}.
        """
        channel = interaction.channel

        # Verifica se o canal atual é um canal de ticket
        if not channel.name.startswith("suporte-"):
            await interaction.response.send_message(
                "Este comando deve ser usado dentro de um canal de ticket (`suporte-*`).",
                ephemeral=True
            )
            return

        # Busca o ticket pelo channel_id para obter o username do jogador
        ticket = await ticket_service.get_ticket_by_channel_id(channel.id)
        if not ticket:
            await interaction.response.send_message(
                "Nenhum ticket encontrado para este canal.", ephemeral=True
            )
            return

        safe_prefix   = _sanitize_channel_name(prefixo)
        safe_username = _sanitize_channel_name(ticket.username or str(ticket.discord_id))
        new_name      = f"suporte-{safe_prefix}-{safe_username}"[:100]

        await channel.edit(name=new_name)
        await interaction.response.send_message(
            f"✅ Canal renomeado para `{new_name}`.", ephemeral=True
        )

    # ── !help ──────────────────────────────────────────────────────

    @commands.command(name="help")
    async def help_cmd(self, ctx: commands.Context):
        embed = discord.Embed(title="Comandos", color=THEME_COLOR)
        embed.add_field(
            name="Suporte (jogador)",
            value="`!chamado` — ver chamados abertos",
            inline=False
        )
        embed.add_field(
            name="Suporte (atendente)",
            value=(
                "Assumir / Fechar: use os botões dentro do canal `suporte-*`\n"
                "`/rc <prefixo>` — renomeia o canal do ticket com contexto"
            ),
            inline=False
        )
        embed.add_field(name="Partidas", value="`!cancelar`  `/perfil`",  inline=False)
        embed.add_field(name="Análise",  value="`/solicitar_analise`",    inline=False)
        embed.set_footer(text="!help_adm para comandos de administrador")
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SupportCog(bot))