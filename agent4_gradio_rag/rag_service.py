import os
import json
from typing import List, Dict, Any, Optional, Generator
from openai import OpenAI
from shared_core.models import RetrievalAuditModel
from datetime import datetime


class RagService:
    def __init__(self, vector_store, conflict_detector, retrieval_planner,
                 prompt_builder, context_compressor, auditor):
        self.vector_store = vector_store
        self.conflict_detector = conflict_detector
        self.retrieval_planner = retrieval_planner
        self.prompt_builder = prompt_builder
        self.context_compressor = context_compressor
        self.auditor = auditor
        self._llm_client = None

    @property
    def llm_client(self):
        if self._llm_client is None:
            base_url = os.getenv("LMSTUDIO_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:1234/v1"))
            api_key = os.getenv("LMSTUDIO_API_KEY", os.getenv("OLLAMA_API_KEY", "lm-studio"))
            self._llm_client = OpenAI(base_url=base_url, api_key=api_key)
        return self._llm_client

    def classify_intent(self, user_input: str) -> tuple[str, str]:
        prompt = f"""You are a classifier. Given the user's message, output TWO things separated by a colon:
1. The intent: greeting, sync, reindex, search, or recommend
2. The search keyword: the specific bank/brand/product name. If none, write "all"

- greeting: User says hi/hello or casual conversation
- sync: User wants to fetch/load/check new emails from Gmail
- reindex: User wants to rebuild the vector index
- recommend: User wants to know which credit card to use for a purchase
- search: User asks about past emails, offers, or promotions

Examples:
"Hi there" → greeting:
"sync my emails" → sync:
"best card for Amazon 5000" → recommend:Amazon
"SBI offers" → search:SBI
"cashback on food delivery" → search:cashback food delivery

Reply with ONLY intent:keyword. Nothing else.

User message: {user_input}"""

        try:
            response = self.llm_client.chat.completions.create(
                model="phi4:14b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=20
            )
            raw = response.choices[0].message.content.strip().lower().rstrip(".")

            if ":" in raw:
                parts = raw.split(":", 1)
                intent = parts[0].strip()
                keyword = parts[1].strip() if len(parts) > 1 else ""
            else:
                intent = raw
                keyword = ""

            valid = {"greeting", "sync", "reindex", "recommend", "search"}
            if intent not in valid:
                if "greet" in intent: intent = "greeting"
                elif "sync" in intent or "fetch" in intent: intent = "sync"
                elif "reindex" in intent or "rebuild" in intent: intent = "reindex"
                elif "recommend" in intent: intent = "recommend"
                else: intent = "search"

            return intent, keyword

        except Exception:
            normalized = user_input.strip().lower()
            if normalized in {"hi", "hello", "hey"}:
                return "greeting", ""
            if any(kw in normalized for kw in ["sync", "fetch", "load"]):
                return "sync", ""
            if any(kw in normalized for kw in ["reindex", "rebuild"]):
                return "reindex", ""
            if any(kw in normalized for kw in ["best card", "which card", "recommend"]):
                return "recommend", ""
            return "search", ""

    def query(self, user_input: str, intent: str = None,
              user_id: int = None, user_cards: List[str] = None,
              conversation_history: List = None) -> Dict[str, Any]:
        start_time = datetime.utcnow()

        if intent is None:
            intent, keyword = self.classify_intent(user_input)
        else:
            keyword = ""

        if intent in ("greeting", "sync", "reindex"):
            return {"intent": intent, "keyword": keyword, "type": "command"}

        plan = self.retrieval_planner.plan(
            user_input, intent, conversation_history
        )

        results = self.vector_store.search(
            query=plan["query"],
            intent=plan["intent"],
            top_k=plan["top_k"],
            filters=plan.get("filters"),
        )

        conflicts = self.conflict_detector.detect(results, user_input)

        context = self.context_compressor.compress(results, user_input, intent)

        prompt = self.prompt_builder.build_prompt(
            query=user_input,
            context=context,
            intent=intent,
            conflicts=conflicts,
            results=results,
        )

        try:
            response = self.llm_client.chat.completions.create(
                model="llama3.2:3b-instruct",
                messages=[
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user", "content": prompt["user"]},
                ],
                temperature=0.1,
            )
            answer = response.choices[0].message.content or "I couldn't generate a response."
        except Exception as e:
            answer = f"Error communicating with LLM: {e}"

        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        if user_id:
            self.auditor.log_retrieval(
                user_id=user_id,
                query=user_input,
                intent=intent,
                plan_mode=plan.get("mode"),
                top_k_requested=plan["top_k"],
                raw_candidates_count=len(results),
                final_candidates_count=len(results),
                conflicts_detected=conflicts,
                llm_response_length=len(answer),
                response_time_ms=response_time,
            )

        return {
            "type": "answer",
            "intent": intent,
            "keyword": keyword,
            "answer": answer,
            "results_count": len(results),
            "conflicts": conflicts,
            "plan": plan,
        }

    def stream_query(self, user_input: str, intent: str = None,
                     user_id: int = None, user_cards: List[str] = None,
                     conversation_history: List = None) -> Generator[str, None, None]:
        result = self.query(user_input, intent, user_id, user_cards, conversation_history)

        if result["type"] == "command":
            yield f"data: {json.dumps(result)}\n\n"
            return

        answer = result["answer"]
        for i in range(0, len(answer), 20):
            chunk = answer[i:i+20]
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'meta': {
            'results_count': result['results_count'],
            'conflicts': len(result['conflicts']),
            'intent': result['intent'],
        }})}\n\n"
