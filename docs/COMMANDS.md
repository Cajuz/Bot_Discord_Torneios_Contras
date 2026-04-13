<div align="center">

# 📖 X1 Frifas — Referência de Comandos

**Guia completo de comandos, canais e permissões**

</div>

---

## 📋 Sumário

- [Legenda](#-legenda)
- [ADM / Controller](#️-adm--controller)
  - [Setup do Servidor](#setup-do-servidor)
  - [Moderação](#moderação)
  - [Operacional](#operacional)
- [Mediador](#-mediador)
- [Suporte](#-suporte)
- [Analista](#-analista)
- [Membro / Jogador](#-membro--jogador)
- [Mapa de Canais](#-mapa-de-canais)
- [Fluxo de Partida](#-fluxo-de-partida)

---

## 🏷️ Legenda

| Símbolo | Significado |
|---------|------------|
| `!comando` | Comando de prefixo (digitar no chat) |
| `/comando` | Slash command (barra `/` no Discord) |
| 🔘 Botão | Interação via botão na interface |
| ✅ | Funcional |
| ⚠️ | Funcional com restrição de contexto |
| 🔒 | Requer permissão de administrador Discord |
| 🎯 | Requer cargo específico no servidor |

---

## 🛡️ ADM / Controller

### Setup do Servidor

> Execute estes comandos em qualquer canal onde você tenha permissão de administrador.

#### Setup Completo

| Comando | Status | Canal | Descrição |
|---------|--------|-------|-----------|
| `!setupcanais` 🔒 | ✅ | Qualquer | Cria/atualiza **toda** a estrutura: cargos, categorias, canais, permissões, painéis, cards de fila e dashboards |

> ⚠️ Leva alguns segundos. O bot responde com confirmação ao concluir.

---

#### Setup Individual — Painéis Base

| Comando | Status | Canal | Descrição |
|---------|--------|-------|-----------|
| `!setup_guias` 🔒 | ✅ | Qualquer | Reescreve os 4 guias: `#guia-jogador`, `#guia-mediador`, `#guia-suporte`, `#guia-analista` |
| `!setup_suporte` 🔒 | ✅ | Qualquer | Posta painéis em `#solicitar-suporte` e `#suporte-admin` |
| `!setup_mediador` 🔒 | ✅ | Qualquer | Posta painéis em `#painel-mediador`, `#mediadores-adm` e `#quero-ser-mediador` |
| `!setup_quero_ser_mediador` 🔒 | ✅ | Qualquer | Posta somente o painel de candidatura a mediador |
| `!setup_influencers` 🔒 | ✅ | Qualquer | Posta painéis em `#influencers` e `#influencers-admin` |
| `!setup_pix` 🔒 | ✅ | Qualquer | Posta o painel PIX em `#pix-mediador` |
| `!setup_renovacao` 🔒 | ✅ | Qualquer | Posta painel de renovação em `#renovacao` |
| `!setup_partidas` 🔒 | ✅ | Qualquer | Posta todos os cards de fila nos canais de partida |
| `!setup_dashboards` 🔒 | ✅ | Qualquer | Atualiza todos os dashboards de analytics |
| `!setup_faturamento` 🔒 | ✅ | Qualquer | Posta painel em `#faturamento` |

---

#### Setup Individual — Novos Painéis

| Comando | Status | Canal | Descrição |
|---------|--------|-------|-----------|
| `!setup_avisos` 🔒 | ✅ | Qualquer | Posta o painel fixo em `#avisos` |
| `!setup_aprovar_mediadores` 🔒 | ✅ | Qualquer | Posta o painel instrucional em `#aprovar-mediadores` |
| `!setup_historico_exposed` 🔒 | ✅ | Qualquer | Posta o painel de histórico em `#historico-blacklist` |
| `!setup_mediadores_afks` 🔒 | ✅ | Qualquer | Posta o painel de AFK em `#mediadores-afks` |
| `!setup_cadastro_mediador` 🔒 | ✅ | Qualquer | Posta o card com formulário de cadastro em `#cadastro-mediador` |
| `!setup_blacklist` 🔒 | ✅ | Qualquer | Posta o painel de consulta em `#blacklist` |
| `!setup_painel_contratos` 🔒 | ✅ | Qualquer | Gera/atualiza painéis em `#painel-contratos` e `#analytics-adm` |

---

### Moderação

| Comando | Status | Canal | Permissão | Descrição |
|---------|--------|-------|----------|-----------|
| `!bloquear @membro [motivo]` | ✅ | Qualquer | Manage Messages | Aplica cargo de bloqueio ao membro e registra no banco |
| `!desbloquear @membro` | ✅ | Qualquer | Manage Messages | Remove cargo de bloqueio do membro |
| `!limpar <1–100>` | ✅ | Qualquer | Manage Messages | Apaga N mensagens do canal (máx. 100) |

---

### Operacional

| Comando | Status | Canal | Permissão | Descrição |
|---------|--------|-------|----------|-----------|
| `!healthcheck` 🔒 | ✅ | Qualquer | Administrador | Exibe painel técnico interativo: latência, conexão, fila, estatísticas |
| `!faturamento [@membro]` 🎯 | ✅ | Qualquer | ADM ou Mediador | Relatório paginado de partidas e faturamento de um mediador |
| `!verpix [@membro]` 🔒 | ✅ | Qualquer | Administrador | Exibe chave PIX e QR Code de um mediador |
| `!help_adm` 🔒 | ✅ | Qualquer | Administrador | Lista todos os comandos admin com descrição |

---

### Análise & Exposição (via analyst_cog)

| Comando | Status | Canal | Permissão | Descrição |
|---------|--------|-------|----------|-----------|
| `!setup_analise` 🔒 | ✅ | Qualquer | Administrador | Posta o painel de solicitação de análise |
| `!setup_exposed` 🔒 | ✅ | Qualquer | Administrador | Posta o painel de gestão da blacklist |

---

### Gestão de Mediadores (via mediator_cog)

| Comando | Status | Canal | Permissão | Descrição |
|---------|--------|-------|----------|-----------|
| `!addmediador @membro` 🔒 | ✅ | Qualquer | Administrador | Adiciona o membro à fila de mediadores disponíveis |
| `!removemediador @membro` 🔒 | ✅ | Qualquer | Administrador | Remove o membro da fila de mediadores |
| `!fila` 🎯 | ✅ | Qualquer | ADM / Mediador | Exibe a fila atual e status de cada mediador |

---

### Thread Pool (via thread_pool_cog)

| Comando | Status | Canal | Permissão | Descrição |
|---------|--------|-------|----------|-----------|
| `/threadpool setup` 🔒 | ✅ | Qualquer | Administrador | Posta ou atualiza o painel de status do pool de threads |
| `/threadpool preaquecer [qtd]` 🔒 | ✅ | Qualquer | Administrador | Cria N threads arquivadas no pool para uso futuro |
| `/threadpool status` 🔒 | ✅ | Qualquer | Administrador | Exibe resumo: total, disponíveis, em uso, margem |

---

### Influencers (via influencer_cog)

| Comando | Status | Canal | Permissão | Descrição |
|---------|--------|-------|----------|-----------|
| `/influencer add @m <invitecode> [comissao]` 🔒 | ✅ | Qualquer | Administrador | Cadastra influencer com código de convite e % de comissão |
| `/influencer remove @membro` 🔒 | ✅ | Qualquer | Administrador | Remove influencer |
| `/influencer stats @membro` 🔒 | ✅ | Qualquer | Administrador | Estatísticas do influencer (convites, comissão acumulada) |
| `/influencer faturamento` 🔒 | ✅ | Qualquer | Administrador | Relatório de faturamento de todos os influencers |
| `/influencer ranking` | ✅ | Qualquer | Qualquer | Ranking público de influencers por convites |

---

### Renovação Manual (via renewal_cog)

| Comando | Status | Canal | Permissão | Descrição |
|---------|--------|-------|----------|-----------|
| `!renovarmediador @m [dias] [valor]` 🔒 | ✅ | Qualquer | Administrador | Gera cobrança PIX manual para renovação do mediador |

---

### Convites & Rate Limit (via invite_cog)

| Comando | Status | Canal | Permissão | Descrição |
|---------|--------|-------|----------|-----------|
| `/topconvites` 🔒 | ✅ | Qualquer | Administrador | Ranking de membros que mais convidaram |
| `/ratelimitstats [horas]` 🔒 | ✅ | Qualquer | Administrador | Estatísticas de rate limit nas últimas N horas |

---

## ⚖️ Mediador

> ⚠️ Os comandos de fluxo de partida **devem ser usados dentro da thread da partida**.

### Fila de Mediadores

| Interação | Status | Canal | Descrição |
|-----------|--------|-------|-----------|
| 🔘 **Entrar na Fila** | ✅ | `#painel-mediador` | Coloca o mediador disponível para assumir partidas |
| 🔘 **Sair da Fila** | ✅ | `#painel-mediador` | Remove o mediador da fila |
| `!fila` | ✅ | Qualquer | Exibe status atual da fila |

---

### Fluxo de Partida

| Comando | Status | Canal | Descrição |
|---------|--------|-------|-----------|
| `!confirmar_pagamento` 🎯 | ✅ | Thread da partida | Confirma que ambos os jogadores pagaram via PIX |
| `!iniciar_partida` 🎯 | ✅ | Thread da partida | Declara oficialmente o início da partida |
| `!winner_team blue` 🎯 | ✅ | Thread da partida | Define o **Time Azul** como vencedor |
| `!winner_team red` 🎯 | ✅ | Thread da partida | Define o **Time Vermelho** como vencedor |
| `!prize` 🎯 | ✅ | Thread da partida | Confirma que o prêmio foi enviado ao vencedor |
| `!cancelar_match [motivo]` 🎯 | ✅ | Thread da partida | Cancela a partida e devolve a thread ao pool |
| `/silence @membro [seg] [motivo]` 🎯 | ✅ | Thread / canal | Silencia jogador no contexto atual |
| `!menu_partida` 🎯 | ✅ | Thread da partida | Envia painel de controle completo via DM |

---

### PIX e Renovação

| Comando / Interação | Status | Canal | Descrição |
|---------------------|--------|-------|-----------|
| 🔘 **Cadastrar PIX** | ✅ | `#pix-mediador` | Abre modal para cadastrar/atualizar chave PIX |
| `/renovar [dias]` | ✅ | Qualquer | Gera cobrança PIX para renovar própria licença (7, 15 ou 30 dias) |
| `!verpix` | ✅ | Qualquer | Exibe própria chave PIX e QR Code |

---

## 🎫 Suporte

### Painel de Chamados

| Interação | Status | Canal | Descrição |
|-----------|--------|-------|-----------|
| 🔘 **Abrir Ticket** | ✅ | `#solicitar-suporte` | Cria ticket e notifica o staff em `#chamados` |
| 🔘 **Assumir** | ✅ | `#chamados` | Atendente assume o ticket e abre canal privado |

### Comandos de Atendimento

| Comando | Status | Canal | Permissão | Descrição |
|---------|--------|-------|----------|-----------|
| `!fechar_chamado <ticket_id>` 🎯 | ✅ | Canal do chamado | Suporte / ADM | Fecha e arquiva o chamado |
| `!concluir_chamado <ticket_id>` 🎯 | ✅ | Canal do chamado | Suporte / ADM | Marca chamado como resolvido com sucesso |
| `!criar_canal_suporte [@membro]` 🎯 | ✅ | Qualquer | Suporte / ADM | Cria canal privado de atendimento para o membro |
| `/renomear_canal [sufixo]` 🎯 | ✅ | Canal do chamado | Suporte | Renomeia o canal com o assunto do chamado |

---

## 🔍 Analista

### Gestão de Casos

| Comando | Status | Canal | Descrição |
|---------|--------|-------|-----------|
| `/assumir_caso <case_id>` 🎯 | ✅ | `#casos-analisar` | Analista assume o caso e o bloqueia para outros |
| `/decidir_caso <case_id> <decisao> <motivo>` 🎯 | ✅ | `#casos-analisar` | Encerra o caso com decisão: `confirmado` / `inconclusivo` / `invalido` |

---

### Blacklist

| Comando | Status | Canal | Descrição |
|---------|--------|-------|-----------|
| `/blacklist_add <player_id> <motivo>` 🎯 | ✅ | `#exposed` | Adiciona jogador à blacklist (registra no banco + posta no canal) |
| `/blacklist_remove <player_id>` 🎯 | ✅ | `#exposed` | Remove jogador da blacklist |
| `/blacklist_check <player_id>` 🎯 | ✅ | Qualquer | Consulta se um jogador está na blacklist |
| `/blacklist_list` 🎯 | ✅ | Qualquer | Lista os últimos registros da blacklist |
| 🔘 **Verificar Minha Situação** | ✅ | `#blacklist` | Auto-verificação — exibe status do próprio usuário (ephemeral) |
| 🔘 **Buscar por Discord ID** | ✅ | `#blacklist` | Abre modal para buscar qualquer usuário pelo ID (visível apenas para quem clicou) |

---

## 🎮 Membro / Jogador

### Filas e Partidas

| Interação / Comando | Status | Canal | Descrição |
|---------------------|--------|-------|-----------|
| 🔘 **Entrar na Fila** | ✅ | Canal de partida | Entra na fila do card selecionado (modo + valor) |
| 🔘 **Sair da Fila** | ✅ | Canal de partida | Cancela entrada na fila |
| `!cancelar` | ✅ | Qualquer | Cancela todas as entradas de fila ativas |
| 🔘 **Confirmar Presença** | ✅ | Thread da partida | Confirma que está presente para a partida |
| 🔘 **Confirmar Recebimento do Prêmio** | ✅ | Thread da partida | Confirma que recebeu o prêmio após vitória |

---

### Perfil e Histórico

| Comando | Status | Canal | Descrição |
|---------|--------|-------|-----------|
| `/perfil` | ✅ | Qualquer | Exibe estatísticas pessoais: partidas, vitórias, taxa de vitória |
| `/convites [@membro]` | ✅ | Qualquer | Consulta quantos membros um usuário convidou |

---

### Suporte

| Interação / Comando | Status | Canal | Descrição |
|---------------------|--------|-------|-----------|
| 🔘 **Abrir Ticket** | ✅ | `#solicitar-suporte` | Abre chamado de suporte |
| `!chamado` | ✅ | Qualquer | Lista os próprios chamados abertos |
| `!fechar_chamado <ticket_id>` | ✅ | Qualquer | Fecha o próprio chamado |

---

### Análise de Suspeita

| Comando | Status | Canal | Descrição |
|---------|--------|-------|-----------|
| `/solicitar_analise <match_id> <motivo> [evidencia]` | ✅ | `#solicitar-analise` | Solicita investigação de suspeita de hack em uma partida |

---

### Blacklist

| Interação | Status | Canal | Descrição |
|-----------|--------|-------|-----------|
| 🔘 **Verificar Minha Situação** | ✅ | `#blacklist` | Consulta se o próprio usuário está na blacklist (privado) |
| 🔘 **Buscar por Discord ID** | ✅ | `#blacklist` | Busca qualquer usuário pelo Discord ID (privado) |

---

## 🗺️ Mapa de Canais

### 📢 Informações

| Canal | Quem vê | Descrição |
|-------|---------|----------|
| `#avisos` | Todos | Avisos oficiais da equipe |
| `#guia-jogador` | Todos | Tutorial completo para jogadores |
| `#ranking` | Todos | Dashboard de ranking atualizado automaticamente |
| `#blacklist` | Todos | Painel de consulta de blacklist |

---

### 🎮 Partidas

| Canal | Quem usa | Descrição |
|-------|----------|----------|
| `#1x1-mob`, `#2x2-mob`, etc. | Jogadores | Cards de fila por modo Mobile |
| `#1x1-emu`, `#2x2-emu`, etc. | Jogadores | Cards de fila por modo Emulador |
| `#2x2-mix`, `#3x3-mix`, etc. | Jogadores | Cards de fila por modo Misto |

---

### ⚖️ Mediação

| Canal | Quem acessa | Descrição |
|-------|------------|----------|
| `#painel-mediador` | Mediadores | Entrar/sair da fila de mediadores |
| `#pix-mediador` | Mediadores | Cadastrar/atualizar chave PIX |
| `#renovacao` | Mediadores | Renovar licença via PIX |
| `#faturamento` | Mediadores / ADM | Relatório de faturamento |
| `#mediadores-adm` | ADM | Painel administrativo de mediadores |
| `#aprovar-mediadores` | ADM | Cards automáticos de aprovação de candidatos |
| `#mediadores-afks` | ADM | Lista de mediadores AFK/inativos |
| `#cadastro-mediador` | ADM / Suporte | Formulário de cadastro de novo mediador |
| `#quero-ser-mediador` | Todos | Canal para candidatura a mediador |

---

### 🎫 Suporte

| Canal | Quem acessa | Descrição |
|-------|------------|----------|
| `#solicitar-suporte` | Todos | Painel para abrir ticket |
| `#chamados` | Suporte / ADM | Cards de chamados aguardando atendimento |
| `#chat-suporte-staff` | Suporte / ADM | Comunicação interna da equipe de suporte |
| `#suporte-admin` | ADM | Painel administrativo de suporte |

---

### 🔍 Análise e Blacklist

| Canal | Quem acessa | Descrição |
|-------|------------|----------|
| `#solicitar-analise` | Todos | Painel para denunciar suspeita de hack |
| `#casos-analisar` | Analistas / ADM | Fila de casos para análise |
| `#painel-analista` | Analistas / ADM | Painel pessoal do analista |
| `#exposed` | Analistas / ADM | Gestão ativa da blacklist |
| `#historico-blacklist` | ADM | Log completo de adições/remoções da blacklist |
| `#chat-analistas` | Analistas / ADM | Comunicação interna dos analistas |

---

### 📣 Influencers

| Canal | Quem acessa | Descrição |
|-------|------------|----------|
| `#influencers` | Todos | Painel público de influencers |
| `#influencers-admin` | ADM | Painel administrativo de influencers |

---

### 📊 Dashboards e Logs (ADM)

| Canal | Descrição |
|-------|-----------|
| `#analytics-adm` | Dashboard financeiro completo |
| `#painel-contratos` | Contratos e renovações de mediadores |
| `#dashboard-partidas` | Estatísticas de partidas em tempo real |
| `#dashboard-mediadores` | Performance e status dos mediadores |
| `#dashboard-suporte` | Métricas do suporte |
| `#dashboard-influencers` | Métricas de influencers |
| `#status-bot` | Status técnico do bot |
| `#health-check` | Painel interativo de health check |
| `#logs-pix` | Registro de pagamentos PIX |
| `#logs-calls` | Log de chamadas de voz/partidas |
| `#logs-commands` | Log de todos os comandos executados |
| `#logs-delete` | Log de mensagens deletadas |
| `#logs-troca-cargo` | Log de alterações de cargo |

---

## 🔄 Fluxo de Partida

```
1. Jogador clica no botão de valor no card do canal de partida
       ↓
2. Fila completa (2 a 8 jogadores dependendo do modo)
       ↓
3. Thread criada automaticamente → jogadores confirmam presença
       ↓
4. Mediador entra na thread → !confirmar_pagamento
       ↓
5. !iniciar_partida → partida começa oficialmente
       ↓
6. Fim da partida → mediador usa !winner_team blue OU !winner_team red
       ↓
7. !prize → mediador confirma que o prêmio foi enviado
       ↓
8. Vencedor clica em [Confirmar Recebimento do Prêmio]
       ↓
9. Partida finalizada → thread devolvida ao pool para reutilização
```

---

<div align="center">

*Dúvidas? Execute `!help_adm` no servidor ou consulte [`deploy/MANUTENCAO.md`](../deploy/MANUTENCAO.md)*

</div>
