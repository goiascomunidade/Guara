# Plano Consolidado: Guara Voice-to-Voice Plugável

## Resumo
Construir o Guara como uma plataforma voice-to-voice open source, com arquitetura por interfaces de domínio e extensibilidade via plugins/ferramentas.
O core será `Python-first`, com foco em uso local `all-in-one` (Docker), integração no-code via MCP/n8n, governança de marketplace, e evolução para autonomia por ferramenta.

## Objetivos de Produto e Qualidade
1. Conversação por voz contínua sem botão/interface obrigatória.
2. Troca de STT/TTS/LLM/tools por configuração, sem reescrever o core.
3. Marketplace de ferramentas com instalação guiada e governança.
4. Latência alvo: `P95 <= 2.0s`.
5. Segurança: LLM não acessa segredos diretamente.
6. Proatividade por ferramenta em modos controlados (`manual`, `agenda`, `autônomo`), com confirmação obrigatória para ações críticas.

## Escopo
1. MVP inclui:
- V2V completo (entrada, orquestração, resposta em voz).
- Ferramentas plugáveis via contrato único.
- MCP/n8n como caminho principal no-code.
- Memória com RAG no MVP.
- Barge-in + endpoint tuning.
2. Fora do MVP:
- Multilíngue amplo (foco inicial em português; inglês depois).
- Tools provider-specific fora do padrão (somente tools standard no MVP).
- Troca automática intra-sessão por incidente (switch será manual por política).

## Arquitetura Base
## 1. Módulos do Core
1. `audio_input`: captura, pré-processamento e VAD.
2. `orchestrator`: estado conversacional, turn-taking, tool routing.
3. `llm_runtime`: chamada LLM + function-calling.
4. `tool_runtime`: execução de ferramentas/plugins.
5. `memory_runtime`: contexto curto + RAG.
6. `safety_runtime`: guardrails e consentimento.
7. `event_bus`: eventos tipados versionados.
8. `telemetry`: logs e métricas locais (opt-in para exportação).

## 2. Interfaces Públicas (POO)
1. `ISTTProvider`
2. `ITTSProvider`
3. `ILLMProvider`
4. `IToolProvider`
5. `IMemoryProvider`
6. `IGuardrail`
7. `ITransport` (áudio/sessão)

## 3. Contrato Universal de Ferramentas
1. `ToolsSchema` universal no core.
2. Adapters de provider transformam o schema universal para formatos nativos.
3. Somente tools standard no MVP.
4. Contrato mínimo de retorno de tool/workflow:
- `message`: texto curto falável.
- `data`: payload estruturado para follow-up.
5. Pós-tool no MVP: `sempre run_llm`.

## 4. Runtime de Tool-Calling
1. Execução paralela com limites por sessão.
2. Fallback para sequencial quando houver dependência declarada entre calls.
3. Política de cancelamento por tool:
- padrão: cancelável em interrupção;
- exceções por policy da ferramenta.
4. Timeout por chamada de tool com falha controlada.
5. Registro de função direta no SDK com schema inferido de assinatura/docstring e validação estrita.

## 5. Integração MCP e No-Code
1. MCP como protocolo principal de integração externa.
2. Suporte a MCP via HTTP streamável e outros transportes necessários.
3. n8n como trilha principal para contribuidores no-code.
4. Descoberta de tools por metadados/manifests e schema de parâmetros.

## 6. Memória e Contexto
1. RAG no MVP.
2. Sumarização automática por threshold híbrido:
- limite de tokens;
- limite de quantidade de mensagens.
3. Resumos persistidos em storage local com abstração para camada RAG.
4. Injeção de contexto relevante por sessão e por perfil de usuário.

## 7. Voz em Tempo Real
1. Barge-in obrigatório.
2. Ajustes de endpointing para reduzir cortes e falsa finalização.
3. Streaming de resposta com controle para manter naturalidade.
4. Estado de sessão mínimo:
- `Listening`, `Thinking`, `Speaking`, `Interrupted`, `ToolRunning`, `Error`.

## 8. Segurança e Governança
1. Modelo “LLM sem segredos”.
2. Segredos ficam no lado de integração/workflow/cofre.
3. Marketplace com validação CI + revisão humana.
4. Política de ações críticas: sempre confirmar.
5. Proatividade por tool:
- `manual`, `agenda`, `autônomo`.
6. Em modo autônomo, ações críticas continuam exigindo confirmação.

## API/Interfaces e Tipos (Mudanças Públicas)
1. `SessionController`
- `start_session`, `push_audio_frame`, `interrupt`, `end_session`.
2. `ToolRouter`
- `resolve_tool`, `execute_tool`, `cancel_tool`, `set_tool_policy`.
3. `PluginLoader`
- `discover`, `validate_manifest`, `load`, `healthcheck`.
4. `ToolManifest` (versionado)
- `tool_id`, `version`, `capabilities`, `input_schema`, `risk_level`, `autonomy_modes`, `compatibility`.
5. `ToolsSchema` universal
- `standard_tools`, metadados versionados.
6. `Event` tipado versionado
- `event_name`, `event_version`, `trace_id`, `session_id`, `payload`.

## Estrutura de Repositório Planejada
1. `core/`
2. `adapters/`
3. `plugins/`
4. `registry/`
5. `policies/`
6. `memory/`
7. `tests/`
8. `docs/architecture/`

## Roadmap de Implementação
1. Fase 0: contratos, event bus tipado, ciclo de sessão, logs locais.
2. Fase 1: V2V reativo, tool-calling paralelo com limites, MCP/n8n, barge-in, guardrails de entrada/saída.
3. Fase 2: marketplace com wizard de instalação (variáveis + credenciais), validação CI e compat matrix.
4. Fase 3: RAG completo + sumarização híbrida persistida.
5. Fase 4: proatividade por tool (`manual/agenda/autônomo`) + confirmação obrigatória para crítico.
6. Fase 5: inglês como segundo idioma.

## Testes e Critérios de Aceite
1. E2E V2V:
- usuário fala, agente responde por voz sem UI manual.
2. Interrupção:
- barge-in interrompe fala e retoma contexto corretamente.
3. Tools:
- execução paralela limitada;
- cancelamento por policy;
- timeout controlado;
- retorno `message + data`.
4. MCP/n8n:
- descoberta de tools;
- execução de workflow;
- instalação via wizard.
5. Memória:
- recuperação RAG;
- sumarização por tokens/mensagens;
- persistência local.
6. Segurança:
- LLM sem acesso a segredos;
- confirmação obrigatória para ação crítica;
- trilha de auditoria por ação.
7. Compatibilidade:
- validação de manifesto com SemVer + matrix.
8. Performance:
- prova de `P95 <= 2.0s` em cenário de referência do MVP.

## Operação e Observabilidade
1. Telemetria `opt-in` e `local-first`.
2. Base operacional no MVP: logs estruturados.
3. Eventos internos tipados versionados para rastreio/replay.
4. Sem observer bus avançado no MVP (decisão explícita).

## Assumptions e Defaults
1. Linguagem principal: Python.
2. Deploy inicial: local all-in-one com Docker.
3. Idioma inicial: português; inglês em fase posterior.
4. Runtime switch entre providers: manual por política, não automático.
5. Tools provider-specific: fora do MVP.
6. Marketplace comunitário com revisão obrigatória.
7. Output de tools sem `output_filter` dedicado no MVP (confiando nas tools).
8. Risco aceito: ausência de filtro mínimo global de saída pode elevar chance de resposta ruidosa/sensível.
