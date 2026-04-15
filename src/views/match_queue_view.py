from __future__ import annotations
import os

import discord
from typing import Optional

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
    if name.endswith("-mob"):   category = "Mobile"
    elif name.endswith("-emu"): category = "Emulador"
    elif name.endswith("-misto"): category = "Misto"
    else:                         category = ""
    return f"{channel_name.upper()} {category}".strip()


def is_1x1_mob(channel_name: str) -> bool:
    return channel_name.lower().startswith("1x1-mob")


async def _player_has_active_match(player_id: int) -> bool:
    try:
        col = db.get_collection("matches")
        active_statuses = [
            "aguardando_pagamento", "aguardando_inicio",
            "em_andamento", "aguardando_premio",
        ]
        doc = await col.find_one({
            "player_ids": str(player_id),
            "status":     {"$in": active_statuses},
        })
        return doc is not None
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Builder de embed
# ─────────────────────────────────────────────────────────────

def create_match_queue_embed(
    channel_name:         str,
    bet_value:            float,
    queue_normal_count:   int = 0,
    queue_infinito_count: int = 0,
    locked_gel:           Optional[str] = None,
    max_players:          int = 2,
) -> discord.Embed:
    """
    Canal 1x1-mob → duas filas (Gel Normal / Gel Infinito).
    Demais canais   → fila única.
    """
    bet_str = f"{bet_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    is_1x1  = is_1x1_mob(channel_name)

    if locked_gel == "all":
        color = 0xE74C3C
    elif locked_gel:
        color = 0xF39C12
    else:
        color = 0x2ECC71

    embed = discord.Embed(
        title=f"R$ {bet_str}",
        description=f"**Modo:** {_channel_label(channel_name)}",
        color=THEME2,
    )
    embed.set_image(url="attachment://banner.png")

    if is_1x1:
        normal_status   = "🔒 Confirmando..." if locked_gel in ("normal",   "all") else f"{queue_normal_count}/{max_players}"
        infinito_status = "🔒 Confirmando..." if locked_gel in ("infinito", "all") else f"{queue_infinito_count}/{max_players}"
        embed.add_field(name="Gel Normal",   value=normal_status,   inline=True)
        embed.add_field(name="Gel Infinito", value=infinito_status, inline=True)
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
    Ao registrar como persistent view (main.py), channel_name fica vazio —
    nesse caso os botões são definidos pelos custom_ids e o contexto é lido do embed.
    Ao criar o card real (match_cog), channel_name é informado e os botões
    corretos são renderizados.
    """

    def __init__(
        self,
        channel_name: str   = "",
        bet_value:    float = 0.0,
        locked_gel:   str   = None,
    ):
        super().__init__(timeout=None)
        self.channel_name = channel_name
        self.bet_value    = bet_value
        self.locked_gel   = locked_gel

        # Só esconde/mostra botões quando channel_name está definido
        # (evita erro no registro de persistent view sem parâmetros)
        if channel_name:
            if is_1x1_mob(channel_name):
                self.remove_item(self.btn_entrar)
            else:
                self.remove_item(self.btn_gel_normal)
                self.remove_item(self.btn_gel_infinito)

    def _parse_context(
        self, interaction: discord.Interaction
    ) -> tuple[str, float]:
        if self.channel_name and self.bet_value:
            return self.channel_name, self.bet_value
        try:
            embed     = interaction.message.embeds[0]
            bet_str   = embed.title.replace("R$ ", "").replace(".", "").replace(",", ".")
            bet_value = float(bet_str)
            desc      = embed.description or ""
            raw       = desc.replace("**Modo:** ", "").split(" ")[0].lower()
            return raw, bet_value
        except Exception as e:
            logger.error(f"[Queue] Erro ao parsear contexto do embed: {e}")
            return "", 0.0

    # ── Botão Entrar (demais modos) ──────────────────────────────
    @discord.ui.button(
        label="✔️ ENTRAR NA FILA",
        style=discord.ButtonStyle.green,
        custom_id="queue_entrar",
    )
    async def btn_entrar(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        ch, bet = self._parse_context(interaction)
        await self._handle_join(interaction, "normal", ch, bet)

    # ── Botões Gel (somente 1x1-mob) ───────────────────────────
    @discord.ui.button(
        label="Gel Normal",
        style=discord.ButtonStyle.green,
        custom_id="queue_gel_normal",
    )
    async def btn_gel_normal(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        ch, bet = self._parse_context(interaction)
        await self._handle_join(interaction, "normal", ch, bet)

    @discord.ui.button(
        label="Gel Infinito",
        style=discord.ButtonStyle.blurple,
        custom_id="queue_gel_infinito",
    )
    async def btn_gel_infinito(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        ch, bet = self._parse_context(interaction)
        await self._handle_join(interaction, "infinito", ch, bet)

    # ── Botão Sair (todos os canais) ────────────────────────────
    @discord.ui.button(
        label="✖️ SAIR DA FILA",
        style=discord.ButtonStyle.red,
        custom_id="queue_sair",
    )
    async def btn_sair(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        ch, bet = self._parse_context(interaction)
        await self._leave_queue(interaction, ch, bet)

    # ── Lógica de entrada ───────────────────────────────────────

    async def _handle_join(
        self,
        interaction:  discord.Interaction,
        gel_type:     str,
        channel_name: str,
        bet_value:    float,
    ):
        try:
            if await _player_has_active_match(interaction.user.id):
                await interaction.response.send_message(
                    "Você já está em uma partida ativa. "
                    "Finalize-a antes de entrar em uma nova fila.",
                    ephemeral=True)
                return

            current_q = await match_queue_service.get_queue_status(
                channel_name, bet_value, gel_type)
            if current_q and current_q.status == MatchQueue.STATUS_CONFIRMING:
                await interaction.response.send_message(
                    "Uma confirmação está em andamento para este valor e gel. "
                    "Aguarde ela terminar para entrar na próxima fila.",
                    ephemeral=True)
                return

            if is_1x1_mob(channel_name):
                other_gel   = "infinito" if gel_type == "normal" else "normal"
                other_queue = await match_queue_service.get_queue_status(
                    channel_name, bet_value, other_gel)
                if other_queue and interaction.user.id in other_queue.players:
                    await interaction.response.send_message(
                        f"Você já está na fila de Gel {other_gel.capitalize()}. "
                        "Saia dela primeiro.", ephemeral=True)
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
                    ephemeral=True)
                await match_queue_service.start_confirmation_timer(
                    queue=queue,
                    bot=interaction.client,
                    channel=interaction.channel,
                )
            else:
                await interaction.response.send_message(message, ephemeral=True)
                await self._refresh_card(interaction, channel_name, bet_value)

        except Exception as e:
            logger.error(f"[Queue] Erro ao entrar na fila: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Erro ao entrar na fila.", ephemeral=True)

    # ── Lógica de saída ────────────────────────────────────────

    async def _leave_queue(
        self,
        interaction:  discord.Interaction,
        channel_name: str,
        bet_value:    float,
    ):
        try:
            gel_types = ["normal", "infinito"] if is_1x1_mob(channel_name) else ["normal"]
            removed   = False

            for gel in gel_types:
                ok, queue = await match_queue_service.remove_player_from_queue(
                    channel_name, bet_value, gel, interaction.user.id)
                if ok:
                    removed = True

            if removed:
                await interaction.response.send_message(
                    "Você saiu da fila.", ephemeral=True)
                await self._refresh_card(interaction, channel_name, bet_value)
            else:
                await interaction.response.send_message(
                    "Você não está em nenhuma fila deste valor.", ephemeral=True)
        except Exception as e:
            logger.error(f"[Queue] Erro ao sair da fila: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Erro ao sair da fila.", ephemeral=True)

    # ── Refresh do card ────────────────────────────────────────

    async def _refresh_card(
        self,
        interaction:  discord.Interaction,
        channel_name: str,
        bet_value:    float,
    ):
        try:
            q_normal   = await match_queue_service.get_queue_status(
                channel_name, bet_value, "normal")
            q_infinito = await match_queue_service.get_queue_status(
                channel_name, bet_value, "infinito")

            normal_count   = len(q_normal.players)   if q_normal   else 0
            infinito_count = len(q_infinito.players) if q_infinito else 0

            locked_gel = None
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

            view = MatchQueueView(
                channel_name=channel_name,
                bet_value=bet_value,
                locked_gel=locked_gel,
            )

            file = get_banner_file(channel_name)

            if file:
                embed.set_image(url=f"attachment://{file.filename}")
                await interaction.message.edit(
                    embed=embed, view=view, attachments=[file])
            else:
                await interaction.message.edit(embed=embed, view=view)

        except Exception as e:
            logger.warning(f"[Queue] Erro ao atualizar card: {e}")
