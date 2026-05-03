from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import faiss
import numpy as np


class SearchEngine:
    """
        SearchEngine 类封装了基于 FAISS 的向量检索逻辑。
        它的主要职责是：接收特征向量 -> 匹配索引 -> 映射元数据 -> 输出结果列表。
    """

    def __init__(
        self,
        index: faiss.Index,
        metadata: List[Dict[str, Any]],
        image_base_url: str = "/gallery",
        path_prefix: str = "",
    ) -> None:
        """
            :param index: 已加载的 FAISS 索引对象
            :param metadata: 包含图片路径信息的元数据列表
            :param image_base_url: 前端访问图片的基础路径 (例如：http://localhost:5000/images)
            :param path_prefix: 领域前缀，用于构造多领域图片URL (如 "auto", "plant", "animal")
        """
        self.index = index
        self.metadata = metadata
        self.image_base_url = image_base_url.rstrip("/")
        self.path_prefix = path_prefix

    @classmethod
    def from_files(
        cls,
        index_path: str | Path,
        metadata_path: str | Path,
        image_base_url: str = "/gallery",
        path_prefix: str = "",
    ) -> "SearchEngine":

# 工厂方法：直接从硬盘文件加载索引和元数据，创建 SearchEngine 实例。

        index_path = Path(index_path)
        metadata_path = Path(metadata_path)

        if not index_path.exists():
            raise FileNotFoundError(f"未找到索引文件: {index_path.resolve()}")
        if not metadata_path.exists():
            raise FileNotFoundError(f"未找到元数据文件: {metadata_path.resolve()}")

            # 加载 FAISS 索引
        print(f"[SearchEngine] 正在从 {index_path.name} 加载索引...")
        index = faiss.read_index(str(index_path))

        # 加载元数据 (JSON)
        print(f"[SearchEngine] 正在从 {metadata_path.name} 加载元数据...")
        with metadata_path.open("r", encoding="utf-8") as f:
            metadata = json.load(f)


        return cls(index=index, metadata=metadata, image_base_url=image_base_url, path_prefix=path_prefix)

    def search(self, query_vec: np.ndarray, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        在索引中执行最近邻搜索，返回包含图片 URL 与相似度的列表。

        :param query_vec: 查询向量，通常由 CNClipModelLoader 生成
        :param top_k: 需要返回的最相似结果数量
        :return: 包含图片信息和相似度得分的字典列表

        """
        # 1. 维度检查：如果输入是单向量 [D]，转换为 [1, D] 以适配 FAISS
        if query_vec.ndim == 1:
            query_vec = query_vec[None, :]

        # 2. 类型检查：FAISS 强制要求 float32
        query_vec = query_vec.astype("float32")


        # 3. 执行搜索
        # scores: 相似度得分 (对于 IndexFlatIP 是内积/余弦相似度)
        # indices: 对应的索引 ID
        scores, indices = self.index.search(query_vec, top_k)
        results: List[Dict[str, Any]] = []

        # 4. 结果映射与清洗
        for rank, (idx, score) in enumerate(zip(indices[0], scores[0]), start=1):
            # 过滤掉 FAISS 返回的空结果 (-1 表示未找到足够匹配项)
            if idx < 0 or idx >= len(self.metadata):
                continue

            meta = self.metadata[idx]

            # 路径处理：修复 Windows 路径分隔符问题
            # 将 gallery\cat.jpg 转换为 gallery/cat.jpg，方便 URL 访问
            rel_path = str(meta.get("path", "")).replace("\\", "/").lstrip("/")

            # 构建最终的图片访问 URL（多领域支持：/gallery/{domain}/{path}）
            if self.path_prefix:
                image_url = f"{self.image_base_url}/{self.path_prefix}/{rel_path}"
            else:
                image_url = f"{self.image_base_url}/{rel_path}" if rel_path else ""

            results.append(
                {
                    "id": int(meta.get("id", idx)),  # 确保是标准 Python int
                    "path": rel_path,  # 相对路径 (可选返回)
                    "image_url": image_url,  # 图片全路径或 URL
                    "caption": meta.get("caption"),  # 图片描述
                    "score": float(score),  # 相似度分数 (float32 转 float)
                    "rank": rank,  # 排名顺序
                }
            )

        return results

    def search_in_subset(
        self,
        query_vec: np.ndarray,
        candidate_indices: List[int],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        if query_vec.ndim == 1:
            query_vec = query_vec[None, :]
        query_vec = query_vec.astype("float32")

        if not candidate_indices:
            return []

        candidate_indices = [int(i) for i in candidate_indices if 0 <= i < len(self.metadata)]
        if not candidate_indices:
            return []

        candidate_vectors = np.array(
            [self.index.reconstruct(i) for i in candidate_indices],
            dtype="float32",
        )

        similarities = np.dot(candidate_vectors, query_vec.T).flatten()

        k = min(top_k, len(candidate_indices))
        top_local = np.argsort(similarities)[-k:][::-1]

        results: List[Dict[str, Any]] = []
        for rank, local_idx in enumerate(top_local, start=1):
            global_idx = candidate_indices[int(local_idx)]
            score = float(similarities[int(local_idx)])
            meta = self.metadata[global_idx]

            rel_path = str(meta.get("path", "")).replace("\\", "/").lstrip("/")

            if self.path_prefix:
                image_url = f"{self.image_base_url}/{self.path_prefix}/{rel_path}"
            else:
                image_url = f"{self.image_base_url}/{rel_path}" if rel_path else ""

            results.append(
                {
                    "id": int(meta.get("id", global_idx)),
                    "path": rel_path,
                    "image_url": image_url,
                    "caption": meta.get("caption"),
                    "score": score,
                    "rank": rank,
                }
            )

        return results
