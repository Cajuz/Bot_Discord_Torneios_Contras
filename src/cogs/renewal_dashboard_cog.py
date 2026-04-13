"""
renewal_dashboard_cog.py

Painel financeiro e operacional de contratos de mediadores — apenas ADM.

Canais:
  #painel-contratos   — embed fixo com resumo financeiro + botões de ação
  #analytics-adm      — dashboard detalhado (atualizado pelo task diário)

Comandos:
  !setup_painel_contratos   — posta/atualiza o card fixo
  !atualizar_contratos      — força atualização manual

Task:
  A cada 6 horas atualiza automaticamente o painel.
"""
from __future__ import annotations

import discord
from discord.ext import commands, tasks
from utils.logger import logger
from utils.datetime_utils import utcnow
from services.channel_service import CONTROLLER_ROLE_NAME

THEME_COLOR      = 0xFFD54F
DANGER_COLOR     = 0xE74C3C
SUCCESS_COLOR    = 0x27AE60
INFO_COLOR       = 0x3498DB

PAINEL_CONTRATOS_CHANNEL = "painel-contratos"
ANALYTICS_ADM_CHANNEL    = "analytics-adm"


# ═══════════════════════════════════════════════════════════════
# Helpers — consultas ao banco
# ═══════════════════════════════════════════════════════════════

async def _fetch_contract_stats() -> dict:
    """Retorna estatísticas consolidadas de contratos/renovações."""
    from config.database import db
    from datetime import timedelta

    now = utcnow()
    col_med = db.get_collection("mediators")
    col_ren = db.get_collection("mediator_renewals")
    col_app = db.get_collection("mediator_applications")

    ativos        = await col_med.count_documents({"is_active": True})
    inativos      = await col_med.count_documents({"is_active": False})
    vencendo_3d   = await col_med.count_documents({
        "expiration_date": {"$gte": now, "$lte": now + timedelta(days=3)},
        "is_active": True,
    })
    vencendo_7d   = await col_med.count_documents({
        "expiration_date": {"$gte": now, "$lte": now + timedelta(days=7)},
        "is_active": True,
    })
    pendentes_app = await col_app.count_documents({"status": "pendente"})

    # Financeiro — renovações pagas
    semana_inicio = now - timedelta(days=7)
    mes_inicio    = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    pipeline_semana = [
        {"$match": {"status": "CONCLUIDA", "paid_at": {"$gte": semana_inicio}}},
        {"$group": {"_id": None, "total": {"$sum": "$value"}, "count": {"$sum": 1}}},
    ]
    pipeline_mes = [
        {"$match": {"status": "CONCLUIDA", "paid_at": {"$gte": mes_inicio}}},
        {"$group": {"_id": None, "total": {"$sum": "$value"}, "count": {"$sum": 1}}},
    ]

    res_semana = await col_ren.aggregate(pipeline_semana).to_list(1)
    res_mes    = await col_ren.aggregate(pipeline_mes).to_list(1)

    receita_semana = res_semana[0]["total"] if res_semana else 0.0
    renovacoes_semana = res_semana[0]["count"] if res_semana else 0
    receita_mes    = res_mes[0]["total"] if res_mes else 0.0
    renovacoes_mes = res_mes[0]["count"] if res_mes else 0

    # Lista mediadores que vencem nos próximos 7 dias
    proximos_vencer = await col_med.find(
        {"expiration_date": {"$gte": now, "$lte": now + timedelta(days=7)}, "is_active": True},
        {"user_id": 1, "username": 1, "expiration_date": 1},
    ).sort("expiration_date", 1).to_list(10)

    return {
        "ativos":            ativos,
        "inativos":          inativos,
        "vencendo_3d":       vencendo_3d,
        "vencendo_7d":       vencendo_7d,
        "pendentes_app":     pendentes_app,
        "receita_semana":    receita_semana,
        "renovacoes_semana": renovacoes_semana,
        "receita_mes":       receita_mes,
        "renovacoes_mes":    renovacoes_mes,
        "proximos_vencer":   proximos_vencer,
    }


# ═══════════════════════════════════════════════════════════════
# Builders de embed
# ═══════════════════════════════════════════════════════════════

def _build_painel_embed(stats: dict) -> discord.Embed:
    """Embed resumido para o card fixo #painel-contratos."""
    e = discord.Embed(
        title="📊  Painel de Contratos — Mediadores",
        description="Visão geral financeira e operacional. Atualizado automaticamente a cada 6h.",
        color=THEME_COLOR,
        timestamp=utcnow(),
    )

    # Operacional
    e.add_field(
        name="👥 Mediadores",
        value=(
            f"Ativos: **{stats['ativos']}**\n"
            f"Inativos: **{stats['inativos']}**\n"
            f"Candidaturas pendentes: **{stats['pendentes_app']}**"
        ),
        inline=True,
    )
    e.add_field(
        name="⏳ Vencimentos",
        value=(
            f"Vencem em 3 dias: **{stats['vencendo_3d']}**\n"
            f"Vencem em 7 dias: **{stats['vencendo_7d']}**"
        ),
        inline=True,
    )

    # Financeiro
    e.add_field(
        name="💰 Receita — Semana",
        value=(
            f"R$ **{stats['receita_semana']:.2f}**\n"
            f"Renovações: **{stats['renovacoes_semana']}**"
        ),
        inline=True,
    )
    e.add_field(
        name="📅 Receita — Mês atual",
        value=(
            f"R$ **{stats['receita_mes']:.2f}**\n"
            f"Renovações: **{stats['renovacoes_mes']}**"
        ),
        inline=True,
    )

    # Próximos vencimentos
    if stats["proximos_vencer"]:
        linhas = []
        for doc in stats["proximos_vencer"][:5]:
            exp = doc.get("expiration_date")
            exp_str = exp.strftime("%d/%m") if exp else "—"
            nome    = doc.get("username", "—")
            uid     = doc.get("user_id", "")
            linhas.append(f"<@{uid}> **{nome}** → `{exp_str}`")
        e.add_field(
            name="🔔 Próximos a vencer (7 dias)",
            value="\n".join(linhas),
            inline=False,
        )

    e.set_footer(text="X1 Frifas · Painel de Contratos · Apenas ADM")
    return e


def _build_analytics_embed(stats: dict) -> discord.Embed:
    """Embed detalhado para #analytics-adm."""
    e = discord.Embed(
        title="📈  Analytics — Contratos & Renovações",
        color=INFO_COLOR,
        timestamp=utcnow(),
    )

    total_mediadores = stats["ativos"] + stats["inativos"] or 1
    taxa_ativa = (stats["ativos"] / total_mediadores) * 100

    e.add_field(
        name="🧮 Base de mediadores",
        value=(
            f"Total cadastrados: **{total_mediadores}**\n"
            f"Ativos: **{stats['ativos']}** ({taxa_ativa:.0f}%)\n"
            f"Inativos / Expirados: **{stats['inativos']}**"
        ),
        inline=False,
    )
    e.add_field(
        name="💸 Financeiro semanal",
        value=(
            f"Renovações pagas: **{stats['renovacoes_semana']}**\n"
            f"Receita: **R$ {stats['receita_semana']:.2f}**\n"
            f"Ticket médio: **R$ {(stats['receita_semana'] / stats['renovacoes_semana']):.2f}**"
            if stats['renovacoes_semana'] else
            "Renovações pagas: **0**\nReceita: **R$ 0,00**"
        ),
        inline=True,
    )
    e.add_field(
        name="📅 Financeiro mensal",
        value=(
            f"Renovações pagas: **{stats['renovacoes_mes']}**\n"
            f"Receita: **R$ {stats['receita_mes']:.2f}**\n"
            f"Ticket médio: **R$ {(stats['receita_mes'] / stats['renovacoes_mes']):.2f}**"
            if stats['renovacoes_mes'] else
            "Renovações pagas: **0**\nReceita: **R$ 0,00**"
        ),
        inline=True,
    )
    e.add_field(
        name="⏳ Alertas de vencimento",
        value=(
            f"Vencem em 3 dias: **{stats['vencendo_3d']}** {'⚠️' if stats['vencendo_3d'] else '✅'}\n"
            f"Vencem em 7 dias: **{stats['vencendo_7d']}**\n"
            f"Candidaturas pendentes: **{stats['pendentes_app']}**"
        ),
        inline=False,
    )

    if stats["proximos_vencer"]:
        linhas = []
        for doc in stats["proximos_vencer"]:
            exp     = doc.get("expiration_date")
            exp_str = exp.strftime("%d/%m/%Y") if exp else "—"
            nome    = doc.get("username", "—")
            uid     = doc.get("user_id", "")
            linhas.append(f"`{exp_str}` — <@{uid}> {nome}")
        e.add_field(
            name="📋 Lista — vencimentos próximos",
            value="\n".join(linhas),
            inline=False,
        )

    e.set_footer(text="X1 Frifas · Analytics · Apenas ADM")
    return e


# ═══════════════════════════════════════════════════════════════
# View — botões de ação no painel
# ═══════════════════════════════════════════════════════════════

class ContractPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔄 Atualizar",
        style=discord.ButtonStyle.secondary,
        custom_id="contracts:refresh",
    )
    async def refresh(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Sem permissão.", ephemeral=True)
            return
        await interaction.response.defer()
        stats = await _fetch_contract_stats()
        await interaction.message.edit(embed=_build_painel_embed(stats), view=self)

    @discord.ui.button(
        label="📋 Ver pendentes",
        style=discord.ButtonStyle.primary,
        custom_id="contracts:pending",
    )
    async def ver_pendentes(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Sem permissão.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            from config.database import db
            docs = await db.get_collection("mediator_applications").find(
                {"status": "pendente"}
            ).sort("submitted_at", -1).to_list(20)
        except Exception:
            docs = []

        if not docs:
            await interaction.followup.send("Nenhuma candidatura pendente.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📋 Candidaturas Pendentes",
            color=THEME_COLOR,
            timestamp=utcnow(),
        )
        for doc in docs:
            nome  = doc.get("nome_completo", "—")
            cpf   = doc.get("cpf", "—")
            data  = doc.get("submitted_at")
            data_str = data.strftime("%d/%m/%Y %H:%M") if data else "—"
            embed.add_field(
                name=nome,
                value=f"CPF: ||{cpf}|| | Enviado: `{data_str}`",
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)


# ═══════════════════════════════════════════════════════════════
# Cog
# ═══════════════════════════════════════════════════════════════

class RenewalDashboardCog(commands.Cog, name="PainelContratos"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._painel_message_id:    int | None = None
        self._analytics_message_id: int | None = None
        if not self.auto_refresh.is_running():
            self.auto_refresh.start()

    # ── Task 6h ──────────────────────────────────────────────
    @tasks.loop(hours=6)
    async def auto_refresh(self):
        for guild in self.bot.guilds:
            await self._update_panels(guild)

    @auto_refresh.before_loop
    async def before_auto_refresh(self):
        await self.bot.wait_until_ready()

    # ── Helpers internos ──────────────────────────────────────
    async def _update_panels(self, guild: discord.Guild):
        try:
            stats = await _fetch_contract_stats()
        except Exception as e:
            logger.error(f"[RenewalDashboard] fetch stats error: {e}")
            return

        # Painel de contratos
        ch_painel = discord.utils.get(guild.text_channels, name=PAINEL_CONTRATOS_CHANNEL)
        if ch_painel:
            await self._upsert_message(
                ch_painel,
                embed=_build_painel_embed(stats),
                view=ContractPanelView(),
                attr="_painel_message_id",
            )

        # Analytics ADM
        ch_analytics = discord.utils.get(guild.text_channels, name=ANALYTICS_ADM_CHANNEL)
        if ch_analytics:
            await self._upsert_message(
                ch_analytics,
                embed=_build_analytics_embed(stats),
                view=None,
                attr="_analytics_message_id",
            )

    async def _upsert_message(
        self,
        channel: discord.TextChannel,
        embed: discord.Embed,
        view: discord.ui.View | None,
        attr: str,
    ):
        """Edita msg existente ou posta nova."""
        msg_id = getattr(self, attr, None)
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed, view=view)
                return
            except (discord.NotFound, discord.HTTPException):
                pass
        kwargs = {"embed": embed}
        if view:
            kwargs["view"] = view
        msg = await channel.send(**kwargs)
        setattr(self, attr, msg.id)

    # ── Comandos ────────────────────────────────────────────
    @commands.command(name="setup_painel_contratos")
    @commands.has_permissions(administrator=True)
    async def setup_painel_contratos(self, ctx: commands.Context):
        """Posta o painel de contratos e o analytics. Só ADM."""
        msg = await ctx.reply("⏳ Gerando painéis de contratos...")
        await self._update_panels(ctx.guild)
        await msg.edit(content="✅ Painéis de contratos atualizados.")

    @commands.command(name="atualizar_contratos")
    @commands.has_permissions(administrator=True)
    async def atualizar_contratos(self, ctx: commands.Context):
        """Força atualização manual imediata."""
        await ctx.reply("⏳ Atualizando...")
        await self._update_panels(ctx.guild)
        await ctx.reply("✅ Painéis atualizados.")

    @commands.command(name="resumo_financeiro")
    @commands.has_permissions(administrator=True)
    async def resumo_financeiro(self, ctx: commands.Context):
        """Envia resumo financeiro diretamente no chat (ephemeral-style)."""
        stats = await _fetch_contract_stats()
        await ctx.reply(embed=_build_analytics_embed(stats))


async def setup(bot: commands.Bot):
    await bot.add_cog(RenewalDashboardCog(bot))
