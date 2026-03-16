"""
SupportCog — Sistema de suporte com canal privado por agente.
Roadmap: cada support tem seu canal support-<nome>, jogador é adicionado/removido.
"""
import discord
from discord.ext import commands
from discord import app_commands
from utils.logger import logger


SUPPORT_ROLE_NAME = "Support"
THEME_COLOR = 0xFFD54F


class SupportCog(commands.Cog, name="Suporte"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── !chamado ──────────────────────────────────────────────────
    @commands.command(name="chamado")
    async def chamado(self, ctx: commands.Context):
        from services.ticket_service import ticket_service
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

    # ── !fechar_chamado ────────────────────────────────────────────
    @commands.command(name="fechar_chamado")
    async def fechar_chamado(self, ctx: commands.Context, ticket_id: str):
        from services.ticket_service import ticket_service
        from views.ticket_view import post_or_update_card
        success, msg, ticket = await ticket_service.close_ticket(
            ticket_id, str(ctx.author.id), ctx.guild.id
        )
        if not success:
            await ctx.reply(f"❌ {msg}")
            return
        await ctx.reply(f"✅ Chamado `{ticket_id}` fechado.")
        await post_or_update_card(ticket, ctx.guild, self.bot)

    # ── !criar_canal_suporte ───────────────────────────────────────
    @commands.command(name="criar_canal_suporte")
    @commands.has_permissions(administrator=True)
    async def criar_canal_suporte(self, ctx: commands.Context, member: discord.Member = None):
        target       = member or ctx.author
        channel_name = f"support-{target.name.lower().replace(' ', '-')}"

        existing = discord.utils.get(ctx.guild.text_channels, name=channel_name)
        if existing:
            await ctx.reply(f"Canal {existing.mention} já existe.")
            return

        support_role = discord.utils.get(ctx.guild.roles, name=SUPPORT_ROLE_NAME)
        category     = discord.utils.get(ctx.guild.categories, name="🎫 SUPORTE")

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            target:                 discord.PermissionOverwrite(read_messages=True, send_messages=True),
            ctx.guild.me:           discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ch = await ctx.guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"Canal privado de suporte — {target.display_name}"
        )
        await ctx.reply(f"✅ Canal {ch.mention} criado para {target.mention}.")

    # ── /renomear_canal ────────────────────────────────────────────
    @app_commands.command(name="renomear_canal", description="Renomeia seu canal de suporte com o assunto")
    @app_commands.describe(sufixo="Sufixo descritivo, ex: problema_pagamento")
    @app_commands.checks.has_any_role("Support", "Admin")
    async def renomear_canal(self, interaction: discord.Interaction, sufixo: str):
        agent_ch_name = f"support-{interaction.user.name.lower()}"
        channel = discord.utils.get(interaction.guild.text_channels, name=agent_ch_name)
        if not channel:
            await interaction.response.send_message(
                f"Seu canal `{agent_ch_name}` não foi encontrado.", ephemeral=True
            )
            return
        new_name = f"support-{interaction.user.name.lower()}-{sufixo.replace(' ', '_')}"[:100]
        await channel.edit(name=new_name)
        await interaction.response.send_message(f"✅ Canal renomeado para `{new_name}`.", ephemeral=True)

    # ── !help ──────────────────────────────────────────────────────
    @commands.command(name="help")
    async def help_cmd(self, ctx: commands.Context):
        embed = discord.Embed(title="Comandos", color=THEME_COLOR)
        embed.add_field(name="Suporte",  value="`!chamado`  `!fechar_chamado <ID>`", inline=False)
        embed.add_field(name="Partidas", value="`!cancelar`  `/perfil`",             inline=False)
        embed.add_field(name="Análise",  value="`/solicitar_analise`",               inline=False)
        embed.set_footer(text="!help_adm para comandos de administrador")
        await ctx.reply(embed=embed)

    # ❌ on_command_error REMOVIDO — centralizado no admin_cog


async def setup(bot: commands.Bot):
    await bot.add_cog(SupportCog(bot))
