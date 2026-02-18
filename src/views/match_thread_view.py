from __future__ import annotations
import discord
from datetime import datetime
from typing import Optional, List
from config.database import db
from utils.logger import logger


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

async def _get_match_by_thread(thread_id: int) -> Optional[dict]:
    return await db.get_collection("matches").find_one({"thread_id": thread_id})


async def _update_match(match_id: str, fields: dict):
    from bson import ObjectId
    await db.get_collection("matches").update_one(
        {"_id": ObjectId(match_id)},
        {"$set": {**fields, "updated_at": datetime.utcnow()}}
    )


async def _update_thread_name(thread: discord.Thread, base_name: str, status: str):
    try:
        await thread.edit(name=f"{base_name}: {status}")
    except Exception as e:
        logger.error(f"Erro ao renomear thread: {e}")


def _base_name(thread_name: str) -> str:
    return thread_name.rsplit(": ", 1)[0] if ": " in thread_name else thread_name


def _calc_values(bet_value: float) -> dict:
    taxa               = bet_value * 0.25
    total_por_jogador  = bet_value + taxa
    premio             = bet_value * 2
    return {
        "bet": bet_value,
        "taxa": taxa,
        "total_por_jogador": total_por_jogador,
        "premio": premio
    }


# ─────────────────────────────────────────────
# Embeds públicos
# ─────────────────────────────────────────────

def embed_match_created(match: dict) -> discord.Embed:
    vals      = _calc_values(match["bet_value"])
    time_blue = match.get("time_blue", [])
    time_red  = match.get("time_red", [])
    gel       = match.get("gel_type", "normal").capitalize()
    modo      = match.get("match_type", "?").upper()

    blue_str = "\n".join(f"• <@{uid}>" for uid in time_blue) or "—"
    red_str  = "\n".join(f"• <@{uid}>" for uid in time_red)  or "—"

    embed = discord.Embed(
        title="⚔️ Partida Criada!",
        description=(
            f"**Modo:** {modo}\n"
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
            "🚫 **PROIBIDO usar:** Inter, Neon, PagBank\n"
        ),
        inline=False
    )
    embed.set_footer(text="Mediador: use !menu_partida para controlar o fluxo.")
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
            f"Após enviar, use `!prize` ou clique em **Entregar Prêmio** no menu."
        ),
        inline=False
    )
    embed.add_field(
        name="⚠️ ATENÇÃO — REGRAS DE PAGAMENTO",
        value=(
            "✅ Pagamentos **somente via PIX**\n"
            "🚫 **PROIBIDO usar:** Inter, Neon, PagBank\n"
        ),
        inline=False
    )
    return embed


# ─────────────────────────────────────────────
# View de controle — ephemeral, só mediador vê
# ─────────────────────────────────────────────

class MediatorMenuView(discord.ui.View):
    """
    Card de controle enviado via !menu_partida — ephemeral.
    Botões controlam o fluxo completo da partida.
    """

    def __init__(self, match: dict):
        super().__init__(timeout=120)
        self.match      = match
        self.match_id   = str(match["_id"])
        self.mediator_id = match["mediator_id"]
        self._refresh_buttons()

    def _refresh_buttons(self):
        """Habilita/desabilita botões com base no status atual"""
        status = self.match.get("status", "")
        pago   = self.match.get("pagamento_confirmado", False)

        for child in self.children:
            cid = getattr(child, "custom_id", "")
            if cid == "menu_confirmar_pag":
                child.disabled = pago or status not in ("aguardando_pagamento", "aguardando_inicio")
                child.label    = "✅ Pagamento Confirmado" if pago else "✅ Confirmar Pagamento"
            elif cid == "menu_iniciar":
                child.disabled = not pago or status != "aguardando_inicio"
            elif cid == "menu_winner_blue":
                child.disabled = status != "em_andamento"
            elif cid == "menu_winner_red":
                child.disabled = status != "em_andamento"
            elif cid == "menu_prize":
                child.disabled = status != "aguardando_premio" or self.match.get("premio_entregue_mediador", False)
            elif cid == "menu_cancelar":
                child.disabled = status in ("finalizado", "cancelado")

    async def _only_mediator(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.mediator_id:
            await interaction.response.send_message(
                "❌ Apenas o mediador desta partida pode usar este menu.",
                ephemeral=True
            )
            return False
        return True

    async def _reload_match(self):
        from bson import ObjectId
        self.match = await db.get_collection("matches").find_one({"_id": ObjectId(self.match_id)})

    # ── Confirmar Pagamento ──────────────────────────────────────
    @discord.ui.button(
        label="✅ Confirmar Pagamento",
        style=discord.ButtonStyle.green,
        custom_id="menu_confirmar_pag",
        row=0
    )
    async def confirmar_pagamento(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._only_mediator(interaction):
            return

        await _update_match(self.match_id, {
            "pagamento_confirmado": True,
            "status": "aguardando_inicio"
        })

        if isinstance(interaction.channel, discord.Thread):
            await _update_thread_name(
                interaction.channel,
                _base_name(interaction.channel.name),
                "Pagamento Confirmado"
            )

        embed_pub = discord.Embed(
            title="✅ Pagamento Confirmado!",
            description=f"O mediador <@{self.mediator_id}> confirmou o recebimento dos pagamentos.\n\nA partida pode ser iniciada!",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=embed_pub)

        await self._reload_match()
        self._refresh_buttons()
        await interaction.response.edit_message(view=self)

    # ── Iniciar Partida ──────────────────────────────────────────
    @discord.ui.button(
        label="▶️ Iniciar Partida",
        style=discord.ButtonStyle.primary,
        custom_id="menu_iniciar",
        row=0,
        disabled=True
    )
    async def iniciar_partida(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._only_mediator(interaction):
            return

        await _update_match(self.match_id, {
            "status": "em_andamento",
            "started_at": datetime.utcnow()
        })

        if isinstance(interaction.channel, discord.Thread):
            await _update_thread_name(
                interaction.channel,
                _base_name(interaction.channel.name),
                "Em Andamento ▶️"
            )

        embed_pub = discord.Embed(
            title="▶️ Partida Iniciada!",
            description="A partida começou! Boa sorte a todos! 🎮\n\nAo finalizar use `!winner_team blue` ou `red`, ou clique nos botões abaixo.",
            color=discord.Color.blue()
        )
        await interaction.channel.send(embed=embed_pub)

        await self._reload_match()
        self._refresh_buttons()
        await interaction.response.edit_message(view=self)

    # ── Vencedor Blue ────────────────────────────────────────────
    @discord.ui.button(
        label="🔵 Blue Venceu",
        style=discord.ButtonStyle.primary,
        custom_id="menu_winner_blue",
        row=1,
        disabled=True
    )
    async def winner_blue(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._only_mediator(interaction):
            return
        await self._set_winner(interaction, "blue")

    # ── Vencedor Red ─────────────────────────────────────────────
    @discord.ui.button(
        label="🔴 Red Venceu",
        style=discord.ButtonStyle.danger,
        custom_id="menu_winner_red",
        row=1,
        disabled=True
    )
    async def winner_red(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._only_mediator(interaction):
            return
        await self._set_winner(interaction, "red")

    async def _set_winner(self, interaction: discord.Interaction, team: str):
        label     = "🔵 Time Blue" if team == "blue" else "🔴 Time Red"
        win_ids   = self.match.get("time_blue" if team == "blue" else "time_red", [])
        mentions  = " ".join(f"<@{uid}>" for uid in win_ids)

        await _update_match(self.match_id, {
            "status": "aguardando_premio",
            "vencedor": team
        })

        if isinstance(interaction.channel, discord.Thread):
            await _update_thread_name(
                interaction.channel,
                _base_name(interaction.channel.name),
                f"Vencedor: {label}"
            )

        embed_pub = discord.Embed(
            title="🏆 Time Vencedor Declarado!",
            description=f"**{label}** venceu a partida!\n\n{mentions}",
            color=discord.Color.gold()
        )
        embed_pub.add_field(
            name="Jogador(es) vencedor(es)",
            value="\n".join(f"• <@{uid}>" for uid in win_ids) or "—",
            inline=False
        )
        await interaction.channel.send(embed=embed_pub)
        await interaction.channel.send(
            embed=embed_prize_instructions({**self.match, "vencedor": team})
        )

        await self._reload_match()
        self._refresh_buttons()
        await interaction.response.edit_message(view=self)

    # ── Entregar Prêmio ──────────────────────────────────────────
    @discord.ui.button(
        label="🎁 Entregar Prêmio",
        style=discord.ButtonStyle.success,
        custom_id="menu_prize",
        row=2,
        disabled=True
    )
    async def entregar_premio(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._only_mediator(interaction):
            return

        vencedor = self.match.get("vencedor", "blue")
        win_ids  = self.match.get("time_blue" if vencedor == "blue" else "time_red", [])
        label    = "🔵 Time Blue" if vencedor == "blue" else "🔴 Time Red"
        vals     = _calc_values(self.match["bet_value"])
        mentions = " ".join(f"<@{uid}>" for uid in win_ids)

        await _update_match(self.match_id, {"premio_entregue_mediador": True})

        embed_pub = discord.Embed(
            title="🎁 Prêmio Entregue!",
            description=(
                f"O mediador <@{self.mediator_id}> confirmou o envio do prêmio!\n\n"
                f"**{label}** — R$ {vals['premio']:.2f} via PIX\n\n"
                f"{mentions}\n\n"
                "Por favor, **confirme o recebimento** clicando no botão abaixo."
            ),
            color=discord.Color.green()
        )
        embed_pub.add_field(
            name="⚠️ ATENÇÃO",
            value="🚫 **PROIBIDO:** Inter, Neon, PagBank\n✅ Apenas PIX",
            inline=False
        )

        prize_view = PrizeConfirmView(
            match_id=self.match_id,
            winner_players=win_ids,
            winner_team=vencedor
        )
        await interaction.channel.send(content=mentions, embed=embed_pub, view=prize_view)

        self._refresh_buttons()
        await interaction.response.edit_message(view=self)

    # ── Cancelar ─────────────────────────────────────────────────
    @discord.ui.button(
        label="❌ Cancelar Match",
        style=discord.ButtonStyle.danger,
        custom_id="menu_cancelar",
        row=2
    )
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._only_mediator(interaction):
            return

        await _update_match(self.match_id, {"status": "cancelado"})

        if isinstance(interaction.channel, discord.Thread):
            await _update_thread_name(
                interaction.channel,
                _base_name(interaction.channel.name),
                "Cancelado ❌"
            )

        embed_pub = discord.Embed(
            title="❌ Partida Cancelada",
            description=f"Partida cancelada por <@{interaction.user.id}>.",
            color=discord.Color.red()
        )
        await interaction.channel.send(embed=embed_pub)

        self._refresh_buttons()
        await interaction.response.edit_message(view=self)

        try:
            await interaction.channel.edit(archived=True)
        except Exception:
            pass


# ─────────────────────────────────────────────
# View de confirmação de prêmio (jogadores)
# ─────────────────────────────────────────────

class PrizeConfirmView(discord.ui.View):

    def __init__(self, match_id: str, winner_players: List[int], winner_team: str):
        super().__init__(timeout=None)
        self.match_id       = match_id
        self.winner_players = winner_players
        self.winner_team    = winner_team
        self.confirmed: set[int] = set()

    @discord.ui.button(
        label="✅ Confirmar Recebimento do Prêmio",
        style=discord.ButtonStyle.success,
        custom_id="prize_confirm"
    )
    async def confirm_prize(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.winner_players:
            await interaction.response.send_message(
                "❌ Apenas os jogadores vencedores podem confirmar.",
                ephemeral=True
            )
            return

        if interaction.user.id in self.confirmed:
            await interaction.response.send_message("✅ Você já confirmou!", ephemeral=True)
            return

        self.confirmed.add(interaction.user.id)

        if self.confirmed >= set(self.winner_players):
            await _update_match(self.match_id, {
                "premio_confirmado_jogador": True,
                "status": "finalizado"
            })

            button.disabled = True
            button.label    = "✅ Prêmio Confirmado"
            await interaction.response.edit_message(view=self)

            if isinstance(interaction.channel, discord.Thread):
                name = interaction.channel.name
                base = name.rsplit(": ", 1)[0] if ": " in name else name
                await _update_thread_name(interaction.channel, base, "Finalizado ✅")

                embed = discord.Embed(
                    title="✅ Partida Encerrada!",
                    description="🎉 Prêmio confirmado! Este tópico será arquivado.",
                    color=discord.Color.green()
                )
                await interaction.channel.send(embed=embed)

                try:
                    await interaction.channel.edit(archived=True)
                except Exception:
                    pass
        else:
            remaining = len(self.winner_players) - len(self.confirmed)
            await interaction.response.send_message(
                f"✅ Confirmado! Aguardando {remaining} confirmação(ões) restante(s).",
                ephemeral=True
            )


# ─────────────────────────────────────────────
# Funções dos comandos de texto (!winner_team, !prize, etc.)
# ─────────────────────────────────────────────

async def cmd_menu_partida(ctx):
    """!menu_partida — Abre card de controle ephemeral para o mediador"""
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.reply("❌ Use dentro de uma thread de partida.")
        return

    match = await _get_match_by_thread(ctx.channel.id)
    if not match:
        await ctx.reply("❌ Nenhuma partida encontrada neste tópico.")
        return

    if ctx.author.id != match["mediator_id"]:
        await ctx.reply("❌ Apenas o mediador pode abrir este menu.")
        return

    vals   = _calc_values(match["bet_value"])
    status = match.get("status", "?")

    embed = discord.Embed(
        title="🎮 Painel do Mediador",
        description=(
            f"**Status atual:** `{status}`\n\n"
            "Use os botões abaixo **ou** os comandos de texto:\n"
            "`!confirmar_pagamento` • `!iniciar_partida`\n"
            "`!winner_team blue/red` • `!prize` • `!cancelar_match`"
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

    view = MediatorMenuView(match)
    await ctx.reply(embed=embed, view=view, ephemeral=True)
    await ctx.message.delete()


async def cmd_winner_team(ctx, team: str):
    """!winner_team blue|red"""
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.reply("❌ Use dentro de uma thread de partida.")
        return

    team = team.lower().strip()
    if team not in ("blue", "red"):
        await ctx.reply("❌ Use: `!winner_team blue` ou `!winner_team red`")
        return

    match = await _get_match_by_thread(ctx.channel.id)
    if not match:
        await ctx.reply("❌ Nenhuma partida encontrada.")
        return

    if ctx.author.id != match["mediator_id"]:
        await ctx.reply("❌ Apenas o mediador pode declarar o vencedor.")
        return

    if match.get("status") != "em_andamento":
        await ctx.reply(f"❌ Partida precisa estar em andamento. Status: `{match.get('status')}`")
        return

    label   = "🔵 Time Blue" if team == "blue" else "🔴 Time Red"
    win_ids = match.get("time_blue" if team == "blue" else "time_red", [])
    mentions = " ".join(f"<@{uid}>" for uid in win_ids)

    await _update_match(str(match["_id"]), {
        "status": "aguardando_premio",
        "vencedor": team
    })

    await _update_thread_name(
        ctx.channel,
        _base_name(ctx.channel.name),
        f"Vencedor: {label}"
    )

    embed_pub = discord.Embed(
        title="🏆 Time Vencedor Declarado!",
        description=f"**{label}** venceu!\n\n{mentions}",
        color=discord.Color.gold()
    )
    embed_pub.add_field(
        name="Vencedor(es)",
        value="\n".join(f"• <@{uid}>" for uid in win_ids) or "—",
        inline=False
    )
    await ctx.channel.send(embed=embed_pub)
    await ctx.channel.send(embed=embed_prize_instructions({**match, "vencedor": team}))
    await ctx.message.delete()


async def cmd_prize(ctx):
    """!prize — Confirma entrega do prêmio"""
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.reply("❌ Use dentro de uma thread de partida.")
        return

    match = await _get_match_by_thread(ctx.channel.id)
    if not match:
        await ctx.reply("❌ Nenhuma partida encontrada.")
        return

    if ctx.author.id != match["mediator_id"]:
        await ctx.reply("❌ Apenas o mediador pode confirmar o prêmio.")
        return

    if match.get("status") != "aguardando_premio":
        await ctx.reply(f"❌ Use `!winner_team` primeiro. Status: `{match.get('status')}`")
        return

    if match.get("premio_entregue_mediador"):
        await ctx.reply("✅ Prêmio já marcado como entregue.")
        return

    vencedor = match.get("vencedor", "blue")
    win_ids  = match.get("time_blue" if vencedor == "blue" else "time_red", [])
    label    = "🔵 Time Blue" if vencedor == "blue" else "🔴 Time Red"
    vals     = _calc_values(match["bet_value"])
    mentions = " ".join(f"<@{uid}>" for uid in win_ids)

    await _update_match(str(match["_id"]), {"premio_entregue_mediador": True})

    embed_pub = discord.Embed(
        title="🎁 Prêmio Entregue!",
        description=(
            f"O mediador <@{match['mediator_id']}> confirmou o envio!\n\n"
            f"**{label}** — R$ {vals['premio']:.2f} via PIX\n\n"
            f"{mentions}\n\n"
            "**Confirme o recebimento** clicando abaixo."
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
    await ctx.message.delete()


async def cmd_confirmar_pagamento(ctx):
    """!confirmar_pagamento"""
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.reply("❌ Use dentro de uma thread de partida.")
        return

    match = await _get_match_by_thread(ctx.channel.id)
    if not match or ctx.author.id != match["mediator_id"]:
        await ctx.reply("❌ Sem permissão ou partida não encontrada.")
        return

    if match.get("pagamento_confirmado"):
        await ctx.reply("✅ Pagamento já confirmado.")
        return

    await _update_match(str(match["_id"]), {
        "pagamento_confirmado": True,
        "status": "aguardando_inicio"
    })
    await _update_thread_name(ctx.channel, _base_name(ctx.channel.name), "Pagamento Confirmado")

    embed = discord.Embed(
        title="✅ Pagamento Confirmado!",
        description=f"<@{match['mediator_id']}> confirmou os pagamentos. A partida pode começar!",
        color=discord.Color.green()
    )
    await ctx.channel.send(embed=embed)
    await ctx.message.delete()


async def cmd_iniciar_partida(ctx):
    """!iniciar_partida"""
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.reply("❌ Use dentro de uma thread de partida.")
        return

    match = await _get_match_by_thread(ctx.channel.id)
    if not match or ctx.author.id != match["mediator_id"]:
        await ctx.reply("❌ Sem permissão ou partida não encontrada.")
        return

    if not match.get("pagamento_confirmado"):
        await ctx.reply("❌ Confirme o pagamento primeiro com `!confirmar_pagamento`.")
        return

    if match.get("status") == "em_andamento":
        await ctx.reply("⚠️ Partida já iniciada.")
        return

    await _update_match(str(match["_id"]), {
        "status": "em_andamento",
        "started_at": datetime.utcnow()
    })
    await _update_thread_name(ctx.channel, _base_name(ctx.channel.name), "Em Andamento ▶️")

    embed = discord.Embed(
        title="▶️ Partida Iniciada!",
        description="A partida começou! Boa sorte a todos! 🎮",
        color=discord.Color.blue()
    )
    await ctx.channel.send(embed=embed)
    await ctx.message.delete()


async def cmd_cancelar_match(ctx):
    """!cancelar_match"""
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.reply("❌ Use dentro de uma thread de partida.")
        return

    match = await _get_match_by_thread(ctx.channel.id)
    if not match:
        await ctx.reply("❌ Partida não encontrada.")
        return

    is_mediator = ctx.author.id == match["mediator_id"]
    is_admin    = ctx.author.guild_permissions.administrator

    if not is_mediator and not is_admin:
        await ctx.reply("❌ Apenas o mediador ou admins podem cancelar.")
        return

    await _update_match(str(match["_id"]), {"status": "cancelado"})
    await _update_thread_name(ctx.channel, _base_name(ctx.channel.name), "Cancelado ❌")

    embed = discord.Embed(
        title="❌ Partida Cancelada",
        description=f"Cancelada por <@{ctx.author.id}>.",
        color=discord.Color.red()
    )
    await ctx.channel.send(embed=embed)
    await ctx.message.delete()

    try:
        await ctx.channel.edit(archived=True)
    except Exception:
        pass
