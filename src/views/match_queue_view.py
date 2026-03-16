# views/match_queue_view.py

import discord
from typing import Optional
from services.match_queue_service import match_queue_service
from models.queue import MatchQueue
from models.match import Match
from config.database import db
from config.channels_config import ChannelsConfig
from utils.logger import logger


def is_1x1_mob(channel_name: str) -> bool:
    return channel_name == "1x1-mob"


# ─────────────────────────────────────────────
# Opção C — verifica partida ativa do jogador
# ─────────────────────────────────────────────

async def _player_has_active_match(player_id: int) -> bool:
    """Retorna True se o jogador já está em uma partida ativa."""
    try:
        col    = db.get_collection('matches')
        active = await col.find_one({
            'player_ids': str(player_id),
            'status':     {'$in': Match.ACTIVE_STATUSES}
        })
        return active is not None
    except Exception as e:
        logger.warning(f"[Queue] Erro ao checar partida ativa: {e}")
        return False


# ─────────────────────────────────────────────
# View do card
# ─────────────────────────────────────────────

class MatchQueueView(discord.ui.View):
    """
    Card de fila.
    - 1x1-mob : GEL NORMAL + GEL INFINITO + SAIR
    - Demais  : ENTRAR NA FILA + SAIR

    locked_gel: "normal" | "infinito" | "all" | None
      → desabilita botões do gel em confirmação (Opção A)
    """

    def __init__(
        self,
        channel_name: str,
        bet_value:    float,
        max_players:  int  = 2,
        locked_gel:   str  = None,   # ← Opção A
    ):
        super().__init__(timeout=None)
        self.channel_name = channel_name
        self.bet_value    = bet_value
        self.max_players  = 2
        self.locked_gel   = locked_gel

        def _is_locked(gel: str) -> bool:
            if locked_gel is None:
                return False
            return locked_gel in (gel, "all")

        if is_1x1_mob(channel_name):
            btn_normal = discord.ui.Button(
                label     = "⏳ AGUARDANDO..." if _is_locked("normal") else "🔥 GEL NORMAL",
                style     = discord.ButtonStyle.grey if _is_locked("normal") else discord.ButtonStyle.green,
                custom_id = f"gel_normal_{channel_name}_{bet_value}",
                disabled  = _is_locked("normal"),
            )
            btn_normal.callback = self._join_normal

            btn_inf = discord.ui.Button(
                label     = "⏳ AGUARDANDO..." if _is_locked("infinito") else "♾️ GEL INFINITO",
                style     = discord.ButtonStyle.grey if _is_locked("infinito") else discord.ButtonStyle.blurple,
                custom_id = f"gel_infinito_{channel_name}_{bet_value}",
                disabled  = _is_locked("infinito"),
            )
            btn_inf.callback = self._join_infinito

            btn_sair = discord.ui.Button(
                label     = "🚪 SAIR DA FILA",
                style     = discord.ButtonStyle.red,
                custom_id = f"sair_fila_{channel_name}_{bet_value}",
            )
            btn_sair.callback = self._leave_queue

            self.add_item(btn_normal)
            self.add_item(btn_inf)
            self.add_item(btn_sair)

        else:
            locked_all = _is_locked("normal")
            btn_entrar = discord.ui.Button(
                label     = "⏳ CONFIRMAÇÃO EM ANDAMENTO..." if locked_all else "⚔️ ENTRAR NA FILA",
                style     = discord.ButtonStyle.grey if locked_all else discord.ButtonStyle.green,
                custom_id = f"entrar_fila_{channel_name}_{bet_value}",
                disabled  = locked_all,
            )
            btn_entrar.callback = self._join_normal

            btn_sair = discord.ui.Button(
                label     = "🚪 SAIR DA FILA",
                style     = discord.ButtonStyle.red,
                custom_id = f"sair_fila_{channel_name}_{bet_value}",
            )
            btn_sair.callback = self._leave_queue

            self.add_item(btn_entrar)
            self.add_item(btn_sair)

    # ── Callbacks ─────────────────────────────────────────────

    async def _join_normal(self, interaction: discord.Interaction):
        await self._handle_join(interaction, "normal")

    async def _join_infinito(self, interaction: discord.Interaction):
        await self._handle_join(interaction, "infinito")

    async def _handle_join(self, interaction: discord.Interaction, gel_type: str):
        try:
            # ── Opção C: jogador já tem partida ativa ─────────
            if await _player_has_active_match(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Você já está em uma **partida ativa**!\n"
                    "Finalize-a antes de entrar em uma nova fila.",
                    ephemeral=True
                )
                return

            # ── Opção A: confirmação em andamento nesta fila ──
            current_q = await match_queue_service.get_queue_status(
                self.channel_name, self.bet_value, gel_type
            )
            if current_q and current_q.status == MatchQueue.STATUS_CONFIRMING:
                await interaction.response.send_message(
                    "⏳ Uma **confirmação está em andamento** para este valor e gel.\n"
                    "Aguarde ela terminar para entrar na próxima fila.",
                    ephemeral=True
                )
                return

            # ── Bloqueia dois géis ao mesmo tempo (1x1-mob) ───
            if is_1x1_mob(self.channel_name):
                other_gel   = "infinito" if gel_type == "normal" else "normal"
                other_queue = await match_queue_service.get_queue_status(
                    self.channel_name, self.bet_value, other_gel
                )
                if other_queue and interaction.user.id in other_queue.players:
                    await interaction.response.send_message(
                        f"⚠️ Você já está na fila de **GEL {other_gel.upper()}**. Saia dela primeiro.",
                        ephemeral=True
                    )
                    return

            # ── Entra na fila ─────────────────────────────────
            success, queue, message = await match_queue_service.add_player_to_queue(
                channel_name = self.channel_name,
                bet_value    = self.bet_value,
                gel_type     = gel_type,
                max_players  = 2,
                player_id    = interaction.user.id
            )

            if not success:
                await interaction.response.send_message(f"❌ {message}", ephemeral=True)
                return

            if message == "full":
                await interaction.response.send_message(
                    "⚡ Fila completa! Um tópico de confirmação foi criado.",
                    ephemeral=True
                )
                await match_queue_service.start_confirmation_timer(
                    queue   = queue,
                    bot     = interaction.client,
                    channel = interaction.channel
                )
            else:
                await interaction.response.send_message(f"✅ {message}", ephemeral=True)
                await self._refresh_card(interaction, gel_type)

        except Exception as e:
            logger.error(f"Erro ao entrar na fila: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Erro ao entrar na fila.", ephemeral=True)

    async def _leave_queue(self, interaction: discord.Interaction):
        try:
            gel_types = ["normal", "infinito"] if is_1x1_mob(self.channel_name) else ["normal"]
            removed   = False

            for gel in gel_types:
                ok, queue = await match_queue_service.remove_player_from_queue(
                    self.channel_name, self.bet_value, gel, interaction.user.id
                )
                if ok:
                    removed = True

            if removed:
                await interaction.response.send_message("✅ Você saiu da fila!", ephemeral=True)
                await self._refresh_card(interaction, "normal")
            else:
                await interaction.response.send_message(
                    "❌ Você não está em nenhuma fila deste valor.", ephemeral=True
                )
        except Exception as e:
            logger.error(f"Erro ao sair da fila: {e}")
            await interaction.response.send_message("❌ Erro ao sair da fila.", ephemeral=True)

    # ── Refresh do card ───────────────────────────────────────

    async def _refresh_card(self, interaction: discord.Interaction, gel_type: str):
        try:
            q_normal   = await match_queue_service.get_queue_status(self.channel_name, self.bet_value, "normal")
            q_infinito = await match_queue_service.get_queue_status(self.channel_name, self.bet_value, "infinito")

            normal_count   = len(q_normal.players)   if q_normal   else 0
            infinito_count = len(q_infinito.players) if q_infinito else 0

            # Confirma se algum gel está em confirmação (para manter lock visual)
            locked_gel = None
            if q_normal and q_normal.status == MatchQueue.STATUS_CONFIRMING:
                locked_gel = "normal"
            if q_infinito and q_infinito.status == MatchQueue.STATUS_CONFIRMING:
                locked_gel = "infinito" if locked_gel is None else "all"

            embed = create_match_queue_embed(
                channel_name       = self.channel_name,
                bet_value          = self.bet_value,
                queue_normal_count = normal_count,
                queue_infinito_count = infinito_count,
                locked_gel         = locked_gel,
            )
            view = MatchQueueView(
                channel_name = self.channel_name,
                bet_value    = self.bet_value,
                locked_gel   = locked_gel,
            )
            try:
                await interaction.message.edit(embed=embed, view=view)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Erro ao atualizar card: {e}")


# ─────────────────────────────────────────────
# Embed do card
# ─────────────────────────────────────────────

def create_match_queue_embed(
    channel_name:         str,
    bet_value:            float,
    queue_normal_count:   int = 0,
    queue_infinito_count: int = 0,
    locked_gel:           str = None,   # ← Opção A: "normal" | "infinito" | "all" | None
) -> discord.Embed:

    display = (
        channel_name.upper()
        .replace("-MOB",   " Mobile")
        .replace("-EMU",   " Emulador")
        .replace("-MISTO", " Misto")
    )

    def bar(n: int) -> str:
        return "🟩" * n + "⬜" * (2 - n)

    def _is_locked(gel: str) -> bool:
        return locked_gel in (gel, "all") if locked_gel else False

    color = discord.Color.orange() if locked_gel else discord.Color.gold()

    embed = discord.Embed(
        title       = f"💰 R$ {bet_value:.2f}",
        description = f"**Modo:** {display}",
        color       = color
    )

    if is_1x1_mob(channel_name):
        # GEL NORMAL
        if _is_locked("normal"):
            embed.add_field(
                name  = "🔥 GEL NORMAL",
                value = f"⏳ **Confirmação em andamento...**\n{bar(queue_normal_count)}",
                inline=True
            )
        else:
            embed.add_field(
                name  = "🔥 GEL NORMAL",
                value = f"Na fila: **{queue_normal_count}/2**\n{bar(queue_normal_count)}",
                inline=True
            )

        # GEL INFINITO
        if _is_locked("infinito"):
            embed.add_field(
                name  = "♾️ GEL INFINITO",
                value = f"⏳ **Confirmação em andamento...**\n{bar(queue_infinito_count)}",
                inline=True
            )
        else:
            embed.add_field(
                name  = "♾️ GEL INFINITO",
                value = f"Na fila: **{queue_infinito_count}/2**\n{bar(queue_infinito_count)}",
                inline=True
            )
    else:
        if _is_locked("normal"):
            embed.add_field(
                name  = "⚔️ FILA",
                value = f"⏳ **Confirmação em andamento...**\n{bar(queue_normal_count)}",
                inline=True
            )
        else:
            embed.add_field(
                name  = "⚔️ FILA",
                value = f"Na fila: **{queue_normal_count}/2**\n{bar(queue_normal_count)}",
                inline=True
            )

    footer = "⏳ Aguardando confirmação dos jogadores..." if locked_gel else "Clique para entrar na fila"
    embed.set_footer(text=footer)
    return embed
