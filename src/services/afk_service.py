"""
afk_service.py — AFK Check para mediadores.

  • Na fila: 5 min sem ação → alerta DM → 2 min para confirmar → remove
  • Em partida (antes de confirmar pagamento): 5 min sem interagir →
    substitui mediador, avisa jogadores por DM e loga em #logs-mediadores
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import tasks

from config.database import db
from utils.datetime_utils import utcnow
from utils.logger import logger

THEME_COLOR    = 0xFFD54F
AFK_TIMEOUT    = timedelta(minutes=5)
CONFIRM_WINDOW = timedelta(minutes=2)


class AFKService:

    def __init__(self):
        self.bot: Optional[discord.Client] = None
        self._queue_activity:   dict[int, datetime]      = {}
        self._match_activity:   dict[int, datetime]      = {}
        self._pending_confirm:  dict[int, asyncio.Task]  = {}
        # Proteção contra substituição dupla: match_id → True
        self._replacing_match:  dict[str, bool]          = {}

    # ─────────────────────────────────────────
    # Atividade
    # ─────────────────────────────────────────

    def mark_queue_activity(self, mediator_id: int):
        self._queue_activity[mediator_id] = utcnow()

    def mark_match_activity(self, mediator_id: int):
        now = utcnow()
        self._match_activity[mediator_id] = now
        self._queue_activity[mediator_id] = now

    def remove_mediator(self, mediator_id: int):
        self._queue_activity.pop(mediator_id, None)
        self._match_activity.pop(mediator_id, None)
        task = self._pending_confirm.pop(mediator_id, None)
        if task and not task.done():
            task.cancel()

    # ─────────────────────────────────────────
    # AFK na fila
    # ─────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def check_queue_afk(self):
        if not self.bot:
            return
        collection = db.get_collection("mediators")
        # ← usa discord_id (string) consistente com o modelo Mediator
        in_queue = await collection.find(
            {"in_queue": True, "is_active": True}).to_list(None)
        now = utcnow()
        for doc in in_queue:
            uid = int(doc.get("discord_id", 0))
            if not uid:
                continue
            if uid in self._pending_confirm:
                continue
            last = self._queue_activity.get(uid, doc.get("updated_at", now))
            if isinstance(last, datetime) and (now - last) >= AFK_TIMEOUT:
                asyncio.create_task(self._warn_and_remove_queue(uid, doc))

    @check_queue_afk.before_loop
    async def before_check_queue_afk(self):
        if self.bot:
            await self.bot.wait_until_ready()

    async def _warn_and_remove_queue(self, uid: int, doc: dict):
        if uid in self._pending_confirm:
            return
        try:
            user = await self.bot.fetch_user(uid)
        except Exception:
            await self._remove_from_queue(uid)
            return

        view  = _AFK_ConfirmView(uid, self)
        embed = discord.Embed(
            title="Você ainda está na fila?",
            description=(
                "Detectamos **5 minutos** de inatividade.\n"
                "Clique em **Confirmar Presença** em 2 minutos "
                "ou será removido da fila."
            ),
            color=THEME_COLOR
        )
        try:
            msg = await user.send(embed=embed, view=view)
        except Exception:
            await self._remove_from_queue(uid)
            return

        async def _timeout():
            await asyncio.sleep(CONFIRM_WINDOW.total_seconds())
            if uid in self._pending_confirm:
                self._pending_confirm.pop(uid, None)
                await self._remove_from_queue(uid)
                try:
                    await user.send(embed=discord.Embed(
                        description="Você foi removido da fila por **inatividade**.",
                        color=0xE74C3C
                    ))
                    await msg.edit(view=None)
                except Exception:
                    pass

        task = asyncio.create_task(_timeout())
        self._pending_confirm[uid] = task

    async def _remove_from_queue(self, uid: int):
        collection = db.get_collection("mediators")
        await collection.update_one(
            {"discord_id": str(uid)},
            {"$set": {"in_queue": False, "updated_at": utcnow()}}
        )
        from services.mediator_queue import mediator_queue
        try:
            mediator_queue.queue.remove(uid)
        except (ValueError, AttributeError):
            pass
        logger.info(f"[AFK] Mediador {uid} removido da fila por inatividade.")
        await self._log_afk(uid, "Removido da fila por inatividade.")

    # ─────────────────────────────────────────
    # AFK em partida ativa
    # ─────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def check_match_afk(self):
        if not self.bot:
            return
        col    = db.get_collection("matches")
        active = await col.find({
            "status": {"$in": ["aguardando_pagamento", "iniciada"]}
        }).to_list(None)
        now = utcnow()
        for match in active:
            med_id   = match.get("mediator_id")
            match_id = str(match.get("_id"))
            if not med_id:
                continue
            # ← proteção contra substituição dupla
            if self._replacing_match.get(match_id):
                continue
            last = self._match_activity.get(
                int(med_id), match.get("created_at", now))
            if isinstance(last, datetime) and (now - last) >= AFK_TIMEOUT:
                self._replacing_match[match_id] = True
                asyncio.create_task(
                    self._replace_afk_mediator(match, int(med_id)))

    @check_match_afk.before_loop
    async def before_check_match_afk(self):
        if self.bot:
            await self.bot.wait_until_ready()

    async def _replace_afk_mediator(self, match: dict, med_id: int):
        match_id   = str(match.get("_id"))
        thread_id  = match.get("thread_id")
        player_ids = match.get("player_ids", [])

        try:
            from services.mediator_queue import mediator_queue
            new_med_id = await mediator_queue.get_next_mediator()
            if not new_med_id or new_med_id == med_id:
                logger.warning(
                    f"[AFK] Sem mediador disponível para substituir em {match_id}")
                return

            # ← usa _id (ObjectId) como filtro — garante encontrar o documento
            col = db.get_collection("matches")
            await col.update_one(
                {"_id": match["_id"]},
                {"$set": {"mediator_id": str(new_med_id), "updated_at": utcnow()}}
            )
            self.remove_mediator(med_id)

            # Avisa na thread
            if thread_id:
                for guild in self.bot.guilds:
                    thread = guild.get_thread(int(thread_id))
                    if thread:
                        await thread.send(embed=discord.Embed(
                            description=(
                                "O mediador ficou inativo. "
                                "Um novo mediador assumiu a partida."
                            ),
                            color=THEME_COLOR
                        ))
                        break

            # Avisa jogadores por DM
            for pid in player_ids:
                try:
                    user = await self.bot.fetch_user(int(pid))
                    await user.send(embed=discord.Embed(
                        description=(
                            f"O mediador da partida `{match_id}` ficou inativo "
                            "e foi substituído.\n"
                            "Um novo mediador foi designado. "
                            "Aguarde as instruções na thread."
                        ),
                        color=THEME_COLOR
                    ))
                except Exception:
                    pass

            # Avisa mediador afastado
            try:
                old_user = await self.bot.fetch_user(med_id)
                await old_user.send(embed=discord.Embed(
                    description=(
                        f"Você foi removido da partida `{match_id}` por inatividade."
                    ),
                    color=0xE74C3C
                ))
            except Exception:
                pass

            await self._log_afk(med_id, f"Substituído na partida `{match_id}`.")
            logger.info(
                f"[AFK] Mediador {med_id} substituído em {match_id} por {new_med_id}")

        except Exception as e:
            logger.error(f"[AFK] Erro ao substituir mediador em {match_id}: {e}",
                         exc_info=True)
        finally:
            # Limpa flag independente de sucesso ou erro
            self._replacing_match.pop(match_id, None)

    # ─────────────────────────────────────────
    # Log no #logs-mediadores
    # ─────────────────────────────────────────

    async def _log_afk(self, uid: int, msg: str):
        if not self.bot:
            return
        for guild in self.bot.guilds:
            ch = discord.utils.get(guild.text_channels, name="logs-mediadores")
            if ch:
                embed = discord.Embed(
                    description=f"<@{uid}> — {msg}",
                    color=0xE74C3C
                )
                embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
                try:
                    await ch.send(embed=embed)
                except Exception:
                    pass


# ─────────────────────────────────────────
# View de confirmação de presença (DM)
# ─────────────────────────────────────────

class _AFK_ConfirmView(discord.ui.View):

    def __init__(self, uid: int, svc: AFKService):
        super().__init__(timeout=130)
        self.uid = uid
        self.svc = svc

    @discord.ui.button(
        label="Confirmar Presença",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.uid:
            await interaction.response.send_message(
                "Esta confirmação não é sua.", ephemeral=True)
            return
        task = self.svc._pending_confirm.pop(self.uid, None)
        if task and not task.done():
            task.cancel()
        self.svc.mark_queue_activity(self.uid)
        await interaction.response.edit_message(
            embed=discord.Embed(
                description="Presença confirmada! Você permanece na fila.",
                color=0x27AE60),
            view=None
        )


afk_service = AFKService()
