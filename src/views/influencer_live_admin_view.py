"""
influencer_live_admin_view.py
View do painel administrativo do modo contra — postada em #influencers-controle.
Permite que ADM gerencie todas as salas ativas, veja estatísticas e force-close.
"""
from __future__ import annotations
import discord
from discord.ui import View, Button, Select
from utils.logger import logger
from utils.datetime_utils import utcnow

THEME_LIVE  = 0xE91E63
THEME_COLOR = 0xFFD54F


def build_influencer_live_admin_embed(rooms: list) -> discord.Embed:
    """
    Embed resumo de todas as salas ativas no modo contra.
    rooms: list[InfluencerLiveRoom]
    """
    embed = discord.Embed(
        title="⚔️ Painel ADM — Modo Contra",
        description=(
            "Visão geral de todas as salas do modo contra ativas no servidor.\n\n"
            "Use os botões abaixo para gerenciar salas individuais."
        ),
        color=THEME_LIVE,
        timestamp=utcnow(),
    )

    if not rooms:
        embed.add_field(name="Salas Ativas", value="Nenhuma sala ativa no momento.", inline=False)
    else:
        lines = []
        for room in rooms:
            status_emoji = {"active": "🟢", "paused": "⏸️", "inactive": "🔴"}.get(room.status, "❓")
            lines.append(
                f"{status_emoji} <@{room.influencer_id}> — `{room.game_mode}` "
                f"R$ `{room.entry_value:.2f}` — fila: `{room.queue_size}`"
            )
        embed.add_field(
            name=f"Salas ({len(rooms)})",
            value="\n".join(lines),
            inline=False,
        )

    embed.set_footer(text=f"SOLAR E-SPORTS · Atualizado em {utcnow().strftime('%d/%m/%Y %H:%M UTC')}")
    return embed


class InfluencerLiveAdminView(View):
    """
    Painel ADM em #influencers-controle.
    Atualizar — força re-render de todas as salas
    Force-Close — fecha sala de qualquer influencer
    Fila Live — exibe fila Controller Live
    """

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔄 Atualizar Painel",
        style=discord.ButtonStyle.secondary,
        custom_id="live_admin_refresh",
        emoji="🔄",
    )
    async def refresh(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Apenas **ADM** pode usar este painel.", ephemeral=True)
            return

        from services.influencer_live_room_service import influencer_live_room_service

        rooms_result = await influencer_live_room_service.list_active_rooms(
            guild_id=str(interaction.guild_id))
        rooms = rooms_result.get("rooms", [])
        embed = build_influencer_live_admin_embed(rooms)

        await interaction.response.edit_message(embed=embed, view=self)
        logger.info(f"[LiveAdmin] Painel atualizado por {interaction.user.name}")

    @discord.ui.button(
        label="❌ Force-Close Sala",
        style=discord.ButtonStyle.danger,
        custom_id="live_admin_force_close",
        emoji="🚫",
    )
    async def force_close(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Apenas **ADM** pode fechar salas forçadamente.", ephemeral=True)
            return

        await interaction.response.send_message(
            "Digite o Discord ID do influencer cuja sala deseja fechar:",
            ephemeral=True,
        )

        def check(m: discord.Message):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel_id

        try:
            msg = await interaction.client.wait_for("message", check=check, timeout=30.0)
        except Exception:
            return

        try:
            influencer_id = int(msg.content.strip())
        except ValueError:
            await interaction.followup.send("❌ ID inválido.", ephemeral=True)
            return

        from services.influencer_live_room_service import influencer_live_room_service

        member = interaction.guild.get_member(influencer_id)
        if not member:
            await interaction.followup.send("❌ Membro não encontrado no servidor.", ephemeral=True)
            return

        result = await influencer_live_room_service.desativar_sala(
            guild=interaction.guild,
            influencer=member,
            forced_by=interaction.user,
        )

        if result["ok"]:
            await interaction.followup.send(
                f"✅ Sala de <@{influencer_id}> fechada com sucesso.", ephemeral=True)
            logger.info(
                f"[LiveAdmin] Sala de {influencer_id} fechada por ADM {interaction.user.name}")
        else:
            await interaction.followup.send(
                f"❌ {result['msg']}", ephemeral=True)

    @discord.ui.button(
        label="📋 Fila Controller Live",
        style=discord.ButtonStyle.primary,
        custom_id="live_admin_view_cl_queue",
        emoji="⚔️",
    )
    async def view_cl_queue(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Apenas **ADM** pode usar este painel.", ephemeral=True)
            return

        from services.mediator_live_queue_service import mediator_live_queue_service

        result = await mediator_live_queue_service.get_fila(guild_id=str(interaction.guild_id))
        queue  = result.get("queue")

        embed = discord.Embed(title="⚔️ Fila Controller Live — ADM", color=THEME_LIVE, timestamp=utcnow())
        if not queue or queue.size() == 0:
            embed.description = "Nenhum Controller Live na fila."
        else:
            lines = [f"`{i+1}.` <@{mid}>" for i, mid in enumerate(queue.mediators[:15])]
            embed.add_field(name=f"Controllers ({queue.size()})", value="\n".join(lines), inline=False)
            embed.add_field(name="Status",        value=f"`{queue.status}`",  inline=True)
            embed.add_field(name="Partida ativa", value=(
                f"`{queue.active_match_id}`" if queue.active_match_id else "—"
            ), inline=True)

        embed.set_footer(text="SOLAR E-SPORTS · Controller Live")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="📊 Estatísticas Modo Contra",
        style=discord.ButtonStyle.secondary,
        custom_id="live_admin_stats",
        emoji="📈",
    )
    async def stats(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Apenas **ADM** pode ver estatísticas.", ephemeral=True)
            return

        from services.influencer_live_room_service import influencer_live_room_service

        result = await influencer_live_room_service.get_stats(guild_id=str(interaction.guild_id))
        data   = result.get("stats", {})

        embed = discord.Embed(
            title="📊 Estatísticas — Modo Contra",
            color=THEME_LIVE,
            timestamp=utcnow(),
        )
        embed.add_field(name="Salas ativas",          value=f"`{data.get('active_rooms', 0)}`",    inline=True)
        embed.add_field(name="Total de partidas hoje", value=f"`{data.get('matches_today', 0)}`",   inline=True)
        embed.add_field(name="Volume hoje",            value=f"R$ `{data.get('volume_today', 0):.2f}`", inline=True)
        embed.add_field(name="Partidas totais",        value=f"`{data.get('total_matches', 0)}`",   inline=True)
        embed.add_field(name="Volume total",           value=f"R$ `{data.get('total_volume', 0):.2f}`", inline=True)
        embed.add_field(name="Jogadores únicos",       value=f"`{data.get('unique_players', 0)}`",  inline=True)
        embed.set_footer(text="SOLAR E-SPORTS · Modo Contra")
        await interaction.response.send_message(embed=embed, ephemeral=True)