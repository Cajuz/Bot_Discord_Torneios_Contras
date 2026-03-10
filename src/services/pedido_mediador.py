import discord
from datetime import datetime, timedelta, timezone, time
import numpy as np
from config.database import db
from utils.logger import logger
import matplotlib.pyplot as plt
import io
import matplotlib
from discord.ext import tasks
from urllib.parse import quote 
from discord import client
from discord import user
from discord.errors import NotFound
from zoneinfo import ZoneInfo 
from config.channels_config import ChannelsConfig

SOLICITACOES_MEDIADOR_CHANNEL = "solicitacoes-mediador"






horario_brasilia = time(3, 0, 0)





# Embed de Benefícios
class PedidomediadorEmbed:

    @staticmethod
    def beneficios():
        embed = discord.Embed(
            title="💼 Torne-se um Mediador",
            description=(
                "Quer ganhar dinheiro ajudando nas negociações do servidor?\n\n"
                "Os mediadores garantem segurança nas transações entre membros "
                "e recebem benefícios exclusivos durante o contrato."
            ),
            color=discord.Color.blue()
        )

        embed.add_field(
            name="✅ Benefícios",
            value=(
                "• Cargo exclusivo de Mediador\n"
                "• Acesso a canais privados\n"
                "• Prioridade nas negociações\n"
                "• Comissão por mediação realizada"
            ),
            inline=False
        )

        embed.add_field(
            name="💰 Ganhos",
            value=(
                "• Possibilidade de ganhos durante o contrato\n"
                "• Receba comissão por cada mediação concluída"
            ),
            inline=False
        )

        embed.add_field(
            name="📅 Plano Disponível",
            value="• Plano semanal",
            inline=False
        )

        embed.set_footer(
            text="Clique no botão abaixo para iniciar o processo."
        )

        return embed


# Modal de Solicitação
class PedidoMediadorModal(discord.ui.Modal, title="Solicitação de Mediador"):

    def __init__(self, plano: str):
        super().__init__()
        self.plano = plano

    mensagem = discord.ui.TextInput(
        label="Por que você quer ser mediador?",
        placeholder="Explique brevemente...",
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            adm_role = discord.utils.get(interaction.guild.roles, name="ADM")

            canal = discord.utils.get(interaction.guild.text_channels, name="solicitacoes-mediador")
            if not canal:
                canal = await interaction.guild.create_text_channel(
                    "solicitacoes-mediador",
                    overwrites={
                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                        adm_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                        interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                    },
                    topic="Solicitações de novos mediadores — apenas ADM pode ver"
                )

            embed = discord.Embed(
                title="📩 Nova solicitação de mediador",
                color=discord.Color.yellow()
            )

            embed.add_field(name="Usuário", value=interaction.user.mention, inline=False)
            embed.add_field(name="Mensagem", value=self.mensagem.value, inline=False)

            # CORREÇÃO: passe o plano ao criar a View
            await canal.send(
                embed=embed,
                view=PedidoMediadorAdminView(plano=self.plano, user_id=interaction.user.id)
            )

            await interaction.response.send_message(
                "✅ Sua solicitação foi enviada para a equipe!",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ocorreu um erro: {e}",
                ephemeral=True
            )


# View com apenas plano semanal
class PedidoMediadorValor(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Plano Semanal - R$50",
        style=discord.ButtonStyle.green
    )
    async def semanal(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            modal = PedidoMediadorModal("Semanal - R$50")
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Erro botão semanal: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Erro ao abrir o formulário.",
                    ephemeral=True
                )


# View principal do usuário
class PedidoMediadorView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Quero ser mediador",
        style=discord.ButtonStyle.green
    )
    async def pedir(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_message(
                "Escolha um plano:",
                view=PedidoMediadorValor(),
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro botão pedir mediador: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Ocorreu um erro.",
                    ephemeral=True
                )


# View para ADM aprovar/recusar
class PedidoMediadorAdminView(discord.ui.View):
    def __init__(self, plano: str, user_id: int):
        super().__init__(timeout=None)
        self.plano = plano
        self.user_id = user_id

    @discord.ui.button(label="Aprovar", style=discord.ButtonStyle.green, custom_id="aprovar_mediador")
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            guild = interaction.guild
            user = guild.get_member(self.user_id)
            admin = interaction.user

            if not user:
                await interaction.response.send_message(
                    "❌ Usuário não encontrado no servidor.", ephemeral=True
                )
                return

            # DM para o usuário
            try:
                await user.send(
                    f"✅ Sua solicitação para ser mediador foi **aprovada** pelo {admin.mention}.\n"
                    f"Plano escolhido: **{self.plano}**\n"
                    "Por favor, entre em contato com o ADM para enviar o comprovante."
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    f"⚠️ Não foi possível enviar DM para {user.mention}.", ephemeral=True
                )

            # DM para o ADM
            try:
                await admin.send(
                    f"📩 Você aprovou {user.mention} para o plano **{self.plano}**.\n"
                    "O usuário foi notificado para entrar em contato com você."
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    f"⚠️ Não foi possível enviar DM para {admin.mention}.", ephemeral=True
                )

            # Confirmação no canal para o ADM
            await interaction.response.send_message(
                f"✅ Solicitação aprovada! DMs enviadas para {user.mention} e você.", ephemeral=True
            )

            button.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ocorreu um erro ao aprovar a solicitação: {e}", ephemeral=True
            )

    @discord.ui.button(label="Recusar", style=discord.ButtonStyle.red, custom_id="recusar_mediador")
    async def recusar(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            guild = interaction.guild
            user = guild.get_member(self.user_id)
            admin = interaction.user

            if user:
                try:
                    await user.send(
                        f"❌ Sua solicitação para ser mediador foi **recusada** pelo {admin.mention}."
                    )
                except discord.Forbidden:
                    await interaction.response.send_message(
                        f"⚠️ Não foi possível enviar DM para {user.mention}.",
                        ephemeral=True
                    )

            await interaction.response.send_message(
                f"❌ Você recusou {user.mention}.", ephemeral=True
            )

            button.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao recusar a solicitação.", ephemeral=True
            )

