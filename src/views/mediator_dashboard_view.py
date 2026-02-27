import discord
import matplotlib.pyplot as plt
import io 
from utils.logger import logger

class MediatorDashboardView(discord.ui.View):
    def __init__(self, service, titulo, dias):
        super().__init__(timeout=None)
        self.service = service
        self.titulo = titulo
        self.dias = dias

    @discord.ui.button(label="🔄 Atualizar Agora", style=discord.ButtonStyle.primary)
    async def atualizar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Indica que o bot está processando (evita erro de 3 segundos do Discord)
        await interaction.response.defer(ephemeral=True) 
        
        try:
            embed, file = await self.service.create_embed(self.titulo, self.dias)
            if embed:
                # Como usamos defer(), agora usamos edit_original_response
                await interaction.edit_original_response(
                    content="✅ Dashboard atualizado!",
                    embed=embed,
                    attachments=[file],
                    view=self
                )
            else:
                await interaction.followup.send("❌ Erro ao gerar gráfico.", ephemeral=True)

        except Exception as e:
            logger.error(f"Erro ao atualizar dashboard: {e}")
            await interaction.followup.send(f"❌ Erro crítico: {e}", ephemeral=True)

