# services/thread_log_service.py

"""
Gera um arquivo HTML + media (zip) com o log completo da thread de partida.
Envia o zip como UM único arquivo no canal #logs-partidas.
"""

import asyncio
import io
import os
import re
import zipfile
import aiohttp
import discord
from datetime import datetime
from utils.datetime_utils import utcnow
from typing import Optional, List, Tuple
from config.database import db
from utils.logger import logger

LOGS_CHANNEL_NAME = "logs-partidas"
MAX_FILE_MB       = 24          # limite seguro do Discord
MAX_EMBED_MB      = 2           # imagens acima disso ficam como link no HTML
MAX_ZIP_MB        = 24          # zip total


# ─────────────────────────────────────────────────────────────
# CSS + HTML template
# ─────────────────────────────────────────────────────────────

HTML_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  background: #1a1a2e;
  color: #e0e0e0;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  font-size: 14px;
  line-height: 1.5;
}

.container { max-width: 900px; margin: 0 auto; padding: 20px; }

/* ── Header ── */
.header {
  background: linear-gradient(135deg, #16213e, #0f3460);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  border: 1px solid #e94560;
  box-shadow: 0 4px 20px rgba(233,69,96,0.2);
}
.header h1 { color: #e94560; font-size: 22px; margin-bottom: 4px; }
.header .match-id { color: #888; font-size: 12px; margin-bottom: 16px; font-family: monospace; }

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-top: 16px;
}
.info-card {
  background: rgba(255,255,255,0.05);
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}
.info-card .label { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 1px; }
.info-card .value { font-size: 16px; font-weight: bold; color: #fff; margin-top: 4px; }
.info-card .value.green  { color: #4ade80; }
.info-card .value.red    { color: #f87171; }
.info-card .value.blue   { color: #60a5fa; }
.info-card .value.yellow { color: #facc15; }

.teams {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 16px;
}
.team-card {
  background: rgba(255,255,255,0.04);
  border-radius: 8px;
  padding: 12px;
}
.team-card.winner { border: 1px solid #facc15; }
.team-card h3 { font-size: 13px; margin-bottom: 8px; }
.team-card h3.blue { color: #60a5fa; }
.team-card h3.red  { color: #f87171; }
.team-card ul { list-style: none; }
.team-card ul li { font-size: 13px; padding: 2px 0; color: #ccc; }

/* ── Status badge ── */
.badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.badge.finalizado { background: #166534; color: #4ade80; }
.badge.cancelado  { background: #7f1d1d; color: #f87171; }
.badge.forcado    { background: #78350f; color: #fb923c; }

/* ── Timeline ── */
.timeline-header {
  font-size: 13px;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 2px;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #2a2a4a;
}

.message {
  display: flex;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.message:last-child { border-bottom: none; }

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #2a2a4a;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 14px;
  flex-shrink: 0;
  color: #fff;
}
.avatar.bot { background: #4f46e5; }

.msg-body { flex: 1; min-width: 0; }

.msg-meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 4px;
}
.msg-author        { font-weight: bold; font-size: 13px; color: #a78bfa; }
.msg-author.bot    { color: #818cf8; }
.msg-author.mediator { color: #34d399; }
.msg-timestamp     { font-size: 11px; color: #555; }

.msg-content       { color: #d1d5db; word-break: break-word; }
.msg-content pre   {
  background: #0d0d1a;
  border-radius: 6px;
  padding: 10px;
  overflow-x: auto;
  font-family: monospace;
  font-size: 13px;
  margin-top: 6px;
  border-left: 3px solid #4f46e5;
}

/* ── Bot embed ── */
.bot-embed {
  border-left: 4px solid #4f46e5;
  background: rgba(79,70,229,0.08);
  border-radius: 0 8px 8px 0;
  padding: 10px 14px;
  margin-top: 6px;
}
.bot-embed.green  { border-color: #4ade80; background: rgba(74,222,128,0.06); }
.bot-embed.red    { border-color: #f87171; background: rgba(248,113,113,0.06); }
.bot-embed.gold   { border-color: #facc15; background: rgba(250,204,21,0.06); }
.bot-embed.blue   { border-color: #60a5fa; background: rgba(96,165,250,0.06); }
.bot-embed.grey   { border-color: #6b7280; background: rgba(107,114,128,0.06); }
.bot-embed-title  { font-weight: bold; font-size: 13px; margin-bottom: 6px; color: #fff; }
.bot-embed-desc   { font-size: 13px; color: #9ca3af; white-space: pre-wrap; }
.bot-embed-field  { margin-top: 8px; }
.bot-embed-field-name  { font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; }
.bot-embed-field-value { font-size: 13px; color: #d1d5db; }

/* ── Mídia ── */
.attachment       { margin-top: 8px; }
.attachment img   {
  max-width: 100%;
  max-height: 400px;
  border-radius: 8px;
  cursor: pointer;
  transition: opacity 0.2s;
}
.attachment img:hover { opacity: 0.9; }

.attachment video {
  max-width: 100%;
  max-height: 400px;
  border-radius: 8px;
}

.attachment-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255,255,255,0.06);
  border-radius: 6px;
  padding: 8px 12px;
  color: #60a5fa;
  text-decoration: none;
  font-size: 13px;
}
.attachment-link:hover { background: rgba(255,255,255,0.1); }

/* ── Footer ── */
.footer {
  margin-top: 32px;
  padding: 16px;
  background: #0d0d1a;
  border-radius: 8px;
  text-align: center;
  color: #444;
  font-size: 12px;
}

/* ── Lightbox ── */
#lightbox {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.92);
  z-index: 1000;
  align-items: center;
  justify-content: center;
  cursor: zoom-out;
}
#lightbox.active { display: flex; }
#lightbox img    { max-width: 95vw; max-height: 95vh; border-radius: 8px; }

/* ── Scrollbar ── */
::-webkit-scrollbar       { width: 6px; }
::-webkit-scrollbar-track { background: #0d0d1a; }
::-webkit-scrollbar-thumb { background: #2a2a4a; border-radius: 3px; }
"""

HTML_JS = """
document.querySelectorAll('.attachment img').forEach(img => {
  img.addEventListener('click', () => {
    const lb = document.getElementById('lightbox');
    document.getElementById('lb-img').src = img.src;
    lb.classList.add('active');
  });
});
document.getElementById('lightbox').addEventListener('click', () => {
  document.getElementById('lightbox').classList.remove('active');
});
"""


def _color_class(color_value) -> str:
    """Converte discord.Color em classe CSS."""
    if color_value is None:
        return "grey"
    v = int(color_value)
    MAP = {
        0x57F287: "green",   # green
        0x2ECC71: "green",
        0x4ade80: "green",
        0xED4245: "red",
        0xf87171: "red",
        0xFEE75C: "gold",
        0xFFD700: "gold",
        0xfacc15: "gold",
        0x5865F2: "blue",
        0x3498DB: "blue",
        0x60a5fa: "blue",
    }
    return MAP.get(v, "grey")


def _avatar_letter(name: str) -> str:
    return (name[0] if name else "?").upper()


def _escape(text: str) -> str:
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ─────────────────────────────────────────────────────────────
# Serviço principal
# ─────────────────────────────────────────────────────────────

class ThreadLogService:

    def __init__(self, bot: discord.Client):
        self.bot = bot

    # ── API pública ───────────────────────────────────────────

    async def archive_thread(self, thread: discord.Thread, match: dict):
        """
        Gera o ZIP (HTML + media) e envia como arquivo único em #logs-partidas.
        """
        try:
            guild        = thread.guild
            logs_channel = discord.utils.get(guild.text_channels, name=LOGS_CHANNEL_NAME)
            if not logs_channel:
                logger.warning(f"[ThreadLog] Canal #{LOGS_CHANNEL_NAME} não encontrado.")
                return

            messages = await self._fetch_messages(thread)
            if not messages:
                logger.info(f"[ThreadLog] Thread {thread.id} sem mensagens.")
                return

            match_id = str(match.get("_id", thread.id))
            logger.info(f"[ThreadLog] Gerando HTML para match {match_id}...")

            zip_buffer, filename = await self._build_zip(thread, match, messages, match_id)

            size_mb = zip_buffer.getbuffer().nbytes / (1024 * 1024)
            if size_mb > MAX_ZIP_MB:
                logger.warning(f"[ThreadLog] ZIP muito grande ({size_mb:.1f}MB) — enviando só HTML.")
                zip_buffer, filename = await self._build_zip(
                    thread, match, messages, match_id, media_only=False
                )

            file  = discord.File(fp=zip_buffer, filename=filename)
            venc  = match.get("vencedor", "—")
            label = "🔵 Blue" if venc == "blue" else ("🔴 Red" if venc == "red" else "—")
            bet   = match.get("bet_value", 0)
            modo  = match.get("match_type", "?").upper()

            embed = discord.Embed(
                title="📦 Log de Partida Gerado",
                description=(
                    f"**Match:** `{match_id}`\n"
                    f"**Modo:** {modo} | **Aposta:** R$ {bet:.2f}\n"
                    f"**Vencedor:** {label} | **Mensagens:** {len(messages)}\n"
                    f"**Canal:** `#{match.get('channel_name','?')}`"
                ),
                color=discord.Color.green() if match.get("status") == "finalizado"
                      else discord.Color.red()
            )
            embed.add_field(
                name="📂 Como abrir",
                value=(
                    "1. Baixe o arquivo ZIP\n"
                    "2. Extraia em qualquer pasta\n"
                    "3. Abra `index.html` no navegador"
                ),
                inline=False
            )
            embed.set_footer(text=f"Gerado em {utcnow().strftime('%d/%m/%Y %H:%M')} UTC")

            await logs_channel.send(embed=embed, file=file)
            logger.info(f"[ThreadLog] ZIP enviado para #{LOGS_CHANNEL_NAME}: {filename}")

        except Exception as e:
            logger.error(f"[ThreadLog] Erro ao arquivar thread {thread.id}: {e}", exc_info=True)

    # ── Geração do ZIP ────────────────────────────────────────

    async def _build_zip(
        self,
        thread: discord.Thread,
        match: dict,
        messages: List[discord.Message],
        match_id: str,
        media_only: bool = True,
    ) -> Tuple[io.BytesIO, str]:
        """
        Retorna (BytesIO do zip, filename).
        media_only=True  → salva mídia em media/ e referencia no HTML
        media_only=False → só o HTML (sem downloads)
        """
        zip_buffer = io.BytesIO()
        media_map: dict[str, str] = {}   # att.url → "media/arquivo.ext"

        # ── 1. Baixa mídias ───────────────────────────────────
        media_files: dict[str, bytes] = {}   # filename → bytes

        if media_only:
            counter = 1
            for msg in messages:
                for att in msg.attachments:
                    size_mb = att.size / (1024 * 1024)
                    if size_mb > MAX_FILE_MB:
                        media_map[att.url] = ""   # marca como "grande demais"
                        continue
                    ext      = os.path.splitext(att.filename)[1].lower() or ".bin"
                    fname    = f"media/{counter:03d}_{att.filename}"
                    data     = await self._download(att.url)
                    if data:
                        media_files[fname] = data
                        media_map[att.url] = fname
                    counter += 1
                    await asyncio.sleep(0.1)

        # ── 2. Gera HTML ──────────────────────────────────────
        html = self._build_html(thread, match, messages, match_id, media_map)

        # ── 3. Monta ZIP ──────────────────────────────────────
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("index.html", html.encode("utf-8"))
            for fname, data in media_files.items():
                zf.writestr(fname, data)

        zip_buffer.seek(0)
        filename = f"match_{match_id[:12]}.zip"
        return zip_buffer, filename

    # ── Geração do HTML ───────────────────────────────────────

    def _build_html(
        self,
        thread: discord.Thread,
        match: dict,
        messages: List[discord.Message],
        match_id: str,
        media_map: dict,
    ) -> str:
        status   = match.get("status", "?")
        bet      = match.get("bet_value", 0)
        taxa     = bet * 0.25
        premio   = bet * 2
        vencedor = match.get("vencedor")
        modo     = match.get("match_type", "?").upper()
        gel      = match.get("gel_type", "normal").capitalize()
        canal    = match.get("channel_name", "?")
        created  = match.get("created_at")
        mediator = str(match.get("mediator_id", "?"))

        time_blue = match.get("time_blue", [])
        time_red  = match.get("time_red", [])
        player_ids = [str(p) for p in match.get("player_ids", [])]

        badge_class = {"finalizado": "finalizado", "cancelado": "cancelado"}.get(status, "forcado")
        badge_label = {"finalizado": "✅ Finalizado", "cancelado": "❌ Cancelado"}.get(status, "⚡ Forçado")
        blue_winner = vencedor == "blue"
        red_winner  = vencedor == "red"

        # ── Teams ─────────────────────────────────────────────
        def team_html(ids, color, winner):
            cls = "winner" if winner else ""
            trophy = "🏆 " if winner else ""
            items  = "".join(f"<li>👤 {_escape(str(uid))}</li>" for uid in ids) or "<li>—</li>"
            return (
                f'<div class="team-card {cls}">'
                f'<h3 class="{color}">{trophy}{"🔵 Time Blue" if color=="blue" else "🔴 Time Red"}</h3>'
                f'<ul>{items}</ul></div>'
            )

        teams_html = (
            f'<div class="teams">'
            f'{team_html(time_blue, "blue", blue_winner)}'
            f'{team_html(time_red,  "red",  red_winner)}'
            f'</div>'
        ) if (time_blue or time_red) else ""

        created_str = created.strftime("%d/%m/%Y %H:%M") if created else "—"

        header = f"""
<div class="header">
  <h1>⚔️ Log de Partida — {_escape(modo)}</h1>
  <div class="match-id">ID: {_escape(match_id)} &nbsp;|&nbsp; Thread: {thread.id}</div>
  <span class="badge {badge_class}">{badge_label}</span>
  <div class="info-grid">
    <div class="info-card">
      <div class="label">Canal</div>
      <div class="value">#{_escape(canal)}</div>
    </div>
    <div class="info-card">
      <div class="label">GEL</div>
      <div class="value">{_escape(gel)}</div>
    </div>
    <div class="info-card">
      <div class="label">Aposta</div>
      <div class="value yellow">R$ {bet:.2f}</div>
    </div>
    <div class="info-card">
      <div class="label">Prêmio</div>
      <div class="value green">R$ {premio:.2f}</div>
    </div>
    <div class="info-card">
      <div class="label">Taxa</div>
      <div class="value">R$ {taxa:.2f}</div>
    </div>
    <div class="info-card">
      <div class="label">Criada em</div>
      <div class="value">{created_str}</div>
    </div>
    <div class="info-card">
      <div class="label">Mediador</div>
      <div class="value blue">{_escape(mediator)}</div>
    </div>
    <div class="info-card">
      <div class="label">Mensagens</div>
      <div class="value">{len(messages)}</div>
    </div>
  </div>
  {teams_html}
</div>
"""

        # ── Timeline de mensagens ─────────────────────────────
        timeline_items = []
        for msg in messages:
            timeline_items.append(self._render_message(msg, match, media_map))

        timeline = f"""
<div class="timeline-header">💬 Timeline da Partida</div>
{''.join(timeline_items)}
"""

        # ── Footer ────────────────────────────────────────────
        total_media = sum(len(m.attachments) for m in messages)
        total_bot   = sum(1 for m in messages if m.author.bot)
        total_user  = len(messages) - total_bot
        now_str     = utcnow().strftime("%d/%m/%Y %H:%M UTC")

        footer = f"""
<div class="footer">
  💬 {total_user} mensagens de usuários &nbsp;|&nbsp;
  🤖 {total_bot} mensagens do bot &nbsp;|&nbsp;
  🖼️ {total_media} arquivos de mídia<br>
  Gerado automaticamente em {now_str}
</div>
"""

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Log — Match {_escape(match_id[:12])}</title>
  <style>{HTML_CSS}</style>
</head>
<body>
<div id="lightbox">
  <img id="lb-img" src="" alt="preview">
</div>
<div class="container">
  {header}
  {timeline}
  {footer}
</div>
<script>{HTML_JS}</script>
</body>
</html>"""

    def _render_message(
        self,
        msg: discord.Message,
        match: dict,
        media_map: dict,
    ) -> str:
        is_bot      = msg.author.bot
        author_name = _escape(msg.author.display_name)
        ts          = msg.created_at.strftime("%H:%M:%S")
        mediator_id = str(match.get("mediator_id", ""))
        is_mediator = str(msg.author.id) == mediator_id

        author_class = "bot" if is_bot else ("mediator" if is_mediator else "")
        avatar_class = "bot" if is_bot else ""
        letter       = "🤖" if is_bot else _avatar_letter(msg.author.display_name)

        # ── Conteúdo de texto ─────────────────────────────────
        content_html = ""
        if msg.content and msg.content.strip():
            text = _escape(msg.content)
            # destaca mentions (@número)
            text = re.sub(r"&lt;@(\d+)&gt;", r'<span style="color:#a78bfa">@\1</span>', text)
            content_html = f'<div class="msg-content">{text}</div>'

        # ── Embeds do bot ─────────────────────────────────────
        embeds_html = ""
        if is_bot and msg.embeds:
            parts = []
            for emb in msg.embeds:
                cc    = _color_class(emb.color)
                title = f'<div class="bot-embed-title">{_escape(emb.title or "")}</div>' if emb.title else ""
                desc  = f'<div class="bot-embed-desc">{_escape(emb.description or "")}</div>' if emb.description else ""
                fields = ""
                for f in emb.fields:
                    fields += (
                        f'<div class="bot-embed-field">'
                        f'<div class="bot-embed-field-name">{_escape(f.name)}</div>'
                        f'<div class="bot-embed-field-value">{_escape(f.value)}</div>'
                        f'</div>'
                    )
                parts.append(
                    f'<div class="bot-embed {cc}">{title}{desc}{fields}</div>'
                )
            embeds_html = "".join(parts)

        # ── Attachments ───────────────────────────────────────
        attachments_html = ""
        for att in msg.attachments:
            fname = att.filename.lower()
            local = media_map.get(att.url, "")

            if any(fname.endswith(e) for e in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
                src = local if local else att.url
                attachments_html += (
                    f'<div class="attachment">'
                    f'<img src="{_escape(src)}" alt="{_escape(att.filename)}" title="{_escape(att.filename)}">'
                    f'</div>'
                )
            elif any(fname.endswith(e) for e in [".mp4", ".mov", ".avi", ".webm"]):
                if local:
                    attachments_html += (
                        f'<div class="attachment">'
                        f'<video controls src="{_escape(local)}"></video>'
                        f'</div>'
                    )
                else:
                    attachments_html += (
                        f'<div class="attachment">'
                        f'<a class="attachment-link" href="{_escape(att.url)}" target="_blank">'
                        f'🎥 {_escape(att.filename)} (link externo — arquivo grande)</a>'
                        f'</div>'
                    )
            else:
                src = local if local else att.url
                attachments_html += (
                    f'<div class="attachment">'
                    f'<a class="attachment-link" href="{_escape(src)}">'
                    f'📎 {_escape(att.filename)}</a>'
                    f'</div>'
                )

        body = content_html + embeds_html + attachments_html
        if not body.strip():
            return ""   # mensagem vazia (ex: só sticker)

        return f"""
<div class="message">
  <div class="avatar {avatar_class}">{letter}</div>
  <div class="msg-body">
    <div class="msg-meta">
      <span class="msg-author {author_class}">{author_name}</span>
      <span class="msg-timestamp">{ts}</span>
    </div>
    {body}
  </div>
</div>"""

    # ── Helpers ───────────────────────────────────────────────

    async def _fetch_messages(self, thread: discord.Thread) -> List[discord.Message]:
        msgs = []
        try:
            async for m in thread.history(limit=500, oldest_first=True):
                msgs.append(m)
        except discord.Forbidden:
            logger.warning(f"[ThreadLog] Sem permissão para ler thread {thread.id}")
        except Exception as e:
            logger.error(f"[ThreadLog] Erro ao ler mensagens: {e}")
        return msgs

    async def _download(self, url: str) -> Optional[bytes]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except Exception as e:
            logger.warning(f"[ThreadLog] Falha ao baixar {url}: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────

_thread_log_service: Optional[ThreadLogService] = None


def init_thread_log_service(bot: discord.Client) -> ThreadLogService:
    global _thread_log_service
    _thread_log_service = ThreadLogService(bot)
    return _thread_log_service


def get_thread_log_service() -> Optional[ThreadLogService]:
    return _thread_log_service
