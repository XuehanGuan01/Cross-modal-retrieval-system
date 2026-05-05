"""
系统性能 Profiling 脚本

评测 CN-CLIP 编码 + FAISS 检索的延迟分布。
输出 P50/P95/P99 和均值，可直接写入简历。

用法：
  python scripts/profile_performance.py [--iterations 100] [--device cpu]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

# 将 backend 目录加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.model_loader import CNClipModelLoader
from core.processor import encode_single_text
from core.search_engine import SearchEngine
from core.domain_registry import DomainRegistry


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
GALLERY_DIR = BASE_DIR / "gallery"
IMAGE_BASE_URL = "/gallery"


def percentile(data: List[float], p: float) -> float:
    """计算百分位数（线性插值）"""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100.0
    f = int(k)
    c = k - f
    if f + 1 < len(sorted_data):
        return sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f])
    return sorted_data[f]


def stats(data: List[float]) -> Dict[str, float]:
    """计算均值、P50、P95、P99、min、max"""
    if not data:
        return {"mean": 0, "p50": 0, "p95": 0, "p99": 0, "min": 0, "max": 0}
    return {
        "mean": sum(data) / len(data),
        "p50": percentile(data, 50),
        "p95": percentile(data, 95),
        "p99": percentile(data, 99),
        "min": min(data),
        "max": max(data),
    }


def fmt_ms(val: float) -> str:
    if val < 1:
        return f"{val * 1000:.1f}us"
    if val < 1000:
        return f"{val:.1f}ms"
    return f"{val / 1000:.2f}s"


def fmt_stats(s: Dict[str, float], unit: str = "ms") -> str:
    if unit == "ms":
        return f"mean={fmt_ms(s['mean'])}  p50={fmt_ms(s['p50'])}  p95={fmt_ms(s['p95'])}  p99={fmt_ms(s['p99'])}"
    return f"mean={s['mean']:.2f}  p50={s['p50']:.2f}  p95={s['p95']:.2f}  p99={s['p99']:.2f}"


def main(iterations: int = 100):
    print("=" * 60)
    print("系统性能 Profiling")
    print("=" * 60)

    # ---- 1. 加载模型 ----
    print("\n[1/4] 加载 CN-CLIP 模型...")
    try:
        loader = CNClipModelLoader(model_name="ViT-B-16")
        device = loader.device
        print(f"  设备: {device}")
    except Exception as e:
        print(f"  模型加载失败: {e}")
        print("  请确保 conda 环境中安装了 cn_clip 和 torch")
        sys.exit(1)

    # ---- 2. 加载领域 ----
    print("\n[2/4] 加载领域索引...")
    registry = DomainRegistry(data_dir=DATA_DIR, gallery_dir=GALLERY_DIR)
    domains = registry.auto_discover()
    engines: Dict[str, SearchEngine] = {}

    for name, config in domains.items():
        engine = SearchEngine.from_files(
            index_path=config.index_path,
            metadata_path=config.metadata_path,
            image_base_url=IMAGE_BASE_URL,
            path_prefix=name,
        )
        engines[name] = engine
        print(f"  {name}: {config.image_count:,} 图片, {engine.index.ntotal:,} 向量")

    # ---- 3. 性能评测 ----
    print(f"\n[3/4] 执行性能评测 (iterations={iterations})...")

    # 测试查询集（覆盖4个领域 + 短/长文本）
    test_queries = [
        "一只白色的猫坐在窗台上",
        "开着黄色小花的植物",
        "红色连衣裙女装",
        "黑白条纹的斑马",
        "海滩上的日落",
        "花",                           # 极短
        "一种生长在热带雨林中的大型蕨类植物的叶片特写",  # 极长
        "物种命名：蒲公英，植物部位：花",      # 结构化 caption 格式
    ]

    results: Dict[str, Any] = {
        "text_encode": {"unit": "ms", "per_domain": {}},
        "faiss_full": {"unit": "ms", "per_domain": {}},
        "faiss_subset": {"unit": "ms", "per_domain": {}},
        "end_to_end": {"unit": "ms", "per_domain": {}},
        "model_load": {},
        "index_meta": {},
    }

    # --- 3a. 文本编码延迟 ---
    print("\n  [文本编码延迟]")
    text_encode_times: List[float] = []
    warmup_done = False
    for i in range(iterations + 5):  # 前5次 warmup
        query = test_queries[i % len(test_queries)]
        t0 = time.perf_counter()
        encode_single_text(loader.model, query, device=str(device))
        elapsed = (time.perf_counter() - t0) * 1000  # ms
        if i >= 5:
            text_encode_times.append(elapsed)
    s = stats(text_encode_times)
    results["text_encode"]["overall"] = s
    print(f"    整体: {fmt_stats(s)}")

    # --- 3b. FAISS 全量检索延迟 ---
    print("\n  [FAISS 全量检索延迟]")
    # 预编码一个文本向量
    query_vec = encode_single_text(loader.model, "一只白色的猫", device=str(device))

    for domain_name, engine in engines.items():
        times: List[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            engine.search(query_vec, top_k=10)
            elapsed = (time.perf_counter() - t0) * 1000
            times.append(elapsed)
        s = stats(times)
        results["faiss_full"]["per_domain"][domain_name] = s
        nvec = engine.index.ntotal
        print(f"    {domain_name} ({nvec:,} 向量): {fmt_stats(s)}")

    # --- 3c. FAISS 子集检索延迟 ---
    print("\n  [FAISS 子集检索延迟]")
    for domain_name, engine in engines.items():
        nvec = engine.index.ntotal
        # 构造一个候选子集（取前 500 个或全部向量的 10%）
        subset_size = min(500, max(50, nvec // 10))
        candidate_indices = list(range(subset_size))

        times: List[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            engine.search_in_subset(query_vec, candidate_indices, top_k=10)
            elapsed = (time.perf_counter() - t0) * 1000
            times.append(elapsed)
        s = stats(times)
        results["faiss_subset"]["per_domain"][domain_name] = s
        print(f"    {domain_name} (子集 {subset_size}): {fmt_stats(s)}")

    # --- 3d. 端到端检索延迟 ---
    print("\n  [端到端检索延迟 (encode + search)]")
    for domain_name, engine in engines.items():
        times: List[float] = []
        for i in range(iterations):
            query = test_queries[i % len(test_queries)]
            t0 = time.perf_counter()
            vec = encode_single_text(loader.model, query, device=str(device))
            engine.search(vec, top_k=10)
            elapsed = (time.perf_counter() - t0) * 1000
            times.append(elapsed)
        s = stats(times)
        results["end_to_end"]["per_domain"][domain_name] = s
        print(f"    {domain_name}: {fmt_stats(s)}")

    # ---- 4. 汇总报告 ----
    print(f"\n{'=' * 60}")
    print("[4/4] 汇总报告")
    print(f"{'=' * 60}")

    # 模型信息
    print(f"\n  模型: CN-CLIP ViT-B-16, dim=512, device={device}")
    print(f"  领域数: {len(engines)}")
    total_imgs = sum(c.image_count for c in domains.values())
    total_vecs = sum(engines[d].index.ntotal for d in engines)
    total_index_size = sum(
        (DATA_DIR / d / "images.index").stat().st_size
        for d in engines
        if (DATA_DIR / d / "images.index").exists()
    )
    print(f"  数据规模: {total_imgs:,} 图片, {total_vecs:,} 向量, 索引 {total_index_size / 1024 / 1024:.1f} MB")

    # 文本编码
    te = results["text_encode"]["overall"]
    print(f"\n  文本编码 (CN-CLIP): mean={te['mean']:.2f}ms, p95={te['p95']:.2f}ms, p99={te['p99']:.2f}ms")

    # FAISS 检索表格
    print(f"\n  {'FAISS检索':-^50}")
    print(f"  {'领域':<10} {'向量数':>8} {'全量P95':>10} {'子集P95':>10}")
    for dn in ["auto", "plant", "animal", "shop"]:
        if dn in engines:
            nv = engines[dn].index.ntotal
            fp95 = results["faiss_full"]["per_domain"].get(dn, {}).get("p95", 0)
            sp95 = results["faiss_subset"]["per_domain"].get(dn, {}).get("p95", 0)
            print(f"  {dn:<10} {nv:>8,} {fmt_ms(fp95):>10} {fmt_ms(sp95):>10}")

    # 端到端表格
    print(f"\n  {'端到端延迟 (encode+search)':-^50}")
    print(f"  {'领域':<10} {'mean':>10} {'p50':>10} {'p95':>10} {'p99':>10}")
    for dn in ["auto", "plant", "animal", "shop"]:
        if dn in engines:
            e2e = results["end_to_end"]["per_domain"].get(dn, {})
            print(f"  {dn:<10} {fmt_ms(e2e.get('mean',0)):>10} {fmt_ms(e2e.get('p50',0)):>10} {fmt_ms(e2e.get('p95',0)):>10} {fmt_ms(e2e.get('p99',0)):>10}")

    # 简历摘要
    print(f"\n{'=' * 40}")
    print(f"[Resume] 简历可用数据：")
    te_p95 = te['p95']
    te_p50 = te['p50']
    print(f"   文本编码延迟: {te_p50:.1f}ms (P50) / {te_p95:.1f}ms (P95)")

    # 取四个领域中最大的 P95 作为保守估计
    worst_p95 = max(
        results["faiss_full"]["per_domain"].get(dn, {}).get("p95", 0)
        for dn in engines
    )
    worst_e2e_p95 = max(
        results["end_to_end"]["per_domain"].get(dn, {}).get("p95", 0)
        for dn in engines
    )
    best_e2e_p50 = min(
        results["end_to_end"]["per_domain"].get(dn, {}).get("p50", 999)
        for dn in engines
    )
    print(f"   FAISS 全量检索延迟: < {worst_p95:.1f}ms (P95, 最差领域)")
    print(f"   端到端检索延迟: {best_e2e_p50:.1f}ms (P50) ~ {worst_e2e_p95:.1f}ms (P95)")
    print(f"{'=' * 40}")

    # 保存 JSON 报告
    report_path = BASE_DIR / "performance_report.json"
    # 清理不可序列化的对象
    clean_results = _make_serializable(results)
    clean_results["total_images"] = total_imgs
    clean_results["total_vectors"] = total_vecs
    clean_results["total_index_mb"] = round(total_index_size / 1024 / 1024, 1)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(clean_results, f, ensure_ascii=False, indent=2)
    print(f"\n  详细报告已保存至: {report_path}")

    return results


def _make_serializable(obj: Any) -> Any:
    """递归转换 numpy 类型和 Path 对象为 Python 原生类型"""
    if isinstance(obj, dict):
        return {str(k): _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, Path):
        return str(obj)
    return obj


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="系统性能 Profiling")
    parser.add_argument("--iterations", type=int, default=100,
                        help="每个评测项的迭代次数 (default: 100)")
    parser.add_argument("--device", type=str, default=None,
                        help="设备 (default: auto)")
    args = parser.parse_args()

    main(iterations=args.iterations)
