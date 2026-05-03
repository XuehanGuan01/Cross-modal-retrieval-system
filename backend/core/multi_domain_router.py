from __future__ import annotations

import re
from typing import Any, Dict, List

import numpy as np

from core.search_engine import SearchEngine


class MultiDomainRouter:
    def __init__(self, engines: Dict[str, SearchEngine]):
        self.engines = engines

    def search_single_domain(
        self, domain: str, query_vec: np.ndarray, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        if domain not in self.engines:
            return []
        return self.engines[domain].search(query_vec, top_k=top_k)

    def search_all_domains(
        self, query_vec: np.ndarray, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        all_results: List[Dict[str, Any]] = []
        for domain, engine in self.engines.items():
            results = engine.search(query_vec, top_k=top_k)
            for r in results:
                r["domain"] = domain
            all_results.extend(results)
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:top_k]

    def get_domain_suggestion(self, query_text: str) -> List[str]:
        suggestions: List[str] = []
        text = query_text.lower()

        domain_keywords: Dict[str, List[str]] = {
            "plant": [
                "花", "草", "树", "叶", "植物", "果实", "种子", "花瓣",
                "开花", "草本", "木本", "灌木", "乔木",
            ],
            "animal": [
                "动物", "鸟", "鱼", "狗", "猫", "马", "牛", "羊",
                "虎", "狮", "象", "猴", "蛇", "昆虫", "宠物",
                "野生动物", "哺乳", "爬行",
            ],
            "shop": [
                "衣服", "裙子", "裤子", "鞋", "包", "手机", "电脑",
                "家具", "化妆品", "食品", "玩具", "首饰", "手表",
                "连衣裙", "T恤", "运动鞋",
            ],
            "auto": [
                "汽车", "风景", "建筑", "人物", "街道", "海滩",
                "城市", "室内", "天空", "食物", "水果",
            ],
        }

        for domain, keywords in domain_keywords.items():
            if domain in self.engines and any(kw in text for kw in keywords):
                suggestions.append(domain)

        if not suggestions and "auto" in self.engines:
            return ["auto"]

        return suggestions

    def search_with_routing(
        self,
        query_vec: np.ndarray,
        query_text: str,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        suggestions = self.get_domain_suggestion(query_text)

        if len(suggestions) == 1:
            domain = suggestions[0]
            results = self.search_single_domain(domain, query_vec, top_k)
        else:
            results = self.search_all_domains(query_vec, top_k)

        return {
            "results": results,
            "routed_domains": suggestions,
        }
