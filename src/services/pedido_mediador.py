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






from services.channel_service import (
    QUEROSERMEDIADOR_CHANNEL,
    #CATEGORY_ANALYTICS_NAME,
    #ADM_ROLE_NAME,
)

horario_brasilia = time(3, 0, 0)


# quero ser mediador 
class querosermediador:
    def __int__(self):
        self.bot= None
        
    # ==================== TASK DIÁRIA ====================


    @tasks.loop(time=horario_brasilia)
    async def daily_update(self):
        logger.info("Executando atualização automática de meia-noite...")
        for guild in self.bot.guilds:
            try:
                channel = await self.resolve_dashboard_channel(guild)
                if channel:
                    await self.update_dashboard_for_channel(channel)
            except Exception as e:
                logger.error(f"Erro no daily_update para guild {guild.name}: {e}")


    @daily_update.before_loop
    async def before_daily_update(self):
        await self.bot.wait_until_ready()


    # ==================== RESOLUÇÃO DO CANAL ====================


    async def resolve_canalmediador(self, guild: discord.Guild) -> discord.TextChannel | None:
        """
        Garante que a categoria Analytics e o canal quero ser mediador existam.
        Usado pela task diária e como fallback independente.
        """
        try:
            # Categoria Analytics
            category = discord.utils.get(guild.categories, name=CATEGORY_ANALYTICS_NAME)
            if not category:
                category = await guild.create_category(CATEGORY_ANALYTICS_NAME)
                logger.info(f"✅ Categoria '{CATEGORY_ANALYTICS_NAME}' criada em {guild.name}")

            # Cargo ADM
            adm_role = discord.utils.get(guild.roles, name=ADM_ROLE_NAME)
            if not adm_role:
                adm_role = await guild.create_role(name=ADM_ROLE_NAME, mentionable=True)
                logger.info(f"✅ Cargo '{ADM_ROLE_NAME}' criado em {guild.name}")

            # Permissões: só ADM vê, @everyone bloqueado, bot pode tudo
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                adm_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    manage_channels=True
                ),
            }

            # Canal dashboard-partidas
            channel = discord.utils.get(guild.text_channels, name=DASHBOARD_CHANNEL_NAME)
            if not channel:
                channel = await guild.create_text_channel(
                    name=DASHBOARD_CHANNEL_NAME,
                    category=category,
                    overwrites=overwrites,
                    topic="📊 Dashboard automático de partidas — atualizado diariamente"
                )
                logger.info(f"✅ Canal '{DASHBOARD_CHANNEL_NAME}' criado em {guild.name}")
            else:
                await channel.edit(
                    category=category,
                    overwrites=overwrites,
                    topic="📊 Dashboard automático de partidas — atualizado diariamente"
                )
                logger.info(f"✅ Canal '{DASHBOARD_CHANNEL_NAME}' atualizado em {guild.name}")

            return channel

        except discord.Forbidden:
            logger.error(f"❌ Sem permissão para criar/editar canal em {guild.name}")
            return None
        except Exception as e:
            logger.error(f"Erro no resolve_dashboard_channel ({guild.name}): {e}")
            return None
        


    async def queroser_mediador(interaction: discord.Interaction):

        guild = interaction.guild
        usuario = interaction.user


        
        # Permissões do canal
        await canal.set_permissions(usuario, view_channel=True, send_messages=True)

        for membro in guild.members:
            if ADM_ROLE_NAME in [r.id for r in membro.roles]:
                await canal.set_permissions(membro, view_channel=True, send_messages=True)

        await interaction.response.send_message(
            "📨 Sua solicitação foi enviada. Aguarde um ADM.",
            ephemeral=True
        )

        await canal.send(
            f"🔔 **Pedido de Mediador**\n\n"
            f"Usuário: {usuario.mention}\n\n"
            f"ADM, decidam abaixo⬇️:", 
            view=AprovarMediador(usuario)
        ) 



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
            name="📅 Planos Disponíveis",
            value=(
                "• Plano semanal\n"
                "• Plano mensal"
            ),
            inline=False
        )

        embed.set_footer(
            text="Clique no botão abaixo para iniciar o processo."
        )

        return embed


import discord

MAX_SALAS = 3
CATEGORIA_ATENDIMENTO = "atendimento-mediador"


class PedidoMediadorVAlor(discord.ui.View):

    async def criar_sala(self, interaction: discord.Interaction, plano: str):

        guild = interaction.guild
        user = interaction.user

        categoria = discord.utils.get(guild.categories, name=CATEGORIA_ATENDIMENTO)

        if not categoria:
            categoria = await guild.create_category(CATEGORIA_ATENDIMENTO)

        canais_abertos = len(categoria.text_channels)

        # sala cheia
        if canais_abertos >= MAX_SALAS:
            await interaction.response.send_message(
                "⚠️ Todas as salas estão ocupadas.\n"
                "Você entrou na **fila de espera**.",
                ephemeral=True
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )
        }

        canal = await guild.create_text_channel(
            name=f"pedido-{user.name}",
            category=categoria,
            overwrites=overwrites
        )

        await canal.send(
            f"{user.mention} bem-vindo!\n"
            f"Plano escolhido: **{plano}**\n"
            "Aguarde um administrador para continuar o pagamento via **PIX**."
        )

        await interaction.response.send_message(
            f"✅ Sua sala foi criada: {canal.mention}",
            ephemeral=True
        )


    @discord.ui.button(
        label="Plano Semanal - R$50",
        style=discord.ButtonStyle.green
    )
    async def semanal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.criar_sala(interaction, "Semanal R$50")


    @discord.ui.button(
        label="Plano Mensal - R$200",
        style=discord.ButtonStyle.blurple
    )
    async def mensal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.criar_sala(interaction, "Mensal R$200")