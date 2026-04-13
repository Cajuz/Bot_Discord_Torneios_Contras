"""
mediator_register_view.py  v2

Fluxo:
  1. Apenas ADM ou Suporte clicam em "Cadastrar Mediador" no canal
     #solicitacoes-mediador (card postado via !setup_cadastro_mediador)
  2. Modal abre com campos: nome, CPF (obrigatório), endereço (opcional),
     telefone, chave PIX, link do comprovante
  3. Submissão salva no banco e gera embed de revisão em #aprovar-mediadores
  4. ADM Aprova → cargo Controller + registro em mediators (30 dias)
             ou Reprova → modal de motivo → DM para o candidato informado
"""
from __future__ import annotations

import discord
from utils.datetime_utils import utcnow
from utils.logger import logger

THEME_COLOR     = 0xFFD54F
APROVAR_CHANNEL = "aprovar-mediadores"
CONTROLLER_ROLE = "Controller"
_ALLOWED_ROLES  = {"ADM", "Suporte"}   # apenas esses podem abrir o formulário


# ═══════════════════════════════════════════════════════════════
# View persistente — card fixo
# ═══════════════════════════════════════════════════════════════

class MediatorRegisterView(discord.ui.View):
    """Card fixo em #solicitacoes-mediador. Persiste entre reinicializações."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📋 Cadastrar Mediador",
        style=discord.ButtonStyle.primary,
        custom_id="mediator_register:open_form",
    )
    async def open_form(self, interaction: discord.Interaction, _: discord.ui.Button):
        # Verifica se é ADM ou Suporte
        role_names = {r.name for r in interaction.user.roles}
        is_adm     = interaction.user.guild_permissions.administrator
        if not is_adm and not (role_names & _ALLOWED_ROLES):
            await interaction.response.send_message(
                "❌ Apenas **ADM** ou **Suporte** podem abrir o formulário de cadastro.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(_MediatorRegisterModal())


# ═══════════════════════════════════════════════════════════════
# Modal — dados pessoais (Discord limita 5 campos por modal)
#   Campo 1: Nome completo (obrigatório)
#   Campo 2: CPF (obrigatório)
#   Campo 3: Telefone / WhatsApp (obrigatório)
#   Campo 4: Chave PIX (obrigatório)
#   Campo 5: Endereço + link comprovante (opcional — multi-linha)
# ═══════════════════════════════════════════════════════════════

class _MediatorRegisterModal(discord.ui.Modal, title="Cadastro de Mediador — X1 Frifas"):

    nome_completo = discord.ui.TextInput(
        label="Nome completo *",
        placeholder="Ex: João da Silva",
        min_length=3,
        max_length=100,
        required=True,
    )
    cpf = discord.ui.TextInput(
        label="CPF (somente números) *",
        placeholder="Ex: 12345678900",
        min_length=11,
        max_length=14,
        required=True,
    )
    telefone_pix = discord.ui.TextInput(
        label="Telefone/WhatsApp  |  Chave PIX *",
        placeholder="Telefone: 11999998888  |  PIX: cpf/email/telefone/aleatória",
        min_length=5,
        max_length=200,
        required=True,
    )
    endereco = discord.ui.TextInput(
        label="Endereço completo (opcional)",
        placeholder="Rua, número, bairro, cidade, UF — CEP",
        max_length=250,
        required=False,
        style=discord.TextStyle.paragraph,
    )
    comprovante_url = discord.ui.TextInput(
        label="Link do comprovante de pagamento *",
        placeholder="Google Drive, Imgur, etc.",
        min_length=5,
        max_length=300,
        required=True,
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild  = interaction.guild
        author = interaction.user   # quem preencheu = ADM/Suporte

        # Salva no banco
        try:
            from config.database import db
            await db.get_collection("mediator_applications").update_one(
                {"cpf": self.cpf.value.strip()},   # chave única = CPF
                {
                    "$set": {
                        "registered_by":  str(author.id),
                        "nome_completo":  self.nome_completo.value.strip(),
                        "cpf":            self.cpf.value.strip(),
                        "telefone_pix":   self.telefone_pix.value.strip(),
                        "endereco":       self.endereco.value.strip() or None,
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
            description=f"Cadastro realizado por {author.mention}.",
            color=THEME_COLOR,
            timestamp=utcnow(),
        )
        review_embed.add_field(name="Nome completo",  value=self.nome_completo.value.strip(), inline=False)
        review_embed.add_field(name="CPF",            value=f"||{self.cpf.value.strip()}||",  inline=True)
        review_embed.add_field(name="Tel / PIX",      value=self.telefone_pix.value.strip(),   inline=True)
        endereco_val = self.endereco.value.strip() or "*Não informado*"
        review_embed.add_field(name="Endereço",        value=endereco_val,                      inline=False)
        review_embed.add_field(
            name="Comprovante",
            value=f"[Ver comprovante]({self.comprovante_url.value.strip()})",
            inline=False,
        )
        review_embed.add_field(name="Registrado por", value=author.mention, inline=True)
        review_embed.set_footer(text="Use os botões abaixo para Aprovar ou Reprovar")

        ch = discord.utils.get(guild.text_channels, name=APROVAR_CHANNEL)
        if ch:
            await ch.send(
                embed=review_embed,
                view=_MediatorApprovalView(cpf=self.cpf.value.strip()),
            )
        else:
            logger.warning(f"[MediatorRegister] Canal #{APROVAR_CHANNEL} não encontrado.")

        await interaction.followup.send(
            embed=discord.Embed(
                title="✅ Candidatura registrada!",
                description="O ADM foi notificado para revisão e aprovação.",
                color=0x27AE60,
            ),
            ephemeral=True,
        )


# ═══════════════════════════════════════════════════════════════
# View de aprovação — canal #aprovar-mediadores
# ═══════════════════════════════════════════════════════════════

class _MediatorApprovalView(discord.ui.View):

    def __init__(self, cpf: str, discord_id: int | None = None):
        super().__init__(timeout=None)
        self.cpf        = cpf
        self.discord_id = discord_id  # preenchido após aprovação se Discord ID for informado

    @discord.ui.button(
        label="✅ Aprovar",
        style=discord.ButtonStyle.success,
        custom_id="mediator_register:approve",
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Sem permissão.", ephemeral=True)
            return
        await interaction.response.send_modal(
            _ApproveDiscordModal(cpf=self.cpf, approval_view=self)
        )

    @discord.ui.button(
        label="❌ Reprovar",
        style=discord.ButtonStyle.danger,
        custom_id="mediator_register:reject",
    )
    async def reject(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Sem permissão.", ephemeral=True)
            return
        await interaction.response.send_modal(
            _RejectReasonModal(cpf=self.cpf, approval_view=self)
        )


class _ApproveDiscordModal(discord.ui.Modal, title="Aprovar Mediador — Informe o Discord ID"):
    """ADM informa o Discord ID do mediador para atribuir o cargo."""

    discord_id_input = discord.ui.TextInput(
        label="Discord ID do mediador",
        placeholder="Ex: 123456789012345678",
        min_length=15,
        max_length=20,
        required=True,
    )

    def __init__(self, cpf: str, approval_view: _MediatorApprovalView):
        super().__init__()
        self.cpf           = cpf
        self.approval_view = approval_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            uid = int(self.discord_id_input.value.strip())
        except ValueError:
            await interaction.followup.send("Discord ID inválido.", ephemeral=True)
            return

        guild  = interaction.guild
        member = guild.get_member(uid) or await guild.fetch_member(uid)

        # Atribui cargo
        role = discord.utils.get(guild.roles, name=CONTROLLER_ROLE)
        if member and role:
            try:
                await member.add_roles(role, reason=f"Aprovado por {interaction.user}")
            except discord.Forbidden:
                pass

        # Atualiza banco
        try:
            from config.database import db
            from datetime import timedelta
            now = utcnow()
            await db.get_collection("mediator_applications").update_one(
                {"cpf": self.cpf},
                {
                    "$set": {
                        "user_id":     str(uid),
                        "username":    str(member) if member else str(uid),
                        "status":      "aprovado",
                        "approved_by": str(interaction.user),
                        "approved_at": now,
                    }
                },
            )
            await db.get_collection("mediators").update_one(
                {"user_id": uid},
                {
                    "$set": {
                        "user_id":         uid,
                        "username":        str(member) if member else str(uid),
                        "cpf":             self.cpf,
                        "is_active":       True,
                        "in_queue":        False,
                        "expiration_date": now + timedelta(days=30),
                        "updated_at":      now,
                    }
                },
                upsert=True,
            )
        except Exception as e:
            logger.error(f"[MediatorApproval] DB error: {e}")

        # DM para o mediador aprovado
        if member:
            try:
                await member.send(embed=discord.Embed(
                    title="🎉 Você foi aprovado como Mediador!",
                    description=(
                        "Bem-vindo à equipe **X1 Frifas**!\n"
                        f"O cargo **{CONTROLLER_ROLE}** foi atribuído à sua conta.\n\n"
                        "Fique atento ao canal de renovação para manter sua licença ativa."
                    ),
                    color=0x27AE60,
                ))
            except discord.Forbidden:
                pass

        # Edita a mensagem de revisão
        for b in self.approval_view.children:
            b.disabled = True
        await interaction.message.edit(
            embed=interaction.message.embeds[0].set_footer(
                text=f"✅ Aprovado por {interaction.user} | Discord: {uid} | "
                     f"{utcnow().strftime('%d/%m/%Y %H:%M UTC')}"
            ),
            view=self.approval_view,
        )


class _RejectReasonModal(discord.ui.Modal, title="Motivo da Reprovação"):

    motivo = discord.ui.TextInput(
        label="Motivo",
        placeholder="Descreva brevemente o motivo da reprovação",
        style=discord.TextStyle.paragraph,
        min_length=5,
        max_length=300,
    )
    discord_id_input = discord.ui.TextInput(
        label="Discord ID do candidato (para DM)",
        placeholder="Ex: 123456789012345678 — deixe vazio se não souber",
        required=False,
        max_length=20,
    )

    def __init__(self, cpf: str, approval_view: _MediatorApprovalView):
        super().__init__()
        self.cpf           = cpf
        self.approval_view = approval_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            from config.database import db
            await db.get_collection("mediator_applications").update_one(
                {"cpf": self.cpf},
                {
                    "$set": {
                        "status":        "reprovado",
                        "rejected_by":   str(interaction.user),
                        "reject_reason": self.motivo.value.strip(),
                        "rejected_at":   utcnow(),
                    }
                },
            )
        except Exception as e:
            logger.error(f"[MediatorReject] DB error: {e}")

        # Tenta enviar DM se Discord ID informado
        raw_id = self.discord_id_input.value.strip()
        if raw_id:
            try:
                uid    = int(raw_id)
                member = interaction.guild.get_member(uid) or await interaction.guild.fetch_member(uid)
                if member:
                    await member.send(embed=discord.Embed(
                        title="Candidatura Reprovada — X1 Frifas",
                        description=(
                            "Infelizmente sua candidatura para mediador **não foi aprovada**.\n\n"
                            f"**Motivo:** {self.motivo.value.strip()}\n\n"
                            "Em caso de dúvidas, entre em contato com a administração."
                        ),
                        color=0xE74C3C,
                    ))
            except Exception:
                pass

        for b in self.approval_view.children:
            b.disabled = True
        await interaction.message.edit(
            embed=interaction.message.embeds[0].set_footer(
                text=f"❌ Reprovado por {interaction.user} | "
                     f"{utcnow().strftime('%d/%m/%Y %H:%M UTC')}"
            ),
            view=self.approval_view,
        )
