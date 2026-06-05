from pathlib import Path

import modal


DATA_PATH = "/tmp/kyc_training_data/offer_extraction_pairs.jsonl"
OUTPUT_DIR = "/tmp/kyc_unsloth_adapter"
BASE_MODEL = "Qwen/Qwen2.5-Coder-3B-Instruct"

image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "unsloth",
    "trl",
    "transformers",
    "datasets",
    "accelerate",
    "peft",
)

app = modal.App("kyc-unsloth-finetune", image=image)


@app.function(gpu="A100", timeout=7200)
def finetune_offer_extractor(data_path: str = DATA_PATH, output_dir: str = OUTPUT_DIR) -> dict:
    from datasets import load_dataset
    from trl import SFTTrainer, SFTConfig
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=4096,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=16,
        lora_dropout=0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )

    dataset = load_dataset("json", data_files=data_path, split="train")

    def format_example(example):
        return {
            "text": (
                "Extract credit-card offers from this messy email as strict JSON.\n"
                f"INPUT:\n{example['input']}\n"
                f"OUTPUT:\n{example['output']}"
            )
        }

    dataset = dataset.map(format_example)
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        args=SFTConfig(
            output_dir=output_dir,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=8,
            num_train_epochs=1,
            learning_rate=2e-4,
            logging_steps=10,
            save_steps=100,
        ),
    )
    trainer.train()
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    return {"adapter_dir": output_dir, "base_model": BASE_MODEL}


@app.local_entrypoint()
def main():
    print(finetune_offer_extractor.remote())
