# Scamantics

**Scamantics explains *how* a message tries to manipulate you. It is not a scam detector.**

Paste a suspicious text message and Scamantics shows which manipulation tactics it uses, quotes the exact phrases as evidence, and explains them in plain language. The goal is educational: to help a non-expert recognise persuasive and coercive patterns and then make their own decision. Scamantics never says "this is a scam"; a message can use pressure tactics and still be legitimate, and a scam can be written without any of them.

![Scamantics analysing a fake bank alert](docs/screenshots/result-light.png)

<details>
<summary>Dark theme</summary>

![Scamantics in dark mode](docs/screenshots/result-dark.png)
</details>

## How it works

```
message ─► one LLM call (detect + identify + quote + explain, JSON schema)
        ─► deterministic validator: every quote must appear verbatim in the message
               └─ invalid quotes rejected → one retry asking the model to fix them
        ─► Gradio UI: highlighted evidence, tactic cards, safety disclaimer
```

1. **Detect and identify.** A pretrained LLM judges whether manipulation is present and labels the tactics from a fixed list of five.
2. **Ground.** For each tactic the model must quote the exact words that support it.
3. **Verify.** Python checks that every quote is a verbatim substring of the message. Quotes that are not are rejected; the model is asked once to correct them. A tactic with no surviving evidence is dropped, and a message with no verified evidence is never flagged.
4. **Explain.** Each verified tactic is shown with its evidence, a plain-language explanation and a model confidence score.

No model is trained. Swapping the LLM is a configuration change (see below).

## Why these five tactics?

The taxonomy is deliberately small and fixed so that outputs are comparable across messages and models and so that each label has an operational definition a non-expert can check against the quoted evidence.

| Label | Tactic | Grounding |
|---|---|---|
| `urgency` | Urgency | Time pressure stops the reader from verifying. It is the "pressure you to act immediately" sign in consumer-protection guidance and maps to scarcity in Cialdini's principles of influence and to the "time" principle in Stajano and Wilson's analysis of scam victims. |
| `impersonation` | Impersonation / authority | Borrowing a trusted identity (bank, government, family member) is the "pretend to be an organisation you know" sign and corresponds to the authority principle. It is the entry point of most phishing and "Hi Mum" scams. |
| `isolation` | Isolation / secrecy | Cutting the target off from second opinions ("don't tell the bank", "keep this between us") is characteristic of romance, courier and safe-account scams and is what makes the other tactics hard to break. |
| `reward` | Reward / incentive | Prizes, refunds, jobs and guaranteed returns exploit what Stajano and Wilson call "need and greed"; it is the "there's a prize" half of the "problem or prize" sign. |
| `threat` | Threat / penalty | Arrest, fines, account closure and exposure exploit fear; it is the "there's a problem" half of "problem or prize" and the coercive counterpart of reward. |

Together these cover the four warning signs that consumer-protection agencies such as the US FTC publish (impersonation, problem or prize, pressure to act, unusual payment), with reward and threat split apart because they call for different explanations, and with isolation added because it is the tactic that most directly removes the user's ability to seek help. The "unusual payment method" sign is not a tactic in the wording of a message and is handled by the safety disclaimer instead.

References: Cialdini, *Influence: The Psychology of Persuasion* (1984); Stajano and Wilson, "Understanding scam victims: seven principles for systems security", *Communications of the ACM* 54(3), 2011; US Federal Trade Commission, "How to avoid a scam".

## Quick start

```bash
conda activate scamantics          # or: pip install -r requirements.txt
python app.py                      # http://127.0.0.1:7860
SCAMANTICS_SHARE=1 python app.py   # also prints a temporary public gradio.live link
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

If the backend is unreachable, the app serves precomputed answers from `data/demo_cache.json` for known messages, so the demo still runs offline. Rebuild the cache with `python scripts/build_demo_cache.py` (add `--all` to include the test set).

## Interface

The result panel shows a verdict banner with tactic chips, the original message with every verified evidence span highlighted and tagged, one card per tactic (definition, quoted evidence, plain-language explanation, model confidence), a "what you can do" box built from the tactics found, and the raw JSON. Light and dark themes are supported; the layout stacks on phones.

For styling work, `scripts/ui_preview.py` launches the UI with a pre-rendered example from the demo cache (no model call):

```bash
SCAMANTICS_PROVIDER=mock python scripts/ui_preview.py 0 7862   # example index, port
```

## Evaluation

`data/test_set.jsonl` holds 90 hand-written, hand-annotated messages with gold tactic labels and gold evidence spans:

| Category | n | What it tests |
|---|---|---|
| `familiar` | 25 | Classic scam templates (bank lock-out, prize, tax warrant, parcel fee…) |
| `paraphrased` | 20 | Scams with unseen wording and different scenarios, for generalisation |
| `subtle_scam` | 15 | Low-key scams with few surface cues: wrong-number openers, slow-burn investment and romance grooming, advance-fee offers phrased politely. Two of these (`ss01`, `ss14`) contain no tactic from the taxonomy and are labelled empty on purpose. |
| `benign` | 15 | Ordinary personal, commercial and institutional messages |
| `hard_benign` | 15 | Legitimate messages that *look* like scams: real fraud alerts, OTP warnings, payment reminders with deadlines, a genuine "lost my phone" text, a police case update |

```bash
python evaluate.py                          # current provider, prints the report
python evaluate.py --provider groq --out results/groq.json
python evaluate.py --category hard_benign   # one subset only
```

Reported per category and overall: detection accuracy, F1 and false-positive rate (is the message flagged at all), macro and micro F1 over the five labels plus per-label F1, **grounding rate** (share of the model's raw quotes that occur exactly in the source, counted before the validator repairs or rejects anything), **span F1** (token-level overlap with gold spans), and mean attempts per message. Results for the local baseline are in `results/`.

### Baseline: local `gemma4:12b` via Ollama (no API cost)

| Category | n | Detection acc. | Macro F1 | Micro F1 | Grounding | Span F1 |
|---|---|---|---|---|---|---|
| all | 90 | 0.978 | 0.943 | 0.939 | 1.000 | 0.786 |
| familiar | 25 | 1.000 | 0.970 | 0.969 | 1.000 | 0.793 |
| paraphrased | 20 | 1.000 | 0.964 | 0.951 | 1.000 | 0.736 |
| subtle_scam | 15 | 0.867 | 0.467 | 0.811 | 1.000 | 0.882 |
| benign | 15 | 1.000 | – | – | 1.000 | – |
| hard_benign | 15 | 1.000 | – | – | 1.000 | – |

Per-label F1 overall: urgency 0.958, impersonation 0.904, isolation 0.963, reward 0.955, threat 0.938. Mean attempts 1.01; about 4 s per message on one GPU.

Reading the numbers: every one of the 30 legitimate messages, including the scam-lookalikes in `hard_benign`, was left unflagged. The weak spot is `subtle_scam`, where the model flags the two deliberately empty-labelled messages (the wrong-number opener as impersonation, the overpaying tenant as reward) and labels the romance groomer as impersonation + reward rather than isolation. Those readings are defensible, which is exactly the kind of annotation disagreement the small benchmark cannot settle. Full per-message predictions are in `results/eval_ollama_gemma4-12b.json`.

## Limitations

- **Small prototype benchmark.** 90 messages written by the project team is enough to compare configurations and catch regressions, not to make claims about real-world performance. Messages are English, UK/US-centric, and short. There is no inter-annotator agreement study; the gold labels reflect the team's reading of each message.
- **The taxonomy is not exhaustive.** Flattery, reciprocity, social proof ("thousands have already claimed"), and pure deception without pressure are not labels. Some scams, such as the wrong-number opener or the overpaying tenant, contain no tactic in the message text and will correctly produce "no strong tactic detected" even though the follow-up conversation would be a scam.
- **Tactics are not verdicts.** Legitimate fraud alerts, OTP messages and payment reminders share wording with scams. Scamantics only looks at wording; it knows nothing about the sender, the link destination or the recipient's actual account. That is why the interface never says "scam" and always points the user to an independent channel.
- **LLM dependence.** Labels, explanations and confidence scores come from a general-purpose model and vary between models and runs. The validator guarantees that quoted evidence is real; it does not guarantee that the label attached to it is right or that the explanation is accurate.
- **Confidence scores are self-reported** by the model and are not calibrated probabilities.
- **No image or OCR input** in this version.

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
data/test_set.jsonl         labelled test set (90 messages, 5 categories)
data/demo_cache.json        cached results for all known messages
docs/screenshots/           README screenshots
scripts/build_demo_cache.py
scripts/ui_preview.py       launch the UI with a pre-rendered example (for screenshots)
tests/                      pytest suite (no network required)
results/                    evaluation reports
```

## Tests

```bash
python -m pytest -q
```
