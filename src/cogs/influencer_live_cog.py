# influencer_live_cog.py — Cog do sistema Influencer Live (Modo Contra).
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from utils.logger import logger


class InfluencerLiveCog(commands.Cog, name="InfluencerLive"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─────────────────────────────────────────────────────────────
    # /encerrar_sala — Influencer encerra sua sala ativa
    # ─────────────────────────────────────────────────────────────

    @app_commands.command(
        name="encerrar_sala",
        description="[Influencer] Encerra sua sala ativa no Modo Contra.",
    )
    async def encerrar_sala(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            role_inf = discord.utils.get(interaction.guild.roles, name="Influencer")
            is_adm   = interaction.user.guild_permissions.administrator
            is_inf   = role_inf and role_inf in interaction.user.roles

            if not (is_adm or is_inf):
                await interaction.followup.send(
                    "❌ Apenas **Influencers** podem usar este comando.", ephemeral=True)
                return

            # FIX: desativar_sala recebe discord.Member, não influencer_id
            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                await interaction.followup.send(
                    "❌ Não foi possível resolver seu perfil no servidor.", ephemeral=True)
                return

            from services.influencer_live_room_service import influencer_live_room_service
            result = await influencer_live_room_service.desativar_sala(
                guild=interaction.guild,
                influencer=member,
            )

            if not result["ok"]:
                await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)
                return

            await interaction.followup.send(
                "✅ Sua sala foi encerrada e os canais foram removidos.", ephemeral=True)
            logger.info(f"[InfluencerLiveCog] Sala encerrada por {interaction.user.name}")

        except Exception as e:
            logger.error(f"[InfluencerLiveCog] /encerrar_sala: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Erro ao encerrar sala: {e}", ephemeral=True)

    # ─────────────────────────────────────────────────────────────
    # /sala_status — ADM verifica salas ativas
    # ─────────────────────────────────────────────────────────────

    @app_commands.command(
        name="sala_status",
        description="[ADM] Lista todas as salas Contra ativas no servidor.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def sala_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            from services.influencer_live_room_service import influencer_live_room_service

            # FIX: list_active_rooms retorna {"ok": True, "rooms": [...]}
            result = await influencer_live_room_service.list_active_rooms(
                guild_id=str(interaction.guild_id)
            )
            rooms = result.get("rooms", []) if result.get("ok") else []

            if not rooms:
                await interaction.followup.send(
                    "📭 Nenhuma sala ativa no momento.", ephemeral=True)
                return

            embed = discord.Embed(
                title="⚔️ Salas Contra Ativas",
                color=0xE91E63,
            )
            for room in rooms:
                embed.add_field(
                    name=f"<@{room.influencer_id}>",
                    value=(
                        f"**Plataforma:** `{room.platform}`\n"
                        f"**Tipo:** `{room.game_mode}`\n"
                        f"**Valor:** R$ `{room.entry_value:.2f}`\n"
                        f"**Fila:** `{room.queue_size}` jogadores\n"
                        f"**Status:** `{room.status}`"
                    ),
                    inline=True,
                )
            embed.set_footer(text="SOLAR E-SPORTS · Influencer Live")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[InfluencerLiveCog] /sala_status: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Erro: {e}", ephemeral=True)

    # ─────────────────────────────────────────────────────────────
    # /forcar_encerrar — ADM força encerramento de sala de qualquer influencer
    # ─────────────────────────────────────────────────────────────

    @app_commands.command(
        name="forcar_encerrar",
        description="[ADM] Força o encerramento da sala de um Influencer.",
    )
    @app_commands.describe(membro="Influencer cuja sala será encerrada")
    @app_commands.checks.has_permissions(administrator=True)
    async def forcar_encerrar(
        self, interaction: discord.Interaction, membro: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)
        try:
            # FIX: desativar_sala recebe discord.Member, não influencer_id
            from services.influencer_live_room_service import influencer_live_room_service
            result = await influencer_live_room_service.desativar_sala(
                guild=interaction.guild,
                influencer=membro,
                forced_by=interaction.user,
            )

            if not result["ok"]:
                await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)
                return

            await interaction.followup.send(
                f"✅ Sala de {membro.mention} encerrada.", ephemeral=True)
            logger.info(
                f"[InfluencerLiveCog] Sala de {membro.name} encerrada por ADM {interaction.user.name}")

        except Exception as e:
            logger.error(f"[InfluencerLiveCog] /forcar_encerrar: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Erro: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(InfluencerLiveCog(bot))
