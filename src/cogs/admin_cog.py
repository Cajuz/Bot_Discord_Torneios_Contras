"""
AdminCog — Comandos administrativos.
"""
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
    # SETUP INDIVIDUAIS
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
        from services.channel_setup_service import channel_setup_service
        msg = await ctx.reply("⏳ Atualizando dashboards...")
        channel_setup_service.bot = self.bot
        await channel_setup_service.setup_dashboards(ctx.guild)
        await msg.edit(content="✅ Todos os dashboards atualizados.")

    # ─────────────────────────────────────────
    # MODERAÇÃO
    # ─────────────────────────────────────────
    @commands.command(name="bloquear")
    @commands.has_permissions(manage_messages=True)
    async def bloquear(self, ctx: commands.Context, member: discord.Member, *, motivo: str = "Bloqueado manualmente"):
        from config.anti_spam_config import AntiSpamConfig
        from config.database import db
        blocked_role = discord.utils.get(ctx.guild.roles, name=AntiSpamConfig.SPAM_BLOCK_ROLE_NAME)
        if not blocked_role:
            blocked_role = await ctx.guild.create_role(name=AntiSpamConfig.SPAM_BLOCK_ROLE_NAME)
        await member.add_roles(blocked_role, reason=motivo)
        await db.get_collection("users").update_one(
            {"discord_id": str(member.id)},
            {"$set": {"spam_blocked": True, "spam_blocked_at": utcnow(), "spam_block_reason": motivo}},
            upsert=True
        )
        await ctx.reply(f"✅ {member.mention} bloqueado. Motivo: *{motivo}*")

    @commands.command(name="desbloquear")
    @commands.has_permissions(manage_messages=True)
    async def desbloquear(self, ctx: commands.Context, member: discord.Member):
        from config.anti_spam_config import AntiSpamConfig
        from config.database import db
        blocked_role = discord.utils.get(ctx.guild.roles, name=AntiSpamConfig.SPAM_BLOCK_ROLE_NAME)
        if blocked_role and blocked_role in member.roles:
            await member.remove_roles(blocked_role)
        await db.get_collection("users").update_one(
            {"discord_id": str(member.id)},
            {"$set": {"spam_blocked": False, "spam_unblocked_at": utcnow(),
                      "spam_unblocked_by": str(ctx.author.id)}}
        )
        await ctx.reply(f"✅ {member.mention} desbloqueado.")

    @commands.command(name="limpar")
    @commands.has_permissions(manage_messages=True)
    async def limpar(self, ctx: commands.Context, quantidade: int = 10):
        if not 1 <= quantidade <= 100:
            await ctx.reply("Informe um valor entre 1 e 100.")
            return
        deleted = await ctx.channel.purge(limit=quantidade + 1)
        await ctx.send(f"🧹 {len(deleted) - 1} mensagens removidas.", delete_after=5)

    # ─────────────────────────────────────────
    # OPERACIONAL
    # ─────────────────────────────────────────
    @commands.command(name="dashboard")
    @commands.has_permissions(administrator=True)
    async def dashboard(self, ctx: commands.Context):
        await ctx.reply("⏳ Atualizando dashboard de partidas...")
        try:
            from services.mediador_dashboard_service import mediator_dashboard_service
            channel = await mediator_dashboard_service.resolve_dashboard_channel(ctx.guild)
            if not channel:
                await ctx.reply("Canal não encontrado. Use `!setupcanais` primeiro.")
                return
            await mediator_dashboard_service.update_dashboard_for_channel(channel)
            await ctx.reply(f"✅ Dashboard atualizado em {channel.mention}.")
        except Exception as e:
            logger.error(f"[dashboard] {e}")
            await ctx.reply("❌ Erro ao atualizar dashboard.")

    @commands.command(name="atualizar_dashboards")
    @commands.has_permissions(administrator=True)
    async def atualizar_dashboards(self, ctx: commands.Context):
        from services.channel_setup_service import channel_setup_service
        msg = await ctx.reply("⏳ Atualizando todos os dashboards...")
        channel_setup_service.bot = self.bot
        await channel_setup_service.setup_dashboards(ctx.guild)
        await msg.edit(content="✅ Todos os dashboards atualizados.")

    @commands.command(name="healthcheck")
    @commands.has_permissions(administrator=True)
    async def healthcheck(self, ctx: commands.Context):
        from views.health_check_view import build_overview_embed, HealthCheckView
        from main import BOT_START_TIME
        embed = await build_overview_embed(self.bot, BOT_START_TIME)
        view  = HealthCheckView(bot=self.bot, start_time=BOT_START_TIME)
        await ctx.reply(embed=embed, view=view)

    @commands.command(name="verpix")
    async def verpix(self, ctx: commands.Context, member: discord.Member = None):
        from config.database import db
        target      = member or ctx.author
        is_admin    = ctx.author.guild_permissions.administrator
        is_mediator = bool({r.name for r in ctx.author.roles} & {"Controller", "Mediador", "Mediator"})
        if not is_admin and not is_mediator:
            await ctx.reply("Apenas mediadores e administradores podem usar este comando.")
            return
        doc = await db.get_collection("mediator_pix").find_one({"discord_id": str(target.id)})
        if not doc:
            await ctx.reply(f"{target.mention} não tem chave PIX cadastrada.")
            return
        embed = discord.Embed(title="Chave PIX", color=THEME_COLOR)
        embed.add_field(name="Mediador", value=target.mention,        inline=True)
        embed.add_field(name="Chave",    value=f"`{doc['pix_key']}`", inline=True)
        await ctx.reply(embed=embed)

    # ─────────────────────────────────────────
    # AJUDA
    # ─────────────────────────────────────────
    @commands.command(name="help_adm")
    @commands.has_permissions(administrator=True)
    async def help_adm(self, ctx: commands.Context):
        embed = discord.Embed(title="Comandos Admin", color=THEME_COLOR)
        embed.add_field(name="Setup completo", value="`!setupcanais`", inline=False)
        embed.add_field(name="Setup individual", value=(
            "`!setup_guias`  `!setup_suporte`  `!setup_mediador`\n"
            "`!setup_influencers`  `!setup_pix`  `!setup_renovacao`\n"
            "`!setup_quero_ser_mediador`  `!setup_partidas`  `!setup_dashboards`\n"
            "`!setup_faturamento`"
        ), inline=False)
        embed.add_field(name="Moderação", value=(
            "`!bloquear @m motivo`  `!desbloquear @m`  `!limpar <n>`"
        ), inline=False)
        embed.add_field(name="Operacional", value=(
            "`!dashboard`  `!atualizar_dashboards`  `!healthcheck`  `!verpix @m`"
        ), inline=False)
        embed.add_field(name="Mediadores → mediator_cog", value=(
            "`!addmediador @m`  `!removemediador @m`  `!fila`  `/silence @m`"
        ), inline=False)
        embed.add_field(name="Analistas → analyst_cog", value=(
            "`!setup_analise`  `!setup_exposed`  `/blacklist_add`  `/blacklist_remove`"
        ), inline=False)
        embed.add_field(name="Suporte → support_cog", value=(
            "`!criar_canal_suporte @m`"
        ), inline=False)
        await ctx.reply(embed=embed)

    # ─────────────────────────────────────────
    # ERROR HANDLER
    # ─────────────────────────────────────────
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("Sem permissão para este comando.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply("Membro não encontrado.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f"Argumento obrigatório: `{error.param.name}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
