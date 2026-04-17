"""
MediatorCog — Comandos de mediadores.
Roadmap: /silence implementado, !addmediador / !removemediador / !fila.
"""
import discord
from discord.ext import commands
from discord import app_commands
from utils.logger import logger
from utils.datetime_utils import utcnow


THEME_COLOR = 0xFFD54F


class MediatorCog(commands.Cog, name="Mediador"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── !addmediador ───────────────────────────────────────────────
    @commands.command(name="addmediador")
    @commands.has_permissions(administrator=True)
    async def addmediador(self, ctx: commands.Context, member: discord.Member):
        from services.mediator_queue import mediator_queue
        result = await mediator_queue.add_mediator(str(member.id), member.name)

        role = discord.utils.get(ctx.guild.roles, name="Controller")
        if role and role not in member.roles:
            await member.add_roles(role, reason="Adicionado como mediador")

        pos = result.position if result else "?"
        await ctx.reply(f"✅ {member.mention} adicionado como mediador! Posição: `{pos}`")

    # ── !removemediador ────────────────────────────────────────────
    @commands.command(name="removemediador")
    @commands.has_permissions(administrator=True)
    async def removemediador(self, ctx: commands.Context, member: discord.Member):
        from services.mediator_queue import mediator_queue
        await mediator_queue.remove_mediador(str(member.id))

        role = discord.utils.get(ctx.guild.roles, name="Controller")
        if role and role in member.roles:
            await member.remove_roles(role, reason="Removido como mediador")

        await ctx.reply(f"✅ {member.mention} removido da fila de mediadores.")

    # ── !fila ──────────────────────────────────────────────────────
    @commands.command(name="fila")
    @commands.has_permissions(administrator=True)
    async def fila(self, ctx: commands.Context):
        from services.mediator_queue import mediator_queue
        stats = await mediator_queue.get_queue_stats()
        embed = discord.Embed(title="Fila de Mediadores", color=THEME_COLOR)
        embed.add_field(name="Ativos",  value=f"`{stats['total_active']}`",  inline=True)
        embed.add_field(name="Na fila", value=f"`{len(stats['mediators'])}`", inline=True)
        if stats["mediators"]:
            lines = []
            for m in stats["mediators"]:
                status = "✅" if m["can_mediate"] else "⏸️"
                lines.append(f"`{m['position']}.` {status} **{m['username']}** — {m['total_matches']} partidas")
            embed.add_field(name="Mediadores", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Mediadores", value="Nenhum na fila.", inline=False)
        await ctx.reply(embed=embed)

    # ── /silence ───────────────────────────────────────────────────
    @app_commands.command(name="silence", description="Silencia um jogador por X segundos")
    @app_commands.describe(membro="Jogador a silenciar", segundos="Duração (máx 300)", motivo="Motivo")
    @app_commands.checks.has_any_role("Controller", "Mediador", "Mediator")
    async def silence(
        self, interaction: discord.Interaction,
        membro: discord.Member, segundos: int = 30, motivo: str = "Comportamento inadequado"
    ):
        await interaction.response.defer(ephemeral=True)
        if not 1 <= segundos <= 300:
            await interaction.followup.send("Duração entre 1 e 300 segundos.", ephemeral=True)
            return

        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.followup.send("Use dentro de um canal ou thread.", ephemeral=True)
            return

        try:
            overwrite = channel.overwrites_for(membro)
            overwrite.send_messages = False
            await channel.set_permissions(
                membro, overwrite=overwrite,
                reason=f"Silenciado por {interaction.user.name}: {motivo}"
            )
            embed = discord.Embed(
                title="Silenciado",
                description=f"{membro.mention} silenciado por **{segundos}s**.",
                color=THEME_COLOR
            )
            embed.add_field(name="Motivo",   value=motivo,                   inline=False)
            embed.add_field(name="Mediador", value=interaction.user.mention, inline=True)
            embed.set_footer(text=f"Permissão restaurada em {segundos}s")
            await channel.send(embed=embed)
            await interaction.followup.send(f"✅ {membro.mention} silenciado por {segundos}s.", ephemeral=True)

            import asyncio
            await asyncio.sleep(segundos)
            overwrite.send_messages = None
            await channel.set_permissions(membro, overwrite=overwrite, reason="Silenciamento expirado")

        except discord.Forbidden:
            await interaction.followup.send("Sem permissão para silenciar.", ephemeral=True)
        except Exception as e:
            logger.error(f"[silence] {e}")
            await interaction.followup.send("Erro ao silenciar.", ephemeral=True)

    @silence.error
    async def silence_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingAnyRole):
            await interaction.response.send_message(
                "Apenas mediadores podem usar este comando.", ephemeral=True
            )
    
        
async def setup(bot: commands.Bot):
    await bot.add_cog(MediatorCog(bot))
