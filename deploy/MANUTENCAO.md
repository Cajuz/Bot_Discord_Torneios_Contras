# Documentação de Comandos — X1 Frifas Bot

---

## Configuração inicial do servidor

Após subir o bot pela primeira vez, rode **apenas este comando**:

```
!setupcanais
```

Ele faz tudo automaticamente em sequência:
- Cria todos os cargos
- Cria todas as categorias e canais na ordem correta
- Posta os guias em cada canal de staff
- Posta todos os painéis interativos nos canais corretos

Não precisa rodar mais nenhum `!setup_*` manualmente após isso.

---

## Onde alterar configurações do servidor

| O que alterar | Arquivo |
|---|---|
| Prefixo `!` dos comandos | `src/config/discord_bot.py` → `command_prefix` |
| Nomes de canais | `src/services/channel_service.py` → constantes no topo |
| Ordem das categorias e canais | `src/services/channel_service.py` → `CHANNEL_STRUCTURE` |
| Permissões por canal | `src/services/channel_service.py` → `CHANNEL_PERMISSIONS` |
| Cargos criados | `src/services/channel_service.py` → `ALL_ROLES` |
| Valores de aposta | `src/config/channels_config.py` → `BET_VALUES` |
| Modos de jogo | `src/config/channels_config.py` → `CATEGORIES` |
| Preços de renovação | `.env` → `RENEWAL_PRICE_7D`, `RENEWAL_PRICE_15D`, `RENEWAL_PRICE_30D` |

---

## Painéis interativos — onde ficam e quem usa

| Canal | Painel | Quem usa |
|---|---|---|
| `#chat-suporte` | Abrir ticket (select menu + botão) | Membros |
| `#chamados-suporte` | Card do ticket com botão Assumir | Support |
| `#painel-mediador` | Entrar/sair da fila, stats, licença | Controller |
| `#mediadores-admin` | Ranking, stats individuais, gerenciar licenças | Admin |
| `#solicitacoes-mediador` | Candidatura a mediador com planos | Todos |
| `#pix-mediadores` | Cadastrar / ver / remover chave PIX | Controller |
| `#renovacao-mediadores` | Renovar licença via PIX (cobrança vai por DM) | Controller |
| `#solicitar-analise` | Solicitar análise de hack (modal) | Membros |
| `#fila-analistas` | Card do caso com Assumir + decisões | Analyst |
| `#analistas-admin` | Visão geral, stats por analista, buscar caso | Admin |
| `#exposed` | Adicionar / remover / buscar na blacklist | Analyst, Admin |
| `#influencers` | Meus stats e faturamento | Influencer |
| `#influencers-admin` | Ranking, status geral, buscar, add/remove | Admin |
| `#suporte-admin` | Visão geral tickets, por agente, buscar, fechar | Admin |

---

## Comandos por perfil

---

### Admin

| Comando | Uso | Descrição |
|---|---|---|
| `!setupcanais` | `!setupcanais` | Constrói o servidor inteiro (canais, cargos, painéis) |
| `!bloquear` | `!bloquear @membro motivo` | Bloqueia membro de usar o bot |
| `!desbloquear` | `!desbloquear @membro` | Remove bloqueio de membro |
| `!limpar` | `!limpar 20` | Remove mensagens do canal (1–100) |
| `!dashboard` | `!dashboard` | Força atualização do dashboard de partidas |
| `!atualizar_dashboards` | `!atualizar_dashboards` | Força atualização de todos os dashboards |
| `!healthcheck` | `!healthcheck` | Status técnico do bot |
| `!addmediador` | `!addmediador @membro` | Adiciona membro como mediador |
| `!removemediador` | `!removemediador @membro` | Remove membro da fila de mediadores |
| `!fila` | `!fila` | Mostra fila completa de mediadores |
| `!verpix` | `!verpix @membro` | Mostra chave PIX de um mediador |
| `!renovar_mediador` | `!renovar_mediador @membro 30 25.00` | Gera cobrança PIX para um mediador |
| `!criar_canal_suporte` | `!criar_canal_suporte @membro` | Cria canal privado para agente de suporte |
| `!help_adm` | `!help_adm` | Lista todos os comandos admin |
| `/influencer add` | `/influencer add @membro abc123 2.50` | Cadastra influencer com invite e comissão |
| `/influencer remove` | `/influencer remove @membro` | Remove influencer do sistema |
| `/influencer ranking` | `/influencer ranking` | Ranking geral de influencers |
| `/top_convites` | `/top_convites` | Ranking dos membros que mais convidaram |
| `/ratelimit_stats` | `/ratelimit_stats horas:24` | Estatísticas de rate limit |

---

### Controller (Mediador)

| Comando | Uso | Descrição |
|---|---|---|
| `/silence` | `/silence @jogador 30 motivo` | Silencia jogador por X segundos (máx 300) |
| `/renovar` | `/renovar dias:30` | Gera cobrança PIX para renovar licença (enviada por DM) |
| `!menu_partida` | `!menu_partida` | Menu de controle da partida (dentro da thread) |
| `!confirmar_pagamento` | `!confirmar_pagamento` | Confirma pagamento dos jogadores |
| `!iniciar_partida` | `!iniciar_partida` | Inicia a partida após pagamento confirmado |
| `!winner_team` | `!winner_team blue` ou `!winner_team red` | Declara time vencedor |
| `!prize` | `!prize` | Confirma entrega do prêmio ao vencedor |
| `!cancelar_match` | `!cancelar_match motivo` | Cancela a partida com motivo |

---

### Analyst (Analista)

| Comando | Uso | Descrição |
|---|---|---|
| `/assumir_caso` | `/assumir_caso case_id:CASE-123-4567` | Assume um caso pendente |
| `/decidir_caso` | `/decidir_caso case_id:... decisao:confirmado motivo:...` | Registra decisão do caso |
| `/blacklist_add` | `/blacklist_add player_id:123 motivo:hack` | Adiciona jogador à blacklist |
| `/blacklist_remove` | `/blacklist_remove player_id:123` | Remove jogador da blacklist |
| `/blacklist_check` | `/blacklist_check player_id:123` | Verifica se jogador está na blacklist |
| `/blacklist_list` | `/blacklist_list` | Lista os últimos 20 jogadores na blacklist |

> Os comandos de blacklist só funcionam dentro do canal `#exposed`.
> O fluxo preferido é usar os botões nos painéis `#solicitar-analise`, `#fila-analistas` e `#exposed`.

---

### Support (Suporte)

| Comando | Uso | Descrição |
|---|---|---|
| `!chamado` | `!chamado` | Lista seus chamados abertos |
| `!fechar_chamado` | `!fechar_chamado TKT-00000001` | Fecha um chamado |
| `/renomear_canal` | `/renomear_canal sufixo:problema_pagamento` | Renomeia seu canal de suporte |

---

### Influencer

| Comando | Uso | Descrição |
|---|---|---|
| `/influencer stats` | `/influencer stats` | Seus stats de convites e comissão |
| `/influencer faturamento` | `/influencer faturamento` | Relatório de comissão acumulada |

> O preferido é usar os botões no canal `#influencers`.

---

### Membro (Jogador)

| Comando | Uso | Descrição |
|---|---|---|
| `/perfil` | `/perfil` | Suas estatísticas de partidas |
| `/solicitar_analise` | `/solicitar_analise match_id:123 motivo:... evidencia:link` | Solicita análise de hack |
| `/convites` | `/convites` | Quantos membros você convidou |
| `!cancelar` | `!cancelar` | Cancela sua entrada na fila |
| `!chamado` | `!chamado` | Lista seus chamados de suporte abertos |
| `!fechar_chamado` | `!fechar_chamado TKT-00000001` | Fecha seu chamado de suporte |
| `!help` | `!help` | Lista os comandos disponíveis |

> O preferido para abrir tickets é usar o botão no canal `#chat-suporte`.
> O preferido para análise é usar o botão no canal `#solicitar-analise`.

---

## Processos automáticos (sem interação)

| Processo | Frequência | O que faz |
|---|---|---|
| AFK Check — Fila | A cada 1 min | Avisa e remove mediadores inativos há 5 min da fila |
| AFK Check — Partida | A cada 1 min | Substitui mediador inativo em partida ativa |
| Aviso de vencimento | A cada 12h | DM para mediadores D-3 e D-1 antes do vencimento |
| Aviso de licença vencida | A cada 12h | DM para mediadores com licença já expirada (máx 7 dias) |
| Expiração de licença | A cada 24h | Remove cargo Controller de mediadores vencidos |
| Expiração de cobrança PIX | 10 min após geração | Cancela cobrança não paga e edita DM do mediador |
| Dashboards | A cada 1h | Atualiza todos os canais de dashboard |
| Dashboard de partidas | Diariamente | Atualiza `#dashboard-partidas` |
| Status do bot | A cada 10 min | Atualiza atividade visível do bot no Discord |
| Rate limit summary | Diariamente | Resumo de rate limits no `#rate-limit-logs` |

---

## Estrutura de canais

| Categoria | Canal | Quem vê |
|---|---|---|
| 📋 INFORMAÇÕES | `#regras` | Todos (somente leitura) |
| | `#boas-vindas` | Todos (somente leitura) |
| | `#guia-jogador` | Todos (somente leitura) |
| | `#guia-mediador` | Controller |
| | `#guia-suporte` | Support |
| | `#guia-analista` | Analyst |
| 📱 MOBILE | `#1x1-mob` `#2x2-mob` `#3x3-mob` `#4x4-mob` | Membros |
| 🖥️ EMULADOR | `#1x1-emu` `#2x2-emu` `#3x3-emu` `#4x4-emu` | Membros |
| 🔀 MISTO | `#4x4-misto` `#3x3-misto` `#2x2-misto` | Membros |
| 🎫 SUPORTE | `#chat-suporte` | Membros |
| | `#chamados-suporte` | Support, Admin |
| | `#suporte-admin` | Admin |
| ⚡ MEDIAÇÃO | `#painel-mediador` | Controller |
| | `#mediadores-admin` | Admin |
| | `#solicitacoes-mediador` | Controller, Admin |
| | `#pix-mediadores` | Controller, Admin |
| | `#renovacao-mediadores` | Controller, Admin |
| 🔍 ANALISTAS | `#solicitar-analise` | Membros |
| | `#fila-analistas` | Analyst, Admin |
| | `#analistas-admin` | Admin |
| | `#exposed` | Analyst, Admin |
| 📊 ANALYTICS | `#dashboard-partidas` | Controller, Admin |
| | `#dashboard-mediadores` | Controller, Admin |
| | `#dashboard-suporte` | Support, Controller, Admin |
| | `#dashboard-influencers` | Influencer, Admin |
| | `#historico-partidas` | Controller, Admin |
| | `#resultados` | Todos (somente leitura) |
| | `#ranking` | Todos (somente leitura) |
| | `#convites` | Admin, Controller |
| 🏆 COMUNIDADE | `#status-bot` | Todos (somente leitura) |
| | `#influencers` | Influencer, Admin |
| | `#influencers-admin` | Admin |
| 🔐 STAFF | `#rate-limit-logs` | Admin |
| | `#membros-bloqueados` | Admin, Controller |
| 📝 LOGS | `#logs-partidas` | Controller, Admin |
| | `#logs-mediadores` | Controller, Admin |
| | `#logs-bot` | Admin |

---

## Cargos criados pelo `!setupcanais`

| Cargo | Quem recebe | Como |
|---|---|---|
| `Membro` | Todos que aceitarem as regras | Automático no onboarding |
| `Controller` | Mediadores | Admin via `!addmediador` ou painel `#mediadores-admin` |
| `Analyst` | Analistas | Admin manual |
| `Support` | Agentes de suporte | Admin manual |
| `Influencer` | Influencers parceiros | Admin via `/influencer add` ou painel `#influencers-admin` |
| `Bloqueado` | Membros bloqueados | Automático (anti-spam) ou `!bloquear` |

---

## Manutenção

### Repostar painéis individualmente

Se um painel sumir ou precisar ser repostado sem rodar o `!setupcanais` completo:

| Comando | Reposta em |
|---|---|
| `!setup_suporte` | `#chat-suporte` |
| `!setup_mediador_completo` | `#painel-mediador` e `#mediadores-admin` |
| `!setup_analistas_completo` | `#fila-analistas` e `#analistas-admin` |
| `!setup_analise` | `#solicitar-analise` |
| `!setup_exposed` | `#exposed` |
| `!setup_influencers` | `#influencers` e `#influencers-admin` |
| `!setup_pix` | `#pix-mediadores` |
| `!setup_renovacao` | `#renovacao-mediadores` |
| `!setup_suporte_admin` | `#suporte-admin` |
| `!setup_guias` | Todos os canais guia |

### Forçar atualização de dashboards

```
!atualizar_dashboards
```

### Verificar saúde do bot

```
!healthcheck
```

Mostra latência do MongoDB, status dos serviços e uptime do bot.

### Verificar rate limits

```
/ratelimit_stats horas:24
```

### Limpar canal

```
!limpar 50
```

Remove as últimas 50 mensagens do canal (máximo 100).

### Recriar canal que foi deletado

Se um canal for deletado acidentalmente, rode `!setupcanais` novamente. Ele só cria o que não existe — não duplica canais já existentes e não apaga nada.

### Atualizar permissões de canais

Se as permissões de um canal ficarem erradas, a forma mais segura é:
1. Deletar o canal no Discord
2. Rodar `!setupcanais`
3. O canal será recriado com as permissões corretas

### Migrações de banco

O bot cria os índices do MongoDB automaticamente no startup. Nenhuma migração manual é necessária.

### Variáveis de ambiente importantes

| Variável | Descrição |
|---|---|
| `DISCORD_TOKEN` | Token do bot |
| `MONGODB_URI` ou `MONGO_URI` | URI de conexão com o MongoDB |
| `MONGODB_DB_NAME` | Nome do banco (padrão: `x1_bot`) |
| `EFI_CLIENT_ID` | Client ID da Efí Pay |
| `EFI_CLIENT_SECRET` | Client Secret da Efí Pay |
| `EFI_PIX_KEY` | Chave Pix do recebedor |
| `EFI_SANDBOX` | `true` para testes, `false` para produção |
| `WEBHOOK_BASE_URL` | URL pública para receber callbacks da Efí Pay |
| `RENEWAL_PRICE_7D` | Preço do plano de 7 dias (padrão: 10.00) |
| `RENEWAL_PRICE_15D` | Preço do plano de 15 dias (padrão: 18.00) |
| `RENEWAL_PRICE_30D` | Preço do plano de 30 dias (padrão: 25.00) |
| `API_PORT` | Porta do servidor webhook (padrão: 8000) |
| `LOG_LEVEL` | Nível de log: `DEBUG` ou `INFO` |
