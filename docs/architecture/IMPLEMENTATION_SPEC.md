# Guara Implementation Spec (Decision-Complete)

Version: `1.0`  
Status: `authoritative handoff spec`  
Audience: engenharia, mantenedores de plugin, contribuidores no-code, revisores de arquitetura.

---

## 1. Objetivo deste documento
Este documento define, com precisao de implementacao, o que foi decidido para o Guara e como implementar cada parte sem depender de contexto de conversa.

Este spec cobre:
1. decisoes de produto e arquitetura travadas.
2. contratos tecnicos (tipos, APIs, protocolos, fluxos).
3. estado atual implementado no repositorio.
4. backlog faseado com Definition of Done (DoD) e criterios de aceite.

Este spec NAO e substituido por README de alto nivel. Este e o documento de handoff.

---

## 2. Decisoes travadas (nao abertas)
As decisoes abaixo estao fechadas e devem ser tratadas como constraints:

| ID | Decisao | Valor travado |
|---|---|---|
| D-001 | Core language | Python-first |
| D-002 | Deploy inicial | all-in-one local (Docker-friendly) |
| D-003 | Ferramentas | contrato unico + adapters MCP |
| D-004 | No-code | prioridade alta no MVP via MCP/n8n |
| D-005 | Tool execution | paralelo com limites por sessao |
| D-006 | Cancelamento em barge-in | por tool, default = cancelar |
| D-007 | Pos-tool | sempre run_llm |
| D-008 | Tool response contract | `message + data` |
| D-009 | Seguranca de credenciais | LLM sem segredos |
| D-010 | Governanca marketplace | validacao CI + revisao humana |
| D-011 | Proatividade por ferramenta | `manual`, `agenda`, `autonomo` |
| D-012 | Acao critica | sempre confirmar |
| D-013 | Eventos internos | tipados e versionados |
| D-014 | Telemetria | local-first e opt-in |
| D-015 | Compatibilidade plugin | SemVer + compat matrix |
| D-016 | Switching de provider | manual por politica |
| D-017 | Provider custom tools | somente standard no MVP |
| D-018 | Idioma | foco inicial PT, EN depois |
| D-019 | Latencia alvo | P95 <= 2.0s |
| D-020 | Summarization trigger | hibrido (tokens + mensagens) |

Decisoes de risco aceito no MVP:
1. sem output_filter dedicado por tool.
2. sem observer bus avancado alem de logs/event store basico.

---

## 2.1 Requisitos funcionais (RF)
Os requisitos abaixo sao obrigatorios para o produto.

### RF-001 Sessao de voz
O sistema deve permitir criar, manter, interromper e encerrar sessoes de voz.

### RF-002 Turno por texto e audio
O sistema deve aceitar turnos por texto e por audio (base64), com transcricao quando necessario.

### RF-003 Resposta em voz
Toda resposta de assistente deve poder ser convertida para audio (TTS).

### RF-004 Barge-in
O usuario deve conseguir interromper o assistente em tempo de execucao, cancelando chamadas interruptiveis.

### RF-005 Ferramentas plugaveis
O sistema deve suportar registro e execucao de ferramentas por contrato unico.

### RF-006 Tool-calling paralelo
O runtime deve executar chamadas de ferramenta em paralelo com limite configuravel por sessao.

### RF-007 Politica por ferramenta
Cada ferramenta deve ter politica de timeout e cancelamento por interrupcao.

### RF-008 Integracao MCP
O sistema deve permitir descoberta e registro dinamico de ferramentas de servidores MCP.

### RF-009 Streaming incremental
O sistema deve expor eventos incrementais de turno (chunks de texto/audio) por JSON stream e SSE.

### RF-010 Transporte realtime
O sistema deve oferecer manager bidirecional para WebSocket com protocolo de mensagens cliente/servidor.

### RF-011 Troca manual de provider
O sistema deve permitir trocar provider ativo de STT/TTS/LLM sem reiniciar processo.

### RF-012 Telemetria local
Eventos internos tipados devem ser armazenados localmente e consultaveis via API.

### RF-013 Guardrails basicos
Input e output devem passar por validacao minima de seguranca.

### RF-014 Compatibilidade de plugins
Manifesto de plugin deve ser validado com SemVer e compatibilidade do core.

### RF-015 Contrato de retorno de tool
Ferramenta deve retornar payload compativel com `message + data`.

### RF-016 Acoes criticas
Acoes marcadas como criticas devem exigir confirmacao explicita.

---

## 2.2 Requisitos nao funcionais (RNF)
### RNF-001 Latencia
Meta de produto: `P95 <= 2.0s` em ambiente de referencia para turno comum.

### RNF-002 Confiabilidade
Falhas de tool-call devem degradar com erro controlado (sem derrubar sessao).

### RNF-003 Observabilidade
Toda etapa principal deve emitir evento tipado versionado com `trace_id`.

### RNF-004 Extensibilidade
Novos providers e tools devem ser adicionados sem alterar contratos centrais.

### RNF-005 Portabilidade
Stack inicial deve rodar localmente com dependencias minimas.

### RNF-006 Seguranca operacional
Credenciais nao devem ser expostas ao modelo de linguagem.

### RNF-007 Compatibilidade
Mudancas breaking de contrato devem seguir SemVer major.

---

## 2.3 Historias de usuario (US)
Formato: "Como <persona>, eu quero <objetivo>, para <valor>".

### US-001 Conversa continua por voz
Como usuario final, eu quero falar com o agente e receber resposta em voz sem botao, para interagir de forma natural.
Aceite:
1. Sessao inicia e responde por voz em um turno valido.
2. Funciona com input texto e audio.

### US-002 Interromper resposta do agente
Como usuario final, eu quero interromper o agente quando ele estiver falando, para retomar controle da conversa.
Aceite:
1. Interrupcao muda estado da sessao para listening.
2. Tool-calls cancelaveis sao interrompidos.

### US-003 Plugar ferramenta sem mexer no core
Como desenvolvedor de plugin, eu quero registrar uma ferramenta via contrato, para extender capacidades sem alterar runtime central.
Aceite:
1. Ferramenta registrada aparece em `GET /tools`.
2. Ferramenta pode ser chamada via turno.

### US-004 Integrar ferramenta no-code
Como colaborador no-code, eu quero publicar/usar ferramentas via MCP/n8n, para contribuir sem programar backend.
Aceite:
1. Registro MCP via endpoint funciona.
2. Tool descoberta e executavel no fluxo normal.

### US-005 Trocar provider em runtime
Como operador, eu quero trocar STT/TTS/LLM ativo manualmente, para controlar custo/latencia/qualidade.
Aceite:
1. `POST /providers/switch` atualiza provider ativo.
2. Proximos turnos refletem novo provider.

### US-006 Consumir stream em tempo real
Como cliente frontend/mobile, eu quero receber chunks incrementais de resposta, para reduzir latencia percebida.
Aceite:
1. `turn-stream` retorna eventos chunkados.
2. `turn-stream-sse` envia eventos incrementais no formato SSE.

### US-007 Consumir canal bidirecional
Como cliente realtime, eu quero enviar turnos e receber eventos no mesmo canal, para UX de baixa latencia.
Aceite:
1. Canal abre e envia `channel_opened`.
2. Mensagens `text_turn`/`audio_turn` geram eventos de stream ate `stream_done`.

### US-008 Auditar comportamento do sistema
Como mantenedor, eu quero consultar eventos internos por sessao e tipo, para debugar falhas e monitorar operacao.
Aceite:
1. `GET /events` filtra por `session_id` e `event_name`.
2. Eventos incluem `trace_id` e `event_version`.

### US-009 Garantir compatibilidade de plugin
Como mantenedor de ecossistema, eu quero validar manifesto e compatibilidade do plugin, para evitar quebra em runtime.
Aceite:
1. Versao invalida falha na validacao.
2. Plugin incompativel com core e rejeitado.

### US-010 Proatividade segura
Como usuario dono da automacao, eu quero definir modo manual/agenda/autonomo por ferramenta, para controlar nivel de autonomia.
Aceite:
1. Modo por ferramenta e configuravel.
2. Acao critica exige confirmacao independente do modo.

### US-011 Robustez em ruido
Como usuario em ambiente ruidoso, eu quero que o agente mantenha boa compreensao de fala, para evitar repeticoes.
Aceite:
1. Pipeline aplica supressao de ruido antes do STT.
2. Em teste com ruido moderado, taxa de erro nao degrada acima do limite definido em RNF.

### US-012 Foco no locutor ativo
Como usuario em ambiente com varias vozes, eu quero que o sistema priorize minha fala, para evitar comandos indevidos.
Aceite:
1. Entrada com diarizacao/selecao de speaker configuravel.
2. Comando de speaker nao autorizado e rejeitado para acoes sensiveis.

### US-013 Turn-taking natural
Como usuario, eu quero que o agente detecte pausas curtas sem encerrar meu turno, para nao cortar minha frase.
Aceite:
1. Detector diferencia pausa curta vs fim de turno.
2. Encerramento prematuro fica abaixo da meta de qualidade.

### US-014 Latencia especulativa
Como usuario, eu quero respostas com menor latencia percebida, para interacao fluida.
Aceite:
1. Orquestrador permite prefetch/execucao especulativa configuravel.
2. Metrica P95 de latencia percebida melhora vs modo nao especulativo.

### US-015 Fallback resiliente
Como operador, eu quero fallback entre providers em falha/incidente, para manter disponibilidade.
Aceite:
1. Politica de fallback por erro/timeout esta configurada.
2. Sessao continua com degradacao controlada e evento auditavel.

### US-016 Roteamento por custo/qualidade
Como operador, eu quero rotear requisicoes por intencao, custo e latencia, para otimizar operacao.
Aceite:
1. Regras de roteamento escolhem provider/modelo por policy.
2. Decisao de roteamento e registrada em telemetria.

### US-017 Personalidade configuravel
Como dono de produto, eu quero ajustar tom/persona do agente por contexto, para experiencia consistente.
Aceite:
1. Perfil de personalidade e aplicado por sessao/canal.
2. Mudanca de perfil nao exige alterar core.

### US-018 Multi-agent interno
Como usuario de tarefas complexas, eu quero que subagentes colaborem internamente, para respostas melhores.
Aceite:
1. Fluxo suporta papeis (researcher/critic/writer) configuraveis.
2. Resposta final registra trilha resumida de raciocinio operacional.

### US-019 Confirmacao humana em acoes criticas
Como usuario, eu quero confirmar explicitamente acoes sensiveis, para reduzir risco.
Aceite:
1. Tool marcada como critica sempre exige confirmacao.
2. Sem confirmacao valida, execucao nao ocorre.

### US-020 Execucao transacional com compensacao
Como operador, eu quero rollback/compensacao em falhas parciais, para evitar inconsistencias.
Aceite:
1. Plano de compensacao por tool pode ser definido.
2. Falha intermediaria dispara compensacao e gera evento de auditoria.

### US-021 Speech-to-Speech nativo opcional
Como usuario, eu quero modo audio->audio quando disponivel, para maior naturalidade.
Aceite:
1. Runtime suporta provider S2S sem quebrar contratos atuais.
2. Fallback STT->LLM->TTS funciona automaticamente quando S2S indisponivel.

### US-022 Prosodia controlada
Como designer conversacional, eu quero controlar pausas e enfase, para fala menos robotica.
Aceite:
1. Camada de saida aceita marcacoes de prosodia (ex.: SSML/policy).
2. Provider sem suporte aplica degradacao segura sem erro fatal.

### US-023 Memoria de preferencias do usuario
Como usuario recorrente, eu quero que o agente lembre preferencias, para interacoes personalizadas.
Aceite:
1. Perfil (preferencias/restricoes) e persistido por usuario.
2. Recuperacao de perfil respeita consentimento e politicas de privacidade.

### US-024 Resumo automatico de historico
Como sistema, eu quero sumarizar historico antigo, para reduzir custo de contexto.
Aceite:
1. Summarization dispara por thresholds definidos.
2. Resumo e versionado e reaproveitado em turnos futuros.

### US-025 Memoria hibrida (vetor + grafo)
Como agente, eu quero combinar busca semantica e relacional, para respostas mais precisas.
Aceite:
1. Consulta ao contexto suporta vetor e grafo no mesmo fluxo.
2. Politica de merge/ranking de memoria e configuravel.

### US-026 Guardrails de entrada e saida
Como responsavel por seguranca, eu quero filtrar entrada/saida, para prevenir abuso e vazamento.
Aceite:
1. Input guardrail bloqueia jailbreak/padroes proibidos.
2. Output guardrail bloqueia toxicidade/PII com trilha auditavel.

### US-027 Verificacao de locutor
Como usuario com conta sensivel, eu quero verificar identidade por voz em comandos criticos, para autorizacao forte.
Aceite:
1. Comando sensivel exige score minimo de verificacao.
2. Falha de verificacao impede execucao e registra evento.

### US-028 Analytics operacional
Como product owner, eu quero dashboard de intents, latencia e custo, para melhoria continua.
Aceite:
1. Eventos alimentam metricas agregadas por sessao/canal/tool.
2. Consultas principais (falhas, P95, custo) ficam disponiveis por periodo.

### US-029 Sentimento em tempo real
Como sistema, eu quero detectar frustracao do usuario, para ajustar estrategia de resposta.
Aceite:
1. Pipeline gera sinal de sentimento por turno.
2. Politica pode reduzir verbosidade/escalar para humano quando necessario.

### US-030 Feedback loop de qualidade
Como usuario, eu quero avaliar respostas, para o agente melhorar ao longo do tempo.
Aceite:
1. API aceita feedback explicito por resposta/tool-call.
2. Feedback entra em fila de melhoria com rastreabilidade.

---

## 2.4 Matriz de rastreabilidade (US -> RF)
| User Story | Requisitos cobertos |
|---|---|
| US-001 | RF-001, RF-002, RF-003 |
| US-002 | RF-004, RF-007 |
| US-003 | RF-005, RF-007, RF-015 |
| US-004 | RF-008, RF-005 |
| US-005 | RF-011 |
| US-006 | RF-009 |
| US-007 | RF-010, RF-009 |
| US-008 | RF-012 |
| US-009 | RF-014 |
| US-010 | RF-016 |

---

## 2.5 Priorizacao (MoSCoW) para execucao
Legenda:
1. `Must`: obrigatorio para declarar MVP funcional.
2. `Should`: importante para MVP+ (curto prazo), pode entrar apos baseline.
3. `Could`: desejavel para fases seguintes.

### Priorizacao dos requisitos funcionais
| RF | Prioridade | Target | Justificativa |
|---|---|---|---|
| RF-001 | Must | MVP-R1 | Sem sessao nao existe agente operacional. |
| RF-002 | Must | MVP-R1 | Entrada texto/audio e base do produto. |
| RF-003 | Must | MVP-R1 | Resposta em voz e proposta central V2V. |
| RF-004 | Must | MVP-R1 | Barge-in e requisito de UX natural. |
| RF-005 | Must | MVP-R1 | Extensibilidade por tools e pilar do Guara. |
| RF-006 | Must | MVP-R1 | Decisao travada de execucao paralela com limite. |
| RF-007 | Must | MVP-R1 | Controle de timeout/cancelamento por tool e essencial para robustez. |
| RF-008 | Must | MVP-R1 | MCP/n8n e trilha principal no-code decidida. |
| RF-009 | Must | MVP-R1 | Streaming incremental reduz latencia percebida. |
| RF-010 | Should | MVP-R2 | WebSocket bidirecional melhora UX realtime, mas SSE ja cobre baseline. |
| RF-011 | Must | MVP-R1 | Troca manual de provider e decisao fechada. |
| RF-012 | Must | MVP-R1 | Telemetria local e essencial para operacao/debug. |
| RF-013 | Must | MVP-R1 | Guardrail minimo para seguranca operacional. |
| RF-014 | Must | MVP-R1 | Compatibilidade de plugin evita quebra do ecossistema. |
| RF-015 | Must | MVP-R1 | Contrato `message+data` e base de follow-up confiavel. |
| RF-016 | Should | MVP-R2 | Confirmacao de acao critica e hardening de seguranca. |

### Priorizacao das historias de usuario
| US | Prioridade | Target | Justificativa |
|---|---|---|---|
| US-001 | Must | MVP-R1 | Entrega valor principal ao usuario final. |
| US-002 | Must | MVP-R1 | Interrupcao e controle conversacional obrigatorios. |
| US-003 | Must | MVP-R1 | Permite evolucao comunitaria sem mexer no core. |
| US-004 | Must | MVP-R1 | Habilita contribuicao no-code via MCP/n8n. |
| US-005 | Must | MVP-R1 | Necessario para operacao por politica manual. |
| US-006 | Must | MVP-R1 | Streaming reduz latencia percebida no frontend/mobile. |
| US-007 | Should | MVP-R2 | Canal full-duplex otimiza UX realtime apos baseline. |
| US-008 | Must | MVP-R1 | Observabilidade e suporte operacional. |
| US-009 | Must | MVP-R1 | Saude do ecossistema de plugins. |
| US-010 | Should | MVP-R3 | Proatividade segura depende de policy engine completo. |
| US-011 | Should | MVP-R2 | Qualidade de reconhecimento em ambiente real. |
| US-012 | Should | MVP-R2 | Reduz falsos positivos de comando em multi-speaker. |
| US-013 | Should | MVP-R2 | Melhora naturalidade conversacional e reduz cortes. |
| US-014 | Should | MVP-R2 | Diminui latencia percebida no dialogo. |
| US-015 | Must | MVP-R2 | Resiliencia operacional sob falhas de provider. |
| US-016 | Should | MVP-R2 | Otimiza custo/latencia/qualidade por policy. |
| US-017 | Could | MVP-R3 | Diferenciacao de experiencia por persona. |
| US-018 | Could | MVP-R3 | Ganho de qualidade em tarefas complexas. |
| US-019 | Must | MVP-R2 | Controle de risco em acoes sensiveis. |
| US-020 | Should | MVP-R3 | Consistencia transacional em workflows de tools. |
| US-021 | Could | MVP-R3 | Aumenta naturalidade quando stack suportar S2S. |
| US-022 | Could | MVP-R3 | Melhora expressividade da voz sintetizada. |
| US-023 | Should | MVP-R2 | Personalizacao de uso recorrente. |
| US-024 | Should | MVP-R2 | Reduz custo de contexto mantendo continuidade. |
| US-025 | Could | MVP-R3 | Precisao maior com memoria hibrida. |
| US-026 | Must | MVP-R2 | Seguranca minima de entrada/saida para escala. |
| US-027 | Could | MVP-R3 | Reforco de autenticacao para comandos criticos. |
| US-028 | Should | MVP-R2 | Direciona melhoria por metricas operacionais. |
| US-029 | Could | MVP-R3 | Adapta estrategia de resposta a emocao do usuario. |
| US-030 | Should | MVP-R2 | Fecha ciclo de qualidade com feedback explicito. |

### Gate de release por prioridade
1. `MVP-R1`: todos os itens `Must` de RF e US entregues e testados.
2. `MVP-R2`: itens `Should` de infraestrutura/realtime/seguranca curta.
3. `MVP-R3`: autonomia e proatividade com politicas completas.

---

## 3. Estado atual implementado (source of truth no codigo)
### 3.1 Nucleo
1. `core/contracts.py`: interfaces `ISTTProvider`, `ITTSProvider`, `ILLMProvider`, `IToolProvider`, `IMemoryProvider`, `IGuardrail`.
2. `core/tools.py`: `FunctionSchema`, `ToolsSchema`, `ToolSpec`, `ToolCall`, `ToolExecutionContext`, `ToolExecutionResult`.
3. `core/tool_runtime.py`: `ToolRouter` com paralelismo limitado, dependencia entre calls, timeout e cancelamento por politica.
4. `core/session.py`: `SessionController` com ciclo de sessao e interrupcao.
5. `core/events.py`: event bus tipado/versionado.
6. `core/provider_registry.py`: registro e switch manual de STT/TTS/LLM.
7. `core/streaming.py`: chunking de texto para streaming TTS.
8. `core/manifest.py`: validacao de manifesto e compatibilidade SemVer.
9. `core/summarizer.py`: gatilho e formato de sumarizacao.
10. `core/memory.py`: memoria local TTL.
11. `core/telemetry.py`: event store local.

### 3.2 Adapters e runtime
1. `adapters/stt_local.py`, `adapters/tts_local.py`, `adapters/llm_rule_based.py`, `adapters/guardrail_basic.py`.
2. `adapters/mcp_http.py`, `adapters/mcp_tool_provider.py`.
3. `runtime/app.py`: composicao principal, APIs de turn, stream, providers, MCP e eventos.
4. `runtime/http_server.py`: API HTTP + SSE.
5. `runtime/realtime.py`: manager bidirecional para canal realtime.
6. `runtime/websocket_server.py`, `runtime/ws_main.py`: transporte websocket opcional.

### 3.3 Testes
Cobertura atual via `unittest`, incluindo:
1. contratos de evento.
2. runtime de tools.
3. sessao/interrupcao.
4. plugin SDK/manifest.
5. MCP integration (mocked RPC).
6. streaming e realtime manager.

---

## 4. Contratos tecnicos obrigatorios
## 4.1 Tool response contract
Toda ferramenta deve retornar estrutura que permita:
1. resposta falavel curta.
2. payload estruturado para follow-up.

Formato recomendado:
```json
{
  "message": "Resumo falavel em linguagem natural",
  "data": { "qualquer": "payload estruturado" }
}
```

## 4.2 Tool call policy
Por ferramenta:
1. `cancel_on_interruption: bool` (default `true`).
2. `timeout_seconds: float` (default `10.0`).

## 4.3 Plugin manifest (obrigatorio)
Campos minimos:
1. `tool_id`
2. `name`
3. `version` (SemVer)
4. `description`
5. `capabilities` (nao vazio)
6. `input_schema`
7. `output_schema`
8. `compatibility.guara_core` (recomendado)

## 4.4 Provider kinds suportados
Kinds aceitos:
1. `stt`
2. `tts`
3. `llm`

Switch de provider deve ser manual e explicito.

---

## 5. Fluxos de execucao (detalhe operacional)
## 5.1 Fluxo text turn (sincrono)
1. Validar sessao.
2. Criar `turn_id` (`SessionController.push_audio_frame`).
3. `Orchestrator.handle_user_text`:
   1. input guardrail.
   2. chamada LLM.
   3. extração de tool calls.
   4. execucao no `ToolRouter`.
   5. output guardrail.
4. Marcar `speaking`.
5. TTS da resposta final.
6. Completar turno.
7. Retornar `turn_id`, `reply_text`, `audio_base64`, `tool_results`.

## 5.2 Fluxo audio turn
1. STT (`transcribe`).
2. Reusar fluxo de text turn com transcript.
3. Retornar transcript no payload.

## 5.3 Fluxo streaming (JSON em lote)
1. Inicia turno.
2. Divide resposta em chunks (`split_text_for_streaming`).
3. Emite eventos em ordem:
   1. `turn_started`
   2. `llm_chunk`/`tts_chunk` (N vezes)
   3. `tool_result` (0..N)
   4. `turn_completed`
4. Fecha turno.

## 5.4 Fluxo streaming realtime (SSE/WS)
Mesmo contrato de eventos do item 5.3, so que enviados incrementalmente.

## 5.5 Fluxo barge-in
1. `interrupt_session` chama `ToolRouter.cancel_interruptible_calls`.
2. Publica evento `barge_in` com `cancelled_calls`.
3. Sessao volta para estado `listening`.

---

## 6. API HTTP (normativa)
Base atual: `runtime/http_server.py`

## 6.1 Endpoints de saude e introspeccao
1. `GET /health`
2. `GET /tools`
3. `GET /providers`
4. `GET /events?limit=100&event_name=<name>&session_id=<id>`

## 6.2 Sessao
1. `POST /sessions/start`
2. `POST /sessions/{session_id}/end`
3. `POST /sessions/{session_id}/interrupt`

## 6.3 Turnos
1. `POST /sessions/{session_id}/turn`
   1. body text: `{ "text": "..." }`
   2. body audio: `{ "audio_base64": "...", "language": "pt-BR" }`
2. `POST /sessions/{session_id}/turn-stream`
   1. text or audio, com `max_chunk_chars`.
3. `GET /sessions/{session_id}/turn-stream-sse`
   1. query `text=...` ou `audio_base64=...`
   2. opcional `language`, `max_chunk_chars`.

## 6.4 Providers
1. `POST /providers/switch`
```json
{ "kind": "llm", "name": "rule-based" }
```

## 6.5 MCP tools
1. `POST /tools/register-mcp`
```json
{
  "server_url": "http://host:port/mcp",
  "auth_token": "optional",
  "allowlist": ["tool_a", "tool_b"],
  "timeout_seconds": 5.0,
  "policy": {
    "cancel_on_interruption": true,
    "timeout_seconds": 10.0
  }
}
```

---

## 7. Protocolo de eventos de stream
## 7.1 Eventos de stream (payload externo)
Tipos:
1. `transcript`
2. `turn_started`
3. `llm_chunk`
4. `tts_chunk`
5. `tool_result`
6. `turn_completed`
7. `stream_done` (realtime manager)
8. `stream_cancelled` (realtime manager)
9. `error` (realtime manager)

Campos principais:
1. `turn_started`: `{ "turn_id", "reply_text" }`
2. `llm_chunk`: `{ "index", "text" }`
3. `tts_chunk`: `{ "index", "audio_base64" }`
4. `tool_result`: `{ "result": ToolExecutionResult }`
5. `transcript`: `{ "text" }`

## 7.2 SSE framing
Formato:
```text
event: <type>
data: <json>

```

---

## 8. Protocolo WebSocket (normativo)
Path: `/ws/{session_id}`  
Server side: `runtime/realtime.py` + `runtime/websocket_server.py`

## 8.1 Mensagens cliente -> servidor
1. `text_turn`
```json
{ "type": "text_turn", "text": "...", "max_chunk_chars": 120 }
```
2. `audio_turn`
```json
{ "type": "audio_turn", "audio_base64": "...", "language": "pt-BR", "max_chunk_chars": 120 }
```
3. `interrupt`
```json
{ "type": "interrupt" }
```
4. `end`
```json
{ "type": "end" }
```

## 8.2 Mensagens servidor -> cliente
1. Eventos de stream do item 7.
2. Eventos de canal:
   1. `channel_opened`
   2. `channel_closed`
   3. `session_ended`
   4. `interrupt_result`
   5. `error`

## 8.3 Regra de concorrencia
Apenas um turno ativo por canal.  
Se cliente enviar novo turno durante stream ativo: emitir `error: turn_in_progress`.

---

## 9. Eventos internos tipados (event bus)
Eventos internos versionados (`event_version=1`):
1. `turn_started`
2. `tool_called`
3. `tts_started`
4. `barge_in`
5. `turn_completed`
6. `turn_failed`
7. `provider_switched`

Formato comum:
```json
{
  "event_name": "turn_started",
  "event_version": 1,
  "trace_id": "uuid",
  "session_id": "id-or-null",
  "created_at": "iso-8601",
  "payload": { "..." : "..." }
}
```

---

## 10. Seguranca e guardrails
## 10.1 Fronteiras
1. LLM nao deve receber segredo de credenciais.
2. Integracoes externas (MCP/n8n) devem isolar credenciais.
3. Acoes criticas exigem confirmacao.

## 10.2 Guardrail baseline
1. Input guardrail ativo (padroes proibidos basicos).
2. Output guardrail ativo (padroes proibidos + tamanho maximo).

## 10.3 Risco explicitamente aceito no MVP
1. sem output_filter dedicado por tool.
2. confianca maior na higiene de resposta da tool.

---

## 11. Politica de compatibilidade e versionamento
1. Core versionado em SemVer.
2. Plugin manifesto com `compatibility.guara_core`.
3. Loader rejeita plugin incompatível com versao ativa.
4. Mudanca breaking de contrato exige incremento major.

---

## 12. Testes obrigatorios para cada PR
Cada PR que altere runtime/contratos deve incluir:
1. teste de sucesso principal.
2. teste de erro/edge case.
3. teste de regressao para comportamento sensivel alterado.

Suite minima que deve continuar verde:
```bash
python3 -m unittest discover -s tests -v
```

---

## 13. Backlog implementavel por fase (com DoD)
## Fase A - Hardening realtime (proxima)
Escopo:
1. heartbeat/ping no WS.
2. auth por token de sessao para HTTP/SSE/WS.
3. backpressure e limite de fila por canal.
4. timeout de stream por turno.

DoD:
1. protocolo documentado em `docs/architecture`.
2. testes para timeout, auth fail, backpressure.
3. sem regressao na suite atual.

## Fase B - Memoria RAG real
Escopo:
1. implementar `IMemoryProvider` vetorial real.
2. injecao de contexto por relevancia.
3. sumarizacao persistida e reutilizada por sessao/perfil.

DoD:
1. provider default selecionavel via registry.
2. teste e2e com recuperacao de contexto em turno futuro.
3. benchmark basico de latencia e custo de token.

## Fase C - Marketplace operacional
Escopo:
1. formato definitivo de indice de ferramentas.
2. pipeline CI para validacao de manifesto/schema/seguranca.
3. fluxo de aprovacao humana e status.

DoD:
1. endpoint/CLI para listar e instalar ferramentas do registry.
2. instalacao com wizard de variaveis/credenciais.
3. teste de rejeicao para manifesto invalido/incompativel.

## Fase D - Proatividade controlada
Escopo:
1. scheduler por ferramenta (`manual|agenda|autonomo`).
2. enforce de confirmacao para acao critica.
3. trilha de auditoria das decisoes autonomas.

DoD:
1. policy engine com regras por ferramenta.
2. testes de bloqueio de acao critica sem confirmacao.
3. logs/auditoria com trace_id e decisao registrada.

## Fase E - Provider integrations reais
Escopo:
1. STT/TTS/LLM cloud/local produtivos.
2. fallback por politica manual e defaults por perfil.
3. qualidade de voz e latencia medida.

DoD:
1. providers selecionaveis via `/providers/switch`.
2. testes integrados com mocks e smoke real opcional.
3. relatorio de P95 em ambiente de referencia.

---

## 14. Criterios de aceite globais (release gate)
Uma release MVP deve cumprir:
1. V2V funcional em fluxo continuo sem botao.
2. tool-calling com paralelismo controlado e cancelamento por policy.
3. MCP registration e execucao de tool externa funcional.
4. SSE ou WS entregando eventos incrementais de turno.
5. eventos internos persistidos localmente e consultaveis.
6. testes automatizados verdes.
7. nenhuma quebra de contrato publico sem migration note.

---

## 15. Checklist de handoff para novo implementador
Antes de codar:
1. ler este arquivo por completo.
2. ler `docs/architecture/MASTER_PLAN.md`.
3. rodar suite de testes.

Durante implementacao:
1. nao quebrar contratos de `core/contracts.py`.
2. manter eventos tipados/versionados.
3. adicionar testes para novos fluxos.

Antes de abrir PR:
1. executar `python3 -m unittest discover -s tests -v`.
2. atualizar `README.md` e docs de arquitetura se API/protocolo mudou.
3. descrever impacto de compatibilidade (plugins/providers/tools).

---

## 16. Escopo explicitamente fora desta versao
1. autoscaling multi-tenant em cloud.
2. politicas complexas de RLHF online.
3. clone de voz e biometria produtiva.
4. filtros de output por ferramenta (alem do guardrail basico).
5. provider custom tools fora do contrato standard.
