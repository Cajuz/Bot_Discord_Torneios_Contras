import discord

from services.channel_service import LOGS_PIX_LOG_CHANNEL


class PixLog:

    def __init__(self, bot):
        self.bot = bot

    async def send_pix_log(self, interaction: discord.Interaction, pix_antigo: str | None, pix_novo: str):

        canal = discord.utils.get(interaction.guild.text_channels, name=LOGS_PIX_LOG_CHANNEL)

        if not canal:
            return

        acao = "Cadastro" if not pix_antigo else "Alteração"

        timestamp = int(discord.utils.utcnow().timestamp())

        embed = discord.Embed(
            title="💳 Log de PIX",
            description=f"**{acao} de chave PIX realizada**",
            color=0x2b2d31
        )

        embed.add_field(
            name="👤 Usuário",
            value=f"{interaction.user.mention} (`{interaction.user.id}`)",
            inline=False
        )

        embed.add_field(
            name="📌 Tipo",
            value=f"`{acao}`",
            inline=True
        )

        # 🔥 DATA + HORA BONITA
        embed.add_field(
            name="⏰ Data e Hora",
            value=f"<t:{timestamp}:F>",
            inline=True
        )

        if pix_antigo:
            embed.add_field(
                name="🔴 PIX Antigo",
                value=f"`{pix_antigo}`",
                inline=False
            )

        embed.add_field(
            name="🟢 PIX Novo",
            value=f"`{pix_novo}`",
            inline=False
        )

        embed.set_footer(text="Sistema de Logs • PIX")

        await canal.send(embed=embed)

    


def build_pix_log_embed():

    embed = discord.Embed(
        title="💳 Sistema de Logs de PIX",
        description=(
            "Todos os **cadastros e alterações de chave PIX** serão registrados aqui.\n\n"
            "🔎 Este canal é automático e usado para auditoria da staff."
        ),
        color=0x2b2d31
    )

    embed.add_field(
        name="📌 O que é registrado?",
        value=(
            "• Cadastro de PIX\n"
            "• Alteração de chave\n"
            "• Usuário responsável\n"
            "• Data e hora"
        ),
        inline=False
    )

    embed.set_footer(text="Sistema de Logs • PIX")

    return embed