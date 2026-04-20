"""
match_queue_service.py — Fila de partidas.
"""
from __future__ import annotations
import asyncio
from datetime import timedelta
from typing import Optional, Dict
from discord import Interaction
import discord
from config.database import db
from models.queue import MatchQueue
from models.match import Match
from services.mediator_queue import mediator_queue
from services.match_service import match_service
from utils.datetime_utils import utcnow
from utils.logger import logger


THEME_COLOR  = 0xFFD54F
THEME_COLOR2 = 0xFFA726


def _thread_name_confirmar(queue: MatchQueue) -> str:
    return f"confirmar-{queue.channel_name}_{queue.bet_value:.0f}_reais"[:100]


def _thread_name_pagamento(queue: MatchQueue) -> str:
    return f"pagamento-{queue.channel_name}_{queue.bet_value:.0f}_reais"[:100]


def _thread_name_pagar(queue: MatchQueue) -> str:
    return f"pagar-{queue.bet_value:.0f}_reais"[:100]


class MatchQueueService:

    def __init__(self):
        self.active_queues:         Dict[str, MatchQueue]   = {}
        self._queue_locks:          Dict[str, asyncio.Lock] = {}
        self._match_creation_locks: Dict[str, asyncio.Lock] = {}
        self._cancelled_queues:     set[str]                = set()

    def get_queue_key(self, channel_name: str, bet_value: float, gel_type: str) -> str:
        return f"{channel_name}_{bet_value}_{gel_type}"

    def _get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._queue_locks:
            self._queue_locks[key] = asyncio.Lock()
        return self._queue_locks[key]

    def _get_match_lock(self, queue_id: str) -> asyncio.Lock:
        if queue_id not in self._match_creation_locks:
            self._match_creation_locks[queue_id] = asyncio.Lock()
        return self._match_creation_locks[queue_id]

    def _cancel_countdown(self, queue_id: str):
        self._cancelled_queues.add(str(queue_id))

    def _is_countdown_cancelled(self, queue_id: str) -> bool:
        return str(queue_id) in self._cancelled_queues

    def _clear_cancelled(self, queue_id: str):
        self._cancelled_queues.discard(str(queue_id))

    async def _get_or_create_queue_unsafe(
        self, channel_name: str, bet_value: float, gel_type: str, max_players: int
    ) -> MatchQueue:
        collection = db.get_collection("match_queues")
        queue_data = await collection.find_one({
            "channel_name": channel_name, "bet_value": bet_value,
            "gel_type": gel_type, "status": MatchQueue.STATUS_WAITING
        })
        if queue_data:
            queue = MatchQueue.from_dict(queue_data)
        else:
            queue = MatchQueue(
                channel_name=channel_name, bet_value=bet_value,
                gel_type=gel_type, max_players=max_players
            )
            await collection.insert_one(queue.to_dict())
        queue_key = self.get_queue_key(channel_name, bet_value, gel_type)
        self.active_queues[queue_key] = queue
        return queue

    async def get_or_create_queue(
        self, channel_name: str, bet_value: float, gel_type: str, max_players: int
    ) -> MatchQueue:
        queue_key = self.get_queue_key(channel_name, bet_value, gel_type)
        async with self._get_lock(queue_key):
            return await self._get_or_create_queue_unsafe(
                channel_name, bet_value, gel_type, max_players)

    async def add_player_to_queue(
        self, channel_name: str, bet_value: float, gel_type: str,
        max_players: int, player_id: int
    ) -> tuple[bool, MatchQueue, str]:
        queue_key = self.get_queue_key(channel_name, bet_value, gel_type)
        async with self._get_lock(queue_key):
            queue = await self._get_or_create_queue_unsafe(
                channel_name, bet_value, gel_type, max_players)
            if player_id in queue.players:
                return False, queue, "Você já está nesta fila!"
            if queue.add_player(player_id):
                await self._save_queue(queue)
                self.active_queues[queue_key] = queue
                if queue.is_full():
                    return True, queue, "full"
                return True, queue, f"Você entrou na fila! ({len(queue.players)}/{queue.max_players})"
            return False, queue, "Fila cheia!"

    async def remove_player_from_queue(
        self, channel_name: str, bet_value: float, gel_type: str, player_id: int
    ) -> tuple[bool, Optional[MatchQueue]]:
        queue_key = self.get_queue_key(channel_name, bet_value, gel_type)
        async with self._get_lock(queue_key):
            collection = db.get_collection("match_queues")
            queue_data = await collection.find_one({
                "channel_name": channel_name, "bet_value": bet_value, "gel_type": gel_type,
                "status": {"$in": [MatchQueue.STATUS_WAITING, MatchQueue.STATUS_CONFIRMING]}
            })
            if not queue_data:
                return False, None
            queue = MatchQueue.from_dict(queue_data)
            if queue.remove_player(player_id):
                await self._save_queue(queue)
                self.active_queues[queue_key] = queue
                return True, queue
            return False, None

    async def _set_card_locked(self, channel, bet_value, gel_type, locked):
        try:
            from views.match_queue_view import create_match_queue_embed, MatchQueueView
            q_n = await self.get_queue_status(channel.name, bet_value, "normal")
            q_i = await self.get_queue_status(channel.name, bet_value, "infinito")
            nc  = len(q_n.players) if q_n else 0
            ic  = len(q_i.players) if q_i else 0
            locked_gel = gel_type if locked else None
            embed = create_match_queue_embed(channel.name, bet_value, nc, ic, locked_gel)
            view  = MatchQueueView(
                channel_name=channel.name,
                bet_value=bet_value,
                locked_gel=locked_gel,
                guild=channel.guild,
            )
            async for msg in channel.history(limit=50):
                if msg.author == channel.guild.me and msg.embeds:
                    if f"{bet_value:.2f}" in (msg.embeds[0].title or ""):
                        await msg.edit(embed=embed, view=view)
                        break
        except Exception as e:
            logger.warning(f"[Queue] Erro ao atualizar lock do card: {e}")

    async def start_confirmation_timer(
        self, queue: MatchQueue, bot: discord.Client, channel: discord.TextChannel
    ):
        try:
            from services.thread_reuse_service import thread_reuse_service
            queue.status     = MatchQueue.STATUS_CONFIRMING
            queue.expires_at = utcnow() + timedelta(seconds=300)
            await self._save_queue(queue)
            await self._set_card_locked(channel, queue.bet_value, queue.gel_type, locked=True)

            guild   = channel.guild
            players = list(queue.players)
            time_blue = [players[0]]
            time_red  = [players[1]]

            thread_name    = _thread_name_confirmar(queue)
            confirm_thread = await thread_reuse_service.get_or_create_thread(
                channel=channel, thread_name=thread_name,
                player_ids=players, guild=guild,
            )
            if not confirm_thread:
                logger.error(f"[Queue] Não foi possível obter thread para #{channel.name}")
                queue.status = MatchQueue.STATUS_WAITING
                await self._save_queue(queue)
                await self._set_card_locked(channel, queue.bet_value, queue.gel_type, locked=False)
                return

            await self._purge_thread_messages(confirm_thread)

            queue.thread_id = confirm_thread.id
            queue.guild_id  = guild.id
            await self._save_queue(queue)

            queue_id = str(queue._id)
            self._clear_cancelled(queue_id)

            embed   = self._build_confirmation_embed(queue, time_blue, time_red, remaining=300)
            view    = ConfirmationView(queue_id=queue_id, service=self, bot=bot,
                                       time_blue=time_blue, time_red=time_red)
            mentions = " ".join(f"<@{uid}>" for uid in players)
            message  = await confirm_thread.send(content=mentions, embed=embed, view=view)

            view.conf_msg                 = message
            queue.confirmation_message_id = message.id
            await self._save_queue(queue)

            asyncio.create_task(
                self._confirmation_countdown(
                    queue, bot, channel, confirm_thread, message, view, time_blue, time_red
                )
            )
        except Exception as e:
            logger.error(f"[Queue] Erro ao iniciar confirmação: {e}", exc_info=True)

    async def _purge_thread_messages(self, thread: discord.Thread):
        try:
            to_delete = [msg async for msg in thread.history(limit=200)]
            if len(to_delete) >= 2:
                await thread.delete_messages(to_delete)
            elif len(to_delete) == 1:
                await to_delete[0].delete()
        except discord.HTTPException as e:
            logger.warning(f"[Queue] Erro ao limpar mensagens da thread {thread.id}: {e}")

    def _build_confirmation_embed(self, queue, time_blue, time_red, remaining):
        blue_str = "\n".join(
            f"{'✅' if uid in queue.confirmations else '⏳'} <@{uid}>" for uid in time_blue
        ) or "—"
        red_str = "\n".join(
            f"{'✅' if uid in queue.confirmations else '⏳'} <@{uid}>" for uid in time_red
        ) or "—"
        confirmed = len(queue.confirmations)
        total     = len(queue.players)
        mins      = remaining // 60
        secs      = remaining % 60
        embed = discord.Embed(
            title="Partida encontrada — Confirme sua presença",
            description=(
                f"**Modo:** `{queue.channel_name.upper()}` | "
                f"**Valor:** R$ {queue.bet_value:.2f} | "
                f"**GEL:** {queue.gel_type.capitalize()}\n\n"
                f"Confirmações: **{confirmed}/{total}** — Tempo: {mins}:{secs:02d}\n"
                f"**Queue-ID:** `{queue._id}`"
            ),
            color=THEME_COLOR2
        )
        embed.add_field(name="Time Blue", value=blue_str, inline=True)
        embed.add_field(name="Time Red",  value=red_str,  inline=True)
        embed.set_footer(text="Todos precisam confirmar para a partida iniciar")
        return embed

    async def _confirmation_countdown(
        self, queue, bot, channel, confirm_thread, message, view, time_blue, time_red
    ):
        total    = 300
        queue_id = str(queue._id)

        for elapsed in range(5, total + 1, 5):
            await asyncio.sleep(5)

            if self._is_countdown_cancelled(queue_id):
                self._clear_cancelled(queue_id)
                return

            match_lock = self._get_match_lock(queue_id)
            if match_lock.locked():
                return

            collection = db.get_collection("match_queues")
            queue_data = await collection.find_one({"_id": queue._id})
            if not queue_data:
                return
            queue = MatchQueue.from_dict(queue_data)
            if queue.status in (MatchQueue.STATUS_MATCHED, MatchQueue.STATUS_EXPIRED):
                return

            if queue.all_confirmed():
                async with self._get_match_lock(queue_id):
                    queue_data = await collection.find_one({"_id": queue._id})
                    if not queue_data or MatchQueue.from_dict(queue_data).status == MatchQueue.STATUS_MATCHED:
                        return
                    await self._create_match_from_queue(
                        queue, bot, channel, confirm_thread, message, time_blue, time_red)
                self._match_creation_locks.pop(queue_id, None)
                return

            remaining = total - elapsed
            embed = self._build_confirmation_embed(queue, time_blue, time_red, remaining)
            try:
                await message.edit(embed=embed, view=view)
            except Exception:
                pass

        if not self._is_countdown_cancelled(queue_id):
            await self._expire_queue(queue, bot, channel, message, confirm_thread)
        self._clear_cancelled(queue_id)

    async def add_confirmation(
        self, queue, player_id, bot, channel, confirm_thread, message, time_blue, time_red
    ) -> bool:
        queue_id   = str(queue._id)
        match_lock = self._get_match_lock(queue_id)

        if queue.add_confirmation(player_id):
            await self._save_queue(queue)
            if queue.all_confirmed() and not match_lock.locked():
                async with match_lock:
                    collection = db.get_collection("match_queues")
                    queue_data = await collection.find_one({"_id": queue._id})
                    if not queue_data or MatchQueue.from_dict(queue_data).status == MatchQueue.STATUS_MATCHED:
                        return True
                    await self._create_match_from_queue(
                        queue, bot, channel, confirm_thread, message, time_blue, time_red)
                self._match_creation_locks.pop(queue_id, None)
            return True
        return False

    async def _create_match_from_queue(
        self, queue, bot, channel, confirm_thread, conf_msg, time_blue, time_red
    ):
        try:
            from views.match_thread_view import embed_match_created
            guild      = channel.guild
            players    = list(queue.players)
            match_type = queue.channel_name.split("-")[0] if "-" in queue.channel_name else queue.channel_name
            platform   = queue.channel_name.split("-")[1] if "-" in queue.channel_name else "mob"

            mediator_id = await mediator_queue.get_next_mediator()
            if not mediator_id:
                await confirm_thread.send("Nenhum mediador disponível. Partida cancelada.")
                await self._expire_queue(queue, bot, channel, None, confirm_thread)
                return

            match_data = await match_service.create_match(
                guild_id=guild.id, channel_id=channel.id, channel_name=queue.channel_name,
                player_ids=players, mediator_id=mediator_id, bet_value=queue.bet_value,
                gel_type=queue.gel_type, match_type=match_type, platform=platform,
            )
            match_id = str(match_data["_id"])
            await match_service._update(match_id, {
                "time_blue": [str(p) for p in time_blue],
                "time_red":  [str(p) for p in time_red],
                "thread_id": confirm_thread.id,
            })

            try:
                from services.thread_reuse_service import thread_reuse_service
                await thread_reuse_service.update_active_thread_match(confirm_thread.id, match_id)
            except Exception as e:
                logger.warning(f"[Queue] Erro ao vincular match ao active_thread: {e}")

            queue.mark_as_matched(match_id)
            await self._save_queue(queue)
            await self._delete_queue(queue)
            await self._set_card_locked(channel, queue.bet_value, queue.gel_type, locked=False)

            match_thread_name = _thread_name_pagamento(queue)
            try:
                await confirm_thread.edit(name=match_thread_name[:100])
            except Exception:
                pass

            mediator_member = guild.get_member(mediator_id)
            blue_str = "\n".join(f"✅ <@{uid}>" for uid in time_blue) or "—"
            red_str  = "\n".join(f"✅ <@{uid}>" for uid in time_red)  or "—"

            confirmed_embed = discord.Embed(
                title="Todos confirmaram!",
                description=(
                    f"**Modo:** `{queue.channel_name.upper()}` | "
                    f"**Valor:** R$ {queue.bet_value:.2f}\n"
                    f"**Mediador:** "
                    f"{mediator_member.mention if mediator_member else f'<@{mediator_id}>'}",
                ),
                color=discord.Color.green()
            )
            confirmed_embed.add_field(name="Time Blue",     value=blue_str,        inline=True)
            confirmed_embed.add_field(name="Time Red",      value=red_str,         inline=True)
            confirmed_embed.add_field(name="ID da Partida", value=f"`{match_id}`", inline=False)
            confirmed_embed.set_footer(text="O mediador confirmará o pagamento para iniciar")
            try:
                await conf_msg.edit(embed=confirmed_embed, view=None)
            except Exception:
                pass

            if mediator_member:
                try:
                    await confirm_thread.add_user(mediator_member)
                except Exception:
                    pass

            match_full = await match_service.get_match(match_id)
            mentions   = " ".join(f"<@{uid}>" for uid in players)
            if mediator_member:
                mentions += f" {mediator_member.mention}"

            await confirm_thread.send(content=mentions, embed=embed_match_created(match_full))
            logger.info(
                f"[Queue] Match criado: {match_thread_name} | "
                f"Jogadores: {players} | Mediador: {mediator_id}"
            )

        except Exception as e:
            logger.error(f"[Queue] Erro ao criar partida da fila: {e}", exc_info=True)
            await confirm_thread.send(f"❌ Erro ao criar partida: {e}")

    async def _expire_queue(self, queue, bot, channel, message, confirm_thread=None):
        self._cancel_countdown(str(queue._id))

        queue.status = MatchQueue.STATUS_EXPIRED
        await self._save_queue(queue)
        not_confirmed = queue.pending_confirmations()
        embed = discord.Embed(
            title="Tempo Esgotado",
            description="A partida foi cancelada porque nem todos confirmaram a tempo.",
            color=discord.Color.red()
        )
        if not_confirmed:
            embed.add_field(
                name="Não confirmaram",
                value="\n".join(f"• <@{uid}>" for uid in not_confirmed),
                inline=False
            )
        if message:
            try:
                await message.edit(embed=embed, view=None)
            except Exception:
                pass
        elif confirm_thread:
            await confirm_thread.send(embed=embed)
        else:
            await channel.send(embed=embed)

        await self._delete_queue(queue)
        await self._set_card_locked(channel, queue.bet_value, queue.gel_type, locked=False)

        if confirm_thread:
            await asyncio.sleep(10)
            try:
                from services.thread_reuse_service import thread_reuse_service
                asyncio.create_task(thread_reuse_service.return_to_pool_empty(confirm_thread))
            except Exception as e:
                logger.warning(f"[Queue] Erro ao devolver thread ao pool: {e}")

    async def get_queue_status(
        self, channel_name, bet_value, gel_type
    ) -> Optional[MatchQueue]:
        collection = db.get_collection("match_queues")
        queue_data = await collection.find_one({
            "channel_name": channel_name, "bet_value": bet_value, "gel_type": gel_type,
            "status": {"$in": [MatchQueue.STATUS_WAITING, MatchQueue.STATUS_CONFIRMING]}
        })
        return MatchQueue.from_dict(queue_data) if queue_data else None

    async def get_all_active_queues(self, guild_id: int = None) -> list:
        collection = db.get_collection("match_queues")
        query = {"status": {"$in": [MatchQueue.STATUS_WAITING, MatchQueue.STATUS_CONFIRMING]}}
        if guild_id:
            query["guild_id"] = guild_id
        docs = await collection.find(query).to_list(length=100)
        return [MatchQueue.from_dict(d) for d in docs]

    async def cancel_match_for_user(self, user_id: str) -> tuple[bool, str]:
        try:
            col   = db.get_collection("matches")
            match = await col.find_one({
                "player_ids": user_id, "status": {"$in": Match.ACTIVE_STATUSES}})
            if not match:
                return False, "Você não está em nenhuma partida ativa."
            result = await match_service.cancel_match(
                str(match["_id"]), cancelled_by=int(user_id), reason="Cancelado pelo jogador")
            return (True, "Sua partida foi cancelada.") if result else (False, "Não foi possível cancelar.")
        except Exception as e:
            logger.error(f"[Queue] Erro ao cancelar partida: {e}")
            return False, "Erro ao cancelar partida."

    async def _save_queue(self, queue: MatchQueue):
        collection = db.get_collection("match_queues")
        await collection.replace_one({"_id": queue._id}, queue.to_dict(), upsert=True)
        queue_key = self.get_queue_key(queue.channel_name, queue.bet_value, queue.gel_type)
        self.active_queues[queue_key] = queue

    async def _delete_queue(self, queue: MatchQueue):
        collection = db.get_collection("match_queues")
        await collection.delete_one({"_id": queue._id})
        queue_key = self.get_queue_key(queue.channel_name, queue.bet_value, queue.gel_type)
        self.active_queues.pop(queue_key, None)
        self._queue_locks.pop(queue_key, None)


class ConfirmationView(discord.ui.View):

    def __init__(
        self,
        queue_id:  str = "__persistent__",
        service:   MatchQueueService = None,
        bot:       discord.Client = None,
        time_blue: list = None,
        time_red:  list = None,
        conf_msg   = None,
    ):
        super().__init__(timeout=None)
        self.queue_id  = queue_id
        self.service   = service or match_queue_service
        self.bot       = bot
        self.time_blue = time_blue or []
        self.time_red  = time_red  or []
        self.conf_msg  = conf_msg

    def _parse_queue_id(self, interaction: discord.Interaction) -> str:
        try:
            embed = interaction.message.embeds[0]
            desc  = embed.description or ""
            for line in desc.split("\n"):
                if "Queue-ID:" in line:
                    return line.split("`")[1].strip()
        except Exception:
            pass
        if self.queue_id != "__persistent__":
            return self.queue_id
        return ""

    def _parse_teams(self, interaction: discord.Interaction) -> tuple[list, list]:
        if self.time_blue and self.time_red:
            return self.time_blue, self.time_red
        try:
            embed = interaction.message.embeds[0]
            blue_field = next((f for f in embed.fields if "Blue" in f.name), None)
            red_field  = next((f for f in embed.fields if "Red"  in f.name), None)
            import re
            def extract_ids(field_value: str) -> list:
                return [int(m) for m in re.findall(r"<@(\d+)>", field_value or "")]
            time_blue = extract_ids(blue_field.value) if blue_field else []
            time_red  = extract_ids(red_field.value)  if red_field  else []
            return time_blue, time_red
        except Exception:
            return [], []

    @discord.ui.button(
        label="Confirmar", style=discord.ButtonStyle.green,
        custom_id="confirm_match_btn", emoji="✔"
    )
    async def btn_confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bson import ObjectId
        queue_id = self._parse_queue_id(interaction)
        if not queue_id:
            await interaction.response.send_message("Esta fila não existe mais.", ephemeral=True)
            return

        collection = db.get_collection("match_queues")
        try:
            queue_data = await collection.find_one({"_id": ObjectId(queue_id)})
        except Exception:
            queue_data = None

        if not queue_data:
            await interaction.response.send_message("Esta fila não existe mais.", ephemeral=True)
            return

        queue = MatchQueue.from_dict(queue_data)

        if interaction.user.id not in queue.players:
            await interaction.response.send_message(
                "Você não está nesta partida.", ephemeral=True)
            return
        if interaction.user.id in queue.confirmations:
            await interaction.response.send_message("Você já confirmou.", ephemeral=True)
            return
        if queue.status == MatchQueue.STATUS_MATCHED:
            await interaction.response.send_message("Partida já criada!", ephemeral=True)
            return
        if queue.status == MatchQueue.STATUS_EXPIRED:
            await interaction.response.send_message("Esta fila expirou.", ephemeral=True)
            return

        parent_channel = (
            interaction.channel.parent
            if hasattr(interaction.channel, "parent")
            else interaction.channel
        )

        time_blue, time_red = self._parse_teams(interaction)

        await self.service.add_confirmation(
            queue=queue, player_id=interaction.user.id, bot=self.bot or interaction.client,
            channel=parent_channel, confirm_thread=interaction.channel,
            message=self.conf_msg or interaction.message,
            time_blue=time_blue, time_red=time_red,
        )
        await interaction.response.send_message("✅ Confirmado!", ephemeral=True)

    @discord.ui.button(
        label="Recusar", style=discord.ButtonStyle.red,
        custom_id="decline_match_btn", emoji="✖"
    )
    async def btn_recusar(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bson import ObjectId
        queue_id = self._parse_queue_id(interaction)
        if not queue_id:
            await interaction.response.send_message("Esta fila não existe mais.", ephemeral=True)
            return

        collection = db.get_collection("match_queues")
        try:
            queue_data = await collection.find_one({"_id": ObjectId(queue_id)})
        except Exception:
            queue_data = None

        if not queue_data:
            await interaction.response.send_message("Esta fila não existe mais.", ephemeral=True)
            return

        queue = MatchQueue.from_dict(queue_data)

        if interaction.user.id not in queue.players:
            await interaction.response.send_message(
                "Você não está nesta partida.", ephemeral=True)
            return

        if queue.status in (MatchQueue.STATUS_MATCHED, MatchQueue.STATUS_EXPIRED):
            await interaction.response.send_message(
                "Esta fila já foi encerrada.", ephemeral=True)
            return

        parent_channel = (
            interaction.channel.parent
            if hasattr(interaction.channel, "parent")
            else interaction.channel
        )

        await interaction.response.send_message("Você recusou a partida.", ephemeral=True)
        self.service._cancel_countdown(queue_id)
        await self.service.remove_player_from_queue(
            queue.channel_name, queue.bet_value, queue.gel_type, interaction.user.id)
        await self.service._expire_queue(
            queue, self.bot or interaction.client, parent_channel,
            self.conf_msg or interaction.message, interaction.channel)


match_queue_service = MatchQueueService()