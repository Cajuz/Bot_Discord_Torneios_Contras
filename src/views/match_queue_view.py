import discord
from typing import Optional
from services.match_queue_service import match_queue_service
from config.channels_config import ChannelsConfig
from utils.logger import logger


def is_1x1_mob(channel_name: str) -> bool:
    return channel_name == "1x1-mob"


class MatchQueueView(discord.ui.View):
    """
    Card de fila.
    - 1x1-mob: botões GEL NORMAL + GEL INFINITO + SAIR
    - Demais canais: botão ENTRAR NA FILA + SAIR
    """

    def __init__(self, channel_name: str, bet_value: float, max_players: int = 2):
        super().__init__(timeout=None)
        self.channel_name = channel_name
        self.bet_value    = bet_value
        self.max_players  = 2  # sempre 2 jogadores

        if is_1x1_mob(channel_name):
            btn_normal = discord.ui.Button(
                label="🔥 GEL NORMAL",
                style=discord.ButtonStyle.green,
                custom_id=f"gel_normal_{channel_name}_{bet_value}"
            )
            btn_normal.callback = self._join_normal

            btn_inf = discord.ui.Button(
                label="♾️ GEL INFINITO",
                style=discord.ButtonStyle.blurple,
                custom_id=f"gel_infinito_{channel_name}_{bet_value}"
            )
            btn_inf.callback = self._join_infinito

            btn_sair = discord.ui.Button(
                label="🚪 SAIR DA FILA",
                style=discord.ButtonStyle.red,
                custom_id=f"sair_fila_{channel_name}_{bet_value}"
            )
            btn_sair.callback = self._leave_queue

            self.add_item(btn_normal)
            self.add_item(btn_inf)
            self.add_item(btn_sair)

        else:
            btn_entrar = discord.ui.Button(
                label="⚔️ ENTRAR NA FILA",
                style=discord.ButtonStyle.green,
                custom_id=f"entrar_fila_{channel_name}_{bet_value}"
            )
            btn_entrar.callback = self._join_normal

            btn_sair = discord.ui.Button(
                label="🚪 SAIR DA FILA",
                style=discord.ButtonStyle.red,
                custom_id=f"sair_fila_{channel_name}_{bet_value}"
            )
            btn_sair.callback = self._leave_queue

            self.add_item(btn_entrar)
            self.add_item(btn_sair)

    async def _join_normal(self, interaction: discord.Interaction):
        await self._handle_join(interaction, "normal")

    async def _join_infinito(self, interaction: discord.Interaction):
        await self._handle_join(interaction, "infinito")

    async def _handle_join(self, interaction: discord.Interaction, gel_type: str):
        try:
            # Bloqueia entrar em dois géis ao mesmo tempo (só para 1x1-mob)
            if is_1x1_mob(self.channel_name):
                other_gel   = "infinito" if gel_type == "normal" else "normal"
                other_queue = await match_queue_service.get_queue_status(
                    self.channel_name, self.bet_value, other_gel
                )
                if other_queue and interaction.user.id in other_queue.players:
                    await interaction.response.send_message(
                        f"⚠️ Você já está na fila de **GEL {other_gel.upper()}**. Saia dela primeiro.",
                        ephemeral=True
                    )
                    return

            success, queue, message = await match_queue_service.add_player_to_queue(
                channel_name=self.channel_name,
                bet_value=self.bet_value,
                gel_type=gel_type,
                max_players=2,
                player_id=interaction.user.id
            )

            if not success:
                await interaction.response.send_message(f"❌ {message}", ephemeral=True)
                return

            if message == "full":
                await interaction.response.send_message(
                    "⚡ Fila completa! Um tópico de confirmação foi criado.",
                    ephemeral=True
                )
                await match_queue_service.start_confirmation_timer(
                    queue=queue,
                    bot=interaction.client,
                    channel=interaction.channel
                )
            else:
                await interaction.response.send_message(f"✅ {message}", ephemeral=True)

            await self._refresh_card(interaction, gel_type)

        except Exception as e:
            logger.error(f"Erro ao entrar na fila: {e}")
            await interaction.response.send_message("❌ Erro ao entrar na fila.", ephemeral=True)

    async def _leave_queue(self, interaction: discord.Interaction):
        try:
            gel_types = ["normal", "infinito"] if is_1x1_mob(self.channel_name) else ["normal"]
            removed = False

            for gel in gel_types:
                ok, queue = await match_queue_service.remove_player_from_queue(
                    self.channel_name, self.bet_value, gel, interaction.user.id
                )
                if ok:
                    removed = True

            if removed:
                await interaction.response.send_message("✅ Você saiu da fila!", ephemeral=True)
                await self._refresh_card(interaction, "normal")
            else:
                await interaction.response.send_message(
                    "❌ Você não está em nenhuma fila deste valor.", ephemeral=True
                )
        except Exception as e:
            logger.error(f"Erro ao sair da fila: {e}")
            await interaction.response.send_message("❌ Erro ao sair da fila.", ephemeral=True)

    async def _refresh_card(self, interaction: discord.Interaction, gel_type: str):
        """Atualiza o embed do card com contagens atuais"""
        try:
            q_normal   = await match_queue_service.get_queue_status(self.channel_name, self.bet_value, "normal")
            q_infinito = await match_queue_service.get_queue_status(self.channel_name, self.bet_value, "infinito")

            normal_count   = len(q_normal.players)   if q_normal   else 0
            infinito_count = len(q_infinito.players) if q_infinito else 0

            embed = create_match_queue_embed(
                channel_name=self.channel_name,
                bet_value=self.bet_value,
                queue_normal_count=normal_count,
                queue_infinito_count=infinito_count
            )
            try:
                await interaction.message.edit(embed=embed, view=self)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Erro ao atualizar card: {e}")


def create_match_queue_embed(
    channel_name: str,
    bet_value: float,
    queue_normal_count: int = 0,
    queue_infinito_count: int = 0
) -> discord.Embed:

    display = channel_name.upper() \
        .replace("-MOB",    " Mobile") \
        .replace("-EMU",    " Emulador") \
        .replace("-MISTO",  " Misto")

    def bar(n: int) -> str:
        return "🟩" * n + "⬜" * (2 - n)  # barra de 2 slots (sempre 2 jogadores)

    embed = discord.Embed(
        title=f"💰 R$ {bet_value:.2f}",
        description=f"**Modo:** {display}",
        color=discord.Color.gold()
    )

    if is_1x1_mob(channel_name):
        embed.add_field(
            name="🔥 GEL NORMAL",
            value=f"Na fila: **{queue_normal_count}/2**\n{bar(queue_normal_count)}",
            inline=True
        )
        embed.add_field(
            name="♾️ GEL INFINITO",
            value=f"Na fila: **{queue_infinito_count}/2**\n{bar(queue_infinito_count)}",
            inline=True
        )
    else:
        embed.add_field(
            name="⚔️ FILA",
            value=f"Na fila: **{queue_normal_count}/2**\n{bar(queue_normal_count)}",
            inline=True
        )

    embed.set_footer(text="Clique para entrar na fila")
    return embed
