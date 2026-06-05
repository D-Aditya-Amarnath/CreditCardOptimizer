import modal


BASE_MODEL = "Qwen/Qwen2.5-Coder-3B-Instruct"
ADAPTER_DIR = "/tmp/kyc_unsloth_adapter"
MERGED_DIR = "/tmp/kyc_merged_model"
GGUF_DIR = "/tmp/kyc_gguf"

image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "unsloth",
    "transformers",
    "peft",
    "huggingface_hub",
)

app = modal.App("kyc-export-gguf", image=image)


@app.function(gpu="A100", timeout=3600)
def export_q4_gguf(adapter_dir: str = ADAPTER_DIR, gguf_dir: str = GGUF_DIR) -> dict:
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=adapter_dir,
        max_seq_length=4096,
        load_in_4bit=True,
    )
    model.save_pretrained_gguf(
        gguf_dir,
        tokenizer,
        quantization_method="q4_k_m",
    )
    return {
        "gguf_dir": gguf_dir,
        "local_download_hint": "modal volume get or modal function artifact download into ./models/",
    }


@app.local_entrypoint()
def main():
    print(export_q4_gguf.remote())
