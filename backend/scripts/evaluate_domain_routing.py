"""
领域自动路由准确率评测脚本

评测 pipeline.py 中关键词规则路由的准确率。
不依赖模型，纯规则匹配。

用法：python scripts/evaluate_domain_routing.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple

# ---- 复制 pipeline.py 中的关键词库和检测逻辑 ----

DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "plant": [
        "花", "草", "树", "叶", "植物", "果实", "种子", "花瓣", "叶子",
        "开花", "草本", "木本", "灌木", "乔木", "野花", "野草", "草药",
        "玫瑰", "牡丹", "菊花", "兰花", "蒲公英", "松树", "竹子", "荷花",
        "梅花", "桃花", "樱花", "向日葵", "仙人掌", "蕨类", "苔藓",
        "茎", "根", "枝", "苗", "芽", "药材",
    ],
    "animal": [
        "动物", "鸟", "鱼", "狗", "猫", "马", "牛", "羊", "猪", "鸡", "鸭",
        "虎", "狮", "象", "猴", "蛇", "熊", "狼", "鹿", "兔", "鼠",
        "虫", "蝴蝶", "蜻蜓", "蜘蛛", "蚂蚁", "蜜蜂",
        "宠物", "野兽", "哺乳", "爬行", "两栖", "飞禽", "走兽",
        "斑马", "老虎", "狮子", "长颈鹿", "企鹅", "海豚", "鲸鱼", "鲨鱼",
        "老鹰", "孔雀", "天鹅", "松鼠", "刺猬", "考拉", "袋鼠", "熊猫",
    ],
    "shop": [
        "衣服", "裙子", "裤子", "鞋", "包", "手机", "电脑", "笔记本",
        "家具", "化妆品", "玩具", "首饰", "手表", "眼镜", "帽子",
        "连衣裙", "T恤", "运动鞋", "高跟鞋", "衬衫", "外套", "羽绒服",
        "商品", "购物", "电商", "淘宝", "网购", "品牌",
        "口红", "香水", "项链", "戒指", "耳环", "手链",
        "沙发", "桌子", "椅子", "床", "灯具", "窗帘",
    ],
}


def detect_domain(query: str) -> str:
    """与 pipeline.py AgentPipeline._detect_domain 完全一致的逻辑"""
    scores: Dict[str, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in query)
        if score > 0:
            scores[domain] = score
    if not scores:
        return "auto"
    return max(scores, key=scores.get)


# ---- 测试用例 ----

# 格式：(query, expected_domain)
# 每个领域 30 条，覆盖常见用户表述

TEST_QUERIES: List[Tuple[str, str]] = [
    # ========== plant (30条) ==========
    ("帮我找一种开黄色小花的植物", "plant"),
    ("粉色的玫瑰花图片", "plant"),
    ("这是什么花", "plant"),
    ("找一张蒲公英的照片", "plant"),
    ("红色的叶子", "plant"),
    ("开白花的树", "plant"),
    ("多肉植物", "plant"),
    ("松树的果实", "plant"),
    ("春天开花的野草", "plant"),
    ("仙人掌开花", "plant"),
    ("梅花含苞待放", "plant"),
    ("樱花飘落的场景", "plant"),
    ("竹子林的风景", "plant"),
    ("蕨类植物的叶片", "plant"),
    ("向日葵花田", "plant"),
    ("荷花池塘", "plant"),
    ("桃花盛开", "plant"),
    ("一株蓝色的小野花", "plant"),
    ("兰花的品种", "plant"),
    ("牡丹花的特写", "plant"),
    ("寻找一种药用植物", "plant"),
    ("心形叶子的灌木", "plant"),
    ("秋天的枫叶", "plant"),
    ("嫩芽刚冒出土壤", "plant"),
    ("草本植物开花", "plant"),
    ("乔木的树皮纹理", "plant"),
    ("种子发芽的过程", "plant"),
    ("带刺的茎", "plant"),
    ("这种草的根茎", "plant"),
    ("盆栽植物的叶子发黄", "plant"),

    # ========== animal (30条) ==========
    ("找一只黑白条纹的斑马", "animal"),
    ("老虎在丛林中", "animal"),
    ("一只猫趴在窗台上", "animal"),
    ("飞翔的老鹰", "animal"),
    ("海豚跃出水面", "animal"),
    ("小狗在草地上奔跑", "animal"),
    ("长颈鹿吃树叶", "animal"),
    ("企鹅在冰面上行走", "animal"),
    ("孔雀开屏", "animal"),
    ("考拉抱着树干", "animal"),
    ("松鼠啃坚果", "animal"),
    ("鲸鱼喷水", "animal"),
    ("狮子的特写", "animal"),
    ("蝴蝶停在花瓣上", "animal"),
    ("熊猫吃竹子的照片", "animal"),
    ("蛇盘绕在树枝上", "animal"),
    ("鹿群在森林中", "animal"),
    ("刺猬蜷缩成球", "animal"),
    ("蜜蜂采蜜", "animal"),
    ("一只牛在吃草", "animal"),
    ("猴子在树上跳跃", "animal"),
    ("蜻蜓在池塘边", "animal"),
    ("天鹅在水面上游", "animal"),
    ("马在草原上奔跑", "animal"),
    ("一头大象", "animal"),
    ("兔子在草地上", "animal"),
    ("鲨鱼游过珊瑚礁", "animal"),
    ("蚂蚁搬运食物", "animal"),
    ("一只羊在山坡上", "animal"),
    ("熊在河边捕鱼", "animal"),

    # ========== shop (30条) ==========
    ("帮我找红色的连衣裙", "shop"),
    ("女士手提包", "shop"),
    ("一双白色运动鞋", "shop"),
    ("好看的T恤", "shop"),
    ("冬天穿的羽绒服", "shop"),
    ("黑色高跟鞋", "shop"),
    ("男士衬衫", "shop"),
    ("牛仔裤子", "shop"),
    ("华为手机", "shop"),
    ("苹果笔记本电脑", "shop"),
    ("复古风格的眼镜", "shop"),
    ("棒球帽子", "shop"),
    ("最新款的口红", "shop"),
    ("香水的瓶子设计", "shop"),
    ("钻石项链", "shop"),
    ("黄金戒指", "shop"),
    ("珍珠耳环", "shop"),
    ("品牌手表", "shop"),
    ("北欧风格沙发", "shop"),
    ("实木桌子", "shop"),
    ("办公椅子", "shop"),
    ("双人床", "shop"),
    ("客厅灯具", "shop"),
    ("遮光窗帘", "shop"),
    ("儿童玩具车", "shop"),
    ("化妆品套盒", "shop"),
    ("运动外套", "shop"),
    ("真皮男鞋", "shop"),
    ("智能手表最新款", "shop"),
    ("韩国化妆品", "shop"),

    # ========== auto (30条) ==========
    ("海滩上的日落风景", "auto"),
    ("城市街道夜景", "auto"),
    ("一座古老的建筑", "auto"),
    ("两个人在喝咖啡", "auto"),
    ("一辆红色汽车停在路边", "auto"),
    ("雪山下的小木屋", "auto"),
    ("雨天的街景", "auto"),
    ("飞机起飞的照片", "auto"),
    ("沙滩上的人群", "auto"),
    ("白色的教堂建筑", "auto"),
    ("火车经过田野", "auto"),
    ("一个人在跑步", "auto"),
    ("桥梁横跨河流", "auto"),
    ("星空下的帐篷", "auto"),
    ("市场里摆摊的场景", "auto"),
    ("摩天大楼群", "auto"),
    ("骑自行车的人", "auto"),
    ("教室里的学生", "auto"),
    ("一杯咖啡的特写", "auto"),
    ("瀑布和彩虹", "auto"),
    ("图书馆内部", "auto"),
    ("自行车停靠在墙边", "auto"),
    ("蓝天白云下的草原", "auto"),
    ("夜晚的霓虹灯", "auto"),
    ("一面涂鸦墙", "auto"),
    ("楼梯和走廊", "auto"),
    ("花园里的长椅", "auto"),
    ("音乐会的舞台", "auto"),
    ("地铁站里的人流", "auto"),
    ("路边的指示牌", "auto"),
]


def main():
    print("=" * 60)
    print("领域自动路由准确率评测")
    print("=" * 60)

    # 逐条评测
    results: Dict[str, Dict[str, int]] = {
        "plant":  {"correct": 0, "total": 0},
        "animal": {"correct": 0, "total": 0},
        "shop":   {"correct": 0, "total": 0},
        "auto":   {"correct": 0, "total": 0},
    }
    errors: List[Tuple[str, str, str]] = []

    for query, expected in TEST_QUERIES:
        predicted = detect_domain(query)
        results[expected]["total"] += 1
        if predicted == expected:
            results[expected]["correct"] += 1
        else:
            errors.append((query, expected, predicted))

    # 打印逐领域结果
    print()
    print(f"{'领域':<10} {'正确':>6} {'总数':>6} {'准确率':>10}")
    print("-" * 35)
    total_correct = 0
    total_count = 0
    for domain in ["plant", "animal", "shop", "auto"]:
        r = results[domain]
        acc = r["correct"] / r["total"] * 100 if r["total"] else 0
        total_correct += r["correct"]
        total_count += r["total"]
        print(f"{domain:<10} {r['correct']:>6} {r['total']:>6} {acc:>9.1f}%")

    overall = total_correct / total_count * 100 if total_count else 0
    print("-" * 35)
    print(f"{'总计':<10} {total_correct:>6} {total_count:>6} {overall:>9.1f}%")

    # 打印错误明细
    if errors:
        print(f"\n错误明细 ({len(errors)} 条)：")
        for q, exp, pred in errors:
            print(f"  查询: 「{q}」 → 预测={pred}  期望={exp}")

    # 混淆矩阵
    print(f"\n{'混淆矩阵':=^40}")
    matrix: Dict[str, Dict[str, int]] = {}
    for d1 in ["plant", "animal", "shop", "auto"]:
        matrix[d1] = {d2: 0 for d2 in ["plant", "animal", "shop", "auto"]}

    for query, expected in TEST_QUERIES:
        predicted = detect_domain(query)
        matrix[expected][predicted] += 1

    print(f"{'':>8} {'plant':>8} {'animal':>8} {'shop':>8} {'auto':>8}")
    for d1 in ["plant", "animal", "shop", "auto"]:
        row = " ".join(f"{matrix[d1][d2]:>8}" for d2 in ["plant", "animal", "shop", "auto"])
        print(f"{d1:>8} {row}")

    # 输出摘要（可直接写入简历）
    print(f"\n{'=' * 40}")
    print(f"[Resume] 简历可用数据：")
    print(f"   领域自动路由准确率: {overall:.1f}% ({total_correct}/{total_count})")
    for domain in ["plant", "animal", "shop", "auto"]:
        r = results[domain]
        acc = r["correct"] / r["total"] * 100
        print(f"   {domain}: {acc:.1f}% ({r['correct']}/{r['total']})")
    print(f"{'=' * 40}")

    return overall, results, errors


if __name__ == "__main__":
    main()
