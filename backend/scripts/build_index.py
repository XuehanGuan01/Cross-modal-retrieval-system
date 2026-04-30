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

# 这个函数用于递归搜索指定目录下所有符合后缀名（jpg, png 等）的图片文件。
def find_images(image_dir: Path, exts: List[str]) -> List[Path]:
    exts = [e.lower() for e in exts]
    paths: List[Path] = []
    for ext in exts:
        # rglob 表示递归搜索所有子目录
        paths.extend(image_dir.rglob(f"*.{ext}"))
    return sorted(paths)


def build_index(
    image_dir: str,
    checkpoint: str,
    index_out: str,
    metadata_out: str,
    batch_size: int = 32,
    device: str = "auto",
) -> None:
    image_dir_path = Path(image_dir)
    if not image_dir_path.exists():
        raise FileNotFoundError(f"图片目录不存在: {image_dir_path.resolve()}")

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
# 代码会自动检测是否有GPU(cuda)，如果没有则使用cpu。接着通过CNClipModelLoader加载预训练好的中文CLIP模型。

    print(f"[build_index] 加载 CN-CLIP 模型，checkpoint: {checkpoint}，device: {device}")
    model_loader = CNClipModelLoader(
        model_name="ViT-B-16",  # 与训练脚本中的 --vision-model 对应
        checkpoint_path=checkpoint,
        device=device,
    )

    print(f"[build_index] 搜索图片文件于: {image_dir_path}")
    image_paths = find_images(image_dir_path, ["jpg", "jpeg", "png", "webp"])
    if not image_paths:
        raise RuntimeError(f"在目录 {image_dir_path} 中未找到任何图片文件")

    all_embeddings: List[np.ndarray] = []
    metadata: List[dict] = []

    total = len(image_paths)
    print(f"[build_index] 共找到 {total} 张图片，开始提取特征...")

    for start in range(0, total, batch_size):
        # 1. 切片获取当前批次的路径
        batch_paths = image_paths[start : start + batch_size]
        images = []
        valid_paths = []
        # 2. 读取图片并转为 RGB（过滤掉损坏的图片）
        for p in batch_paths:
            try:
                img = Image.open(p).convert("RGB")
                images.append(img)
                valid_paths.append(p)
            except Exception as e:
                print(f"[build_index] 警告: 打开图片失败 {p}: {e}")
                continue

        if not images:
            continue

        # 第二步：特征提取（最耗时的部分）使用 cn_clip 的 preprocess + encode_image 得到特征

        # 1 预处理：将图片统一缩放、裁剪并转换为模型需要的Tensor格式。
        image_tensors = [model_loader.preprocess(img) for img in images]
        image_batch = torch.stack(image_tensors, dim=0)# 组合成一个 Batch 维度

        with torch.no_grad():# 推理模式，不计算梯度以节省内存
            embeddings = model_loader.encode_image(image_batch)
            # 2 推理：调用 model_loader.encode_image。
        # 存入内存列表
        embeddings_np = embeddings.cpu().numpy().astype("float32")
        # 3 向量化：将模型输出的特征转换为 32 位浮点数的 NumPy 数组。
        all_embeddings.append(embeddings_np)

        # 记录元数据，方便以后根据 ID 找回图片路径
        for p in valid_paths:
            # 记录相对路径，增加跨平台的可移植性
            rel_path = os.path.relpath(p, image_dir_path).replace(os.sep, "/")
            metadata.append(
                {
                    "id": len(metadata),
                    "path": rel_path,
                    "caption": "",
                }
            )

        print(f"[build_index] 已处理 {min(start + batch_size, total)} / {total}")

    if not all_embeddings:
        raise RuntimeError("未成功提取到任何特征向量")

    # 第三步：构建 FAISS索引
    embeddings_matrix = np.vstack(all_embeddings).astype("float32")

    dim = embeddings_matrix.shape[1]
    print(f"[build_index] 构建 FAISS IndexFlatIP, 向量维度: {dim}")
    # 使用内积 (Inner Product) 索引，适合经过归一化的特征向量
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings_matrix)
    # FAISS是由Meta开发的高性能向量搜索库。
    # IndexFlatIP是一种暴力搜索索引，虽然是全量比对，但在万级数据量下速度极快且精度最高。

    index_out_path = Path(index_out)
    metadata_out_path = Path(metadata_out)
    index_out_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[build_index] 写入索引到 {index_out_path}")
    faiss.write_index(index, str(index_out_path))

    print(f"[build_index] 写入元数据到 {metadata_out_path}")
    with metadata_out_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # 第四步：保存结果
    # .index文件：存储了所有图片的二进制特征向量。
    # .json文件：存储了向量ID与图片路径的对应关系（元数据）。

    print("[build_index] 索引构建完成 ✅")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="遍历图片目录，提取特征并构建 FAISS 索引"
    )
    parser.add_argument(
        "--image-dir",
        type=str,
        default="gallery",
        help="图片根目录（默认: gallery）",
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default="model/epoch_latest.pt",
        help="CN-CLIP 训练 checkpoint 路径（默认: model/epoch_latest.pt）",
    )
    parser.add_argument(
        "--index-out",
        type=str,
        default="data/images.index",
        help="FAISS 索引输出路径（默认: data/images.index）",
    )
    parser.add_argument(
        "--metadata-out",
        type=str,
        default="data/metadata.json",
        help="元数据 JSON 输出路径（默认: data/metadata.json）",
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
        help="运行设备：cpu / cuda / auto（默认: auto，自动选择）",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_index(
        image_dir=args.image_dir,
        checkpoint=args.checkpoint,
        index_out=args.index_out,
        metadata_out=args.metadata_out,
        batch_size=args.batch_size,
        device=args.device,
    )

