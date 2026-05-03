from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class MetadataItem(TypedDict, total=False):
    id: int
    path: str  # animal: "antelope/antelope_10001.jpg", others: "xxx.jpg"
    caption: str
    domain: str
    attributes: Dict[str, Any]
    source: str


MetadataList = List[MetadataItem]
