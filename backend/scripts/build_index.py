"""
离线索引构建脚本
按领域（domain）遍历图片目录，用 CN-CLIP 提取图像特征，构建 FAISS 索引并输出元数据。

用法：
    python build_index.py --domain auto --source "COCO-CN,Flickr30K-CN,MUGE"
    python build_index.py --domain plant
    python build_index.py --domain animal --batch-size 64
    python build_index.py --domain shop --device cuda
"""

import argparse
import json
import os
from pathlib import Path
from typing import List

import faiss
import numpy as np
from PIL import Image
import torch

from core.model_loader import CNClipModelLoader


def find_images(image_dir: Path, exts: List[str]) -> List[Path]:
    """递归搜索指定目录下所有符合后缀名的图片文件"""
    exts = [e.lower() for e in exts]
    paths: List[Path] = []
    for ext in exts:
        paths.extend(image_dir.rglob(f"*.{ext}"))
    return sorted(paths)


def build_index(
    domain: str,
    checkpoint: str,
    batch_size: int = 32,
    device: str = "auto",
    source: str = "",
    image_root: str = "gallery",
    data_root: str = "data",
) -> None:
    """
    为指定领域构建 FAISS 索引与元数据文件。

    路径约定（由 domain 自动推导）：
        - 图片目录：{image_root}/{domain}/
        - 索引输出：{data_root}/{domain}/images.index
        - 元数据输出：{data_root}/{domain}/metadata.json
    """
    # ==== 根据 domain 自动推导输入/输出路径 ====
    image_dir = Path(image_root) / domain
    index_out = Path(data_root) / domain / "images.index"
    metadata_out = Path(data_root) / domain / "metadata.json"

    if not image_dir.exists():
        raise FileNotFoundError(f"图片目录不存在: {image_dir.resolve()}")

    # ==== 设备选择 ====
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    # ==== 加载 CN-CLIP 模型 ====
    print(f"[build_index] 领域: {domain}")
    print(f"[build_index] 加载 CN-CLIP 模型, checkpoint: {checkpoint}, device: {device}")
    model_loader = CNClipModelLoader(
        model_name="ViT-B-16",
        checkpoint_path=checkpoint,
        device=device,
    )

    # ==== 扫描图片文件 ====
    print(f"[build_index] 搜索图片文件于: {image_dir.resolve()}")
    image_paths = find_images(image_dir, ["jpg", "jpeg", "png", "webp"])
    if not image_paths:
        raise RuntimeError(f"在目录 {image_dir.resolve()} 中未找到任何图片文件")

    total = len(image_paths)
    print(f"[build_index] 共找到 {total} 张图片，开始提取特征...")

    all_embeddings: List[np.ndarray] = []
    metadata: List[dict] = []

    # ==== 分批提取图像特征 ====
    for start in range(0, total, batch_size):
        batch_paths = image_paths[start : start + batch_size]
        images = []
        valid_paths = []

        for p in batch_paths:
            try:
                img = Image.open(p).convert("RGB")
                images.append(img)
                valid_paths.append(p)
            except Exception:
                # 跳过损坏或无法打开的图片
                continue

        if not images:
            continue

        # 预处理：缩放、裁剪、转 Tensor
        image_tensors = [model_loader.preprocess(img) for img in images]
        image_batch = torch.stack(image_tensors, dim=0)

        # 推理：CN-CLIP 图像编码（不计算梯度以节省显存）
        with torch.no_grad():
            embeddings = model_loader.encode_image(image_batch)

        # 向量转 NumPy（float32，适配 FAISS）
        embeddings_np = embeddings.cpu().numpy().astype("float32")
        all_embeddings.append(embeddings_np)

        # 记录元数据（相对路径 + 领域信息）
        for p in valid_paths:
            rel_path = os.path.relpath(p, image_dir).replace(os.sep, "/")
            metadata.append({
                "id": len(metadata),
                "path": rel_path,
                "caption": "",
                "domain": domain,
                "attributes": {},
                "source": source,
            })

        print(f"[build_index] 已处理 {min(start + batch_size, total)} / {total}")

    if not all_embeddings:
        raise RuntimeError("未成功提取到任何特征向量")

    # ==== 构建 FAISS 索引（内积 = 余弦相似度，因为向量已 L2 归一化） ====
    embeddings_matrix = np.vstack(all_embeddings).astype("float32")
    dim = embeddings_matrix.shape[1]
    print(f"[build_index] 构建 FAISS IndexFlatIP, 向量维度: {dim}")
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings_matrix)

    # ==== 写入输出文件 ====
    index_out.parent.mkdir(parents=True, exist_ok=True)
    metadata_out.parent.mkdir(parents=True, exist_ok=True)

    print(f"[build_index] 写入索引到 {index_out.resolve()}")
    faiss.write_index(index, str(index_out))

    print(f"[build_index] 写入元数据到 {metadata_out.resolve()}")
    with metadata_out.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"[build_index] 领域 [{domain}] 索引构建完成 ✅  (共 {len(metadata)} 条记录)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="按领域遍历图片目录，提取特征并构建 FAISS 索引"
    )
    # --domain 是唯一必填参数，路径由它自动推导
    parser.add_argument(
        "--domain",
        type=str,
        required=True,
        help="领域名称（必填），如 auto / plant / animal / shop。"
             "图片从 {image-root}/{domain}/ 读取，索引输出到 {data-root}/{domain}/",
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default="model/epoch_latest.pt",
        help="CN-CLIP 权重文件路径（默认: model/epoch_latest.pt）",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="批处理大小（默认: 32）",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        help="运行设备：cpu / cuda / auto（默认: auto）",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="",
        help="数据集来源标注，会写入 metadata（如 'COCO-CN,Flickr30K-CN,MUGE'）",
    )
    parser.add_argument(
        "--image-root",
        type=str,
        default="gallery",
        help="图片根目录（默认: gallery）",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default="data",
        help="数据输出根目录（默认: data）",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_index(
        domain=args.domain,
        checkpoint=args.checkpoint,
        batch_size=args.batch_size,
        device=args.device,
        source=args.source,
        image_root=args.image_root,
        data_root=args.data_root,
    )
