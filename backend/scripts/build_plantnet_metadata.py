"""
PlantNet300K 元数据构建脚本 (v4)
================================
从原始元数据 + 物种名映射 + 中文名映射，构建带 caption 的完整图像元数据。

caption 格式: "物种命名：xxx，植物部位：xxx"

输入:
    data/plantnet300K_metadata.json               # 306,146 条图片级元数据
    data/plantnet300K_species_id_2_name.json      # species_id → 拉丁学名
    data/plantnet300K_species_id_2_chinese.json   # species_id → 中文名（可选）

输出:
    data/plantnet300K_image_metadata_full.json     # 完整元数据备份（hash索引）
    注: 检索系统用的 metadata.json 由 build_plantnet300k_index.py 输出到 backend/data/plant/

用法:
    python "C:/Users/Lenovo/Desktop/manual/scripts/build_plantnet_metadata.py"
"""

import json
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ==================== 固定路径 ====================
PROJECT_ROOT = Path("C:/Users/Lenovo/Desktop/Cross-modal retrieval system")
DATA_ROOT = PROJECT_ROOT / "data"

META_PATH = DATA_ROOT / "plantnet300K_metadata.json"
NAME_MAP_PATH = DATA_ROOT / "plantnet300K_species_id_2_name.json"
CN_MAP_PATH = DATA_ROOT / "plantnet300K_species_id_2_chinese.json"

OUT_FULL = DATA_ROOT / "plantnet300K_image_metadata_full.json"

ORGAN_LABELS = {
    "flower": "花",
    "leaf": "叶",
    "fruit": "果实",
    "bark": "树皮",
    "habit": "整体形态",
    "branch": "枝干",
    "scan": "扫描",
    "other": "其他",
    "none": "未知",
}


def remove_author(scientific_name: str) -> str:
    """去除拉丁学名的命名人部分"""
    import re
    name = scientific_name.strip()
    name = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
    parts = name.split()
    while parts:
        last = parts[-1]
        if re.match(r'^[A-Z][a-z]{0,3}\.?$', last) or last == 'ex':
            parts.pop()
        elif re.match(r"^[A-Z]\.?-[A-Z][a-z]*\.?$", last):
            parts.pop()
        elif last in ("Hér.", "L'Hér.", "f.", "var.", "subsp."):
            parts.pop()
        else:
            break
    return " ".join(parts).strip()


def build_caption(cn_name: str, scientific_name: str, organ_en: str) -> str:
    """构建检索用 caption: 物种命名：xxx，植物部位：xxx"""
    species_label = cn_name if cn_name else remove_author(scientific_name)
    organ_label = ORGAN_LABELS.get(organ_en, organ_en)
    return f"物种命名：{species_label}，植物部位：{organ_label}"


def main():
    print("=" * 60)
    print("PlantNet300K 元数据构建 (v4)")

    # ==== 1. 加载 ====
    print("\n[1/3] 加载原始数据...")
    with open(META_PATH, "r", encoding="utf-8") as f:
        raw_meta = json.load(f)
    print(f"  图片元数据: {len(raw_meta):,} 条")

    with open(NAME_MAP_PATH, "r", encoding="utf-8") as f:
        sid_to_name = json.load(f)
    print(f"  物种名映射: {len(sid_to_name):,} 条")

    cn_map = {}
    if CN_MAP_PATH.exists():
        with open(CN_MAP_PATH, "r", encoding="utf-8") as f:
            cn_map = json.load(f)
        cn_count = sum(1 for v in cn_map.values() if any('一' <= c <= '鿿' for c in v))
        print(f"  中文名映射: {len(cn_map):,} 条 (含中文: {cn_count})")

    # ==== 2. 构建 ====
    print("\n[2/3] 构建元数据与 caption...")
    full_meta = {}
    organ_stats = {}

    for i, (img_hash, meta) in enumerate(raw_meta.items()):
        sid = meta.get("species_id", "")
        sname = sid_to_name.get(sid, "")
        cname = cn_map.get(sid, "")
        organ = meta.get("organ", "other")
        canonical = remove_author(sname)
        caption = build_caption(cname, sname, organ)

        full_meta[img_hash] = {
            "id": i,
            "image_hash": img_hash,
            "species_id": sid,
            "scientific_name": sname,
            "canonical_name": canonical,
            "chinese_name": cname,
            "caption": caption,
            "organ": organ,
            "organ_cn": ORGAN_LABELS.get(organ, organ),
            "author": meta.get("author", ""),
            "license": meta.get("license", ""),
            "split": meta.get("split", ""),
        }
        organ_stats[organ] = organ_stats.get(organ, 0) + 1

    print(f"  元数据条目: {len(full_meta):,} 条")

    # ==== 3. 写入 ====
    print("\n[3/3] 写入...")

    with open(OUT_FULL, "w", encoding="utf-8") as f:
        json.dump(full_meta, f, ensure_ascii=False, indent=2)
    size_mb = OUT_FULL.stat().st_size / 1024 / 1024
    print(f"  完整备份 → {OUT_FULL} ({size_mb:.1f} MB)")

    # 统计
    unique_species = len(set(m["species_id"] for m in full_meta.values()))
    print(f"\n[统计]")
    print(f"  物种数: {unique_species}")
    print(f"  器官分布:")
    for k, v in sorted(organ_stats.items(), key=lambda x: -x[1]):
        print(f"    {ORGAN_LABELS.get(k, k)}: {v:,}")

    # 预览
    keys = list(full_meta.keys())[:5]
    print(f"\n[Caption 预览]")
    for k in keys:
        print(f"  {full_meta[k]['caption']}")

    print(f"\n  注: 检索系统 metadata.json 由 build_plantnet300k_index.py 生成")
    print("=" * 60)
    print("完成!")


if __name__ == "__main__":
    main()
