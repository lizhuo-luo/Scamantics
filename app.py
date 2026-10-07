"""Scamantics Gradio demo: paste a message, see which manipulation tactics it uses and why."""

from __future__ import annotations

import html
import logging
import os

import gradio as gr

from scamantics.analyzer import Analyzer
from scamantics.schema import AnalysisResult
from scamantics.taxonomy import COLOR_MAP, TACTIC_BY_LABEL, TACTICS

logging.basicConfig(level=os.getenv("SCAMANTICS_LOG", "INFO"))

DISCLAIMER = (
    "**Please note:** Scamantics is an educational tool. It highlights persuasive or coercive patterns "
    "so you can judge for yourself. It cannot confirm whether a message is genuinely fraudulent. "
    "If a message asks for money, codes or personal details, verify the request through an independent "
    "channel such as the official phone number on your bank card or the organisation's real website."
)

EXAMPLES = [
    "URGENT: Your HSBC account has been locked due to suspicious activity. Verify your identity within 2 hours at hsbc-secure-verify.com or your funds will be frozen permanently. Do not share this message with anyone.",
    "Congratulations! You have been selected as our lucky winner of a $1,000 Walmart gift card. Reply YES to claim your prize before midnight tonight.",
    "Hi Mum, it's me. I dropped my phone in the sink so this is my new number. I need to pay a bill today but my banking app is locked on the old phone, could you transfer £850 to this account? Please don't tell Dad, he'll be angry about the phone.",
    "This is Officer Daniels from the Australian Taxation Office. A warrant has been issued for your arrest due to unpaid tax. Call 02 8000 1234 immediately to settle the amount and avoid prosecution.",
    "Your parcel could not be delivered because of an unpaid customs fee of $2.99. Pay within 12 hours at royalmail-redelivery.net or the item will be returned to sender.",
    "Hi Sam, running about 10 minutes late, can you grab me a flat white? Thanks!",
    "Reminder: your dentist appointment is on Tuesday 14 Oct at 9:30am. Reply C to confirm or call us on 020 7946 0000 to reschedule.",
]

_analyzer: Analyzer | None = None


def get_analyzer() -> Analyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = Analyzer()
    return _analyzer


def build_highlight(result: AnalysisResult) -> list[tuple[str, str | None]]:
    """Convert verified spans into HighlightedText segments."""
    msg = result.message
    segments: list[tuple[str, str | None]] = []
    pos = 0
    for span in result.spans:
        if span.start < pos:  # overlapping span already covered
            continue
        if span.start > pos:
            segments.append((msg[pos : span.start], None))
        segments.append((msg[span.start : span.end], span.label))
        pos = span.end
    if pos < len(msg):
        segments.append((msg[pos:], None))
    if not segments:
        segments.append((msg, None))
    return segments


def verdict_markdown(result: AnalysisResult) -> str:
    if result.error:
        return f"### ⚠️ Could not analyse\n{html.escape(result.error)}"
    if result.is_suspicious:
        n = len(result.tactics)
        head = f"### 🔎 Suspicious patterns found ({n} tactic{'s' if n != 1 else ''})"
    else:
        head = "### ✅ No strong manipulation tactic detected"
    return f"{head}\n\n{result.summary}"


def tactic_cards_html(result: AnalysisResult) -> str:
    if result.error or not result.tactics:
        return ""
    cards = []
    for t in result.tactics:
        info = TACTIC_BY_LABEL[t.label]
        quotes = "".join(f"<li>“{html.escape(q)}”</li>" for q in t.evidence)
        conf = f"<span class='sc-conf'>confidence {t.confidence:.0%}</span>" if t.confidence is not None else ""
        cards.append(
            f"<div class='sc-card' style='border-left:6px solid {info.color}'>"
            f"<div class='sc-card-head'><span class='sc-dot' style='background:{info.color}'></span>"
            f"<strong>{html.escape(info.name)}</strong>{conf}</div>"
            f"<div class='sc-def'>{html.escape(info.definition)}</div>"
            f"<div class='sc-sub'>Evidence in this message</div><ul>{quotes}</ul>"
            f"<div class='sc-sub'>Why it matters</div><p>{html.escape(t.explanation)}</p>"
            f"<div class='sc-advice'>💡 {html.escape(info.advice)}</div>"
            f"</div>"
        )
    return "<div class='sc-cards'>" + "".join(cards) + "</div>"


def meta_markdown(result: AnalysisResult) -> str:
    bits = []
    if result.from_cache:
        bits.append("source: cached demo result")
    elif result.model:
        bits.append(f"model: {result.provider}:{result.model}")
    if result.attempts > 1:
        bits.append(f"attempts: {result.attempts}")
    if result.rejected_quotes:
        bits.append(f"{len(result.rejected_quotes)} quote(s) rejected by the evidence check")
    return "<small>" + " · ".join(bits) + "</small>" if bits else ""


def analyse(message: str):
    result = get_analyzer().analyze(message)
    return (
        verdict_markdown(result),
        build_highlight(result),
        tactic_cards_html(result),
        meta_markdown(result),
        result.model_dump(),
    )


CSS = """
.sc-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-top: 8px; }
.sc-card { background: var(--block-background-fill); border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.sc-card-head { display: flex; align-items: center; gap: 8px; font-size: 1.05em; margin-bottom: 6px; }
.sc-dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
.sc-conf { margin-left: auto; font-size: .8em; opacity: .7; }
.sc-def { font-size: .9em; opacity: .8; margin-bottom: 8px; }
.sc-sub { font-weight: 600; font-size: .85em; text-transform: uppercase; letter-spacing: .03em; margin-top: 8px; opacity: .75; }
.sc-card ul { margin: 4px 0 0 18px; }
.sc-card p { margin: 4px 0; }
.sc-advice { margin-top: 10px; font-size: .9em; padding: 8px 10px; border-radius: 6px; background: rgba(127,127,127,.1); }
.sc-legend { display: flex; flex-wrap: wrap; gap: 10px 18px; font-size: .9em; }
.sc-legend span { display: inline-flex; align-items: center; gap: 6px; }
"""


def legend_html() -> str:
    items = "".join(
        f"<span><i class='sc-dot' style='background:{t.color}'></i>{html.escape(t.name)}</span>" for t in TACTICS
    )
    return f"<div class='sc-legend'>{items}</div>"


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Scamantics") as demo:
        gr.Markdown(
            "# Scamantics\n"
            "**Explainable scam manipulation analysis.** Paste a suspicious text message and Scamantics will show "
            "which manipulation tactics it uses, quote the exact phrases as evidence, and explain them in plain language."
        )
        with gr.Row():
            with gr.Column(scale=1):
                inp = gr.Textbox(
                    label="Message to analyse",
                    placeholder="Paste the text message or email here…",
                    lines=8,
                    max_lines=20,
                )
                with gr.Row():
                    btn = gr.Button("Analyse", variant="primary")
                    clear = gr.ClearButton([inp], value="Clear")
                gr.Examples(examples=[[e] for e in EXAMPLES], inputs=[inp], label="Try an example")
                gr.HTML(legend_html())
            with gr.Column(scale=1):
                verdict = gr.Markdown("### Results will appear here")
                highlighted = gr.HighlightedText(
                    label="Evidence highlighted in the message",
                    color_map=COLOR_MAP,
                    show_legend=False,
                    combine_adjacent=False,
                )
                cards = gr.HTML()
                meta = gr.HTML()
                with gr.Accordion("Raw JSON result", open=False):
                    raw = gr.JSON()
        gr.Markdown(DISCLAIMER)

        outputs = [verdict, highlighted, cards, meta, raw]
        btn.click(analyse, inputs=[inp], outputs=outputs, api_name="analyse")
        inp.submit(analyse, inputs=[inp], outputs=outputs)
        clear.add([verdict, highlighted, cards, meta, raw])
    return demo


if __name__ == "__main__":
    ok, status = get_analyzer().provider.healthcheck()
    print(f"[scamantics] provider status: {status}")
    if not ok:
        print("[scamantics] WARNING: provider unavailable; only cached demo examples will work.")
    build_app().launch(
        css=CSS,
        theme=gr.themes.Soft(),
        server_name=os.getenv("SCAMANTICS_HOST", "127.0.0.1"),
        server_port=int(os.getenv("SCAMANTICS_PORT", "7860")),
        share=os.getenv("SCAMANTICS_SHARE", "0") == "1",
    )
