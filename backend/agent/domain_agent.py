from __future__ import annotations

from typing import Any, Dict, List, Optional

from .prompts import DOMAIN_AGENT_CONFIG, TEXT_TEMPLATES


class DomainAgent:
    def __init__(
        self,
        domain: str,
        metadata: List[Dict[str, Any]],
    ):
        self.domain = domain
        self.metadata = metadata
        self.config = DOMAIN_AGENT_CONFIG.get(domain, DOMAIN_AGENT_CONFIG["auto"])
        self._knowledge: Optional[Dict[str, Any]] = None
        self._index_map: Optional[Dict[str, List[int]]] = None

    @property
    def knowledge(self) -> Dict[str, Any]:
        if self._knowledge is None:
            self._knowledge = self._build_knowledge()
        return self._knowledge

    @property
    def index_map(self) -> Dict[str, List[int]]:
        if self._index_map is None:
            self._index_map = self._build_index_map()
        return self._index_map

    def _build_knowledge(self) -> Dict[str, Any]:
        if self.domain == "plant":
            return self._build_plant_knowledge()
        elif self.domain == "animal":
            return self._build_animal_knowledge()
        return {}

    def _build_plant_knowledge(self) -> Dict[str, Any]:
        species_map: Dict[str, Dict[str, str]] = {}
        for m in self.metadata:
            attrs = m.get("attributes", {})
            sid = attrs.get("species_id", "")
            if sid and sid not in species_map:
                species_map[sid] = {
                    "species_id": sid,
                    "scientific_name": m.get("scientific_name", attrs.get("scientific_name", "")),
                    "chinese_name": m.get("chinese_name", attrs.get("chinese_name", "")),
                }
        return {"species": list(species_map.values()), "count": len(species_map)}

    def _build_animal_knowledge(self) -> Dict[str, Any]:
        class_map: Dict[str, Dict[str, Any]] = {}
        for m in self.metadata:
            attrs = m.get("attributes", {})
            cname = attrs.get("class_name", "")
            if cname and cname not in class_map:
                class_map[cname] = {
                    "class_name": cname,
                    "class_name_cn": attrs.get("class_name_cn", ""),
                    "predicates_cn": attrs.get("predicates_cn", []),
                }
        return {"classes": list(class_map.values()), "count": len(class_map)}

    def _build_index_map(self) -> Dict[str, List[int]]:
        index_map: Dict[str, List[int]] = {}
        if self.domain == "plant":
            attr_field = "species_id"
        elif self.domain == "animal":
            attr_field = "class_name"
        else:
            return index_map

        for i, m in enumerate(self.metadata):
            attrs = m.get("attributes", {})
            key = attrs.get(attr_field, "")
            if key:
                index_map.setdefault(key, []).append(i)
        return index_map

    def knowledge_text(self) -> str:
        k = self.knowledge
        if self.domain == "plant":
            species_list = k.get("species", [])
            lines = []
            for s in species_list:
                cn = s.get("chinese_name", "")
                sn = s.get("scientific_name", "")
                sid = s.get("species_id", "")
                name = cn or sn
                lines.append(f"{sid}: {name}")
            return "\n".join(lines)
        elif self.domain == "animal":
            classes = k.get("classes", [])
            lines = []
            for c in classes:
                cn = c.get("class_name_cn", "")
                en = c.get("class_name", "")
                preds = c.get("predicates_cn", [])
                pred_str = "、".join(preds[:5]) if preds else ""
                lines.append(f"{en}（{cn}）: {pred_str}")
            return "\n".join(lines)
        return ""

    def find_candidate_indices(self, candidate_keys: List[str]) -> List[int]:
        indices: List[int] = []
        imap = self.index_map
        for key in candidate_keys:
            key_indices = imap.get(key, [])
            indices.extend(key_indices)
        return sorted(set(indices))

    def condense_text(
        self,
        extraction: Dict[str, Any],
        query: str = "",
    ) -> str:
        domain = self.domain
        templates = TEXT_TEMPLATES.get(domain, TEXT_TEMPLATES["auto"])

        if domain == "plant":
            features = extraction.get("features", {})
            organ = features.get("organ", "any")
            if organ == "any":
                organ = ""
            else:
                organ_cn_map = {
                    "flower": "花", "leaf": "叶", "fruit": "果实",
                    "bark": "树皮", "habit": "整体",
                }
                organ = organ_cn_map.get(organ, organ)

            condensed = extraction.get("condensed_query", "")
            if condensed:
                return condensed

            query_type = extraction.get("query_type", "morphology")
            if query_type == "species_name" and condensed:
                return templates["species_name"].format(
                    chinese_name=condensed, organ=organ
                )
            if query_type == "morphology":
                color = features.get("color", "")
                shape = features.get("shape", "")
                return templates["morphology"].format(
                    color=color or "未知色", organ=organ or "部位", shape=shape or ""
                )
            return f"植物照片，{organ}" if organ else query

        elif domain == "animal":
            condensed = extraction.get("condensed_query", "")
            if condensed:
                return condensed

            features = extraction.get("features", {})
            attrs = features.get("attributes", [])
            if attrs:
                return templates["attribute"].format(
                    attributes_str="、".join(attrs)
                )
            return query

        else:
            condensed = extraction.get("condensed_query", query)
            if len(condensed) > 20:
                condensed = condensed[:20]
            return condensed

    def generate_suggestions(
        self,
        results: List[Dict[str, Any]],
        is_low_confidence: bool = False,
    ) -> List[str]:
        suggestions: List[str] = []

        if is_low_confidence:
            suggestions.append("搜索结果置信度较低，能提供更多细节描述吗？（如颜色、形状、大小）")

        if not results:
            suggestions.append("没有找到匹配的结果，试试换一种描述方式？")
            return suggestions

        top_k = min(5, len(results))
        for i in range(top_k):
            r = results[i]
            caption = r.get("caption", "")
            if caption and len(caption) > 3:
                short = caption[:25].strip()
                suggestions.append(f"第{i + 1}个「{short}」符合你的预期吗？")

        suggestions.append("都不对？试试更精确地描述你要找的目标")
        return suggestions[:6]
