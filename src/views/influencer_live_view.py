"""
influencer_live_view.py
View do canal contra-<influencer> — painel público onde jogadores entram
na fila para desafiar o influencer no modo contra.
"""
from __future__ import annotations
import discord
from discord.ui import View, Button
from utils.logger import logger
from utils.datetime_utils import utcnow

THEME_LIVE  = 0xE91E63
THEME_COLOR = 0xFFD54F


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE EMBED
# ══════════════════════════════════════════════════════════════════════════════

def build_contra_room_embed(room, queue_size: int = 0) -> discord.Embed:
    """
    Embed principal do canal contra-<influencer>.
    room: InfluencerLiveRoom (model Fase 1)
    """
    status_map = {
        "active":   ("🟢 Aberta",   discord.Colour.green()),
        "paused":   ("⏸️ Pausada",  discord.Colour.orange()),
        "inactive": ("🔴 Fechada",  discord.Colour.red()),
    }
    status_label, color = status_map.get(room.status, ("❓ Desconhecido", discord.Colour.greyple()))

    embed = discord.Embed(
        title=f"⚔️ Sala Contra — <@{room.influencer_id}>",
        description=(
            "Desafie o influencer em uma partida ao vivo!\n\n"
            "Clique em **Jogar Contra** para entrar na fila.\n"
            "Quando for sua vez, você será notificado aqui mesmo."
        ),
        color=color,
        timestamp=utcnow(),
    )
    embed.add_field(name="Status",          value=status_label,                    inline=True)
    embed.add_field(name="Modo",            value=f"`{room.game_mode}`",            inline=True)
    embed.add_field(name="Valor de Entrada", value=f"R$ `{room.entry_value:.2f}`",  inline=True)
    embed.add_field(name="Jogadores na Fila", value=f"`{queue_size}`",              inline=True)

    if room.custom_rules:
        embed.add_field(name="Regras Especiais", value=room.custom_rules, inline=False)

    embed.set_footer(text="SOLAR E-SPORTS · Modo Contra · Apenas leitura")
    return embed


def build_contra_match_started_embed(
    influencer: discord.Member,
    challenger: discord.Member,
    room,
) -> discord.Embed:
    """Embed postado na thread/canal quando a partida live começa."""
    embed = discord.Embed(
        title="⚔️ Partida ao Vivo Iniciada!",
        color=THEME_LIVE,
        timestamp=utcnow(),
    )
    embed.add_field(name="🎥 Influencer",   value=influencer.mention,              inline=True)
    embed.add_field(name="⚔️ Desafiante",  value=challenger.mention,              inline=True)
    embed.add_field(name="🎮 Modo",         value=f"`{room.game_mode}`",            inline=True)
    embed.add_field(name="💰 Valor",        value=f"R$ `{room.entry_value:.2f}`",   inline=True)
    embed.set_footer(
        text=f"Mediador Controller Live · {utcnow().strftime('%d/%m/%Y %H:%M UTC')}"
    )
    return embed


def build_contra_match_result_embed(
    winner: discord.Member,
    loser: discord.Member,
    prize: float,
    match_id: str,
) -> discord.Embed:
    """Embed de resultado final da partida no modo contra."""
    embed = discord.Embed(
        title="🏆 Resultado da Partida — Modo Contra",
        color=discord.Colour.gold(),
        timestamp=utcnow(),
    )
    embed.add_field(name="🥇 Vencedor",  value=winner.mention,          inline=True)
    embed.add_field(name="💀 Perdedor",  value=loser.mention,           inline=True)
    embed.add_field(name="💰 Prêmio",    value=f"R$ `{prize:.2f}`",     inline=True)
    embed.add_field(name="📋 Partida",   value=f"`{match_id}`",         inline=False)
    embed.set_footer(text="SOLAR E-SPORTS · Modo Contra")
    return embed


# ══════════════════════════════════════════════════════════════════════════════
# VIEW PÚBLICA — canal contra-<influencer>
# ══════════════════════════════════════════════════════════════════════════════

class ContraRoomView(View):
    """
    Painel público no canal contra-<influencer>.
    Qualquer Membro pode clicar em Jogar Contra para entrar na fila.
    """

    def __init__(self, influencer_id: int, guild_id: int):
        super().__init__(timeout=None)
        self.influencer_id = influencer_id
        self.guild_id      = guild_id

    @discord.ui.button(
        label="⚔️ Jogar Contra",
        style=discord.ButtonStyle.danger,
        custom_id="contra_join_queue",
        emoji="🎮",
    )
    async def join_queue(self, interaction: discord.Interaction, button: Button):
        from services.influencer_live_queue_service import influencer_live_queue_service
        from services.influencer_live_room_service  import influencer_live_room_service

        # Verifica se a sala está ativa
        room_result = await influencer_live_room_service.get_room(
            influencer_id=str(self.influencer_id),
            guild_id=str(self.guild_id),
        )
        if not room_result["ok"] or room_result["room"].status != "active":
            await interaction.response.send_message(
                "❌ A sala está fechada ou pausada no momento.", ephemeral=True)
            return

        # Influencer não pode entrar na própria fila
        if interaction.user.id == self.influencer_id:
            await interaction.response.send_message(
                "❌ Você não pode entrar na fila da sua própria sala.", ephemeral=True)
            return

        result = await influencer_live_queue_service.enter_queue(
            influencer_id=str(self.influencer_id),
            guild_id=str(self.guild_id),
            player_id=str(interaction.user.id),
        )

        if result["ok"]:
            pos = result.get("position", "?")
            await interaction.response.send_message(
                f"✅ Você entrou na fila! Posição: **{pos}º**\n"
                "Aguarde ser chamado para a partida.",
                ephemeral=True,
            )
            logger.info(
                f"[ContraRoom] {interaction.user.name} entrou na fila "
                f"— influencer {self.influencer_id} — posição {pos}"
            )
        else:
            await interaction.response.send_message(
                f"❌ {result['msg']}", ephemeral=True)

    @discord.ui.button(
        label="🚪 Sair da Fila",
        style=discord.ButtonStyle.secondary,
        custom_id="contra_leave_queue",
        emoji="❌",
    )
    async def leave_queue(self, interaction: discord.Interaction, button: Button):
        from services.influencer_live_queue_service import influencer_live_queue_service

        result = await influencer_live_queue_service.leave_queue(
            influencer_id=str(self.influencer_id),
            guild_id=str(self.guild_id),
            player_id=str(interaction.user.id),
        )

        if result["ok"]:
            await interaction.response.send_message(
                "✅ Você saiu da fila.", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"❌ {result['msg']}", ephemeral=True)

    @discord.ui.button(
        label="📊 Ver Fila",
        style=discord.ButtonStyle.secondary,
        custom_id="contra_view_queue",
        emoji="📋",
    )
    async def view_queue(self, interaction: discord.Interaction, button: Button):
        from services.influencer_live_queue_service import influencer_live_queue_service

        result = await influencer_live_queue_service.get_fila(
            influencer_id=str(self.influencer_id),
            guild_id=str(self.guild_id),
        )

        if not result["ok"]:
            await interaction.response.send_message(
                f"❌ {result['msg']}", ephemeral=True)
            return

        queue   = result["queue"]
        players = queue.players

        embed = discord.Embed(
            title="📋 Fila — Modo Contra",
            color=THEME_LIVE,
            timestamp=utcnow(),
        )
        embed.add_field(
            name="Influencer",
            value=f"<@{self.influencer_id}>",
            inline=True,
        )
        embed.add_field(
            name="Jogadores na Fila",
            value=f"`{len(players)}`",
            inline=True,
        )

        if players:
            lines = [f"`{i+1}.` <@{pid}>" for i, pid in enumerate(players[:15])]
            embed.add_field(name="Fila Atual", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Fila Atual", value="Nenhum jogador na fila.", inline=False)

        embed.set_footer(text="SOLAR E-SPORTS · Modo Contra")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW DO CONTROLLER LIVE — painel interno #painel-mediador-live
# ══════════════════════════════════════════════════════════════════════════════

class ControllerLivePanelView(View):
    """
    Painel no canal #painel-mediador-live.
    Apenas Controllers Live veem o canal — botões para entrar/sair da fila live.
    """

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Entrar na Fila Live",
        style=discord.ButtonStyle.success,
        custom_id="controller_live_join",
        emoji="✅",
    )
    async def join_live_queue(self, interaction: discord.Interaction, button: Button):
        from services.mediator_live_queue_service import mediator_live_queue_service

        role = discord.utils.get(interaction.guild.roles, name="Controller Live")
        if not role or role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ Você precisa do cargo **Controller Live** para entrar nesta fila.",
                ephemeral=True,
            )
            return

        result = await mediator_live_queue_service.enter_queue(
            guild_id=str(interaction.guild_id),
            mediator_id=interaction.user.id,
        )

        if result["ok"]:
            pos = result.get("position", "?")
            await interaction.response.send_message(
                f"✅ Você entrou na fila Controller Live! Posição: **{pos}º**\n"
                "Você será chamado quando um desafio live começar.",
                ephemeral=True,
            )
            logger.info(
                f"[ControllerLive] {interaction.user.name} entrou na fila — posição {pos}"
            )
        else:
            await interaction.response.send_message(
                f"⚠️ {result['msg']}", ephemeral=True)

    @discord.ui.button(
        label="Sair da Fila Live",
        style=discord.ButtonStyle.red,
        custom_id="controller_live_leave",
        emoji="❌",
    )
    async def leave_live_queue(self, interaction: discord.Interaction, button: Button):
        from services.mediator_live_queue_service import mediator_live_queue_service

        result = await mediator_live_queue_service.leave_queue(
            guild_id=str(interaction.guild_id),
            mediator_id=interaction.user.id,
        )

        if result["ok"]:
            await interaction.response.send_message(
                "✅ Você saiu da fila Controller Live.", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"⚠️ {result['msg']}", ephemeral=True)

    @discord.ui.button(
        label="Ver Fila Live",
        style=discord.ButtonStyle.secondary,
        custom_id="controller_live_view",
        emoji="📊",
    )
    async def view_live_queue(self, interaction: discord.Interaction, button: Button):
        from services.mediator_live_queue_service import mediator_live_queue_service

        role   = discord.utils.get(interaction.guild.roles, name="Controller Live")
        is_adm = interaction.user.guild_permissions.administrator
        is_cl  = role and role in interaction.user.roles

        if not (is_adm or is_cl):
            await interaction.response.send_message(
                "❌ Apenas **Controller Live** ou **ADM** podem ver esta fila.",
                ephemeral=True,
            )
            return

        result = await mediator_live_queue_service.get_fila(guild_id=str(interaction.guild_id))
        queue  = result.get("queue")

        embed = discord.Embed(title="⚔️ Fila Controller Live", color=THEME_LIVE, timestamp=utcnow())
        if not queue or queue.size() == 0:
            embed.description = "Nenhum Controller Live na fila no momento."
        else:
            lines = [f"`{i+1}.` <@{mid}>" for i, mid in enumerate(queue.mediators[:15])]
            embed.add_field(name=f"Controllers ({queue.size()})", value="\n".join(lines), inline=False)
            embed.add_field(name="Status",        value=f"`{queue.status}`",            inline=True)
            embed.add_field(name="Partida ativa", value=(
                f"`{queue.active_match_id}`" if queue.active_match_id else "—"
            ), inline=True)

        embed.set_footer(text="SOLAR E-SPORTS · Controller Live")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="Minha Posição",
        style=discord.ButtonStyle.primary,
        custom_id="controller_live_position",
        emoji="📍",
    )
    async def my_position(self, interaction: discord.Interaction, button: Button):
        from services.mediator_live_queue_service import mediator_live_queue_service

        result = await mediator_live_queue_service.get_position(
            guild_id=str(interaction.guild_id),
            mediator_id=interaction.user.id,
        )

        if result["ok"]:
            pos = result["position"]
            await interaction.response.send_message(
                f"📍 Sua posição na fila Controller Live: **{pos}º**",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"❌ {result['msg']}", ephemeral=True)