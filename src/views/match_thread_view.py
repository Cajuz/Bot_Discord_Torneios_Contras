from __future__ import annotations
import discord
from datetime import datetime
from typing import Optional, List
from config.database import db
from utils.logger import logger


async def _get_match(match_id: str) -> Optional[dict]:
    from bson import ObjectId
    try:
        return await db.get_collection("matches").find_one({"_id": ObjectId(match_id)})
    except Exception as e:
        logger.error(f"Erro ao buscar match {match_id}: {e}")
        return None


async def _update_thread_name(thread: discord.Thread, base_name: str, status: str):
    try:
        await thread.edit(name=f"{base_name}: {status}")
    except Exception as e:
        logger.error(f"Erro ao renomear thread: {e}")


class MediatorMatchControlView(discord.ui.View):

    def __init__(self, match_id: str, mediator_id: int):
        super().__init__(timeout=None)
        self.match_id    = match_id
        self.mediator_id = mediator_id
        self._base_name: Optional[str] = None

    async def _check_mediator(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.mediator_id:
            await interaction.response.send_message(
                "❌ Apenas o mediador desta partida pode usar este botão.",
                ephemeral=True
            )
            return False
        return True

    def _set_base_name(self, thread_name: str):
        if ": " in thread_name:
            self._base_name = thread_name.rsplit(": ", 1)[0]
        else:
            self._base_name = thread_name

    @discord.ui.button(
        label="✅ Confirmar Pagamento",
        style=discord.ButtonStyle.green,
        custom_id="mediator_confirm_payment"
    )
    async def confirm_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_mediator(interaction):
            return

        match = await _get_match(self.match_id)
        if not match:
            await interaction.response.send_message("❌ Partida não encontrada.", ephemeral=True)
            return

        if match.get("pagamento_confirmado"):
            await interaction.response.send_message("✅ Pagamento já confirmado.", ephemeral=True)
            return

        from bson import ObjectId
        await db.get_collection("matches").update_one(
            {"_id": ObjectId(self.match_id)},
            {"$set": {"pagamento_confirmado": True, "updated_at": datetime.utcnow()}}
        )

        button.disabled = True
        button.label    = "✅ Pagamento Confirmado"
        for child in self.children:
            if getattr(child, "custom_id", None) == "mediator_start_match":
                child.disabled = False

        await interaction.response.edit_message(view=self)

        if isinstance(interaction.channel, discord.Thread):
            self._set_base_name(interaction.channel.name)
            await _update_thread_name(interaction.channel, self._base_name, "Pagamento Confirmado")

        await interaction.followup.send("✅ Pagamento confirmado! Você pode iniciar a partida.", ephemeral=True)

    @discord.ui.button(
        label="▶️ Iniciar Partida",
        style=discord.ButtonStyle.primary,
        custom_id="mediator_start_match",
        disabled=True
    )
    async def start_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_mediator(interaction):
            return

        match = await _get_match(self.match_id)
        if not match:
            await interaction.response.send_message("❌ Partida não encontrada.", ephemeral=True)
            return

        if not match.get("pagamento_confirmado"):
            await interaction.response.send_message(
                "❌ Confirme o pagamento antes de iniciar a partida.", ephemeral=True
            )
            return

        if match.get("status") == "em_andamento":
            await interaction.response.send_message("⚠️ Partida já iniciada.", ephemeral=True)
            return

        from bson import ObjectId
        await db.get_collection("matches").update_one(
            {"_id": ObjectId(self.match_id)},
            {"$set": {"status": "em_andamento", "started_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
        )

        button.disabled = True
        button.label    = "▶️ Partida Iniciada"
        for child in self.children:
            if getattr(child, "custom_id", None) in ("mediator_end_match", "mediator_cancel_match"):
                child.disabled = False

        await interaction.response.edit_message(view=self)

        if isinstance(interaction.channel, discord.Thread):
            self._set_base_name(interaction.channel.name)
            await _update_thread_name(interaction.channel, self._base_name, "Em Andamento")

        await interaction.followup.send("▶️ Partida iniciada!", ephemeral=False)

    @discord.ui.button(
        label="🏁 Finalizar Partida",
        style=discord.ButtonStyle.secondary,
        custom_id="mediator_end_match",
        disabled=True
    )
    async def end_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"[DEBUG] end_match clicado por {interaction.user.id}")

        if not await self._check_mediator(interaction):
            return

        match = await _get_match(self.match_id)
        logger.info(f"[DEBUG] match encontrado: {match}")

        if not match:
            await interaction.response.send_message("❌ Partida não encontrada.", ephemeral=True)
            return

        view = WinnerSelectView(
            match_id=self.match_id,
            mediator_id=self.mediator_id,
            time_blue=match.get("time_blue", []),
            time_red=match.get("time_red", []),
            parent_view=self,
            parent_message=interaction.message
        )

        logger.info(f"[DEBUG] WinnerSelectView criada, enviando...")

        await interaction.response.send_message(
            "🏆 Selecione o time vencedor:",
            view=view,
            ephemeral=False
        )

        logger.info(f"[DEBUG] WinnerSelectView enviada com sucesso")

    @discord.ui.button(
        label="❌ Cancelar Match",
        style=discord.ButtonStyle.danger,
        custom_id="mediator_cancel_match",
        disabled=True
    )
    async def cancel_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_mediator(interaction):
            return

        from bson import ObjectId
        await db.get_collection("matches").update_one(
            {"_id": ObjectId(self.match_id)},
            {"$set": {"status": "cancelado", "updated_at": datetime.utcnow()}}
        )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(view=self)

        if isinstance(interaction.channel, discord.Thread):
            self._set_base_name(interaction.channel.name)
            await _update_thread_name(interaction.channel, self._base_name, "Cancelado")

        await interaction.followup.send("❌ Partida cancelada.", ephemeral=False)


class WinnerSelectView(discord.ui.View):

    def __init__(
        self,
        match_id: str,
        mediator_id: int,
        time_blue: List[int],
        time_red: List[int],
        parent_view: MediatorMatchControlView,
        parent_message: discord.Message
    ):
        super().__init__(timeout=None)
        self.match_id       = match_id
        self.mediator_id    = mediator_id
        self.time_blue      = time_blue
        self.time_red       = time_red
        self.parent_view    = parent_view
        self.parent_message = parent_message

        blue_btn = discord.ui.Button(
            label="🔵 Time Blue Venceu",
            style=discord.ButtonStyle.primary
        )
        blue_btn.callback = self._blue_callback
        self.add_item(blue_btn)

        red_btn = discord.ui.Button(
            label="🔴 Time Red Venceu",
            style=discord.ButtonStyle.danger
        )
        red_btn.callback = self._red_callback
        self.add_item(red_btn)

    async def _blue_callback(self, interaction: discord.Interaction):
        await self._set_winner(interaction, "blue", self.time_blue)

    async def _red_callback(self, interaction: discord.Interaction):
        await self._set_winner(interaction, "red", self.time_red)

    async def _set_winner(
        self,
        interaction: discord.Interaction,
        winner_team: str,
        winner_players: List[int]
    ):
        if interaction.user.id != self.mediator_id:
            await interaction.response.send_message(
                "❌ Apenas o mediador pode definir o vencedor.", ephemeral=True
            )
            return

        try:
            from bson import ObjectId
            await db.get_collection("matches").update_one(
                {"_id": ObjectId(self.match_id)},
                {
                    "$set": {
                        "status": "aguardando_premio",
                        "vencedor": winner_team,
                        "winner_players": winner_players,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            if self.parent_view:
                for child in self.parent_view.children:
                    child.disabled = True
                try:
                    await self.parent_message.edit(view=self.parent_view)
                except Exception as e:
                    logger.error(f"Erro ao editar mensagem pai: {e}")

            if isinstance(interaction.channel, discord.Thread):
                if self.parent_view:
                    self.parent_view._set_base_name(interaction.channel.name)
                    base = self.parent_view._base_name
                else:
                    name = interaction.channel.name
                    base = name.rsplit(": ", 1)[0] if ": " in name else name

                await _update_thread_name(
                    interaction.channel,
                    base,
                    f"Vencedor: Time {'Blue 🔵' if winner_team == 'blue' else 'Red 🔴'}"
                )

            label        = "🔵 Time Blue" if winner_team == "blue" else "🔴 Time Red"
            winners_text = "\n".join(f"• <@{uid}>" for uid in winner_players) or "—"

            embed = discord.Embed(
                title="🏆 Partida Finalizada!",
                description=f"**Vencedor:** {label}\n\n{winners_text}",
                color=discord.Color.gold()
            )
            embed.set_footer(text="Os vencedores devem confirmar o recebimento do prêmio.")

            prize_view = PrizeConfirmView(
                match_id=self.match_id,
                winner_players=winner_players,
                winner_team=winner_team
            )

            mentions = " ".join(f"<@{uid}>" for uid in winner_players)

            await interaction.response.edit_message(
                content=f"✅ Time {'Blue 🔵' if winner_team == 'blue' else 'Red 🔴'} definido como vencedor!",
                view=None
            )

            await interaction.channel.send(content=mentions, embed=embed, view=prize_view)

        except Exception as e:
            logger.error(f"Erro ao definir vencedor: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ Erro: {e}", ephemeral=True)
            except Exception:
                pass


class PrizeConfirmView(discord.ui.View):

    def __init__(self, match_id: str, winner_players: List[int], winner_team: str):
        super().__init__(timeout=None)
        self.match_id       = match_id
        self.winner_players = winner_players
        self.winner_team    = winner_team
        self.confirmed: set[int] = set()

    @discord.ui.button(
        label="🎁 Confirmar Recebimento do Prêmio",
        style=discord.ButtonStyle.success,
        custom_id="prize_confirm"
    )
    async def confirm_prize(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.winner_players:
            await interaction.response.send_message(
                "❌ Apenas os jogadores vencedores podem confirmar o prêmio.",
                ephemeral=True
            )
            return

        if interaction.user.id in self.confirmed:
            await interaction.response.send_message("✅ Você já confirmou!", ephemeral=True)
            return

        self.confirmed.add(interaction.user.id)

        if self.confirmed >= set(self.winner_players):
            from bson import ObjectId
            await db.get_collection("matches").update_one(
                {"_id": ObjectId(self.match_id)},
                {
                    "$set": {
                        "premio_confirmado_jogador": True,
                        "status": "finalizado",
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            button.disabled = True
            button.label    = "✅ Prêmio Confirmado"
            await interaction.response.edit_message(view=self)

            if isinstance(interaction.channel, discord.Thread):
                name = interaction.channel.name
                base = name.rsplit(": ", 1)[0] if ": " in name else name
                await _update_thread_name(interaction.channel, base, "Finalizado ✅")
                try:
                    await interaction.channel.edit(archived=True)
                except Exception:
                    pass

            await interaction.followup.send(
                "🎉 Todos os vencedores confirmaram o prêmio! Partida encerrada.",
                ephemeral=False
            )
        else:
            remaining = len(self.winner_players) - len(self.confirmed)
            await interaction.response.send_message(
                f"✅ Confirmado! Aguardando {remaining} confirmação(ões) restante(s).",
                ephemeral=True
            )
