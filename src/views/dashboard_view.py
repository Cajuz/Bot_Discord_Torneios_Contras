"""
dashboard_view.py — View persistente para cada dashboard.

Botões:
  🔄 Atualizar — recarrega o embed com dados frescos
  📥 Exportar  — envia CSV em DM ou ephemeral
"""
from __future__ import annotations

import io
import discord
from utils.logger import logger

THEME = 0xFFD54F


class DashboardView(discord.ui.View):
    """
    View fixa postada em cada canal de dashboard.
    Parâmetros:
      ch_name   — nome do canal (ex: 'dashboard-partidas')
      guild_id  — ID do servidor
      builder   — coroutine async def builder(guild_id) -> (embed, csv_str)
    """

    def __init__(self, ch_name: str, guild_id: int, builder):
        super().__init__(timeout=None)
        self.ch_name  = ch_name
        self.guild_id = guild_id
        self.builder  = builder
        # Garante custom_ids únicos por canal
        self.children[0].custom_id = f"dash_update_{ch_name}"
        self.children[1].custom_id = f"dash_export_{ch_name}"

    # ── Atualizar ─────────────────────────────────────────────
    @discord.ui.button(
        label="Atualizar",
        style=discord.ButtonStyle.secondary,
        emoji="🔄",
        custom_id="dash_update_placeholder",
    )
    async def btn_update(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            embed, _ = await self.builder(self.guild_id)
            # Reconstrói a view com os mesmos parâmetros para manter botões ativos
            new_view = DashboardView(
                ch_name=self.ch_name,
                guild_id=self.guild_id,
                builder=self.builder,
            )
            await interaction.message.edit(embed=embed, view=new_view)
            await interaction.followup.send("Dashboard atualizado.", ephemeral=True)
        except Exception as e:
            logger.error(f"[DashboardView] Erro ao atualizar {self.ch_name}: {e}")
            await interaction.followup.send("Erro ao atualizar. Tente novamente.", ephemeral=True)

    # ── Exportar ──────────────────────────────────────────────
    @discord.ui.button(
        label="Exportar CSV",
        style=discord.ButtonStyle.secondary,
        emoji="📥",
        custom_id="dash_export_placeholder",
    )
    async def btn_export(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            _, csv_data = await self.builder(self.guild_id)
            fname = f"{self.ch_name}_{interaction.created_at.strftime('%Y%m%d_%H%M')}.csv"
            file  = discord.File(io.BytesIO(csv_data.encode("utf-8")), filename=fname)
            await interaction.followup.send(
                content=f"Exportação do **{self.ch_name}**:",
                file=file,
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"[DashboardView] Erro ao exportar {self.ch_name}: {e}")
            await interaction.followup.send("Erro ao exportar. Tente novamente.", ephemeral=True)
