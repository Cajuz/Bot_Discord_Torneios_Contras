# src/bot/cogs/queue_commands.py
from src.database.repositories.user_repository import UserRepository
from src.database.repositories.match_repository import MatchRepository
from src.database.models import MatchType

@bot.tree.command(name="stats", description="Ver suas estatísticas")
async def stats(interaction: discord.Interaction):
    user = await UserRepository.find_by_discord_id(interaction.user.id)
    
    if not user:
        # Cria usuário se não existir
        user = await UserRepository.create_or_update(
            interaction.user.id,
            interaction.user.name
        )
    
    await interaction.response.send_message(
        f"📊 **Estatísticas de {interaction.user.mention}**\n\n"
        f"🎮 Partidas: {user['total_matches']}\n"
        f"✅ Vitórias: {user['wins']}\n"
        f"❌ Derrotas: {user['losses']}\n"
        f"💰 Ganhos: R$ {user['total_earned']:.2f}\n"
        f"💸 Gastos: R$ {user['total_spent']:.2f}",
        ephemeral=True
    )
