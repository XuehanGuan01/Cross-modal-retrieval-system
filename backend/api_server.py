from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image

from core.model_loader import CNClipModelLoader
from core.processor import encode_single_image, encode_single_text
from core.search_engine import SearchEngine


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

INDEX_PATH = DATA_DIR / "images.index"
METADATA_PATH = DATA_DIR / "metadata.json"

# 图片静态目录（需要你根据实际图片目录调整）
# 建议：设置为你构建索引时使用的 image_dir
GALLERY_DIR = (BASE_DIR / "gallery").resolve()
IMAGE_BASE_URL = "/gallery"

app = FastAPI(title="Cross-modal Retrieval API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if GALLERY_DIR.exists():
    # 将本地图片目录挂载到 /gallery，用于前端直接访问图片
    app.mount(IMAGE_BASE_URL, StaticFiles(directory=str(GALLERY_DIR)), name="gallery")
else:
    print(f"[api_server] 警告：图片目录 {GALLERY_DIR} 不存在，/gallery 静态服务未挂载。")


@app.on_event("startup")
def init_resources() -> None:
    """
    在服务启动时加载模型与 FAISS 索引，避免每次请求重复初始化。
    """
    global MODEL_LOADER, DEVICE, SEARCH_ENGINE

    print("[api_server] 初始化 CN-CLIP 模型...")
    MODEL_LOADER = CNClipModelLoader(
        model_name="ViT-B-16",
        # checkpoint_path 默认是 model/epoch_latest.pt，你可以按需修改
    )
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    print("[api_server] 加载向量索引与元数据...")
    SEARCH_ENGINE = SearchEngine.from_files(
        index_path=INDEX_PATH,
        metadata_path=METADATA_PATH,
        image_base_url=IMAGE_BASE_URL,
    )


class TextSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="中文搜索文本")
    top_k: int = Field(50, ge=1, le=200, description="返回前 K 条结果")


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {"status": "ok"}


@app.post("/api/search/text")
def search_text(req: TextSearchRequest) -> Dict[str, List[Dict[str, Any]]]:
    """
    文本搜图：输入中文文本，返回相似图片列表（用于前端瀑布流展示）。
    """
    text_vec: np.ndarray = encode_single_text(
        MODEL_LOADER.model,
        req.query,
        device=DEVICE,
    )
    results = SEARCH_ENGINE.search(text_vec, top_k=req.top_k)
    return {"results": results}


@app.post("/api/search/image")
async def search_image(
    file: UploadFile = File(...),
    top_k: int = Form(50),
) -> Dict[str, List[Dict[str, Any]]]:
    """
    图搜文：上传图片，先在图片索引中执行搜索，然后将命中的元数据转为“文本结果”返回。

    说明：
    - 当前 metadata.json 只有 id/path 字段，尚未包含人类可读的 caption。
    - 这里只是用 path 或 future 的 caption 字段来构造文本结果。
      若你之后在 metadata 中加入 "caption" 字段，这个接口会自动优先返回 caption。
    """
    content = await file.read()
    image = Image.open(BytesIO(content)).convert("RGB")

    image_vec: np.ndarray = encode_single_image(
        MODEL_LOADER.model,
        MODEL_LOADER.preprocess,
        image,
        device=DEVICE,
    )

    image_results = SEARCH_ENGINE.search(image_vec, top_k=top_k)

    text_results: List[Dict[str, Any]] = []
    for item in image_results:
        # 如果未来 metadata 中包含 caption/text 字段，则优先使用
        caption = (
            str(item.get("caption")) if item.get("caption") is not None
            else f"图片：{item.get('path', '')}"
        )
        text_results.append(
            {
                "text": caption,
                "score": float(item.get("score", 0.0)),
                "meta": item,
            }
        )

    return {"results": text_results}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)

