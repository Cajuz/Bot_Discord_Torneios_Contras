# views/match_thread_view.py

from __future__ import annotations
import asyncio
import discord
from utils.datetime_utils import utcnow
from typing import Optional, List
from config.database import db
from models.match import Match
from services.match_service import match_service
from utils.logger import logger


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

async def _get_match_by_thread(thread_id: int) -> Optional[dict]:
    col = db.get_collection("matches")
    doc = await col.find_one({"thread_id": thread_id})
    if not doc:
        doc = await col.find_one({"thread_id": str(thread_id)})
    return doc


def _is_mediator(ctx_or_interaction, match: dict) -> bool:
    user_id = (
        ctx_or_interaction.user.id
        if isinstance(ctx_or_interaction, discord.Interaction)
        else ctx_or_interaction.author.id
    )
    return str(user_id) == str(match.get("mediator_id", ""))


def _is_admin(ctx_or_interaction) -> bool:
    member = (
        ctx_or_interaction.user
        if isinstance(ctx_or_interaction, discord.Interaction)
        else ctx_or_interaction.author
    )
    return getattr(getattr(member, "guild_permissions", None), "administrator", False)


async def _update_thread_name(thread: discord.Thread, base_name: str, status: str):
    try:
        await thread.edit(name=f"{base_name}: {status}")
    except Exception as e:
        logger.error(f"Erro ao renomear thread: {e}")


def _base_name(thread_name: str) -> str:
    return thread_name.rsplit(": ", 1)[0] if ": " in thread_name else thread_name


def _calc_values(bet_value: float) -> dict:
    taxa             = bet_value * 0.25
    total_por_jogador = bet_value + taxa
    premio           = bet_value * 2
    return {
        "bet":              bet_value,
        "taxa":             taxa,
        "total_por_jogador": total_por_jogador,
        "premio":           premio,
    }


async def _post_log(
    channel: discord.TextChannel,
    title: str,
    description: str,
    color: discord.Color = discord.Color.blurple()
):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=f"Log de partida • {utcnow().strftime('%H:%M')}")
    await channel.send(embed=embed)


def _try_return_to_pool(channel):
    """Dispara return_to_pool_after_match de forma segura, sem bloquear."""
    try:
        from services.thread_reuse_service import thread_reuse_service
        if thread_reuse_service and isinstance(channel, discord.Thread):
            asyncio.create_task(
                thread_reuse_service.return_to_pool_after_match(channel)
            )
        else:
            logger.warning(
                f"[ThreadPool] thread_reuse_service indisponível "
                f"para thread {getattr(channel, 'id', '?')}"
            )
    except Exception as e:
        logger.warning(f"[ThreadPool] Erro ao devolver thread ao pool: {e}")


# ─────────────────────────────────────────────
# Embeds públicos
# ─────────────────────────────────────────────

def embed_match_created(match: dict) -> discord.Embed:
    vals      = _calc_values(match["bet_value"])
    time_blue = match.get("time_blue", [])
    time_red  = match.get("time_red",  [])
    gel       = match.get("gel_type",  "normal").capitalize()
    modo      = match.get("match_type","?").upper()

    blue_str = "\n".join(f"• <@{uid}>" for uid in time_blue) or "—"
    red_str  = "\n".join(f"• <@{uid}>" for uid in time_red)  or "—"

    embed = discord.Embed(
        title="⚔️ Partida Criada!",
        description=(
            f"**Modo:** {modo} | **GEL:** {gel}\n"
            f"**Mediador:** <@{match['mediator_id']}>"
        ),
        color=discord.Color.gold()
    )
    embed.add_field(name="🔵 Time Blue", value=blue_str, inline=True)
    embed.add_field(name="🔴 Time Red",  value=red_str,  inline=True)
    embed.add_field(name="\u200b",       value="\u200b", inline=False)
    embed.add_field(
        name="💰 Valores",
        value=(
            f"**Cada jogador paga ao mediador:** R$ {vals['total_por_jogador']:.2f}\n"
            f"*(R$ {vals['bet']:.2f} da fila + R$ {vals['taxa']:.2f} de taxa)*\n\n"
            f"**Mediador paga ao vencedor:** R$ {vals['premio']:.2f}"
        ),
        inline=False
    )
    embed.add_field(
        name="⚠️ REGRAS DE PAGAMENTO",
        value=(
            "✅ Pagamentos **somente via PIX**\n"
            "🚫 **PROIBIDO usar:** Inter, Neon, PagBank"
        ),
        inline=False
    )
    embed.set_footer(text="Mediador: use !menu_partida para ver o painel de controle.")
    return embed


def embed_prize_instructions(match: dict) -> discord.Embed:
    vals     = _calc_values(match["bet_value"])
    vencedor = match.get("vencedor", "blue")
    label    = "🔵 Time Blue" if vencedor == "blue" else "🔴 Time Red"
    ids      = match.get("time_blue" if vencedor == "blue" else "time_red", [])
    winners  = "\n".join(f"• <@{uid}>" for uid in ids) or "—"

    embed = discord.Embed(
        title="🏆 Partida Finalizada — Instruções do Prêmio",
        description=f"**Vencedor:** {label}\n{winners}",
        color=discord.Color.green()
    )
    embed.add_field(
        name="💰 Pagamento do Prêmio",
        value=(
            f"O **mediador** deve pagar **R$ {vals['premio']:.2f}** via PIX ao(s) vencedor(es).\n\n"
            f"Após enviar, use `!prize` no tópico."
        ),
        inline=False
    )
    embed.add_field(
        name="⚠️ ATENÇÃO — REGRAS DE PAGAMENTO",
        value=(
            "✅ Pagamentos **somente via PIX**\n"
            "🚫 **PROIBIDO usar:** Inter, Neon, PagBank"
        ),
        inline=False
    )
    return embed


# ─────────────────────────────────────────────
# PrizeConfirmView
# ─────────────────────────────────────────────

class PrizeConfirmView(discord.ui.View):
    def __init__(self, match_id: str, winner_players: List, winner_team: str):
        super().__init__(timeout=None)
        self.match_id       = match_id
        self.winner_players = [str(p) for p in winner_players]
        self.winner_team    = winner_team

        btn = discord.ui.Button(
            label="✅ Confirmar Recebimento do Prêmio",
            style=discord.ButtonStyle.success,
            custom_id=f"prize_confirm_{match_id}"
        )
        btn.callback = self.confirm_prize
        self.add_item(btn)

    async def confirm_prize(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        if user_id not in self.winner_players:
            await interaction.response.send_message(
                "❌ Apenas os jogadores vencedores podem confirmar.",
                ephemeral=True
            )
            return

        match_doc = await match_service.get_match(self.match_id)
        if not match_doc:
            await interaction.response.send_message(
                "❌ Partida não encontrada.", ephemeral=True)
            return

        already_done = match_doc.get("status") == Match.STATUS_FINALIZADO

        if not already_done:
            result = await match_service.confirm_prize_received(self.match_id)
            if not result:
                await interaction.response.send_message(
                    "❌ Erro ao finalizar partida.", ephemeral=True)
                return

        # Desabilita botão
        for item in self.children:
            item.disabled = True
            item.label    = "✅ Prêmio Confirmado"
        await interaction.response.edit_message(view=self)

        if not already_done:
            if isinstance(interaction.channel, discord.Thread):
                await _update_thread_name(
                    interaction.channel,
                    _base_name(interaction.channel.name),
                    "Finalizado ✅"
                )
            embed = discord.Embed(
                title="✅ Partida Encerrada!",
                description="🎉 Prêmio confirmado pelos vencedores! Obrigado a todos.",
                color=discord.Color.green()
            )
            await interaction.channel.send(embed=embed)

        # ✅ SEMPRE devolve ao pool — independente do caminho
        _try_return_to_pool(interaction.channel)


# ─────────────────────────────────────────────
# Comandos de texto — mediador e ADM
# ─────────────────────────────────────────────

async def cmd_menu_partida(ctx):
    """!menu_partida — envia painel informativo via DM ao mediador."""
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.message.delete()
        return

    match = await _get_match_by_thread(ctx.channel.id)
    if not match:
        try:
            await ctx.author.send("❌ Nenhuma partida encontrada neste tópico.")
        except discord.Forbidden:
            pass
        await ctx.message.delete()
        return

    if not _is_mediator(ctx, match) and not _is_admin(ctx):
        await ctx.message.delete()
        return

    vals   = _calc_values(match["bet_value"])
    status = match.get("status", "?")

    embed = discord.Embed(
        title="🎮 Painel do Mediador",
        description=(
            f"**Status atual:** `{status}`\n\n"
            "**Comandos disponíveis na thread:**\n"
            "`!confirmar_pagamento` — confirma recebimento dos pagamentos\n"
            "`!winner_team blue` ou `!winner_team red` — declara o vencedor\n"
            "`!prize` — confirma entrega do prêmio\n"
            "`!cancelar_match` — cancela a partida"
        ),
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="💰 Resumo Financeiro",
        value=(
            f"Cada jogador te paga: **R$ {vals['total_por_jogador']:.2f}**\n"
            f"*(R$ {vals['bet']:.2f} + R$ {vals['taxa']:.2f} de taxa)*\n\n"
            f"Você paga ao vencedor: **R$ {vals['premio']:.2f}**"
        ),
        inline=False
    )
    embed.add_field(
        name="⚠️ Lembrete",
        value="🚫 **PROIBIDO:** Inter, Neon, PagBank\n✅ Apenas PIX",
        inline=False
    )
    embed.set_footer(text="Esta mensagem foi enviada apenas para você via DM.")

    try:
        await ctx.author.send(embed=embed)
    except discord.Forbidden:
        await ctx.channel.send(embed=embed, delete_after=15)

    await ctx.message.delete()


async def cmd_confirmar_pagamento(ctx):
    """!confirmar_pagamento — mediador confirma recebimento dos pagamentos."""
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.message.delete()
        return

    match = await _get_match_by_thread(ctx.channel.id)
    if not match:
        await ctx.message.delete()
        return

    if not _is_mediator(ctx, match):
        await ctx.message.delete()
        return

    if match.get("pagamento_confirmado"):
        try:
            await ctx.author.send("✅ Pagamento já confirmado anteriormente.")
        except discord.Forbidden:
            pass
        await ctx.message.delete()
        return

    result = await match_service.confirm_payment(str(match["_id"]))
    if not result:
        try:
            await ctx.author.send(
                f"❌ Transição inválida. Status atual: `{match.get('status')}`")
        except discord.Forbidden:
            pass
        await ctx.message.delete()
        return

    await _update_thread_name(
        ctx.channel, _base_name(ctx.channel.name), "Pagamento Confirmado")
    await ctx.message.delete()
    await _post_log(
        ctx.channel,
        "✅ Pagamento Confirmado",
        f"<@{match['mediator_id']}> confirmou o recebimento dos pagamentos.\n"
        "A partida pode ser iniciada!",
        discord.Color.green()
    )


async def cmd_iniciar_partida(ctx):
    """!iniciar_partida — mediador inicia a partida."""
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.message.delete()
        return

    match = await _get_match_by_thread(ctx.channel.id)
    if not match:
        await ctx.message.delete()
        return

    if not _is_mediator(ctx, match):
        await ctx.message.delete()
        return

    if not match.get("pagamento_confirmado"):
        try:
            await ctx.author.send(
                "❌ Confirme o pagamento primeiro com `!confirmar_pagamento`.")
        except discord.Forbidden:
            pass
        await ctx.message.delete()
        return

    result = await match_service.start_match(str(match["_id"]))
    if not result:
        try:
            await ctx.author.send(
                f"❌ Transição inválida. Status atual: `{match.get('status')}`")
        except discord.Forbidden:
            pass
        await ctx.message.delete()
        return

    await _update_thread_name(
        ctx.channel, _base_name(ctx.channel.name), "Em Andamento ▶️")
    await ctx.message.delete()
    await _post_log(
        ctx.channel,
        "▶️ Partida Iniciada!",
        "A partida começou! Boa sorte a todos! 🎮\n\n"
        "Ao finalizar use `!winner_team blue` ou `!winner_team red`.",
        discord.Color.blue()
    )


async def cmd_winner_team(ctx, team: str):
    """!winner_team blue|red — mediador declara o vencedor."""
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.message.delete()
        return

    team = team.lower().strip()
    if team not in ("blue", "red"):
        try:
            await ctx.author.send(
                "❌ Use: `!winner_team blue` ou `!winner_team red`")
        except discord.Forbidden:
            pass
        await ctx.message.delete()
        return

    match = await _get_match_by_thread(ctx.channel.id)
    if not match:
        await ctx.message.delete()
        return

    if not _is_mediator(ctx, match):
        await ctx.message.delete()
        return

    time_blue = match.get("time_blue", [])
    time_red  = match.get("time_red",  [])

    result = await match_service.set_winner(
        match_id=str(match["_id"]),
        vencedor=team,
        time_blue=time_blue,
        time_red=time_red,
    )
    if not result:
        try:
            await ctx.author.send(
                f"❌ Transição inválida. Status atual: `{match.get('status')}`")
        except discord.Forbidden:
            pass
        await ctx.message.delete()
        return

    label    = "🔵 Time Blue" if team == "blue" else "🔴 Time Red"
    win_ids  = time_blue if team == "blue" else time_red
    mentions = " ".join(f"<@{uid}>" for uid in win_ids)

    await _update_thread_name(
        ctx.channel, _base_name(ctx.channel.name), f"Vencedor: {label}")
    await ctx.message.delete()

    embed_log = discord.Embed(
        title="🏆 Time Vencedor Declarado!",
        description=f"**{label}** venceu a partida!\n\n{mentions}",
        color=discord.Color.gold()
    )
    embed_log.add_field(
        name="Vencedor(es)",
        value="\n".join(f"• <@{uid}>" for uid in win_ids) or "—",
        inline=False
    )
    await ctx.channel.send(embed=embed_log)
    await ctx.channel.send(embed=embed_prize_instructions({**match, "vencedor": team}))


async def cmd_prize(ctx):
    """!prize — mediador confirma que entregou o prêmio."""
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.message.delete()
        return

    match = await _get_match_by_thread(ctx.channel.id)
    if not match:
        await ctx.message.delete()
        return

    if not _is_mediator(ctx, match):
        await ctx.message.delete()
        return

    if match.get("status") != Match.STATUS_AGUARDANDO_PREMIO:
        try:
            await ctx.author.send(
                f"❌ Use `!winner_team` primeiro. Status: `{match.get('status')}`")
        except discord.Forbidden:
            pass
        await ctx.message.delete()
        return

    if match.get("premio_entregue_mediador"):
        try:
            await ctx.author.send("✅ Prêmio já marcado como entregue.")
        except discord.Forbidden:
            pass
        await ctx.message.delete()
        return

    result = await match_service.confirm_prize_delivery(str(match["_id"]))
    if not result:
        await ctx.message.delete()
        return

    vencedor = match.get("vencedor", "blue")
    win_ids  = match.get("time_blue" if vencedor == "blue" else "time_red", [])
    label    = "🔵 Time Blue" if vencedor == "blue" else "🔴 Time Red"
    vals     = _calc_values(match["bet_value"])
    mentions = " ".join(f"<@{uid}>" for uid in win_ids)

    await ctx.message.delete()

    embed_pub = discord.Embed(
        title="🎁 Prêmio Enviado!",
        description=(
            f"O mediador <@{match['mediator_id']}> confirmou o envio!\n\n"
            f"**{label}** — R$ {vals['premio']:.2f} via PIX\n\n"
            f"{mentions}\n\n"
            "**Confirme o recebimento** clicando no botão abaixo."
        ),
        color=discord.Color.green()
    )
    embed_pub.add_field(
        name="⚠️ ATENÇÃO",
        value="🚫 **PROIBIDO:** Inter, Neon, PagBank\n✅ Apenas PIX",
        inline=False
    )

    prize_view = PrizeConfirmView(
        match_id=str(match["_id"]),
        winner_players=win_ids,
        winner_team=vencedor
    )
    await ctx.channel.send(content=mentions, embed=embed_pub, view=prize_view)


async def cmd_cancelar_match(ctx, reason: str = None):
    """!cancelar_match [motivo] — mediador ou ADM cancela a partida."""
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.message.delete()
        return

    match = await _get_match_by_thread(ctx.channel.id)
    if not match:
        await ctx.message.delete()
        return

    if not _is_mediator(ctx, match) and not _is_admin(ctx):
        await ctx.message.delete()
        return

    match_obj = Match(match)
    if match_obj.is_finished():
        try:
            await ctx.author.send(
                f"❌ Partida já finalizada/cancelada. Status: `{match.get('status')}`")
        except discord.Forbidden:
            pass
        await ctx.message.delete()
        return

    result = await match_service.cancel_match(
        match_id=str(match["_id"]),
        cancelled_by=ctx.author.id,
        reason=reason or "Cancelado pelo mediador/admin"
    )
    if not result:
        await ctx.message.delete()
        return

    await _update_thread_name(
        ctx.channel, _base_name(ctx.channel.name), "Cancelado ❌")
    await ctx.message.delete()
    await _post_log(
        ctx.channel,
        "❌ Partida Cancelada",
        f"Cancelada por <@{ctx.author.id}>."
        + (f"\n**Motivo:** {reason}" if reason else ""),
        discord.Color.red()
    )

    # ✅ Devolve thread ao pool após cancelamento
    _try_return_to_pool(ctx.channel)


# ─────────────────────────────────────────────
# View persistente para registro no on_ready
# ─────────────────────────────────────────────

class MatchThreadView(discord.ui.View):
    """Stub persistente — registrada no on_ready para sobreviver a reinicializações."""
    def __init__(self, match_id: str = "__persistent__"):
        super().__init__(timeout=None)
        self.match_id = match_id
