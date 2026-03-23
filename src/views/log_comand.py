from venv import logger
import discord
from services.channel_service import LOGS_COMMAND_CHANNEL


class CommandLog:
    def __init__(self, bot):
        self.bot = bot
    async def send_command_log(self, user, command_name, args, channel):
        logger.info(f"[COMMAND] Logando comando: {command_name}")
        canal = discord.utils.find(
            lambda c: (
                isinstance(c, discord.TextChannel) and
                c.name.lower().strip() == LOGS_COMMAND_CHANNEL.lower().strip()
            ),
            channel.guild.channels
        )
        if not canal:
            logger.warning("[COMMAND] Canal não encontrado")
            return
        try:
            timestamp = int(discord.utils.utcnow().timestamp())
            embed = discord.Embed(
                title="⚙️ Comando Executado",
                color=0x2b2d31
            )
            embed.add_field(
                name="👤 Usuário",
                value=f"{user.mention}",
                inline=True
            )
            embed.add_field(
                name="📌 Comando",
                value=f"`{command_name}`",
                inline=True
            )
            embed.add_field(
                name="📍 Canal",
                value=f"{channel.mention}",
                inline=True
            )
            embed.add_field(
                name="📝 Args",
                value=args or "Sem argumentos",
                inline=True
            )
            embed.add_field(
                name="⏰ Data",
                value=f"<t:{timestamp}:F>",
                inline=True
            )
            embed.set_footer(text="Sistema de Logs • Comandos")
            await canal.send(embed=embed)
            logger.info("[COMMAND] Log enviado com sucesso")
        except Exception as e:
            logger.error(f"[COMMAND] Erro: {e}")




def build_command_log_embed():
    embed = discord.Embed(
        title="⚙️ Sistema de Logs de Comandos",
        description=(
            "Todos os comandos executados serão registrados aqui.\n\n"
            "🔎 Monitoramento e segurança."
        ),
        color=0x2b2d31
    )
    embed.add_field(
        name="📌 O que é registrado?",
        value=(
            "• Usuário\n"
            "• Comando\n"
            "• Argumentos\n"
            "• Canal\n"
            "• Data e hora"
        ),
        inline=False
    )
    embed.set_footer(text="Sistema de Logs • Comandos")
    return embed