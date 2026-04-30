from pathlib import Path
from typing import Optional

import torch
import cn_clip.clip as cn_clip
from cn_clip.clip.model import convert_state_dict


class CNClipModelLoader:
    """
    使用 cn_clip 初始化模型并加载本地微调权重，用于推理阶段的特征抽取。

    - 默认从 `model/epoch_latest.pt` 加载训练阶段保存的 state_dict。
    - 提供 `encode_image(image_tensor)` 和 `encode_text(text_tokens)` 两个方法，
      返回 L2 归一化后的特征向量 (torch.Tensor)。
    """

    def __init__(
        self,
        model_name: str,
        checkpoint_path: str = "model/epoch_latest.pt",
        device: Optional[str] = None,
    ) -> None:
        # 确定运行设备(CUDA / CPU)
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)

        # 1. 从官方库加载基础模型架构及预训练参数，使用 cn_clip 根据名称构建基础模型（带预训练权重）
        # 例如：model_name = "ViT-B-16", "ViT-L-14" 等
        self.model, self.preprocess = cn_clip.load_from_name(
            model_name, device=self.device
        )
        self.model.eval()

        # 2. 加载自己训练得到的 checkpoint（epoch_latest.pt）自定义微调的权重文件
        ckpt_path = Path(checkpoint_path)
        if not ckpt_path.exists():
            raise FileNotFoundError(f"未找到模型权重文件: {ckpt_path.resolve()}")

        print(f"[Loader] 正在注入微调权重: {ckpt_path.name}")

        # map_location 确保在没有 GPU 的机器上也能加载 GPU 训练的模型
        checkpoint = torch.load(ckpt_path, map_location=self.device)

        # 处理不同的保存格式：有些保存的是整个 dict (含 epoch, optimizer)，有些只保存 state_dict
        state_dict = checkpoint.get("state_dict", checkpoint)

        # 核心步骤：转换 state_dict 格式以适配当前模型架构
        # 这会自动处理 Flash Attention 带来的命名差异
        state_dict = convert_state_dict(state_dict)

        # 【重要修复】如果权重是用 DataParallel 训练的，需要移除 "module." 前缀
        new_state_dict = {}
        for k, v in state_dict.items():
            name = k[7:] if k.startswith('module.') else k
            new_state_dict[name] = v

        # 加载权重。strict=False 允许忽略一些不影响推理的辅助参数（如某些 buffer）
        msg = self.model.load_state_dict(new_state_dict, strict=False)
        print(f"[Loader] 权重加载结果: {msg}")

        self.model.to(self.device)
        self.model.eval()  # 必须设为 eval 模式，关闭 Dropout 和 BatchNorm

    @torch.no_grad()
    def encode_image(self, image_tensor: torch.Tensor) -> torch.Tensor:
        """
                提取图像特征。
                :param image_tensor: 形状为 [C, H, W] 或 [B, C, H, W] 的张量
                :return: L2 归一化后的特征向量 [B, D]
        """
        # 如果是单张图片，增加 Batch 维度 [1, C, H, W]
        if image_tensor.dim() == 3:
            image_tensor = image_tensor.unsqueeze(0)

        # 移动到计算设备
        image_tensor = image_tensor.to(self.device, non_blocking=True)
        # 得到原始特征 [B, D]
        image_features = self.model.encode_image(image_tensor)

        # 【关键】L2 归一化：使向量长度为 1，这样后续用内积计算就等同于余弦相似度
        # 公式: v = v / ||v||_2
        image_features = image_features / image_features.norm(
            dim=-1, keepdim=True
        )
        return image_features

    @torch.no_grad()
    def encode_text(self, text_tokens: torch.Tensor) -> torch.Tensor:
        """
        输入已经通过 cn_clip.tokenize 得到的文本 token（形状 [L] 或 [B, L]），
        返回归一化后的文本特征，形状 [B, D]。
        """
        if text_tokens.dim() == 1:
            text_tokens = text_tokens.unsqueeze(0)

        text_tokens = text_tokens.to(self.device, non_blocking=True)
        text_features = self.model.encode_text(text_tokens)
        text_features = text_features / text_features.norm(
            dim=-1, keepdim=True
        )
        return text_features

