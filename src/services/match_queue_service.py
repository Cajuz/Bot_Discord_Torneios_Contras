import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import discord
from config.database import db
from models.queue import MatchQueue
from services.mediator_queue import mediator_queue
from services.match_service import match_service
from utils.logger import logger


class MatchQueueService:

    def __init__(self):
        self.active_queues: Dict[str, MatchQueue] = {}
        self.queue_cards: Dict[str, int] = {}

    def get_queue_key(self, channel_name: str, bet_value: float, gel_type: str) -> str:
        return f"{channel_name}_{bet_value}_{gel_type}"

    async def get_or_create_queue(
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str,
        max_players: int
    ) -> MatchQueue:
        queue_key = self.get_queue_key(channel_name, bet_value, gel_type)

        if queue_key in self.active_queues:
            return self.active_queues[queue_key]

        collection = db.get_collection('match_queues')
        queue_data = await collection.find_one({
            "channel_name": channel_name,
            "bet_value": bet_value,
            "gel_type": gel_type,
            "status": "waiting"
        })

        if queue_data:
            queue = MatchQueue.from_dict(queue_data)
        else:
            queue = MatchQueue(
                channel_name=channel_name,
                bet_value=bet_value,
                gel_type=gel_type,
                max_players=max_players
            )
            await collection.insert_one(queue.to_dict())

        self.active_queues[queue_key] = queue
        return queue

    async def add_player_to_queue(
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str,
        max_players: int,
        player_id: int
    ) -> tuple[bool, MatchQueue, str]:
        queue = await self.get_or_create_queue(channel_name, bet_value, gel_type, max_players)

        if player_id in queue.players:
            return False, queue, "Você já está nesta fila!"

        if queue.add_player(player_id):
            await self._save_queue(queue)

            if queue.is_full():
                return True, queue, "full"

            return True, queue, f"Você entrou na fila! ({len(queue.players)}/{queue.max_players})"

        return False, queue, "Fila cheia!"

    async def remove_player_from_queue(
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str,
        player_id: int
    ) -> tuple[bool, Optional[MatchQueue]]:
        queue_key = self.get_queue_key(channel_name, bet_value, gel_type)

        if queue_key not in self.active_queues:
            return False, None

        queue = self.active_queues[queue_key]

        if queue.remove_player(player_id):
            await self._save_queue(queue)
            return True, queue

        return False, None

    async def start_confirmation_timer(
        self,
        queue: MatchQueue,
        bot: discord.Client,
        channel: discord.TextChannel
    ):
        queue.status = "confirming"
        queue.expires_at = datetime.utcnow() + timedelta(minutes=1)
        await self._save_queue(queue)

        embed = discord.Embed(
            title="⏰ PARTIDA ENCONTRADA!",
            description=f"**R$ {queue.bet_value:.2f}** - {queue.channel_name.upper()} - {queue.gel_type.upper()}",
            color=discord.Color.orange()
        )

        players_text = "\n".join([
            f"• <@{player_id}> ⏳" for player_id in queue.players
        ])

        embed.add_field(name="Jogadores", value=players_text, inline=False)
        embed.add_field(name="⏰ Confirme em 60 segundos!", value="Clique em ✅ para aceitar", inline=False)

        view = ConfirmationView(queue, self, bot)

        mentions = " ".join([f"<@{player_id}>" for player_id in queue.players])
        message = await channel.send(content=mentions, embed=embed, view=view)

        queue.confirmation_message_id = message.id
        await self._save_queue(queue)

        asyncio.create_task(self._confirmation_countdown(queue, bot, channel, message, view))

    async def _confirmation_countdown(
        self,
        queue: MatchQueue,
        bot: discord.Client,
        channel: discord.TextChannel,
        message: discord.Message,
        view: discord.ui.View
    ):
        for remaining in range(60, 0, -5):
            await asyncio.sleep(5)

            collection = db.get_collection('match_queues')
            queue_data = await collection.find_one({"_id": queue._id})
            if not queue_data:
                return

            queue = MatchQueue.from_dict(queue_data)

            if queue.all_confirmed():
                await self._create_match_from_queue(queue, bot, channel)
                return

            embed = message.embeds[0]

            players_text = "\n".join([
                f"• <@{player_id}> {'✅' if player_id in queue.confirmations else '⏳'}"
                for player_id in queue.players
            ])

            embed.set_field_at(0, name="Jogadores", value=players_text, inline=False)
            embed.set_field_at(
                1,
                name=f"⏰ Tempo restante: {remaining}s",
                value="Clique em ✅ para aceitar",
                inline=False
            )

            try:
                await message.edit(embed=embed, view=view)
            except Exception:
                pass

        await self._expire_queue(queue, bot, channel, message)

    async def add_confirmation(
        self,
        queue: MatchQueue,
        player_id: int,
        bot: discord.Client,
        channel: discord.TextChannel
    ) -> bool:
        if queue.add_confirmation(player_id):
            await self._save_queue(queue)

            if queue.all_confirmed():
                await self._create_match_from_queue(queue, bot, channel)

            return True

        return False

    async def _create_match_from_queue(
        self,
        queue: MatchQueue,
        bot: discord.Client,
        channel: discord.TextChannel
    ):
        try:
            from views.match_thread_view import MediatorMatchControlView

            mediator_id = await mediator_queue.get_next_mediator()

            if not mediator_id:
                await channel.send("❌ Não há mediadores disponíveis no momento.")
                await self._expire_queue(queue, bot, channel, None)
                return

            guild = channel.guild

            players   = list(queue.players)
            mid       = len(players) // 2
            time_blue = players[:mid]
            time_red  = players[mid:]

            match_data = await match_service.create_match(
                guild_id=guild.id,
                channel_id=channel.id,
                player_ids=players,
                mediator_id=mediator_id,
                bet_value=queue.bet_value,
                gel_type=queue.gel_type,
                match_type=queue.channel_name
            )

            # ✅ FIX 1: converte ObjectId para str
            match_id = str(match_data.get("_id"))

            from bson import ObjectId
            await db.get_collection("matches").update_one(
                {"_id": ObjectId(match_id)},
                {
                    "$set": {
                        "status": "aguardando_pagamento",
                        "time_blue": time_blue,
                        "time_red": time_red,
                        "thread_id": None,
                        "pagamento_confirmado": False,
                        "premio_entregue_mediador": False,
                        "premio_confirmado_jogador": False,
                        "vencedor": None,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            # ✅ FIX 2: thread_name com divisão correta
            thread_name = (
                f"⚔️ R${queue.bet_value:.2f} "
                f"{queue.gel_type.capitalize()} "
                f"({len(time_blue)}v{len(time_red)})"
            )

            thread = await channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.public_thread,
                auto_archive_duration=60
            )

            await db.get_collection("matches").update_one(
                {"_id": ObjectId(match_id)},
                {"$set": {"thread_id": thread.id}}
            )

            mediator_member = guild.get_member(mediator_id)
            all_members = players + ([mediator_id] if mediator_id not in players else [])
            for uid in all_members:
                member = guild.get_member(uid)
                if member:
                    try:
                        await thread.add_user(member)
                    except Exception:
                        pass

            for uid in time_blue:
                m = guild.get_member(uid)
                if m:
                    try:
                        await m.send(
                            f"🔵 Você está no **Time Blue** no match `{thread_name}`!\n"
                            f"Acesse: {thread.mention}"
                        )
                    except discord.Forbidden:
                        pass

            for uid in time_red:
                m = guild.get_member(uid)
                if m:
                    try:
                        await m.send(
                            f"🔴 Você está no **Time Red** no match `{thread_name}`!\n"
                            f"Acesse: {thread.mention}"
                        )
                    except discord.Forbidden:
                        pass

            blue_str = "\n".join(f"• <@{uid}>" for uid in time_blue) or "—"
            red_str  = "\n".join(f"• <@{uid}>" for uid in time_red)  or "—"

            embed = discord.Embed(
                title="⚔️ Match Criado!",
                description=(
                    f"**Modo:** {queue.channel_name}\n"
                    f"**Valor:** R$ {queue.bet_value:.2f}\n"
                    f"**GEL:** {queue.gel_type.capitalize()}\n\n"
                    f"🕵️ **Mediador:** "
                    f"{mediator_member.mention if mediator_member else f'<@{mediator_id}>'}"
                ),
                color=discord.Color.gold()
            )
            embed.add_field(name="🔵 Time Blue", value=blue_str, inline=True)
            embed.add_field(name="🔴 Time Red",  value=red_str,  inline=True)
            embed.set_footer(text="Aguardando confirmação de pagamento pelo mediador.")

            mentions = " ".join(f"<@{uid}>" for uid in players)
            if mediator_member:
                mentions += f" {mediator_member.mention}"

            view = MediatorMatchControlView(match_id, mediator_id)
            await thread.send(content=mentions, embed=embed, view=view)

            await self._delete_queue(queue)

            if queue.confirmation_message_id:
                try:
                    msg = await channel.fetch_message(queue.confirmation_message_id)
                    await msg.delete()
                except Exception:
                    pass

            logger.info(
                f"Match criado: {thread_name} | "
                f"{len(players)} jogadores | "
                f"Mediador: {mediator_id}"
            )

        except Exception as e:
            logger.error(f"Erro ao criar partida da fila: {e}", exc_info=True)
            await channel.send(f"❌ Erro ao criar partida: {e}")

    async def _expire_queue(
        self,
        queue: MatchQueue,
        bot: discord.Client,
        channel: discord.TextChannel,
        message: Optional[discord.Message]
    ):
        queue.status = "expired"
        await self._save_queue(queue)

        not_confirmed = [p for p in queue.players if p not in queue.confirmations]

        embed = discord.Embed(
            title="❌ Tempo Esgotado",
            description="A partida foi cancelada porque nem todos confirmaram.",
            color=discord.Color.red()
        )

        if not_confirmed:
            not_confirmed_text = "\n".join([f"• <@{player_id}>" for player_id in not_confirmed])
            embed.add_field(name="Não confirmaram", value=not_confirmed_text, inline=False)

        if message:
            await message.edit(embed=embed, view=None)
        else:
            await channel.send(embed=embed)

        await self._delete_queue(queue)

    async def get_queue_status(
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str
    ) -> Optional[MatchQueue]:
        queue_key = self.get_queue_key(channel_name, bet_value, gel_type)
        return self.active_queues.get(queue_key)

    async def _save_queue(self, queue: MatchQueue):
        collection = db.get_collection('match_queues')
        await collection.replace_one(
            {"_id": queue._id},
            queue.to_dict(),
            upsert=True
        )

    async def _delete_queue(self, queue: MatchQueue):
        collection = db.get_collection('match_queues')
        await collection.delete_one({"_id": queue._id})

        queue_key = self.get_queue_key(queue.channel_name, queue.bet_value, queue.gel_type)
        if queue_key in self.active_queues:
            del self.active_queues[queue_key]


# ──────────────────────────────────────────────
# ✅ FIX 3: ConfirmationView com botões dinâmicos
# ──────────────────────────────────────────────

class ConfirmationView(discord.ui.View):

    def __init__(self, queue: MatchQueue, service: MatchQueueService, bot: discord.Client):
        super().__init__(timeout=None)
        self.queue   = queue
        self.service = service
        self.bot     = bot

        confirm_btn = discord.ui.Button(label="✅ ACEITAR", style=discord.ButtonStyle.green)
        confirm_btn.callback = self._confirm_callback
        self.add_item(confirm_btn)

        decline_btn = discord.ui.Button(label="❌ RECUSAR", style=discord.ButtonStyle.red)
        decline_btn.callback = self._decline_callback
        self.add_item(decline_btn)

    async def _confirm_callback(self, interaction: discord.Interaction):
        if interaction.user.id not in self.queue.players:
            await interaction.response.send_message("❌ Você não está nesta partida!", ephemeral=True)
            return

        if interaction.user.id in self.queue.confirmations:
            await interaction.response.send_message("✅ Você já confirmou!", ephemeral=True)
            return

        await self.service.add_confirmation(
            self.queue,
            interaction.user.id,
            self.bot,
            interaction.channel
        )
        await interaction.response.send_message("✅ Confirmado!", ephemeral=True)

    async def _decline_callback(self, interaction: discord.Interaction):
        if interaction.user.id not in self.queue.players:
            await interaction.response.send_message("❌ Você não está nesta partida!", ephemeral=True)
            return

        await self.service.remove_player_from_queue(
            self.queue.channel_name,
            self.queue.bet_value,
            self.queue.gel_type,
            interaction.user.id
        )
        await interaction.response.send_message("❌ Você saiu da fila.", ephemeral=True)
        await self.service._expire_queue(self.queue, self.bot, interaction.channel, None)


# Instância global
match_queue_service = MatchQueueService()
