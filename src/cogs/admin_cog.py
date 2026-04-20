# admin_cog.py — Comandos administrativos.
import discord
from discord.ext import commands
from utils.logger import logger
from utils.datetime_utils import utcnow

THEME_COLOR = 0xFFD54F


class AdminCog(commands.Cog, name="Admin"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─────────────────────────────────────────
    # SETUP COMPLETO
    # ─────────────────────────────────────────

    @commands.command(name="setupcanais")
    @commands.has_permissions(administrator=True)
    async def setupcanais(self, ctx: commands.Context):
        """Configura todos os canais, painéis e dashboards do servidor."""
        msg = await ctx.reply("⏳ Configurando servidor...\nIsso pode levar alguns segundos.")
        try:
            from services.channel_setup_service import channel_setup_service
            channel_setup_service.bot = self.bot
            result = await channel_setup_service.setup_all(ctx.guild)
            await msg.edit(content=f"✅ **Setup concluído!**\n{result}")
        except Exception as e:
            logger.error(f"[setupcanais] {e}")
            await msg.edit(content=f"❌ Erro durante o setup: {e}")

    # ─────────────────────────────────────────
    # SETUP INDIVIDUAIS — painéis base
    # ─────────────────────────────────────────

    @commands.command(name="setup_faturamento")
    @commands.has_permissions(administrator=True)
    async def setup_faturamento(self, ctx: commands.Context):
        from services.channel_setup_service import channel_setup_service
        await channel_setup_service.setup_faturamento(ctx.guild)
        await ctx.reply("✅ Painel de faturamento postado.")

    @commands.command(name="setup_guias")
    @commands.has_permissions(administrator=True)
    async def setup_guias(self, ctx: commands.Context):
        from services.channel_setup_service import channel_setup_service
        await ctx.reply("⏳ Postando guias...")
        await channel_setup_service.setup_guide_channels(ctx.guild)
        await ctx.reply("✅ Guias atualizados.")

    @commands.command(name="setup_suporte")
    @commands.has_permissions(administrator=True)
    async def setup_suporte(self, ctx: commands.Context):
        from services.channel_setup_service import channel_setup_service
        await channel_setup_service.setup_suporte(ctx.guild)
        await ctx.reply("✅ Painéis de suporte postados.")

    @commands.command(name="setup_mediador")
    @commands.has_permissions(administrator=True)
    async def setup_mediador(self, ctx: commands.Context):
        from services.channel_setup_service import channel_setup_service
        await channel_setup_service.setup_mediador(ctx.guild)
        await ctx.reply("✅ Painéis de mediador postados.")

    @commands.command(name="setup_quero_ser_mediador")
    @commands.has_permissions(administrator=True)
    async def setup_quero_ser_mediador(self, ctx: commands.Context):
        from views.quero_ser_mediador_view import PedidoMediadorView, PedidomediadorEmbed
        from services.channel_service import SOLICITACOES_CHANNEL
        ch = discord.utils.get(ctx.guild.text_channels, name=SOLICITACOES_CHANNEL)
        if not ch:
            await ctx.reply(f"Canal `#{SOLICITACOES_CHANNEL}` não encontrado.")
            return
        await ch.send(embed=PedidomediadorEmbed.beneficios(), view=PedidoMediadorView())
        await ctx.reply(f"✅ Painel de candidatura postado em {ch.mention}.")

    @commands.command(name="setup_influencers")
    @commands.has_permissions(administrator=True)
    async def setup_influencers(self, ctx: commands.Context):
        from services.channel_setup_service import channel_setup_service
        await channel_setup_service.setup_influencers(ctx.guild)
        await ctx.reply("✅ Painéis de influencers postados.")

    @commands.command(name="setup_pix")
    @commands.has_permissions(administrator=True)
    async def setup_pix(self, ctx: commands.Context):
        from services.channel_setup_service import channel_setup_service
        await channel_setup_service.setup_pix(ctx.guild)
        await ctx.reply("✅ Painel PIX postado.")

    @commands.command(name="setup_renovacao")
    @commands.has_permissions(administrator=True)
    async def setup_renovacao(self, ctx: commands.Context):
        from services.channel_setup_service import channel_setup_service
        await channel_setup_service.setup_renovacao(ctx.guild)
        await ctx.reply("✅ Painel de renovação postado.")

    @commands.command(name="setup_partidas")
    @commands.has_permissions(administrator=True)
    async def setup_partidas(self, ctx: commands.Context):
        from services.channel_setup_service import channel_setup_service
        msg = await ctx.reply("⏳ Postando cards de partida...")
        await channel_setup_service.setup_match_cards(ctx.guild)
        await msg.edit(content="✅ Cards de partida postados em todos os canais.")

    @commands.command(name="setup_dashboards")
    @commands.has_permissions(administrator=True)
    async def setup_dashboards(self, ctx: commands.Context):
        """Atualiza os dashboards de analytics (partidas, mediadores, ranking, suporte)."""
        from services.channel_setup_service import channel_setup_service
        msg = await ctx.reply("⏳ Atualizando dashboards...")
        channel_setup_service.bot = self.bot
        await channel_setup_service.setup_dashboards(ctx.guild)
        await msg.edit(content="✅ Todos os dashboards atualizados.")

    # ─────────────────────────────────────────
    # SETUP INDIVIDUAIS — novos painéis
    # ─────────────────────────────────────────

    @commands.command(name="setup_avisos")
    @commands.has_permissions(administrator=True)
    async def setup_avisos(self, ctx: commands.Context):
        from services.channel_setup_service import channel_setup_service
        await channel_setup_service.setup_avisos(ctx.guild)
        await ctx.reply("✅ Painel de avisos postado.")

    @commands.command(name="setup_aprovar_mediadores")
    @commands.has_permissions(administrator=True)
    async def setup_aprovar_mediadores(self, ctx: commands.Context):
        from services.channel_setup_service import channel_setup_service
        await channel_setup_service.setup_aprovar_mediadores(ctx.guild)
        await ctx.reply("✅ Painel de aprovação de mediadores postado.")

    @commands.command(name="setup_historico_exposed")
    @commands.has_permissions(administrator=True)
    async def setup_historico_exposed(self, ctx: commands.Context):
        from services.channel_setup_service import channel_setup_service
        await channel_setup_service.setup_historico_exposed(ctx.guild)
        await ctx.reply("✅ Painel de histórico da blacklist postado.")

    @commands.command(name="setup_mediadores_afks")
    @commands.has_permissions(administrator=True)
    async def setup_mediadores_afks(self, ctx: commands.Context):
        from services.channel_setup_service import channel_setup_service
        await channel_setup_service.setup_mediadores_afks(ctx.guild)
        await ctx.reply("✅ Painel de mediadores AFK postado.")

    @commands.command(name="setup_cadastro_mediador")
    @commands.has_permissions(administrator=True)
    async def setup_cadastro_mediador(self, ctx: commands.Context):
        """Posta o card fixo de cadastro de mediador com formulário modal."""
        from services.channel_setup_service import channel_setup_service
        await channel_setup_service.setup_cadastro_mediador(ctx.guild)
        await ctx.reply("✅ Card de cadastro de mediador postado.")

    @commands.command(name="setup_blacklist")
    @commands.has_permissions(administrator=True)
    async def setup_blacklist(self, ctx: commands.Context):
        """Posta o painel de verificação de blacklist no canal #blacklist."""
        from services.channel_setup_service import channel_setup_service
        await channel_setup_service.setup_blacklist(ctx.guild)
        await ctx.reply("✅ Painel de blacklist postado.")

    @commands.command(name="setup_alertas")
    @commands.has_permissions(administrator=True)
    async def setup_alertas(self, ctx: commands.Context):
        """Posta o painel informativo no canal #alertas-adm."""
        from services.channel_setup_service import channel_setup_service
        await channel_setup_service.setup_alertas_adm(ctx.guild)
        await ctx.reply("✅ Painel de alertas postado em #alertas-adm.")

    # ─────────────────────────────────────────
    # CONTRATOS (delegado ao renewal_dashboard_cog)
    # ─────────────────────────────────────────

    @commands.command(name="setup_painel_contratos")
    @commands.has_permissions(administrator=True)
    async def setup_painel_contratos(self, ctx: commands.Context):
        """Posta/atualiza os painéis financeiros de contratos de mediadores."""
        cog = self.bot.cogs.get("PainelContratos")
        if not cog:
            await ctx.reply("❌ Cog PainelContratos não carregado.")
            return
        msg = await ctx.reply("⏳ Gerando painéis de contratos...")
        await cog._update_panels(ctx.guild)
        await msg.edit(content="✅ Painéis de contratos atualizados.")

    # ─────────────────────────────────────────
    # OPERACIONAL
    # ─────────────────────────────────────────

    @commands.command(name="healthcheck")
    @commands.has_permissions(administrator=True)
    async def healthcheck(self, ctx: commands.Context):
        """Exibe o health check completo do bot (banco, filas, latência)."""
        from views.health_check_view import build_overview_embed, HealthCheckView
        from main import BOT_START_TIME
        embed = await build_overview_embed(self.bot, BOT_START_TIME)
        view  = HealthCheckView(bot=self.bot, start_time=BOT_START_TIME)
        await ctx.reply(embed=embed, view=view)

    @commands.command(name="stats")
    @commands.has_permissions(manage_messages=True)
    async def stats(self, ctx: commands.Context, member: discord.Member = None):
        """Exibe relatório completo de um membro (partidas, blacklist, contrato, tickets)."""
        target = member or ctx.author
        is_admin    = ctx.author.guild_permissions.administrator
        is_analyst  = bool({r.name for r in ctx.author.roles} & {"Analista", "Analyst", "Controller"})
        if not is_admin and not is_analyst and target.id != ctx.author.id:
            await ctx.reply("❌ Você só pode consultar o seu próprio perfil.")
            return

        msg = await ctx.reply("⏳ Buscando dados...")
        try:
            from services.stats_service import stats_service
            s = await stats_service.get(str(target.id))

            cor = 0xFF0000 if s.na_blacklist else (0xFFD54F if s.e_mediador else 0x2ECC71)
            embed = discord.Embed(
                title=f"📊 Perfil — {target.display_name}",
                color=cor,
                timestamp=utcnow(),
            )
            embed.set_thumbnail(url=target.display_avatar.url)

            if s.tags:
                embed.add_field(name="Status", value="  ".join(s.tags), inline=False)

            embed.add_field(
                name="🎮 Partidas",
                value=(
                    f"Total: **{s.total_partidas}**\n"
                    f"Vitórias: **{s.partidas_ganhas}** · Derrotas: **{s.partidas_perdidas}**\n"
                    f"Canceladas: **{s.partidas_canceladas}** · Win Rate: **{s.win_rate}%**"
                ),
                inline=True,
            )

            embed.add_field(
                name="💰 Financeiro",
                value=(
                    f"Apostado: **R$ {s.valor_apostado_total:.2f}**\n"
                    f"Ganho: **R$ {s.valor_ganho_total:.2f}**"
                ),
                inline=True,
            )

            if s.na_blacklist:
                embed.add_field(
                    name="🚫 Blacklist",
                    value=(
                        f"Motivo: {s.blacklist_motivo}\n"
                        f"Data: {s.blacklist_data}\n"
                        f"Por: {s.blacklist_adicionado_por or 'N/A'}"
                    ),
                    inline=False,
                )
            else:
                embed.add_field(name="✅ Blacklist", value="Não está na blacklist.", inline=False)

            if s.e_mediador:
                embed.add_field(
                    name="🎖️ Contrato",
                    value=(
                        f"Status: **{s.contrato_status}**\n"
                        f"Vence: **{s.contrato_vence or 'N/A'}**\n"
                        f"PIX: {'✅ Cadastrado' if s.pix_cadastrado else '⚠️ Não cadastrado'}"
                    ),
                    inline=True,
                )

            if s.tickets_abertos or s.tickets_fechados:
                embed.add_field(
                    name="🎫 Tickets",
                    value=f"Abertos: **{s.tickets_abertos}** · Fechados: **{s.tickets_fechados}**",
                    inline=True,
                )

            if s.spam_bloqueado:
                embed.add_field(
                    name="🔇 Bloqueio Anti-Spam",
                    value=f"Motivo: {s.spam_motivo or 'Não informado'}",
                    inline=False,
                )

            embed.set_footer(text=f"ID: {target.id} · X1 Frifas")
            await msg.edit(content=None, embed=embed)
        except Exception as e:
            logger.error(f"[stats] {e}", exc_info=True)
            await msg.edit(content=f"❌ Erro ao buscar dados: {e}")

    @commands.command(name="faturamento")
    async def faturamento(self, ctx: commands.Context, member: discord.Member = None):
        """Exibe o relatório de faturamento de um mediador. ADM pode ver qualquer um."""
        from services.faturamento_mediador import FaturamentoMediadorService, FaturamentoView
        target = member or ctx.author
        is_admin = ctx.author.guild_permissions.administrator
        is_mediator = bool({r.name for r in ctx.author.roles} & {"Controller", "Mediador", "Mediator"})
        if not is_admin and not is_mediator:
            await ctx.reply("❌ Apenas mediadores ou administradores podem usar este comando.")
            return
        if not is_admin and target.id != ctx.author.id:
            await ctx.reply("❌ Você só pode ver o seu próprio faturamento.")
            return
        service = FaturamentoMediadorService()
        partidas = await service.buscar_partidas_do_banco(str(target.id))
        if not partidas:
            await ctx.reply(f"❌ Nenhuma partida encontrada para {target.mention}.")
            return
        avatar_url = target.display_avatar.url if target.display_avatar else None
        view = FaturamentoView(
            service=service, partidas=partidas, mediador_id=int(target.id),
            nome_mediador=target.name, avatar_url=avatar_url
        )
        embed = await view.gerar_embed(1)
        await ctx.reply(embed=embed, view=view)

    @commands.command(name="verpix")
    @commands.has_permissions(administrator=True)
    async def verpix(self, ctx: commands.Context, member: discord.Member = None):
        """Exibe a chave PIX e QR Code de um mediador."""
        try:
            from services.pix_mediador import PixQRCode
            from config.database import db
            target = member or ctx.author
            is_admin = ctx.author.guild_permissions.administrator
            is_mediator = bool({r.name for r in ctx.author.roles} & {"Controller", "Mediador", "Mediator"})
            if not is_admin and not is_mediator:
                await ctx.reply("❌ Apenas mediadores e administradores podem usar este comando.")
                return
            if not is_admin and target.id != ctx.author.id:
                await ctx.reply("❌ Apenas administradores podem ver o PIX de outros usuários.")
                return
            collection = db.get_collection("mediator_pix")
            doc = await collection.find_one({"discord_id": str(target.id)})
            if not doc:
                await ctx.reply(f"❌ {target.mention} não tem chave PIX cadastrada.")
                return
            pix_key = doc["pix_key"]
            qr = PixQRCode(pix_key)
            buffer = qr.generate_qrcode()
            file = discord.File(buffer, filename="pix.png")
            embed = discord.Embed(title="💳 Pagamento via PIX", color=THEME_COLOR)
            embed.add_field(name="Mediador", value=target.mention, inline=True)
            embed.add_field(name="Chave PIX", value=f"`{pix_key}`", inline=True)
            embed.set_image(url="attachment://pix.png")
            await ctx.reply(embed=embed, file=file)
        except Exception as e:
            await ctx.send(f"❌ ERRO: {e}")

    # ─────────────────────────────────────────
    # AJUDA
    # ─────────────────────────────────────────

    @commands.command(name="help_adm")
    @commands.has_permissions(administrator=True)
    async def help_adm(self, ctx: commands.Context):
        """Lista todos os comandos disponíveis para ADM/Controller."""
        embed = discord.Embed(
            title="📋 Comandos Admin — X1 Frifas",
            description="Prefixo: `!`  |  Slash: `/`",
            color=THEME_COLOR,
        )
        embed.add_field(name="🔧 Setup completo", value="`!setupcanais`", inline=False)
        embed.add_field(
            name="🛠️ Setup individual — painéis base",
            value=(
                "`!setup_guias`  `!setup_suporte`  `!setup_mediador`\n"
                "`!setup_influencers`  `!setup_pix`  `!setup_renovacao`\n"
                "`!setup_quero_ser_mediador`  `!setup_partidas`\n"
                "`!setup_dashboards`  `!setup_faturamento`"
            ),
            inline=False,
        )
        embed.add_field(
            name="🆕 Setup individual — novos painéis",
            value=(
                "`!setup_avisos`  `!setup_aprovar_mediadores`\n"
                "`!setup_historico_exposed`  `!setup_mediadores_afks`\n"
                "`!setup_cadastro_mediador`  `!setup_blacklist`\n"
                "`!setup_alertas`"
            ),
            inline=False,
        )
        embed.add_field(
            name="💰 Contratos & Finance",
            value="`!setup_painel_contratos`  `!resumo_financeiro`",
            inline=False,
        )
        embed.add_field(
            name="🚫 Moderação (slash)",
            value=(
                "`/aviso`  `/ban`  `/kick`  `/timeout`  `/untimeout`\n"
                "`/unban`  `/warn`  `/silence`  `/bloquear`  `/desbloquear`  `/limpar`"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚙️ Operacional",
            value="`!healthcheck`  `!verpix [@m]`  `!faturamento [@m]`  `!stats [@m]`",
            inline=False,
        )
        embed.add_field(
            name="👥 Mediadores → mediator_cog",
            value="`!addmediador @m`  `!removemediador @m`  `!fila`",
            inline=False,
        )
        embed.add_field(
            name="🔍 Analistas → analyst_cog",
            value="`!setup_analise`  `!setup_exposed`  `/blacklist_add`  `/blacklist_remove`",
            inline=False,
        )
        embed.add_field(
            name="🎫 Suporte → support_cog",
            value="`!criar_canal_suporte @m`",
            inline=False,
        )
        embed.set_footer(text="X1 Frifas · Apenas ADM/Controller")
        await ctx.reply(embed=embed)

    # ─────────────────────────────────────────
    # ERROR HANDLER
    # ─────────────────────────────────────────

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("❌ Sem permissão para este comando.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply("❌ Membro não encontrado.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f"❌ Argumento obrigatório faltando: `{error.param.name}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))