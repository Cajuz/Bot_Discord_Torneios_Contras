import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import discord
from config.database import db
from models.queue import MatchQueue
from models.match import Match
from services.mediator_queue import mediator_queue
from services.match_service import match_service
from utils.logger import logger


class MatchQueueService:

    def __init__(self):
        # cache apenas para consulta rápida de contagem — banco é fonte da verdade
        self.active_queues: Dict[str, MatchQueue] = {}
        # lock por chave para evitar criação duplicada de fila
        self._queue_locks: Dict[str, asyncio.Lock] = {}
        # lock por queue_id para evitar double-trigger de _create_match_from_queue
        self._match_creation_locks: Dict[str, bool] = {}

    # ─────────────────────────────────────────────
    # Helpers de chave e fila
    # ─────────────────────────────────────────────

    def get_queue_key(self, channel_name: str, bet_value: float, gel_type: str) -> str:
        return f"{channel_name}_{bet_value}_{gel_type}"

    def _get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._queue_locks:
            self._queue_locks[key] = asyncio.Lock()
        return self._queue_locks[key]

    async def get_or_create_queue(
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str,
        max_players: int
    ) -> MatchQueue:
        queue_key = self.get_queue_key(channel_name, bet_value, gel_type)

        async with self._get_lock(queue_key):
            # Sempre lê do banco (fonte da verdade)
            collection = db.get_collection('match_queues')
            queue_data = await collection.find_one({
                "channel_name": channel_name,
                "bet_value":    bet_value,
                "gel_type":     gel_type,
                "status":       MatchQueue.STATUS_WAITING
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

    # ─────────────────────────────────────────────
    # Entrar / Sair da fila
    # ─────────────────────────────────────────────

    async def add_player_to_queue(
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str,
        max_players: int,
        player_id: int
    ) -> tuple[bool, MatchQueue, str]:
        queue_key = self.get_queue_key(channel_name, bet_value, gel_type)

        async with self._get_lock(queue_key):
            queue = await self.get_or_create_queue(channel_name, bet_value, gel_type, max_players)

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
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str,
        player_id: int
    ) -> tuple[bool, Optional[MatchQueue]]:
        queue_key = self.get_queue_key(channel_name, bet_value, gel_type)

        async with self._get_lock(queue_key):
            # Relê do banco para garantir estado atual
            collection = db.get_collection('match_queues')
            queue_data = await collection.find_one({
                "channel_name": channel_name,
                "bet_value":    bet_value,
                "gel_type":     gel_type,
                "status":       {"$in": [MatchQueue.STATUS_WAITING, MatchQueue.STATUS_CONFIRMING]}
            })
            if not queue_data:
                return False, None

            queue = MatchQueue.from_dict(queue_data)
            if queue.remove_player(player_id):
                await self._save_queue(queue)
                self.active_queues[queue_key] = queue
                return True, queue

            return False, None

    # ─────────────────────────────────────────────
    # Fila cheia → cria tópico e inicia confirmação
    # ─────────────────────────────────────────────

    async def start_confirmation_timer(
        self,
        queue: MatchQueue,
        bot: discord.Client,
        channel: discord.TextChannel
    ):
        try:
            queue.status     = MatchQueue.STATUS_CONFIRMING
            queue.expires_at = datetime.utcnow() + timedelta(seconds=300)
            await self._save_queue(queue)

            guild     = channel.guild
            players   = list(queue.players)
            time_blue = [players[0]]
            time_red  = [players[1]]

            # Cria tópico de confirmação
            thread_name = (
                f"🟡 Confirmando — R${queue.bet_value:.2f} "
                f"{queue.gel_type.capitalize()} "
                f"{queue.channel_name.upper()}"
            )
            confirm_thread = await channel.create_thread(
                name=thread_name[:100],
                type=discord.ChannelType.public_thread,
                auto_archive_duration=60
            )

            for uid in players:
                member = guild.get_member(uid)
                if member:
                    try:
                        await confirm_thread.add_user(member)
                    except Exception:
                        pass

            queue.thread_id = confirm_thread.id
            queue.guild_id  = guild.id
            await self._save_queue(queue)

            embed    = self._build_confirmation_embed(queue, time_blue, time_red, remaining=300)
            view     = ConfirmationView(queue, self, bot)
            mentions = " ".join(f"<@{uid}>" for uid in players)
            message  = await confirm_thread.send(content=mentions, embed=embed, view=view)

            queue.confirmation_message_id = message.id
            await self._save_queue(queue)

            asyncio.create_task(
                self._confirmation_countdown(
                    queue, bot, channel, confirm_thread, message, view, time_blue, time_red
                )
            )

        except Exception as e:
            logger.error(f"Erro ao iniciar confirmação: {e}", exc_info=True)

    # ─────────────────────────────────────────────
    # Embed de confirmação
    # ─────────────────────────────────────────────

    def _build_confirmation_embed(
        self,
        queue: MatchQueue,
        time_blue: List[int],
        time_red: List[int],
        remaining: int
    ) -> discord.Embed:
        blue_str = "\n".join(
            f"{'✅' if uid in queue.confirmations else '⏳'} <@{uid}>"
            for uid in time_blue
        ) or "—"
        red_str = "\n".join(
            f"{'✅' if uid in queue.confirmations else '⏳'} <@{uid}>"
            for uid in time_red
        ) or "—"

        confirmed = len(queue.confirmations)
        total     = len(queue.players)
        mins      = remaining // 60
        secs      = remaining % 60

        embed = discord.Embed(
            title="⚡ PARTIDA ENCONTRADA — Confirme sua presença!",
            description=(
                f"**Modo:** `{queue.channel_name.upper()}` | "
                f"**Valor:** R$ {queue.bet_value:.2f} | "
                f"**GEL:** {queue.gel_type.capitalize()}\n\n"
                f"📊 **Status:** 🟡 Confirmando ({confirmed}/{total})\n"
                f"⏰ **Tempo restante:** {mins}:{secs:02d}"
            ),
            color=discord.Color.orange()
        )
        embed.add_field(name="🔵 Time Blue", value=blue_str, inline=True)
        embed.add_field(name="🔴 Time Red",  value=red_str,  inline=True)
        embed.add_field(
            name="Como confirmar",
            value=(
                "• Clique em **✅ CONFIRMAR** para aceitar\n"
                "• Clique em **❌ RECUSAR** para sair — a partida será cancelada"
            ),
            inline=False
        )
        embed.set_footer(text="Todos precisam confirmar para a partida iniciar")
        return embed

    # ─────────────────────────────────────────────
    # Countdown de 5 minutos
    # ─────────────────────────────────────────────

    async def _confirmation_countdown(
        self,
        queue: MatchQueue,
        bot: discord.Client,
        channel: discord.TextChannel,
        confirm_thread: discord.Thread,
        message: discord.Message,
        view: discord.ui.View,
        time_blue: List[int],
        time_red: List[int]
    ):
        total    = 300
        queue_id = str(queue._id)

        for elapsed in range(5, total + 1, 5):
            await asyncio.sleep(5)

            # Se já foi processado por add_confirmation, para o countdown
            if self._match_creation_locks.get(queue_id):
                return

            collection = db.get_collection('match_queues')
            queue_data = await collection.find_one({"_id": queue._id})
            if not queue_data:
                return  # fila deletada — match já criado ou expirado

            queue = MatchQueue.from_dict(queue_data)

            # Checa se já foi marcado como matched (criado pelo add_confirmation)
            if queue.status == MatchQueue.STATUS_MATCHED:
                return

            if queue.all_confirmed():
                # Trava para evitar double-trigger
                if self._match_creation_locks.get(queue_id):
                    return
                self._match_creation_locks[queue_id] = True
                await self._create_match_from_queue(
                    queue, bot, channel, confirm_thread, message, time_blue, time_red
                )
                self._match_creation_locks.pop(queue_id, None)
                return

            remaining = total - elapsed
            embed = self._build_confirmation_embed(queue, time_blue, time_red, remaining)
            try:
                await message.edit(embed=embed, view=view)
            except Exception:
                pass

        # Tempo esgotado
        await self._expire_queue(queue, bot, channel, message, confirm_thread)

    # ─────────────────────────────────────────────
    # Confirmação individual
    # ─────────────────────────────────────────────

    async def add_confirmation(
        self,
        queue: MatchQueue,
        player_id: int,
        bot: discord.Client,
        channel: discord.TextChannel,
        confirm_thread: discord.Thread,
        message: discord.Message,
        time_blue: List[int],
        time_red: List[int],
    ) -> bool:
        queue_id = str(queue._id)

        if queue.add_confirmation(player_id):
            await self._save_queue(queue)

            # Dispara imediatamente se todos confirmaram
            if queue.all_confirmed() and not self._match_creation_locks.get(queue_id):
                self._match_creation_locks[queue_id] = True
                await self._create_match_from_queue(
                    queue, bot, channel, confirm_thread, message, time_blue, time_red
                )
                self._match_creation_locks.pop(queue_id, None)
            return True
        return False

    # ─────────────────────────────────────────────
    # Todos confirmaram → transforma em partida
    # ─────────────────────────────────────────────

    async def _create_match_from_queue(
        self,
        queue: MatchQueue,
        bot: discord.Client,
        channel: discord.TextChannel,
        confirm_thread: discord.Thread,
        conf_msg: discord.Message,
        time_blue: List[int],
        time_red: List[int]
    ):
        try:
            from views.match_thread_view import embed_match_created

            guild   = channel.guild
            players = list(queue.players)

            # Extrai match_type ("1x1") do channel_name ("1x1-mob")
            match_type = queue.channel_name.split("-")[0] if "-" in queue.channel_name else queue.channel_name
            platform   = queue.channel_name.split("-")[1] if "-" in queue.channel_name else "mob"

            # ── Mediador ──────────────────────────────────────
            mediator_id = await mediator_queue.get_next_mediator()
            if not mediator_id:
                await confirm_thread.send(
                    "❌ Nenhum mediador disponível. Partida cancelada.\n"
                    "Tente novamente em alguns instantes."
                )
                await self._expire_queue(queue, bot, channel, None, confirm_thread)
                return

            # ── Cria match no banco (tudo de uma vez) ─────────
            match_data = await match_service.create_match(
                guild_id=guild.id,
                channel_id=channel.id,
                channel_name=queue.channel_name,
                player_ids=players,
                mediator_id=mediator_id,
                bet_value=queue.bet_value,
                gel_type=queue.gel_type,
                match_type=match_type,
                platform=platform,
            )
            match_id = str(match_data['_id'])

            # Salva time_blue, time_red e thread_id via service
            await match_service._update(match_id, {
                'time_blue': [str(p) for p in time_blue],
                'time_red':  [str(p) for p in time_red],
                'thread_id': confirm_thread.id,
            })

            # Marca fila como matched (rastreabilidade) e remove do cache
            queue.mark_as_matched(match_id)
            await self._save_queue(queue)
            await self._delete_queue(queue)

            # ── Renomeia tópico ───────────────────────────────
            match_thread_name = (
                f"⚔️ R${queue.bet_value:.2f} "
                f"{queue.gel_type.capitalize()} "
                f"— {queue.channel_name.upper()}"
            )
            try:
                await confirm_thread.edit(name=match_thread_name[:100])
            except Exception:
                pass

            # ── Embed de confirmação final ────────────────────
            mediator_member = guild.get_member(mediator_id)
            blue_str = "\n".join(f"✅ <@{uid}>" for uid in time_blue) or "—"
            red_str  = "\n".join(f"✅ <@{uid}>" for uid in time_red)  or "—"

            confirmed_embed = discord.Embed(
                title="✅ Todos confirmaram!",
                description=(
                    f"**Modo:** `{queue.channel_name.upper()}` | "
                    f"**Valor:** R$ {queue.bet_value:.2f} | "
                    f"**GEL:** {queue.gel_type.capitalize()}\n\n"
                    f"📊 **Status:** 🟢 Aguardando Pagamento\n"
                    f"👨‍⚖️ **Mediador:** "
                    f"{mediator_member.mention if mediator_member else f'<@{mediator_id}>'}"
                ),
                color=discord.Color.green()
            )
            confirmed_embed.add_field(name="🔵 Time Blue", value=blue_str, inline=True)
            confirmed_embed.add_field(name="🔴 Time Red",  value=red_str,  inline=True)
            confirmed_embed.add_field(name="🎯 ID da Partida", value=f"`{match_id}`", inline=False)
            confirmed_embed.set_footer(text="O mediador irá confirmar o pagamento para iniciar")

            try:
                await conf_msg.edit(embed=confirmed_embed, view=None)
            except Exception:
                pass

            # ── Adiciona mediador ao tópico ───────────────────
            if mediator_member:
                try:
                    await confirm_thread.add_user(mediator_member)
                except Exception:
                    pass

            # ── Busca match completo e posta embed principal ──
            match_full = await match_service.get_match(match_id)
            mentions   = " ".join(f"<@{uid}>" for uid in players)
            if mediator_member:
                mentions += f" {mediator_member.mention}"

            await confirm_thread.send(
                content=mentions,
                embed=embed_match_created(match_full)
            )

            # Lembrete para o mediador (só ele e ADM verão o card)
            lembrete = discord.Embed(
                title="🎮 Mediador — Painel de Controle",
                description=(
                    f"<@{mediator_id}>, use o comando abaixo para controlar a partida:\n\n"
                    "**`!menu_partida`**\n\n"
                    "O painel abre **somente para você** (ephemeral)."
                ),
                color=discord.Color.blurple()
            )
            await confirm_thread.send(embed=lembrete)

            # ── DM para cada jogador com seu time ─────────────
            for uid in time_blue:
                m = guild.get_member(uid)
                if m:
                    try:
                        await m.send(
                            f"🔵 Você está no **Time Blue**!\n"
                            f"**Valor:** R$ {queue.bet_value:.2f}\n"
                            f"**Tópico:** {confirm_thread.mention}"
                        )
                    except discord.Forbidden:
                        pass

            for uid in time_red:
                m = guild.get_member(uid)
                if m:
                    try:
                        await m.send(
                            f"🔴 Você está no **Time Red**!\n"
                            f"**Valor:** R$ {queue.bet_value:.2f}\n"
                            f"**Tópico:** {confirm_thread.mention}"
                        )
                    except discord.Forbidden:
                        pass

            logger.info(
                f"✅ Match criado: {match_thread_name} | "
                f"Jogadores: {players} | Mediador: {mediator_id}"
            )

        except Exception as e:
            logger.error(f"Erro ao criar partida da fila: {e}", exc_info=True)
            await confirm_thread.send(f"❌ Erro ao criar partida: {e}")

    # ─────────────────────────────────────────────
    # Expirar fila
    # ─────────────────────────────────────────────

    async def _expire_queue(
        self,
        queue: MatchQueue,
        bot: discord.Client,
        channel: discord.TextChannel,
        message: Optional[discord.Message],
        confirm_thread: discord.Thread = None
    ):
        queue.status = MatchQueue.STATUS_EXPIRED
        await self._save_queue(queue)

        not_confirmed = queue.pending_confirmations()

        embed = discord.Embed(
            title="❌ Tempo Esgotado",
            description="A partida foi cancelada porque nem todos confirmaram a tempo.",
            color=discord.Color.red()
        )
        if not_confirmed:
            embed.add_field(
                name="Não confirmaram",
                value="\n".join(f"• <@{uid}>" for uid in not_confirmed),
                inline=False
            )
        embed.set_footer(text="Este tópico será arquivado em 10 segundos")

        if message:
            try:
                await message.edit(embed=embed, view=None)
            except Exception:
                pass
        elif confirm_thread:
            await confirm_thread.send(embed=embed)
        else:
            await channel.send(embed=embed)

        if confirm_thread:
            await asyncio.sleep(10)
            try:
                await confirm_thread.edit(archived=True, locked=True)
            except Exception:
                pass

        await self._delete_queue(queue)

    # ─────────────────────────────────────────────
    # Status / Save / Delete
    # ─────────────────────────────────────────────

    async def get_queue_status(
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str
    ) -> Optional[MatchQueue]:
        """Lê sempre do banco para garantir estado atual."""
        collection = db.get_collection('match_queues')
        queue_data = await collection.find_one({
            "channel_name": channel_name,
            "bet_value":    bet_value,
            "gel_type":     gel_type,
            "status":       {"$in": [MatchQueue.STATUS_WAITING, MatchQueue.STATUS_CONFIRMING]}
        })
        return MatchQueue.from_dict(queue_data) if queue_data else None

    async def _save_queue(self, queue: MatchQueue):
        collection = db.get_collection('match_queues')
        await collection.replace_one({"_id": queue._id}, queue.to_dict(), upsert=True)
        queue_key = self.get_queue_key(queue.channel_name, queue.bet_value, queue.gel_type)
        self.active_queues[queue_key] = queue

    async def _delete_queue(self, queue: MatchQueue):
        collection = db.get_collection('match_queues')
        await collection.delete_one({"_id": queue._id})
        queue_key = self.get_queue_key(queue.channel_name, queue.bet_value, queue.gel_type)
        self.active_queues.pop(queue_key, None)
        self._queue_locks.pop(queue_key, None)

    # ─────────────────────────────────────────────
    # Compatibilidade com !simularfila
    # ─────────────────────────────────────────────

    async def _create_match_from_queue_compat(
        self,
        queue: MatchQueue,
        bot: discord.Client,
        channel: discord.TextChannel
    ):
        players   = list(queue.players)
        time_blue = [players[0]]
        time_red  = [players[1]]

        thread_name = (
            f"🟡 Confirmando — R${queue.bet_value:.2f} "
            f"{queue.gel_type.capitalize()} "
            f"{queue.channel_name.upper()}"
        )
        confirm_thread = await channel.create_thread(
            name=thread_name[:100],
            type=discord.ChannelType.public_thread,
            auto_archive_duration=60
        )
        for uid in players:
            m = channel.guild.get_member(uid)
            if m:
                try:
                    await confirm_thread.add_user(m)
                except Exception:
                    pass

        queue.confirmations = list(queue.players)
        queue.thread_id     = confirm_thread.id
        await self._save_queue(queue)

        embed    = self._build_confirmation_embed(queue, time_blue, time_red, remaining=0)
        conf_msg = await confirm_thread.send(embed=embed)

        await self._create_match_from_queue(
            queue, bot, channel, confirm_thread, conf_msg, time_blue, time_red
        )


# ─────────────────────────────────────────────
# ConfirmationView
# ─────────────────────────────────────────────

class ConfirmationView(discord.ui.View):

    def __init__(
        self,
        queue: MatchQueue,
        service: MatchQueueService,
        bot: discord.Client,
        time_blue: List[int] = None,
        time_red: List[int]  = None,
        conf_msg: discord.Message = None,
    ):
        super().__init__(timeout=None)
        self.queue     = queue
        self.service   = service
        self.bot       = bot
        self.time_blue = time_blue or []
        self.time_red  = time_red  or []
        self.conf_msg  = conf_msg

        btn_confirmar          = discord.ui.Button(
            label="✅ CONFIRMAR",
            style=discord.ButtonStyle.green,
            custom_id=f"confirm_{queue._id}"
        )
        btn_confirmar.callback = self._confirm_callback
        self.add_item(btn_confirmar)

        btn_recusar          = discord.ui.Button(
            label="❌ RECUSAR",
            style=discord.ButtonStyle.red,
            custom_id=f"decline_{queue._id}"
        )
        btn_recusar.callback = self._decline_callback
        self.add_item(btn_recusar)

    async def _confirm_callback(self, interaction: discord.Interaction):
        if interaction.user.id not in self.queue.players:
            await interaction.response.send_message("❌ Você não está nesta partida!", ephemeral=True)
            return

        if interaction.user.id in self.queue.confirmations:
            await interaction.response.send_message("✅ Você já confirmou!", ephemeral=True)
            return

        # Relê do banco para garantir estado atual
        collection = db.get_collection('match_queues')
        queue_data = await collection.find_one({"_id": self.queue._id})
        if not queue_data:
            await interaction.response.send_message("❌ Esta fila não existe mais.", ephemeral=True)
            return

        self.queue = MatchQueue.from_dict(queue_data)

        if self.queue.status == MatchQueue.STATUS_MATCHED:
            await interaction.response.send_message("✅ Partida já foi criada!", ephemeral=True)
            return

        parent_channel = interaction.channel.parent if hasattr(interaction.channel, 'parent') else interaction.channel

        await self.service.add_confirmation(
            queue=self.queue,
            player_id=interaction.user.id,
            bot=self.bot,
            channel=parent_channel,
            confirm_thread=interaction.channel,
            message=self.conf_msg or interaction.message,
            time_blue=self.time_blue,
            time_red=self.time_red,
        )
        await interaction.response.send_message("✅ Confirmado! Aguardando os demais...", ephemeral=True)

    async def _decline_callback(self, interaction: discord.Interaction):
        # Relê do banco antes de qualquer ação
        collection = db.get_collection('match_queues')
        queue_data = await collection.find_one({"_id": self.queue._id})
        if not queue_data:
            await interaction.response.send_message("❌ Esta fila não existe mais.", ephemeral=True)
            return

        self.queue = MatchQueue.from_dict(queue_data)

        if interaction.user.id not in self.queue.players:
            await interaction.response.send_message("❌ Você não está nesta partida!", ephemeral=True)
            return

        parent_channel = interaction.channel.parent if hasattr(interaction.channel, 'parent') else interaction.channel

        await self.service.remove_player_from_queue(
            self.queue.channel_name,
            self.queue.bet_value,
            self.queue.gel_type,
            interaction.user.id
        )
        await interaction.response.send_message("❌ Você recusou a partida.", ephemeral=True)

        await self.service._expire_queue(
            self.queue,
            self.bot,
            parent_channel,
            None,
            interaction.channel
        )


# Instância global
match_queue_service = MatchQueueService()
