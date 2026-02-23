
## ۲. `prepare_dataset.py`


#!/usr/bin/env python3
"""
آماده‌سازی دیتاست برای Fine-tuning
این اسکریپت فایل دیتاست رو ZIP میکنه برای آپلود به Colab
"""

import os
import shutil
import zipfile


def main():
    print("=" * 60)
    print("📦 PREPARE DATASET FOR FINE-TUNING")
    print("=" * 60)

    # مسیرها
    dataset_source = "../dataset-generator/datasets/alpaca_format_dataset.jsonl"
    output_dir = "data"
    zip_file = "datasets.zip"

    # چک کردن وجود فایل منبع
    if not os.path.exists(dataset_source):
        print(f"❌ فایل دیتاست پیدا نشد: {dataset_source}")
        print("   ابتدا مرحله dataset-generator رو اجرا کن!")
        return False

    # ساخت پوشه خروجی
    os.makedirs(output_dir, exist_ok=True)

    # کپی فایل
    dest_file = os.path.join(output_dir, "alpaca_format_dataset.jsonl")
    print(f"\n📄 کپی دیتاست...")
    print(f"   از: {dataset_source}")
    print(f"   به: {dest_file}")
    shutil.copy2(dataset_source, dest_file)

    # شمارش نمونه‌ها
    with open(dest_file, "r", encoding="utf-8") as f:
        sample_count = sum(1 for line in f if line.strip())
    print(f"   📊 تعداد نمونه‌ها: {sample_count}")

    # ساخت ZIP
    print(f"\n📦 ساخت {zip_file}...")
    with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(dest_file, "alpaca_format_dataset.jsonl")

    zip_size = os.path.getsize(zip_file) / (1024 * 1024)
    print(f"   ✅ فایل ZIP ساخته شد: {zip_file} ({zip_size:.2f} MB)")

    print(f"\n{'='*60}")
    print("✅ آماده‌سازی کامل شد!")
    print(f"{'='*60}")
    print(f"""
📋 مراحل بعدی:

1️⃣  فایل {zip_file} رو به Google Colab آپلود کن

2️⃣  کد colab_notebook/finetune_qwen.py رو اجرا کن

3️⃣  فایل my_finetuned_model.gguf رو دانلود کن
""")

    return True


if __name__ == "__main__":
    main()