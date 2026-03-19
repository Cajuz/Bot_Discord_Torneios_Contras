import asyncio
from venv import logger

import discord
from services.channel_service import LOGS_MESSAGE_DELETE_CHANNEL


class MessageDeleteLog:

    def __init__(self, bot):
        self.bot = bot
        

    async def send_delete_log(self, message: discord.Message):

        logger.info(f"[DELETE] Detectado | author={getattr(message.author, 'id', 'unknown')}")

        if not message.guild:
            return

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
            await asyncio.sleep(1)

            deleter = message.author  # fallback

            # 🔥 AUDIT LOG SEGURO
            try:
                async for entry in message.guild.audit_logs(
                    limit=5,
                    action=discord.AuditLogAction.message_delete
                ):
                    if not entry.target:
                        continue

                    if entry.target.id == getattr(message.author, "id", None):
                        if hasattr(entry, "extra") and entry.extra:
                            if getattr(entry.extra, "channel", None) == message.channel:
                                deleter = entry.user
                                break
            except Exception as e:
                logger.warning(f"[DELETE] Falha audit log: {e}")

            timestamp = int(discord.utils.utcnow().timestamp())

            embed = discord.Embed(
                title="🗑️ Mensagem Deletada",
                color=0x2b2d31
            )

            embed.add_field(
                name="👤 Autor",
                value=message.author.mention if message.author else "Desconhecido",
                inline=True
            )

            embed.add_field(
                name="🛠️ Deletado por",
                value=deleter.mention if deleter else "Desconhecido",
                inline=True
            )

            embed.add_field(
                name="📍 Canal",
                value=message.channel.mention if message.channel else "Desconhecido",
                inline=True
            )

            # 💬 CONTEÚDO SEGURO
            content = message.content if getattr(message, "content", None) else "Sem texto"

            embed.add_field(
                name="💬 Conteúdo",
                value=content[:1024],  # evita erro de limite
                inline=False
            )

            embed.add_field(
                name="⏰ Data",
                value=f"<t:{timestamp}:F>",
                inline=True
            )

            # 🔥 ANEXOS SEGURO
            if hasattr(message, "attachments") and message.attachments:
                attachment = message.attachments[0]

                url = getattr(attachment, "url", None)

                if url:
                    # tenta setar imagem direto (sem content_type)
                    embed.set_image(url=url)

                    embed.add_field(
                        name="📎 Anexo",
                        value=f"[Abrir arquivo]({url})",
                        inline=False
                    )

            embed.set_footer(text="Sistema de Logs • Mensagens")

            await canal.send(embed=embed)

            logger.info("[DELETE] Log enviado com sucesso")

        except Exception as e:
            logger.error(f"[DELETE] Erro geral: {e}")


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