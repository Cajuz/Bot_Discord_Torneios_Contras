Relatório de Comandos — Bot X1 Frifas
Repositório: `Cajuz/X1_frifas-Discord_bot`  
Gerado em: 18/04/2026  
Total de Cogs: 11
---
1. Visão Geral
O bot é inicializado em `main.py` e carrega automaticamente os seguintes módulos (cogs):
#	Módulo	Nome do Cog
1	`cogs.admin_cog`	Administração
2	`cogs.mediator_cog`	Mediador
3	`cogs.support_cog`	Suporte
4	`cogs.match_cog`	Partida
5	`cogs.analyst_cog`	Analista
6	`cogs.invite_cog`	Convites
7	`cogs.influencer_cog`	Influencer
8	`cogs.renewal_cog`	Renovação
9	`cogs.thread_pool_cog`	Thread Pool
10	`cogs.renewal_dashboard_cog`	Painel Contratos
11	`cogs.alerts_cog`	Alertas
---
2. Comandos por Cog
2.1 AdminCog — Administração
Responsável pela gestão de mediadores, candidaturas, ajustes de saldo, configuração de canais e ações administrativas gerais.
Comando	Tipo	Permissão	Descrição
`/candidatura`	Slash	Público	Abre modal para candidatura a mediador
`/mediador add`	Slash (grupo)	Administrador	Cadastra novo mediador
`/mediador remove`	Slash (grupo)	Administrador	Remove mediador
`/mediador info`	Slash (grupo)	Administrador	Exibe informações de um mediador
`/mediador listar`	Slash (grupo)	Administrador	Lista todos os mediadores ativos
`/mediador fila`	Slash (grupo)	Administrador	Mostra a fila de mediadores
`/ajustar_saldo`	Slash	Administrador	Adiciona ou subtrai saldo de um usuário
`/ver_saldo`	Slash	Administrador	Consulta saldo de qualquer usuário
`!setup_painel_contratos`	Prefix	Administrador	Cria/atualiza o painel de contratos
`!atualizar_contratos`	Prefix	Administrador	Força atualização dos painéis
`!aprovar`	Prefix	Administrador	Aprova candidatura de mediador pendente
`!rejeitar`	Prefix	Administrador	Rejeita candidatura de mediador pendente
`!setup_renovacao`	Prefix	Administrador	Posta painel fixo no canal de renovação
---
2.2 MediatorCog — Mediador
Gerencia o ciclo de vida do mediador: fila, status, entrada em partidas e encerramento.
Comando	Tipo	Permissão	Descrição
`/entrar`	Slash	Cargo Controller/Mediador	Entra na fila de mediadores disponíveis
`/sair`	Slash	Cargo Controller/Mediador	Sai da fila de mediadores
`/status`	Slash	Cargo Controller/Mediador	Exibe status atual na fila
`/sala`	Slash	Cargo Controller/Mediador	Inicia a partida (muda status para `partida_iniciada`)
`/afk`	Slash	Cargo Controller/Mediador	Marca mediador como AFK
`/voltar`	Slash	Cargo Controller/Mediador	Remove status AFK e retorna à fila
`/fila`	Slash	Público	Mostra fila atual de mediadores
---
2.3 SupportCog — Suporte
Sistema de tickets para suporte ao usuário via canal privado.
Comando	Tipo	Permissão	Descrição
`!chamado`	Prefix	Público	Abre ou lista tickets de suporte do usuário
`/ticket`	Slash	Público	Cria novo ticket de suporte (canal privado)
`/fechar_ticket`	Slash	Cargo Suporte	Fecha um ticket aberto
---
2.4 MatchCog — Partida
Gerencia criação de partidas e o fluxo de X1 (desafio entre dois jogadores).
Comando	Tipo	Permissão	Descrição
`/x1`	Slash	Público	Desafia outro usuário para uma partida
`/cancelar_partida`	Slash	Administrador	Cancela uma partida em andamento
`/partidas`	Slash	Público	Lista partidas ativas do usuário
`!wt red`	Prefix	Cargo Controller/Mediador	Declara time Red como vencedor da partida
`!wt blue`	Prefix	Cargo Controller/Mediador	Declara time Blue como vencedor da partida
---
2.5 AnalystCog — Analista
Dashboard analítico com estatísticas do servidor, partidas e financeiro.
Comando	Tipo	Permissão	Descrição
`/stats`	Slash	Público	Estatísticas gerais do usuário (partidas, saldo)
`/leaderboard`	Slash	Público	Ranking dos jogadores por vitórias
`/stats_servidor`	Slash	Administrador	Estatísticas globais do servidor
`/relatorio_diario`	Slash	Administrador	Relatório financeiro e operacional do dia
`/relatorio_semanal`	Slash	Administrador	Relatório da semana
`!dashboard`	Prefix	Administrador	Posta painel analítico no canal atual
---
2.6 InviteCog — Convites
Rastreamento de convites e monitoramento de rate limits da API do Discord.
Comando	Tipo	Permissão	Descrição
`/convites`	Slash	Público	Exibe total de convites do usuário ou de outro membro
`/top_convites`	Slash	`manage_guild`	Ranking dos membros que mais convidaram
`/ratelimit_stats`	Slash	Administrador	Estatísticas de rate limit da API (período configurável em horas)
Listeners automáticos: `on_member_join` (registra quem convidou), `on_member_remove` (log de saída), `on_invite_create/delete` (atualiza cache).
---
2.7 InfluencerCog — Influencer
Controle e comissionamento de influencers que trazem membros ao servidor.
Comando	Tipo	Permissão	Descrição
`/influencer add`	Slash (grupo)	Administrador	Cadastra influencer com código de invite e comissão
`/influencer remove`	Slash (grupo)	Administrador	Remove influencer e revoga cargo
`/influencer stats`	Slash (grupo)	Público / Admin	Estatísticas de membros trazidos, partidas e comissão
`/influencer faturamento`	Slash (grupo)	Público / Admin	Relatório financeiro de comissão acumulada
`/influencer ranking`	Slash (grupo)	Administrador	Ranking geral dos 10 influencers com mais membros
---
2.8 RenewalCog — Renovação
Renovação automática de licença de mediador via PIX (integração Efí Pay).
Comando	Tipo	Permissão	Descrição
`/renovar`	Slash	Cargo Controller/Mediador/Mediator	Abre modal para renovação de licença (planos 7, 15 ou 30 dias)
`!renovar_mediador`	Prefix	Administrador	Gera cobrança PIX para outro mediador via DM
Tasks automáticas:
`check_expiring` (a cada 12h): avisa mediadores com licença vencendo em D-3 e D-1; notifica licenças já vencidas.
`expire_mediators` (a cada 24h): expira mediadores vencidos, remove cargo Controller e envia DM.
---
2.9 ThreadPoolCog — Pool de Threads
Monitoramento e gerenciamento do pool de threads reutilizáveis para partidas.
Comando	Tipo	Permissão	Descrição
`/thread_pool setup`	Slash (grupo)	Administrador	Posta/atualiza painel de monitoramento no canal atual
`/thread_pool preaquecer`	Slash (grupo)	Administrador	Cria N threads arquivadas no pool (padrão 3, máx 10)
`/thread_pool status`	Slash (grupo)	Administrador	Exibe resumo rápido do pool (ephemeral)
Task automática: `_auto_refresh` (a cada 5 minutos) — atualiza o painel em todos os servidores.
---
2.10 RenewalDashboardCog — Painel de Contratos
Painel financeiro e operacional de contratos de mediadores, atualizado automaticamente.
Comando	Tipo	Permissão	Descrição
`!resumo_financeiro`	Prefix	Administrador	Envia resumo financeiro analítico diretamente no chat
Canais gerenciados:
`#painel-contratos` — embed fixo com resumo financeiro + botões Atualizar e Ver Pendentes.
`#analytics-adm` — dashboard detalhado com métricas semanais e mensais.
Task automática: `auto_refresh` (a cada 6h) — atualiza ambos os painéis automaticamente.
---
2.11 AlertsCog — Alertas
Loop automático de alertas operacionais para o canal `#alertas-adm`.
Recurso	Tipo	Descrição
`alerts_loop`	Task (5 min)	Verifica latência alta, contratos vencendo, fila parada e mediadores AFK prolongado
`send_alert()`	Método público	API interna para outros cogs enviarem alertas manuais para `#alertas-adm`
Verificações automáticas:
Latência do bot acima de 300 ms.
Contratos vencidos ou vencendo em até 3 dias.
Fila de mediadores inativa há mais de 30 minutos.
Mediadores com status AFK há mais de 2 horas.
> Este cog **não expõe comandos de usuário** — funciona exclusivamente como serviço de monitoramento em background.
---
3. Resumo por Tipo de Comando
Tipo	Quantidade
Slash (`/`)	35
Prefix (`!`)	10
Total	45
---
4. Resumo por Nível de Permissão
Permissão	Comandos
Público	`/x1`, `/partidas`, `/convites`, `/stats`, `/leaderboard`, `/fila`, `/status`, `/candidatura`, `/influencer stats`, `/influencer faturamento`
Cargo específico (Mediador/Controller)	`/entrar`, `/sair`, `/sala`, `/afk`, `/voltar`, `/renovar`, `!wt red`, `!wt blue`
`manage_guild`	`/top_convites`
Administrador	Demais comandos
---
5. Fluxo de Partida (Status)
O fluxo atual de uma partida segue os seguintes estados:
```
criado
  └→ aguardando_partida   (mediador entra na thread)
       └→ partida_iniciada  (mediador usa /sala)
            └→ finalizado   (mediador usa !wt red ou !wt blue)
            └→ cancelado    (cancelamento manual)
```
Os comandos envolvidos neste fluxo são:
`/x1` (MatchCog) — cria a partida com status `criado`.
Mediador entra na thread (automático via fila) — status passa para `aguardando_partida`.
`/sala` (MediatorCog) — mediador inicia oficialmente a partida → `partida_iniciada`.
`!wt red` ou `!wt blue` (MatchCog) — declara vencedor → `finalizado`.
---
Relatório gerado automaticamente a partir do código-fonte do repositório `Cajuz/X1_frifas-Discord_bot`.
