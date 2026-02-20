import discord
import matplotlib.pyplot as plt
import io 

from services.mediador_dashbord_service import mediator_dashboard_service
from utils.logger import logger




class MediatorDashboardView(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot


    @discord.ui.button(label="Atualizar", style=discord.ButtonStyle.primary)
    async def atualizar(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
        # Removido o 'self.bot'
            embed, file = await mediator_dashboard_service.create_embed()

            if embed:
            # Importante: ao editar com anexo, usamos 'attachments'
                await interaction.response.edit_message(
                embed=embed,
                attachments=[file],
                view=self
            )
            else:
                await interaction.response.send_message("Erro ao gerar gráfico.", ephemeral=True)

        except Exception as e:
            logger.error(f"Erro ao atualizar dashboard: {e}")
        # O response só pode ser usado uma vez. Se o edit falhar, usamos followup
            await interaction.followup.send(f"❌ Erro: {e}", ephemeral=True)