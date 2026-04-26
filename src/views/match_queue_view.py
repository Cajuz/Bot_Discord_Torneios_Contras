from __future__ import annotations
import os
import re

import discord
from typing import Optional

from discord import guild
from discord import channel

from services.match_queue_service import match_queue_service
from models.queue import MatchQueue
from models.match import Match
from config.database import db
from config.channels_config import ChannelsConfig
from services.dashboard_service import THEME2
from views.imagens import get_banner_file
from utils.logger import logger
from discord import Interaction


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def _channel_label(channel_name: str) -> str:
    name = channel_name.lower()
    if name.endswith("-mob"):
        category = "Mobile"
    elif name.endswith("-emu"):
        category = "Emulador"
    elif name.endswith("-misto"):
        category = "Misto"
    else:
        category = ""
    return f"{channel_name.upper()} {category}".strip()


def is_1x1_mob(channel_name: str) -> bool:
    return channel_name.lower().startswith("📱1x1-mob")


def is_mob(channel_name: str) -> bool:
    """Mobile que NÃO é 1x1 (ex: 4v4-mob, 2v2-mob)"""
    name = channel_name.lower()
    return name.endswith("-mob") and not is_1x1_mob(channel_name)


def is_emu(channel_name: str) -> bool:
    """Canais emulador (ex: 3v3-emu, 4v4-emu)"""
    return channel_name.lower().endswith("-emu")


def is_misto(channel_name: str) -> bool:
    """Canais misto (ex: 2v2-misto, 3v3-misto, 4v4-misto)"""
    return channel_name.lower().endswith("-misto")


def get_misto_max_emus(channel_name: str) -> int:
    """
    Retorna quantos botões de emulador o canal misto deve ter:
      2v2-misto → 1 emu
      3v3-misto → 2 emus
      4v4-misto → 3 emus
    """
    name = channel_name.lower()
    match = re.match(r".*?(\d+)v\d+-misto", name)
    if match:
        n = int(match.group(1))
        return max(1, n - 1)
    return 1


async def _player_has_active_match(player_id: int) -> bool:
    try:
        col = db.get_collection("matches")
        active_statuses = [
            "aguardando_pagamento", "aguardando_inicio",
            "em_andamento", "aguardando_premio",
        ]
        doc = await col.find_one({
            "player_ids": str(player_id),
            "status": {"$in": active_statuses},
        })
        return doc is not None
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Builder de embed
# ─────────────────────────────────────────────────────────────


def create_match_queue_embed(
    channel_name: str,
    bet_value: float,
    queue_normal_count: int = 0,
    queue_infinito_count: int = 0,
    locked_gel: Optional[str] = None,
    max_players: int = 2,
    # contagens para filas misto (por slot de emu)
    queue_emu1_count: int = 0,
    queue_emu2_count: int = 0,
    queue_emu3_count: int = 0,
) -> discord.Embed:
    """
    Canal 1x1-mob    → duas filas (Gel Normal / Gel Infinito).
    Canal mob / emu  → duas filas (Entrar na Fila / Full Ump e Xm8).
    Canal misto 2v2  → fila 1 Emu.
    Canal misto 3v3  → filas 1 Emu e 2 Emu.
    Canal misto 4v4  → filas 1 Emu, 2 Emu e 3 Emu.
    """
    bet_str = f"{bet_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    if locked_gel == "all":
        color = 0xE74C3C
    elif locked_gel:
        color = 0xF39C12
    else:
        color = 0x2ECC71

    embed = discord.Embed(
        title=f"R$ {bet_str}",
        description=f"**Modo:** {_channel_label(channel_name)}",
        color=THEME2 if THEME2 else color,
    )
    embed.set_thumbnail(url="attachment://banner.png")

    if is_1x1_mob(channel_name):
        normal_status   = "🔒 Confirmando..." if locked_gel in ("normal", "all")   else f"{queue_normal_count}/{max_players}"
        infinito_status = "🔒 Confirmando..." if locked_gel in ("infinito", "all") else f"{queue_infinito_count}/{max_players}"
        embed.add_field(name="Gel Normal",   value=normal_status,   inline=True)
        embed.add_field(name="Gel Infinito", value=infinito_status, inline=True)

    elif is_mob(channel_name) or is_emu(channel_name):
        normal_status  = "🔒 Confirmando..." if locked_gel in ("normal", "all")    else f"{queue_normal_count}/{max_players}"
        fullump_status = "🔒 Confirmando..." if locked_gel in ("fullump", "all")   else f"{queue_infinito_count}/{max_players}"
        embed.add_field(name="Fila Normal",      value=normal_status,  inline=True)
        embed.add_field(name="Full Ump e Xm8",   value=fullump_status, inline=True)

    elif is_misto(channel_name):
        max_emus = get_misto_max_emus(channel_name)
        counts = [queue_emu1_count, queue_emu2_count, queue_emu3_count]
        for i in range(max_emus):
            status = "🔒 Confirmando..." if locked_gel == f"emu{i+1}" or locked_gel == "all" else f"{counts[i]}/{max_players}"
            embed.add_field(name=f"{i+1} Emu", value=status, inline=True)

    else:
        normal_status = "🔒 Confirmando..." if locked_gel else f"{queue_normal_count}/{max_players}"
        embed.add_field(name="Jogadores na fila", value=normal_status, inline=True)

    embed.set_footer(text="Use os botões abaixo para entrar ou sair da fila")
    return embed


# ─────────────────────────────────────────────────────────────
# View
# ─────────────────────────────────────────────────────────────


class MatchQueueView(discord.ui.View):
    """
    View de fila de partidas.

    Lógica de botões por tipo de canal:
      1x1-mob   → Gel Normal + Gel Infinito + Sair
      mob / emu → Entrar na Fila + Full Ump e Xm8 + Sair
      2v2-misto → 1 Emu + Sair
      3v3-misto → 1 Emu + 2 Emu + Sair
      4v4-misto → 1 Emu + 2 Emu + 3 Emu + Sair
    """

    def __init__(
        self,
        channel_name: str = "",
        bet_value: float = 0.0,
        locked_gel: str = None,
        guild: discord.Guild = None,
    ):
        super().__init__(timeout=None)
        self.channel_name = channel_name
        self.bet_value = bet_value
        self.locked_gel = locked_gel
        self.guild = guild

        aprovar_emoji = discord.utils.get(guild.emojis, name="aprovar") if guild else None
        cancelar_emoji = discord.utils.get(guild.emojis, name="cancelar") if guild else None
        gel_emoji = discord.utils.get(guild.emojis, name="gel") if guild else None

        self.btn_entrar.emoji = aprovar_emoji
        self.btn_sair.emoji = cancelar_emoji
        self.btn_gel_normal.emoji = gel_emoji
        self.btn_gel_infinito.emoji = gel_emoji
        self.btn_full_ump_xm8.emoji = aprovar_emoji

        if channel_name:
            if is_1x1_mob(channel_name):
                # 1x1: remove botões não pertinentes
                self.remove_item(self.btn_entrar)
                self.remove_item(self.btn_full_ump_xm8)
                self.remove_item(self.btn_1_emu)
                self.remove_item(self.btn_2_emu)
                self.remove_item(self.btn_3_emu)

            elif is_mob(channel_name) or is_emu(channel_name):
                # Mobile (exceto 1x1) e Emulador: Entrar + Full Ump e Xm8 + Sair
                self.remove_item(self.btn_gel_normal)
                self.remove_item(self.btn_gel_infinito)
                self.remove_item(self.btn_1_emu)
                self.remove_item(self.btn_2_emu)
                self.remove_item(self.btn_3_emu)

            elif is_misto(channel_name):
                # Misto: apenas botões de emu conforme o tamanho da partida
                self.remove_item(self.btn_entrar)
                self.remove_item(self.btn_full_ump_xm8)
                self.remove_item(self.btn_gel_normal)
                self.remove_item(self.btn_gel_infinito)
                max_emus = get_misto_max_emus(channel_name)
                if max_emus < 3:
                    self.remove_item(self.btn_3_emu)
                if max_emus < 2:
                    self.remove_item(self.btn_2_emu)

            else:
                # Fallback: apenas fila normal
                self.remove_item(self.btn_gel_normal)
                self.remove_item(self.btn_gel_infinito)
                self.remove_item(self.btn_full_ump_xm8)
                self.remove_item(self.btn_1_emu)
                self.remove_item(self.btn_2_emu)
                self.remove_item(self.btn_3_emu)

    def _parse_context(self, interaction: discord.Interaction) -> tuple[str, float]:
        if self.channel_name and self.bet_value:
            return self.channel_name, self.bet_value
        try:
            embed = interaction.message.embeds[0]
            bet_str = embed.title.replace("R$ ", "").replace(".", "").replace(",", ".")
            bet_value = float(bet_str)
            desc = embed.description or ""
            raw = desc.replace("**Modo:** ", "").split(" ")[0].lower()
            return raw, bet_value
        except Exception as e:
            logger.error(f"[Queue] Erro ao parsear contexto do embed: {e}")
            return "", 0.0

    # ── Botões 1x1-mob ──────────────────────────────────────────

    @discord.ui.button(
        label="Gel Normal",
        style=discord.ButtonStyle.secondary,
        custom_id="queue_gel_normal",
    )
    async def btn_gel_normal(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        ch, bet = self._parse_context(interaction)
        await self._handle_join(interaction, "normal", ch, bet)

    @discord.ui.button(
        label="Gel Infinito",
        style=discord.ButtonStyle.secondary,
        custom_id="queue_gel_infinito",
    )
    async def btn_gel_infinito(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        ch, bet = self._parse_context(interaction)
        await self._handle_join(interaction, "infinito", ch, bet)

    # ── Botões Mobile / Emulador ────────────────────────────────

    @discord.ui.button(
        label="ENTRAR NA FILA",
        style=discord.ButtonStyle.secondary,
        custom_id="queue_entrar",
    )
    async def btn_entrar(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        ch, bet = self._parse_context(interaction)
        await self._handle_join(interaction, "normal", ch, bet)

    @discord.ui.button(
        label="Full Ump e Xm8",
        style=discord.ButtonStyle.secondary,
        custom_id="queue_full_ump_xm8",
    )
    async def btn_full_ump_xm8(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        ch, bet = self._parse_context(interaction)
        await self._handle_join(interaction, "fullump", ch, bet)

    # ── Botões Misto ────────────────────────────────────────────

    @discord.ui.button(
        label="1 Emu",
        style=discord.ButtonStyle.secondary,
        custom_id="queue_1_emu",
    )
    async def btn_1_emu(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        ch, bet = self._parse_context(interaction)
        await self._handle_join(interaction, "emu1", ch, bet)

    @discord.ui.button(
        label="2 Emu",
        style=discord.ButtonStyle.secondary,
        custom_id="queue_2_emu",
    )
    async def btn_2_emu(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        ch, bet = self._parse_context(interaction)
        await self._handle_join(interaction, "emu2", ch, bet)

    @discord.ui.button(
        label="3 Emu",
        style=discord.ButtonStyle.secondary,
        custom_id="queue_3_emu",
    )
    async def btn_3_emu(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        ch, bet = self._parse_context(interaction)
        await self._handle_join(interaction, "emu3", ch, bet)

    # ── Sair (universal) ────────────────────────────────────────

    @discord.ui.button(
        label="SAIR DA FILA",
        style=discord.ButtonStyle.danger,
        custom_id="queue_sair",
    )
    async def btn_sair(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        ch, bet = self._parse_context(interaction)
        await self._leave_queue(interaction, ch, bet)

    async def _handle_join(
        self,
        interaction: discord.Interaction,
        gel_type: str,
        channel_name: str,
        bet_value: float,
    ):
        try:
            if await _player_has_active_match(interaction.user.id):
                await interaction.response.send_message(
                    "Você já está em uma partida ativa. Finalize-a antes de entrar em uma nova fila.",
                    ephemeral=True,
                )
                return

            current_q = await match_queue_service.get_queue_status(channel_name, bet_value, gel_type)
            if current_q and current_q.status == MatchQueue.STATUS_CONFIRMING:
                await interaction.response.send_message(
                    "Uma confirmação está em andamento para este valor. Aguarde ela terminar para entrar na próxima fila.",
                    ephemeral=True,
                )
                return

            if is_1x1_mob(channel_name):
                other_gel = "infinito" if gel_type == "normal" else "normal"
                other_queue = await match_queue_service.get_queue_status(channel_name, bet_value, other_gel)
                if other_queue and interaction.user.id in other_queue.players:
                    await interaction.response.send_message(
                        f"Você já está na fila de Gel {other_gel.capitalize()}. Saia dela primeiro.",
                        ephemeral=True,
                    )
                    return

            success, queue, message = await match_queue_service.add_player_to_queue(
                channel_name=channel_name,
                bet_value=bet_value,
                gel_type=gel_type,
                max_players=2,
                player_id=interaction.user.id,
            )

            if not success:
                await interaction.response.send_message(message, ephemeral=True)
                return

            if message == "full":
                await interaction.response.send_message(
                    "Fila completa! Um tópico de confirmação foi aberto.",
                    ephemeral=True,
                )
                await match_queue_service.start_confirmation_timer(
                    queue=queue,
                    bot=interaction.client,
                    channel=interaction.channel,
                )
                await self._refresh_card(interaction, channel_name, bet_value)
            else:
                await interaction.response.send_message(message, ephemeral=True)
                await self._refresh_card(interaction, channel_name, bet_value)

        except Exception as e:
            logger.error(f"[Queue] Erro ao entrar na fila: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Erro ao entrar na fila.", ephemeral=True
                )

    async def _leave_queue(
        self,
        interaction: discord.Interaction,
        channel_name: str,
        bet_value: float,
    ):
        try:
            if is_1x1_mob(channel_name):
                gel_types = ["normal", "infinito"]
            elif is_mob(channel_name) or is_emu(channel_name):
                gel_types = ["normal", "fullump"]
            elif is_misto(channel_name):
                max_emus = get_misto_max_emus(channel_name)
                gel_types = [f"emu{i+1}" for i in range(max_emus)]
            else:
                gel_types = ["normal"]

            removed = False
            for gel in gel_types:
                ok, queue = await match_queue_service.remove_player_from_queue(
                    channel_name, bet_value, gel, interaction.user.id
                )
                if ok:
                    removed = True

            if removed:
                await interaction.response.send_message(
                    "Você saiu da fila.", ephemeral=True
                )
                await self._refresh_card(interaction, channel_name, bet_value)
            else:
                await interaction.response.send_message(
                    "Você não está em nenhuma fila deste valor.", ephemeral=True
                )
        except Exception as e:
            logger.error(f"[Queue] Erro ao sair da fila: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Erro ao sair da fila.", ephemeral=True
                )

    async def _refresh_card(
        self,
        interaction: discord.Interaction,
        channel_name: str,
        bet_value: float,
    ):
        try:
            locked_gel = None

            if is_1x1_mob(channel_name):
                q_normal   = await match_queue_service.get_queue_status(channel_name, bet_value, "normal")
                q_infinito = await match_queue_service.get_queue_status(channel_name, bet_value, "infinito")
                normal_count   = len(q_normal.players)   if q_normal   else 0
                infinito_count = len(q_infinito.players) if q_infinito else 0
                if q_normal   and q_normal.status   == MatchQueue.STATUS_CONFIRMING:
                    locked_gel = "normal"
                if q_infinito and q_infinito.status == MatchQueue.STATUS_CONFIRMING:
                    locked_gel = "infinito" if locked_gel is None else "all"
                embed = create_match_queue_embed(
                    channel_name=channel_name,
                    bet_value=bet_value,
                    queue_normal_count=normal_count,
                    queue_infinito_count=infinito_count,
                    locked_gel=locked_gel,
                )

            elif is_mob(channel_name) or is_emu(channel_name):
                q_normal  = await match_queue_service.get_queue_status(channel_name, bet_value, "normal")
                q_fullump = await match_queue_service.get_queue_status(channel_name, bet_value, "fullump")
                normal_count  = len(q_normal.players)  if q_normal  else 0
                fullump_count = len(q_fullump.players) if q_fullump else 0
                if q_normal  and q_normal.status  == MatchQueue.STATUS_CONFIRMING:
                    locked_gel = "normal"
                if q_fullump and q_fullump.status == MatchQueue.STATUS_CONFIRMING:
                    locked_gel = "fullump" if locked_gel is None else "all"
                embed = create_match_queue_embed(
                    channel_name=channel_name,
                    bet_value=bet_value,
                    queue_normal_count=normal_count,
                    queue_infinito_count=fullump_count,
                    locked_gel=locked_gel,
                )

            elif is_misto(channel_name):
                max_emus = get_misto_max_emus(channel_name)
                counts = []
                for i in range(3):
                    if i < max_emus:
                        q = await match_queue_service.get_queue_status(channel_name, bet_value, f"emu{i+1}")
                        counts.append(len(q.players) if q else 0)
                        if q and q.status == MatchQueue.STATUS_CONFIRMING:
                            locked_gel = f"emu{i+1}" if locked_gel is None else "all"
                    else:
                        counts.append(0)
                embed = create_match_queue_embed(
                    channel_name=channel_name,
                    bet_value=bet_value,
                    locked_gel=locked_gel,
                    queue_emu1_count=counts[0],
                    queue_emu2_count=counts[1],
                    queue_emu3_count=counts[2],
                )

            else:
                q_normal = await match_queue_service.get_queue_status(channel_name, bet_value, "normal")
                normal_count = len(q_normal.players) if q_normal else 0
                if q_normal and q_normal.status == MatchQueue.STATUS_CONFIRMING:
                    locked_gel = "normal"
                embed = create_match_queue_embed(
                    channel_name=channel_name,
                    bet_value=bet_value,
                    queue_normal_count=normal_count,
                    locked_gel=locked_gel,
                )

            view = MatchQueueView(
                channel_name=channel_name,
                bet_value=bet_value,
                locked_gel=locked_gel,
                guild=interaction.guild,
            )

            file = get_banner_file(channel_name)
            if file:
                embed.set_thumbnail(url=f"attachment://{file.filename}")
                await interaction.message.edit(embed=embed, view=view, attachments=[file])
            else:
                await interaction.message.edit(embed=embed, view=view)

        except Exception as e:
            logger.warning(f"[Queue] Erro ao atualizar card: {e}")
