"""
commission_cog.py
Slash commands para admins configurarem a taxa de comissão por servidor.

Subcomandos:
  /comissao ver           — exibe a config atual (match + live)
  /comissao match         — define a taxa para partidas normais
  /comissao live          — define a taxa para o modo contra (influencer live)
  /comissao reset match   — restaura defaults do match
  /comissao reset live    — restaura defaults do live

Esquema de taxa:
  - Abaixo de `fixed_threshold`: cobra `fixed_fee` por jogador (fixo).
  - Acima do threshold:          cobra `pct` × bet_value por jogador (percentual).
"""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from services.commission_service import commission_service
from utils.logger import logger

THEME = 0x01696F  # teal


def _scheme_fields(scheme: dict, tipo: str) -> list[tuple[str, str]]:
    """Gera campos legíveis para um embed de comissão."""
    threshold = scheme.get("fixed_threshold", 20.0)
    fee       = scheme.get("fixed_fee", 2.0)
    pct       = scheme.get("pct", 0.10)
    return [
        (f"[{tipo}] Limite p/ taxa fixa", f"R$ `{threshold:.2f}`"),
        (f"[{tipo}] Taxa fixa/jogador",   f"R$ `{fee:.2f}`"),
        (f"[{tipo}] Taxa percentual",     f"`{pct*100:.1f}%` do bet"),
    ]


class CommissionCog(commands.Cog):
    """Configuração de comissão por servidor."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── grupo raiz ────────────────────────────────────────────────────────────
    comissao = app_commands.Group(
        name="comissao",
        description="Configuração de taxa de comissão do servidor",
        default_permissions=discord.Permissions(administrator=True),
    )

    # ── /comissao ver ─────────────────────────────────────────────────────────
    @comissao.command(name="ver", description="Exibe a configuração de comissão atual")
    async def ver(self, interaction: discord.Interaction):
        cfg = await commission_service.get_config(str(interaction.guild_id))
        embed = discord.Embed(
            title="⚙️ Comissão — Configuração Atual",
            color=THEME,
        )
        for name, value in _scheme_fields(cfg["match"], "Match"):
            embed.add_field(name=name, value=value, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=False)  # separador
        for name, value in _scheme_fields(cfg["live"], "Live"):
            embed.add_field(name=name, value=value, inline=True)
        embed.set_footer(text=f"Servidor: {interaction.guild.name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /comissao match ───────────────────────────────────────────────────────
    @comissao.command(
        name="match",
        description="Define a taxa de comissão para partidas normais",
    )
    @app_commands.describe(
        fixed_threshold="Valor máximo para taxa fixa (ex: 20.0)",
        fixed_fee="Taxa fixa por jogador abaixo do threshold (ex: 2.0)",
        pct="Percentual cobrado acima do threshold, entre 0 e 1 (ex: 0.10 = 10%)",
    )
    async def match_cmd(
        self,
        interaction: discord.Interaction,
        fixed_threshold: float,
        fixed_fee: float,
        pct: float,
    ):
        if not (0 < pct < 1):
            await interaction.response.send_message(
                "❌ `pct` deve estar entre 0 e 1 (ex: 0.10 para 10%).",
                ephemeral=True,
            )
            return
        if fixed_fee < 0 or fixed_threshold < 0:
            await interaction.response.send_message(
                "❌ Valores não podem ser negativos.", ephemeral=True)
            return

        scheme = await commission_service.update_match(
            guild_id=str(interaction.guild_id),
            fixed_threshold=fixed_threshold,
            fixed_fee=fixed_fee,
            pct=pct,
        )
        embed = discord.Embed(
            title="✅ Comissão Match Atualizada",
            color=THEME,
        )
        for name, value in _scheme_fields(scheme, "Match"):
            embed.add_field(name=name, value=value, inline=True)
        logger.info(
            f"[CommissionCog] match atualizado por {interaction.user} "
            f"guild={interaction.guild_id} scheme={scheme}"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /comissao live ────────────────────────────────────────────────────────
    @comissao.command(
        name="live",
        description="Define a taxa de comissão para o modo contra (influencer live)",
    )
    @app_commands.describe(
        fixed_threshold="Valor máximo para taxa fixa (ex: 20.0)",
        fixed_fee="Taxa fixa por jogador abaixo do threshold (ex: 2.0)",
        pct="Percentual cobrado acima do threshold, entre 0 e 1 (ex: 0.10 = 10%)",
    )
    async def live_cmd(
        self,
        interaction: discord.Interaction,
        fixed_threshold: float,
        fixed_fee: float,
        pct: float,
    ):
        if not (0 < pct < 1):
            await interaction.response.send_message(
                "❌ `pct` deve estar entre 0 e 1 (ex: 0.10 para 10%).",
                ephemeral=True,
            )
            return
        if fixed_fee < 0 or fixed_threshold < 0:
            await interaction.response.send_message(
                "❌ Valores não podem ser negativos.", ephemeral=True)
            return

        scheme = await commission_service.update_live(
            guild_id=str(interaction.guild_id),
            fixed_threshold=fixed_threshold,
            fixed_fee=fixed_fee,
            pct=pct,
        )
        embed = discord.Embed(
            title="✅ Comissão Live Atualizada",
            color=THEME,
        )
        for name, value in _scheme_fields(scheme, "Live"):
            embed.add_field(name=name, value=value, inline=True)
        logger.info(
            f"[CommissionCog] live atualizado por {interaction.user} "
            f"guild={interaction.guild_id} scheme={scheme}"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /comissao reset ───────────────────────────────────────────────────────
    reset_group = app_commands.Group(
        name="reset",
        description="Restaura os valores padrão de comissão",
        parent=comissao,  # type: ignore[arg-type]
    )

    @reset_group.command(name="match", description="Restaura os defaults de comissão do match")
    async def reset_match(self, interaction: discord.Interaction):
        scheme = await commission_service.reset_match(str(interaction.guild_id))
        embed = discord.Embed(
            title="🔄 Comissão Match Restaurada",
            color=THEME,
        )
        for name, value in _scheme_fields(scheme, "Match"):
            embed.add_field(name=name, value=value, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @reset_group.command(name="live", description="Restaura os defaults de comissão do live")
    async def reset_live(self, interaction: discord.Interaction):
        scheme = await commission_service.reset_live(str(interaction.guild_id))
        embed = discord.Embed(
            title="🔄 Comissão Live Restaurada",
            color=THEME,
        )
        for name, value in _scheme_fields(scheme, "Live"):
            embed.add_field(name=name, value=value, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommissionCog(bot))
    logger.info("[CommissionCog] carregado.")
