# Streaming Contracts Design

**Data:** 2026-02-23
**Status:** aprovado
**Escopo:** Abordagem 2 — gaps arquiteturais críticos para MVP V2V

---

## Problema

Os contratos atuais (`core/contracts.py`) são totalmente batch: cada etapa espera a anterior terminar antes de produzir qualquer saída. Isso resulta em latência de 3–5s no pipeline V2V e impossibilita barge-in real — dois requisitos explícitos do MVP.

Os gaps identificados se dividem em:
- **Arquiteturais** — se não entrarem agora, todos os adapters (incluindo da comunidade) precisarão ser reescritos depois.
- **De feature** — podem ser adicionados como campos opcionais quando a feature concreta chegar.

Esta decisão trata apenas dos gaps arquiteturais.

---

## Decisão

Adicionar streaming e cancel nos três providers de mídia. Todos os outros contratos ficam inalterados.

---

## Mudanças nos Contratos

### Novo tipo compartilhado — `core/types.py`

```python
@dataclass(frozen=True)
class TranscriptionChunk:
    text: str
    is_final: bool
    confidence: float = 1.0
```

### `ISTTProvider` — adiciona `transcribe_stream`

```python
class ISTTProvider(Protocol):
    async def transcribe(self, audio: bytes, language: str | None = None) -> str: ...

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str | None = None,
    ) -> AsyncIterator[TranscriptionChunk]: ...
```

### `ILLMProvider` — adiciona `stream`

```python
class ILLMProvider(Protocol):
    async def complete(self, messages: list[dict], tools: Any | None = None) -> dict: ...

    async def stream(
        self,
        messages: list[dict],
        tools: Any | None = None,
    ) -> AsyncIterator[str]: ...
```

### `ITTSProvider` — adiciona `synthesize_stream` e `cancel`

```python
class ITTSProvider(Protocol):
    async def synthesize(self, text: str, voice: str | None = None) -> bytes: ...

    async def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        voice: str | None = None,
    ) -> AsyncIterator[bytes]: ...

    async def cancel(self, session_id: str) -> None: ...
```

### Contratos sem mudança

`IToolProvider`, `IMemoryProvider`, `IGuardrail` — sem alteração neste design.

---

## Fluxo de Dados

### Antes (batch)
```
áudio completo → STT (espera) → texto → LLM (espera) → texto → TTS (espera) → áudio
                                                                                  ↑ usuário ouve (~3-5s)
```

### Depois (streaming)
```
áudio chunks → STT stream → texto parcial → LLM stream → tokens → TTS stream → áudio chunks
                                ↑ isFinal=true                                      ↑ usuário ouve (~0.8-1.2s)
```

### Barge-in

```
usuário fala (interrompe)
  → AudioInput detecta → SessionState = INTERRUPTED
  → tts_provider.cancel(session_id)          ← novo
  → ToolRouter.cancel_interruptible_calls()  ← já existe
  → pipeline reinicia do STT
```

### Sentence buffer (entre LLM e TTS)

O TTS não sintetiza token por token. Um sentence buffer em `core/streaming.py` (arquivo já existe) acumula tokens até uma frase completa antes de passar ao TTS. Não altera os contratos.

---

## Impacto nos Adapters

### Adapters stub (`adapters/`)

Todos implementam os novos métodos como compatibilidade backward:

| Adapter | `transcribe_stream` | `stream` | `synthesize_stream` | `cancel` |
|---|---|---|---|---|
| `LocalSTTProvider` | Emite resultado do `transcribe` como chunk único com `is_final=True` | — | — | — |
| `RuleBasedLLMProvider` | — | Itera resultado do `complete` caractere a caractere | — | — |
| `LocalTTSProvider` | — | — | Coleta stream em string, chama `synthesize` | no-op |

Zero lógica nova — só wrappers de compatibilidade.

### Regra para adapters da comunidade

Um adapter que implementa apenas os métodos batch ainda funciona. O core usa batch por padrão e chama os métodos stream apenas quando o modo streaming estiver ativo. Isso deve ser documentado no `CONTRIBUTING.md` e no `plugins/sdk.py`.

---

## Mudanças no Orchestrator

Novo método paralelo ao `handle_user_text` (que é mantido):

```python
async def stream_user_text(
    self,
    user_text: str,
    *,
    session_id: str,
    trace_id: str,
) -> AsyncIterator[str]:
    ...
```

---

## Estratégia de Testes

### Testes de contrato (novos)

```python
# STT stream emite chunk final
async def test_stt_stream_emits_final_chunk():
    chunks = [c async for c in provider.transcribe_stream(async_bytes(b"audio"))]
    assert any(c.is_final for c in chunks)

# TTS cancel é idempotente
async def test_tts_cancel_is_idempotent():
    await provider.cancel("session-1")
    await provider.cancel("session-1")  # não explode

# LLM stream concatenado = resultado batch
async def test_llm_stream_concatenates_to_complete():
    tokens = [t async for t in provider.stream([{"role": "user", "content": "oi"}])]
    assert "".join(tokens)
```

### Teste de integração (barge-in)

```python
async def test_barge_in_cancels_tts():
    # SessionState vai para INTERRUPTED
    # tts_provider.cancel foi chamado
    # pipeline reinicia
```

### Teste de pipeline streaming

```python
async def test_stream_user_text_yields_tokens():
    tokens = [t async for t in orchestrator.stream_user_text("oi", session_id="s1", trace_id="t1")]
    assert len(tokens) > 0
```

---

## O que Não Muda

- Todos os testes existentes continuam passando
- `ToolRouter`, `ToolPolicy`, `cancel_interruptible_calls()`
- `EventBus`, `LocalEventStore`, `telemetry.py`
- `PluginLoader`, `ToolManifest`, `DirectFunctionToolProvider`
- `runtime/app.py` (`GuaraRuntime`) — streaming entra como método novo

---

## Gaps Fora do Escopo (entram quando a feature pedir)

| Gap | Quando entra |
|---|---|
| `ActionResult.status: "pending_approval"` | Human-in-the-loop feature |
| `rollback()` no tool execution | Transacionalidade feature |
| `SpeechToSpeechPort` | Quando existir adapter S2S real |
| `speaker_verify()` | Biometria de voz feature |
| `clone_voice()` no TTS | Clonagem de voz feature |
| `IGuardrail` + `session_id` | Rastreabilidade avançada |
| `IMemoryProvider.save_message()/get_history()` | Quando o put/get/query virar gargalo real |
