# Guia de Contribuição — Guara

Obrigado por querer contribuir com o Guara! Este documento explica como participar de forma organizada e produtiva.

---

## Visão geral do projeto

O Guara é uma plataforma open source de agente voice-to-voice plugável. O core é Python-first, com deploy local all-in-one (Docker-friendly) e extensibilidade via plugins e MCP/n8n.

Antes de contribuir, leia:

- [`README.md`](README.md) — visão geral e comandos de desenvolvimento.
- [`docs/architecture/MASTER_PLAN.md`](docs/architecture/MASTER_PLAN.md) — plano de produto e arquitetura.
- [`docs/architecture/IMPLEMENTATION_SPEC.md`](docs/architecture/IMPLEMENTATION_SPEC.md) — spec técnico com decisões travadas, contratos e backlog.

---

## Estrutura do repositório

```
core/           Contratos, event bus, sessão, orchestrator, tool runtime
adapters/       Implementações de providers (STT, TTS, LLM, guardrail, MCP)
plugins/        Plugin SDK e exemplos
runtime/        Composição principal, servidor HTTP, WebSocket realtime
policies/       Valores default de políticas
memory/         Namespace de memória (RAG futuro)
registry/       Namespace de registry de ferramentas
tests/          Testes unitários e de integração
docs/           Arquitetura, planos e decisões
```

Regra: `core/foo.py` deve ter testes em `tests/test_foo.py`.

---

## Configuração do ambiente

### Pré-requisitos

- Python 3.11+
- Git

### Setup local

```bash
git clone git@github.com:goiascomunidade/Guara.git
cd Guara
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Rodar testes

```bash
python3 -m unittest discover -s tests -v
```

Todos os testes devem passar antes de abrir PR. A suite atual tem 29 testes cobrindo event bus, tool runtime, sessão, plugin SDK, MCP, streaming, summarizer, runtime app e realtime manager.

### Rodar servidor HTTP (desenvolvimento)

```bash
python3 -m runtime.main --host 0.0.0.0 --port 8080
```

### Rodar servidor WebSocket (desenvolvimento)

```bash
python3 -m runtime.ws_main --host 0.0.0.0 --port 8765
```

---

## Fluxo de contribuição

### 1. Escolha ou crie uma issue

- Verifique as issues abertas antes de começar.
- Para features novas ou mudanças grandes, abra uma issue para discussão antes de codar.
- Issues com label `good first issue` são boas para começar.

### 2. Crie uma branch

```bash
git checkout -b tipo/descricao-curta
```

Convenção de nomes:

| Prefixo | Uso |
|---|---|
| `feat/` | Nova funcionalidade |
| `fix/` | Correção de bug |
| `docs/` | Documentação |
| `refactor/` | Reestruturação sem mudar comportamento |
| `test/` | Adição ou melhoria de testes |
| `chore/` | Manutenção, CI, configs |

### 3. Desenvolva

- Siga os padrões de código descritos abaixo.
- Adicione testes para código novo.
- Rode `python3 -m unittest discover -s tests -v` frequentemente.

### 4. Faça commits focados

Formato: linha imperativa e concisa em inglês.

```
feat: add heartbeat to WebSocket transport
fix: prevent race condition in channel close
docs: update API endpoint reference
test: add edge case for tool timeout
```

Regras:
- Um commit = uma mudança lógica.
- Não misture refatoração com feature nova no mesmo commit.
- Não commite arquivos com segredos (API keys, `.env`, credentials).

### 5. Abra um Pull Request

- Faça push da branch e abra PR contra `main`.
- O template de PR será preenchido automaticamente — preencha todos os campos.
- Vincule a issue com `Closes #N`.
- Aguarde revisão; responda aos comentários.

---

## Padrões de código

### Estilo geral

- `snake_case` para arquivos, diretórios, funções e variáveis.
- `PascalCase` para classes.
- `UPPER_SNAKE_CASE` para constantes.
- Nomes descritivos: `session_controller`, não `sc`.
- Módulos pequenos com responsabilidade única.
- Sem comentários óbvios. Comente apenas lógica não-trivial, trade-offs e constraints.

### Contratos e interfaces

Os contratos em `core/contracts.py` são a API pública do Guara. Regras:
- Não quebre contratos existentes sem incremento de versão major (SemVer).
- Novos providers e tools devem ser adicionáveis sem alterar contratos centrais.
- Toda ferramenta retorna payload `{ "message": "...", "data": {...} }`.

### Eventos

- Eventos internos são tipados e versionados (`event_version`).
- Todo evento deve ter `trace_id` e `session_id`.
- Novos eventos devem seguir o formato de `core/events.py`.

### Segurança

- LLM nunca recebe segredos ou credenciais.
- Credenciais ficam isoladas no lado de integração.
- Ações críticas exigem confirmação explícita.
- Input e output passam por guardrails básicos.

---

## Testes

### Regras para PRs

Toda PR que altere runtime ou contratos deve incluir:

1. Teste do caso de sucesso principal.
2. Teste de erro ou edge case.
3. Teste de regressão se o comportamento alterado é sensível.

### Convenções

- Testes em `tests/`, espelhando layout de `core/`/`runtime/`.
- Nome por comportamento: `test_rejects_invalid_token`, não `test_token_1`.
- Use `unittest` ou `unittest.IsolatedAsyncioTestCase` para código async.
- Mocks são aceitos para providers externos (STT, TTS, LLM, MCP).

### Rodar suite completa

```bash
python3 -m unittest discover -s tests -v
```

---

## Decisões travadas

Estas decisões estão fechadas e não devem ser revertidas sem discussão ampla:

| Decisão | Valor |
|---|---|
| Linguagem principal | Python-first |
| Deploy inicial | All-in-one local (Docker) |
| Tool execution | Paralelo com limites por sessão |
| Pós-tool | Sempre run_llm |
| Segurança de credenciais | LLM sem segredos |
| Eventos internos | Tipados e versionados |
| Telemetria | Local-first e opt-in |
| Idioma inicial | Português; inglês depois |
| Latência alvo | P95 <= 2.0s |

Lista completa em [`docs/architecture/IMPLEMENTATION_SPEC.md`](docs/architecture/IMPLEMENTATION_SPEC.md), seção 2.

---

## Roadmap resumido

| Fase | Escopo |
|---|---|
| 0 (concluída) | Contratos, event bus, sessão, logs |
| 1 (concluída) | V2V reativo, tool-calling, MCP, barge-in, guardrails, streaming, realtime WS |
| A (próxima) | Hardening: heartbeat WS, auth, backpressure, timeout de stream |
| B | Memória RAG real |
| C | Marketplace operacional |
| D | Proatividade controlada |
| E | Provider integrations reais |

Contribuições alinhadas com a fase atual e próxima têm prioridade de revisão.

---

## Código de conduta

- Seja respeitoso e construtivo.
- Foque no problema, não na pessoa.
- Contribuições de qualquer nível de experiência são bem-vindas.
- Em caso de dúvida, pergunte na issue antes de assumir.

---

## Dúvidas?

Abra uma issue com label `question` ou comente na issue/PR relevante.
