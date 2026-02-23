"""
Fine-tuning Qwen2.5-1.5B با دیتاست‌های کرول شده از GitHub
این فایل رو در Google Colab اجرا کنید (در ۵ سل جدا)
"""

# ==========================================
# سل ۱: نصب پکیج‌ها
# ==========================================
"""
import os, json, glob, shutil

%cd /content

!nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
print("=" * 50)

!pip install llamafactory -q
!pip install bitsandbytes accelerate sentencepiece protobuf -q
!pip install peft datasets -q

print("✅ Phase 1 Done: Packages installed")
"""

# ==========================================
# سل ۲: آماده‌سازی دیتاست
# ==========================================
"""
import os, json, glob

%cd /content

assert os.path.exists("datasets.zip"), "❌ datasets.zip آپلود نشده!"

!rm -rf /content/data /content/raw_data
!mkdir -p /content/data
!unzip -o datasets.zip -d /content/raw_data

# تبدیل به فرمت واحد
unified_data = []

all_files = glob.glob("/content/raw_data/**/*.jsonl", recursive=True) + \
            glob.glob("/content/raw_data/**/*.json", recursive=True)
all_files = [f for f in all_files if "dataset_info" not in os.path.basename(f)]

print(f"📁 Found {len(all_files)} data file(s):")

for filepath in all_files:
    fname = os.path.basename(filepath)
    count = 0
    errors = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)

                if "instruction" in obj and "output" in obj:
                    unified_data.append({
                        "instruction": str(obj.get("instruction", "")),
                        "input":       str(obj.get("input", "")),
                        "output":      str(obj.get("output", ""))
                    })
                    count += 1
                elif "question" in obj and "answer" in obj:
                    unified_data.append({
                        "instruction": str(obj.get("question", "")),
                        "input":       str(obj.get("context", "")),
                        "output":      str(obj.get("answer", ""))
                    })
                    count += 1
                else:
                    errors += 1

            except json.JSONDecodeError:
                errors += 1

    print(f"  📄 {fname}: {count} samples, {errors} errors")

# ذخیره
output_path = "/content/data/train_data.jsonl"
with open(output_path, "w", encoding="utf-8") as f:
    for item in unified_data:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print(f"\\n📊 Total samples: {len(unified_data)}")

# ساخت dataset_info.json
info = {
    "my_data": {
        "file_name": "train_data.jsonl",
        "formatting": "alpaca",
        "columns": {
            "prompt": "instruction",
            "query": "input",
            "response": "output"
        }
    }
}
with open("/content/data/dataset_info.json", "w") as f:
    json.dump(info, f, indent=2)

print("✅ Phase 2 Done: Dataset prepared")
"""

# ==========================================
# سل ۳: آموزش مدل
# ==========================================
"""
import torch
from transformers import (
    AutoModelForCausalLM, AutoTokenizer,
    TrainingArguments, Trainer, DataCollatorForSeq2Seq,
    BitsAndBytesConfig
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from datasets import load_dataset

# تنظیمات
MODEL = "Qwen/Qwen2.5-1.5B"
MAX_SAMPLES = 5000  # برای Colab رایگان
MAX_LENGTH = 512

print(f"🚀 Phase 3: Fine-tuning {MODEL}")
print(f"📊 GPU: {torch.cuda.get_device_properties(0).name}")
print(f"📊 VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

# Tokenizer
print("\\n1️⃣ Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.pad_token_id = tokenizer.eos_token_id

# Model (4-bit)
print("2️⃣ Loading model in 4-bit...")
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True,
)
model = prepare_model_for_kbit_training(model)

# LoRA
print("3️⃣ Applying LoRA...")
lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# Dataset
print("4️⃣ Loading dataset...")
dataset = load_dataset("json", data_files="/content/data/train_data.jsonl", split="train")
print(f"   Total samples: {len(dataset)}")

if len(dataset) > MAX_SAMPLES:
    dataset = dataset.shuffle(seed=42).select(range(MAX_SAMPLES))
    print(f"   Trimmed to: {len(dataset)} samples")

def format_and_tokenize(example):
    instruction = example.get("instruction", "").strip()
    inp = example.get("input", "").strip()
    output = example.get("output", "").strip()

    if inp:
        text = f"<|im_start|>user\\n{instruction}\\n\\nContext: {inp}<|im_end|>\\n<|im_start|>assistant\\n{output}<|im_end|>"
    else:
        text = f"<|im_start|>user\\n{instruction}<|im_end|>\\n<|im_start|>assistant\\n{output}<|im_end|>"

    tokenized = tokenizer(text, truncation=True, max_length=MAX_LENGTH, padding=False)
    tokenized["labels"] = tokenized["input_ids"].copy()
    return tokenized

print("5️⃣ Tokenizing...")
dataset = dataset.map(format_and_tokenize, remove_columns=dataset.column_names, desc="Tokenizing")

# Training
print("6️⃣ Starting training...")
training_args = TrainingArguments(
    output_dir="/content/lora_output",
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    num_train_epochs=1,
    learning_rate=2e-4,
    fp16=True,
    logging_steps=10,
    save_strategy="epoch",
    save_total_limit=1,
    lr_scheduler_type="cosine",
    warmup_ratio=0.1,
    gradient_checkpointing=True,
    optim="adamw_8bit",
    report_to="none",
    max_grad_norm=0.3,
    weight_decay=0.001,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    data_collator=DataCollatorForSeq2Seq(tokenizer, pad_to_multiple_of=8, return_tensors="pt", padding=True),
)

train_result = trainer.train()

model.save_pretrained("/content/lora_output")
tokenizer.save_pretrained("/content/lora_output")

print(f"\\n📊 Training Loss: {train_result.training_loss:.4f}")
print("✅ Phase 3 Done: Training completed")
"""

# ==========================================
# سل ۴: ادغام LoRA با مدل اصلی
# ==========================================
"""
import torch, gc
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

print("🔗 Phase 4: Merging LoRA...")

gc.collect()
torch.cuda.empty_cache()

print("  Loading base model on CPU...")
base_model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-1.5B",
    torch_dtype=torch.float16,
    device_map="cpu",
    trust_remote_code=True,
)
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B", trust_remote_code=True)

print("  Merging adapter...")
model = PeftModel.from_pretrained(base_model, "/content/lora_output")
model = model.merge_and_unload()

print("  Saving merged model...")
model.save_pretrained("/content/merged_model")
tokenizer.save_pretrained("/content/merged_model")

del model, base_model
gc.collect()

print("✅ Phase 4 Done: Model merged")
"""

# ==========================================
# سل ۵: تبدیل به GGUF
# ==========================================
"""
import os, glob

print("📐 Phase 5: Converting to GGUF...")

!rm -rf /content/llama.cpp
!git clone --depth 1 https://github.com/ggerganov/llama.cpp.git
!pip install -r /content/llama.cpp/requirements.txt -q 2>/dev/null
!pip install gguf -q

# پیدا کردن اسکریپت
convert_script = None
for name in ["convert_hf_to_gguf.py", "convert-hf-to-gguf.py"]:
    path = f"/content/llama.cpp/{name}"
    if os.path.exists(path):
        convert_script = path
        break

assert convert_script, "❌ Convert script not found!"

print(f"Using: {convert_script}")
!python {convert_script} /content/merged_model --outfile /content/my_finetuned_model.gguf --outtype q8_0

if os.path.exists("/content/my_finetuned_model.gguf"):
    size_mb = os.path.getsize("/content/my_finetuned_model.gguf") / (1024**2)
    print(f'''
{'='*50}
🎉 تمام شد!

📁 فایل:  my_finetuned_model.gguf
📏 حجم:   {size_mb:.0f} MB
📊 مدل:   Qwen2.5-1.5B + LoRA fine-tuned

📥 از پنل فایل سمت چپ Colab دانلود کنید

💡 قابل استفاده در:
   • LM Studio
   • Ollama
   • llama.cpp
{'='*50}
''')
else:
    print("❌ Conversion failed!")
"""