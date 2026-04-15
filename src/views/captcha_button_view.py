"""
CaptchaButtonView — CAPTCHA simples via botões no servidor.
O usuário clica no botão correto dentre 4 opções (1 certa + 3 erradas).
Rápido, acessível, sem necessidade de DM ou digitação.
"""
import asyncio
import random
import discord


CAPTCHA_QUESTIONS = [
    {"pergunta": "Qual é a cor do céu?",          "correta": "Azul",      "erradas": ["Verde", "Vermelho", "Amarelo"]},
    {"pergunta": "Quantos lados tem um triângulo?", "correta": "3",        "erradas": ["4", "5", "6"]},
    {"pergunta": "Qual animal late?",               "correta": "Cachorro", "erradas": ["Gato", "Pato", "Peixe"]},
    {"pergunta": "Qual é a capital do Brasil?",     "correta": "Brasília", "erradas": ["São Paulo", "Rio de Janeiro", "Salvador"]},
    {"pergunta": "Quantos dias tem uma semana?",    "correta": "7",        "erradas": ["5", "6", "8"]},
    {"pergunta": "O fogo é quente ou frio?",        "correta": "Quente",   "erradas": ["Frio", "Morno", "Gelado"]},
    {"pergunta": "Qual o resultado de 2 + 2?",      "correta": "4",        "erradas": ["3", "5", "22"]},
    {"pergunta": "O Sol é uma estrela?",            "correta": "Sim",      "erradas": ["Não", "Às vezes", "Talvez"]},
    {"pergunta": "Quantas patas tem um cachorro?",  "correta": "4",        "erradas": ["2", "6", "8"]},
    {"pergunta": "Qual fruta é amarela e tem casca?","correta": "Banana",   "erradas": ["Maçã", "Uva", "Morango"]},
]


class CaptchaButtonView(discord.ui.View):

    def __init__(self, member: discord.Member, attempt: int):
        super().__init__(timeout=60.0)
        self.member  = member
        self.attempt = attempt
        self._result_future: asyncio.Future = asyncio.get_event_loop().create_future()

        question_data = random.choice(CAPTCHA_QUESTIONS)
        self.question = question_data["pergunta"]
        self.correct  = question_data["correta"]

        options = [question_data["correta"]] + random.sample(question_data["erradas"], 3)
        random.shuffle(options)

        for option in options:
            is_correct = (option == self.correct)
            btn = discord.ui.Button(
                label=option,
                style=discord.ButtonStyle.primary,
                custom_id=f"captcha_{member.id}_{attempt}_{option[:8]}"
            )
            btn.callback = self._make_callback(is_correct)
            self.add_item(btn)

    def _make_callback(self, is_correct: bool):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.member.id:
                await interaction.response.send_message(
                    "Este captcha não é para você.", ephemeral=True
                )
                return
            await interaction.response.defer()
            self.stop()
            if not self._result_future.done():
                self._result_future.set_result(is_correct)
        return callback

    async def wait_result(self, timeout: float = 60.0) -> bool:
        """Aguarda o resultado do captcha. Lança asyncio.TimeoutError se expirar."""
        return await asyncio.wait_for(
            asyncio.shield(self._result_future),
            timeout=timeout
        )
