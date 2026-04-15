"""
extra_panels.py — Painéis fixos para canais adicionais.
"""
from __future__ import annotations
import discord
import os
import re
from utils.datetime_utils import utcnow
from utils.logger import logger
from services.channel_service import CONTROLLER_ROLE_NAME, ADM_ROLE_NAME

THEME  = 0xFFD54F   # amarelo  — mediador / renovação
THEME2 = 0xFFA726   # laranja  — admin / influencer
SUCCESS = 0x2ECC71  # verde    — confirmações


def _is_mediator(interaction: discord.Interaction) -> bool:
    """Controller ou ADM podem interagir com painéis de mediador."""
    if interaction.user.guild_permissions.administrator:
        return True
    return bool({r.name for r in interaction.user.roles} & {CONTROLLER_ROLE_NAME, ADM_ROLE_NAME})


# ═══════════════════════════════════════════════════════════════
# 1. #renovacao-mediadores
# ═══════════════════════════════════════════════════════════════

def build_renovacao_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🔄 Renovação de Licença — Mediador",
        description=(
            "Gerencie sua licença de mediador aqui.\n\n"
            "**Como funciona:**\n"
            "• Clique em **Renovar Licença** para escolher o plano\n"
            "• O QR Code PIX será enviado para sua **DM** (privado)\n"
            "• Após pagar, clique em **Validar Pagamento** na sua DM\n"
            "• Sua licença é renovada automaticamente após confirmação\n\n"
            "**Avisos automáticos por DM:**\n"
            "• 3 dias antes do vencimento\n"
            "• 1 dia antes do vencimento\n"
            "• No dia do vencimento"
        ),
        color=THEME,
    )
    embed.add_field(
        name="📑 Planos disponíveis",
        value=(
            "`7 dias`  — R$ 10,00\n"
            "`15 dias` — R$ 18,00\n"
            "`30 dias` — R$ 25,00"
        ),
        inline=False,
    )
    embed.set_footer(text="Pagamento via PIX — QR Code enviado por DM | X1 Frifas")
    return embed


class RenovacaoPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Renovar Licença", style=discord.ButtonStyle.success,
                       emoji="🔄", custom_id="renovacao_panel_renovar")
    async def renovar(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_mediator(interaction):
            await interaction.response.send_message(
                "Apenas **mediadores** (Controller) podem renovar a licença.", ephemeral=True)
            return
        await interaction.response.send_modal(_RenovacaoPlanoModal())

    @discord.ui.button(label="Ver minha licença", style=discord.ButtonStyle.secondary,
                       emoji="📋", custom_id="renovacao_panel_ver")
    async def ver_licenca(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        doc = await db.get_collection("mediators").find_one({"user_id": interaction.user.id})
        if not doc:
            await interaction.followup.send(
                "Você não está cadastrado como mediador.", ephemeral=True)
            return
        embed = discord.Embed(title="📋 Sua Licença", color=THEME)
        exp   = doc.get("expiration_date")
        if exp:
            delta  = (exp - utcnow()).days
            status = "🟢 Ativa" if delta > 0 else "🔴 Vencida"
            embed.add_field(name="Validade",       value=exp.strftime("%d/%m/%Y"), inline=True)
            embed.add_field(name="Status",         value=status,                  inline=True)
            embed.add_field(name="Dias restantes", value=f"`{max(delta, 0)}`",    inline=True)
        else:
            embed.description = "Sem data de vencimento cadastrada."
        last = doc.get("last_renewal_at")
        if last:
            embed.add_field(
                name="Última renovação", value=last.strftime("%d/%m/%Y"), inline=True)
        embed.set_footer(text="X1 Frifas — Licença de Mediador")
        await interaction.followup.send(embed=embed, ephemeral=True)


class _RenovacaoPlanoModal(discord.ui.Modal, title="Escolha seu plano de renovação"):
    plano = discord.ui.TextInput(
        label="Plano (7, 15 ou 30 dias)",
        placeholder="Digite 7, 15 ou 30",
        min_length=1, max_length=2,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            dias = int(self.plano.value.strip())
            if dias not in (7, 15, 30):
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "Plano inválido. Digite 7, 15 ou 30.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from services.efi_pay_service import efi_pay_service
        price  = float(os.getenv(f"RENEWAL_PRICE_{dias}D", "25.00"))
        charge = await efi_pay_service.create_charge(
            mediator_id=str(interaction.user.id),
            value=price, plan_days=dias,
            description=f"Renovação {dias}d — {interaction.user.name}",
        )
        if not charge:
            await interaction.followup.send(
                "Erro ao gerar cobrança. Tente novamente.", ephemeral=True)
            return
        from cogs.renewal_cog import _send_charge_dm
        sent = await _send_charge_dm(
            interaction.user, charge, dias, price, interaction.client)
        if sent:
            await interaction.followup.send(
                "✅ Cobrança gerada e enviada para sua **DM**. "
                "Você tem **10 minutos** para pagar antes de expirar.",
                ephemeral=True)
        else:
            await interaction.followup.send(
                "Não foi possível enviar sua DM. "
                "Verifique se aceita mensagens diretas e tente novamente.",
                ephemeral=True)


# ═══════════════════════════════════════════════════════════════
# 2. #cadastra-pix
# ═══════════════════════════════════════════════════════════════

def build_pix_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="❖ Chave PIX — Mediadores",
        description=(
            "Cadastre ou atualize sua chave PIX para receber os pagamentos das partidas.\n\n"
            "**Tipo aceito:** E-mail\n"
            "Exemplo: `seuemail@gmail.com`\n\n"
            "Sua chave fica visível apenas para mediadores e administradores."
        ),
        color=THEME,
    )
    embed.set_footer(text="Mantenha sua chave sempre atualizada | X1 Frifas")
    return embed


class PixPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Cadastrar / Atualizar PIX", style=discord.ButtonStyle.success,
                    custom_id="pix_panel_cadastrar")
    async def cadastrar_pix(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_mediator(interaction):
            await interaction.response.send_message(
                "Apenas **mediadores** (Controller) podem cadastrar chave PIX.", ephemeral=True)
            return
        await interaction.response.send_modal(_PixCadastroModal())

    @discord.ui.button(label="Ver minha chave", style=discord.ButtonStyle.secondary,
                       emoji="🔍", custom_id="pix_panel_ver")
    async def ver_pix(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        doc = await db.get_collection("mediator_pix").find_one(
            {"discord_id": str(interaction.user.id)})
        if not doc:
            await interaction.followup.send(
                "Você não tem chave PIX cadastrada.", ephemeral=True)
            return
        embed = discord.Embed(title="❖ Sua Chave PIX", color=THEME)
        embed.add_field(name="Chave",    value=f"`{doc['pix_key']}`",     inline=False)
        embed.add_field(name="Tipo",     value=doc.get("pix_type", "—"),  inline=True)
        updated = doc.get("updated_at")
        if updated:
            embed.add_field(
                name="Atualizado", value=updated.strftime("%d/%m/%Y"), inline=True)
        embed.set_footer(text="X1 Frifas — Chave PIX")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Remover minha chave", style=discord.ButtonStyle.danger,
                       emoji="🗑️", custom_id="pix_panel_remover")
    async def remover_pix(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        result = await db.get_collection("mediator_pix").delete_one(
            {"discord_id": str(interaction.user.id)})
        if result.deleted_count:
            await interaction.followup.send("✅ Chave PIX removida.", ephemeral=True)
        else:
            await interaction.followup.send("Nenhuma chave PIX cadastrada.", ephemeral=True)


class _PixCadastroModal(discord.ui.Modal, title="Cadastrar Chave PIX"):
    pix_key = discord.ui.TextInput(
        label="Chave PIX (e-mail)",
        placeholder="seuemail@gmail.com",
        min_length=5, max_length=150,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        pix = self.pix_key.value.strip()
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", pix):
            await interaction.followup.send(
                "❌ Apenas chave PIX do tipo **e-mail** é aceita. Ex: `seuemail@gmail.com`",
                ephemeral=True)
            return
        doc = await db.get_collection("mediator_pix").find_one(
            {"discord_id": str(interaction.user.id)})
        pix_antigo = doc["pix_key"] if doc else None
        await db.get_collection("mediator_pix").update_one(
            {"discord_id": str(interaction.user.id)},
            {"$set": {
                "discord_id": str(interaction.user.id),
                "username":   interaction.user.name,
                "pix_key":    pix,
                "pix_type":   "EMAIL",
                "updated_at": utcnow(),
            }},
            upsert=True,
        )
        from views.pix_log import PixLog
        pix_logger = PixLog(interaction.client)
        await pix_logger.send_pix_log(interaction, pix_antigo, pix)
        embed = discord.Embed(
            title="❖ PIX Atualizado",
            description=f"Chave PIX cadastrada com sucesso.\n`{pix}`",
            color=SUCCESS,
        )
        embed.set_footer(text=f"🕐 {utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
        await interaction.channel.send(
            content=f"{interaction.user.mention} atualizou sua chave PIX.",
            embed=embed,
        )
        await interaction.followup.send("✅ Chave PIX (e-mail) cadastrada com sucesso!", ephemeral=True)


# ═══════════════════════════════════════════════════════════════
# 3. #influencers — painel do influencer
# ═══════════════════════════════════════════════════════════════

def build_influencer_member_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🏆 Painel do Influencer",
        description=(
            "Acompanhe seus resultados como parceiro.\n\n"
            "• **Meus Stats** — membros que você trouxe e comissão acumulada\n"
            "• **Meu Faturamento** — detalhamento da sua comissão"
        ),
        color=THEME,
    )
    embed.set_footer(text="Seus dados são atualizados em tempo real | X1 Frifas")
    return embed


class InfluencerMemberView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Meus Stats", style=discord.ButtonStyle.primary,
                       emoji="📊", custom_id="inf_member_stats")
    async def meus_stats(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_service import influencer_service
        stats = await influencer_service.get_stats(
            str(interaction.user.id), str(interaction.guild_id))
        if not stats:
            await interaction.followup.send(
                "Você não está cadastrado como influencer.", ephemeral=True)
            return
        inf   = stats["influencer"]
        embed = discord.Embed(title="📊 Seus Stats", color=THEME)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="Link de convite",  value=f"`{inf.get('invite_code','—')}`",              inline=True)
        embed.add_field(name="Membros trazidos", value=f"`{stats['total_members_brought']}`",          inline=True)
        embed.add_field(name="Comissão/membro",  value=f"R$ {inf.get('commission_per_member',2):.2f}", inline=True)
        embed.add_field(name="Total acumulado",  value=f"**R$ {stats['commission_due']:.2f}**",        inline=False)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Meu Faturamento", style=discord.ButtonStyle.secondary,
                       emoji="💰", custom_id="inf_member_faturamento")
    async def meu_faturamento(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_service import influencer_service
        stats = await influencer_service.get_stats(
            str(interaction.user.id), str(interaction.guild_id))
        if not stats:
            await interaction.followup.send(
                "Você não está cadastrado como influencer.", ephemeral=True)
            return
        inf   = stats["influencer"]
        embed = discord.Embed(title="💰 Faturamento Acumulado", color=THEME)
        embed.add_field(name="Membros trazidos", value=f"`{stats['total_members_brought']}`",           inline=True)
        embed.add_field(name="Comissão/membro",  value=f"R$ {inf.get('commission_per_member', 2):.2f}", inline=True)
        embed.add_field(name="Total acumulado",  value=f"**R$ {stats['commission_due']:.2f}**",         inline=False)
        created = inf.get("created_at")
        if created:
            embed.set_footer(text=f"Parceiro desde {created.strftime('%d/%m/%Y')} | X1 Frifas")
        else:
            embed.set_footer(text="X1 Frifas")
        await interaction.followup.send(embed=embed, ephemeral=True)


# ═══════════════════════════════════════════════════════════════
# 4. #influencers-controle — painel admin
# ═══════════════════════════════════════════════════════════════

def build_influencer_admin_embed() -> discord.Embed:
    embed = discord.Embed(
        title="⚙️ Painel ADM — Influencers",
        description=(
            "Gerencie todos os influencers parceiros.\n\n"
            "• **Ranking Geral** — top por membros trazidos\n"
            "• **Status Geral** — resumo consolidado do programa\n"
            "• **Buscar Influencer** — stats completos de um parceiro\n"
            "• **Adicionar / Remover** — cadastro de influencers"
        ),
        color=THEME2,
    )
    embed.set_footer(text="🔒 Canal restrito — apenas ADM | X1 Frifas")
    return embed


class InfluencerAdminView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    def _check_admin(self, interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator

    @discord.ui.button(label="Ranking Geral", style=discord.ButtonStyle.primary,
                       emoji="🏆", custom_id="inf_admin_ranking", row=0)
    async def ranking(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self._check_admin(interaction):
            await interaction.response.send_message("Apenas **ADM**.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from services.influencer_service import influencer_service
        rows  = await influencer_service.get_ranking(str(interaction.guild_id), limit=10)
        embed = discord.Embed(title="🏆 Ranking de Influencers", color=THEME2)
        if not rows:
            embed.description = "Nenhum influencer cadastrado."
        else:
            medals = ["🥇", "🥈", "🥉"]
            lines  = [
                f"{medals[i] if i < 3 else f'`{i+1}.`'} **{r['username']}** — "
                f"`{r['total_members']}` membros | R$ {r['commission']:.2f}"
                for i, r in enumerate(rows)
            ]
            embed.description = "\n".join(lines)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Status Geral", style=discord.ButtonStyle.secondary,
                       emoji="📈", custom_id="inf_admin_status", row=0)
    async def status_geral(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self._check_admin(interaction):
            await interaction.response.send_message("Apenas **ADM**.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        from services.influencer_service import influencer_service
        total_inf     = await db.get_collection("influencers").count_documents({"is_active": True})
        rows          = await influencer_service.get_ranking(str(interaction.guild_id), limit=100)
        total_comm    = sum(r["commission"] for r in rows)
        total_members = sum(r["total_members"] for r in rows)
        top = rows[0] if rows else None
        embed = discord.Embed(title="📈 Status Geral — Influencers", color=THEME2)
        embed.add_field(name="Influencers ativos",    value=f"`{total_inf}`",       inline=True)
        embed.add_field(name="Membros trazidos",      value=f"`{total_members}`",   inline=True)
        embed.add_field(name="Comissão total devida", value=f"R$ {total_comm:.2f}", inline=True)
        if top:
            embed.add_field(
                name="Melhor influencer",
                value=f"**{top['username']}** — `{top['total_members']}` membros",
                inline=False)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Buscar Influencer", style=discord.ButtonStyle.secondary,
                       emoji="🔍", custom_id="inf_admin_buscar", row=0)
    async def buscar(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self._check_admin(interaction):
            await interaction.response.send_message("Apenas **ADM**.", ephemeral=True)
            return
        await interaction.response.send_modal(_BuscarInfluencerModal())

    @discord.ui.button(label="Adicionar Influencer", style=discord.ButtonStyle.success,
                       emoji="➕", custom_id="inf_admin_add", row=1)
    async def adicionar(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self._check_admin(interaction):
            await interaction.response.send_message("Apenas **ADM**.", ephemeral=True)
            return
        await interaction.response.send_modal(_AdicionarInfluencerModal())

    @discord.ui.button(label="Remover Influencer", style=discord.ButtonStyle.danger,
                       emoji="➖", custom_id="inf_admin_remove", row=1)
    async def remover(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self._check_admin(interaction):
            await interaction.response.send_message("Apenas **ADM**.", ephemeral=True)
            return
        await interaction.response.send_modal(_RemoverInfluencerModal())


class _BuscarInfluencerModal(discord.ui.Modal, title="Stats de Influencer"):
    membro_id = discord.ui.TextInput(label="ID Discord do influencer",
                                      placeholder="Ex: 123456789012345678",
                                      min_length=10, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_service import influencer_service
        stats = await influencer_service.get_stats(
            self.membro_id.value.strip(), str(interaction.guild_id))
        if not stats:
            await interaction.followup.send("Influencer não encontrado.", ephemeral=True)
            return
        inf    = stats["influencer"]
        member = interaction.guild.get_member(int(self.membro_id.value.strip()))
        name   = member.display_name if member else inf.get("username", "?")
        embed  = discord.Embed(title=f"📊 Stats — {name}", color=THEME2)
        if member:
            embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Invite",           value=f"`{inf.get('invite_code','—')}`",              inline=True)
        embed.add_field(name="Membros trazidos", value=f"`{stats['total_members_brought']}`",          inline=True)
        embed.add_field(name="Comissão/membro",  value=f"R$ {inf.get('commission_per_member',2):.2f}", inline=True)
        embed.add_field(name="Partidas geradas", value=f"`{stats['total_matches_played']}`",           inline=True)
        embed.add_field(name="Volume apostado",  value=f"R$ {stats['total_wagered']:.2f}",             inline=True)
        embed.add_field(name="Comissão total",   value=f"**R$ {stats['commission_due']:.2f}**",        inline=True)
        created = inf.get("created_at")
        if created:
            embed.set_footer(text=f"Parceiro desde {created.strftime('%d/%m/%Y')} | X1 Frifas")
        await interaction.followup.send(embed=embed, ephemeral=True)


class _AdicionarInfluencerModal(discord.ui.Modal, title="Adicionar Influencer"):
    membro_id   = discord.ui.TextInput(label="ID Discord do membro",
                                        placeholder="Ex: 123456789012345678",
                                        min_length=10, max_length=20)
    invite_code = discord.ui.TextInput(label="Código do invite",
                                        placeholder="Ex: abc123",
                                        min_length=1, max_length=20)
    comissao    = discord.ui.TextInput(label="Comissão por membro (R$)",
                                        placeholder="Ex: 2.50",
                                        min_length=1, max_length=6)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            comm = float(self.comissao.value.replace(",", "."))
        except ValueError:
            await interaction.followup.send("Valor de comissão inválido.", ephemeral=True)
            return
        member = interaction.guild.get_member(int(self.membro_id.value.strip()))
        name   = member.display_name if member else f"ID:{self.membro_id.value}"
        from services.influencer_service import influencer_service
        await influencer_service.add_influencer(
            discord_id=self.membro_id.value.strip(), username=name,
            invite_code=self.invite_code.value.strip(), commission_per_member=comm)
        if member:
            role = discord.utils.get(interaction.guild.roles, name="Influencer")
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Cadastrado como influencer")
                except Exception:
                    pass
        await interaction.followup.send(
            f"✅ **{name}** cadastrado | Invite: `{self.invite_code.value}` | "
            f"Comissão: R$ {comm:.2f}/membro", ephemeral=True)


class _RemoverInfluencerModal(discord.ui.Modal, title="Remover Influencer"):
    membro_id = discord.ui.TextInput(label="ID Discord do influencer",
                                      placeholder="Ex: 123456789012345678",
                                      min_length=10, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_service import influencer_service
        ok     = await influencer_service.remove_influencer(self.membro_id.value.strip())
        member = interaction.guild.get_member(int(self.membro_id.value.strip()))
        if member:
            role = discord.utils.get(interaction.guild.roles, name="Influencer")
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Removido como influencer")
                except Exception:
                    pass
        if ok:
            await interaction.followup.send("✅ Influencer removido.", ephemeral=True)
        else:
            await interaction.followup.send("Influencer não encontrado.", ephemeral=True)
