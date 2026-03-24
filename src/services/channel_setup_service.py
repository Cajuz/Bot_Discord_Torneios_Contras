# channel_setup_service.py
from __future__ import annotations
import discord
from views.imagens import get_banner_file
from utils.logger import logger, log_success
from services.channel_service import (
    CHANNEL_STRUCTURE, ALL_ROLES,
    GUIA_JOGADOR_CHANNEL, GUIA_MEDIADOR_CHANNEL,
    GUIA_SUPORTE_CHANNEL, GUIA_ANALISTA_CHANNEL,
    # Suporte
    SOLICITAR_SUPORTE_CHANNEL, SUPPORT_CHANNEL_NAME,
    CHAMADOS_CHANNEL_NAME, CHAT_SUPORTE_STAFF_CHANNEL,
    PAINEL_SUPORTE_CHANNEL, SUPORTE_ADMIN_CHANNEL,
    # Mediação
    MEDIADOR_PANEL_CHANNEL, MEDIADORES_ADMIN_CHANNEL,
    SOLICITACOES_CHANNEL, MEDIADOR_PIX_CHANNEL,
    RENOVACAO_CHANNEL, FATURAMENTO_CHANNEL,
    APROVAR_MEDIADORES_CHANNEL,
    HISTORICO_CHANNEL,
    # Analistas
    SOLICITAR_ANALISE_CHANNEL,
    CASOS_ANALISAR_CHANNEL,
    PAINEL_ANALISTA_CHANNEL, ANALYST_QUEUE_CHANNEL,
    ANALISTAS_ADMIN_CHANNEL,
    EXPOSED_CHANNEL_NAME,
    HISTORICO_EXPOSED_CHANNEL,
    CHAT_ANALISTAS_CHANNEL,
    # Comunidade
    INFLUENCERS_CHANNEL, INFLUENCERS_ADMIN_CHANNEL,
    SUPORTE_ADMIN_CHANNEL, STATUS_BOT_CHANNEL,LOGS_COMMAND_CHANNEL,
    FATURAMENTO_CHANNEL,LOGS_PIX_LOG_CHANNEL,LOGS_CALL_CHANNEL,LOGS_MESSAGE_DELETE_CHANNEL,
    LOGS_TROCA_CARGO_CHANNEL,HEALTH_CHECK_CHANNEL,    # ← adicionado
    permission_service,
)
from config.channels_config import ChannelsConfig


THEME = 0xFFD54F


class ChannelSetupService:

    def __init__(self):
        self.bot: discord.Client | None = None

    # ══════════════════════════════════════════════════════════
    # ENTRY POINT
    # ══════════════════════════════════════════════════════════

    async def setup_all(self, guild: discord.Guild) -> str:
        await self.setup_roles(guild)
        await self.setup_categories_and_channels(guild)
        await self.setup_guide_channels(guild)
        await self.setup_all_panels(guild)
        await self.setup_match_cards(guild)
        await self.setup_dashboards(guild)
        await self.setup_faturamento(guild)
        log_success(f"[ChannelSetup] Setup completo em {guild.name}")
        return f"Servidor **{guild.name}** configurado com sucesso."

    # ══════════════════════════════════════════════════════════
    # ROLES
    # ══════════════════════════════════════════════════════════

    async def setup_roles(self, guild: discord.Guild) -> dict[str, discord.Role]:
        existing = {r.name: r for r in guild.roles}
        roles = {}
        for name in ALL_ROLES:
            if name in existing:
                roles[name] = existing[name]
            else:
                role = await guild.create_role(name=name)
                roles[name] = role
                logger.info(f"[ChannelSetup] Cargo criado: {name}")
        return roles

    # ══════════════════════════════════════════════════════════
    # CATEGORIAS E CANAIS
    # ══════════════════════════════════════════════════════════

    async def setup_categories_and_channels(self, guild: discord.Guild):
        roles             = {r.name: r for r in guild.roles}
        existing_channels = {c.name: c for c in guild.channels}

        for category_name, channels in CHANNEL_STRUCTURE.items():
            category = discord.utils.get(guild.categories, name=category_name)
            if not category:
                ow       = await permission_service.get_category_overwrites(guild, category_name, roles)
                category = await guild.create_category(category_name, overwrites=ow)
                logger.info(f"[ChannelSetup] Categoria criada: {category_name}")

            for ch_name in channels:
                ow = await permission_service.get_channel_overwrites(guild, ch_name, roles)
                if ch_name in existing_channels:
                    try:
                        await existing_channels[ch_name].edit(overwrites=ow)
                    except Exception as e:
                        logger.warning(f"[ChannelSetup] Permissões #{ch_name}: {e}")
                else:
                    await guild.create_text_channel(ch_name, category=category, overwrites=ow)
                    logger.info(f"[ChannelSetup] Canal criado: #{ch_name}")

    # ══════════════════════════════════════════════════════════
    # GUIAS
    # ══════════════════════════════════════════════════════════

    async def setup_guide_channels(self, guild: discord.Guild):
        guides = {
            GUIA_JOGADOR_CHANNEL:  self._guide_player_embed(),
            GUIA_MEDIADOR_CHANNEL: self._guide_mediator_embed(),
            GUIA_SUPORTE_CHANNEL:  self._guide_support_embed(),
            GUIA_ANALISTA_CHANNEL: self._guide_analyst_embed(),
        }
        for ch_name, embed in guides.items():
            ch = discord.utils.get(guild.text_channels, name=ch_name)
            if not ch:
                continue
            await self._clear_bot_messages(ch)
            await ch.send(embed=embed)
            logger.info(f"[ChannelSetup] Guia postado: #{ch_name}")

    # ══════════════════════════════════════════════════════════
    # PAINÉIS — ORQUESTRADOR
    # ══════════════════════════════════════════════════════════

    async def setup_all_panels(self, guild: discord.Guild):
        await self.setup_suporte(guild)
        await self.setup_mediador(guild)
        await self.setup_analise(guild)
        await self.setup_exposed(guild)
        await self.setup_influencers(guild)
        await self.setup_pix(guild)
        await self.setup_renovacao(guild)
        await self.setup_status_bot(guild)
        await self.setup_pix_logs(guild)
        await self.setup_call_logs(guild)
        await self.setup_command_logs(guild)
        await self.setup_delete_logs(guild)
        await self.setup_troca_cargo_logs(guild)
        await self.setup_health_check(guild)    # ← adicionado
        logger.info("[ChannelSetup] Todos os painéis postados")

    # ══════════════════════════════════════════════════════════
    # PAINÉIS EXISTENTES (atualizados)
    # ══════════════════════════════════════════════════════════

    async def setup_suporte(self, guild: discord.Guild):
        from views.ticket_view import TicketPanelView, build_support_embed
        from views.staff_panels import build_suporte_admin_embed, SuporteAdminView
        # canal renomeado: solicitar-suporte (era chat-suporte)
        await self._post_panel(guild, SOLICITAR_SUPORTE_CHANNEL,
                               build_support_embed(), TicketPanelView())
        await self._post_panel(guild, SUPORTE_ADMIN_CHANNEL,
                               build_suporte_admin_embed(), SuporteAdminView())

    async def setup_mediador(self, guild: discord.Guild):
        from views.staff_panels import (
            build_mediador_pessoal_embed, MediadorPessoalView,
            build_mediador_admin_embed, MediadorAdminView,
        )
        from views.quero_ser_mediador_view import PedidoMediadorView, PedidomediadorEmbed
        from services.mediator_queue import mediator_queue
        info = await mediator_queue.get_queue_info()
        await self._post_panel(guild, MEDIADOR_PANEL_CHANNEL,
                               build_mediador_pessoal_embed(info), MediadorPessoalView())
        await self._post_panel(guild, MEDIADORES_ADMIN_CHANNEL,
                               build_mediador_admin_embed(), MediadorAdminView())
        await self._post_panel(guild, SOLICITACOES_CHANNEL,
                               PedidomediadorEmbed.beneficios(), PedidoMediadorView())

    async def setup_analise(self, guild: discord.Guild):
        from views.analyst_views import build_analise_panel_embed, AnalisePanelView
        from views.staff_panels import (
            build_analista_pessoal_embed, AnalistaPessoalView,
            build_analista_admin_embed, AnalistaAdminView,
        )
        await self._post_panel(guild, SOLICITAR_ANALISE_CHANNEL,
                               build_analise_panel_embed(), AnalisePanelView())
        # canal renomeado: painel-analista (era fila-analistas)
        await self._post_panel(guild, PAINEL_ANALISTA_CHANNEL,
                               build_analista_pessoal_embed(), AnalistaPessoalView())
        await self._post_panel(guild, ANALISTAS_ADMIN_CHANNEL,
                               build_analista_admin_embed(), AnalistaAdminView())

    async def setup_exposed(self, guild: discord.Guild):
        from views.analyst_views import build_exposed_embed, ExposedPanelView
        await self._post_panel(guild, EXPOSED_CHANNEL_NAME,
                               build_exposed_embed(), ExposedPanelView())
    
    async def setup_pix_logs(self, guild: discord.Guild):
        from views.pix_log import build_pix_log_embed
        await self._post_panel(guild,LOGS_PIX_LOG_CHANNEL,build_pix_log_embed(),None,clear=False)

    async def setup_troca_cargo_logs(self, guild: discord.Guild):
        from views.log_troca_cargo import build_troca_cargo_log_embed
        await self._post_panel(guild,LOGS_TROCA_CARGO_CHANNEL,build_troca_cargo_log_embed(),None,clear=False)

    
    async def setup_call_logs(self, guild: discord.Guild):
        from views.log_call import build_call_log_embed
        await self._post_panel(guild,LOGS_CALL_CHANNEL,build_call_log_embed(),None,clear=False)

    async def setup_command_logs(self, guild: discord.Guild):
        from views.log_comand import build_command_log_embed
        await self._post_panel(guild,LOGS_COMMAND_CHANNEL,build_command_log_embed(),None,clear=False)
    

    async def setup_delete_logs(self,guild: discord.Guild):
        from views.log_delete import build_message_delete_embed
        await self._post_panel(guild,LOGS_MESSAGE_DELETE_CHANNEL,build_message_delete_embed(),None,clear=False)
    


    async def setup_influencers(self, guild: discord.Guild):
        from views.extra_panels import (
            build_influencer_member_embed, InfluencerMemberView,
            build_influencer_admin_embed, InfluencerAdminView,
        )
        await self._post_panel(guild, INFLUENCERS_CHANNEL,
                               build_influencer_member_embed(), InfluencerMemberView())
        await self._post_panel(guild, INFLUENCERS_ADMIN_CHANNEL,
                               build_influencer_admin_embed(), InfluencerAdminView())

    async def setup_pix(self, guild: discord.Guild):
        from views.extra_panels import build_pix_panel_embed, PixPanelView
        await self._post_panel(guild, MEDIADOR_PIX_CHANNEL,
                               build_pix_panel_embed(), PixPanelView())

    async def setup_renovacao(self, guild: discord.Guild):
        from views.extra_panels import build_renovacao_panel_embed, RenovacaoPanelView
        await self._post_panel(guild, RENOVACAO_CHANNEL,
                               build_renovacao_panel_embed(), RenovacaoPanelView())

    async def setup_status_bot(self, guild: discord.Guild):
        from utils.datetime_utils import utcnow
        embed = discord.Embed(
            title="Status do Sistema",
            description="Todos os sistemas operacionais.",
            color=0x2ECC71,
        )
        embed.add_field(name="Bot",   value="🟢 Online",    inline=True)
        embed.add_field(name="Banco", value="🟢 Conectado", inline=True)
        embed.add_field(name="Fila",  value="🟢 Ativa",     inline=True)
        embed.set_footer(text=f"Configurado em {utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
        await self._post_panel(guild, STATUS_BOT_CHANNEL, embed, None)

    async def setup_health_check(self, guild: discord.Guild):
        try:
            from views.health_check_view import HealthCheckView, build_overview_embed
            from services.health_check_service import health_check_service

            if health_check_service:
                report = await health_check_service.run_check(guild)
                embed  = await build_overview_embed(report)
                view   = HealthCheckView(report=report, service=health_check_service, guild=guild)
            elif self.bot:
                from main import BOT_START_TIME
                embed = await build_overview_embed(self.bot, BOT_START_TIME)
                view  = HealthCheckView(bot=self.bot, start_time=BOT_START_TIME)
            else:
                logger.warning("[ChannelSetup] Health check: bot e service indisponíveis")
                return

            await self._post_panel(guild, HEALTH_CHECK_CHANNEL, embed, view)

            ch = discord.utils.get(guild.text_channels, name=HEALTH_CHECK_CHANNEL)
            if ch:
                async for msg in ch.history(limit=3):
                    if msg.author == guild.me and msg.embeds:
                        from config.database import db
                        from utils.datetime_utils import utcnow
                        await db.get_collection("thread_pool_panels").update_one(
                            {"guild_id": str(guild.id), "channel_id": str(ch.id)},
                            {"$set": {
                                "guild_id":   str(guild.id),
                                "channel_id": str(ch.id),
                                "message_id": str(msg.id),
                                "updated_at": utcnow(),
                            }},
                            upsert=True,
                        )
                        break
        except Exception as e:
            logger.error(f"[ChannelSetup] setup_health_check erro: {e}", exc_info=True)

    async def setup_faturamento(self, guild: discord.Guild):
        from services.faturamento_mediador import RelatorioGeralView
        embed = discord.Embed(
            title="💰 Faturamento dos Mediadores",
            description=(
                "Use o botão abaixo para gerar o relatório geral de faturamento.\n\n"
                "Este painel é restrito à equipe responsável pela mediação."
            ),
            color=0xFFA500,
        )
        await self._post_panel(guild, FATURAMENTO_CHANNEL, embed, RelatorioGeralView())

    async def setup_dashboards(self, guild: discord.Guild):
        if not self.bot:
            logger.warning("[ChannelSetup] Dashboards: bot não disponível")
            return
        try:
            from services.analytics_service import analytics_service
            analytics_service.bot = self.bot
            await analytics_service.update_all(guild)
            logger.info("[ChannelSetup] Dashboards atualizados")
        except Exception as e:
            logger.warning(f"[ChannelSetup] Dashboards: {e}")

    # ══════════════════════════════════════════════════════════
    # PAINÉIS NOVOS
    # ══════════════════════════════════════════════════════════

    async def setup_avisos(self, guild: discord.Guild):
        embed = discord.Embed(
            title="📢 Avisos",
            description=(
                "Este canal é reservado para avisos oficiais da equipe.\n\n"
                "Apenas a administração e o bot podem postar mensagens aqui."
            ),
            color=0xFFD54F,
        )
        embed.set_footer(text="Fique atento às novidades!")
        await self._post_panel(guild, AVISOS_CHANNEL, embed, None)

    async def setup_painel_suporte(self, guild: discord.Guild):
        embed = discord.Embed(
            title="🎫 Painel de Suporte",
            description=(
                "Acompanhe o status dos atendimentos e informações da equipe de suporte.\n\n"
                f"Para abrir um chamado, acesse `#{SOLICITAR_SUPORTE_CHANNEL}`."
            ),
            color=0x5865F2,
        )
        embed.set_footer(text="Apenas leitura — atualizado automaticamente pelo bot.")
        await self._post_panel(guild, PAINEL_SUPORTE_CHANNEL, embed, None)

    async def setup_casos_analisar(self, guild: discord.Guild):
        embed = discord.Embed(
            title="🔍 Casos em Análise",
            description=(
                "Os cards de pedidos de análise aparecem automaticamente aqui.\n\n"
                "**Analistas:** clique em **Assumir** no card para iniciar a investigação.\n\n"
                "Apenas o bot posta neste canal."
            ),
            color=0xE74C3C,
        )
        embed.set_footer(text="Apenas leitura — cards gerados automaticamente.")
        await self._post_panel(guild, CASOS_ANALISAR_CHANNEL, embed, None)

    async def setup_aprovar_mediadores(self, guild: discord.Guild):
        embed = discord.Embed(
            title="⚡ Aprovação de Mediadores",
            description=(
                "Pedidos para se tornar mediador aparecem automaticamente aqui.\n\n"
                "**Controllers / Adm:** revise o perfil e use os botões do card para "
                "**aprovar** ou **recusar** o candidato.\n\n"
                "Apenas o bot posta neste canal."
            ),
            color=0xFFD54F,
        )
        embed.set_footer(text="Apenas leitura — cards gerados automaticamente.")
        await self._post_panel(guild, APROVAR_MEDIADORES_CHANNEL, embed, None)

    async def setup_historico_exposed(self, guild: discord.Guild):
        embed = discord.Embed(
            title="📋 Histórico — Blacklist",
            description=(
                "Registro automático de todas as alterações na blacklist.\n\n"
                "✅ **Adicionado** — membro incluído na blacklist\n"
                "❌ **Removido** — membro retirado da blacklist\n\n"
                "Apenas o bot posta neste canal."
            ),
            color=0x992D22,
        )
        embed.set_footer(text="Apenas leitura — logs gerados automaticamente.")
        await self._post_panel(guild, HISTORICO_EXPOSED_CHANNEL, embed, None)

    async def setup_mediadores_afks(self, guild: discord.Guild):
        embed = discord.Embed(
            title="💤 Mediadores AFK",
            description=(
                "Lista de mediadores com status AFK ou inativos.\n\n"
                "Este painel é atualizado automaticamente pelo bot."
            ),
            color=0x95A5A6,
        )
        embed.set_footer(text="Apenas leitura — atualizado automaticamente.")
        await self._post_panel(guild, MEDIADORES_AFKS_CHANNEL, embed, None)

    # ══════════════════════════════════════════════════════════
    # MATCH CARDS
    # ══════════════════════════════════════════════════════════

    async def setup_match_cards(self, guild: discord.Guild):
        from views.match_queue_view import MatchQueueView, create_match_queue_embed

        for cat in ChannelsConfig.CATEGORIES.values():
            for ch_config in cat["channels"]:
                ch = discord.utils.get(guild.text_channels, name=ch_config["name"])
                if not ch:
                    continue

                await self._clear_bot_messages(ch, limit=50)

                for value in ChannelsConfig.BET_VALUES:
                    try:
                        embed = create_match_queue_embed(
                            channel_name=ch_config["name"],
                            bet_value=value,
                            queue_normal_count=0,
                            queue_infinito_count=0,
                        )
                        view = MatchQueueView(
                            channel_name=ch_config["name"],
                            bet_value=value,
                        )
                        file = get_banner_file(ch_config["name"])

                        if file:
                            embed.set_image(url=f"attachment://{file.filename}")
                            await ch.send(embed=embed, view=view, file=file)
                        else:
                            await ch.send(embed=embed, view=view)
                    except Exception as e:
                        logger.error(f"[ChannelSetup] Erro em #{ch_config['name']}: {e}")
                logger.info(
                    f"[ChannelSetup] {len(ChannelsConfig.BET_VALUES)} cards postados: #{ch_config['name']}")

    # ══════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════

    async def _clear_bot_messages(
        self, channel: discord.TextChannel, limit: int = 10
    ):
        to_delete = []
        async for msg in channel.history(limit=limit):
            if msg.author == channel.guild.me and (msg.embeds or msg.components):
                to_delete.append(msg)
        if not to_delete:
            return
        try:
            if len(to_delete) >= 2:
                await channel.delete_messages(to_delete)
            else:
                await to_delete[0].delete()
        except discord.HTTPException:
            for msg in to_delete:
                try:
                    await msg.delete()
                except Exception:
                    pass

    async def oi(
        self,
        guild: discord.Guild,
        channel_name: str,
        embed: discord.Embed,
        view: discord.ui.View | None,
    ):
        ch = discord.utils.get(guild.text_channels, name=channel_name)
        if not ch:
            logger.warning(f"[ChannelSetup] Canal não encontrado: #{channel_name}")
            return
        await self._clear_bot_messages(ch)
        try:
            await ch.send(embed=embed, view=view)
            logger.info(f"[ChannelSetup] Painel postado: #{channel_name}")
        except Exception as e:
            logger.error(f"[ChannelSetup] Erro em #{channel_name}: {e}")
        # 🔥 NÃO LIMPA logs
        try:
            await ch.send(embed=embed)
            logger.info(f"[ChannelSetup] Painel de log postado: #{channel_name}")
        except Exception as e:
            logger.error(f"[ChannelSetup] Erro em #{channel_name}: {e}")
#teste 
    async def _post_panel(
        self,
        guild: discord.Guild,
        channel_name: str,
        embed: discord.Embed,
        view: discord.ui.View | None,
        clear: bool = True,  # 👈 CONTROLE
    ):
        ch = discord.utils.get(guild.text_channels, name=channel_name)
        if not ch:
            logger.warning(f"[ChannelSetup] Canal não encontrado: #{channel_name}")
            return

        # 👇 só limpa se for painel normal
        if clear:
            await self._clear_bot_messages(ch)

        try:
            await ch.send(embed=embed, view=view)
            logger.info(f"[ChannelSetup] Painel postado: #{channel_name}")
        except Exception as e:
            logger.error(f"[ChannelSetup] Erro em #{channel_name}: {e}")

    async def get_or_create_channel(
        self, guild: discord.Guild, name: str, category_name: str | None = None
    ) -> discord.TextChannel:
        ch = discord.utils.get(guild.text_channels, name=name)
        if ch:
            return ch
        category = discord.utils.get(guild.categories, name=category_name) if category_name else None
        ch = await guild.create_text_channel(name, category=category)
        logger.info(f"[ChannelSetup] Canal criado on-demand: #{name}")
        return ch

    # ══════════════════════════════════════════════════════════
    # EMBEDS DE GUIA
    # ══════════════════════════════════════════════════════════

    def _guide_player_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Guia do Jogador", color=THEME)
        embed.add_field(name="Como jogar", value=(
            "1. Vá ao canal do modo desejado (ex: `#1x1-mob`)\n"
            "2. Clique no valor de aposta\n"
            "3. Aguarde outro jogador entrar na fila\n"
            "4. Confirme sua presença no tópico criado\n"
            "5. Pague ao mediador via **PIX**\n"
            "6. Jogue! O mediador declara o vencedor e paga o prêmio."
        ), inline=False)
        embed.add_field(name="Modos disponíveis", value=(
            "**Mobile** — 1x1, 2x2, 3x3, 4x4\n"
            "**Emulador** — 1x1, 2x2, 3x3, 4x4\n"
            "**Misto** — 2x2, 3x3, 4x4"
        ), inline=False)
        embed.add_field(
            name="Valores",
            value=" | ".join(f"R${v:.0f}" for v in ChannelsConfig.BET_VALUES),
            inline=False,
        )
        embed.add_field(name="Pagamento", value="✅ Apenas **PIX**\n❌ Inter, Neon, PagBank", inline=False)
        embed.add_field(name="Comandos",  value="`!cancelar`  `/perfil`  `/solicitar_analise`", inline=False)
        return embed

    def _guide_mediator_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Guia do Mediador", color=THEME)
        embed.add_field(name="Fluxo da partida", value=(
            "1. Fila completa → thread `confirmar-<modo>` criada\n"
            "2. Jogadores confirmam presença\n"
            "3. Thread → `pagamento-<modo>`\n"
            "4. `!confirmar_pagamento` → thread `pagar-<valor>`\n"
            "5. `!iniciar_partida` → partida começa\n"
            "6. `!winner_team blue/red` → vencedor declarado\n"
            "7. `!prize` → confirma entrega do prêmio"
        ), inline=False)
        embed.add_field(name="Comandos", value=(
            "`!menu_partida`  `!confirmar_pagamento`\n"
            "`!iniciar_partida`  `!winner_team`  `!prize`\n"
            "`!cancelar_match`  `/silence`"
        ), inline=False)
        embed.add_field(name="Seus canais", value=(
            f"`#{MEDIADOR_PANEL_CHANNEL}` — entrar/sair da fila\n"
            f"`#{MEDIADOR_PIX_CHANNEL}` — cadastrar chave PIX\n"
            f"`#{RENOVACAO_CHANNEL}` — renovar licença"
        ), inline=False)
        return embed

    def _guide_support_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Guia do Suporte", color=THEME)
        embed.add_field(name="Fluxo", value=(
            f"1. Jogador abre ticket em `#{SOLICITAR_SUPORTE_CHANNEL}`\n"
            f"2. Card aparece em `#{CHAMADOS_CHANNEL_NAME}`\n"
            "3. Clique **Assumir** → jogador entra no seu canal\n"
            "4. Atenda no canal `support-<seu-nome>`\n"
            "5. `!fechar_chamado <ID>` → fecha e remove jogador\n\n"
            f"💬 Use `#{CHAT_SUPORTE_STAFF_CHANNEL}` para comunicação interna com a equipe."
        ), inline=False)
        embed.add_field(name="Comandos", value=(
            "`!fechar_chamado <ID>`\n`/renomear_canal <sufixo>`"
        ), inline=False)
        return embed

    def _guide_analyst_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Guia do Analista", color=THEME)
        embed.add_field(name="Fluxo de análise", value=(
            f"1. Jogador solicita em `#{SOLICITAR_ANALISE_CHANNEL}`\n"
            f"2. Card aparece em `#{CASOS_ANALISAR_CHANNEL}` com botão **Assumir**\n"
            "3. Clique **Assumir** → você assume o caso\n"
            "4. Investigue e clique na decisão\n"
            "5. Se confirmado → jogador vai para blacklist automaticamente"
        ), inline=False)
        embed.add_field(name="Painel & Blacklist", value=(
            f"`#{PAINEL_ANALISTA_CHANNEL}` — fila de casos\n"
            f"`#{EXPOSED_CHANNEL_NAME}` — gestão da blacklist\n"
            f"`#{HISTORICO_EXPOSED_CHANNEL}` — histórico de alterações\n\n"
            f"💬 Use `#{CHAT_ANALISTAS_CHANNEL}` para falar com a adm."
        ), inline=False)
        return embed


channel_setup_service = ChannelSetupService()
