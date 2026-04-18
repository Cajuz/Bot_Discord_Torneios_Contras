"""
mediator_panel_view.py — Painel de mediadores.
"""
import discord
from discord.ui import View, Button
from services.mediator_queue import mediator_queue
from services.channel_service import CONTROLLER_ROLE_NAME, ADM_ROLE_NAME
from utils.logger import logger

THEME_COLOR = 0xFFD54F


def create_mediator_panel_embed(info: dict | None = None) -> discord.Embed:

    embed = discord.Embed(
        title="⚡ Painel de Mediadores",
        description="Gerencie sua presença na fila de mediação.",
        color=THEME_COLOR,
    )
    embed.add_field(
        name="Como funciona",
        value=(
            "• **Entrar na Fila** — começa a receber partidas\n"
            "• **Sair da Fila** — para de receber partidas\n"
            "• Apenas cargo **Controller** pode mediar"
        ),
        inline=False,
    )
    embed.set_footer(text="X1 Frifas — Painel de Mediação")
    return embed


class MediatorPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Entrar na Fila",
        style=discord.ButtonStyle.success,
        custom_id="mediator_join_queue",
        emoji="✅",
    )
    async def join_queue_button(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        role    = discord.utils.get(interaction.guild.roles, name=CONTROLLER_ROLE_NAME)
        if not role or role not in interaction.user.roles:
            await interaction.response.send_message(
                f"Você precisa do cargo **{CONTROLLER_ROLE_NAME}** para entrar na fila.",
                ephemeral=True)
            return

        from config.database import db
        collection = db.get_collection("mediators")
        mediator   = await collection.find_one({"user_id": user_id})
        if not mediator:
            await mediator_queue.register_mediator(
                user_id=user_id,
                username=interaction.user.name,
                guild_id=interaction.guild.id,
            )

        success = await mediator_queue.add_to_queue(user_id)
        if success:
            pos = await mediator_queue.get_mediator_position(user_id)
            await interaction.response.send_message(
                f"✅ Você entrou na fila! Posição: **{pos}º**", ephemeral=True)
            await self._update_panel(interaction)
        else:
            await interaction.response.send_message(
                "Você já está na fila.", ephemeral=True)

    @discord.ui.button(
        label="Sair da Fila",
        style=discord.ButtonStyle.red,
        custom_id="mediator_leave_queue",
        emoji="❌",
    )
    async def leave_queue_button(self, interaction: discord.Interaction, button: Button):
        success = await mediator_queue.remove_from_queue(interaction.user.id)
        if success:
            await interaction.response.send_message("✅ Você saiu da fila.", ephemeral=True)
            await self._update_panel(interaction)
        else:
            await interaction.response.send_message(
                "Você não está na fila.", ephemeral=True)

    @discord.ui.button(
        label="Ver Fila",
        style=discord.ButtonStyle.secondary,
        custom_id="mediator_view_queue",
        emoji="📊",
    )
    async def view_queue_button(self, interaction: discord.Interaction, button: Button):
        adm_role = discord.utils.get(interaction.guild.roles, name=ADM_ROLE_NAME)
        is_adm   = (adm_role and adm_role in interaction.user.roles) or \
                   interaction.user.guild_permissions.administrator
        if not is_adm:
            await interaction.response.send_message(
                "Apenas **ADM** pode visualizar a fila completa.", ephemeral=True)
            return
        info  = await mediator_queue.get_queue_info()
        embed = discord.Embed(title="📋 Fila de Mediadores", color=THEME_COLOR)
        embed.add_field(
            name="Estatísticas",
            value=f"Ativos: `{info['total_active']}` | Na fila: `{info['in_queue']}`",
            inline=False,
        )
        if info["queue"]:
            lines = [f"`{i}.` <@{uid}>" for i, uid in enumerate(info["queue"][:15], 1)]
            embed.add_field(name="Fila atual", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Fila atual", value="Nenhum mediador na fila.", inline=False)
        embed.set_footer(text="SOLAR E-SPORTS — Fila de Mediação")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _update_panel(self, interaction: discord.Interaction):
        try:
            info  = await mediator_queue.get_queue_info()
            embed = create_mediator_panel_embed(info)
            await interaction.message.edit(embed=embed)
        except Exception:
            pass
