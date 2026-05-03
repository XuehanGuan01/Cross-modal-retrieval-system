from __future__ import annotations

import os
from typing import Optional

from langchain_community.chat_models.tongyi import ChatTongyi


def create_llm(model: str = "qwen3-max", temperature: float = 0.1) -> ChatTongyi:
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DASHSCOPE_API_KEY 未设置。请设置环境变量后重启服务。"
        )

    return ChatTongyi(
        model=model,
        temperature=temperature,
        dashscope_api_key=api_key,
    )
