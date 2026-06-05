import json
import os
from dataclasses import dataclass
from typing import Any, Optional


KYC_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["answer", "recommendations", "confidence", "sources"],
    "properties": {
        "answer": {"type": "string"},
        "confidence": {"type": "number"},
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["card_name", "reason", "category", "estimated_value"],
                "properties": {
                    "card_name": {"type": "string"},
                    "reason": {"type": "string"},
                    "category": {"type": "string"},
                    "estimated_value": {"type": "string"},
                },
            },
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source_type", "label"],
                "properties": {
                    "source_type": {"type": "string"},
                    "label": {"type": "string"},
                },
            },
        },
    },
}


JSON_OBJECT_GRAMMAR = r"""
root ::= object
value ::= object | array | string | number | ("true" | "false" | "null")
object ::= "{" ws (string ws ":" ws value (ws "," ws string ws ":" ws value)*)? ws "}"
array ::= "[" ws (value (ws "," ws value)*)? ws "]"
string ::= "\"" ([^"\\] | "\\" ["\\/bfnrt] | "\\u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F])* "\""
number ::= "-"? ([0-9] | [1-9] [0-9]*) ("." [0-9]+)? ([eE] [-+]? [0-9]+)?
ws ::= [ \t\n\r]*
"""


@dataclass
class LocalLlamaConfig:
    model_path: str
    n_ctx: int = 4096
    n_gpu_layers: int = 24
    temperature: float = 0.1
    max_tokens: int = 700


class LocalLlamaJsonGenerator:
    """Local GGUF inference with grammar-constrained JSON output."""

    def __init__(self, config: Optional[LocalLlamaConfig] = None):
        self.config = config or LocalLlamaConfig(
            model_path=os.getenv("KYC_GGUF_MODEL_PATH", "models/kyc-qwen3b-q4.gguf"),
            n_ctx=int(os.getenv("KYC_LLAMA_N_CTX", "4096")),
            n_gpu_layers=int(os.getenv("KYC_LLAMA_N_GPU_LAYERS", "24")),
        )
        self._llm = None
        self._grammar = None

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        llm = self._load()
        prompt = self._format_prompt(system_prompt, user_prompt)

        response = llm(
            prompt,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            grammar=self._grammar,
            stop=["<|im_end|>", "</s>"],
        )
        text = response["choices"][0]["text"]
        return self._parse_json(text)

    def _load(self):
        if self._llm is not None:
            return self._llm

        try:
            from llama_cpp import Llama, LlamaGrammar
        except ImportError as exc:
            raise RuntimeError(
                "llama-cpp-python is required for local inference. "
                "Install it in the local environment and set KYC_GGUF_MODEL_PATH."
            ) from exc

        self._grammar = LlamaGrammar.from_string(JSON_OBJECT_GRAMMAR)
        self._llm = Llama(
            model_path=self.config.model_path,
            n_ctx=self.config.n_ctx,
            n_gpu_layers=self.config.n_gpu_layers,
            verbose=False,
        )
        return self._llm

    def _format_prompt(self, system_prompt: str, user_prompt: str) -> str:
        return (
            "<|im_start|>system\n"
            f"{system_prompt}\n"
            "Return only a JSON object matching this schema:\n"
            f"{json.dumps(KYC_RESPONSE_SCHEMA)}\n"
            "<|im_end|>\n"
            "<|im_start|>user\n"
            f"{user_prompt}\n"
            "<|im_end|>\n"
            "<|im_start|>assistant\n"
        )

    def _parse_json(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start < 0 or end <= start:
            raise ValueError("Model did not return a JSON object")
        return json.loads(cleaned[start:end])
