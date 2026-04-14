"""
analyst_embed.py

Embeds padronizados para o fluxo de analistas:
  - Painel de análise de casos
  - Card de analista ativo
  - Embed de blacklist (add / remove / listagem)
Todos usam THEME_COLOR = 0xFFD54F (dourado X1 Frifas)
"""
from __future__ import annotations

import discord
from utils.datetime_utils import utcnow

THEME_COLOR   = 0xFFD54F   # dourado
DANGER_COLOR  = 0xE74C3C   # vermelho — blacklist / reprovação
SUCCESS_COLOR = 0x27AE60   # verde   — aprovações
INFO_COLOR    = 0x3498DB   # azul    — informações neutras

FOOTER_TEXT = "X1 Frifas · Painel de Análise"


class AnalystEmbed:
    """Factory de embeds para o módulo Analista."""

    # ── Painel principal do canal #análise-de-casos ──────────────
    @staticmethod
    def painel_analise() -> discord.Embed:
        e = discord.Embed(
            title="🔍  Painel de Análise de Casos",
            description=(
                "Todos os casos abertos para análise aparecem aqui.\n\n"
                "**Como funciona**\n"
                "— Suporte abre um caso → analista avalia provas\n"
                "— Analista vota: Culpado / Inocente\n"
                "— Resultado é registrado no histórico automaticamente\n\n"
                "Selecione um caso abaixo para iniciar a análise."
            ),
            color=THEME_COLOR,
        )
        e.set_footer(text=FOOTER_TEXT)
        return e

    # ── Card de analista ativo ────────────────────────────────────
    @staticmethod
    def analista_ativo(
        member: discord.Member,
        casos_analisados: int = 0,
        casos_abertos: int = 0,
    ) -> discord.Embed:
        e = discord.Embed(
            title="🕵️  Analista Ativo",
            color=THEME_COLOR,
            timestamp=utcnow(),
        )
        e.add_field(name="Analista",         value=member.mention,        inline=True)
        e.add_field(name="Casos Analisados", value=str(casos_analisados), inline=True)
        e.add_field(name="Casos em Aberto",  value=str(casos_abertos),    inline=True)
        e.set_thumbnail(url=member.display_avatar.url)
        e.set_footer(text=FOOTER_TEXT)
        return e

    # ── Novo caso aberto ─────────────────────────────────────────
    @staticmethod
    def caso_aberto(
        numero: int,
        denunciado: discord.Member,
        denunciante: discord.Member,
        motivo: str,
        provas_url: str = "",
    ) -> discord.Embed:
        e = discord.Embed(
            title=f"📂  Caso #{numero:04d} — Em Análise",
            description=motivo,
            color=INFO_COLOR,
            timestamp=utcnow(),
        )
        e.add_field(name="Denunciado",  value=denunciado.mention,  inline=True)
        e.add_field(name="Denunciante", value=denunciante.mention, inline=True)
        if provas_url:
            e.add_field(name="Provas", value=f"[Ver provas]({provas_url})", inline=False)
        e.set_footer(text=FOOTER_TEXT)
        return e

    # ── Resultado do caso ────────────────────────────────────────
    @staticmethod
    def caso_resultado(
        numero: int,
        denunciado: discord.Member,
        veredicto: str,          # "Culpado" | "Inocente"
        analisado_por: discord.Member,
        observacao: str = "",
    ) -> discord.Embed:
        culpado = veredicto.lower() == "culpado"
        e = discord.Embed(
            title=f"{'⛔' if culpado else '✅'}  Caso #{numero:04d} — {veredicto}",
            color=DANGER_COLOR if culpado else SUCCESS_COLOR,
            timestamp=utcnow(),
        )
        e.add_field(name="Denunciado",    value=denunciado.mention,     inline=True)
        e.add_field(name="Veredicto",     value=veredicto,               inline=True)
        e.add_field(name="Analisado por", value=analisado_por.mention,  inline=True)
        if observacao:
            e.add_field(name="Observação", value=observacao, inline=False)
        e.set_footer(text=FOOTER_TEXT)
        return e


class BlacklistEmbed:
    """Factory de embeds para o módulo Blacklist."""

    FOOTER = "X1 Frifas · Blacklist"

    # ── Confirmação de adição ─────────────────────────────────────
    @staticmethod
    def adicionado(
        member: discord.Member,
        motivo: str,
        adicionado_por: discord.Member,
    ) -> discord.Embed:
        e = discord.Embed(
            title="⛔  Usuário Adicionado à Blacklist",
            color=DANGER_COLOR,
            timestamp=utcnow(),
        )
        e.add_field(name="Usuário",       value=f"{member.mention} (`{member.id}`)", inline=False)
        e.add_field(name="Motivo",        value=motivo,                               inline=False)
        e.add_field(name="Adicionado por", value=adicionado_por.mention,             inline=True)
        e.set_thumbnail(url=member.display_avatar.url)
        e.set_footer(text=BlacklistEmbed.FOOTER)
        return e

    # ── Confirmação de remoção ───────────────────────────────────
    @staticmethod
    def removido(
        member: discord.Member,
        removido_por: discord.Member,
    ) -> discord.Embed:
        e = discord.Embed(
            title="✅  Usuário Removido da Blacklist",
            color=SUCCESS_COLOR,
            timestamp=utcnow(),
        )
        e.add_field(name="Usuário",     value=f"{member.mention} (`{member.id}`)", inline=False)
        e.add_field(name="Removido por", value=removido_por.mention,               inline=True)
        e.set_thumbnail(url=member.display_avatar.url)
        e.set_footer(text=BlacklistEmbed.FOOTER)
        return e

    # ── Listagem paginada ─────────────────────────────────────────
    @staticmethod
    def listagem(entradas: list[dict], pagina: int, total_paginas: int) -> discord.Embed:
        e = discord.Embed(
            title="📋  Blacklist — Usuários Banidos",
            color=DANGER_COLOR,
        )
        if not entradas:
            e.description = "Nenhum usuário na blacklist no momento."
        else:
            linhas = []
            for idx, doc in enumerate(entradas, start=1):
                uid    = doc.get("user_id", "—")
                nome   = doc.get("username", "—")
                motivo = doc.get("motivo", "—")[:60]
                linhas.append(f"`{idx}.` <@{uid}> · **{nome}**\n     ↳ {motivo}")
            e.description = "\n\n".join(linhas)
        e.set_footer(text=f"X1 Frifas · Blacklist · Pág. {pagina}/{total_paginas}")
        return e

    # ── Aviso público (canal #exposed) ────────────────────────────
    @staticmethod
    def exposed(
        member: discord.Member,
        motivo: str,
        provas_url: str = "",
    ) -> discord.Embed:
        e = discord.Embed(
            title="🚫  Jogador Banido — X1 Frifas",
            description=(
                f"{member.mention} foi adicionado à blacklist e está "
                "**impedido de participar** de partidas neste servidor."
            ),
            color=DANGER_COLOR,
            timestamp=utcnow(),
        )
        e.add_field(name="Motivo", value=motivo, inline=False)
        if provas_url:
            e.add_field(name="Provas", value=f"[Ver provas]({provas_url})", inline=False)
        e.set_thumbnail(url=member.display_avatar.url)
        e.set_footer(text="X1 Frifas · Blacklist pública")
        return e


class MediatorEmbed:
    """Factory de embeds padronizados para o módulo Mediador."""

    FOOTER = "X1 Frifas · Mediadores"

    # ── Dashboard de mediadores ───────────────────────────────────
    @staticmethod
    def dashboard(
        mediadores_ativos: int,
        mediadores_fila: int,
        partidas_em_andamento: int,
    ) -> discord.Embed:
        e = discord.Embed(
            title="🎮  Dashboard — Mediadores",
            color=THEME_COLOR,
            timestamp=utcnow(),
        )
        e.add_field(name="Mediadores Ativos",        value=str(mediadores_ativos),       inline=True)
        e.add_field(name="Na Fila",                  value=str(mediadores_fila),          inline=True)
        e.add_field(name="Partidas em Andamento",    value=str(partidas_em_andamento),    inline=True)
        e.set_footer(text=MediatorEmbed.FOOTER)
        return e

    # ── Card de mediador individual ───────────────────────────────
    @staticmethod
    def perfil(
        member: discord.Member,
        partidas: int = 0,
        avaliacao: float = 0.0,
        expiracao: str = "—",
    ) -> discord.Embed:
        e = discord.Embed(
            title=f"🛡️  Mediador — {member.display_name}",
            color=THEME_COLOR,
            timestamp=utcnow(),
        )
        e.add_field(name="Partidas Mediadas", value=str(partidas),       inline=True)
        e.add_field(name="Avaliação",         value=f"⭐ {avaliacao:.1f}", inline=True)
        e.add_field(name="Licença válida até", value=expiracao,          inline=True)
        e.set_thumbnail(url=member.display_avatar.url)
        e.set_footer(text=MediatorEmbed.FOOTER)
        return e

    # ── Mediador silenciado ───────────────────────────────────────
    @staticmethod
    def silenciado(
        member: discord.Member,
        motivo: str,
        por: discord.Member,
        duracao: str = "indefinida",
    ) -> discord.Embed:
        e = discord.Embed(
            title="🔇  Mediador Silenciado",
            color=DANGER_COLOR,
            timestamp=utcnow(),
        )
        e.add_field(name="Mediador",  value=member.mention, inline=True)
        e.add_field(name="Por",       value=por.mention,    inline=True)
        e.add_field(name="Duração",   value=duracao,         inline=True)
        e.add_field(name="Motivo",    value=motivo,          inline=False)
        e.set_thumbnail(url=member.display_avatar.url)
        e.set_footer(text=MediatorEmbed.FOOTER)
        return e

    # ── AFK / Fora da fila ────────────────────────────────────────
    @staticmethod
    def afk_lista(mediadores_afk: list[dict]) -> discord.Embed:
        e = discord.Embed(
            title="💤  Mediadores AFK / Fora da Fila",
            color=INFO_COLOR,
            timestamp=utcnow(),
        )
        if not mediadores_afk:
            e.description = "Nenhum mediador AFK no momento."
        else:
            linhas = []
            for doc in mediadores_afk:
                uid   = doc.get("user_id", "—")
                nome  = doc.get("username", "—")
                desde = doc.get("afk_since", "—")
                linhas.append(f"<@{uid}> · **{nome}** · AFK desde `{desde}`")
            e.description = "\n".join(linhas)
        e.set_footer(text=MediatorEmbed.FOOTER)
        return e
