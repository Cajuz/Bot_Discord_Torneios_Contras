import discord
import asyncio
from typing import Dict, Any
from config.database import db
from config.channels_config import ChannelsConfig
from services.mediator_queue import mediator_queue
from services.match_queue_service import match_queue_service
from views.match_queue_view import create_match_queue_embed, MatchQueueView
from utils.logger import logger, log_success


# ─────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────

MEMBER_ROLE_NAME    = "Membro"
RULES_CHANNEL_NAME  = "📜regras"
AVISOS_CHANNEL_NAME = "📢avisos"
MEDIATOR_ROLE_NAME  = "Controller"
MEDIATOR_PANEL_NAME = "painel-mediadores"
DASHBOARD_CHANNEL_NAME = "dashboard-mediadores"

MEDIATOR_PANEL_CHANNEL_NAME = "painel-mediadores"
MEDIATOR_CHAT_CHANNEL_NAME  = "chat-mediadores"
DASHBOARD_CHANNEL_NAME      = "dashboard-partidas"
RULES_CHANNEL_NAME          = "📜regras"
AVISOS_CHANNEL_NAME         = "📢avisos"

SUPPORT_CHANNEL_NAME       = "suporte"
SUPPORT_CHAT_CHANNEL_NAME  = "chat-suporte"
CHAMADOS_CHANNEL_NAME      = "chamados-suporte"
CHAMADOS_CHAT_CHANNEL_NAME = "chat-chamados"

SPAM_BLOCKED_CHANNEL_NAME = "membros-bloqueados"

CATEGORY_ANALYTICS_NAME = "📈 ANALYTICS"
INFO_CATEGORY_NAME      = "ℹ️ INFORMAÇÕES"
CATEGORY_MEDIATOR_NAME  = "🧑‍⚖️ MEDIADORES"
CATEGORY_SUPPORT_NAME   = "🎫 SUPORTE"
BAN_CONTROL_CATEGORY_NAME = "🚫 BANS-CONTROL"


class ChannelService:

    def __init__(self, bot: discord.Client):
        self.bot          = bot
        self.active_cards: Dict[str, discord.Message] = {}

    # ─────────────────────────────────────────────
    # Setup completo do servidor
    # ─────────────────────────────────────────────

    async def setup_all_channels(self, guild: discord.Guild):
        """
        Ordem:
        0 — 📈 ANALYTICS
        1 — 🚫 Ban-Control  (só ADM)
        2 — ℹ️ INFORMAÇÕES
        3 — 🧑‍⚖️ MEDIADORES
        4 — 🎫 SUPORTE
        5+ — Categorias de partidas
        """
        try:
            logger.info("Iniciando configuração completa do servidor...")

            # ── 1. Cargos ──────────────────────────────────────────
            member_role = await self._ensure_role(
                guild, MEMBER_ROLE_NAME,
                color=discord.Color.green(),
                reason="Cargo padrão — concedido após aceitar regras"
            )
            mediator_role = await self._ensure_role(
                guild, MEDIATOR_ROLE_NAME,
                color=discord.Color.blue(),
                reason="Cargo de mediador"
            )
            support_role = await self._ensure_role(
                guild, SUPPORT_ROLE_NAME,
                color=discord.Color.purple(),
                reason="Cargo de suporte"
            )
            adm_role = await self._ensure_role(
                guild, ADM_ROLE_NAME,
                color=discord.Color.red(),
                reason="Cargo de administrador"
            )

            # ── 2. ANALYTICS (posição 0) ───────────────────────────
            analytics_category = await self._ensure_category(guild, CATEGORY_ANALYTICS_NAME)
            await analytics_category.edit(position=0)

            dashboard_channel = await self.ensure_dashboard_channel(guild, adm_role, analytics_category)
            if dashboard_channel:
                from services.mediador_dashboard_service import mediator_dashboard_service
                await mediator_dashboard_service.update_dashboard_for_channel(dashboard_channel)

            # ── 3. BAN CONTROL (posição 1) — só ADM ───────────────
            await self._setup_ban_control_category(guild, adm_role, position=1)

            # ── 4. INFORMAÇÕES (posição 2) ─────────────────────────
            info_category = await self._ensure_category(guild, INFO_CATEGORY_NAME)
            await info_category.edit(
                position=2,
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=False
                    ),
                    guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True
                    )
                }
            )

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

            await self._ensure_text_channel(
                guild,
                name=AVISOS_CHANNEL_NAME,
                category=info_category,
                topic="Avisos oficiais do servidor.",
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(
                        read_messages=False,
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

            # ── 5. MEDIADORES (posição 3) ──────────────────────────
            controller_category = await self._ensure_category(guild, CATEGORY_MEDIATOR_NAME)
            await controller_category.edit(position=3)

            mediator_channel = await self._ensure_text_channel(
                guild,
                name=MEDIATOR_PANEL_CHANNEL_NAME,
                category=controller_category,
                topic="Painel de controle para mediadores.",
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    member_role:        discord.PermissionOverwrite(view_channel=False),
                    mediator_role: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=False
                    ),
                    adm_role: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True
                    ),
                    guild.me: discord.PermissionOverwrite(
                        view_channel=True,
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
                    adm_role: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True
                    ),
                    guild.me: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True
                    )
                }
            

            # ── 6. SUPORTE (posição 4) ─────────────────────────────
            await self._setup_support_category(
                guild,
                member_role=member_role,
                support_role=support_role,
                adm_role=adm_role,
                position=4
            )

            # ── 7. Categorias de partidas (posição 5+) ─────────────
            game_overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    read_messages=False,
                    send_messages=False
                ),
                member_role: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=False
                ),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_threads=True
                )
            }

            for idx, (category_name, category_data) in enumerate(ChannelsConfig.CATEGORIES.items()):
                game_category = await self._ensure_category(guild, category_name)
                await game_category.edit(position=5 + idx, overwrites=game_overwrites)

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
    # Ban Control — só ADM visualiza
    # ─────────────────────────────────────────────

    async def _setup_ban_control_category(
        self,
        guild: discord.Guild,
        adm_role: discord.Role,
        position: int = 1
    ):
        ban_category = await self._ensure_category(guild, BAN_CONTROL_CATEGORY_NAME)
        await ban_category.edit(
            position=position,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                adm_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True
                )
            }
        )

        await self._ensure_text_channel(
            guild,
            name=SPAM_BLOCKED_CHANNEL_NAME,
            category=ban_category,
            topic="Membros bloqueados por spam — use o botão Desbloquear para liberar o acesso.",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                adm_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True
                )
            }
        )
        logger.info("Categoria Ban-Control configurada com sucesso")

    # ─────────────────────────────────────────────
    # Setup categoria Suporte
    # ─────────────────────────────────────────────

    async def _setup_support_category(
        self,
        guild: discord.Guild,
        member_role: discord.Role,
        support_role: discord.Role,
        adm_role: discord.Role,
        position: int = 4
    ):
        support_category = await self._ensure_category(guild, CATEGORY_SUPPORT_NAME)
        await support_category.edit(position=position)

        suporte_channel = await self._ensure_text_channel(
            guild,
            name=SUPPORT_CHANNEL_NAME,
            category=support_category,
            topic="Abra um ticket ou consulte seu histórico de chamados.",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                member_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    use_application_commands=True
                ),
                support_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False
                ),
                adm_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True
                )
            }
        )
        await self._post_support_panel(guild, suporte_channel)

        await self._ensure_text_channel(
            guild,
            name=SUPPORT_CHAT_CHANNEL_NAME,
            category=support_category,
            topic="Chat de atendimento — converse com a equipe de suporte.",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                member_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                ),
                support_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                ),
                adm_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                )
            }
        )

        await self._ensure_text_channel(
            guild,
            name=CHAMADOS_CHANNEL_NAME,
            category=support_category,
            topic="Chamados abertos — use os botões para assumir.",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                member_role:        discord.PermissionOverwrite(view_channel=False),
                support_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False
                ),
                adm_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True
                )
            }
        )

        await self._ensure_text_channel(
            guild,
            name=CHAMADOS_CHAT_CHANNEL_NAME,
            category=support_category,
            topic="Chat interno da equipe de suporte.",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                member_role:        discord.PermissionOverwrite(view_channel=False),
                support_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                ),
                adm_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                )
            }
        )

        logger.info("Categoria SUPORTE configurada com sucesso")

    # ─────────────────────────────────────────────
    # Painel fixo do suporte
    # ─────────────────────────────────────────────

    async def _post_support_panel(self, guild: discord.Guild, channel: discord.TextChannel):
        from views.ticket_view import TicketPanelView

        async for msg in channel.history(limit=20):
            if msg.author == guild.me and msg.embeds:
                await msg.delete()
                break

        embed = discord.Embed(
            title="🎫 Central de Suporte",
            description=(
                "Bem-vindo à Central de Suporte!\n\n"
                "**📋 Abrir Ticket** — Relate um problema ou dúvida.\n"
                "**📂 Ver Histórico** — Consulte seus chamados anteriores.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "**Como funciona:**\n"
                "1. Clique em **Abrir Ticket**\n"
                "2. Selecione a **categoria** do problema\n"
                "3. Descreva o problema em detalhes\n"
                "4. Aguarde — um atendente entrará em contato via **DM**\n\n"
                "⚠️ Só é permitido **1 chamado ativo** por vez.\n\n"
                "❗ Feche o atual com `!fechar_chamado <id>`."
            ),
            color=discord.Color.purple()
        )
        embed.set_footer(text="Use !fechar_chamado <id> apenas se quiser fechar seu chamado ativo!")
        view = TicketPanelView(self.bot)
        await channel.send(embed=embed, view=view)
        logger.info("Painel de suporte postado em #suporte")

    # ─────────────────────────────────────────────
    # Dashboard
    # ─────────────────────────────────────────────

    async def ensure_dashboard_channel(
        self,
        guild: discord.Guild,
        adm_role: discord.Role = None,
        analytics_category: discord.CategoryChannel = None
    ) -> discord.TextChannel | None:
        try:
            if not adm_role:
                adm_role = discord.utils.get(guild.roles, name=ADM_ROLE_NAME)
                if not adm_role:
                    adm_role = await guild.create_role(
                        name=ADM_ROLE_NAME,
                        color=discord.Color.red(),
                        mentionable=True
                    )
            if not analytics_category:
                analytics_category = await self._ensure_category(guild, CATEGORY_ANALYTICS_NAME)

            channel = await self._ensure_text_channel(
                guild,
                name=DASHBOARD_CHANNEL_NAME,
                category=analytics_category,
                topic="📊 Dashboard automático de partidas — atualizado diariamente",
                overwrites={
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
            )
            return channel

        except discord.Forbidden:
            logger.error(f"Sem permissão para criar canal Analytics em {guild.name}")
            return None
        except Exception as e:
            logger.error(f"Erro no ensure_dashboard_channel: {e}")
            return None

    # ─────────────────────────────────────────────
    # Cards de fila
    # ─────────────────────────────────────────────

    async def setup_queue_cards(self, guild: discord.Guild, channel: discord.TextChannel) -> bool:
        try:
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
                view    = MatchQueueView(channel_name=channel_name, bet_value=bet_value)
                message = await channel.send(embed=embed, view=view)
                self.active_cards[f"{channel_name}_{bet_value}"] = message
                await asyncio.sleep(0.5)

            logger.info(f"Cards configurados em #{channel_name}")
            return True

        except Exception as e:
            logger.error(f"Erro ao configurar cards em #{channel.name}: {e}")
            return False

    async def refresh_queue_card(self, channel: discord.TextChannel, bet_value: float) -> bool:
        try:
            channel_name = channel.name
            q_normal     = await match_queue_service.get_queue_status(channel_name, bet_value, "normal")
            q_infinito   = await match_queue_service.get_queue_status(channel_name, bet_value, "infinito")
            normal_count   = len(q_normal.players)   if q_normal   else 0
            infinito_count = len(q_infinito.players) if q_infinito else 0

            embed    = create_match_queue_embed(
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
            col       = db.get_collection('matches')
            total     = await col.count_documents({'channel_name': channel_name})
            active    = await col.count_documents({
                'channel_name': channel_name,
                'status': {'$in': ['aguardando_pagamento', 'aguardando_inicio', 'em_andamento']}
            })
            completed = await col.count_documents({
                'channel_name': channel_name,
                'status': 'finalizado'
            })
            return {'total': total, 'active': active, 'completed': completed}
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {'total': 0, 'active': 0, 'completed': 0}

    # ─────────────────────────────────────────────
    # Helpers internos
    # ─────────────────────────────────────────────

    async def _ensure_role(self, guild, name, color=discord.Color.default(), reason="") -> discord.Role:
        role = discord.utils.get(guild.roles, name=name)
        if not role:
            role = await guild.create_role(name=name, color=color, reason=reason)
            logger.info(f"Cargo '{name}' criado")
        else:
            logger.info(f"Cargo '{name}' já existe")
        return role

    async def _ensure_category(self, guild, name) -> discord.CategoryChannel:
        category = discord.utils.get(guild.categories, name=name)
        if not category:
            category = await guild.create_category(name=name)
            logger.info(f"Categoria '{name}' criada")
        return category

    async def _ensure_text_channel(
        self, guild, name, category, topic="", overwrites=None
    ) -> discord.TextChannel:
        channel = discord.utils.get(guild.text_channels, name=name)
        if not channel:
            channel = await guild.create_text_channel(
                name=name, category=category, topic=topic, overwrites=overwrites or {}
            )
            logger.info(f"Canal '#{name}' criado")
        else:
            await channel.edit(category=category, topic=topic, overwrites=overwrites or {})
        return channel

    async def _post_rules_embed(self, guild: discord.Guild, rules_channel: discord.TextChannel):
        from config.rules import ServerRules

        async for msg in rules_channel.history(limit=10):
            if msg.author == guild.me and msg.embeds:
                await msg.delete()
                break

        rules_embed = ServerRules.get_rules_embed()
        info_embed  = discord.Embed(
            title="📩 Como funciona o acesso",
            description=(
                "**1.** Ao entrar no servidor você receberá uma **DM** com os botões.\n"
                "**2.** Você tem **30 minutos** para aceitar.\n"
                "**3.** ✅ Aceitar → CAPTCHA → cargo **Membro** → acesso a todos os canais.\n"
                "**4.** ❌ Recusar ou não responder → removido automaticamente.\n\n"
                "⚠️ **Certifique-se de ter as DMs abertas para este servidor!**"
            ),
            color=discord.Color.gold()
        )
        await rules_channel.send(embeds=[rules_embed, info_embed])

    async def _post_mediator_panel(
        self,
        guild: discord.Guild,
        panel_channel: discord.TextChannel,
        mediator_role: discord.Role,
    ):
        """Posta (ou atualiza) o painel de mediadores"""
        from views.mediator_panel_view import create_mediator_panel_embed, MediatorPanelView

        async for msg in panel_channel.history(limit=10):
            if msg.author == guild.me and msg.embeds:
                await msg.delete()
                break

        info  = await mediator_queue.get_queue_info()
        embed = create_mediator_panel_embed(info)
        view  = MediatorPanelView()
        await panel_channel.send(embed=embed, view=view)
        logger.info("Painel de mediadores atualizado")


channel_service = None
