import asyncio
from venv import logger

import discord
from services.channel_service import LOGS_MESSAGE_DELETE_CHANNEL


class MessageDeleteLog:

    def __init__(self, bot):
        self.bot = bot

    async def send_delete_log(self, message: discord.Message):

        logger.info(f"[DELETE] Detectado | author={message.author.id}")

        canal = discord.utils.find(
            lambda c: (
                isinstance(c, discord.TextChannel) and
                c.name.lower().strip() == LOGS_MESSAGE_DELETE_CHANNEL.lower().strip()
            ),
            message.guild.channels
        )

        if not canal:
            logger.warning("[DELETE] Canal não encontrado")
            return

        try:
            # 🔥 ESPERA O AUDIT LOG ATUALIZAR
            await asyncio.sleep(1)

            deleter = message.author  # fallback

            async for entry in message.guild.audit_logs(
                limit=5,
                action=discord.AuditLogAction.message_delete
            ):
                # verifica se bate com autor e canal
                if (
                    entry.target.id == message.author.id and
                    entry.extra.channel.id == message.channel.id
                ):
                    deleter = entry.user
                    break

            timestamp = int(discord.utils.utcnow().timestamp())

            embed = discord.Embed(
                title="🗑️ Mensagem Deletada",
                color=0x2b2d31
            )

            # 🔥 PRIMEIRA LINHA
            embed.add_field(
                name="👤 Autor",
                value=f"{message.author.mention}",
                inline=True
            )

            embed.add_field(
                name="🛠️ Deletado por",
                value=f"{deleter.mention}",
                inline=True
            )

            embed.add_field(
                name="📍 Canal",
                value=message.channel.mention,
                inline=True
            )

            # 🔥 CONTEÚDO
            embed.add_field(
                name="💬 Conteúdo",
                value=message.content or "Sem conteúdo",
                inline=False
            )

            embed.add_field(
                name="⏰ Data",
                value=f"<t:{timestamp}:F>",
                inline=True
            )

            embed.set_footer(text="Sistema de Logs • Mensagens")

            await canal.send(embed=embed)

            logger.info("[DELETE] Log enviado com sucesso")

        except Exception as e:
            logger.error(f"[DELETE] Erro: {e}")


def build_message_delete_embed():
    embed = discord.Embed(
        title="🗑️ Sistema de Logs de Mensagens",
        description=(
            "Mensagens deletadas serão registradas aqui.\n\n"
            "🔎 Auditoria da staff."
        ),
        color=0x2b2d31
    )

    embed.add_field(
        name="📌 O que é registrado?",
        value=(
            "• Autor\n"
            "• Canal\n"
            "• Conteúdo\n"
            "• Data e hora"
        ),
        inline=False
    )

    embed.set_footer(text="Sistema de Logs • Mensagens")

    return embed