#!/usr/bin/env python3
"""
Dataset Generator - Main Entry Point
Generates 3 datasets from Gitea crawled data:
1. Instruction Dataset (code generation)
2. QA Dataset (question answering)
3. Debug Dataset (debugging & code review)
"""

import json
import os
import sys
from config import Config
from generate_instruction import InstructionDatasetGenerator
from generate_qa import QADatasetGenerator
from generate_debug import DebugDatasetGenerator


def save_jsonl(data, filepath):
    """ذخیره به فرمت JSONL (هر خط یک JSON)"""
    with open(filepath, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def merge_datasets():
    """ادغام سه دیتاست در یک فایل کامل"""
    print("\n" + "=" * 60)
    print("🔗 MERGING ALL DATASETS")
    print("=" * 60)

    merged = []
    files = [
        "instruction_dataset.jsonl",
        "qa_dataset.jsonl",
        "debug_dataset.jsonl",
    ]

    for filename in files:
        filepath = os.path.join(Config.OUTPUT_DIR, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = [json.loads(line) for line in f if line.strip()]
                merged.extend(data)
                print(f"   📄 {filename}: {len(data)} samples")

    # ذخیره فایل ادغام شده (با metadata)
    merged_path = os.path.join(Config.OUTPUT_DIR, "full_dataset.jsonl")
    save_jsonl(merged, merged_path)

    print(f"\n   ✅ Merged dataset: {len(merged)} total samples")
    print(f"   💾 Saved to: {merged_path}")

    # ساخت نسخه Alpaca-compatible (بدون فیلدهای اضافی)
    alpaca_dataset = []
    for item in merged:
        alpaca_dataset.append({
            "instruction": item["instruction"],
            "input": item.get("input", ""),
            "output": item["output"],
        })

    alpaca_path = os.path.join(Config.OUTPUT_DIR, "alpaca_format_dataset.jsonl")
    save_jsonl(alpaca_dataset, alpaca_path)

    print(f"   💾 Alpaca format: {alpaca_path}")

    return merged


def print_stats(merged):
    """نمایش آمار نهایی"""
    print("\n" + "=" * 60)
    print("📊 FINAL STATISTICS")
    print("=" * 60)

    # By source
    sources = {}
    for item in merged:
        s = item.get("source", "unknown")
        sources[s] = sources.get(s, 0) + 1

    print("\n📦 By Source:")
    for s, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"   {s}: {count}")

    # By type
    types = {}
    for item in merged:
        t = item.get("type", "unknown")
        types[t] = types.get(t, 0) + 1

    print("\n🏷️ By Type:")
    for t, count in sorted(types.items(), key=lambda x: -x[1]):
        print(f"   {t}: {count}")

    # Avg lengths
    avg_instruction = sum(len(i["instruction"]) for i in merged) / max(len(merged), 1)
    avg_input = sum(len(i.get("input", "")) for i in merged) / max(len(merged), 1)
    avg_output = sum(len(i["output"]) for i in merged) / max(len(merged), 1)

    print(f"\n📏 Average Lengths:")
    print(f"   Instruction: {avg_instruction:.0f} chars")
    print(f"   Input: {avg_input:.0f} chars")
    print(f"   Output: {avg_output:.0f} chars")

    # Sample
    print(f"\n📝 Sample Entry:")
    if merged:
        sample = merged[0]
        print(f"   Instruction: {sample['instruction'][:100]}...")
        print(f"   Input: {sample.get('input', '')[:100]}...")
        print(f"   Output: {sample['output'][:100]}...")


def main():
    print("=" * 60)
    print("🏭 DATASET GENERATOR")
    print(f"   Repo: {Config.GITEA_ORG}/{Config.REPO_NAME}")
    print(f"   Gitea: {Config.GITEA_URL}")
    print(f"   Output: {Config.OUTPUT_DIR}/")
    print("=" * 60)

    if not Config.GITEA_TOKEN:
        print("❌ GITEA_TOKEN not set in .env")
        sys.exit(1)

    # 1. Instruction Dataset
    print("\n\n" + "🔵" * 30)
    instruction_gen = InstructionDatasetGenerator()
    instruction_gen.generate()

    # 2. QA Dataset
    print("\n\n" + "🟢" * 30)
    qa_gen = QADatasetGenerator()
    qa_gen.generate()

    # 3. Debug Dataset
    print("\n\n" + "🔴" * 30)
    debug_gen = DebugDatasetGenerator()
    debug_gen.generate()

    # 4. Merge
    merged = merge_datasets()

    # 5. Stats
    print_stats(merged)

    print(f"\n\n{'='*60}")
    print(f"✅ ALL DATASETS GENERATED SUCCESSFULLY!")
    print(f"{'='*60}")
    print(f"\n📁 Output files:")
    print(f"   {Config.OUTPUT_DIR}/instruction_dataset.jsonl")
    print(f"   {Config.OUTPUT_DIR}/qa_dataset.jsonl")
    print(f"   {Config.OUTPUT_DIR}/debug_dataset.jsonl")
    print(f"   {Config.OUTPUT_DIR}/full_dataset.jsonl")
    print(f"   {Config.OUTPUT_DIR}/alpaca_format_dataset.jsonl  ← برای Fine-tuning")


if __name__ == "__main__":
    main()