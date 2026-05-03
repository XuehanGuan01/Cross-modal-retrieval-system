"""
PlantNet300K 专用索引构建脚本
=============================
基于 build_index.py 的架构，为 PlantNet300K 数据集定制：
  - 图片目录：backend/gallery/plant/
  - 元数据源：backend/data/plant/metadata.json  （由 build_plantnet_metadata.py 生成）
  - 输出目录：backend/data/plant/
  - caption 格式: "物种命名：xxx，植物部位：xxx"

用法：
    cd backend
    python scripts/build_plantnet300k_index.py
    python scripts/build_plantnet300k_index.py --batch-size 64
    python scripts/build_plantnet300k_index.py --device cuda
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import faiss
import numpy as np
from PIL import Image
import torch

# 确保 backend 在 path 中
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from core.model_loader import CNClipModelLoader


# ==================== 路径约定 ====================
GALLERY_PLANT = BACKEND_ROOT / "gallery" / "plant"
DATA_DIR = BACKEND_ROOT / "data" / "plant"
INDEX_OUT = DATA_DIR / "images.index"
METADATA_OUT = DATA_DIR / "metadata.json"

# 元数据源：由 build_plantnet_metadata.py 生成的完整备份
PROJECT_ROOT = BACKEND_ROOT.parent
FULL_META_PATH = PROJECT_ROOT / "data" / "plantnet300K_image_metadata_full.json"


def load_plantnet_metadata() -> Dict[str, dict]:
    """
    加载 PlantNet300K 元数据（由 build_plantnet_metadata.py 生成的 hash 索引文件）。
    返回以 image_hash 为 key 的字典。
    """
    if not FULL_META_PATH.exists():
        raise FileNotFoundError(
            f"元数据文件不存在: {FULL_META_PATH}\n"
            f"请先运行: python manual/scripts/build_plantnet_metadata.py"
        )

    with open(FULL_META_PATH, "r", encoding="utf-8") as f:
        hash_index: Dict[str, dict] = json.load(f)

    print(f"[metadata] 加载 {len(hash_index):,} 条元数据")
    return hash_index


def find_images(gallery_dir: Path) -> List[Path]:
    """递归搜索所有 jpg/jpeg/png/webp 图片"""
    paths = []
    exts = ["jpg", "jpeg", "png", "webp"]
    for ext in exts:
        paths.extend(gallery_dir.rglob(f"*.{ext}"))
    return sorted(paths)


def hash_from_path(filepath: Path) -> str:
    """从文件名提取 hash（如 01aca26dc...jpg → 01aca26dc...）"""
    return filepath.stem


def build_index(
    checkpoint: str,
    batch_size: int = 32,
    device: str = "auto",
) -> None:
    """
    为 PlantNet300K 构建 FAISS 索引 + 元数据。
    """
    # ==== 设备 ====
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    # ==== 加载元数据 ====
    print(f"[PlantNet300K] 加载元数据: {METADATA_PATH}")
    meta_index = load_plantnet_metadata()

    # ==== 扫描图片 ====
    if not GALLERY_PLANT.exists():
        raise FileNotFoundError(
            f"图片目录不存在: {GALLERY_PLANT}\n"
            f"请先运行: python manual/scripts/extract_plantnet_parquet.py"
        )

    print(f"[PlantNet300K] 扫描图片: {GALLERY_PLANT}")
    image_paths = find_images(GALLERY_PLANT)
    total = len(image_paths)

    if total == 0:
        raise RuntimeError(f"未找到任何图片文件于 {GALLERY_PLANT}")

    print(f"[PlantNet300K] 共 {total:,} 张图片")

    # ==== 加载 CN-CLIP ====
    print(f"[PlantNet300K] 加载 CN-CLIP: checkpoint={checkpoint}, device={device}")
    model_loader = CNClipModelLoader(
        model_name="ViT-B-16",
        checkpoint_path=checkpoint,
        device=device,
    )

    # ==== 提取图像特征 + 构建元数据 ====
    all_embeddings: List[np.ndarray] = []
    output_metadata: List[dict] = []
    skipped_no_meta = 0
    skipped_bad_image = 0

    for start in range(0, total, batch_size):
        batch_paths = image_paths[start : start + batch_size]
        images = []
        valid_paths = []

        for p in batch_paths:
            # 查找元数据
            img_hash = hash_from_path(p)
            meta = meta_index.get(img_hash)

            if meta is None:
                skipped_no_meta += 1
                continue  # 无元数据的跳过

            try:
                img = Image.open(p).convert("RGB")
                images.append(img)
                valid_paths.append((p, meta))
            except Exception:
                skipped_bad_image += 1
                continue

        if not images:
            continue

        # 编码图像
        image_tensors = [model_loader.preprocess(img) for img in images]
        image_batch = torch.stack(image_tensors, dim=0)

        with torch.no_grad():
            embeddings = model_loader.encode_image(image_batch)

        embeddings_np = embeddings.cpu().numpy().astype("float32")
        all_embeddings.append(embeddings_np)

        # 记录元数据（格式对齐 v2 规范）
        for p, meta in valid_paths:
            rel_path = os.path.relpath(p, GALLERY_PLANT).replace(os.sep, "/")
            output_metadata.append({
                "id": meta.get("id", len(output_metadata)),
                "path": rel_path,
                "caption": meta.get("caption", ""),
                "domain": "plant",
                "attributes": {
                    "species_id": meta.get("species_id", ""),
                    "scientific_name": meta.get("scientific_name", ""),
                    "chinese_name": meta.get("chinese_name", ""),
                    "organ": meta.get("organ", ""),
                    "organ_cn": meta.get("organ_cn", ""),
                    "author": meta.get("author", ""),
                    "license": meta.get("license", ""),
                },
                "source": "PlantNet300K",
            })

        pct = min(start + batch_size, total) / total * 100
        print(f"[PlantNet300K] {min(start + batch_size, total):,}/{total:,} ({pct:.1f}%)"
              f" | 有效: {len(output_metadata):,}")

    if not all_embeddings:
        raise RuntimeError("未成功提取到任何特征向量！")

    # ==== 构建 FAISS 索引 ====
    embeddings_matrix = np.vstack(all_embeddings).astype("float32")
    dim = embeddings_matrix.shape[1]
    print(f"[PlantNet300K] 构建 FAISS IndexFlatIP, dim={dim}, vectors={embeddings_matrix.shape[0]:,}")

    index = faiss.IndexFlatIP(dim)
    index.add(embeddings_matrix)

    # ==== 写入文件 ====
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[PlantNet300K] 写入索引: {INDEX_OUT}")
    faiss.write_index(index, str(INDEX_OUT))

    print(f"[PlantNet300K] 写入元数据: {METADATA_OUT}")
    with open(METADATA_OUT, "w", encoding="utf-8") as f:
        json.dump(output_metadata, f, ensure_ascii=False, indent=2)

    # ==== 汇总 ====
    print("\n" + "=" * 60)
    print(f"[PlantNet300K] 索引构建完成!")
    print(f"  图片总数:     {total:,}")
    print(f"  成功编码:     {len(output_metadata):,}")
    print(f"  无元数据跳过: {skipped_no_meta:,}")
    print(f"  损坏图片:     {skipped_bad_image:,}")
    print(f"  向量维度:     {dim}")
    print(f"  索引文件:     {INDEX_OUT}")
    print(f"  元数据文件:   {METADATA_OUT}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="PlantNet300K FAISS 索引构建")
    parser.add_argument("--checkpoint", type=str, default="model/epoch_latest.pt",
                        help="CN-CLIP 权重文件路径")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", type=str, default="auto",
                        help="cpu / cuda / auto")
    args = parser.parse_args()
    build_index(args.checkpoint, args.batch_size, args.device)


if __name__ == "__main__":
    main()
