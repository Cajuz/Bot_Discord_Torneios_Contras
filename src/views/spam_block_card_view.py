import discord
from datetime import datetime
from typing import Optional

# Referência injetada pelo main.py para evitar import circular
_anti_spam_service = None


def set_anti_spam_service(service):
    global _anti_spam_service
    _anti_spam_service = service


# ─────────────────────────────────────────────
# Embeds
# ─────────────────────────────────────────────

def create_blocked_embed(
    member_id: int,
    member_name: str,
    member_avatar_url: str,
    reason: str,
    evidence: str,
    blocked_at: datetime
) -> discord.Embed:
    embed = discord.Embed(
        title="🚫 Membro Bloqueado",
        color=discord.Color.red()
    )
    embed.set_thumbnail(url=member_avatar_url or "")
    embed.add_field(name="👤 Membro",       value=f"<@{member_id}> (`{member_name}`)", inline=False)
    embed.add_field(name="📋 Motivo",        value=reason or "—",                       inline=False)
    if evidence:
        embed.add_field(name="🔍 Evidência", value=evidence,                            inline=False)
    embed.add_field(name="📊 Status",        value="🔴 **BLOQUEADO**",                  inline=True)
    embed.add_field(
        name="🕐 Bloqueado em",
        value=f"<t:{int(blocked_at.timestamp())}:f>",
        inline=True
    )
    embed.set_footer(text=f"member_id:{member_id}")
    return embed


def create_unblocked_embed(
    member_id: int,
    member_name: str,
    member_avatar_url: str,
    reason: str,
    evidence: str,
    blocked_at: Optional[datetime],
    unblocked_by_id: int,
    unblocked_by_name: str,
    unblocked_at: datetime
) -> discord.Embed:
    embed = discord.Embed(
        title="✅ Membro Desbloqueado",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=member_avatar_url or "")
    embed.add_field(name="👤 Membro",          value=f"<@{member_id}> (`{member_name}`)",              inline=False)
    embed.add_field(name="📋 Motivo orig.",     value=reason or "—",                                    inline=False)
    if evidence:
        embed.add_field(name="🔍 Evidência",   value=evidence,                                          inline=False)
    embed.add_field(name="📊 Status",           value="🟢 **DESBLOQUEADO**",                            inline=True)
    if blocked_at:
        embed.add_field(
            name="🕐 Bloqueado em",
            value=f"<t:{int(blocked_at.timestamp())}:f>",
            inline=True
        )
    embed.add_field(
        name="🔓 Desbloqueado em",
        value=f"<t:{int(unblocked_at.timestamp())}:f>",
        inline=True
    )
    embed.add_field(
        name="👮 Desbloqueado por",
        value=f"<@{unblocked_by_id}> (`{unblocked_by_name}`)",
        inline=False
    )
    embed.set_footer(text=f"member_id:{member_id}")
    return embed


# ─────────────────────────────────────────────
# View persistente
# ─────────────────────────────────────────────

class SpamBlockCardView(discord.ui.View):
    """
    View do card de bloqueio por spam.
    Persistent: custom_id fixo 'unblock_spam_card'.
    Registrada UMA vez no on_ready com bot.add_view(SpamBlockCardView()).
    """

    def __init__(self, disabled: bool = False):
        super().__init__(timeout=None)
        self.unblock_btn.disabled = disabled

    @discord.ui.button(
        label="Desbloquear",
        style=discord.ButtonStyle.success,
        custom_id="unblock_spam_card",
        emoji="🔓"
    )
    async def unblock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Apenas administradores podem desbloquear membros.", ephemeral=True
            )
            return

        if not interaction.message or not interaction.message.embeds:
            await interaction.response.send_message("❌ Não consegui ler o card.", ephemeral=True)
            return

        # Extrai member_id do footer
        footer_text = interaction.message.embeds[0].footer.text or ""
        member_id_str = footer_text.replace("member_id:", "").strip()

        try:
            member_id = int(member_id_str)
        except ValueError:
            await interaction.response.send_message("❌ ID inválido no card.", ephemeral=True)
            return

        if not _anti_spam_service:
            await interaction.response.send_message("❌ Serviço não inicializado.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        guild  = interaction.guild
        member = guild.get_member(member_id)

        try:
            await _anti_spam_service.unblock_member(
                guild=guild,
                member=member,
                by=interaction.user,
                card_message=interaction.message,
                member_id_fallback=member_id
            )
            await interaction.followup.send(
                f"✅ Membro <@{member_id}> desbloqueado com sucesso!", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao desbloquear: {e}", ephemeral=True)
