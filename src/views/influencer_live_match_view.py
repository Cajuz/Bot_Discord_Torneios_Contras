"""
influencer_live_match_view.py
View da thread de partida no modo contra.

ARQUITETURA DE PERSISTENT VIEW COM custom_id DINÂMICO:
  - ContraConfirmView e ContraResultView usam custom_id dinâmico (com match_id).
  - bot.add_view() NÃO funciona para custom_ids dinâmicos.
  - A reconstrução das views após restart é feita via on_interaction no main.py,
    que extrai o match_id do custom_id e reconstrói a view consultando o banco.
  - As views NÃO são mais registradas como persistent no boot.
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

    def __init__(
        self,
        match_id: str,
        player_id: int,
        influencer_id: int,
        challenger_id: int,
        guild_id: int,
        mediator_id: int | None,
        channel: discord.TextChannel,
    ):
        super().__init__()
        self.match_id      = match_id
        self.player_id     = player_id
        self.influencer_id = influencer_id
        self.challenger_id = challenger_id
        self.guild_id      = guild_id
        self.mediator_id   = mediator_id
        self.channel       = channel  # guardado para não depender de interaction.guild

    async def on_submit(self, interaction: discord.Interaction):
        from services.match_service import match_service
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

        # FIX BUG 5: usa self.channel.guild em vez de interaction.guild
        # (mais robusto — interaction.guild pode ser None em edge cases)
        guild = self.channel.guild
        try:
            influencer = guild.get_member(self.influencer_id) or await guild.fetch_member(self.influencer_id)
            challenger = guild.get_member(self.challenger_id) or await guild.fetch_member(self.challenger_id)
            mediator_mention = f"<@{self.mediator_id}>" if self.mediator_id else "⚠️ *Nenhum Controller Live disponível*"

            embed_result = discord.Embed(
                title="🏆 Painel de Resultado — Controller Live",
                description=(
                    f"**Partida:** `{self.match_id}`\n"
                    f"**Influencer:** {influencer.mention if influencer else f'<@{self.influencer_id}>'}\n"
                    f"**Desafiante:** {challenger.mention if challenger else f'<@{self.challenger_id}>'}\n\n"
                    f"✅ Pagamento confirmado. Declare o vencedor quando a partida terminar.\n"
                    f"Controller Live: {mediator_mention}"
                ),
                color=THEME_LIVE,
            )
            result_view = ContraResultView(
                match_id=self.match_id,
                influencer_id=self.influencer_id,
                challenger_id=self.challenger_id,
                guild_id=self.guild_id,
            )
            await self.channel.send(embed=embed_result, view=result_view)
            logger.info(f"[ContraMatch] ContraResultView postada pós-pagamento — match {self.match_id}")
        except Exception as e:
            logger.error(f"[ContraMatch] Erro ao postar ContraResultView: {e}", exc_info=True)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW DE CONFIRMAÇÃO — desafiante confirma presença e pagamento
# ══════════════════════════════════════════════════════════════════════════════

class ContraConfirmView(View):
    """
    Postada no canal logo após o desafiante ser chamado da fila.

    custom_id dinâmico: contra_confirm_{match_id} / contra_giveup_{match_id}
    NÃO é registrada via bot.add_view — é reconstruída pelo on_interaction
    do main.py quando necessário (pós-restart).
    """

    def __init__(
        self,
        match_id: str,
        challenger_id: int,
        influencer_id: int,
        mediator_id: int | None = None,
        channel: discord.TextChannel | None = None,
        guild_id: int = 0,
    ):
        super().__init__(timeout=None)
        self.match_id      = match_id
        self.challenger_id = challenger_id
        self.influencer_id = influencer_id
        self.mediator_id   = mediator_id
        self.channel       = channel
        self.guild_id      = guild_id

        btn_confirm = Button(
            label="✅ Confirmar Presença & Pagamento",
            style=discord.ButtonStyle.success,
            custom_id=f"contra_confirm_{match_id}",
        )
        btn_confirm.callback = self._confirm_presence

        btn_giveup = Button(
            label="❌ Desistir",
            style=discord.ButtonStyle.secondary,
            custom_id=f"contra_giveup_{match_id}",
        )
        btn_giveup.callback = self._give_up

        self.add_item(btn_confirm)
        self.add_item(btn_giveup)

    async def _confirm_presence(self, interaction: discord.Interaction):
        # FIX BUG 6: challenger_id extraído do custom_id como fallback confiável
        # ao invés de regex frágil no embed
        challenger_id = self.challenger_id

        if challenger_id and interaction.user.id != challenger_id:
            await interaction.response.send_message(
                "❌ Apenas o desafiante desta partida pode confirmar aqui.",
                ephemeral=True,
            )
            return

        channel = self.channel or interaction.channel
        if not isinstance(channel, discord.TextChannel):
            channel = interaction.channel

        modal = ContraPaymentModal(
            match_id=self.match_id,
            player_id=interaction.user.id,
            influencer_id=self.influencer_id,
            challenger_id=self.challenger_id or interaction.user.id,
            guild_id=self.guild_id or (interaction.guild_id or 0),
            mediator_id=self.mediator_id,
            channel=channel,
        )
        await interaction.response.send_modal(modal)

    async def _give_up(self, interaction: discord.Interaction):
        challenger_id = self.challenger_id
        if challenger_id and interaction.user.id != challenger_id:
            await interaction.response.send_message(
                "❌ Apenas o desafiante pode desistir.", ephemeral=True)
            return

        from services.influencer_live_queue_service import influencer_live_queue_service
        from services.match_service import match_service
        from config.discord_bot import get_bot

        await match_service.cancel_match(
            match_id=self.match_id,
            reason=f"Desistência do desafiante <@{interaction.user.id}>",
        )
        await influencer_live_queue_service.advance_queue(
            influencer_id=str(self.influencer_id or 0),
            guild_id=str(self.guild_id or interaction.guild_id or 0),
            bot=get_bot(),
        )
        await interaction.response.send_message(
            "✅ Você desistiu. O próximo da fila será chamado.", ephemeral=True)
        await interaction.channel.send(
            f"⚠️ {interaction.user.mention} desistiu. Chamando próximo da fila...")
        logger.info(f"[ContraMatch] Desistência — match {self.match_id}")


# ══════════════════════════════════════════════════════════════════════════════
# VIEW DE RESULTADO — Controller Live declara vencedor
# ══════════════════════════════════════════════════════════════════════════════

class ContraResultView(View):
    """
    Postada após pagamento confirmado (via ContraPaymentModal.on_submit).

    custom_id dinâmico: contra_inf_wins_{match_id} etc.
    NÃO é registrada via bot.add_view — é reconstruída pelo on_interaction
    do main.py quando necessário (pós-restart).
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

        btn_inf = Button(
            label="🎥 Influencer Venceu",
            style=discord.ButtonStyle.primary,
            custom_id=f"contra_inf_wins_{match_id}",
            emoji="🏆",
        )
        btn_inf.callback = self._influencer_wins

        btn_chal = Button(
            label="⚔️ Desafiante Venceu",
            style=discord.ButtonStyle.danger,
            custom_id=f"contra_chal_wins_{match_id}",
            emoji="🏆",
        )
        btn_chal.callback = self._challenger_wins

        btn_cancel = Button(
            label="⚠️ Cancelar Partida",
            style=discord.ButtonStyle.secondary,
            custom_id=f"contra_cancel_{match_id}",
            emoji="🚫",
        )
        btn_cancel.callback = self._cancel_match

        self.add_item(btn_inf)
        self.add_item(btn_chal)
        self.add_item(btn_cancel)

    async def _declare_winner(
        self,
        interaction: discord.Interaction,
        vencedor: str,
        winner_id: int,
        loser_id: int,
    ):
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
            winner=winner, loser=loser, prize=prize, match_id=self.match_id)

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(
            content=f"🏆 {winner.mention} venceu! {loser.mention} foi derrotado.",
            embed=embed,
        )
        await influencer_live_queue_service.advance_queue(
            influencer_id=str(self.influencer_id),
            guild_id=str(self.guild_id),
            bot=get_bot(),
        )
        logger.info(
            f"[ContraMatch] Resultado — match {self.match_id} "
            f"vencedor {winner_id} por {interaction.user.name}"
        )

    async def _influencer_wins(self, interaction: discord.Interaction):
        await self._declare_winner(interaction, "influencer", self.influencer_id, self.challenger_id)

    async def _challenger_wins(self, interaction: discord.Interaction):
        await self._declare_winner(interaction, "challenger", self.challenger_id, self.influencer_id)

    async def _cancel_match(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
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
        logger.info(f"[ContraMatch] Cancelada por ADM {interaction.user.name} — match {self.match_id}")
