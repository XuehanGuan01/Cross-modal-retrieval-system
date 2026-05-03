"""
AWA2 动物数据集 FAISS 索引构建脚本
==================================
基于 build_plantnet300k_index.py 架构，为 AWA2 动物数据集定制：
  - 图片目录：backend/gallery/animal/
  - 元数据源：data/awa2_image_metadata_full.json （由 build_awa2_metadata.py 生成）
  - 输出目录：backend/data/animal/
  - 元数据 key：相对路径（非 hash）

用法：
    cd backend
    python scripts/build_awa2_index.py
    python scripts/build_awa2_index.py --batch-size 64
    python scripts/build_awa2_index.py --device cuda
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

import faiss
import numpy as np
from PIL import Image
import torch

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from core.model_loader import CNClipModelLoader

# ==================== 路径约定 ====================
GALLERY_ANIMAL = BACKEND_ROOT / "gallery" / "animal"
DATA_DIR = BACKEND_ROOT / "data" / "animal"
INDEX_OUT = DATA_DIR / "images.index"
METADATA_OUT = DATA_DIR / "metadata.json"

PROJECT_ROOT = BACKEND_ROOT.parent
FULL_META_PATH = PROJECT_ROOT / "data" / "awa2_image_metadata_full.json"


def load_awa2_metadata() -> Dict[str, dict]:
    """加载 AWA2 元数据（key 为相对路径）"""
    if not FULL_META_PATH.exists():
        raise FileNotFoundError(
            f"元数据文件不存在: {FULL_META_PATH}\n"
            f"请先运行: python scripts/build_awa2_metadata.py"
        )

    with open(FULL_META_PATH, "r", encoding="utf-8") as f:
        path_index: Dict[str, dict] = json.load(f)

    print(f"[metadata] 加载 {len(path_index):,} 条元数据")
    return path_index


def find_images(gallery_dir: Path) -> List[Path]:
    """递归搜索所有 jpg/jpeg/png/webp 图片"""
    paths = []
    for ext in ["jpg", "jpeg", "png", "webp"]:
        paths.extend(gallery_dir.rglob(f"*.{ext}"))
    return sorted(paths)


def rel_path(filepath: Path, base_dir: Path) -> str:
    """获取相对路径，统一使用正斜杠"""
    return filepath.relative_to(base_dir).as_posix()


def build_index(
    checkpoint: str,
    batch_size: int = 32,
    device: str = "auto",
) -> None:
    # ==== 设备 ====
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    # ==== 加载元数据 ====
    print(f"[AWA2] 加载元数据: {FULL_META_PATH}")
    meta_index = load_awa2_metadata()

    # ==== 扫描图片 ====
    if not GALLERY_ANIMAL.exists():
        raise FileNotFoundError(f"图片目录不存在: {GALLERY_ANIMAL}")

    print(f"[AWA2] 扫描图片: {GALLERY_ANIMAL}")
    image_paths = find_images(GALLERY_ANIMAL)
    total = len(image_paths)

    if total == 0:
        raise RuntimeError(f"未找到任何图片文件于 {GALLERY_ANIMAL}")

    print(f"[AWA2] 共 {total:,} 张图片")

    # ==== 加载 CN-CLIP ====
    print(f"[AWA2] 加载 CN-CLIP: checkpoint={checkpoint}, device={device}")
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
            rp = rel_path(p, GALLERY_ANIMAL)
            meta = meta_index.get(rp)

            if meta is None:
                skipped_no_meta += 1
                continue

            try:
                img = Image.open(p).convert("RGB")
                images.append(img)
                valid_paths.append((p, meta))
            except Exception:
                skipped_bad_image += 1
                continue

        if not images:
            continue

        image_tensors = [model_loader.preprocess(img) for img in images]
        image_batch = torch.stack(image_tensors, dim=0)

        with torch.no_grad():
            embeddings = model_loader.encode_image(image_batch)

        embeddings_np = embeddings.cpu().numpy().astype("float32")
        all_embeddings.append(embeddings_np)

        for p, meta in valid_paths:
            output_metadata.append({
                "id": len(output_metadata),
                "path": meta["path"],
                "caption": meta["caption"],
                "domain": "animal",
                "attributes": meta["attributes"],
                "source": "AWA2",
            })

        pct = min(start + batch_size, total) / total * 100
        print(f"[AWA2] {min(start + batch_size, total):,}/{total:,} ({pct:.1f}%)"
              f" | 有效: {len(output_metadata):,}")

    if not all_embeddings:
        raise RuntimeError("未成功提取到任何特征向量！")

    # ==== 构建 FAISS 索引 ====
    embeddings_matrix = np.vstack(all_embeddings).astype("float32")
    dim = embeddings_matrix.shape[1]
    print(f"[AWA2] 构建 FAISS IndexFlatIP, dim={dim}, vectors={embeddings_matrix.shape[0]:,}")

    index = faiss.IndexFlatIP(dim)
    index.add(embeddings_matrix)

    # ==== 写入文件 ====
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[AWA2] 写入索引: {INDEX_OUT}")
    faiss.write_index(index, str(INDEX_OUT))

    print(f"[AWA2] 写入元数据: {METADATA_OUT}")
    with open(METADATA_OUT, "w", encoding="utf-8") as f:
        json.dump(output_metadata, f, ensure_ascii=False, indent=2)

    # ==== 汇总 ====
    print("\n" + "=" * 60)
    print(f"[AWA2] 索引构建完成!")
    print(f"  图片总数:     {total:,}")
    print(f"  成功编码:     {len(output_metadata):,}")
    print(f"  无元数据跳过: {skipped_no_meta:,}")
    print(f"  损坏图片:     {skipped_bad_image:,}")
    print(f"  向量维度:     {dim}")
    print(f"  索引文件:     {INDEX_OUT}")
    print(f"  元数据文件:   {METADATA_OUT}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="AWA2 FAISS 索引构建")
    parser.add_argument("--checkpoint", type=str, default="model/epoch_latest.pt",
                        help="CN-CLIP 权重文件路径")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", type=str, default="auto",
                        help="cpu / cuda / auto")
    args = parser.parse_args()
    build_index(args.checkpoint, args.batch_size, args.device)


if __name__ == "__main__":
    main()
