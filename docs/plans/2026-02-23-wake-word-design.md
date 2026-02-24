# Wake Word Design

**Goal:** O servidor detecta a palavra "Guará" pelo microfone e inicia automaticamente uma conversa, encerrando quando o usuário diz a palavra de parada configurável.

**Architecture:** openwakeword com modelo personalizado treinado com amostras sintéticas (Piper) + amostras reais gravadas. Um processo independente (`runtime/listener.py`) escuta continuamente o microfone e aciona o pipeline existente do `GuaraRuntime`.

**Tech Stack:** openwakeword, pyaudio, Whisper (já existente), Piper (já existente), GuaraRuntime (já existente)

---

## Novos módulos

| Arquivo | Responsabilidade |
|---|---|
| `adapters/wakeword_oww.py` | Adapter openwakeword — carrega modelo `.tflite`, pontua frames de áudio |
| `runtime/listener.py` | Loop contínuo de escuta — estados SLEEPING/AWAKE/RECORDING/SENDING |
| `tools/train_wakeword.py` | Script de treinamento — geração sintética, gravação real, treino |

## Fluxo em produção

```
mic (pyaudio, 80ms frames, 16kHz mono)
  → openwakeword score ≥ threshold  →  "Guará detectado"
  → acumula áudio  →  Whisper detecta stop word a cada 2s
  → áudio completo  →  GuaraRuntime.process_turn()
  → Piper sintetiza  →  aplay toca resposta
  → volta a SLEEPING
```

## Estados do listener

```
SLEEPING   ouve frames, score < threshold
AWAKE      score ≥ threshold → bipe de confirmação → inicia gravação
RECORDING  acumula áudio, Whisper a cada 2s para detectar stop word
SENDING    envia para GuaraRuntime, aguarda resposta, toca via aplay → SLEEPING
```

## Script de treinamento

```bash
# Gerar amostras sintéticas com Piper (500 variações)
python tools/train_wakeword.py --generate --word "Guará" \
  --model /tmp/piper-models/pt_BR-faber-medium.onnx \
  --out /tmp/wakeword-samples/synthetic/

# Gravar amostras reais (30 repetições)
python tools/train_wakeword.py --record \
  --out /tmp/wakeword-samples/real/

# Treinar e salvar modelo
python tools/train_wakeword.py --train \
  --synthetic /tmp/wakeword-samples/synthetic/ \
  --real /tmp/wakeword-samples/real/ \
  --out /tmp/models/guara.tflite

# Ou tudo de uma vez
python tools/train_wakeword.py --all --word "Guará"
```

## Env vars

| Variável | Padrão | Descrição |
|---|---|---|
| `GUARA_WAKE_WORD_MODEL` | `/tmp/models/guara.tflite` | Caminho do modelo treinado |
| `GUARA_STOP_WORD` | `obrigado` | Palavra que encerra a gravação |
| `GUARA_WAKE_THRESHOLD` | `0.5` | Confiança mínima para acordar |

## Feedback sonoro

- Acorda: bipe curto (440Hz, 150ms)
- Stop word detectada: bipe duplo
- Erro: bipe longo

## Testes

- `tests/core/test_wakeword_oww.py` — unit: pontuação de frames com modelo mock
- `tests/core/test_listener.py` — unit: transições de estado (SLEEPING→AWAKE→RECORDING→SENDING)
- `tests/core/test_train_wakeword.py` — unit: geração de amostras, integração com Piper mock
