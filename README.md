# Scamantics

Explainable scam manipulation analysis. Paste a suspicious message and Scamantics shows **which manipulation tactics** it uses, **quotes the exact phrases** as evidence, and **explains** them in plain language. It is an educational aid that supports human judgement; it never claims a message is definitely a scam.

## How it works

```
message ─► one LLM call (detect + identify + quote + explain, JSON schema)
        ─► deterministic validator: every quote must appear verbatim in the message
               └─ invalid quotes rejected → one retry asking the model to fix them
        ─► Gradio UI: highlighted evidence, tactic cards, safety disclaimer
```

Taxonomy (fixed, five labels): `urgency`, `impersonation` (impersonation / authority), `isolation` (isolation / secrecy), `reward` (reward / incentive), `threat` (threat / penalty). Definitions and examples live in `scamantics/taxonomy.py` and are injected into the system prompt.

## Quick start

```bash
conda activate scamantics          # or: pip install -r requirements.txt
python app.py                      # http://127.0.0.1:7860
```

By default the app talks to a **local Ollama** server (`gemma4:12b`), which is free. Switch provider with environment variables or a `.env` file (see `.env.example`):

| `SCAMANTICS_PROVIDER` | Backend | Needs key | Notes |
|---|---|---|---|
| `ollama` (default) | local Ollama `/api/chat` | no | schema-constrained JSON output |
| `openai` | OpenAI chat completions | `OPENAI_API_KEY` | default model `gpt-4o-mini` |
| `groq` | Groq (OpenAI-compatible) | `GROQ_API_KEY` | free tier, very fast |
| `openrouter` | OpenRouter (OpenAI-compatible) | `OPENROUTER_API_KEY` | has `:free` models |
| `deepseek` | DeepSeek (OpenAI-compatible) | `DEEPSEEK_API_KEY` | cheap |
| `anthropic` | Anthropic Messages API | `ANTHROPIC_API_KEY` | default `claude-haiku-4-5` |
| `gemini` | Google Gemini | `GEMINI_API_KEY` | free tier |
| `mock` | cached demo answers only | no | offline fallback |

Any other OpenAI-compatible server (vLLM, LM Studio, Together…) works with `SCAMANTICS_PROVIDER=openai` plus `SCAMANTICS_BASE_URL` and `SCAMANTICS_MODEL`.

If the backend is unreachable, the app serves precomputed answers from `data/demo_cache.json` for the built-in example messages, so the demo still runs offline. Rebuild the cache with `python scripts/build_demo_cache.py` (add `--all` to include the test set).

## Evaluation

`data/test_set.jsonl` holds 60 annotated messages (25 familiar scam patterns, 20 paraphrased / structurally different scams, 15 benign) with gold tactic labels and evidence spans.

```bash
python evaluate.py                          # current provider, prints the report
python evaluate.py --provider groq --out results/groq.json
python evaluate.py --category paraphrased   # generalisation subset only
```

Reported metrics: detection accuracy / F1 and false-positive rate, macro and micro F1 over the five labels, per-label F1, **grounding rate** (share of model quotes that occur exactly in the source), **span F1** (token-level overlap with gold spans), mean attempts per message.

## Project layout

```
app.py                      Gradio interface
evaluate.py                 evaluation CLI
scamantics/
  taxonomy.py               the five tactics, definitions, examples, colours, advice
  schema.py                 Pydantic models + JSON schema sent to the model
  prompt.py                 system / user / retry prompts
  validator.py              exact-substring evidence check (lenient locate, strict output)
  analyzer.py               orchestration: call → parse → validate → retry → result
  cache.py                  offline demo cache
  config.py                 env-based settings and provider presets
  evaluation.py             metrics (sklearn)
  providers/                ollama, openai-compatible, anthropic, gemini, mock
data/test_set.jsonl         labelled test set
data/demo_cache.json        cached results for the UI examples
scripts/build_demo_cache.py
tests/                      pytest suite (no network required)
```

## Tests

```bash
python -m pytest -q
```

## Safety note

The interface never states that a message *is* a scam. It highlights persuasive and coercive patterns and reminds the user to verify any request for money, codes or personal data through an independent channel.
