"""
influencer_live_match_view.py
View da thread de partida no modo contra (equivalente ao match_thread_view,
porém adaptado ao fluxo influencer_live).

Thread criada em contra-<influencer> com:
  - Confirmação de presença do desafiante
  - Painel de resultado (Controller Live declara vencedor)
  - Cancelamento de emergência (ADM)
"""
from __future__ import annotations
import discord
from discord.ui import View, Button, Modal, TextInput
from utils.logger import logger
from utils.datetime_utils import utcnow

THEME_LIVE = 0xE91E63


# ══════════════════════════════════════════════════════════════════════════════
# MODAL — confirmação de pagamento PIX pelo desafiante
# ══════════════════════════════════════════════════════════════════════════════

class ContraPaymentModal(Modal, title="Confirmação de Pagamento"):
    comprovante = TextInput(
        label="Chave PIX do Mediador / Comprovante",
        placeholder="Cole aqui a chave PIX usada ou número do comprovante",
        style=discord.TextStyle.short,
        required=True,
        max_length=200,
    )
    observacao = TextInput(
        label="Observação (opcional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=400,
    )

    def __init__(self, match_id: str, player_id: int):
        super().__init__()
        self.match_id  = match_id
        self.player_id = player_id

    async def on_submit(self, interaction: discord.Interaction):
        from services.match_service import match_service
        # register_payment_confirmation só recebe match_id
        updated = await match_service.register_payment_confirmation(
            match_id=self.match_id,
        )
        if not updated:
            await interaction.response.send_message(
                "❌ Não foi possível registrar o pagamento. Contate um admin.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "✅ Pagamento confirmado! Aguarde o Controller Live abrir a sala.",
            ephemeral=True,
        )
        logger.info(f"[ContraMatch] Pagamento confirmado — match {self.match_id} player {self.player_id}")


# ══════════════════════════════════════════════════════════════════════════════
# VIEW DE CONFIRMAÇÃO — desafiante confirma presença e pagamento
# ══════════════════════════════════════════════════════════════════════════════

class ContraConfirmView(View):
    """
    Postada na thread logo após a partida ser criada.
    O desafiante confirma presença; o influencer já está confirmado automaticamente.
    """

    def __init__(self, match_id: str, challenger_id: int, influencer_id: int):
        super().__init__(timeout=None)
        self.match_id      = match_id
        self.challenger_id = challenger_id
        self.influencer_id = influencer_id

    @discord.ui.button(
        label="✅ Confirmar Presença & Pagamento",
        style=discord.ButtonStyle.success,
        custom_id="contra_confirm_presence",
    )
    async def confirm_presence(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.challenger_id:
            await interaction.response.send_message(
                "❌ Apenas o desafiante desta partida pode confirmar aqui.",
                ephemeral=True,
            )
            return

        modal = ContraPaymentModal(
            match_id=self.match_id,
            player_id=interaction.user.id,
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="❌ Desistir",
        style=discord.ButtonStyle.secondary,
        custom_id="contra_give_up",
    )
    async def give_up(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.challenger_id:
            await interaction.response.send_message(
                "❌ Apenas o desafiante pode desistir.", ephemeral=True)
            return

        from services.influencer_live_queue_service import influencer_live_queue_service
        from services.match_service import match_service
        from config.discord_bot import get_bot

        await match_service.cancel_match(
            match_id=self.match_id,
            reason=f"Desistência do desafiante <@{self.challenger_id}>",
        )
        await influencer_live_queue_service.advance_queue(
            influencer_id=str(self.influencer_id),
            guild_id=str(interaction.guild_id),
            bot=get_bot(),
        )

        await interaction.response.send_message(
            "✅ Você desistiu. O próximo da fila será chamado.", ephemeral=True)
        await interaction.channel.send(
            f"⚠️ <@{self.challenger_id}> desistiu. Chamando próximo da fila...")
        logger.info(f"[ContraMatch] Desistência — match {self.match_id} challenger {self.challenger_id}")


# ══════════════════════════════════════════════════════════════════════════════
# VIEW DE RESULTADO — Controller Live declara vencedor
# ══════════════════════════════════════════════════════════════════════════════

class ContraResultView(View):
    """
    Postada pelo bot após `/sala_live` — Controller Live declara quem ganhou.
    """

    def __init__(
        self,
        match_id: str,
        influencer_id: int,
        challenger_id: int,
        guild_id: int,
    ):
        super().__init__(timeout=None)
        self.match_id      = match_id
        self.influencer_id = influencer_id
        self.challenger_id = challenger_id
        self.guild_id      = guild_id

    async def _declare_winner(
        self,
        interaction: discord.Interaction,
        vencedor: str,          # 'influencer' | 'challenger'
        winner_id: int,
        loser_id: int,
    ):
        """Lógica comum de declaração de vencedor."""
        role   = discord.utils.get(interaction.guild.roles, name="Controller Live")
        is_adm = interaction.user.guild_permissions.administrator
        is_cl  = role and role in interaction.user.roles

        if not (is_adm or is_cl):
            await interaction.response.send_message(
                "❌ Apenas **Controller Live** ou **ADM** podem declarar o resultado.",
                ephemeral=True,
            )
            return

        from services.match_service import match_service
        from services.influencer_live_queue_service import influencer_live_queue_service
        from views.influencer_live_view import build_contra_match_result_embed
        from config.discord_bot import get_bot

        # finish_live_match(match_id, vencedor: 'influencer'|'challenger')
        updated = await match_service.finish_live_match(
            match_id=self.match_id,
            vencedor=vencedor,
        )

        if not updated:
            await interaction.response.send_message(
                "❌ Não foi possível finalizar a partida. Verifique o status.",
                ephemeral=True,
            )
            return

        bet_value = updated.get("bet_value", 0.0)
        prize     = bet_value * 2

        winner = interaction.guild.get_member(winner_id) or await interaction.guild.fetch_member(winner_id)
        loser  = interaction.guild.get_member(loser_id)  or await interaction.guild.fetch_member(loser_id)

        embed = build_contra_match_result_embed(
            winner=winner,
            loser=loser,
            prize=prize,
            match_id=self.match_id,
        )

        # Desabilita todos os botões após o resultado
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(view=self)
        await interaction.channel.send(
            content=f"🏆 {winner.mention} venceu! {loser.mention} foi derrotado.",
            embed=embed,
        )

        # Avança a fila para o próximo desafiante (com bot para notificar)
        await influencer_live_queue_service.advance_queue(
            influencer_id=str(self.influencer_id),
            guild_id=str(self.guild_id),
            bot=get_bot(),
        )

        logger.info(
            f"[ContraMatch] Resultado declarado — match {self.match_id} "
            f"vencedor {winner_id} — por {interaction.user.name}"
        )

    @discord.ui.button(
        label="🎥 Influencer Venceu",
        style=discord.ButtonStyle.primary,
        custom_id="contra_influencer_wins",
        emoji="🏆",
    )
    async def influencer_wins(self, interaction: discord.Interaction, button: Button):
        await self._declare_winner(
            interaction,
            vencedor="influencer",
            winner_id=self.influencer_id,
            loser_id=self.challenger_id,
        )

    @discord.ui.button(
        label="⚔️ Desafiante Venceu",
        style=discord.ButtonStyle.danger,
        custom_id="contra_challenger_wins",
        emoji="🏆",
    )
    async def challenger_wins(self, interaction: discord.Interaction, button: Button):
        await self._declare_winner(
            interaction,
            vencedor="challenger",
            winner_id=self.challenger_id,
            loser_id=self.influencer_id,
        )

    @discord.ui.button(
        label="⚠️ Cancelar Partida",
        style=discord.ButtonStyle.secondary,
        custom_id="contra_cancel_match",
        emoji="🚫",
    )
    async def cancel_match(self, interaction: discord.Interaction, button: Button):
        is_adm = interaction.user.guild_permissions.administrator
        if not is_adm:
            await interaction.response.send_message(
                "❌ Apenas **ADM** pode cancelar uma partida em andamento.",
                ephemeral=True,
            )
            return

        from services.match_service import match_service
        from services.influencer_live_queue_service import influencer_live_queue_service
        from config.discord_bot import get_bot

        await match_service.cancel_match(
            match_id=self.match_id,
            reason=f"Cancelado por ADM {interaction.user.name}",
        )
        await influencer_live_queue_service.advance_queue(
            influencer_id=str(self.influencer_id),
            guild_id=str(self.guild_id),
            bot=get_bot(),
        )

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(
            f"🚫 Partida **{self.match_id}** cancelada por {interaction.user.mention}.\n"
            "Chamando próximo da fila..."
        )
        logger.info(
            f"[ContraMatch] Cancelada por ADM {interaction.user.name} — match {self.match_id}"
        )
