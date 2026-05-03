from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from core.metadata_schema import MetadataList


@dataclass
class DomainConfig:
    name: str
    index_path: Path
    metadata_path: Path
    gallery_dir: Path
    image_count: int
    description: str
    gallery_style: str = "flat"  # "flat" | "class_subdirs"
    attributes: List[str] = field(default_factory=list)

    @property
    def has_structured_attrs(self) -> bool:
        return self.gallery_style == "class_subdirs" or bool(self.attributes)


class DomainRegistry:
    def __init__(self, data_dir: str | Path, gallery_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.gallery_dir = Path(gallery_dir)
        self._domains: Dict[str, DomainConfig] = {}

    @property
    def default_domain(self) -> str:
        return "auto"

    def auto_discover(self) -> Dict[str, DomainConfig]:
        if not self.data_dir.exists():
            raise FileNotFoundError(f"数据目录不存在: {self.data_dir.resolve()}")

        domain_descriptions = {
            "auto": "泛化图片检索 — COCO-CN + Flickr30k-CN",
            "plant": "植物识别 — PlantNet300K（物种+器官）",
            "animal": "动物识别 — AWA2（50类别+属性）",
            "shop": "电商商品检索 — MUGE",
        }

        domain_gallery_styles = {
            "auto": "flat",
            "plant": "flat",
            "animal": "class_subdirs",
            "shop": "flat",
        }

        domain_attributes = {
            "auto": ["dataset"],
            "plant": ["species_id", "organ", "author", "license"],
            "animal": ["class_name", "class_name_cn", "predicates_en", "predicates_cn"],
            "shop": ["dataset"],
        }

        for domain_dir in sorted(self.data_dir.iterdir()):
            if not domain_dir.is_dir():
                continue

            name = domain_dir.name
            index_path = domain_dir / "images.index"
            metadata_path = domain_dir / "metadata.json"

            if not index_path.exists() or not metadata_path.exists():
                print(f"[DomainRegistry] 跳过 {name}: 缺少 index 或 metadata")
                continue

            # Read metadata to get image count
            with metadata_path.open("r", encoding="utf-8") as f:
                metadata: MetadataList = json.load(f)
            image_count = len(metadata)

            gallery_dir = self.gallery_dir / name
            description = domain_descriptions.get(name, f"{name} 领域")
            gallery_style = domain_gallery_styles.get(name, "flat")
            attributes = domain_attributes.get(name, [])

            config = DomainConfig(
                name=name,
                index_path=index_path,
                metadata_path=metadata_path,
                gallery_dir=gallery_dir,
                image_count=image_count,
                description=description,
                gallery_style=gallery_style,
                attributes=attributes,
            )

            self._domains[name] = config
            print(
                f"[DomainRegistry] 发现领域: {name} "
                f"(图片: {image_count}, 目录结构: {gallery_style})"
            )

        print(f"[DomainRegistry] 共发现 {len(self._domains)} 个领域")
        return self._domains

    def get(self, name: str) -> DomainConfig:
        if name not in self._domains:
            available = ", ".join(self._domains.keys())
            raise KeyError(f"未知领域 '{name}'，可用: {available}")
        return self._domains[name]

    def list_all(self) -> List[DomainConfig]:
        return list(self._domains.values())

    def __contains__(self, name: str) -> bool:
        return name in self._domains

    def __len__(self) -> int:
        return len(self._domains)
