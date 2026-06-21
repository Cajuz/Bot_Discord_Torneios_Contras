# services/match_service.py
from __future__ import annotations
import asyncio
from typing import Dict, Any, List, Optional

from bson import ObjectId
import discord

from config.database import db
from models.match import Match
from services.commission_service import commission_service
from utils.datetime_utils import utcnow
from utils.logger import logger, log_success


class MatchService:

    # ── Helpers internos ────────────────────────────────────────────

    def _get_collection(self):
        return db.get_collection("matches")

    async def _find(self, match_id: str) -> Optional[Dict[str, Any]]:
        col = self._get_collection()
        return await col.find_one({"_id": ObjectId(match_id)})

    async def _update(self, match_id: str, fields: dict) -> Optional[Dict[str, Any]]:
        col = self._get_collection()
        fields["updated_at"] = utcnow()
        await col.update_one({"_id": ObjectId(match_id)}, {"$set": fields})
        return await col.find_one({"_id": ObjectId(match_id)})

    # ── Snapshot de comissão ─────────────────────────────────────────

    async def _snapshot_commission(self, match_id: str, match_doc: dict) -> dict:
        """
        Calcula e persiste commission_per_player e commission_total no documento
        da partida (snapshot no momento do encerramento).
        Retorna dict com {taxa, total} para uso imediato.
        """
        bet_value = float(match_doc.get("bet_value", 0) or 0)
        guild_id  = str(match_doc.get("guild_id", ""))
        try:
            scheme = await commission_service.get_match_config(guild_id) if guild_id else {}
            taxa   = commission_service.calculate_per_player(bet_value, scheme)
        except Exception as e:
            logger.warning(f"[MatchService] commission snapshot fallback: {e}")
            taxa = commission_service.calculate_per_player(bet_value, {})

        num_players = len(match_doc.get("player_ids", [])) or 2
        total       = taxa * num_players

        await self._update(match_id, {
            "commission_per_player": round(taxa, 2),
            "commission_total":      round(total, 2),
        })
        return {"taxa": taxa, "total": total}

    # ── Acumula comissão no saldo do mediador ─────────────────────────

    async def _credit_mediator_commission(self, match_doc: dict, commission_total: float) -> None:
        """
        Incrementa saldo_pendente e partidas_mediadas na collection 'comissoes'
        para o mediador responsável pela partida.
        Só credita se commission_total > 0 e mediator_id presente.
        """
        mediator_id = str(match_doc.get("mediator_id", ""))
        if not mediator_id or commission_total <= 0:
            return
        try:
            nome = ""
            try:
                from config.discord_bot import get_bot
                bot = get_bot()
                guild_id = match_doc.get("guild_id")
                if bot and guild_id:
                    guild = bot.get_guild(int(guild_id))
                    if guild:
                        member = guild.get_member(int(mediator_id))
                        if member:
                            nome = member.display_name
            except Exception:
                pass

            update = {
                "$inc": {
                    "saldo_pendente":    round(commission_total, 2),
                    "partidas_mediadas": 1,
                },
                "$set": {"updated_at": utcnow()},
                "$setOnInsert": {
                    "total_recebido": 0.0,
                    "mediador_id":    mediator_id,
                },
            }
            if nome:
                update["$set"]["nome"] = nome

            await db.get_collection("comissoes").update_one(
                {"mediador_id": mediator_id},
                update,
                upsert=True,
            )
            logger.info(
                f"[MatchService] Comissão creditada: mediador={mediator_id} "
                f"valor={commission_total:.2f}"
            )
        except Exception as e:
            logger.error(f"[MatchService] _credit_mediator_commission erro: {e}", exc_info=True)

    # ── Histórico ─────────────────────────────────────────────────────

    async def _post_history(self, match_doc: dict, outcome: str = "finalizado"):
        try:
            from config.discord_bot import get_bot
            bot: discord.Client = get_bot()
            if not bot:
                return
            guild_id = match_doc.get("guild_id")
            if not guild_id:
                return
            guild = bot.get_guild(int(guild_id))
            if not guild:
                return
            history_ch = discord.utils.get(guild.text_channels, name="historico-partidas")
            if not history_ch:
                return
            embed = await self._build_history_embed(match_doc, outcome)
            await history_ch.send(embed=embed)
            logger.info(f"[History] Partida {match_doc['_id']} postada em #historico-partidas")
        except Exception as e:
            logger.warning(f"[History] Erro ao postar histórico: {e}")

    async def _build_history_embed(self, match: dict, outcome: str) -> discord.Embed:
        bet_value = match.get("bet_value", 0)

        # Usa snapshot salvo no documento (mais confiável que recalcular)
        taxa = float(match.get("commission_per_player") or 0)
        if not taxa:
            guild_id = str(match.get("guild_id", ""))
            scheme   = await commission_service.get_match_config(guild_id) if guild_id else {}
            taxa     = commission_service.calculate_per_player(bet_value, scheme)

        total_por_jogador = bet_value + taxa
        premio            = bet_value * 2

        vencedor   = match.get("vencedor")
        gel        = match.get("gel_type", "normal").capitalize()
        modo       = match.get("match_type", "?").upper()
        canal      = match.get("channel_name", "?")
        match_id   = str(match.get("_id", "?"))
        player_ids = match.get("player_ids", [])
        time_blue  = match.get("time_blue", [])
        time_red   = match.get("time_red", [])

        color_map = {
            "finalizado": discord.Color.green(),
            "cancelado":  discord.Color.red(),
            "forcado":    discord.Color.orange(),
        }
        title_map = {
            "finalizado": "✅ Partida Finalizada",
            "cancelado":  "❌ Partida Cancelada",
            "forcado":    "⚡ Partida Encerrada (Admin)",
        }
        color = color_map.get(outcome, discord.Color.greyple())
        title = title_map.get(outcome, "Partida Encerrada")

        embed = discord.Embed(
            title=title,
            description=f"**Modo:** {modo} | **GEL:** {gel} | **Canal:** `#{canal}`",
            color=color,
        )

        if time_blue or time_red:
            blue_mark = "🏆 " if vencedor == "blue" else ""
            red_mark  = "🏆 " if vencedor == "red"  else ""
            embed.add_field(
                name=f"{blue_mark}🔵 Time Blue",
                value="\n".join(f"• <@{uid}>" for uid in time_blue) or "—",
                inline=True,
            )
            embed.add_field(
                name=f"{red_mark}🔴 Time Red",
                value="\n".join(f"• <@{uid}>" for uid in time_red) or "—",
                inline=True,
            )
        else:
            embed.add_field(
                name="👥 Jogadores",
                value="\n".join(f"• <@{uid}>" for uid in player_ids) or "—",
                inline=False,
            )

        embed.add_field(name="\u200b", value="\u200b", inline=False)

        if outcome == "finalizado" and vencedor:
            label   = "🔵 Time Blue" if vencedor == "blue" else "🔴 Time Red"
            win_ids = time_blue if vencedor == "blue" else time_red
            embed.add_field(
                name="🏆 Vencedor",
                value=f"{label}\n" + " ".join(f"<@{uid}>" for uid in win_ids),
                inline=True,
            )
            embed.add_field(name="💰 Prêmio pago", value=f"R$ {premio:.2f}", inline=True)
        elif outcome == "cancelado":
            reason       = match.get("cancel_reason") or "—"
            cancelled_by = match.get("cancelled_by")
            embed.add_field(name="🚫 Motivo", value=reason, inline=True)
            if cancelled_by:
                embed.add_field(name="👤 Cancelado por",
                                value=f"<@{cancelled_by}>", inline=True)

        embed.add_field(
            name="📊 Valores",
            value=(
                f"Aposta: **R$ {bet_value:.2f}** | "
                f"Taxa: **R$ {taxa:.2f}** | "
                f"Cada jogador pagou: **R$ {total_por_jogador:.2f}**"
            ),
            inline=False,
        )
        embed.add_field(name="🕵️ Mediador",
                        value=f"<@{match['mediator_id']}>", inline=True)
        embed.add_field(name="🆔 Match ID", value=f"`{match_id}`", inline=True)

        completed_at = match.get("completed_at") or match.get("cancelled_at") or utcnow()
        embed.set_footer(text="Encerrada em")
        embed.timestamp = completed_at
        return embed

    # ── Criação ─────────────────────────────────────────────────────

    async def create_match(
        self,
        guild_id:    int,
        channel_id:  int,
        channel_name: str,
        player_ids:  List[int],
        mediator_id: int,
        bet_value:   float,
        gel_type:    str = "normal",
        match_type:  str = "📱1x1",
        platform:    str = "mob",
    ) -> Dict[str, Any]:
        try:
            match_data = {
                "guild_id":                  str(guild_id),
                "channel_id":                str(channel_id),
                "channel_name":              channel_name,
                "match_type":                match_type,
                "platform":                  platform,
                "bet_value":                 bet_value,
                "gel_type":                  gel_type,
                "player_ids":                [str(pid) for pid in player_ids],
                "max_players":               len(player_ids),
                "mediator_id":               str(mediator_id),
                # ─ novo fluxo: inicia direto em aguardando_partida ─
                "status":                    Match.STATUS_AGUARDANDO_PARTIDA,
                "thread_id":                 None,
                "time_blue":                 [],
                "time_red":                  [],
                "vencedor":                  None,
                "winner_id":                 None,
                "premio_confirmado_jogador": False,
                "cancelled_by":              None,
                "cancel_reason":             None,
                "commission_per_player":     None,
                "commission_total":          None,
                "created_at":                utcnow(),
                "updated_at":                utcnow(),
                "started_at":                None,
                "completed_at":              None,
                "cancelled_at":              None,
            }
            col    = self._get_collection()
            result = await col.insert_one(match_data)
            match_data["_id"] = result.inserted_id
            logger.info(
                f"✅ Partida criada: {result.inserted_id} | guild={guild_id} | "
                f"bet={bet_value} | mediator={mediator_id}"
            )
            return match_data
        except Exception as e:
            logger.error(f"❌ Erro ao criar partida: {e}")
            return {}

    # ── Leitura ──────────────────────────────────────────────────────

    async def get_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await self._find(match_id)
        except Exception as e:
            logger.error(f"Erro ao buscar partida {match_id}: {e}")
            return None

    async def get_active_match_for_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        try:
            col = self._get_collection()
            return await col.find_one({
                "channel_id": str(channel_id),
                "status": {"$nin": [Match.STATUS_FINALIZADO, Match.STATUS_CANCELADO]}
            })
        except Exception as e:
            logger.error(f"Erro ao buscar partida ativa para canal {channel_id}: {e}")
            return None

    # ── Atualização de status ────────────────────────────────────────

    async def assign_thread(self, match_id: str, thread_id: int) -> Optional[Dict[str, Any]]:
        try:
            return await self._update(match_id, {"thread_id": str(thread_id)})
        except Exception as e:
            logger.error(f"Erro ao atribuir thread {thread_id} à partida {match_id}: {e}")
            return None

    async def assign_teams(
        self,
        match_id: str,
        time_blue: List[int],
        time_red: List[int],
    ) -> Optional[Dict[str, Any]]:
        try:
            return await self._update(match_id, {
                "time_blue": [str(uid) for uid in time_blue],
                "time_red":  [str(uid) for uid in time_red],
            })
        except Exception as e:
            logger.error(f"Erro ao atribuir times à partida {match_id}: {e}")
            return None

    async def start_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        try:
            match = await self._find(match_id)
            if not match:
                return None
            if match["status"] != Match.STATUS_AGUARDANDO_PARTIDA:
                return None
            return await self._update(match_id, {
                "status":     Match.STATUS_PARTIDA_INICIADA,
                "started_at": utcnow(),
            })
        except Exception as e:
            logger.error(f"Erro ao iniciar partida {match_id}: {e}")
            return None

    async def set_winner(
        self,
        match_id:  str,
        vencedor:  str,
        time_blue: List = None,
        time_red:  List = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            match = await self._find(match_id)
            if not match:
                return None
            if match["status"] != Match.STATUS_PARTIDA_INICIADA:
                return None

            fields = {
                "status":   Match.STATUS_AGUARDANDO_PREMIO,
                "vencedor": vencedor,
            }
            if vencedor == "blue" and time_blue:
                fields["winner_id"] = str(time_blue[0])
            elif vencedor == "red" and time_red:
                fields["winner_id"] = str(time_red[0])

            return await self._update(match_id, fields)
        except Exception as e:
            logger.error(f"Erro ao definir vencedor da partida {match_id}: {e}")
            return None

    async def confirm_prize_received(self, match_id: str) -> Optional[Dict[str, Any]]:
        try:
            match = await self._find(match_id)
            if not match:
                return None
            if match["status"] not in (
                Match.STATUS_AGUARDANDO_PREMIO,
                Match.STATUS_AGUARDANDO_PARTIDA,
                Match.STATUS_PARTIDA_INICIADA,
            ):
                return None

            # Salva snapshot e obtém o total para creditar ao mediador
            snap = await self._snapshot_commission(match_id, match)

            result = await self._update(match_id, {
                "status":                    Match.STATUS_FINALIZADO,
                "premio_confirmado_jogador": True,
                "completed_at":              utcnow(),
            })
            if result:
                await self._post_history(result, "finalizado")
                # Credita comissão no saldo do mediador
                await self._credit_mediator_commission(result, snap["total"])
            return result
        except Exception as e:
            logger.error(f"Erro ao confirmar prêmio da partida {match_id}: {e}")
            return None

    async def cancel_match(
        self,
        match_id:     str,
        cancelled_by: int = 0,
        reason:       str = "Cancelado",
    ) -> Optional[Dict[str, Any]]:
        try:
            match = await self._find(match_id)
            if not match:
                return None
            if match["status"] in (Match.STATUS_FINALIZADO, Match.STATUS_CANCELADO):
                return None

            # Snapshot (taxa = 0 em partidas canceladas — sem crédito)
            await self._snapshot_commission(match_id, match)

            result = await self._update(match_id, {
                "status":        Match.STATUS_CANCELADO,
                "cancelled_by":  str(cancelled_by),
                "cancel_reason": reason,
                "cancelled_at":  utcnow(),
            })
            if result:
                await self._post_history(result, "cancelado")
            # Partidas canceladas NÃO creditam comissão ao mediador
            return result
        except Exception as e:
            logger.error(f"Erro ao cancelar partida {match_id}: {e}")
            return None

    async def force_finish_match(
        self,
        match_id:  str,
        vencedor:  str,
        forced_by: int,
    ) -> Optional[Dict[str, Any]]:
        try:
            match = await self._find(match_id)
            if not match:
                return None

            # Salva snapshot e obtém o total para creditar ao mediador
            snap = await self._snapshot_commission(match_id, match)

            result = await self._update(match_id, {
                "status":                    Match.STATUS_FINALIZADO,
                "vencedor":                  vencedor,
                "premio_confirmado_jogador": True,
                "completed_at":              utcnow(),
                "forced_by":                 str(forced_by),
            })
            if result:
                await self._post_history(result, "forcado")
                # Credita comissão no saldo do mediador
                await self._credit_mediator_commission(result, snap["total"])
            return result
        except Exception as e:
            logger.error(f"Erro ao forçar finalização da partida {match_id}: {e}")
            return None

    # ── Live match finalization ──────────────────────────────────────

    async def finish_live_match(
        self,
        match_id: str,
        vencedor: str,
    ) -> Optional[Dict[str, Any]]:
        """Finaliza uma partida do modo live e credita comissão ao mediador."""
        try:
            match = await self._find(match_id)
            if not match:
                return None

            bet_value = float(match.get("bet_value", 0) or 0)
            guild_id  = str(match.get("guild_id", ""))

            try:
                live_scheme  = await commission_service.get_live_config(guild_id) if guild_id else {}
                commission_total = commission_service.calculate(bet_value, live_scheme)
            except Exception as e:
                logger.warning(f"[MatchService] finish_live_match commission fallback: {e}")
                commission_total = commission_service.calculate(bet_value, {})

            result = await self._update(match_id, {
                "status":           Match.STATUS_FINALIZADO,
                "vencedor":         vencedor,
                "completed_at":     utcnow(),
                "commission_total": round(commission_total, 2),
            })
            if result:
                await self._credit_mediator_commission(result, commission_total)
            return result
        except Exception as e:
            logger.error(f"Erro ao finalizar partida live {match_id}: {e}")
            return None

    async def register_payment_confirmation(self, match_id: str) -> Optional[Dict[str, Any]]:
        """Registra confirmação de pagamento do desafiante no modo live."""
        try:
            return await self._update(match_id, {
                "payment_confirmed": True,
                "payment_confirmed_at": utcnow(),
            })
        except Exception as e:
            logger.error(f"Erro ao registrar confirmação de pagamento {match_id}: {e}")
            return None


match_service = MatchService()
