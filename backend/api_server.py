from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch
from fastapi import FastAPI, File, Form, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image

from core.model_loader import CNClipModelLoader
from core.processor import encode_single_image, encode_single_text
from core.search_engine import SearchEngine
from core.domain_registry import DomainRegistry

from agent.llm_factory import create_llm
from agent.session_manager import SessionManager
from agent.domain_agent import DomainAgent
from agent.pipeline import AgentPipeline

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
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
    app.mount(IMAGE_BASE_URL, StaticFiles(directory=str(GALLERY_DIR)), name="gallery")
else:
    print(f"[api_server] 警告：图片目录 {GALLERY_DIR} 不存在，/gallery 静态服务未挂载。")


# ---- 全局资源 ----

MODEL_LOADER: CNClipModelLoader = None
DEVICE: str = "cpu"
DOMAIN_REGISTRY: DomainRegistry = None
ENGINES: Dict[str, SearchEngine] = {}
DOMAIN_AGENTS: Dict[str, DomainAgent] = {}
SESSION_MANAGER: SessionManager = None
PIPELINE: AgentPipeline = None


@app.on_event("startup")
def init_resources() -> None:
    global MODEL_LOADER, DEVICE, DOMAIN_REGISTRY, ENGINES
    global DOMAIN_AGENTS, SESSION_MANAGER, PIPELINE

    print("[api_server] 初始化 CN-CLIP 模型...")
    MODEL_LOADER = CNClipModelLoader(model_name="ViT-B-16")
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    print("[api_server] 扫描领域并加载多领域索引...")
    DOMAIN_REGISTRY = DomainRegistry(data_dir=DATA_DIR, gallery_dir=GALLERY_DIR)
    domains = DOMAIN_REGISTRY.auto_discover()

    for name, config in domains.items():
        print(f"[api_server] 加载领域 [{name}]: {config.description}")
        engine = SearchEngine.from_files(
            index_path=config.index_path,
            metadata_path=config.metadata_path,
            image_base_url=IMAGE_BASE_URL,
            path_prefix=name,
        )
        ENGINES[name] = engine

        # 为每个领域创建 DomainAgent（用于 Agent Pipeline）
        domain_agent = DomainAgent(name, engine.metadata)
        DOMAIN_AGENTS[name] = domain_agent
        if domain_agent.knowledge:
            kcount = domain_agent.knowledge.get("count", 0)
            print(f"  [DomainAgent] {name}: 知识库条目={kcount}")

    # 初始化 LLM
    print("[api_server] 初始化 LLM (Qwen3-max)...")
    try:
        llm = create_llm(model="qwen3-max")
        print("[api_server] LLM 连接成功")
    except Exception as e:
        print(f"[api_server] LLM 初始化失败: {e}")
        llm = None

    # 初始化会话管理与 Pipeline
    SESSION_MANAGER = SessionManager(ttl_seconds=3600)
    PIPELINE = AgentPipeline(
        llm=llm,
        engines=ENGINES,
        domain_agents=DOMAIN_AGENTS,
        model_loader=MODEL_LOADER,
        device=DEVICE,
    )

    print(f"[api_server] 就绪 — 领域数: {len(ENGINES)}, Agent Pipeline: {'可用' if llm else 'LLM未连接'}")



# ---- 请求模型 ----

class TextSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="中文搜索文本")
    top_k: int = Field(50, ge=1, le=200, description="返回前 K 条结果")
    domain: str = Field("auto", description="领域: auto / plant / animal / shop")


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户消息")
    session_id: str = Field(None, description="会话ID（可选，新会话则留空）")
    domain: str = Field("auto", description="领域")


# ---- 检索端点 ----

@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "domains_loaded": len(ENGINES),
        "agent_ready": PIPELINE is not None and PIPELINE.llm is not None,
        "active_sessions": SESSION_MANAGER.active_count if SESSION_MANAGER else 0,
    }


@app.get("/api/domains")
def list_domains() -> List[Dict[str, Any]]:
    configs = DOMAIN_REGISTRY.list_all()
    return [
        {
            "name": c.name,
            "description": c.description,
            "image_count": c.image_count,
            "gallery_style": c.gallery_style,
        }
        for c in configs
    ]


@app.post("/api/search/text")
def search_text(req: TextSearchRequest) -> Dict[str, Any]:
    domain = req.domain
    if domain not in ENGINES:
        available = ", ".join(ENGINES.keys())
        return {"error": f"未知领域 '{domain}'，可用: {available}", "results": []}

    engine = ENGINES[domain]
    text_vec: np.ndarray = encode_single_text(
        MODEL_LOADER.model,
        req.query,
        device=DEVICE,
    )
    results = engine.search(text_vec, top_k=req.top_k)
    return {"results": results, "domain": domain}


@app.post("/api/search/image")
async def search_image(
    file: UploadFile = File(...),
    top_k: int = Form(50),
    domain: str = Form("auto"),
) -> Dict[str, Any]:
    if domain not in ENGINES:
        available = ", ".join(ENGINES.keys())
        return {"error": f"未知领域 '{domain}'，可用: {available}", "results": []}

    engine = ENGINES[domain]
    content = await file.read()
    image = Image.open(BytesIO(content)).convert("RGB")

    image_vec: np.ndarray = encode_single_image(
        MODEL_LOADER.model,
        MODEL_LOADER.preprocess,
        image,
        device=DEVICE,
    )

    image_results = engine.search(image_vec, top_k=top_k)

    text_results: List[Dict[str, Any]] = []
    for item in image_results:
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

    return {"results": text_results, "domain": domain}


# ---- Agent 端点 ----

@app.post("/api/agent/chat")
async def agent_chat(req: AgentChatRequest) -> Dict[str, Any]:
    if PIPELINE is None or PIPELINE.llm is None:
        return {
            "reply": "Agent Pipeline 未就绪，请检查 LLM 配置（DASHSCOPE_API_KEY）。",
            "results": [],
            "reasoning_steps": ["LLM 初始化失败"],
            "suggestions": ["请检查后端日志"],
            "is_low_confidence": True,
        }

    session = SESSION_MANAGER.get_or_create(req.session_id, req.domain)

    result = await PIPELINE.run(
        session=session,
        user_message=req.message,
    )

    session.messages.append({"role": "user", "content": req.message})
    session.messages.append({
        "role": "assistant",
        "content": result["reply"],
        "results": result["results"],
    })
    session.touch()

    return result


@app.post("/api/agent/session/new")
def create_agent_session(domain: str = "auto") -> Dict[str, str]:
    session = SESSION_MANAGER.create(domain)
    return {"session_id": session.session_id, "domain": session.domain}


@app.delete("/api/agent/session/{session_id}")
def delete_agent_session(session_id: str) -> Dict[str, Any]:
    deleted = SESSION_MANAGER.delete(session_id)
    return {"deleted": deleted, "session_id": session_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
