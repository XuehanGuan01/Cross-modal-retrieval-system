"""
AWA2 (Animals with Attributes 2) 元数据构建脚本
================================================
输入: E:/Animals_with_Attributes2/ （classes.txt, predicates.txt, predicate-matrix-binary.txt）
      backend/gallery/animal/ （图片目录）
输出: data/awa2_image_metadata_full.json

用法:
    cd "C:/Users/Lenovo/Desktop/Cross-modal retrieval system"
    python scripts/build_awa2_metadata.py
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GALLERY_ANIMAL = PROJECT_ROOT / "backend" / "gallery" / "animal"
DATA_OUT = PROJECT_ROOT / "data" / "awa2_image_metadata_full.json"
AWA2_SRC = Path("E:/Animals_with_Attributes2")

CLASSES_FILE = AWA2_SRC / "classes.txt"
PREDICATES_FILE = AWA2_SRC / "predicates.txt"
MATRIX_FILE = AWA2_SRC / "predicate-matrix-binary.txt"

# ========= 中英文类别名映射 =========
CLASS_CN_MAP: Dict[str, str] = {
    "antelope": "羚羊",
    "grizzly+bear": "灰熊",
    "killer+whale": "虎鲸",
    "beaver": "海狸",
    "dalmatian": "斑点狗",
    "persian+cat": "波斯猫",
    "horse": "马",
    "german+shepherd": "德国牧羊犬",
    "blue+whale": "蓝鲸",
    "siamese+cat": "暹罗猫",
    "skunk": "臭鼬",
    "mole": "鼹鼠",
    "tiger": "老虎",
    "hippopotamus": "河马",
    "leopard": "豹",
    "moose": "驼鹿",
    "spider+monkey": "蜘蛛猴",
    "humpback+whale": "座头鲸",
    "elephant": "大象",
    "gorilla": "大猩猩",
    "ox": "公牛",
    "fox": "狐狸",
    "sheep": "绵羊",
    "seal": "海豹",
    "chimpanzee": "黑猩猩",
    "hamster": "仓鼠",
    "squirrel": "松鼠",
    "rhinoceros": "犀牛",
    "rabbit": "兔子",
    "bat": "蝙蝠",
    "giraffe": "长颈鹿",
    "wolf": "狼",
    "chihuahua": "吉娃娃",
    "rat": "老鼠",
    "weasel": "黄鼠狼",
    "otter": "水獭",
    "buffalo": "水牛",
    "zebra": "斑马",
    "giant+panda": "大熊猫",
    "deer": "鹿",
    "bobcat": "短尾猫",
    "pig": "猪",
    "lion": "狮子",
    "mouse": "小鼠",
    "polar+bear": "北极熊",
    "collie": "牧羊犬",
    "walrus": "海象",
    "raccoon": "浣熊",
    "cow": "奶牛",
    "dolphin": "海豚",
}

# ========= 中英文属性名映射 =========
PREDICATE_CN_MAP: Dict[str, str] = {
    "black": "黑色",
    "white": "白色",
    "blue": "蓝色",
    "brown": "棕色",
    "gray": "灰色",
    "orange": "橙色",
    "red": "红色",
    "yellow": "黄色",
    "patches": "斑块",
    "spots": "斑点",
    "stripes": "条纹",
    "furry": "毛茸茸",
    "hairless": "无毛",
    "toughskin": "厚皮",
    "big": "大型",
    "small": "小型",
    "bulbous": "圆胖",
    "lean": "精瘦",
    "flippers": "鳍肢",
    "hands": "手",
    "hooves": "蹄",
    "pads": "肉垫",
    "paws": "爪子",
    "longleg": "长腿",
    "longneck": "长颈",
    "tail": "尾巴",
    "chewteeth": "咀嚼齿",
    "meatteeth": "食肉齿",
    "buckteeth": "龅牙",
    "strainteeth": "滤食齿",
    "horns": "角",
    "claws": "利爪",
    "tusks": "獠牙",
    "smelly": "臭味",
    "flys": "会飞",
    "hops": "跳跃",
    "swims": "游泳",
    "tunnels": "挖洞",
    "walks": "行走",
    "fast": "快速",
    "slow": "缓慢",
    "strong": "强壮",
    "weak": "弱小",
    "muscle": "肌肉",
    "bipedal": "双足",
    "quadrapedal": "四足",
    "active": "活跃",
    "inactive": "不活跃",
    "nocturnal": "夜行",
    "hibernate": "冬眠",
    "agility": "敏捷",
    "fish": "食鱼",
    "meat": "食肉",
    "plankton": "食浮游生物",
    "vegetation": "食草",
    "insects": "食虫",
    "forager": "觅食者",
    "grazer": "食草动物",
    "hunter": "狩猎者",
    "scavenger": "食腐者",
    "skimmer": "掠食者",
    "stalker": "潜行者",
    "newworld": "新世界",
    "oldworld": "旧世界",
    "arctic": "北极",
    "coastal": "沿海",
    "desert": "沙漠",
    "bush": "灌木丛",
    "plains": "平原",
    "forest": "森林",
    "fields": "田野",
    "jungle": "丛林",
    "mountains": "山区",
    "ocean": "海洋",
    "ground": "地面",
    "water": "水中",
    "tree": "树上",
    "cave": "洞穴",
    "fierce": "凶猛",
    "timid": "胆小",
    "smart": "聪明",
    "group": "群居",
    "solitary": "独居",
    "nestspot": "筑巢",
    "domestic": "家养",
}


def load_classes() -> List[str]:
    """加载 classes.txt，返回 50 个类别名（+ 替换为空格）"""
    classes = []
    with open(CLASSES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            cls_name = parts[-1].strip()
            classes.append(cls_name)
    return classes


def load_predicates() -> List[str]:
    """加载 predicates.txt，返回 85 个属性名"""
    predicates = []
    with open(PREDICATES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            pred_name = parts[-1].strip()
            predicates.append(pred_name)
    return predicates


def load_predicate_matrix() -> List[List[int]]:
    """加载 50×85 二值属性矩阵"""
    matrix = []
    with open(MATRIX_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = [int(x) for x in line.split()]
            matrix.append(row)
    return matrix


def find_images(gallery_dir: Path) -> List[Path]:
    """递归搜索所有图片"""
    paths = []
    for ext in ["jpg", "jpeg", "png", "webp"]:
        paths.extend(gallery_dir.rglob(f"*.{ext}"))
    return sorted(paths)


def class_name_from_path(filepath: Path, gallery_dir: Path) -> str:
    """从路径提取类别名（即所在子目录名）"""
    return filepath.parent.relative_to(gallery_dir).name


def build_caption(class_name: str, active_predicates_en: List[str]) -> str:
    """生成中文 caption：类别：xxx，属性：xxx、xxx"""
    cls_cn = CLASS_CN_MAP.get(class_name, class_name.replace("+", " "))
    pred_cn_list = [PREDICATE_CN_MAP.get(p, p) for p in active_predicates_en]
    # 限制属性数量，避免 caption 过长
    pred_str = "、".join(pred_cn_list[:12])
    if len(pred_cn_list) > 12:
        pred_str += "等"
    return f"类别：{cls_cn}，属性：{pred_str}"


def main():
    # 1. 加载原始标注
    print("[AWA2 Metadata] 加载 classes.txt ...")
    classes = load_classes()
    print(f"  类别数: {len(classes)}")

    print("[AWA2 Metadata] 加载 predicates.txt ...")
    predicates = load_predicates()
    print(f"  属性数: {len(predicates)}")

    print("[AWA2 Metadata] 加载 predicate-matrix-binary.txt ...")
    matrix = load_predicate_matrix()
    print(f"  矩阵: {len(matrix)} × {len(matrix[0])}")

    # 2. 建立 class_name → (class_index, attribute_vector) 映射
    class_info: Dict[str, dict] = {}
    for i, cls_name in enumerate(classes):
        active_preds = [predicates[j] for j, v in enumerate(matrix[i]) if v == 1]
        class_info[cls_name] = {
            "index": i,
            "class_name": cls_name,
            "class_name_cn": CLASS_CN_MAP.get(cls_name, cls_name.replace("+", " ")),
            "predicates_en": active_preds,
            "predicates_cn": [PREDICATE_CN_MAP.get(p, p) for p in active_preds],
        }

    # 3. 遍历图片
    print(f"[AWA2 Metadata] 扫描图片: {GALLERY_ANIMAL}")
    image_paths = find_images(GALLERY_ANIMAL)
    print(f"  图片总数: {len(image_paths):,}")

    # 4. 生成元数据
    output: Dict[str, dict] = {}
    idx = 0

    for img_path in image_paths:
        cls_name = class_name_from_path(img_path, GALLERY_ANIMAL)
        info = class_info.get(cls_name)
        if info is None:
            print(f"  [警告] 未知类别: {cls_name} ← {img_path.name}")
            continue

        rel_path = img_path.relative_to(GALLERY_ANIMAL).as_posix()
        caption = build_caption(cls_name, info["predicates_en"])

        output[rel_path] = {
            "id": idx,
            "path": rel_path,
            "caption": caption,
            "domain": "animal",
            "attributes": {
                "class_name": info["class_name"],
                "class_name_cn": info["class_name_cn"],
                "predicates_en": info["predicates_en"],
                "predicates_cn": info["predicates_cn"],
            },
            "source": "AWA2",
        }
        idx += 1

    # 5. 写入
    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"[AWA2 Metadata] 写入: {DATA_OUT}")
    with open(DATA_OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"[AWA2 Metadata] 完成! 共 {idx:,} 条记录")
    print(f"  输出: {DATA_OUT}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
