"""
mediator_register_view.py

Card fixo postado em #cadastro-mediador.
Fluxo:
  1. Usuário clica em "Cadastrar" → modal com dados pessoais + link do comprovante
  2. Submissão gera embed resumo em #aprovar-mediadores (canal privado ADM)
  3. ADM clica Aprovar → cargo Controller atribuído + DM de boas-vindas
             ou Reprovar → DM de feedback
"""
from __future__ import annotations

import discord
from utils.datetime_utils import utcnow
from utils.logger import logger

THEME_COLOR  = 0xFFD54F   # dourado padrão X1 Frifas
APROVAR_CHANNEL = "aprovar-mediadores"
CONTROLLER_ROLE = "Controller"


# ═══════════════════════════════════════════════════════════════
# View persistente — card fixo
# ═══════════════════════════════════════════════════════════════

class MediatorRegisterView(discord.ui.View):
    """Postado em #cadastro-mediador. Persiste entre reinicializações."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📋 Cadastrar como Mediador",
        style=discord.ButtonStyle.primary,
        custom_id="mediator_register:open_form",
    )
    async def open_form(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(_MediatorRegisterModal())


# ═══════════════════════════════════════════════════════════════
# Modal — dados pessoais
# ═══════════════════════════════════════════════════════════════

class _MediatorRegisterModal(discord.ui.Modal, title="Cadastro de Mediador — X1 Frifas"):

    nome_completo = discord.ui.TextInput(
        label="Nome completo",
        placeholder="Ex: João da Silva",
        min_length=3,
        max_length=100,
    )
    cpf = discord.ui.TextInput(
        label="CPF (somente números)",
        placeholder="Ex: 12345678900",
        min_length=11,
        max_length=14,
    )
    telefone = discord.ui.TextInput(
        label="Telefone / WhatsApp",
        placeholder="Ex: 11999998888",
        min_length=10,
        max_length=15,
    )
    chave_pix = discord.ui.TextInput(
        label="Chave PIX",
        placeholder="CPF, e-mail, telefone ou chave aleatória",
        min_length=5,
        max_length=100,
    )
    comprovante_url = discord.ui.TextInput(
        label="Link do comprovante de pagamento",
        placeholder="Cole aqui o link do comprovante (Google Drive, Imgur, etc.)",
        min_length=5,
        max_length=300,
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild  = interaction.guild
        author = interaction.user

        # Salva no banco
        try:
            from config.database import db
            await db.get_collection("mediator_applications").update_one(
                {"user_id": str(author.id)},
                {
                    "$set": {
                        "user_id":        str(author.id),
                        "username":       str(author),
                        "nome_completo":  self.nome_completo.value.strip(),
                        "cpf":            self.cpf.value.strip(),
                        "telefone":       self.telefone.value.strip(),
                        "chave_pix":      self.chave_pix.value.strip(),
                        "comprovante":    self.comprovante_url.value.strip(),
                        "status":         "pendente",
                        "submitted_at":   utcnow(),
                    }
                },
                upsert=True,
            )
        except Exception as e:
            logger.error(f"[MediatorRegister] DB error: {e}")

        # Embed para revisão do ADM
        review_embed = discord.Embed(
            title="🆕  Nova Candidatura — Mediador",
            description=f"<@{author.id}> enviou sua candidatura para mediador.",
            color=THEME_COLOR,
            timestamp=utcnow(),
        )
        review_embed.add_field(name="Discord",         value=str(author),                    inline=True)
        review_embed.add_field(name="ID",              value=str(author.id),                 inline=True)
        review_embed.add_field(name="Nome completo",   value=self.nome_completo.value.strip(), inline=False)
        review_embed.add_field(name="CPF",             value=f"||{self.cpf.value.strip()}||", inline=True)
        review_embed.add_field(name="Telefone",        value=self.telefone.value.strip(),      inline=True)
        review_embed.add_field(name="Chave PIX",       value=self.chave_pix.value.strip(),     inline=False)
        review_embed.add_field(
            name="Comprovante",
            value=f"[Ver comprovante]({self.comprovante_url.value.strip()})",
            inline=False,
        )
        review_embed.set_thumbnail(url=author.display_avatar.url)
        review_embed.set_footer(text="Use os botões abaixo para Aprovar ou Reprovar")

        # Envia no canal de aprovação
        ch = discord.utils.get(guild.text_channels, name=APROVAR_CHANNEL)
        if ch:
            await ch.send(
                embed=review_embed,
                view=_MediatorApprovalView(applicant_id=author.id),
            )
        else:
            logger.warning(f"[MediatorRegister] Canal #{APROVAR_CHANNEL} não encontrado.")

        await interaction.followup.send(
            embed=discord.Embed(
                title="Candidatura enviada!",
                description=(
                    "Seus dados foram enviados para análise.\n"
                    "Você receberá uma mensagem direta com o resultado em breve."
                ),
                color=0x27AE60,
            ),
            ephemeral=True,
        )


# ═══════════════════════════════════════════════════════════════
# View de aprovação — canal #aprovar-mediadores
# ═══════════════════════════════════════════════════════════════

class _MediatorApprovalView(discord.ui.View):

    def __init__(self, applicant_id: int):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id

    @discord.ui.button(
        label="✅ Aprovar",
        style=discord.ButtonStyle.success,
        custom_id="mediator_register:approve",
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Sem permissão.", ephemeral=True)
            return

        await interaction.response.defer()
        guild  = interaction.guild
        member = guild.get_member(self.applicant_id)

        # Atribuir cargo
        role = discord.utils.get(guild.roles, name=CONTROLLER_ROLE)
        if member and role:
            try:
                await member.add_roles(role, reason=f"Aprovado por {interaction.user}")
            except discord.Forbidden:
                pass

        # Atualiza banco
        try:
            from config.database import db
            await db.get_collection("mediator_applications").update_one(
                {"user_id": str(self.applicant_id)},
                {"$set": {"status": "aprovado", "approved_by": str(interaction.user), "approved_at": utcnow()}},
            )
            # Cria/atualiza registro em mediators
            from datetime import timedelta
            await db.get_collection("mediators").update_one(
                {"user_id": self.applicant_id},
                {
                    "$set": {
                        "user_id":         self.applicant_id,
                        "username":        str(member) if member else str(self.applicant_id),
                        "is_active":       True,
                        "in_queue":        False,
                        "expiration_date": utcnow() + timedelta(days=30),
                        "updated_at":      utcnow(),
                    }
                },
                upsert=True,
            )
        except Exception as e:
            logger.error(f"[MediatorApproval] DB error: {e}")

        # DM para o candidato
        if member:
            try:
                await member.send(embed=discord.Embed(
                    title="🎉 Candidatura Aprovada!",
                    description=(
                        f"Parabéns! Você foi aprovado como mediador no **X1 Frifas**.\n"
                        f"O cargo **{CONTROLLER_ROLE}** foi atribuído à sua conta.\n\n"
                        "Boas-vindas à equipe!"
                    ),
                    color=0x27AE60,
                ))
            except discord.Forbidden:
                pass

        # Edita mensagem de revisão
        for b in self.children:
            b.disabled = True
        await interaction.message.edit(
            embed=interaction.message.embeds[0].set_footer(
                text=f"✅ Aprovado por {interaction.user} em {utcnow().strftime('%d/%m/%Y %H:%M UTC')}"
            ),
            view=self,
        )

    @discord.ui.button(
        label="❌ Reprovar",
        style=discord.ButtonStyle.danger,
        custom_id="mediator_register:reject",
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Sem permissão.", ephemeral=True)
            return

        await interaction.response.send_modal(_RejectReasonModal(self.applicant_id, self))


class _RejectReasonModal(discord.ui.Modal, title="Motivo da Reprovação"):

    motivo = discord.ui.TextInput(
        label="Motivo",
        placeholder="Descreva brevemente o motivo da reprovação",
        style=discord.TextStyle.paragraph,
        min_length=5,
        max_length=300,
    )

    def __init__(self, applicant_id: int, approval_view: _MediatorApprovalView):
        super().__init__()
        self.applicant_id  = applicant_id
        self.approval_view = approval_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            from config.database import db
            await db.get_collection("mediator_applications").update_one(
                {"user_id": str(self.applicant_id)},
                {
                    "$set": {
                        "status":      "reprovado",
                        "rejected_by": str(interaction.user),
                        "reject_reason": self.motivo.value.strip(),
                        "rejected_at": utcnow(),
                    }
                },
            )
        except Exception as e:
            logger.error(f"[MediatorReject] DB error: {e}")

        member = interaction.guild.get_member(self.applicant_id)
        if member:
            try:
                await member.send(embed=discord.Embed(
                    title="Candidatura Reprovada",
                    description=(
                        f"Infelizmente sua candidatura para mediador no **X1 Frifas** "
                        f"não foi aprovada.\n\n"
                        f"**Motivo:** {self.motivo.value.strip()}\n\n"
                        "Em caso de dúvidas, entre em contato com a administração."
                    ),
                    color=0xE74C3C,
                ))
            except discord.Forbidden:
                pass

        for b in self.approval_view.children:
            b.disabled = True
        await interaction.message.edit(
            embed=interaction.message.embeds[0].set_footer(
                text=f"❌ Reprovado por {interaction.user} em {utcnow().strftime('%d/%m/%Y %H:%M UTC')}"
            ),
            view=self.approval_view,
        )
