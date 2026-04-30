from typing import List, Union
import numpy as np
import torch
from PIL import Image
import cn_clip.clip as cn_clip  # 切换到 cn_clip 库


def _l2_normalize(x: torch.Tensor) -> torch.Tensor:
    """
    对特征向量进行 L2 归一化。
    在跨模态检索中，归一化后的向量点积等于余弦相似度。
    """
    return x / x.norm(p=2, dim=-1, keepdim=True)


def encode_images(
        model: torch.nn.Module,
        preprocess,  # cn_clip.load_from_name 返回的预处理函数
        images: List[Image.Image],
        device: str = "cpu",
) -> np.ndarray:
    """
    使用 cn_clip 逻辑将批量图片转换为归一化向量。
    """
    if not images:
        return np.empty((0, 512), dtype="float32")  # 假设 ViT-B-16 维度为 512

    # 1. 使用 cn_clip 特有的 preprocess 对每张图片进行缩放/裁剪/归一化
    image_tensors = [preprocess(img) for img in images]
    image_batch = torch.stack(image_tensors, dim=0).to(device)

    # 2. 提取视觉特征
    with torch.no_grad():
        image_features = model.encode_image(image_batch)
        # 执行归一化
        image_features = _l2_normalize(image_features)

    return image_features.cpu().numpy().astype("float32")


def encode_texts(
        model: torch.nn.Module,
        texts: List[str],
        device: str = "cpu",
) -> np.ndarray:
    """
    使用 cn_clip 逻辑将批量中文文本转换为归一化向量。
    """
    if not texts:
        return np.empty((0, 512), dtype="float32")

    # 1. 使用 cn_clip 的分词器将中文转为 Token
    # 注意：cn_clip.tokenize 默认返回的是长整型张量
    text_tokens = cn_clip.tokenize(texts).to(device)

    # 2. 提取文本特征
    with torch.no_grad():
        text_features = model.encode_text(text_tokens)
        # 执行归一化
        text_features = _l2_normalize(text_features)

    return text_features.cpu().numpy().astype("float32")


def encode_single_image(model, preprocess, image: Image.Image, device: str = "cpu") -> np.ndarray:
    """封装单张图片处理接口"""
    return encode_images(model, preprocess, [image], device=device)[0]


def encode_single_text(model, text: str, device: str = "cpu") -> np.ndarray:
    """封装单句文本处理接口"""
    return encode_texts(model, [text], device=device)[0]