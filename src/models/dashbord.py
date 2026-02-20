from discord.ext import commands # Adicionado o 'commands' aqui
from services.mediador_dashbord_service import mediator_dashboard_service

class Dashboard(commands.Cog): # Adicionado o 'commands.' antes de Cog

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="dashboard")
    async def dashboard(self, ctx):
        try:
            # Chamada correta sem o parâmetro 'bot'
            embed, file = await mediator_dashboard_service.create_embed()

            if embed and file:
                # O Discord precisa receber o embed e o file juntos
                await ctx.send(embed=embed, file=file)
            else:
                await ctx.send("❌ Erro ao obter dados do banco para o gráfico.")
        
        except Exception as e:
            await ctx.send(f"❌ Erro interno: {e}")

async def setup(bot):
    await bot.add_cog(Dashboard(bot))