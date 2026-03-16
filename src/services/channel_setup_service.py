from __future__ import annotations
import discord
from utils.logger import logger, log_success
from services.channel_service import (
    CHANNEL_STRUCTURE, ALL_ROLES,
    GUIA_JOGADOR_CHANNEL, GUIA_MEDIADOR_CHANNEL,
    GUIA_SUPORTE_CHANNEL, GUIA_ANALISTA_CHANNEL,
    SUPPORT_CHANNEL_NAME, CHAMADOS_CHANNEL_NAME,
    MEDIADOR_PANEL_CHANNEL, MEDIADORES_ADMIN_CHANNEL,
    SOLICITACOES_CHANNEL, MEDIADOR_PIX_CHANNEL, RENOVACAO_CHANNEL,
    ANALYST_QUEUE_CHANNEL, ANALISTAS_ADMIN_CHANNEL,
    SOLICITAR_ANALISE_CHANNEL, EXPOSED_CHANNEL_NAME,
    INFLUENCERS_CHANNEL, INFLUENCERS_ADMIN_CHANNEL,
    SUPORTE_ADMIN_CHANNEL, STATUS_BOT_CHANNEL,
    permission_service,
)
from config.channels_config import ChannelsConfig


THEME = 0xFFD54F


class ChannelSetupService:

    def __init__(self):
        self.bot: discord.Client | None = None

    async def setup_all(self, guild: discord.Guild) -> str:
        await self.setup_roles(guild)
        await self.setup_categories_and_channels(guild)
        await self.setup_guide_channels(guild)
        await self.setup_all_panels(guild)
        await self.setup_match_cards(guild)
        await self.setup_dashboards(guild)
        log_success(f"[ChannelSetup] Setup completo em {guild.name}")
        return f"Servidor **{guild.name}** configurado com sucesso."

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

    async def setup_categories_and_channels(self, guild: discord.Guild):
        roles = {r.name: r for r in guild.roles}
        existing_channels = {c.name: c for c in guild.channels}

        for category_name, channels in CHANNEL_STRUCTURE.items():
            category = discord.utils.get(guild.categories, name=category_name)
            if not category:
                ow = await permission_service.get_category_overwrites(guild, category_name, roles)
                category = await guild.create_category(category_name, overwrites=ow)
                logger.info(f"[ChannelSetup] Categoria criada: {category_name}")

            for ch_name in channels:
                if ch_name in existing_channels:
                    continue
                ow = await permission_service.get_channel_overwrites(guild, ch_name, roles)
                await guild.create_text_channel(ch_name, category=category, overwrites=ow)
                logger.info(f"[ChannelSetup] Canal criado: #{ch_name}")

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
            async for msg in ch.history(limit=10):
                if msg.author == guild.me and msg.embeds:
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                    break
            await ch.send(embed=embed)
            logger.info(f"[ChannelSetup] Guia postado: #{ch_name}")

    async def setup_all_panels(self, guild: discord.Guild):
        await self.setup_suporte(guild)
        await self.setup_mediador(guild)
        await self.setup_analise(guild)
        await self.setup_exposed(guild)
        await self.setup_influencers(guild)
        await self.setup_pix(guild)
        await self.setup_renovacao(guild)
        await self.setup_status_bot(guild)
        logger.info("[ChannelSetup] Todos os painéis postados")

    async def setup_suporte(self, guild: discord.Guild):
        from views.ticket_view import TicketPanelView, build_support_embed
        from views.staff_panels import build_suporte_admin_embed, SuporteAdminView
        await self._post_panel(guild, SUPPORT_CHANNEL_NAME,
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
        await self._post_panel(guild, ANALYST_QUEUE_CHANNEL,
                               build_analista_pessoal_embed(), AnalistaPessoalView())
        await self._post_panel(guild, ANALISTAS_ADMIN_CHANNEL,
                               build_analista_admin_embed(), AnalistaAdminView())

    async def setup_exposed(self, guild: discord.Guild):
        from views.analyst_views import build_exposed_embed, ExposedPanelView
        await self._post_panel(guild, EXPOSED_CHANNEL_NAME,
                               build_exposed_embed(), ExposedPanelView())

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
            color=0x2ECC71
        )
        embed.add_field(name="Bot",   value="🟢 Online",    inline=True)
        embed.add_field(name="Banco", value="🟢 Conectado", inline=True)
        embed.add_field(name="Fila",  value="🟢 Ativa",     inline=True)
        embed.set_footer(text=f"Configurado em {utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
        await self._post_panel(guild, STATUS_BOT_CHANNEL, embed, None)

    async def setup_match_cards(self, guild: discord.Guild):
        """Posta um card por valor com status de fila em cada canal de jogo."""
        from views.match_queue_view import MatchQueueView, create_match_queue_embed

        for cat in ChannelsConfig.CATEGORIES.values():
            for ch_config in cat["channels"]:
                ch = discord.utils.get(guild.text_channels, name=ch_config["name"])
                if not ch:
                    continue

                # Limpa mensagens antigas do bot
                to_delete = []
                async for msg in ch.history(limit=30):
                    if msg.author == guild.me and (msg.embeds or msg.components):
                        to_delete.append(msg)
                for msg in to_delete:
                    try:
                        await msg.delete()
                    except Exception:
                        pass

                # Posta um card por valor com fila 0/2
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
                        await ch.send(embed=embed, view=view)
                    except Exception as e:
                        logger.warning(f"[ChannelSetup] Card {ch_config['name']} R${value}: {e}")

                logger.info(f"[ChannelSetup] {len(ChannelsConfig.BET_VALUES)} cards postados: #{ch_config['name']}")



    async def setup_dashboards(self, guild: discord.Guild):
        try:
            from services.analytics_service import analytics_service
            if self.bot:
                analytics_service.bot = self.bot
            await analytics_service.update_all(guild)
            logger.info("[ChannelSetup] Dashboards atualizados")
        except Exception as e:
            logger.warning(f"[ChannelSetup] Dashboards: {e}")

    async def _post_panel(
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
        async for msg in ch.history(limit=10):
            if msg.author == guild.me and msg.embeds:
                try:
                    await msg.delete()
                except Exception:
                    pass
                break
        try:
            await ch.send(embed=embed, view=view)
            logger.info(f"[ChannelSetup] Painel postado: #{channel_name}")
        except Exception as e:
            logger.error(f"[ChannelSetup] Erro em #{channel_name}: {e}")

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
            inline=False
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
            f"1. Jogador abre ticket em `#{SUPPORT_CHANNEL_NAME}`\n"
            f"2. Card aparece em `#{CHAMADOS_CHANNEL_NAME}`\n"
            "3. Clique **Assumir** → jogador entra no seu canal\n"
            "4. Atenda no canal `support-<seu-nome>`\n"
            "5. `!fechar_chamado <ID>` → fecha e remove jogador"
        ), inline=False)
        embed.add_field(name="Comandos", value=(
            "`!fechar_chamado <ID>`\n"
            "`/renomear_canal <sufixo>`"
        ), inline=False)
        return embed

    def _guide_analyst_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Guia do Analista", color=THEME)
        embed.add_field(name="Fluxo de análise", value=(
            f"1. Jogador solicita em `#{SOLICITAR_ANALISE_CHANNEL}`\n"
            f"2. Card aparece em `#{ANALYST_QUEUE_CHANNEL}` com botão **Assumir**\n"
            "3. Clique **Assumir** → você assume o caso\n"
            "4. Investigue e clique na decisão\n"
            "5. Se confirmado → jogador vai para blacklist automaticamente"
        ), inline=False)
        embed.add_field(name="Blacklist", value=(
            f"`#{EXPOSED_CHANNEL_NAME}` — painel com botões de gestão"
        ), inline=False)
        return embed

    async def get_or_create_channel(
        self,
        guild: discord.Guild,
        name: str,
        category_name: str | None = None,
    ) -> discord.TextChannel:
        ch = discord.utils.get(guild.text_channels, name=name)
        if ch:
            return ch
        category = discord.utils.get(guild.categories, name=category_name) if category_name else None
        ch = await guild.create_text_channel(name, category=category)
        logger.info(f"[ChannelSetup] Canal criado on-demand: #{name}")
        return ch


channel_setup_service = ChannelSetupService()
