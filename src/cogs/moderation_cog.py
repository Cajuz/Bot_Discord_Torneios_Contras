# moderation_cog.py — Comandos de moderação slash (ADM only).
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from utils.logger import logger
from utils.datetime_utils import utcnow
from datetime import timedelta

THEME_COLOR   = 0xFFD54F
COLOR_SUCCESS = 0x2ECC71
COLOR_ERROR   = 0xFF0000
COLOR_WARN    = 0xFF6B35

AVISOS_CHANNEL       = "🚨-avisos"
LOGS_BOT_CHANNEL     = "📝-logs-bot"
LOGS_COMMAND_CHANNEL = "📝-logs-command"
ADM_ROLE_NAME        = "ADM"
SPAM_BLOCK_ROLE_NAME = "Bloqueado"


def _is_adm():
    async def predicate(interaction: discord.Interaction) -> bool:
        adm_role = discord.utils.get(interaction.user.roles, name=ADM_ROLE_NAME)
        if adm_role or interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message("❌ Apenas ADM podem usar este comando.", ephemeral=True)
        return False
    return app_commands.check(predicate)


async def _log_action(guild, autor, acao, alvo, motivo, cor=COLOR_WARN):
    ch = discord.utils.get(guild.text_channels, name=LOGS_COMMAND_CHANNEL)
    if not ch:
        return
    embed = discord.Embed(title=f"🔨 Moderação — {acao}", color=cor, timestamp=utcnow())
    embed.add_field(name="Executor", value=f"{autor.mention} (`{autor.id}`)", inline=True)
    embed.add_field(name="Alvo",     value=alvo,                              inline=True)
    embed.add_field(name="Motivo",   value=motivo or "Não informado",         inline=False)
    embed.set_footer(text="X1 Frifas · Moderação")
    try:
        await ch.send(embed=embed)
    except Exception as e:
        logger.warning(f"[ModerationCog] log_action: {e}")


class ModerationCog(commands.Cog, name="Moderação"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─────────────────────────────────────────
    # /aviso
    # ─────────────────────────────────────────

    @app_commands.command(name="aviso", description="Posta um aviso oficial no canal 🚨-avisos.")
    @app_commands.describe(
        titulo="Título do aviso",
        mensagem="Conteúdo do aviso",
        mencionar_everyone="Mencionar @everyone? (padrão: não)",
    )
    @_is_adm()
    async def aviso(self, interaction: discord.Interaction, titulo: str, mensagem: str, mencionar_everyone: bool = False):
        ch = discord.utils.get(interaction.guild.text_channels, name=AVISOS_CHANNEL)
        if not ch:
            await interaction.response.send_message(f"❌ Canal `#{AVISOS_CHANNEL}` não encontrado.", ephemeral=True)
            return
        embed = discord.Embed(title=f"🚨 {titulo}", description=mensagem, color=COLOR_ERROR, timestamp=utcnow())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="X1 Frifas · Avisos Oficiais")
        content = "@everyone" if mencionar_everyone else None
        await ch.send(content=content, embed=embed)
        await interaction.response.send_message(f"✅ Aviso postado em {ch.mention}.", ephemeral=True)
        await _log_action(interaction.guild, interaction.user, "Aviso", ch.mention, titulo)

    # ─────────────────────────────────────────
    # /ban
    # ─────────────────────────────────────────

    @app_commands.command(name="ban", description="Bane um membro do servidor.")
    @app_commands.describe(membro="Membro a ser banido", motivo="Motivo do ban", deletar_mensagens="Dias de mensagens para deletar (0-7)")
    @_is_adm()
    async def ban(self, interaction: discord.Interaction, membro: discord.Member, motivo: str = "Não informado", deletar_mensagens: app_commands.Range[int, 0, 7] = 0):
        if membro.top_role >= interaction.user.top_role:
            await interaction.response.send_message("❌ Você não pode banir alguém com cargo igual ou superior ao seu.", ephemeral=True)
            return
        try:
            await membro.ban(reason=f"{motivo} — por {interaction.user}", delete_message_days=deletar_mensagens)
            embed = discord.Embed(title="🔨 Membro Banido", description=f"{membro.mention} foi banido.", color=COLOR_ERROR, timestamp=utcnow())
            embed.add_field(name="Motivo", value=motivo, inline=False)
            embed.set_footer(text=f"ID: {membro.id} · X1 Frifas")
            await interaction.response.send_message(embed=embed)
            await _log_action(interaction.guild, interaction.user, "Ban", f"{membro} (`{membro.id}`)", motivo, COLOR_ERROR)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão para banir este membro.", ephemeral=True)
        except Exception as e:
            logger.error(f"[/ban] {e}")
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

    # ─────────────────────────────────────────
    # /unban
    # ─────────────────────────────────────────

    @app_commands.command(name="unban", description="Remove o ban de um usuário pelo ID.")
    @app_commands.describe(user_id="ID do usuário banido", motivo="Motivo do unban")
    @_is_adm()
    async def unban(self, interaction: discord.Interaction, user_id: str, motivo: str = "Não informado"):
        try:
            uid = int(user_id)
        except ValueError:
            await interaction.response.send_message("❌ ID inválido.", ephemeral=True)
            return
        try:
            user = await self.bot.fetch_user(uid)
            await interaction.guild.unban(user, reason=f"{motivo} — por {interaction.user}")
            embed = discord.Embed(title="✅ Ban Removido", description=f"**{user}** (`{uid}`) foi desbanido.", color=COLOR_SUCCESS, timestamp=utcnow())
            embed.add_field(name="Motivo", value=motivo, inline=False)
            embed.set_footer(text="X1 Frifas · Moderação")
            await interaction.response.send_message(embed=embed)
            await _log_action(interaction.guild, interaction.user, "Unban", f"{user} (`{uid}`)", motivo, COLOR_SUCCESS)
        except discord.NotFound:
            await interaction.response.send_message("❌ Usuário não encontrado ou não está banido.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão para desbanir.", ephemeral=True)
        except Exception as e:
            logger.error(f"[/unban] {e}")
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

    # ─────────────────────────────────────────
    # /kick
    # ─────────────────────────────────────────

    @app_commands.command(name="kick", description="Expulsa um membro do servidor.")
    @app_commands.describe(membro="Membro a ser expulso", motivo="Motivo da expulsão")
    @_is_adm()
    async def kick(self, interaction: discord.Interaction, membro: discord.Member, motivo: str = "Não informado"):
        if membro.top_role >= interaction.user.top_role:
            await interaction.response.send_message("❌ Você não pode expulsar alguém com cargo igual ou superior ao seu.", ephemeral=True)
            return
        try:
            await membro.kick(reason=f"{motivo} — por {interaction.user}")
            embed = discord.Embed(title="👢 Membro Expulso", description=f"{membro.mention} foi expulso.", color=COLOR_WARN, timestamp=utcnow())
            embed.add_field(name="Motivo", value=motivo, inline=False)
            embed.set_footer(text=f"ID: {membro.id} · X1 Frifas")
            await interaction.response.send_message(embed=embed)
            await _log_action(interaction.guild, interaction.user, "Kick", f"{membro} (`{membro.id}`)", motivo, COLOR_WARN)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão para expulsar este membro.", ephemeral=True)
        except Exception as e:
            logger.error(f"[/kick] {e}")
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

    # ─────────────────────────────────────────
    # /timeout
    # ─────────────────────────────────────────

    @app_commands.command(name="timeout", description="Silencia um membro temporariamente.")
    @app_commands.describe(membro="Membro a ser silenciado", minutos="Duração em minutos (máx. 40320 = 28 dias)", motivo="Motivo do timeout")
    @_is_adm()
    async def timeout(self, interaction: discord.Interaction, membro: discord.Member, minutos: app_commands.Range[int, 1, 40320], motivo: str = "Não informado"):
        if membro.top_role >= interaction.user.top_role:
            await interaction.response.send_message("❌ Você não pode silenciar alguém com cargo igual ou superior ao seu.", ephemeral=True)
            return
        try:
            until = utcnow() + timedelta(minutes=minutos)
            await membro.timeout(until, reason=f"{motivo} — por {interaction.user}")
            duracao = f"{minutos} min" if minutos < 60 else f"{minutos // 60}h {minutos % 60}min"
            embed = discord.Embed(title="🔇 Timeout Aplicado", description=f"{membro.mention} foi silenciado por **{duracao}**.", color=COLOR_WARN, timestamp=utcnow())
            embed.add_field(name="Motivo", value=motivo, inline=False)
            embed.set_footer(text=f"ID: {membro.id} · X1 Frifas")
            await interaction.response.send_message(embed=embed)
            await _log_action(interaction.guild, interaction.user, f"Timeout ({duracao})", f"{membro} (`{membro.id}`)", motivo, COLOR_WARN)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão para aplicar timeout.", ephemeral=True)
        except Exception as e:
            logger.error(f"[/timeout] {e}")
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

    # ─────────────────────────────────────────
    # /untimeout
    # ─────────────────────────────────────────

    @app_commands.command(name="untimeout", description="Remove o timeout de um membro.")
    @app_commands.describe(membro="Membro para remover o timeout", motivo="Motivo")
    @_is_adm()
    async def untimeout(self, interaction: discord.Interaction, membro: discord.Member, motivo: str = "Não informado"):
        try:
            await membro.timeout(None, reason=f"{motivo} — por {interaction.user}")
            await interaction.response.send_message(f"✅ Timeout de {membro.mention} removido.", ephemeral=True)
            await _log_action(interaction.guild, interaction.user, "Untimeout", f"{membro} (`{membro.id}`)", motivo, COLOR_SUCCESS)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        except Exception as e:
            logger.error(f"[/untimeout] {e}")
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

    # ─────────────────────────────────────────
    # /bloquear — bloqueia via cargo Bloqueado
    # NOTA: /silence foi removido daqui pois está duplicado no admin_cog
    # ─────────────────────────────────────────

    @app_commands.command(name="bloquear", description="Bloqueia um membro (cargo Bloqueado + registro no banco).")
    @app_commands.describe(membro="Membro a ser bloqueado", motivo="Motivo do bloqueio")
    @_is_adm()
    async def bloquear(self, interaction: discord.Interaction, membro: discord.Member, motivo: str = "Bloqueado manualmente"):
        try:
            from config.database import db
            blocked_role = discord.utils.get(interaction.guild.roles, name=SPAM_BLOCK_ROLE_NAME)
            if not blocked_role:
                blocked_role = await interaction.guild.create_role(name=SPAM_BLOCK_ROLE_NAME)
            await membro.add_roles(blocked_role, reason=motivo)
            await db.get_collection("users").update_one(
                {"discord_id": str(membro.id)},
                {"$set": {
                    "spam_blocked": True,
                    "spam_blocked_at": utcnow(),
                    "spam_block_reason": motivo,
                }},
                upsert=True,
            )
            await interaction.response.send_message(f"✅ {membro.mention} bloqueado. Motivo: *{motivo}*")
            await _log_action(interaction.guild, interaction.user, "Bloquear", f"{membro} (`{membro.id}`)", motivo, COLOR_WARN)
        except Exception as e:
            logger.error(f"[/bloquear] {e}")
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

    # ─────────────────────────────────────────
    # /desbloquear
    # ─────────────────────────────────────────

    @app_commands.command(name="desbloquear", description="Remove o bloqueio de um membro.")
    @app_commands.describe(membro="Membro a ser desbloqueado")
    @_is_adm()
    async def desbloquear(self, interaction: discord.Interaction, membro: discord.Member):
        try:
            from config.database import db
            blocked_role = discord.utils.get(interaction.guild.roles, name=SPAM_BLOCK_ROLE_NAME)
            if blocked_role and blocked_role in membro.roles:
                await membro.remove_roles(blocked_role)
            await db.get_collection("users").update_one(
                {"discord_id": str(membro.id)},
                {"$set": {
                    "spam_blocked": False,
                    "spam_unblocked_at": utcnow(),
                    "spam_unblocked_by": str(interaction.user.id),
                }},
            )
            await interaction.response.send_message(f"✅ {membro.mention} desbloqueado.")
            await _log_action(interaction.guild, interaction.user, "Desbloquear", f"{membro} (`{membro.id}`)", "—", COLOR_SUCCESS)
        except Exception as e:
            logger.error(f"[/desbloquear] {e}")
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

    # ─────────────────────────────────────────
    # /warn
    # ─────────────────────────────────────────

    @app_commands.command(name="warn", description="Registra um aviso para um membro.")
    @app_commands.describe(membro="Membro a ser avisado", motivo="Motivo do aviso")
    @_is_adm()
    async def warn(self, interaction: discord.Interaction, membro: discord.Member, motivo: str):
        try:
            from config.database import db
            col = db.get_collection("warns")
            await col.insert_one({
                "discord_id": str(membro.id),
                "guild_id":   str(interaction.guild_id),
                "motivo":     motivo,
                "por":        str(interaction.user.id),
                "criado_em":  utcnow(),
            })
            total = await col.count_documents({"discord_id": str(membro.id), "guild_id": str(interaction.guild_id)})
            embed = discord.Embed(title="⚠️ Aviso Registrado", description=f"{membro.mention} recebeu um aviso.", color=COLOR_WARN, timestamp=utcnow())
            embed.add_field(name="Motivo",          value=motivo,    inline=False)
            embed.add_field(name="Total de Avisos", value=str(total), inline=True)
            embed.set_footer(text=f"ID: {membro.id} · X1 Frifas")
            await interaction.response.send_message(embed=embed)
            try:
                dm_embed = discord.Embed(title="⚠️ Você recebeu um aviso", description=f"**Servidor:** {interaction.guild.name}\n**Motivo:** {motivo}", color=COLOR_WARN, timestamp=utcnow())
                await membro.send(embed=dm_embed)
            except discord.Forbidden:
                pass
            await _log_action(interaction.guild, interaction.user, f"Warn (total: {total})", f"{membro} (`{membro.id}`)", motivo, COLOR_WARN)
        except Exception as e:
            logger.error(f"[/warn] {e}")
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

    # ─────────────────────────────────────────
    # /limpar
    # ─────────────────────────────────────────

    @app_commands.command(name="limpar", description="Apaga N mensagens do canal atual (máx. 100).")
    @app_commands.describe(quantidade="Número de mensagens para apagar (1-100)", membro="Apagar apenas mensagens deste membro (opcional)")
    @_is_adm()
    async def limpar(self, interaction: discord.Interaction, quantidade: app_commands.Range[int, 1, 100], membro: discord.Member = None):
        await interaction.response.defer(ephemeral=True)
        try:
            def check(msg):
                return membro is None or msg.author == membro
            deleted = await interaction.channel.purge(limit=quantidade, check=check)
            await interaction.followup.send(
                f"🧹 {len(deleted)} mensagem(ns) removida(s)" + (f" de {membro.mention}" if membro else "") + ".",
                ephemeral=True,
            )
            await _log_action(interaction.guild, interaction.user, "Limpar", interaction.channel.mention, f"{len(deleted)} msgs" + (f" de {membro}" if membro else ""), COLOR_WARN)
        except discord.Forbidden:
            await interaction.followup.send("❌ Sem permissão para apagar mensagens.", ephemeral=True)
        except Exception as e:
            logger.error(f"[/limpar] {e}")
            await interaction.followup.send(f"❌ Erro: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))