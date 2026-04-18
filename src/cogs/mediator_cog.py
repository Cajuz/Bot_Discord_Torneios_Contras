"""
MediatorCog — Comandos de mediadores.
Roadmap: /silence, /sala implementados. !addmediador / !removemediador / !fila.
"""
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from utils.logger import logger
from utils.datetime_utils import utcnow


THEME_COLOR = 0xFFD54F


class MediatorCog(commands.Cog, name="Mediador"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── !addmediador ─────────────────────────────────────────────────────
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

    # ── !removemediador ────────────────────────────────────────────────
    @commands.command(name="removemediador")
    @commands.has_permissions(administrator=True)
    async def removemediador(self, ctx: commands.Context, member: discord.Member):
        from services.mediator_queue import mediator_queue
        await mediator_queue.remove_mediador(str(member.id))

        role = discord.utils.get(ctx.guild.roles, name="Controller")
        if role and role in member.roles:
            await member.remove_roles(role, reason="Removido como mediador")

        await ctx.reply(f"✅ {member.mention} removido da fila de mediadores.")

    # ── !fila ─────────────────────────────────────────────────────────
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

    # ── /sala ─────────────────────────────────────────────────────────
    @app_commands.command(
        name="sala",
        description="[Mediador] Informa sala + senha e inicia a partida"
    )
    @app_commands.describe(
        sala_id="ID da sala no jogo",
        senha="Senha da sala",
        modo="Modo de jogo (ex: Normal, Ranked, Torneio)"
    )
    @app_commands.checks.has_any_role("Controller", "Mediador", "Mediator")
    async def sala(
        self,
        interaction: discord.Interaction,
        sala_id: str,
        senha: str,
        modo: str = "Normal",
    ):
        await interaction.response.defer(ephemeral=True)

        from services.match_service import match_service
        from models.match import Match

        # Busca automaticamente a partida ativa do mediador
        partidas = await match_service.get_matches_by_mediator(interaction.user.id, limit=10)
        match = next(
            (m for m in partidas if m.get("status") == Match.STATUS_AGUARDANDO_PARTIDA),
            None
        )

        if not match:
            await interaction.followup.send(
                "❌ Nenhuma partida sua com status `aguardando_partida` encontrada.\n"
                "Verifique se a partida foi criada corretamente.",
                ephemeral=True
            )
            return

        match_id = str(match["_id"])

        # Transiciona aguardando_partida → partida_iniciada
        updated = await match_service.iniciar_partida(
            match_id=match_id,
            sala_id=sala_id,
            sala_senha=senha,
            modo_jogo=modo,
        )
        if not updated:
            await interaction.followup.send(
                "❌ Erro ao iniciar partida. Tente novamente.", ephemeral=True
            )
            return

        # Monta embed da sala
        embed = discord.Embed(
            title="🎮 Sala Aberta — Partida Iniciada!",
            color=discord.Color.green(),
            timestamp=utcnow()
        )
        embed.add_field(name="🏠 ID da Sala", value=f"`{sala_id}`",  inline=True)
        embed.add_field(name="🔑 Senha",      value=f"`{senha}`",    inline=True)
        embed.add_field(name="🎯 Modo",       value=f"`{modo}`",     inline=True)
        embed.add_field(name="📋 Partida",    value=f"`{match_id}`", inline=False)

        time_blue = match.get("time_blue", [])
        time_red  = match.get("time_red",  [])
        if time_blue or time_red:
            embed.add_field(
                name="⚔️ Times",
                value=(
                    "**Time Blue:** " + (" ".join(f"<@{p}>" for p in time_blue) or "—") + "\n"
                    "**Time Red:** "  + (" ".join(f"<@{p}>" for p in time_red)  or "—")
                ),
                inline=False
            )

        embed.set_footer(
            text=f"Mediador: {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )

        player_ids = match.get("player_ids", [])
        mentions   = " ".join(f"<@{pid}>" for pid in player_ids)

        thread_id = match.get("thread_id")
        thread    = interaction.guild.get_thread(int(thread_id)) if thread_id else None

        if thread:
            await thread.send(content=f"🚨 **SALA ABERTA!** {mentions}", embed=embed)
            await interaction.followup.send("✅ Sala publicada na thread da partida!", ephemeral=True)
        else:
            await interaction.channel.send(content=f"🚨 **SALA ABERTA!** {mentions}", embed=embed)
            await interaction.followup.send(
                "✅ Sala publicada (thread não encontrada — postado no canal atual).",
                ephemeral=True
            )

        logger.info(
            f"[Sala] Partida {match_id} iniciada pelo mediador "
            f"{interaction.user.name} — Sala: {sala_id}"
        )

    @sala.error
    async def sala_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingAnyRole):
            await interaction.response.send_message(
                "Apenas mediadores podem usar este comando.", ephemeral=True
            )

    # ── /silence ─────────────────────────────────────────────────────────
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
