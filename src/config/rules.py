import discord

class ServerRules:
    """Configuração das regras do servidor"""
    
    RULES_TITLE = "📜 Regras do Servidor"
    
    RULES_TEXT = """
**Bem-vindo(a) ao nosso servidor!**

Antes de prosseguir, leia atentamente nossas regras:

**1️⃣ Respeito Mútuo**
• Trate todos os membros com respeito
• Não toleramos discriminação, racismo ou assédio
• Mantenha um ambiente saudável e amigável

**2️⃣ Comunicação**
• Use os canais apropriados para cada tipo de conversa
• Evite spam, flood ou mensagens repetitivas
• Não use CAPS LOCK excessivamente

**3️⃣ Partidas e Mediação**
• Respeite as decisões dos mediadores
• Não abandone partidas sem aviso prévio
• Jogue de forma justa e honesta

**4️⃣ Conteúdo Proibido**
• Não compartilhe conteúdo NSFW
• Proibido links suspeitos ou maliciosos
• Não faça propaganda sem autorização

**5️⃣ Punições**
• Avisos → Mute temporário → Kick → Ban
• Infrações graves resultam em ban imediato
• Todos os casos são analisados pela staff

**6️⃣ Suporte**
• Use o canal de suporte para dúvidas
• Respeite o tempo de resposta da equipe
• Seja claro e objetivo ao pedir ajuda

**━━━━━━━━━━━━━━━━━━━━━━━━**

Ao aceitar as regras, você concorda em seguir todas as diretrizes acima.
Caso não aceite, infelizmente não poderemos mantê-lo no servidor.

**Você aceita nossas regras?**
"""

    CONFIRMATION_TITLE = "⚠️ Tem certeza?"
    CONFIRMATION_TEXT = """
**Você está prestes a recusar nossas regras.**

Caso não aceite as regras, não podemos alocar você em nosso servidor, logo **expulsaremos você automaticamente**.

**O que deseja fazer?**
"""

    WELCOME_TITLE = "✅ Bem-vindo(a)!"
    WELCOME_TEXT = """
**Parabéns! Você agora faz parte do nosso servidor!**

Aqui estão algumas informações úteis:

🎮 **Canais Disponíveis:**
• `#chat` - Conversa geral
• `#partidas` - Organize suas partidas
• `#fila` - Veja a fila de mediadores
• `#suporte` - Tire suas dúvidas
• `#avisos` - Acompanhe atualizações

📋 **Comandos Úteis:**
• `!help` - Ver todos os comandos
• `!x1 @usuario` - Desafiar alguém
• `!fila` - Ver fila de mediadores
• `!perfil` - Ver seu perfil

**Divirta-se e boa sorte em suas partidas!** 🎉
"""

    @staticmethod
    def get_rules_embed() -> discord.Embed:
        """Criar embed das regras"""
        embed = discord.Embed(
            title=ServerRules.RULES_TITLE,
            description=ServerRules.RULES_TEXT,
            color=discord.Color.blue()
        )
        embed.set_footer(text="Leia com atenção antes de aceitar")
        return embed
    
    @staticmethod
    def get_confirmation_embed() -> discord.Embed:
        """Criar embed de confirmação"""
        embed = discord.Embed(
            title=ServerRules.CONFIRMATION_TITLE,
            description=ServerRules.CONFIRMATION_TEXT,
            color=discord.Color.red()
        )
        embed.set_footer(text="Esta ação é irreversível")
        return embed
    
    @staticmethod
    def get_welcome_embed(member: discord.Member) -> discord.Embed:
        """Criar embed de boas-vindas"""
        embed = discord.Embed(
            title=ServerRules.WELCOME_TITLE,
            description=ServerRules.WELCOME_TEXT,
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")
        return embed
