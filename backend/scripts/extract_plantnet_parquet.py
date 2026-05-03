"""
PlantNet300K Parquet → 图片文件提取脚本
==========================================
从 HuggingFace 缓存的 67 个 Parquet 文件中提取 image.bytes，
保存到 backend/gallery/plant/。

用法:
    python "C:/Users/Lenovo/Desktop/manual/scripts/extract_plantnet_parquet.py"
    python "C:/Users/Lenovo/Desktop/manual/scripts/extract_plantnet_parquet.py" --test --limit 100
    python "C:/Users/Lenovo/Desktop/manual/scripts/extract_plantnet_parquet.py" --splits train
"""

import argparse
import io
import json
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pyarrow.parquet as pq
from PIL import Image

# ==================== 固定路径 ====================
PROJECT_ROOT = Path("C:/Users/Lenovo/Desktop/Cross-modal retrieval system")
BACKEND_ROOT = PROJECT_ROOT / "backend"
GALLERY_PLANT = BACKEND_ROOT / "gallery" / "plant"
DATA_ROOT = PROJECT_ROOT / "data"

# HuggingFace 缓存
HF_PARQUET_DIR = Path.home() / ".cache" / "huggingface" / "hub" / \
    "datasets--mikehemberger--plantnet300K" / "snapshots" / \
    "cee4086ba902c7663483de51d5e518be9f5fe26a" / "data"

MANUAL_ROOT = Path("C:/Users/Lenovo/Desktop/manual")
PROGRESS_FILE = MANUAL_ROOT / "extraction_progress.json"


def find_parquet_files(splits=None):
    if not HF_PARQUET_DIR.exists():
        raise FileNotFoundError(
            f"Parquet 缓存目录不存在:\n  {HF_PARQUET_DIR}\n"
            f"请先运行 download_plantDataset.py 下载数据集"
        )
    files = sorted(HF_PARQUET_DIR.glob("*.parquet"))
    if splits:
        files = [f for f in files if any(f.name.startswith(s) for s in splits)]
    return files


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"extracted_files": [], "total_extracted": 0, "total_skipped": 0, "total_errors": 0}


def save_progress(p):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="PlantNet300K Parquet → 图片提取")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--splits", type=str, default="")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    splits = [s.strip() for s in args.splits.split(",") if s.strip()] if args.splits else None
    parquet_files = find_parquet_files(splits)

    print("=" * 60)
    print(f"PlantNet300K Parquet → 图片提取")
    print(f"Parquet 源:  {HF_PARQUET_DIR}")
    print(f"文件数:     {len(parquet_files)}")
    print(f"图片目标:   {GALLERY_PLANT}")
    if args.test:
        print(f"模式:       测试 (limit={args.limit or 100})")
    else:
        print(f"模式:       完整提取 (~306,146 张, ~30 GB)")
    print("=" * 60)

    GALLERY_PLANT.mkdir(parents=True, exist_ok=True)

    if args.no_resume:
        progress = {"extracted_files": [], "total_extracted": 0, "total_skipped": 0, "total_errors": 0}
    else:
        progress = load_progress()
    existing_set = set(progress.get("extracted_files", []))
    if existing_set:
        print(f"[续跑] 已有 {len(existing_set):,} 张，将跳过\n")

    total_new = progress["total_extracted"]
    total_skip = progress["total_skipped"]
    total_err = progress["total_errors"]
    start_time = time.time()
    checkpoint_interval = 5000

    for pf_idx, pf in enumerate(parquet_files):
        print(f"[{pf_idx+1}/{len(parquet_files)}] {pf.name}  ", end="", flush=True)

        try:
            table = pq.read_table(pf)
        except Exception as e:
            print(f"读取失败: {e}")
            continue

        file_new, file_skip = 0, 0
        for i in range(table.num_rows):
            if args.test and args.limit and total_new >= args.limit:
                break

            try:
                row = table.column("image")[i].as_py()
                img_path = row["path"]
                img_bytes = row["bytes"]

                if img_path in existing_set:
                    total_skip += 1
                    file_skip += 1
                    continue

                dest = GALLERY_PLANT / img_path
                img = Image.open(io.BytesIO(img_bytes))
                img.save(dest)
                total_new += 1
                file_new += 1
                existing_set.add(img_path)

                if total_new % checkpoint_interval == 0:
                    elapsed = time.time() - start_time
                    rate = total_new / elapsed if elapsed > 0 else 0
                    eta_min = (306146 - total_new - total_skip) / rate / 60 if rate > 0 else 0
                    progress.update({
                        "extracted_files": list(existing_set),
                        "total_extracted": total_new, "total_skipped": total_skip,
                        "total_errors": total_err,
                    })
                    save_progress(progress)
                    print(f"\n  [checkpoint] 已提取 {total_new:,} | "
                          f"速率 {rate:.0f}/s | 预计剩余 {eta_min:.0f}min")

            except Exception as e:
                total_err += 1
                if total_err <= 20:
                    print(f"\n  !! row {i}: {e}")
                continue

        print(f" → 提取 {file_new} | 跳过 {file_skip} | 累计 {total_new:,}")

        if args.test and args.limit and total_new >= args.limit:
            print(f"[测试] 达到 limit={args.limit}")
            break

    elapsed = time.time() - start_time
    progress.update({
        "extracted_files": list(existing_set),
        "total_extracted": total_new, "total_skipped": total_skip,
        "total_errors": total_err, "elapsed_seconds": round(elapsed, 1),
        "gallery_dir": str(GALLERY_PLANT),
    })
    save_progress(progress)

    print("\n" + "=" * 60)
    print(f"[完成]")
    print(f"  新提取: {total_new:,} 张")
    print(f"  跳过:   {total_skip:,} 张")
    print(f"  错误:   {total_err}")
    print(f"  耗时:   {elapsed/60:.1f} 分钟")
    print(f"  目录:   {GALLERY_PLANT}")
    print("=" * 60)


if __name__ == "__main__":
    main()
