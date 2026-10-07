"""Scamantics Gradio demo: paste a message, see which manipulation tactics it uses and why."""

from __future__ import annotations

import html
import logging
import os
import time

import gradio as gr

from scamantics.analyzer import Analyzer
from scamantics.schema import AnalysisResult
from scamantics.taxonomy import TACTIC_BY_LABEL, TACTICS

logging.basicConfig(level=os.getenv("SCAMANTICS_LOG", "INFO"))

DISCLAIMER = (
    "Scamantics is an educational tool. It highlights persuasive or coercive patterns so you can judge for "
    "yourself; it cannot confirm whether a message is genuinely fraudulent. If a message asks for money, codes "
    "or personal details, verify the request through an independent channel such as the phone number on your "
    "bank card or the organisation's official website."
)

EXAMPLES: list[str] = [
    "URGENT: Your HSBC account has been locked due to suspicious activity. Verify your identity within 2 hours at hsbc-secure-verify.com or your funds will be frozen permanently. Do not share this message with anyone.",
    "Congratulations! You have been selected as our lucky winner of a $1,000 Walmart gift card. Reply YES to claim your prize before midnight tonight.",
    "Hi Mum, it's me. I dropped my phone in the sink so this is my new number. I need to pay a bill today but my banking app is locked on the old phone, could you transfer £850 to this account? Please don't tell Dad, he'll be angry about the phone.",
    "This is Officer Daniels from the Australian Taxation Office. A warrant has been issued for your arrest due to unpaid tax. Call 02 8000 1234 immediately to settle the amount and avoid prosecution.",
    "Your parcel could not be delivered because of an unpaid customs fee of $2.99. Pay within 12 hours at royalmail-redelivery.net or the item will be returned to sender.",
    "Hi Sam, running about 10 minutes late, can you grab me a flat white? Thanks!",
    "Reminder: your dentist appointment is on Tuesday 14 Oct at 9:30am. Reply C to confirm or call us on 020 7946 0000 to reschedule.",
]
EXAMPLE_LABELS: list[str] = [
    "Bank account locked",
    "Gift card winner",
    "\"Hi Mum\" new number",
    "Tax office arrest warrant",
    "Parcel customs fee",
    "Benign: running late",
    "Benign: dentist reminder",
]

_analyzer: Analyzer | None = None


def get_analyzer() -> Analyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = Analyzer()
    return _analyzer


# ---------------------------------------------------------------------------------------------
# rendering helpers


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _tint(hex_color: str, alpha_hex: str = "33") -> str:
    return hex_color + alpha_hex


def render_message(result: AnalysisResult) -> str:
    """The original message with verified evidence spans marked up inline."""
    msg = result.message
    parts: list[str] = []
    pos = 0
    for span in result.spans:
        if span.start < pos:
            continue
        if span.start > pos:
            parts.append(_esc(msg[pos : span.start]))
        info = TACTIC_BY_LABEL[span.label]
        parts.append(
            f"<mark class='sc-mark' style='background:{_tint(info.color, '2e')};border-bottom-color:{info.color}' "
            f"title='{_esc(info.name)}'>{_esc(msg[span.start : span.end])}"
            f"<span class='sc-tag' style='background:{info.color}'>{_esc(info.name.split(' /')[0])}</span></mark>"
        )
        pos = span.end
    if pos < len(msg):
        parts.append(_esc(msg[pos:]))
    body = "".join(parts).replace("\n", "<br>")
    return f"<div class='sc-message'><div class='sc-message-label'>Message</div><div class='sc-message-body'>{body}</div></div>"


def render_banner(result: AnalysisResult) -> str:
    if result.error:
        return (
            "<div class='sc-banner sc-banner-error'><div class='sc-banner-icon'>⚠️</div><div>"
            "<div class='sc-banner-title'>Could not analyse this message</div>"
            f"<div class='sc-banner-text'>{_esc(result.error)}</div></div></div>"
        )
    if result.is_suspicious:
        n = len(result.tactics)
        chips = "".join(
            f"<span class='sc-chip' style='background:{TACTIC_BY_LABEL[t.label].color}'>{_esc(TACTIC_BY_LABEL[t.label].name)}</span>"
            for t in result.tactics
        )
        return (
            "<div class='sc-banner sc-banner-warn'><div class='sc-banner-icon'>🔎</div><div>"
            f"<div class='sc-banner-title'>{n} manipulation tactic{'s' if n != 1 else ''} found</div>"
            f"<div class='sc-banner-text'>{_esc(result.summary)}</div>"
            f"<div class='sc-chips'>{chips}</div></div></div>"
        )
    return (
        "<div class='sc-banner sc-banner-ok'><div class='sc-banner-icon'>✅</div><div>"
        "<div class='sc-banner-title'>No strong manipulation tactic detected</div>"
        f"<div class='sc-banner-text'>{_esc(result.summary)} Stay alert anyway: this tool only looks at wording, "
        "not at who really sent the message.</div></div></div>"
    )


def render_cards(result: AnalysisResult) -> str:
    if result.error or not result.tactics:
        return ""
    cards = []
    for t in result.tactics:
        info = TACTIC_BY_LABEL[t.label]
        quotes = "".join(
            f"<li><span class='sc-quote' style='background:{_tint(info.color, '2e')};border-color:{info.color}'>“{_esc(q)}”</span></li>"
            for q in t.evidence
        )
        if t.confidence is not None:
            pct = int(round(t.confidence * 100))
            conf = (
                f"<div class='sc-conf' title='Model confidence {pct}%'><div class='sc-conf-bar'>"
                f"<div style='width:{pct}%;background:{info.color}'></div></div><span>{pct}%</span></div>"
            )
        else:
            conf = ""
        cards.append(
            f"<div class='sc-card'><div class='sc-card-strip' style='background:{info.color}'></div>"
            f"<div class='sc-card-body'>"
            f"<div class='sc-card-head'><span class='sc-dot' style='background:{info.color}'></span>"
            f"<span class='sc-card-title'>{_esc(info.name)}</span>{conf}</div>"
            f"<div class='sc-def'>{_esc(info.definition)}</div>"
            f"<div class='sc-sub'>Evidence</div><ul class='sc-quotes'>{quotes}</ul>"
            f"<div class='sc-sub'>Why it matters</div><p class='sc-expl'>{_esc(t.explanation)}</p>"
            f"</div></div>"
        )
    return "<div class='sc-section-title'>Tactics in detail</div><div class='sc-cards'>" + "".join(cards) + "</div>"


def render_next_steps(result: AnalysisResult) -> str:
    if result.error or not result.tactics:
        return ""
    tips: list[str] = []
    for t in result.tactics:
        adv = TACTIC_BY_LABEL[t.label].advice
        if adv not in tips:
            tips.append(adv)
    tips.append("Never pay, share a code or click a link because a message tells you to. Check with the real organisation first.")
    items = "".join(f"<li>{_esc(x)}</li>" for x in tips)
    return f"<div class='sc-next'><div class='sc-next-title'>💡 What you can do</div><ul>{items}</ul></div>"


def render_meta(result: AnalysisResult, seconds: float | None) -> str:
    bits: list[str] = []
    if result.from_cache:
        bits.append("cached demo result")
    elif result.model:
        bits.append(f"model {result.provider}:{result.model}")
    if seconds is not None and not result.from_cache:
        bits.append(f"{seconds:.1f}s")
    if result.attempts > 1:
        bits.append(f"{result.attempts} attempts")
    if result.rejected_quotes:
        bits.append(f"{len(result.rejected_quotes)} quote(s) rejected by the evidence check")
    if result.tactics:
        bits.append("every highlighted phrase was verified to appear verbatim in the message")
    return "<div class='sc-meta'>" + " · ".join(_esc(b) for b in bits) + "</div>"


def render_result(result: AnalysisResult, seconds: float | None = None) -> str:
    if result.error and not result.message:
        return render_banner(result)
    return (
        render_banner(result)
        + (render_message(result) if not result.error else "")
        + render_cards(result)
        + render_next_steps(result)
        + render_meta(result, seconds)
    )


EMPTY_STATE = (
    "<div class='sc-empty'><div class='sc-empty-icon'>🛡️</div>"
    "<div class='sc-empty-title'>Paste a message to begin</div>"
    "<div class='sc-empty-text'>Scamantics will highlight the phrases that pressure or persuade you, name the tactic behind each one, "
    "and explain it in plain language.</div></div>"
)


def legend_html() -> str:
    items = "".join(
        f"<span class='sc-legend-item' title='{_esc(t.definition)}'><i class='sc-dot' style='background:{t.color}'></i>{_esc(t.name)}</span>"
        for t in TACTICS
    )
    return f"<div class='sc-legend'>{items}</div>"


def header_html(status: str, ok: bool) -> str:
    dot = "sc-status-ok" if ok else "sc-status-bad"
    return (
        "<div class='sc-header'><div class='sc-brand'>"
        "<div class='sc-logo'>S</div><div><div class='sc-title'>Scamantics</div>"
        "<div class='sc-tagline'>Explains how a message tries to manipulate you. Not a scam detector.</div></div></div>"
        f"<div class='sc-status'><span class='sc-status-dot {dot}'></span>{_esc(status)}</div></div>"
    )


def how_it_works_html() -> str:
    rows = "".join(
        f"<tr><td><span class='sc-dot' style='background:{t.color}'></span> <strong>{_esc(t.name)}</strong></td>"
        f"<td>{_esc(t.definition)}</td><td class='sc-ex'>“{_esc(t.examples[0])}”</td></tr>"
        for t in TACTICS
    )
    return (
        "<div class='sc-how'>"
        "<ol class='sc-steps'>"
        "<li><strong>Detect &amp; identify.</strong> One call to a language model judges whether manipulation is present and labels the tactics from a fixed list of five.</li>"
        "<li><strong>Ground.</strong> For each tactic the model must quote the exact words that support it.</li>"
        "<li><strong>Verify.</strong> A deterministic checker confirms every quote appears verbatim in your message. Quotes that do not are rejected and the model is asked to correct them.</li>"
        "<li><strong>Explain.</strong> Each verified tactic is shown with its evidence and a plain-language explanation.</li>"
        "</ol>"
        "<table class='sc-tax'><thead><tr><th>Tactic</th><th>Definition</th><th>Example</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    )


# ---------------------------------------------------------------------------------------------
# event handlers


def analyse(message: str):
    t0 = time.time()
    result = get_analyzer().analyze(message)
    return render_result(result, time.time() - t0), result.model_dump()


def clear_all():
    return "", EMPTY_STATE, None


CSS = """
:root { --sc-radius: 14px; }
.gradio-container { max-width: 1240px !important; margin: 0 auto !important; }
footer { opacity: .6; }

/* header */
.sc-header { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; padding: 6px 0 10px; }
.sc-brand { display:flex; align-items:center; gap:14px; }
.sc-logo { width:46px; height:46px; border-radius:12px; display:grid; place-items:center; font-weight:800; font-size:24px; color:#fff;
  background: linear-gradient(135deg, #6366f1, #a855f7); box-shadow: 0 6px 16px rgba(99,102,241,.35); }
.sc-title { font-size:1.65em; font-weight:800; letter-spacing:-.01em; line-height:1.1; }
.sc-tagline { color: var(--body-text-color-subdued); font-size:.95em; }
.sc-status { font-size:.8em; color: var(--body-text-color-subdued); background: var(--block-background-fill); border:1px solid var(--border-color-primary);
  padding:6px 12px; border-radius:999px; display:inline-flex; align-items:center; gap:8px; }
.sc-status-dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
.sc-status-ok { background:#22c55e; box-shadow:0 0 0 3px rgba(34,197,94,.2); }
.sc-status-bad { background:#ef4444; box-shadow:0 0 0 3px rgba(239,68,68,.2); }

/* input side */
#sc-input textarea { font-size: 1rem; line-height: 1.5; }
#sc-analyse { font-weight: 700; }
.sc-legend { display:flex; flex-wrap:wrap; gap:8px 16px; font-size:.85em; color: var(--body-text-color-subdued); padding: 4px 2px; }
.sc-legend-item { display:inline-flex; align-items:center; gap:6px; cursor:help; }
.sc-dot { width:10px; height:10px; border-radius:50%; display:inline-block; flex:none; }

/* result panel */
#sc-result { min-height: 420px; }
.sc-empty { border: 2px dashed var(--border-color-primary); border-radius: var(--sc-radius); padding: 56px 24px; text-align:center;
  color: var(--body-text-color-subdued); min-height: 380px; display:flex; flex-direction:column; justify-content:center; align-items:center; gap:8px; }
.sc-empty-icon { font-size: 40px; }
.sc-empty-title { font-weight:700; font-size:1.15em; color: var(--body-text-color); }
.sc-empty-text { max-width: 420px; line-height:1.5; }

.sc-banner { display:flex; gap:14px; align-items:flex-start; padding:16px 18px; border-radius: var(--sc-radius); border:1px solid transparent; margin-bottom:14px; }
.sc-banner-icon { font-size: 26px; line-height:1; margin-top:2px; }
.sc-banner-title { font-weight:800; font-size:1.15em; margin-bottom:4px; }
.sc-banner-text { line-height:1.5; }
.sc-banner-warn { background: rgba(249,115,22,.10); border-color: rgba(249,115,22,.35); }
.sc-banner-ok { background: rgba(34,197,94,.10); border-color: rgba(34,197,94,.35); }
.sc-banner-error { background: rgba(127,127,127,.10); border-color: rgba(127,127,127,.35); }
.sc-chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
.sc-chip { color:#fff; font-size:.75em; font-weight:700; padding:3px 10px; border-radius:999px; letter-spacing:.02em; }

.sc-message { background: var(--block-background-fill); border:1px solid var(--border-color-primary); border-radius: var(--sc-radius); padding: 14px 18px 16px; margin-bottom:16px; }
.sc-message-label { font-size:.72em; text-transform:uppercase; letter-spacing:.08em; font-weight:700; color: var(--body-text-color-subdued); margin-bottom:8px; }
.sc-message-body { font-size: 1.05em; line-height: 1.9; white-space: normal; word-break: break-word; }
.sc-mark { color: inherit; padding: 2px 3px; border-radius: 4px; border-bottom: 2px solid; position: relative; }
.sc-tag { color:#fff; font-size:.62em; font-weight:700; padding:1px 6px; border-radius:999px; margin-left:4px; vertical-align: 2px; letter-spacing:.02em; white-space:nowrap; }

.sc-section-title { font-weight:800; font-size:1.05em; margin: 4px 0 10px; }
.sc-cards { display:grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap:14px; margin-bottom:16px; }
.sc-card { background: var(--block-background-fill); border:1px solid var(--border-color-primary); border-radius: var(--sc-radius); overflow:hidden;
  box-shadow: 0 1px 2px rgba(0,0,0,.04); display:flex; flex-direction:column; }
.sc-card-strip { height: 5px; }
.sc-card-body { padding: 12px 16px 14px; }
.sc-card-head { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
.sc-card-title { font-weight:800; font-size:1.02em; }
.sc-conf { margin-left:auto; display:inline-flex; align-items:center; gap:6px; font-size:.75em; color: var(--body-text-color-subdued); }
.sc-conf-bar { width:54px; height:6px; border-radius:999px; background: rgba(127,127,127,.2); overflow:hidden; }
.sc-conf-bar div { height:100%; border-radius:999px; }
.sc-def { font-size:.86em; color: var(--body-text-color-subdued); line-height:1.45; margin-bottom:8px; }
.sc-sub { font-size:.72em; text-transform:uppercase; letter-spacing:.08em; font-weight:700; color: var(--body-text-color-subdued); margin-top:10px; margin-bottom:4px; }
.sc-quotes { list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:6px; }
.sc-quote { display:inline-block; padding:3px 8px; border-radius:6px; border-left:3px solid; font-style: italic; line-height:1.45; }
.sc-expl { margin:0; line-height:1.5; }

.sc-next { background: rgba(99,102,241,.08); border:1px solid rgba(99,102,241,.3); border-radius: var(--sc-radius); padding: 12px 18px 12px; margin-bottom: 10px; }
.sc-next-title { font-weight:800; margin-bottom:6px; }
.sc-next ul { margin: 0 0 0 18px; padding:0; line-height:1.55; }
.sc-next li { margin: 2px 0; }
.sc-meta { font-size:.78em; color: var(--body-text-color-subdued); padding: 2px 4px; }

/* how it works */
.sc-how { font-size:.92em; line-height:1.55; }
.sc-steps { margin: 0 0 12px 18px; padding:0; }
.sc-steps li { margin: 4px 0; }
.sc-tax { width:100%; border-collapse: collapse; font-size:.9em; }
.sc-tax th, .sc-tax td { text-align:left; vertical-align:top; padding:8px 10px; border-top:1px solid var(--border-color-primary); }
.sc-tax th { font-size:.78em; text-transform:uppercase; letter-spacing:.06em; color: var(--body-text-color-subdued); border-top:none; }
.sc-tax td:first-child { white-space:nowrap; }
.sc-ex { color: var(--body-text-color-subdued); font-style: italic; }

.sc-disclaimer { font-size:.85em; color: var(--body-text-color-subdued); line-height:1.5; border-top:1px solid var(--border-color-primary); padding-top:12px; margin-top:8px; }

@media (max-width: 900px) { .sc-status { display:none; } }
"""


def build_app(initial_message: str | None = None) -> gr.Blocks:
    """Build the UI. `initial_message` pre-fills and pre-renders a result (used for previews)."""
    analyzer = get_analyzer()
    ok, _status = analyzer.provider.healthcheck()
    status = f"{analyzer.settings.preset} · {analyzer.provider.model}" if ok else "model offline · cached demos only"
    init_html, init_raw, init_text = EMPTY_STATE, None, ""
    if initial_message:
        init_text = initial_message
        init_html, init_raw = analyse(initial_message)

    with gr.Blocks(title="Scamantics") as demo:
        gr.HTML(header_html(status, ok))
        with gr.Row(equal_height=False):
            with gr.Column(scale=5, min_width=340):
                inp = gr.Textbox(
                    label="Message to analyse",
                    info="Paste a text message, email or chat message. English works best.",
                    placeholder="e.g. URGENT: your account will be suspended in 24 hours unless you verify now…",
                    lines=9,
                    max_lines=24,
                    autofocus=True,
                    value=init_text,
                    elem_id="sc-input",
                )
                with gr.Row():
                    btn = gr.Button("Analyse message", variant="primary", scale=3, elem_id="sc-analyse")
                    clear = gr.Button("Clear", variant="secondary", scale=1)
                gr.Examples(
                    examples=[[e] for e in EXAMPLES],
                    example_labels=EXAMPLE_LABELS,
                    inputs=[inp],
                    label="Try an example",
                    examples_per_page=8,
                )
                gr.HTML(legend_html())
                with gr.Accordion("How Scamantics works", open=False):
                    gr.HTML(how_it_works_html())
            with gr.Column(scale=7, min_width=380):
                result_html = gr.HTML(init_html, elem_id="sc-result")
                with gr.Accordion("Raw JSON result", open=False):
                    raw = gr.JSON(init_raw)
        gr.HTML(f"<div class='sc-disclaimer'><strong>Please note:</strong> {_esc(DISCLAIMER)}</div>")

        btn.click(analyse, inputs=[inp], outputs=[result_html, raw], api_name="analyse")
        inp.submit(analyse, inputs=[inp], outputs=[result_html, raw])
        clear.click(clear_all, outputs=[inp, result_html, raw])
    return demo


if __name__ == "__main__":
    ok, status = get_analyzer().provider.healthcheck()
    print(f"[scamantics] provider status: {status}")
    if not ok:
        print("[scamantics] WARNING: provider unavailable; only cached demo examples will work.")
    _app, local_url, share_url = build_app().launch(
        css=CSS,
        theme=gr.themes.Soft(primary_hue="indigo", neutral_hue="slate", radius_size="lg"),
        server_name=os.getenv("SCAMANTICS_HOST", "127.0.0.1"),
        server_port=int(os.getenv("SCAMANTICS_PORT", "7860")),
        share=os.getenv("SCAMANTICS_SHARE", "0") == "1",
        prevent_thread_lock=True,
    )
    print(f"[scamantics] local URL:  {local_url}", flush=True)
    print(f"[scamantics] public URL: {share_url or '(share disabled or tunnel failed)'}", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
