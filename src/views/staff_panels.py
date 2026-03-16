"""
staff_panels.py — Painéis pessoais e admin para Mediadores, Analistas e Suporte.
"""
from __future__ import annotations
import discord
from utils.datetime_utils import utcnow
from utils.logger import logger


THEME  = 0xFFD54F
THEME2 = 0xFFA726
DANGER = 0xE74C3C


def _is_mediador(u: discord.Member) -> bool:
    return u.guild_permissions.administrator or \
           bool({r.name for r in u.roles} & {"Controller", "Mediador", "Mediator"})


def _is_analyst(u: discord.Member) -> bool:
    return u.guild_permissions.administrator or \
           bool({r.name for r in u.roles} & {"Analyst", "Analista"})


def _is_support(u: discord.Member) -> bool:
    return u.guild_permissions.administrator or \
           bool({r.name for r in u.roles} & {"Support", "Suporte"})


def _is_admin(u: discord.Member) -> bool:
    return u.guild_permissions.administrator


# ═══════════════════════════════════════════════════════════════
# MEDIADOR — Painel pessoal (#painel-mediador)
# ═══════════════════════════════════════════════════════════════


def build_mediador_pessoal_embed(info: dict | None = None) -> discord.Embed:
    total_active = info.get("total_active", 0) if info else 0
    in_queue     = info.get("in_queue", 0)     if info else 0
    embed = discord.Embed(
        title="Painel de Mediadores",
        description=(
            "Gerencie sua presença na fila e acompanhe seus dados.\n\n"
            "• **Entrar / Sair da Fila** — controle sua disponibilidade\n"
            "• **Meus Stats** — suas partidas mediadas e faturamento\n"
            "• **Minha Licença** — validade e renovação"
        ),
        color=THEME
    )
    embed.add_field(name="Na fila agora", value=f"`{in_queue}`",     inline=True)
    embed.add_field(name="Ativos hoje",   value=f"`{total_active}`", inline=True)
    embed.set_footer(text="Apenas Controllers podem mediar partidas")
    return embed


class MediadorPessoalView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrar na Fila", style=discord.ButtonStyle.success,
                       emoji="✅", custom_id="med_join_queue", row=0)
    async def entrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _is_mediador(interaction.user):
            await interaction.response.send_message(
                "Apenas Controllers podem entrar na fila.", ephemeral=True)
            return
        from services.mediator_queue import mediator_queue
        from config.database import db
        col = db.get_collection("mediators")
        doc = await col.find_one({"user_id": interaction.user.id})
        if not doc:
            await mediator_queue.register_mediator(
                user_id=interaction.user.id,
                username=interaction.user.name,
                guild_id=interaction.guild.id
            )
        result = await mediator_queue.add_to_queue(interaction.user.id)
        if result:
            await interaction.response.send_message(
                "Você entrou na fila de mediadores.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Você já está na fila ou não está ativo.", ephemeral=True)
        await self._refresh(interaction)

    @discord.ui.button(label="Sair da Fila", style=discord.ButtonStyle.danger,
                       emoji="⏸️", custom_id="med_leave_queue", row=0)
    async def sair(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _is_mediador(interaction.user):
            await interaction.response.send_message("Apenas Controllers.", ephemeral=True)
            return
        from services.mediator_queue import mediator_queue
        await mediator_queue.remove_from_queue(interaction.user.id)
        await interaction.response.send_message(
            "Você saiu da fila de mediadores.", ephemeral=True)
        await self._refresh(interaction)

    @discord.ui.button(label="Meus Stats", style=discord.ButtonStyle.secondary,
                       emoji="📊", custom_id="med_stats", row=1)
    async def meus_stats(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_mediador(interaction.user):
            await interaction.response.send_message("Apenas Controllers.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        from datetime import timedelta
        col  = db.get_collection("mediators")
        mcol = db.get_collection("matches")
        doc  = await col.find_one({"user_id": interaction.user.id})
        if not doc:
            await interaction.followup.send("Você não está cadastrado como mediador.", ephemeral=True)
            return
        now   = utcnow()
        day30 = now - timedelta(days=30)
        total  = await mcol.count_documents({"mediator_id": str(interaction.user.id)})
        mes    = await mcol.count_documents({
            "mediator_id": str(interaction.user.id), "created_at": {"$gte": day30}})
        cancel = await mcol.count_documents({
            "mediator_id": str(interaction.user.id),
            "status": "cancelado", "created_at": {"$gte": day30}})
        in_q  = "✅ Sim" if doc.get("in_queue") else "❌ Não"
        embed = discord.Embed(title="Seus Stats — Mediador", color=THEME)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="Na fila",          value=in_q,          inline=True)
        embed.add_field(name="Total mediadas",   value=f"`{total}`",  inline=True)
        embed.add_field(name="Últimos 30 dias",  value=f"`{mes}`",    inline=True)
        embed.add_field(name="Canceladas (30d)", value=f"`{cancel}`", inline=True)
        if mes > 0:
            embed.add_field(name="Taxa cancelamento",
                            value=f"`{(cancel/mes*100):.1f}%`", inline=True)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Minha Licença", style=discord.ButtonStyle.secondary,
                       emoji="🔑", custom_id="med_licenca", row=1)
    async def minha_licenca(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        doc = await db.get_collection("mediators").find_one({"user_id": interaction.user.id})
        embed = discord.Embed(title="Sua Licença", color=THEME)
        if doc and doc.get("expiration_date"):
            exp   = doc["expiration_date"]
            delta = (exp - utcnow()).days
            embed.add_field(name="Validade",       value=exp.strftime("%d/%m/%Y"), inline=True)
            embed.add_field(name="Status",         value="🟢 Ativa" if delta > 0 else "🔴 Vencida", inline=True)
            embed.add_field(name="Dias restantes", value=f"`{max(delta, 0)}`", inline=True)
        else:
            embed.description = "Sem data de vencimento. Use `#renovacao-mediadores` para renovar."
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Ver Fila Completa", style=discord.ButtonStyle.secondary,
                       emoji="📋", custom_id="med_view_queue", row=1)
    async def ver_fila(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_admin(interaction.user):
            await interaction.response.send_message(
                "Apenas administradores podem ver a fila completa.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from services.mediator_queue import mediator_queue
        stats = await mediator_queue.get_queue_stats()
        embed = discord.Embed(title="Fila de Mediadores", color=THEME)
        embed.add_field(name="Ativos",  value=f"`{stats['total_active']}`",   inline=True)
        embed.add_field(name="Na fila", value=f"`{len(stats['mediators'])}`", inline=True)
        if stats["mediators"]:
            lines = []
            for m in stats["mediators"]:
                status = "✅" if m["can_mediate"] else "⏸️"
                lines.append(f"{status} **{m['username']}** — `{m['total_matches']}` partidas")
            embed.add_field(name="Mediadores", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Fila", value="Nenhum mediador ativo.", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _refresh(self, interaction: discord.Interaction):
        from services.mediator_queue import mediator_queue
        info  = await mediator_queue.get_queue_info()
        embed = build_mediador_pessoal_embed(info)
        try:
            await interaction.message.edit(embed=embed)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# MEDIADOR — Painel admin (#mediadores-admin)
# ═══════════════════════════════════════════════════════════════


def build_mediador_admin_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Painel Admin — Mediadores",
        description=(
            "Gerencie todos os mediadores do servidor.\n\n"
            "• **Ranking** — top mediadores por partidas\n"
            "• **Stats individuais** — dados de um mediador específico\n"
            "• **Gerenciar** — adicionar, remover e verificar licença"
        ),
        color=THEME2
    )
    embed.set_footer(text="Canal restrito — apenas Administradores")
    return embed


class MediadorAdminView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ranking", style=discord.ButtonStyle.primary,
                       emoji="🏆", custom_id="medad_ranking", row=0)
    async def ranking(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_admin(interaction.user):
            await interaction.response.send_message("Apenas admins.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        from datetime import timedelta
        col   = db.get_collection("matches")
        mcol  = db.get_collection("mediators")
        day30 = utcnow() - timedelta(days=30)
        pipe  = [
            {"$match": {"created_at": {"$gte": day30}, "mediator_id": {"$exists": True}}},
            {"$group": {"_id": "$mediator_id", "total": {"$sum": 1}}},
            {"$sort":  {"total": -1}},
            {"$limit": 10}
        ]
        rows   = await col.aggregate(pipe).to_list(10)
        embed  = discord.Embed(title="Ranking de Mediadores — 30 dias", color=THEME2)
        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for i, r in enumerate(rows):
            med  = await mcol.find_one({"user_id": int(r["_id"])}) if r["_id"] else None
            name = med.get("username", r["_id"]) if med else str(r["_id"])
            pos  = medals[i] if i < 3 else f"`{i+1}.`"
            lines.append(f"{pos} **{name}** — `{r['total']}` partidas")
        embed.description = "\n".join(lines) if lines else "Sem dados."
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Stats Individuais", style=discord.ButtonStyle.secondary,
                       emoji="🔍", custom_id="medad_stats", row=0)
    async def stats_ind(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_admin(interaction.user):
            await interaction.response.send_message("Apenas admins.", ephemeral=True)
            return
        await interaction.response.send_modal(_BuscarMediadorModal())

    @discord.ui.button(label="Adicionar Mediador", style=discord.ButtonStyle.success,
                       emoji="➕", custom_id="medad_add", row=1)
    async def adicionar(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_admin(interaction.user):
            await interaction.response.send_message("Apenas admins.", ephemeral=True)
            return
        await interaction.response.send_modal(_AdicionarMediadorModal())

    @discord.ui.button(label="Remover Mediador", style=discord.ButtonStyle.danger,
                       emoji="➖", custom_id="medad_remove", row=1)
    async def remover(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_admin(interaction.user):
            await interaction.response.send_message("Apenas admins.", ephemeral=True)
            return
        await interaction.response.send_modal(_RemoverMediadorModal())

    @discord.ui.button(label="Ver Licenças", style=discord.ButtonStyle.secondary,
                       emoji="📅", custom_id="medad_licencas", row=1)
    async def licencas(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_admin(interaction.user):
            await interaction.response.send_message("Apenas admins.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        docs  = await db.get_collection("mediators").find(
            {"is_active": True}).sort("expiration_date", 1).limit(15).to_list(15)
        embed = discord.Embed(title="Licenças dos Mediadores", color=THEME2)
        lines = []
        for doc in docs:
            exp  = doc.get("expiration_date")
            name = doc.get("username", "?")
            if exp:
                delta = (exp - utcnow()).days
                icon  = "🟢" if delta > 7 else ("🟡" if delta > 0 else "🔴")
                lines.append(f"{icon} **{name}** — vence {exp.strftime('%d/%m/%Y')} (`{max(delta,0)}d`)")
            else:
                lines.append(f"⚪ **{name}** — sem vencimento")
        embed.description = "\n".join(lines) if lines else "Nenhum mediador ativo."
        await interaction.followup.send(embed=embed, ephemeral=True)


class _BuscarMediadorModal(discord.ui.Modal, title="Stats de Mediador"):
    membro_id = discord.ui.TextInput(label="ID Discord do mediador",
                                      placeholder="Ex: 123456789012345678",
                                      min_length=10, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        from datetime import timedelta
        uid  = int(self.membro_id.value.strip())
        doc  = await db.get_collection("mediators").find_one({"user_id": uid})
        if not doc:
            await interaction.followup.send("Mediador não encontrado.", ephemeral=True)
            return
        col   = db.get_collection("matches")
        now   = utcnow()
        total = await col.count_documents({"mediator_id": str(uid)})
        mes   = await col.count_documents({"mediator_id": str(uid),
                                           "created_at": {"$gte": now - timedelta(days=30)}})
        member = interaction.guild.get_member(uid)
        name   = member.display_name if member else doc.get("username", "?")
        embed  = discord.Embed(title=f"Stats — {name}", color=THEME2)
        if member:
            embed.set_thumbnail(url=member.display_avatar.url)
        in_q = "✅ Sim" if doc.get("in_queue") else "❌ Não"
        embed.add_field(name="Na fila",         value=in_q,         inline=True)
        embed.add_field(name="Total mediadas",  value=f"`{total}`", inline=True)
        embed.add_field(name="Últimos 30 dias", value=f"`{mes}`",   inline=True)
        exp = doc.get("expiration_date")
        if exp:
            delta = (exp - now).days
            status_icon = "🟢" if delta > 0 else "🔴"
            exp_str     = exp.strftime("%d/%m/%Y")
            embed.add_field(
                name="Licença",
                value=f"{status_icon} {exp_str} (`{max(delta,0)}d`)",
                inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)


class _AdicionarMediadorModal(discord.ui.Modal, title="Adicionar Mediador"):
    membro_id = discord.ui.TextInput(label="ID Discord do membro",
                                      placeholder="Ex: 123456789012345678",
                                      min_length=10, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from services.mediator_queue import mediator_queue
        uid    = int(self.membro_id.value.strip())
        member = interaction.guild.get_member(uid)
        name   = member.display_name if member else f"ID:{uid}"
        await mediator_queue.add_mediator(str(uid), name)
        role = discord.utils.get(interaction.guild.roles, name="Controller")
        if member and role and role not in member.roles:
            try:
                await member.add_roles(role, reason="Cadastrado como mediador")
            except Exception:
                pass
        await interaction.followup.send(f"✅ **{name}** adicionado como mediador.", ephemeral=True)


class _RemoverMediadorModal(discord.ui.Modal, title="Remover Mediador"):
    membro_id = discord.ui.TextInput(label="ID Discord do mediador",
                                      placeholder="Ex: 123456789012345678",
                                      min_length=10, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from services.mediator_queue import mediator_queue
        uid    = int(self.membro_id.value.strip())
        member = interaction.guild.get_member(uid)
        await mediator_queue.remove_mediador(str(uid))
        role = discord.utils.get(interaction.guild.roles, name="Controller")
        if member and role and role in member.roles:
            try:
                await member.remove_roles(role, reason="Removido como mediador")
            except Exception:
                pass
        name = member.display_name if member else f"ID:{uid}"
        await interaction.followup.send(f"✅ **{name}** removido da fila.", ephemeral=True)


# ═══════════════════════════════════════════════════════════════
# ANALISTA — Painel pessoal (#fila-analistas)
# ═══════════════════════════════════════════════════════════════


def build_analista_pessoal_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Painel do Analista",
        description=(
            "Acompanhe seus casos e histórico de análises.\n\n"
            "• **Meus Casos Ativos** — casos que você está analisando\n"
            "• **Meu Histórico** — todas as decisões que tomou\n"
            "• **Fila de Casos** — casos aguardando análise"
        ),
        color=THEME
    )
    embed.set_footer(text="Acesso restrito — Analyst")
    return embed


class AnalistaPessoalView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Meus Casos Ativos", style=discord.ButtonStyle.primary,
                       emoji="🔍", custom_id="ana_ativos", row=0)
    async def casos_ativos(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_analyst(interaction.user):
            await interaction.response.send_message("Apenas analistas.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        docs = await db.get_collection("analysis_cases").find(
            {"analyst_id": str(interaction.user.id), "status": "em_analise"}
        ).sort("created_at", -1).to_list(10)
        embed = discord.Embed(title="Seus Casos em Análise", color=THEME)
        if not docs:
            embed.description = "Você não tem casos em análise no momento."
        else:
            for doc in docs:
                embed.add_field(
                    name=f"`{doc['case_id']}`",
                    value=f"Partida: `{doc.get('match_id','—')}` | {doc.get('motivo','—')[:60]}",
                    inline=False
                )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Meu Histórico", style=discord.ButtonStyle.secondary,
                       emoji="📋", custom_id="ana_historico", row=0)
    async def historico(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_analyst(interaction.user):
            await interaction.response.send_message("Apenas analistas.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        docs = await db.get_collection("analysis_cases").find(
            {"analyst_id": str(interaction.user.id),
             "status": {"$in": ["confirmado", "inconclusivo", "invalido"]}}
        ).sort("closed_at", -1).limit(10).to_list(10)
        status_icon = {"confirmado": "🚫", "inconclusivo": "❓", "invalido": "✖"}
        embed = discord.Embed(title="Seu Histórico de Análises", color=THEME)
        if not docs:
            embed.description = "Nenhuma análise concluída ainda."
        else:
            confirmed = sum(1 for d in docs if d.get("status") == "confirmado")
            inconc    = sum(1 for d in docs if d.get("status") == "inconclusivo")
            invalid   = sum(1 for d in docs if d.get("status") == "invalido")
            embed.add_field(name="Confirmados",   value=f"`{confirmed}`", inline=True)
            embed.add_field(name="Inconclusivos", value=f"`{inconc}`",    inline=True)
            embed.add_field(name="Inválidos",     value=f"`{invalid}`",   inline=True)
            lines = [
                f"{status_icon.get(d.get('status',''),'❓')} `{d['case_id']}` — {d.get('motivo','—')[:40]}"
                for d in docs[:8]
            ]
            embed.add_field(name="Últimas decisões", value="\n".join(lines), inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Fila de Casos", style=discord.ButtonStyle.secondary,
                       emoji="📥", custom_id="ana_fila", row=0)
    async def fila_casos(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_analyst(interaction.user):
            await interaction.response.send_message("Apenas analistas.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        aguardando = await db.get_collection("analysis_cases").count_documents(
            {"status": "aguardando_analise"})
        em_analise = await db.get_collection("analysis_cases").count_documents(
            {"status": "em_analise"})
        embed = discord.Embed(title="Status da Fila de Análises", color=THEME)
        embed.add_field(name="Aguardando análise", value=f"`{aguardando}`", inline=True)
        embed.add_field(name="Em análise",         value=f"`{em_analise}`", inline=True)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)


# ═══════════════════════════════════════════════════════════════
# ANALISTA — Painel admin (#analistas-admin)
# ═══════════════════════════════════════════════════════════════


def build_analista_admin_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Painel Admin — Analistas",
        description=(
            "Supervisione todos os casos e analistas.\n\n"
            "• **Visão Geral** — todos os casos por status\n"
            "• **Stats por Analista** — desempenho individual\n"
            "• **Buscar Caso** — detalhes de um caso específico"
        ),
        color=THEME2
    )
    embed.set_footer(text="Canal restrito — apenas Administradores")
    return embed


class AnalistaAdminView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Visão Geral", style=discord.ButtonStyle.primary,
                       emoji="📊", custom_id="anaad_geral", row=0)
    async def visao_geral(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_admin(interaction.user):
            await interaction.response.send_message("Apenas admins.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        col = db.get_collection("analysis_cases")
        embed = discord.Embed(title="Visão Geral — Análises", color=THEME2)
        for status, label in [
            ("aguardando_analise", "Aguardando"),
            ("em_analise", "Em análise"),
            ("confirmado", "Confirmados (BL)"),
            ("inconclusivo", "Inconclusivos"),
            ("invalido", "Inválidos"),
        ]:
            count = await col.count_documents({"status": status})
            embed.add_field(name=label, value=f"`{count}`", inline=True)
        total = await col.count_documents({})
        embed.add_field(name="Total", value=f"`{total}`", inline=True)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Stats por Analista", style=discord.ButtonStyle.secondary,
                       emoji="👤", custom_id="anaad_stats", row=0)
    async def stats_analistas(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_admin(interaction.user):
            await interaction.response.send_message("Apenas admins.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        pipe = [
            {"$match": {"analyst_id": {"$exists": True, "$ne": None}}},
            {"$group": {
                "_id":         "$analyst_id",
                "total":       {"$sum": 1},
                "confirmados": {"$sum": {"$cond": [{"$eq": ["$status", "confirmado"]}, 1, 0]}},
                "invalidos":   {"$sum": {"$cond": [{"$eq": ["$status", "invalido"]}, 1, 0]}},
            }},
            {"$sort": {"total": -1}},
            {"$limit": 10}
        ]
        rows   = await db.get_collection("analysis_cases").aggregate(pipe).to_list(10)
        embed  = discord.Embed(title="Stats por Analista", color=THEME2)
        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for i, r in enumerate(rows):
            # ✅ extraído antes da f-string — sem backslash dentro de {}
            rid        = r["_id"]
            member_obj = interaction.guild.get_member(int(rid)) if rid else None
            name       = member_obj.display_name if member_obj else f"ID:{rid}"
            pos        = medals[i] if i < 3 else f"`{i+1}.`"
            lines.append(
                f"{pos} **{name}** — `{r['total']}` | "
                f"🚫`{r['confirmados']}` ✖`{r['invalidos']}`"
            )
        embed.description = "\n".join(lines) if lines else "Sem dados."
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Buscar Caso", style=discord.ButtonStyle.secondary,
                       emoji="🔍", custom_id="anaad_buscar", row=0)
    async def buscar_caso(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_admin(interaction.user):
            await interaction.response.send_message("Apenas admins.", ephemeral=True)
            return
        await interaction.response.send_modal(_BuscarCasoModal())


class _BuscarCasoModal(discord.ui.Modal, title="Buscar Caso"):
    case_id = discord.ui.TextInput(label="ID do caso",
                                    placeholder="Ex: CASE-ABC123-5678",
                                    min_length=5, max_length=40)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        from views.analyst_views import build_case_embed
        doc = await db.get_collection("analysis_cases").find_one(
            {"case_id": self.case_id.value.strip()})
        if not doc:
            await interaction.followup.send("Caso não encontrado.", ephemeral=True)
            return
        await interaction.followup.send(embed=build_case_embed(doc), ephemeral=True)


# ═══════════════════════════════════════════════════════════════
# SUPORTE — Painéis
# ═══════════════════════════════════════════════════════════════


def build_suporte_pessoal_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Central de Suporte",
        description=(
            "Precisa de ajuda? Estamos aqui.\n\n"
            "• **Abrir Ticket** — selecione a categoria e descreva o problema\n\n"
            "Nossa equipe responderá o mais breve possível."
        ),
        color=THEME
    )
    embed.set_footer(text="Suporte disponível todos os dias")
    return embed


def build_suporte_admin_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Painel Admin — Suporte",
        description=(
            "Supervisione todos os tickets e agentes.\n\n"
            "• **Visão Geral** — tickets abertos, em andamento e resolvidos\n"
            "• **Por Agente** — tickets de cada membro do suporte\n"
            "• **Buscar Ticket** — detalhes de um ticket específico\n"
            "• **Forçar Fechar** — encerrar ticket administrativamente\n"
            "• **Tickets Abertos** — lista todos os tickets em aberto"
        ),
        color=THEME2
    )
    embed.set_footer(text="Canal restrito — apenas Administradores")
    return embed


class SuporteAdminView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Visão Geral", style=discord.ButtonStyle.primary,
                       emoji="📊", custom_id="supad_geral", row=0)
    async def visao_geral(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_admin(interaction.user):
            await interaction.response.send_message("Apenas admins.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        from datetime import timedelta
        col  = db.get_collection("tickets")
        now  = utcnow()
        d30  = now - timedelta(days=30)
        embed = discord.Embed(title="Visão Geral — Suporte", color=THEME2)
        embed.add_field(name="Abertos agora",    value=f"`{await col.count_documents({'status': 'aberto'})}`",   inline=True)
        embed.add_field(name="Em atendimento",   value=f"`{await col.count_documents({'status': 'pendente'})}`", inline=True)
        embed.add_field(
            name="Resolvidos (30d)",
            value=f"`{await col.count_documents({'status': {'$in': ['resolvido','fechado']}, 'created_at': {'$gte': d30}})}`",
            inline=True
        )
        embed.add_field(name="Total mês", value=f"`{await col.count_documents({'created_at': {'$gte': d30}})}`", inline=True)
        pipe = [
            {"$match": {"created_at": {"$gte": d30}}},
            {"$group": {"_id": "$categoria", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}, {"$limit": 5}
        ]
        cats = await col.aggregate(pipe).to_list(5)
        if cats:
            embed.add_field(
                name="Por categoria",
                value=" | ".join(f"{c['_id']}:`{c['count']}`" for c in cats),
                inline=False
            )
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Por Agente", style=discord.ButtonStyle.secondary,
                       emoji="👤", custom_id="supad_agente", row=0)
    async def por_agente(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_admin(interaction.user):
            await interaction.response.send_message("Apenas admins.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        from datetime import timedelta
        pipe = [
            {"$match": {"atendente_id": {"$exists": True, "$ne": None},
                        "created_at": {"$gte": utcnow() - timedelta(days=30)}}},
            {"$group": {
                "_id":        "$atendente_id",
                "total":      {"$sum": 1},
                "resolvidos": {"$sum": {"$cond": [{"$in": ["$status", ["resolvido","fechado"]]}, 1, 0]}}
            }},
            {"$sort": {"resolvidos": -1}}
        ]
        rows   = await db.get_collection("tickets").aggregate(pipe).to_list(10)
        embed  = discord.Embed(title="Tickets por Agente — 30 dias", color=THEME2)
        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for i, r in enumerate(rows):
            # ✅ extraído antes da f-string — sem backslash dentro de {}
            aid    = r["_id"]
            member = interaction.guild.get_member(int(aid)) if aid else None
            name   = member.display_name if member else f"ID:{aid}"
            pos    = medals[i] if i < 3 else f"`{i+1}.`"
            lines.append(
                f"{pos} **{name}** — "
                f"`{r['total']}` tickets | `{r['resolvidos']}` resolvidos"
            )
        embed.description = "\n".join(lines) if lines else "Sem dados."
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Buscar Ticket", style=discord.ButtonStyle.secondary,
                       emoji="🔍", custom_id="supad_buscar", row=0)
    async def buscar_ticket(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_admin(interaction.user):
            await interaction.response.send_message("Apenas admins.", ephemeral=True)
            return
        await interaction.response.send_modal(_BuscarTicketModal())

    @discord.ui.button(label="Forçar Fechar", style=discord.ButtonStyle.danger,
                       emoji="🔒", custom_id="supad_fechar", row=1)
    async def forcar_fechar(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_admin(interaction.user):
            await interaction.response.send_message("Apenas admins.", ephemeral=True)
            return
        await interaction.response.send_modal(_FecharTicketModal())

    @discord.ui.button(label="Tickets Abertos", style=discord.ButtonStyle.secondary,
                       emoji="📂", custom_id="supad_abertos", row=1)
    async def tickets_abertos(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _is_admin(interaction.user):
            await interaction.response.send_message("Apenas admins.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        docs = await db.get_collection("tickets").find(
            {"status": {"$in": ["aberto", "pendente"]}}
        ).sort("created_at", 1).limit(15).to_list(15)
        embed = discord.Embed(title="Tickets Abertos", color=THEME2)
        if not docs:
            embed.description = "Nenhum ticket aberto."
        else:
            lines = []
            for doc in docs:
                # ✅ extraído antes da f-string — sem backslash dentro de {}
                atendente = f"<@{doc['atendente_id']}>" if doc.get("atendente_id") else "Sem atendente"
                lines.append(
                    f"`{doc.get('ticket_id','?')}` — {doc.get('categoria','?')} | {atendente}"
                )
            embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed, ephemeral=True)


class _BuscarTicketModal(discord.ui.Modal, title="Buscar Ticket"):
    ticket_id = discord.ui.TextInput(label="ID do ticket",
                                      placeholder="Ex: TKT-00000001",
                                      min_length=3, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        from models.ticket import Ticket
        from views.ticket_view import build_card_embed
        doc = await db.get_collection("tickets").find_one(
            {"ticket_id": self.ticket_id.value.strip()})
        if not doc:
            await interaction.followup.send("Ticket não encontrado.", ephemeral=True)
            return
        await interaction.followup.send(
            embed=build_card_embed(Ticket.from_dict(doc), interaction.guild),
            ephemeral=True)


class _FecharTicketModal(discord.ui.Modal, title="Forçar Fechamento de Ticket"):
    ticket_id = discord.ui.TextInput(label="ID do ticket",
                                      placeholder="Ex: TKT-00000001",
                                      min_length=3, max_length=20)
    motivo    = discord.ui.TextInput(label="Motivo",
                                      placeholder="Ex: Inatividade do usuário",
                                      min_length=5, max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        tid = self.ticket_id.value.strip()
        await db.get_collection("tickets").update_one(
            {"ticket_id": tid},
            {"$set": {
                "status":       "fechado",
                "closed_at":    utcnow(),
                "closed_by":    str(interaction.user.id),
                "close_reason": self.motivo.value,
                "updated_at":   utcnow(),
            }}
        )
        await interaction.followup.send(
            f"Ticket `{tid}` fechado administrativamente.", ephemeral=True)
