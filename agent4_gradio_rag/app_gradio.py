import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import html
import json
from typing import Optional

import gradio as gr

from shared_core.database import DatabaseManager
from agent4_gradio_rag.kyc_rag_engine import KycRagEngine


CSS_PATH = "agent4_gradio_rag/static/kyc_theme.css"


def build_theme() -> gr.Theme:
    return gr.Theme(
        primary_hue="orange",
        secondary_hue="blue",
        neutral_hue="slate",
        font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui"],
    )


def load_css() -> str:
    with open(CSS_PATH, "r", encoding="utf-8") as handle:
        return handle.read()


def account_choices() -> list[str]:
    try:
        accounts = DatabaseManager().get_all_accounts()
        choices = [item["account_email"] for item in accounts]
        return choices or ["All local accounts"]
    except Exception:
        return ["All local accounts"]


def render_offers(engine: KycRagEngine, account_email: Optional[str]) -> str:
    offers = engine.active_offer_badges(None if account_email == "All local accounts" else account_email)
    if not offers:
        return "<div class='kyc-offer-meta'>No active local offers loaded.</div>"

    chunks = []
    for offer in offers:
        chunks.append(
            "<div class='kyc-offer-card'>"
            f"<span class='elemental-badge {html.escape(offer['badge_class'])}'>{html.escape(offer['category'])}</span>"
            f"<div class='kyc-offer-title'>{html.escape(offer['title'])}</div>"
            f"<div class='kyc-offer-meta'>{html.escape(offer['bank'])}</div>"
            "</div>"
        )
    return "\n".join(chunks)


def chat_turn(message, history, account_email, engine: KycRagEngine):
    selected_account = None if account_email == "All local accounts" else account_email
    try:
        result = engine.answer(message, account_email=selected_account)
        answer = result.get("answer", "I could not produce a local answer.")
    except Exception as exc:
        result = {
            "answer": f"Local inference is not ready: {exc}",
            "recommendations": [],
            "confidence": 0,
            "sources": [],
        }
        answer = result["answer"]

    history = history + [[message, answer]]
    return history, json.dumps(result, indent=2), render_offers(engine, selected_account)


def build_app() -> gr.Blocks:
    engine = KycRagEngine()
    with gr.Blocks(theme=build_theme(), css=load_css(), elem_classes=["kyc-shell"]) as app:
        with gr.Row():
            with gr.Column(scale=1, elem_classes=["kyc-sidebar"]):
                account = gr.Dropdown(
                    choices=account_choices(),
                    value=account_choices()[0],
                    label="Family Account",
                )
                refresh = gr.Button("Refresh Offers")

            with gr.Column(scale=2, elem_classes=["kyc-chat-pane"]):
                chatbot = gr.Chatbot(label="Know Your Card", height=520)
                question = gr.Textbox(
                    label="Ask",
                    placeholder="Which card should I use for a Rs 4,000 dining bill?",
                )
                json_out = gr.Code(label="Local JSON", language="json")

            with gr.Column(scale=1, elem_classes=["kyc-offers-pane"]):
                offers = gr.HTML(render_offers(engine, None))

        question.submit(
            fn=lambda msg, hist, acct: chat_turn(msg, hist, acct, engine),
            inputs=[question, chatbot, account],
            outputs=[chatbot, json_out, offers],
        ).then(lambda: "", outputs=[question])

        refresh.click(
            fn=lambda acct: render_offers(engine, None if acct == "All local accounts" else acct),
            inputs=[account],
            outputs=[offers],
        )

    return app


if __name__ == "__main__":
    DatabaseManager().initialize_schema()
    build_app().launch(server_name="0.0.0.0", server_port=7860)
