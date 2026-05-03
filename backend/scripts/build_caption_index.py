"""
通用 JSONL Caption 索引构建脚本
================================
基于 build_plantnet300k_index.py / build_awa2_index.py 架构，
为 auto（COCO-CN + Flickr30k-CN）和 shop（MUGE）领域构建 FAISS 索引 + v2 元数据。

特性：
  - 通过 --domain 切换领域（auto / shop）
  - 从 JSONL caption 文件构建 image_id → caption 映射
  - 只取每个 image_id 的第一条 caption（按 text_id 升序）
  - 跳过无 caption 的图片
  - 输出 data/{domain}/images.index + metadata.json

用法：
    cd backend
    python scripts/build_caption_index.py --domain auto
    python scripts/build_caption_index.py --domain shop --batch-size 64 --device cuda
    python scripts/build_caption_index.py --domain auto --jsonl-root "E:/Chinese-Clip-datasets"
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import faiss
import numpy as np
from PIL import Image
import torch

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from core.model_loader import CNClipModelLoader


# ==================== 领域配置 ====================

DOMAIN_CONFIG = {
    "auto": {
        "datasets": ["COCO-CN", "Flickr30k-CN"],
        "gallery": BACKEND_ROOT / "gallery" / "auto",
        "output_dir": BACKEND_ROOT / "data" / "auto",
    },
    "shop": {
        "datasets": ["MUGE"],
        "gallery": BACKEND_ROOT / "gallery" / "shop",
        "output_dir": BACKEND_ROOT / "data" / "shop",
    },
}

# JSONL 文件名（每个 split 对应的 caption 文件）
JSONL_FILES = {
    "COCO-CN": ["train_texts.jsonl", "val_texts.jsonl", "test_texts.jsonl"],
    "Flickr30k-CN": ["train_texts.jsonl", "valid_texts.jsonl", "test_texts.jsonl"],
    "MUGE": ["train_texts.jsonl", "valid_texts.jsonl", "test_texts.jsonl"],
}


# ==================== ID 提取 ====================

_COCO_PATTERN = re.compile(r"^COCO_(?:train|val)2014_(\d{12})\.(jpg|jpeg|png|webp)$", re.IGNORECASE)
_FLICKR_PATTERN = re.compile(r"^Flickr30K_(\d+)\.(jpg|jpeg|png|webp)$", re.IGNORECASE)
_MUGE_PATTERN = re.compile(r"^MUGE_(\d+)\.(jpg|jpeg|png|webp)$", re.IGNORECASE)


def extract_image_id(filename: str) -> Tuple[int, str]:
    """
    从文件名提取 (image_id, dataset_name)。
    根据文件名前缀自动判断所属数据集。
    """
    m = _COCO_PATTERN.match(filename)
    if m:
        return int(m.group(1)), "COCO-CN"
    m = _FLICKR_PATTERN.match(filename)
    if m:
        return int(m.group(1)), "Flickr30k-CN"
    m = _MUGE_PATTERN.match(filename)
    if m:
        return int(m.group(1)), "MUGE"
    raise ValueError(f"Unknown filename pattern: {filename}")


# ==================== Caption 加载 ====================

def load_caption_map(jsonl_root: str, datasets: List[str]) -> Dict[int, Tuple[str, str]]:
    """
    加载所有数据集、所有 split 的 JSONL caption 文件，
    构建 image_id → (caption, dataset_name) 映射。

    只保留每个 image_id 的第一条 caption（按 text_id 升序）。
    """
    caption_map: Dict[int, Tuple[str, str]] = {}

    for ds_name in datasets:
        splits = JSONL_FILES.get(ds_name, [])
        total_lines = 0
        new_images = 0

        for split_file in splits:
            filepath = Path(jsonl_root) / ds_name / split_file
            if not filepath.exists():
                print(f"  [跳过] 文件不存在: {filepath}")
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    total_lines += 1
                    obj = json.loads(line)
                    image_ids = obj.get("image_ids", [])
                    text = obj.get("text", "")

                    if not image_ids or not text:
                        continue

                    for img_id in image_ids:
                        if img_id not in caption_map:
                            caption_map[img_id] = (text, ds_name)
                            new_images += 1

        print(f"  [{ds_name}] {total_lines:,} 行 → {new_images:,} 张新图片有 caption")

    return caption_map


# ==================== 图片扫描 ====================

def find_images(gallery_dir: Path) -> List[Path]:
    """扫描所有 jpg/jpeg/png/webp 图片，按文件名排序"""
    paths = []
    for ext in ["jpg", "jpeg", "png", "webp"]:
        paths.extend(gallery_dir.glob(f"*.{ext}"))
    return sorted(paths)


# ==================== 索引构建 ====================

def build_index(
    domain: str,
    jsonl_root: str,
    checkpoint: str,
    batch_size: int = 32,
    device: str = "auto",
) -> None:
    config = DOMAIN_CONFIG[domain]
    gallery_dir = config["gallery"]
    output_dir = config["output_dir"]
    datasets = config["datasets"]
    index_out = output_dir / "images.index"
    metadata_out = output_dir / "metadata.json"

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    # ==== 加载 caption 映射 ====
    print(f"[{domain}] 加载 JSONL caption 文件: {jsonl_root}")
    caption_map = load_caption_map(jsonl_root, datasets)
    print(f"[{domain}] caption 映射: {len(caption_map):,} 个 image_id")

    # ==== 扫描图片 ====
    if not gallery_dir.exists():
        raise FileNotFoundError(f"图片目录不存在: {gallery_dir}")

    print(f"[{domain}] 扫描图片: {gallery_dir}")
    image_paths = find_images(gallery_dir)
    total = len(image_paths)
    if total == 0:
        raise RuntimeError(f"未找到任何图片文件于 {gallery_dir}")
    print(f"[{domain}] 共 {total:,} 张图片")

    # ==== 加载 CN-CLIP ====
    print(f"[{domain}] 加载 CN-CLIP: checkpoint={checkpoint}, device={device}")
    model_loader = CNClipModelLoader(
        model_name="ViT-B-16",
        checkpoint_path=checkpoint,
        device=device,
    )

    # ==== 提取图像特征 + 构建元数据 ====
    all_embeddings: List[np.ndarray] = []
    output_metadata: List[dict] = []
    skipped_no_caption = 0
    skipped_bad_image = 0
    skipped_unknown_pattern = 0

    for start in range(0, total, batch_size):
        batch_paths = image_paths[start : start + batch_size]
        images = []
        valid_paths: List[Tuple[Path, str, str]] = []  # (path, caption, dataset_name)

        for p in batch_paths:
            # 提取 image_id
            try:
                img_id, ds_name = extract_image_id(p.name)
            except ValueError:
                skipped_unknown_pattern += 1
                continue

            # 查找 caption
            entry = caption_map.get(img_id)
            if entry is None:
                skipped_no_caption += 1
                continue

            caption, _ = entry

            # 加载图片
            try:
                img = Image.open(p).convert("RGB")
                images.append(img)
                valid_paths.append((p, caption, ds_name))
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

        # 记录元数据（v2 规范）
        for p, caption, ds_name in valid_paths:
            rel_path = p.name  # gallery 内为扁平目录，文件名即相对路径
            output_metadata.append({
                "id": len(output_metadata),
                "path": rel_path,
                "caption": caption,
                "domain": domain,
                "source": ds_name,
                "attributes": {
                    "dataset": ds_name,
                },
            })

        pct = min(start + batch_size, total) / total * 100
        print(f"[{domain}] {min(start + batch_size, total):,}/{total:,} ({pct:.1f}%)"
              f" | 有效: {len(output_metadata):,}"
              f" | 无caption: {skipped_no_caption:,}"
              f" | 坏图: {skipped_bad_image:,}")

    if not all_embeddings:
        raise RuntimeError("未成功提取到任何特征向量！")

    # ==== 构建 FAISS 索引 ====
    embeddings_matrix = np.vstack(all_embeddings).astype("float32")
    dim = embeddings_matrix.shape[1]
    print(f"[{domain}] 构建 FAISS IndexFlatIP, dim={dim}, vectors={embeddings_matrix.shape[0]:,}")

    index = faiss.IndexFlatIP(dim)
    index.add(embeddings_matrix)

    # ==== 写入文件 ====
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{domain}] 写入索引: {index_out}")
    faiss.write_index(index, str(index_out))

    print(f"[{domain}] 写入元数据: {metadata_out}")
    with open(metadata_out, "w", encoding="utf-8") as f:
        json.dump(output_metadata, f, ensure_ascii=False, indent=2)

    # ==== 汇总 ====
    print("\n" + "=" * 60)
    print(f"[{domain}] 索引构建完成!")
    print(f"  图片总数:       {total:,}")
    print(f"  成功编码:       {len(output_metadata):,}")
    print(f"  无caption跳过:  {skipped_no_caption:,}")
    print(f"  损坏图片:       {skipped_bad_image:,}")
    print(f"  未知命名模式:   {skipped_unknown_pattern:,}")
    print(f"  向量维度:       {dim}")
    print(f"  索引文件:       {index_out}")
    print(f"  元数据文件:     {metadata_out}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="通用 JSONL Caption 索引构建")
    parser.add_argument("--domain", type=str, required=True,
                        choices=["auto", "shop"],
                        help="领域名称: auto / shop")
    parser.add_argument("--jsonl-root", type=str,
                        default="E:/Chinese-Clip-datasets",
                        help="JSONL caption 文件根目录")
    parser.add_argument("--checkpoint", type=str, default="model/epoch_latest.pt",
                        help="CN-CLIP 权重文件路径")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", type=str, default="auto",
                        help="cpu / cuda / auto")
    args = parser.parse_args()
    build_index(args.domain, args.jsonl_root, args.checkpoint, args.batch_size, args.device)


if __name__ == "__main__":
    main()
