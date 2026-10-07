"""Launch the UI with a pre-rendered example result, for screenshots and styling work.

    SCAMANTICS_PROVIDER=mock python scripts/ui_preview.py [example-index] [port]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gradio as gr  # noqa: E402

from app import CSS, EXAMPLES, build_app  # noqa: E402

idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
port = int(sys.argv[2]) if len(sys.argv) > 2 else 7862
message = EXAMPLES[idx] if idx >= 0 else None
build_app(initial_message=message).launch(
    css=CSS,
    theme=gr.themes.Soft(primary_hue="indigo", neutral_hue="slate", radius_size="lg"),
    server_name="127.0.0.1",
    server_port=port,
    prevent_thread_lock=True,
)
print(f"[preview] http://127.0.0.1:{port}/", flush=True)
while True:
    time.sleep(3600)
