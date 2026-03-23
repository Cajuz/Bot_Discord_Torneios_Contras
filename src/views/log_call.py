from venv import logger

import discord
from services.channel_service import LOGS_CALL_CHANNEL

class CallLog:

    def __init__(self, bot):
        self.bot = bot
        self.calls = {}  

    async def on_enter(self, member, channel):
        logger.info(f"[CALL] Entrada detectada | user={member.id}")

        self.calls[member.id] = {
            "channel": channel,
            "start": discord.utils.utcnow(),
            "members": [m.id for m in channel.members]
        }

    async def on_exit(self, member):
        logger.info(f"[CALL] Saída detectada | user={member.id}")

        data = self.calls.pop(member.id, None)

        if not data:
            logger.warning("[CALL] Nenhum registro encontrado para saída")
            return

        duration = int((discord.utils.utcnow() - data["start"]).total_seconds())

        await self.send_call_log(
            member,
            data["channel"],
            duration,
            data["members"]
        )

    async def send_call_log(self, member, channel, duration_seconds, members_ids):

        logger.info(f"[CALL] Iniciando log | user={member.id}")
        logger.info(f"[CALL] Procurando canal: '{LOGS_CALL_CHANNEL}'")

        canal = discord.utils.find(
            lambda c: (
                isinstance(c, discord.TextChannel) and
                c.name.lower().strip() == LOGS_CALL_CHANNEL.lower().strip()
            ),
            member.guild.channels
        )

        if not canal:
            logger.warning("[CALL] Canal de log NÃO encontrado")

            for ch in member.guild.channels:
                logger.warning(f"[DEBUG CANAL] '{ch.name}' | {type(ch)}")

            return

        logger.info(f"[CALL] Canal encontrado: {canal.name}")

        try:
            minutes = duration_seconds // 60
            seconds = duration_seconds % 60

            timestamp = int(discord.utils.utcnow().timestamp())

            membros = ", ".join(f"<@{m}>" for m in members_ids)

            embed = discord.Embed(
                title="📞 Log de Call",
                description="**Sessão de call finalizada**",
                color=0x2b2d31
            )

            embed.add_field(
                name="👤 Usuário",
                value=f"{member.mention} (`{member.id}`)",
                inline=False
            )

            embed.add_field(
                name="📍 Canal",
                value=channel.mention,
                inline=True
            )

            embed.add_field(
                name="⏱️ Duração",
                value=f"{minutes}m {seconds}s",
                inline=True
            )

            embed.add_field(
                name="👥 Participantes",
                value=membros or "Ninguém",
                inline=False
            )

            embed.add_field(
                name="⏰ Data",
                value=f"<t:{timestamp}:F>",
                inline=False
            )

            embed.set_footer(text="Sistema de Logs • Call")

            await canal.send(embed=embed)

            logger.info("[CALL] Log enviado com sucesso")

        except Exception as e:
            logger.error(f"[CALL] Erro ao enviar log: {e}")

def build_call_log_embed():
    embed = discord.Embed(
        title="📞 Sistema de Logs de Call",
        description=(
            "Todas as **calls finalizadas** serão registradas aqui.\n\n"
            "🔎 Monitoramento de atividade."
        ),
        color=0x2b2d31
    )

    embed.add_field(
        name="📌 O que é registrado?",
        value=(
            "• Usuário\n"
            "• Canal\n"
            "• Duração\n"
            "• Participantes\n"
            "• Data e hora"
        ),
        inline=False
    )

    embed.set_footer(text="Sistema de Logs • Call")

    return embed