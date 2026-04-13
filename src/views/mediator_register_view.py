"""
mediator_register_view.py

Painel de cadastro de mediador (processo externo).
O usuário preenche dados pessoais e envia comprovante de pagamento.
Apenas ADM aprova. Não existe “virar mediador pelo bot” — esse fluxo
é divulgado externamente e o formulário só faz o cadastro no sistema.
"""
from __future__ import annotations
import discord
from utils.datetime_utils import utcnow
from utils.logger import logger
from services.channel_service import (
    APROVAR_MEDIADORES_CHANNEL,
    ADM_ROLE_NAME,
)

THEME_COLOR  = 0xFFD54F   # amarelo  — padrão mediadores
SUCCESS_COLOR = 0x2ECC71   # verde
DANGER_COLOR  = 0xE74C3C   # vermelho


# ── Embed do painel público ───────────────────────────────────────

def build_mediator_register_embed() -> discord.Embed:
    embed = discord.Embed(
        title="⚡ Cadastro de Mediador",
        description=(
            "Seja bem-vindo ao processo de cadastro de mediadores do **X1 Frifas**!\n\n"
            "Para se tornar um mediador, você deve ter passado pelo processo externo "
            "de seleção divulgado no servidor.\n\n"
            "**O que você vai informar no formulário:**\n"
            "• Nome completo\n"
            "• CPF\n"
            "• Chave Pix\n"
            "• Telefone (WhatsApp)\n"
            "• Link do comprovante de pagamento da taxa de inscrição"
        ),
        color=THEME_COLOR,
    )
    embed.add_field(
        name="⚠️ Importante",
        value=(
            "• Seus dados serão usados exclusivamente para gestão interna.\n"
            "• O cadastro será analisado pela equipe ADM.\n"
            "• Comprovante falso resulta em ban permanente."
        ),
        inline=False,
    )
    embed.set_footer(text="X1 Frifas — Equipe de Mediadores")
    return embed


# ── View pública ────────────────────────────────────────────────

class MediatorRegisterView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Enviar Cadastro",
        style=discord.ButtonStyle.success,
        emoji="📝",
        custom_id="btn_mediator_register",
    )
    async def btn_cadastrar(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # Verifica se já tem cadastro pendente
        from config.database import db
        existing = await db.get_collection("mediator_applications").find_one({
            "discord_id": str(interaction.user.id),
            "status":     {"$in": ["pendente", "aprovado"]},
        })
        if existing:
            status = existing["status"]
            await interaction.response.send_message(
                f"Você já possui um cadastro com status **{status}**.\n"
                "Aguarde a análise da equipe.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(_MediatorRegisterModal())


# ── Modal com dados pessoais + comprovante ────────────────────────

class _MediatorRegisterModal(discord.ui.Modal, title="Cadastro de Mediador"):
    nome = discord.ui.TextInput(
        label="Nome completo",
        placeholder="Ex: João da Silva",
        min_length=5, max_length=100,
    )
    cpf = discord.ui.TextInput(
        label="CPF",
        placeholder="Somente números: 12345678901",
        min_length=11, max_length=14,
    )
    pix = discord.ui.TextInput(
        label="Chave Pix",
        placeholder="CPF, e-mail, telefone ou chave aleatória",
        min_length=5, max_length=150,
    )
    telefone = discord.ui.TextInput(
        label="Telefone (WhatsApp)",
        placeholder="Ex: 11999999999",
        min_length=10, max_length=15,
    )
    comprovante = discord.ui.TextInput(
        label="Link do comprovante de pagamento",
        placeholder="https://... (drive, imgur, etc.)",
        min_length=10, max_length=300,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from config.database import db

        doc = {
            "discord_id":    str(interaction.user.id),
            "discord_name":  interaction.user.name,
            "nome":          self.nome.value.strip(),
            "cpf":           self.cpf.value.strip(),
            "pix":           self.pix.value.strip(),
            "telefone":      self.telefone.value.strip(),
            "comprovante":   self.comprovante.value.strip(),
            "status":        "pendente",
            "submitted_at":  utcnow(),
            "reviewed_by":   None,
            "reviewed_at":   None,
        }

        await db.get_collection("mediator_applications").insert_one(doc)

        # Notifica canal de aprovação
        guild    = interaction.guild
        aprova_ch = discord.utils.get(guild.text_channels, name=APROVAR_MEDIADORES_CHANNEL)
        if aprova_ch:
            embed = discord.Embed(
                title="📎 Novo Cadastro de Mediador",
                color=THEME_COLOR,
            )
            embed.add_field(name="Discord",     value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
            embed.add_field(name="Nome",         value=self.nome.value,         inline=True)
            embed.add_field(name="CPF",          value=f"||{self.cpf.value}||", inline=True)
            embed.add_field(name="Pix",          value=self.pix.value,          inline=True)
            embed.add_field(name="Telefone",     value=self.telefone.value,     inline=True)
            embed.add_field(name="Comprovante",  value=f"[Ver comprovante]({self.comprovante.value})", inline=False)
            embed.set_footer(text=f"🕐 Enviado em {utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
            await aprova_ch.send(
                embed=embed,
                view=_MediatorApprovalView(applicant_id=str(interaction.user.id)),
            )

        await interaction.followup.send(
            embed=discord.Embed(
                title="✅ Cadastro enviado!",
                description=(
                    "Seus dados foram enviados para análise da equipe.\n"
                    "Você será notificado por **DM** com o resultado."
                ),
                color=SUCCESS_COLOR,
            ),
            ephemeral=True,
        )


# ── View de aprovação (ADM) ───────────────────────────────────

class _MediatorApprovalView(discord.ui.View):

    def __init__(self, applicant_id: str = ""):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id

    def _get_applicant_id(self, interaction: discord.Interaction) -> str:
        if self.applicant_id:
            return self.applicant_id
        # Tenta parsear do embed
        try:
            embed = interaction.message.embeds[0]
            for field in embed.fields:
                if field.name == "Discord":
                    # valor: "<@12345> (`12345`)"
                    val = field.value or ""
                    if "(`" in val:
                        return val.split("(`")[1].split("`)")[0]
        except Exception:
            pass
        return ""

    @discord.ui.button(
        label="Aprovar",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="btn_approve_mediator",
    )
    async def btn_aprovar(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        adm_role = discord.utils.get(interaction.guild.roles, name=ADM_ROLE_NAME)
        if not adm_role or adm_role not in interaction.user.roles:
            await interaction.response.send_message("Apenas **ADM** pode aprovar.", ephemeral=True)
            return

        applicant_id = self._get_applicant_id(interaction)
        if not applicant_id:
            await interaction.response.send_message("Não foi possível identificar o candidato.", ephemeral=True)
            return

        await interaction.response.defer()
        from config.database import db
        from services.channel_service import CONTROLLER_ROLE_NAME

        await db.get_collection("mediator_applications").update_one(
            {"discord_id": applicant_id, "status": "pendente"},
            {"$set": {
                "status":      "aprovado",
                "reviewed_by": str(interaction.user.id),
                "reviewed_at": utcnow(),
            }},
        )

        # Atribui cargo Controller
        try:
            member       = await interaction.guild.fetch_member(int(applicant_id))
            controller_r = discord.utils.get(interaction.guild.roles, name=CONTROLLER_ROLE_NAME)
            if member and controller_r:
                await member.add_roles(controller_r, reason="Cadastro de mediador aprovado")
                try:
                    await member.send(
                        embed=discord.Embed(
                            title="✅ Cadastro Aprovado!",
                            description=(
                                "Seu cadastro como **Mediador** foi aprovado!\n"
                                "Você recebeu o cargo **Controller** e já pode entrar na fila de mediação."
                            ),
                            color=SUCCESS_COLOR,
                        )
                    )
                except discord.Forbidden:
                    pass
        except Exception as e:
            logger.error(f"[MediatorRegister] Erro ao atribuir cargo: {e}")

        # Atualiza embed
        embed = interaction.message.embeds[0]
        embed.color = SUCCESS_COLOR
        embed.set_footer(text=f"✅ Aprovado por {interaction.user.name} — {utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
        await interaction.message.edit(embed=embed, view=discord.ui.View())
        await interaction.followup.send(
            f"✅ Candidato <@{applicant_id}> aprovado e cargo atribuído.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Reprovar",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="btn_reject_mediator",
    )
    async def btn_reprovar(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        adm_role = discord.utils.get(interaction.guild.roles, name=ADM_ROLE_NAME)
        if not adm_role or adm_role not in interaction.user.roles:
            await interaction.response.send_message("Apenas **ADM** pode reprovar.", ephemeral=True)
            return
        applicant_id = self._get_applicant_id(interaction)
        await interaction.response.send_modal(
            _MediatorRejectModal(applicant_id=applicant_id))


class _MediatorRejectModal(discord.ui.Modal, title="Reprovar Cadastro"):
    motivo = discord.ui.TextInput(
        label="Motivo da reprovação",
        style=discord.TextStyle.paragraph,
        placeholder="Informe o motivo...",
        min_length=5, max_length=300,
    )

    def __init__(self, applicant_id: str):
        super().__init__()
        self.applicant_id = applicant_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        from config.database import db

        await db.get_collection("mediator_applications").update_one(
            {"discord_id": self.applicant_id, "status": "pendente"},
            {"$set": {
                "status":      "reprovado",
                "reviewed_by": str(interaction.user.id),
                "reviewed_at": utcnow(),
                "reject_reason": self.motivo.value,
            }},
        )
        try:
            member = await interaction.guild.fetch_member(int(self.applicant_id))
            await member.send(
                embed=discord.Embed(
                    title="❌ Cadastro Reprovado",
                    description=(
                        f"Seu cadastro como Mediador foi **reprovado**.\n"
                        f"**Motivo:** {self.motivo.value}\n\n"
                        "Em caso de dúvidas, entre em contato com a equipe."
                    ),
                    color=DANGER_COLOR,
                )
            )
        except Exception:
            pass

        embed = interaction.message.embeds[0]
        embed.color = DANGER_COLOR
        embed.add_field(name="Motivo da reprovação", value=self.motivo.value, inline=False)
        embed.set_footer(text=f"❌ Reprovado por {interaction.user.name} — {utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
        await interaction.message.edit(embed=embed, view=discord.ui.View())
        await interaction.followup.send(
            f"❌ Cadastro de <@{self.applicant_id}> reprovado.",
            ephemeral=True,
        )
