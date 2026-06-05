import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from models import RetrievalAuditModel


class RetrievalAuditor:
    def log_retrieval(self, user_id: Optional[int], query: str, intent: str,
                      plan_mode: str, top_k_requested: int,
                      raw_candidates_count: int, final_candidates_count: int,
                      prefilter_rejected: List[Dict] = None,
                      rerank_applied: bool = False,
                      conflicts_detected: List[Dict] = None,
                      llm_response_length: int = 0,
                      response_time_ms: float = 0.0,
                      error: str = None):
        from database import DatabaseManager
        try:
            db = DatabaseManager()
            log = RetrievalAuditModel(
                user_id=user_id,
                query=query,
                intent=intent,
                plan_mode=plan_mode,
                top_k_requested=top_k_requested,
                raw_candidates_count=raw_candidates_count,
                final_candidates_count=final_candidates_count,
                prefilter_rejected=prefilter_rejected,
                rerank_applied=rerank_applied,
                conflicts_detected=conflicts_detected,
                llm_response_length=llm_response_length,
                response_time_ms=response_time_ms,
                error=error,
            )
            db.insert_audit_log(log)
        except Exception:
            pass

    def get_audit_summary(self, db_manager, user_id: int = None, limit: int = 100) -> Dict[str, Any]:
        logs = db_manager.get_audit_logs(user_id=user_id, limit=limit)

        if not logs:
            return {
                "total_queries": 0,
                "avg_response_time_ms": 0,
                "conflict_rate": 0,
                "top_intents": {},
                "recent_queries": [],
            }

        total = len(logs)
        avg_time = sum(l.response_time_ms or 0 for l in logs) / total
        conflicts = sum(1 for l in logs if l.conflicts_detected)

        intent_counts = {}
        for l in logs:
            intent_counts[l.intent] = intent_counts.get(l.intent, 0) + 1

        return {
            "total_queries": total,
            "avg_response_time_ms": round(avg_time, 1),
            "conflict_rate": round(conflicts / total * 100, 1),
            "top_intents": intent_counts,
            "recent_queries": [
                {
                    "query": l.query,
                    "intent": l.intent,
                    "timestamp": l.timestamp.isoformat(),
                    "results_count": l.final_candidates_count,
                    "response_time_ms": l.response_time_ms,
                }
                for l in logs[:10]
            ],
        }
