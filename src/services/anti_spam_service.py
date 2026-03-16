import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from utils.datetime_utils import utcnow
from typing import Deque, Dict, Optional

import discord

from config.database import db
from config.anti_spam_config import AntiSpamConfig
from utils.logger import logger


SPAM_BLOCK_ROLE_NAME = AntiSpamConfig.SPAM_BLOCK_ROLE_NAME
MEMBER_ROLE_NAME     = "Membro"


@dataclass
class _DupState:
    content_key: str = ""
    first_ts: float  = 0.0
    count: int       = 0


class AntiSpamService:
    """
    Bloquear  = remove cargo Membro + adiciona cargo Bloqueado
    Desbloquear (só ADM) = remove Bloqueado + devolve Membro
    Card postado em #membros-bloqueados e atualizado ao desbloquear.
    """

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self._rate: Dict[int, Dict[int, Deque[float]]] = defaultdict(lambda: defaultdict(deque))
        self._dup:  Dict[int, Dict[int, _DupState]]    = defaultdict(lambda: defaultdict(_DupState))
        self._block_role_cache:  Dict[int, int] = {}
        self._member_role_cache: Dict[int, int] = {}

    # ─────────────────────────────────────────────
    # Setup — só cria o cargo (sem overwrites)
    # ─────────────────────────────────────────────

    async def ensure_role_and_overwrites(self, guild: discord.Guild) -> discord.Role:
        role = discord.utils.get(guild.roles, name=SPAM_BLOCK_ROLE_NAME)
        if not role:
            role = await guild.create_role(
                name=SPAM_BLOCK_ROLE_NAME,
                reason="Cargo de bloqueio automático por spam",
                mentionable=False,
                colour=discord.Color.dark_red()
            )
            logger.info(f"[AntiSpam] Cargo '{SPAM_BLOCK_ROLE_NAME}' criado em {guild.name}")
        self._block_role_cache[guild.id] = role.id
        return role

    # ─────────────────────────────────────────────
    # Helpers de cargo
    # ─────────────────────────────────────────────

    async def _get_block_role(self, guild: discord.Guild) -> discord.Role:
        rid  = self._block_role_cache.get(guild.id)
        role = guild.get_role(rid) if rid else None
        if role:
            return role
        role = discord.utils.get(guild.roles, name=SPAM_BLOCK_ROLE_NAME)
        if role:
            self._block_role_cache[guild.id] = role.id
            return role
        return await self.ensure_role_and_overwrites(guild)

    async def _get_member_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        rid  = self._member_role_cache.get(guild.id)
        role = guild.get_role(rid) if rid else None
        if role:
            return role
        role = discord.utils.get(guild.roles, name=MEMBER_ROLE_NAME)
        if role:
            self._member_role_cache[guild.id] = role.id
        return role

    # ─────────────────────────────────────────────
    # Restaurar bloqueados ao reiniciar
    # ─────────────────────────────────────────────

    async def restore_blocked_members(self, guild: discord.Guild):
        try:
            col         = db.get_collection("users")
            block_role  = await self._get_block_role(guild)
            member_role = await self._get_member_role(guild)
            count       = 0

            async for doc in col.find({"spam_blocked": True, "is_active": True}):
                did = doc.get("discord_id")
                if not did:
                    continue
                try:
                    member = guild.get_member(int(did))
                    if not member:
                        continue
                    if block_role not in member.roles:
                        await member.add_roles(block_role, reason="AntiSpam: restaurar bloqueio")
                        count += 1
                    if member_role and member_role in member.roles:
                        await member.remove_roles(member_role, reason="AntiSpam: restaurar bloqueio")
                except Exception:
                    continue

            if count:
                logger.info(f"[AntiSpam] {count} membros bloqueados restaurados em {guild.name}")
        except Exception as e:
            logger.error(f"[AntiSpam] Erro restore_blocked_members: {e}")

    async def handle_member_join(self, member: discord.Member):
        try:
            col = db.get_collection("users")
            doc = await col.find_one({"discord_id": str(member.id)})
            if doc and doc.get("spam_blocked"):
                block_role  = await self._get_block_role(member.guild)
                member_role = await self._get_member_role(member.guild)
                if block_role not in member.roles:
                    await member.add_roles(block_role, reason="AntiSpam: membro bloqueado re-entrou")
                if member_role and member_role in member.roles:
                    await member.remove_roles(member_role, reason="AntiSpam: membro bloqueado re-entrou")
                logger.warning(f"[AntiSpam] {member.name} re-entrou bloqueado — cargo reaplicado")
        except Exception as e:
            logger.warning(f"[AntiSpam] Erro handle_member_join: {e}")

    # ─────────────────────────────────────────────
    # Processamento de mensagens
    # ─────────────────────────────────────────────

    async def process_message(self, message: discord.Message):
        if not message.guild:
            return
        if not message.author or message.author.bot:
            return
        if not isinstance(message.author, discord.Member):
            return

        guild:  discord.Guild  = message.guild
        author: discord.Member = message.author

        if author.guild_permissions.administrator:
            return

        block_role = discord.utils.get(guild.roles, name=SPAM_BLOCK_ROLE_NAME)
        if block_role and block_role in author.roles:
            try:
                await message.delete()
            except Exception:
                pass
            return

        now = time.monotonic()

        # Flood de menções
        if message.mentions and len(message.mentions) >= AntiSpamConfig.MAX_MENTIONS_PER_MESSAGE:
            await self._block_member(
                member=author,
                reason=f"Flood de menções ({len(message.mentions)})",
                evidence=f"canal=#{getattr(message.channel, 'name', '?')}"
            )
            try:
                await message.delete()
            except Exception:
                pass
            return

        # Rate limit
        dq = self._rate[guild.id][author.id]
        dq.append(now)
        self._trim_deque(dq, now, AntiSpamConfig.RATE_WINDOW_SECS)
        if len(dq) >= AntiSpamConfig.RATE_MAX_MESSAGES:
            await self._block_member(
                member=author,
                reason=f"Rate spam ({len(dq)} msgs/{AntiSpamConfig.RATE_WINDOW_SECS}s)",
                evidence=f"canal=#{getattr(message.channel, 'name', '?')}"
            )
            try:
                await message.delete()
            except Exception:
                pass
            return

        # Mensagem repetida
        content_key = self._content_key(message)
        if content_key:
            ds = self._dup[guild.id][author.id]
            if ds.content_key != content_key or (now - ds.first_ts) > AntiSpamConfig.DUP_WINDOW_SECS:
                ds.content_key = content_key
                ds.first_ts    = now
                ds.count       = 1
            else:
                ds.count += 1

            if ds.count >= AntiSpamConfig.DUP_MAX_COUNT:
                await self._block_member(
                    member=author,
                    reason=f"Mensagem repetida ({ds.count}x/{AntiSpamConfig.DUP_WINDOW_SECS}s)",
                    evidence=f"msg='{content_key[:80]}'"
                )
                try:
                    await message.delete()
                except Exception:
                    pass

    def _trim_deque(self, dq: Deque[float], now: float, window: int):
        limit = now - float(window)
        while dq and dq[0] < limit:
            dq.popleft()

    def _content_key(self, message: discord.Message) -> str:
        text = (message.content or "").strip().lower()
        if not text and message.attachments:
            return "<attachment>"
        while "  " in text:
            text = text.replace("  ", " ")
        return text

    # ─────────────────────────────────────────────
    # Bloquear
    # ─────────────────────────────────────────────

    async def _block_member(self, member: discord.Member, reason: str, evidence: str = ""):
        guild       = member.guild
        block_role  = await self._get_block_role(guild)
        member_role = await self._get_member_role(guild)
        now         = utcnow()

        # Remove cargo Membro
        try:
            if member_role and member_role in member.roles:
                await member.remove_roles(member_role, reason=f"AntiSpam: {reason}")
        except Exception as e:
            logger.warning(f"[AntiSpam] Não consegui remover Membro de {member.name}: {e}")

        # Adiciona cargo Bloqueado
        try:
            if block_role not in member.roles:
                await member.add_roles(block_role, reason=f"AntiSpam: {reason}")
        except Exception as e:
            logger.error(f"[AntiSpam] Não consegui aplicar Bloqueado em {member.name}: {e}")
            return

        # Posta card no canal de bloqueados
        card_msg = await self._post_block_card(guild, member, reason, evidence, now)

        # Salva no banco
        try:
            col = db.get_collection("users")
            await col.update_one(
                {"discord_id": str(member.id)},
                {"$set": {
                    "spam_blocked":               True,
                    "spam_blocked_at":             now,
                    "spam_block_reason":           reason,
                    "spam_block_evidence":         evidence,
                    "spam_block_card_message_id":  card_msg.id      if card_msg else None,
                    "spam_block_card_channel_id":  card_msg.channel.id if card_msg else None,
                    "has_accepted_rules":          False,
                    "updated_at":                  now,
                }},
                upsert=True
            )
        except Exception as e:
            logger.warning(f"[AntiSpam] Falha ao salvar bloqueio no banco: {e}")

        logger.warning(f"[AntiSpam] {member.name} BLOQUEADO — {reason} | {evidence}")

    async def block_member_manual(
        self,
        guild: discord.Guild,
        member: discord.Member,
        by: discord.Member,
        reason: str
    ):
        await self._block_member(
            member=member,
            reason=f"Manual por {by.display_name}: {reason}",
            evidence=f"by={by} ({by.id})"
        )

    # ─────────────────────────────────────────────
    # Card no canal de bloqueados
    # ─────────────────────────────────────────────

    async def _post_block_card(
        self,
        guild: discord.Guild,
        member: discord.Member,
        reason: str,
        evidence: str,
        blocked_at: datetime
    ) -> Optional[discord.Message]:
        try:
            from views.spam_block_card_view import create_blocked_embed, SpamBlockCardView

            channel = discord.utils.get(
                guild.text_channels,
                name=AntiSpamConfig.SPAM_BLOCKED_CHANNEL_NAME
            )
            if not channel:
                logger.warning(f"[AntiSpam] Canal '{AntiSpamConfig.SPAM_BLOCKED_CHANNEL_NAME}' não encontrado")
                return None

            embed = create_blocked_embed(
                member_id=member.id,
                member_name=member.display_name,
                member_avatar_url=str(member.display_avatar.url),
                reason=reason,
                evidence=evidence,
                blocked_at=blocked_at
            )
            return await channel.send(embed=embed, view=SpamBlockCardView())
        except Exception as e:
            logger.error(f"[AntiSpam] Erro ao postar card de bloqueio: {e}")
            return None

    # ─────────────────────────────────────────────
    # Desbloquear (só ADM)
    # ─────────────────────────────────────────────

    async def unblock_member(
        self,
        guild: discord.Guild,
        member: Optional[discord.Member],
        by: discord.Member,
        card_message: Optional[discord.Message] = None,
        member_id_fallback: Optional[int] = None
    ):
        member_id   = member.id if member else member_id_fallback
        member_name = member.display_name if member else f"ID:{member_id}"
        member_avatar = str(member.display_avatar.url) if member else ""

        if not member_id:
            raise ValueError("member ou member_id_fallback é obrigatório")

        block_role  = await self._get_block_role(guild)
        member_role = await self._get_member_role(guild)

        if member:
            # Remove cargo Bloqueado
            try:
                if block_role in member.roles:
                    await member.remove_roles(block_role, reason=f"AntiSpam: desbloqueado por {by}")
            except Exception as e:
                logger.error(f"[AntiSpam] Erro ao remover Bloqueado de {member_name}: {e}")
                raise

            # Devolve cargo Membro
            try:
                if member_role and member_role not in member.roles:
                    await member.add_roles(member_role, reason=f"AntiSpam: acesso restaurado por {by}")
            except Exception as e:
                logger.warning(f"[AntiSpam] Não consegui devolver Membro para {member_name}: {e}")

        now = utcnow()

        # Busca dados originais no banco
        col = db.get_collection("users")
        doc = await col.find_one({"discord_id": str(member_id)})
        original_reason   = doc.get("spam_block_reason",   "Desconhecido") if doc else "Desconhecido"
        original_evidence = doc.get("spam_block_evidence", "")             if doc else ""
        blocked_at        = doc.get("spam_blocked_at")                      if doc else None
        card_msg_id       = doc.get("spam_block_card_message_id")           if doc else None
        card_ch_id        = doc.get("spam_block_card_channel_id")           if doc else None

        # Atualiza banco
        await col.update_one(
            {"discord_id": str(member_id)},
            {"$set": {
                "spam_blocked":       False,
                "spam_unblocked_at":  now,
                "spam_unblocked_by":  str(by.id),
                "has_accepted_rules": True,
                "updated_at":         now,
            }},
            upsert=True
        )

        # Tenta encontrar o card se não foi passado diretamente
        if not card_message and card_msg_id and card_ch_id:
            try:
                ch = guild.get_channel(int(card_ch_id))
                if ch:
                    card_message = await ch.fetch_message(int(card_msg_id))
            except Exception:
                pass

        # Atualiza o card
        if card_message:
            try:
                from views.spam_block_card_view import create_unblocked_embed, SpamBlockCardView

                new_embed = create_unblocked_embed(
                    member_id=member_id,
                    member_name=member_name,
                    member_avatar_url=member_avatar,
                    reason=original_reason,
                    evidence=original_evidence,
                    blocked_at=blocked_at,
                    unblocked_by_id=by.id,
                    unblocked_by_name=by.display_name,
                    unblocked_at=now
                )
                await card_message.edit(embed=new_embed, view=SpamBlockCardView(disabled=True))
            except Exception as e:
                logger.warning(f"[AntiSpam] Não consegui atualizar card: {e}")

        logger.info(f"[AntiSpam] {member_name} desbloqueado por {by.name}")

    # Alias para compatibilidade com main.py
    async def check_message(self, message: discord.Message) -> bool:
        """Retorna True se a mensagem foi bloqueada (spam)."""
        await self.process_message(message)
        return False  # main.py usa o retorno como "bloquear processamento"


# Instância global — precisa de bot; será inicializado no on_ready
from discord.ext import commands as _commands
_bot_placeholder = _commands.Bot.__new__(_commands.Bot)
anti_spam_service = AntiSpamService(_bot_placeholder)
