import discord
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId

from config.database import db
from config.channels_config import ChannelsConfig
from models.match import Match
from services.mediator_queue import mediator_queue
from services.match_queue_service import match_queue_service
from views.match_queue_view import create_match_queue_embed, MatchQueueView
from utils.logger import logger, log_success


# ─────────────────────────────────────────────
# Constantes de estrutura do servidor
# ─────────────────────────────────────────────

MEMBER_ROLE_NAME    = "Membro"
RULES_CHANNEL_NAME  = "📜regras"
AVISOS_CHANNEL_NAME = "📢avisos"
MEDIATOR_ROLE_NAME  = "Controller"
MEDIATOR_PANEL_NAME = "painel-mediadores"
DASHBOARD_CHANNEL_NAME = "dashboard-mediadores"

INFO_CATEGORY_NAME  = "ℹ️ INFORMAÇÕES"
GAME_CATEGORY_BASE  = None  # usa as categorias do ChannelsConfig


class ChannelService:
    """Serviço de gerenciamento de canais de partidas"""

    def __init__(self, bot: discord.Client):
        self.bot          = bot
        self.active_cards: Dict[str, discord.Message] = {}

    # ─────────────────────────────────────────────
    # Setup completo do servidor
    # ─────────────────────────────────────────────

    async def setup_all_channels(self, guild: discord.Guild):
        """
        Configura toda a estrutura do servidor:
        1. Cargos (Membro, Controller)
        2. Categoria ℹ️ INFORMAÇÕES com #📜regras e #📢avisos
        3. Canal #painel-mediadores (só Controller)
        4. Categorias e canais de jogo com permissões corretas
        """
        try:
            logger.info("Iniciando configuração completa do servidor...")

            # ── 1. Cargos ─────────────────────────────────────────
            member_role   = await self._ensure_role(
                guild, MEMBER_ROLE_NAME,
                color=discord.Color.green(),
                reason="Cargo padrão — concedido após aceitar regras"
            )
            mediator_role = await self._ensure_role(
                guild, MEDIATOR_ROLE_NAME,
                color=discord.Color.blue(),
                reason="Cargo de mediador"
            )

            # ── 2. Categoria de informações ───────────────────────
            info_category = await self._ensure_category(guild, INFO_CATEGORY_NAME)

            # Permissões padrão da categoria info:
            # @everyone vê mas não escreve
            info_overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=False
                ),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True
                )
            }
            await info_category.edit(overwrites=info_overwrites)

            # ── 3. Canal #📜regras ────────────────────────────────
            rules_channel = await self._ensure_text_channel(
                guild,
                name=RULES_CHANNEL_NAME,
                category=info_category,
                topic="Leia as regras e aguarde a DM para liberar seu acesso.",
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=False,
                        add_reactions=False
                    ),
                    member_role: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=False
                    ),
                    guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True
                    )
                }
            )
            await self._post_rules_embed(guild, rules_channel)

            # ── 4. Canal #📢avisos ────────────────────────────────
            await self._ensure_text_channel(
                guild,
                name=AVISOS_CHANNEL_NAME,
                category=info_category,
                topic="Avisos oficiais do servidor.",
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(
                        read_messages=False,  # só membros veem
                        send_messages=False
                    ),
                    member_role: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=False
                    ),
                    guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True
                    )
                }
            )

            # ── 5. Canal #painel-mediadores ───────────────────────
            mediator_channel = await self._ensure_text_channel(
                guild,
                name=MEDIATOR_PANEL_NAME,
                category=info_category,
                topic="Painel de controle para mediadores.",
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    member_role:        discord.PermissionOverwrite(read_messages=False),
                    mediator_role:      discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=False
                    ),
                    guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True
                    )
                }
            )
            # ── 6. Canal Dashborad-mediadores ───────────────────────────────
            dashboard_channel = await self._ensure_text_channel(
                guild,
                name=DASHBOARD_CHANNEL_NAME,
                category=info_category,
                topic="Dashboard de mediadores.",
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    member_role:        discord.PermissionOverwrite(read_messages=False),
                    mediator_role:      discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=False
                    ),
                    guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True
                    )
                }
            )
            





            await self._post_mediator_panel(guild, mediator_channel, mediator_role)
            # ── 7. Categorias e canais de jogo ────────────────────
            for category_name, category_data in ChannelsConfig.CATEGORIES.items():
                game_category = await self._ensure_category(guild, category_name)

                # Canais de jogo: @everyone bloqueado, Membro liberado
                game_overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        read_messages=False,
                        send_messages=False
                    ),
                    member_role: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=False  # só via botões
                    ),
                    guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_threads=True
                    )
                }
                await game_category.edit(overwrites=game_overwrites)

                for ch_info in category_data["channels"]:
                    channel = await self._ensure_text_channel(
                        guild,
                        name=ch_info["name"],
                        category=game_category,
                        topic=f"Fila de partidas {ch_info['name'].upper()} — escolha seu valor",
                        overwrites=game_overwrites
                    )
                    await self.setup_queue_cards(guild, channel)

            log_success("Servidor configurado com sucesso!")

        except Exception as e:
            logger.error(f"Erro ao configurar servidor: {e}")
            raise

    # ─────────────────────────────────────────────
    # Cards de fila
    # ─────────────────────────────────────────────

    async def setup_queue_cards(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel
    ) -> bool:
        """Remove cards antigos e cria novos para cada valor de aposta"""
        try:
            # Limpa mensagens antigas do bot
            async for message in channel.history(limit=100):
                if message.author == guild.me:
                    try:
                        await message.delete()
                    except Exception:
                        pass

            channel_name = channel.name

            for bet_value in ChannelsConfig.BET_VALUES:
                embed = create_match_queue_embed(
                    channel_name=channel_name,
                    bet_value=bet_value,
                    queue_normal_count=0,
                    queue_infinito_count=0
                )
                view = MatchQueueView(
                    channel_name=channel_name,
                    bet_value=bet_value
                )
                message = await channel.send(embed=embed, view=view)

                card_key = f"{channel_name}_{bet_value}"
                self.active_cards[card_key] = message

                logger.info(f"Card R$ {bet_value:.2f} criado em #{channel_name}")
                await asyncio.sleep(0.5)

            logger.info(f"✅ Cards configurados em #{channel_name}")
            return True

        except Exception as e:
            logger.error(f"Erro ao configurar cards em #{channel.name}: {e}")
            return False

    async def refresh_queue_card(
        self,
        channel: discord.TextChannel,
        bet_value: float
    ) -> bool:
        """Atualiza embed de um card com contagem atual da fila"""
        try:
            channel_name = channel.name

            q_normal   = await match_queue_service.get_queue_status(channel_name, bet_value, "normal")
            q_infinito = await match_queue_service.get_queue_status(channel_name, bet_value, "infinito")

            normal_count   = len(q_normal.players)   if q_normal   else 0
            infinito_count = len(q_infinito.players) if q_infinito else 0

            embed = create_match_queue_embed(
                channel_name=channel_name,
                bet_value=bet_value,
                queue_normal_count=normal_count,
                queue_infinito_count=infinito_count
            )

            card_key = f"{channel_name}_{bet_value}"

            if card_key in self.active_cards:
                try:
                    await self.active_cards[card_key].edit(embed=embed)
                    return True
                except Exception:
                    pass

            # Fallback: busca no histórico
            async for message in channel.history(limit=50):
                if message.author == channel.guild.me and message.embeds:
                    if f"R$ {bet_value:.2f}" in (message.embeds[0].title or ""):
                        await message.edit(embed=embed)
                        self.active_cards[card_key] = message
                        return True

            return False

        except Exception as e:
            logger.error(f"Erro ao atualizar card: {e}")
            return False

    # ─────────────────────────────────────────────
    # Estatísticas
    # ─────────────────────────────────────────────

    async def get_channel_stats(self, channel_name: str) -> Dict[str, Any]:
        try:
            collection = db.get_collection('matches')
            total     = await collection.count_documents({'channel_name': channel_name})
            active    = await collection.count_documents({
                'channel_name': channel_name,
                'status': {'$in': ['aguardando_pagamento', 'aguardando_inicio', 'em_andamento']}
            })
            completed = await collection.count_documents({
                'channel_name': channel_name,
                'status': 'concluido'
            })
            return {'total': total, 'active': active, 'completed': completed}
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {'total': 0, 'active': 0, 'completed': 0}

    # ─────────────────────────────────────────────
    # Helpers internos
    # ─────────────────────────────────────────────

    async def _ensure_role(
        self,
        guild: discord.Guild,
        name: str,
        color: discord.Color = discord.Color.default(),
        reason: str = ""
    ) -> discord.Role:
        role = discord.utils.get(guild.roles, name=name)
        if not role:
            role = await guild.create_role(name=name, color=color, reason=reason)
            logger.info(f"Cargo '{name}' criado")
        else:
            logger.info(f"Cargo '{name}' já existe")
        return role

    async def _ensure_category(
        self,
        guild: discord.Guild,
        name: str
    ) -> discord.CategoryChannel:
        category = discord.utils.get(guild.categories, name=name)
        if not category:
            category = await guild.create_category(name=name)
            logger.info(f"Categoria '{name}' criada")
        return category

    async def _ensure_text_channel(
        self,
        guild: discord.Guild,
        name: str,
        category: discord.CategoryChannel,
        topic: str = "",
        overwrites: dict = None
    ) -> discord.TextChannel:
        channel = discord.utils.get(guild.text_channels, name=name)
        if not channel:
            channel = await guild.create_text_channel(
                name=name,
                category=category,
                topic=topic,
                overwrites=overwrites or {}
            )
            logger.info(f"Canal '#{name}' criado")
        else:
            # Atualiza permissões se o canal já existir
            if overwrites:
                await channel.edit(overwrites=overwrites, topic=topic)
        return channel

    async def _post_rules_embed(
        self,
        guild: discord.Guild,
        rules_channel: discord.TextChannel
    ):
        """Posta (ou atualiza) o embed fixo de regras no canal"""
        from config.rules import ServerRules

        # Apaga embed anterior do bot
        async for msg in rules_channel.history(limit=10):
            if msg.author == guild.me and msg.embeds:
                await msg.delete()
                break

        rules_embed = ServerRules.get_rules_embed()

        info_embed = discord.Embed(
            title="📩 Como funciona o acesso",
            description=(
                "**1.** Ao entrar no servidor você receberá uma **DM** com os botões.\n"
                "**2.** Você tem **5 minutos** para aceitar.\n"
                "**3.** ✅ Aceitar → cargo **Membro** → acesso a todos os canais.\n"
                "**4.** ❌ Recusar ou não responder → removido automaticamente.\n\n"
                "⚠️ **Certifique-se de ter as DMs abertas para este servidor!**"
            ),
            color=discord.Color.gold()
        )
        info_embed.set_footer(text="X1 Frifas — Sistema de Verificação")

        await rules_channel.send(embeds=[rules_embed, info_embed])

    async def _post_mediator_panel(
        self,
        guild: discord.Guild,
        panel_channel: discord.TextChannel,
        mediator_role: discord.Role,
    ):
        """Posta (ou atualiza) o painel de mediadores"""
        from views.mediator_panel_view import create_mediator_panel_embed, MediatorPanelView

        # Remove painel anterior
        async for msg in panel_channel.history(limit=10):
            if msg.author == guild.me and msg.embeds:
                await msg.delete()
                break

        info  = await mediator_queue.get_queue_info()
        embed = create_mediator_panel_embed(info)
        view  = MediatorPanelView()
        await panel_channel.send(embed=embed, view=view)
        logger.info("Painel de mediadores atualizado")


# Instância global (inicializada no main.py)
channel_service = None
