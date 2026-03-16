from __future__ import annotations
import discord
from utils.logger import logger
from utils.retry import with_retry


class CardService:

    def __init__(self):
        self.bot: discord.Client | None = None

    @with_retry(attempts=3, backoff=2.0)
    async def post_or_update_card(
        self,
        channel: discord.TextChannel,
        embed: discord.Embed,
        view: discord.ui.View | None,
        card_id: str,
        storage_collection: str = "bot_cards"
    ) -> discord.Message | None:
        from config.database import db
        col = db.get_collection(storage_collection)
        doc = await col.find_one({"card_id": card_id, "channel_id": str(channel.id)})
        if doc and doc.get("message_id"):
            try:
                msg = await channel.fetch_message(int(doc["message_id"]))
                await msg.edit(embed=embed, view=view)
                return msg
            except (discord.NotFound, discord.HTTPException):
                pass
        msg = await channel.send(embed=embed, view=view)
        await col.update_one(
            {"card_id": card_id, "channel_id": str(channel.id)},
            {"$set": {"message_id": str(msg.id)}},
            upsert=True
        )
        return msg

    @with_retry(attempts=3, backoff=2.0)
    async def delete_card(
        self,
        channel: discord.TextChannel,
        card_id: str,
        storage_collection: str = "bot_cards"
    ):
        from config.database import db
        col = db.get_collection(storage_collection)
        doc = await col.find_one({"card_id": card_id, "channel_id": str(channel.id)})
        if doc and doc.get("message_id"):
            try:
                msg = await channel.fetch_message(int(doc["message_id"]))
                await msg.delete()
            except (discord.NotFound, discord.HTTPException):
                pass
        await col.delete_one({"card_id": card_id, "channel_id": str(channel.id)})

    async def bulk_update_match_cards(self, guild: discord.Guild):
        from services.match_queue_service import match_queue_service
        active_queues = await match_queue_service.get_all_active_queues(guild.id)
        for queue in active_queues:
            try:
                ch = discord.utils.get(guild.text_channels, name=queue.channel_name)
                if not ch:
                    continue
                embed, view = await match_queue_service.build_queue_card(queue)
                await self.post_or_update_card(ch, embed, view, f"queue_{queue.channel_name}")
            except Exception as e:
                logger.warning(f"[CardService] Erro ao atualizar card {queue.channel_name}: {e}")

    async def setup_channel_cards(self, channel: discord.TextChannel):
        from views.match_cards_view import MatchCardView, build_match_card_embed
        from config.channels_config import ChannelsConfig

        ch_name = channel.name
        to_delete = []
        async for msg in channel.history(limit=30):
            if msg.author == channel.guild.me and (msg.embeds or msg.components):
                to_delete.append(msg)
        for msg in to_delete:
            try:
                await msg.delete()
            except Exception:
                pass

        for value in ChannelsConfig.BET_VALUES:
            try:
                embed = build_match_card_embed(ch_name, value)
                view  = MatchCardView(channel_name=ch_name, bet_value=value)
                await channel.send(embed=embed, view=view)
            except Exception as e:
                logger.warning(f"[CardService] Erro ao postar card {ch_name} R${value}: {e}")

        logger.info(f"[CardService] {len(ChannelsConfig.BET_VALUES)} cards postados: #{ch_name}")


card_service = CardService()
