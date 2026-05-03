# 交互式跨模态检索 Agent — 系统迭代方案 v2pro

> **基于 v2 方案的优化版**。根据 2026-05-03 讨论，删除 medical 领域、适配动物子目录、采纳 Agent 推理 Pipeline 优化方案。
> 本文档仅输出方案，不做任何代码修改。

---

## 〇、修订说明（相比 v2）

| 维度           | v2 方案                                                                                                  | v2pro 修订                                                                                |
| ------------ | ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| 领域划分         | auto + medical + plant + animal + shop（5领域）                                                            | **auto + plant + animal + shop（4领域）**，删除 medical                                        |
| medical 领域   | 预留医学影像领域                                                                                               | **删除** — 医学影像无现实意义，需专用 CLIP 模型                                                          |
| animal 图片结构  | 未特殊说明                                                                                                  | **需处理子目录结构** — gallery/animal/{class_name}/{class_name}_{id}.jpg                        |
| Agent 推理架构   | 8节点 LangGraph（IntentParser → DomainLocator → QueryExtractor → VectorSearch → RAG → Reflect → Response） | **4步简化 Pipeline**（LLM特征提取 → 文本浓缩 → CLIP+FAISS检索 → 结果反馈+对话循环），采纳 [[Agent推理Pipeline优化方案]] |
| Agent Prompt | 通用意图解析 JSON                                                                                            | **领域感知 Prompt**（plant: 物种过滤，animal: 类别过滤，auto/shop: 直接检索），采纳 [[Agent推理Prompt模板设计]]      |
| LLM 调用方式     | LangGraph 多节点 LLM 调用                                                                                   | **精简为 2 次 LLM 调用**（特征提取 + 可选 Rerank），减少延迟和成本                                            |
| 前端           | 两大板块 + AgentChat UI                                                                                    | **不变**                                                                                  |

---

## 一、当前系统基线（2026-05-03 最终态）

### 1.1 领域数据状态

| Domain | Gallery 图片 | 子目录 | Metadata 条目 | FAISS 向量 | 属性字段 |
|--------|:--:|:--:|:--:|:--:|------|
| auto | 155,070 | 扁平 | 52,077 | 52,077 | `dataset`（COCO-CN / Flickr30k-CN） |
| plant | 306,146 | 扁平 | 306,146 | 306,146 | `species_id`, `organ`, `author`, `license` |
| animal | 37,322 | **50 个类别子目录** | 37,322 | 37,322 | `class_name`, `class_name_cn`, `predicates_en`, `predicates_cn` |
| shop | 159,186 | 扁平 | 159,186 | 159,186 | `dataset`（MUGE） |
| **合计** | **657,724** | | **554,731** | **554,731** | |

### 1.2 animal 领域特殊说明

animal 的 gallery 结构与其余三者不同，图片按 50 个动物类别分目录存储：

```
gallery/animal/
├── antelope/antelope_10001.jpg
├── bat/bat_10002.jpg
├── zebra/zebra_1170.jpg
```

**影响**：
- `metadata.json` 中 `path` 字段为相对路径（如 `"antelope/antelope_10001.jpg"`）
- 图片 URL 构造需拼接子目录路径
- 检索结果展示时需正确组装 `gallery/animal/` + `path`

**处理方式**（Phase 1 实现）：
- `SearchEngine` 的 `image_base_url` 构造逻辑已支持子目录（只需正确拼接 `gallery_dir / metadata_path`）
- `DomainRegistry` 的 `gallery_dir` 指向 `gallery/animal/`，`metadata.path` 包含子目录部分

### 1.3 后端现状

```
backend/
├── api_server.py              # FastAPI: 当前仅加载全局旧索引
├── core/
│   ├── model_loader.py        # CNClipModelLoader (ViT-B-16, dim=512)
│   ├── processor.py           # encode_images / encode_texts
│   └── search_engine.py       # SearchEngine (FAISS IndexFlatIP)
├── scripts/
│   ├── build_index.py         # v1 legacy（无 caption）
│   ├── build_plantnet300k_index.py
│   ├── build_awa2_index.py
│   └── build_caption_index.py # auto/shop 通用
├── data/
│   ├── auto/    (images.index + metadata.json)
│   ├── plant/   (images.index + metadata.json)
│   ├── animal/  (images.index + metadata.json)
│   └── shop/    (images.index + metadata.json)
├── gallery/
│   ├── auto/    (155,070 张，扁平)
│   ├── plant/   (306,146 张，扁平)
│   ├── animal/  (37,322 张，50个子目录)
│   └── shop/    (159,186 张，扁平)
└── model/
    └── epoch_latest.pt
```

**核心限制**（与 v2 相同）：
1. API server 未支持多领域路由 — 仅加载全局旧索引
2. 无 LLM 集成
3. 无状态请求 — 无法多轮对话

### 1.4 前端现状

与 v2 方案 §1.2 相同，不再重复。

---

## 二、Phase 1：多领域隔离 + API 适配

**目标**：完成领域注册、多索引加载、API 领域路由，前端增加领域选择。

### 2.1 领域配置（4 领域，删除 medical）

| 文件夹名 | domain 值 | 描述 | gallery 结构 |
|---------|-----------|------|-------------|
| `auto` | `"auto"` | 泛化图片检索 | 扁平 |
| `plant` | `"plant"` | 植物识别 | 扁平 |
| `animal` | `"animal"` | 动物识别 | **50 个子目录** |
| `shop` | `"shop"` | 电商商品 | 扁平 |

### 2.2 后端改动

#### 2.2.1 新建：`backend/core/domain_registry.py`

```text
作用：领域注册中心，自动扫描 data/ 目录发现所有领域

关键适配 — animal 子目录处理：
  - DomainConfig 增加 gallery_subdir_style: "flat" | "class_subdirs"
  - animal 领域标记为 "class_subdirs"
  - 图片 URL 构造时自动处理路径拼接

DomainConfig:
  - name: str
  - index_path: Path
  - metadata_path: Path
  - gallery_dir: Path
  - image_count: int
  - description: str
  - gallery_style: "flat" | "class_subdirs"  # ★ 新增

DomainRegistry:
  - auto_discover() → Dict[str, DomainConfig]
  - get(name) → DomainConfig
  - list_all() → List[DomainConfig]
  - default_domain = "auto"
```

#### 2.2.2 新建：`backend/core/metadata_schema.py`

与 v2 方案 §3.1.2 相同。

```python
class MetadataItem(TypedDict):
    id: int
    path: str          # animal: "antelope/antelope_10001.jpg", 其余: "xxx.jpg"
    caption: str
    domain: str
    attributes: dict
    source: str
```

#### 2.2.3 修改：`backend/core/search_engine.py`

```text
改动：
  - 构造函数接受 gallery_dir: Path 参数
  - image_url 构造逻辑适配子目录路径：
    image_url = f"/gallery/{domain}/{metadata['path']}"
  - 对于 animal 领域，path 已含子目录，直接拼接即可
```

#### 2.2.4 修改：`backend/api_server.py`

```text
1. startup 事件：
   - DomainRegistry.auto_discover() → 发现 4 个领域
   - 为每个领域预加载 SearchEngine → engines: Dict[str, SearchEngine]
   - 默认引擎 → "auto"（泛化领域，用户未指定时使用）

2. 新增端点：
   GET /api/domains → List[{name, description, image_count}]

3. 修改现有端点：
   POST /api/search/text  — 增加可选 domain 参数（默认 "auto"）
   POST /api/search/image — 增加可选 domain 参数（默认 "auto"）

4. 静态文件挂载：
   - 挂载 /gallery/ → backend/gallery/
   - animal 子目录路径自动由浏览器解析
```

### 2.3 前端改动

与 v2 方案 §3.2 相同（`DomainInfo`、`fetchDomains()`、SearchBar 领域选择器、DirectSearch.vue）。

**差异**：领域列表仅 4 项，无 medical。

### 2.4 Phase 1 产出物汇总

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `backend/core/domain_registry.py` | 4领域注册中心，含 animal 子目录适配 |
| 新建 | `backend/core/metadata_schema.py` | 元数据 schema |
| 修改 | `backend/core/search_engine.py` | 适配子目录路径 |
| 修改 | `backend/api_server.py` | 多引擎预加载 + /api/domains + domain 参数 |
| 新建 | `frontend/src/views/DirectSearch.vue` | 抽取现有检索界面 |
| 修改 | `frontend/src/api/search.ts` | 增加 fetchDomains + domain 参数 |
| 修改 | `frontend/src/stores/search.ts` | 增加 currentDomain |
| 修改 | `frontend/src/components/SearchBar.vue` | 增加领域下拉选择器 |

---

## 三、Phase 2：前端双板块 + Agent UI 骨架

**目标**：前端划分为两大功能板块，Agent 板块 UI 就位。

### 3.1 前端架构

与 v2 方案 §4.1 相同：

```
App.vue
├── el-header → 跨模态检索系统 · 交互式 Agent
└── el-main
    └── el-tabs → 直接检索 | 智能搜物 Agent
        ├── DirectSearch.vue（Phase 1）
        └── AgentChat.vue（Phase 2 UI，Phase 3 接入逻辑）
```

### 3.2 Phase 2 产出物汇总

与 v2 方案 §4.4 相同（无 medical 相关调整）。

---

## 四、Phase 3：Agent 推理 Pipeline（★ 核心优化）

**目标**：实现智能搜物 Agent，采纳 `Agent推理Pipeline优化方案.md` 和 `Agent推理Prompt模板设计.md` 的精简架构。

### 4.1 架构对比：v2 vs v2pro

| 维度 | v2（LangGraph 8节点） | v2pro（4步 Pipeline） |
|------|----------------------|----------------------|
| LLM 调用次数 | 4~6 次（IntentParser + RAG + Reflect + Response） | **1~2 次**（特征提取 + 可选 Rerank） |
| 检索策略 | 全量 FAISS → RAG 推理 Top-3 | **子集过滤（有属性时）→ CLIP 检索** |
| 领域适配 | 通用流程 | **领域感知** — 有属性则过滤，无属性则直接检索 |
| 多轮对话 | LangGraph conditional edges 循环 | **对话状态机**（IDLE → EXTRACTING → SEARCHING → PRESENTING） |
| 复杂度 | 高（8节点 + 4条件边 + Redis checkpoint） | **中**（4步 + 状态机） |

### 4.2 整体推理流程

```
用户输入 "帮我找一种开黄色小花、叶子心形的植物"
       │
       ▼
┌──────────────────────────────────────┐
│ Step 1: LLM 领域感知特征提取          │  ← 1 次 LLM 调用
│                                        │
│ 根据当前领域，提取特征：                 │
│  - plant: species_id + organ + 形态   │
│  - animal: class_name + 属性          │
│  - auto/shop: 浓缩查询文本（≤20字）    │
│                                        │
│ 输出: { features, candidates, query } │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ Step 2: 文本浓缩（规则引擎，非 LLM）    │
│                                        │
│ 将特征转为 CLIP 友好的检索文本：         │
│  - plant: "物种命名：xxx，植物部位：x"  │
│  - animal: "类别：xxx"                 │
│  - auto/shop: 直接使用原查询            │
│                                        │
│ 目的：对齐 metadata caption 格式       │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ Step 3: CLIP + FAISS 检索             │
│                                        │
│ 策略 A（有候选ID）：子集过滤 + CLIP 检索 │
│ 策略 B（无候选ID）：全量 CLIP 检索      │
│                                        │
│ 降级：候选图片 < 50 → 自动降级全量检索  │
│ 降级：CLIP 相似度 max < 0.3 → 提示用户  │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ Step 4: 结果反馈 + 对话循环            │
│                                        │
│ 展示 Top-K 结果 + 追问引导              │
│ 用户确认 → 结束                        │
│ 用户细化 → 回到 Step 1                 │
│ 用户扩大 → 放宽条件 → Step 2           │
└──────────────────────────────────────┘
```

### 4.3 Step 1：领域感知特征提取

#### 4.3.1 plant 领域 Prompt（采纳 `Agent推理Prompt模板设计.md` §二）

```
System: 你是植物学检索专家。根据用户描述，从植物物种库中筛选候选。

输入：
- 用户查询（中文自然语言）
- 物种知识库（species_id + 学名 + 中文名）

输出（JSON）：
{
  "query_type": "species_name" | "morphology" | "mixed",
  "features": {
    "color": "花色/叶色",
    "shape": "叶形/花形",
    "organ": "flower" | "leaf" | "fruit" | "bark" | "habit" | "any"
  },
  "reasoning": "推理过程",
  "candidate_species_ids": ["1355868", ...],   // 最多20个
  "condensed_query": "物种命名：xxx，植物部位：xxx",
  "confidence": 0.85
}

约束：
- species_id 从知识库中选取，不可编造
- 不确定时宁可多选，不要遗漏
- condensed_query 对齐 caption 格式
```

#### 4.3.2 animal 领域 Prompt

```
System: 你是动物学检索专家。根据用户描述，从动物类别库中筛选候选。

输入：
- 用户查询（中文自然语言）
- 动物类别库（class_name + 中文名 + 属性列表）

输出（JSON）：
{
  "query_type": "class_name" | "attribute" | "mixed",
  "features": {
    "color": "颜色",
    "size": "体型",
    "habitat": "栖息地",
    "attributes": ["furry", "hooves", ...]
  },
  "reasoning": "推理过程",
  "candidate_classes": ["zebra", "horse", ...],
  "condensed_query": "类别：xxx",
  "confidence": 0.85
}
```

#### 4.3.3 auto / shop 领域

```text
无结构化属性 → 简化处理：
  - Step 1 输出 condensed_query = 用户原始查询（截断至 20 字）
  - 跳过候选过滤，直接全量 CLIP 检索
  - LLM 调用可选（仅用于查询改写，非必须）
```

### 4.4 Step 2：文本浓缩（规则引擎）

```python
TEXT_TEMPLATES = {
    "plant": {
        "species_name": "物种命名：{chinese_name}，植物部位：{organ}",
        "morphology": "植物照片，{color}的{organ}，{shape}",
        "bilingual": "{chinese_name} ({scientific_name}), {organ}",
    },
    "animal": {
        "class_name": "类别：{chinese_name}",
        "attribute": "动物照片，{attributes_str}",
    },
    "auto": {
        "direct": "{query}",      # 直接使用原查询
    },
    "shop": {
        "direct": "{query}",      # 直接使用原查询
    },
}
```

### 4.5 Step 3：CLIP + FAISS 检索

```python
def domain_search(domain, condensed_query, candidates=None, top_k=20):
    engine = engines[domain]
    metadata = domain_metadata[domain]

    if candidates and len(candidates) >= top_k * 2:
        # ★ 策略 A：子集过滤检索
        # plant: candidates = [species_id, ...]
        # animal: candidates = [class_name, ...]
        candidate_indices = [
            i for i, m in enumerate(metadata)
            if m.get_identifier() in candidates
        ]
        # FAISS 子集检索
        results = engine.search_in_subset(
            condensed_query, candidate_indices, top_k
        )
    else:
        # ★ 策略 B：全量检索
        results = engine.search(condensed_query, top_k)

    # 降级检测
    if results[0].score < 0.3:
        results.is_low_confidence = True

    return results
```

**子集过滤实现**：
- `faiss.IndexIDMap` 包装 `IndexFlatIP`，支持按 ID 子集检索
- 或：提取候选向量 → 构建临时小索引 → 检索

### 4.6 Step 4：结果反馈与对话状态机

```
            ┌──────────┐
            │   IDLE   │
            └────┬─────┘
                 │ 用户输入
                 ▼
         ┌──────────────┐
         │  EXTRACTING  │  ← Step 1: LLM 特征提取
         └──────┬───────┘
                │
                ▼
         ┌──────────────┐
         │  SEARCHING   │  ← Step 2+3: 文本浓缩 + CLIP+FAISS
         └──────┬───────┘
                │
                ▼
         ┌──────────────┐
         │  PRESENTING  │  ← Step 4: 展示结果 + 追问引导
         └──┬───┬───┬───┘
            │   │   │
    ┌───────┘   │   └────────┐
    ▼           ▼            ▼
┌────────┐ ┌────────┐ ┌──────────┐
│  DONE  │ │REFINING│ │EXPANDING │
│ 检索成 │ │细化条件│ │放宽条件   │
│ 功结束 │ │→EXTRACT│ │→EXTRACT  │
└────────┘ └────────┘ └──────────┘
```

**返回格式**：
```json
{
  "results": [
    {
      "rank": 1,
      "image_url": "/gallery/plant/xxx.jpg",
      "caption": "物种命名：蒲公英，植物部位：花",
      "similarity": 0.87,
      "metadata": {...}
    }
  ],
  "query_summary": "您搜索的 '黄色小花心形叶' 匹配到以下结果",
  "suggestions": [
    "是蒲公英吗？",
    "需要更偏红色的花吗？"
  ]
}
```

**对话分支**：

| 用户操作 | 系统响应 |
|---------|---------|
| "第3个是对的" | 确认结果 → DONE |
| "都不对，花更大一些" | 修改特征 → REFINING → Step 1 |
| "有没有其他颜色的" | 放宽约束 → EXPANDING → Step 2 |
| "这是什么植物" + 图片 | 以图搜图 → SEARCHING（跳过 Step 1） |

### 4.7 领域感知路由

```python
DOMAIN_AGENT_CONFIG = {
    "plant": {
        "has_structured_attrs": True,
        "attr_field": "species_id",
        "attr_name": "物种",
        "prompt_template": PLANT_EXTRACT_PROMPT,
        "candidate_limit": 20,
    },
    "animal": {
        "has_structured_attrs": True,
        "attr_field": "class_name",
        "attr_name": "类别",
        "prompt_template": ANIMAL_EXTRACT_PROMPT,
        "candidate_limit": 15,
    },
    "auto": {
        "has_structured_attrs": False,
        "use_direct_search": True,
    },
    "shop": {
        "has_structured_attrs": False,
        "use_direct_search": True,
    },
}
```

### 4.8 后端文件改动

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `backend/agent/__init__.py` | 模块入口 |
| 新建 | `backend/agent/llm_factory.py` | 阿里云 Qwen3-max LLM 工厂 |
| 新建 | `backend/agent/prompts.py` | 领域感知 Prompt 模板（plant/animal/auto/shop） |
| 新建 | `backend/agent/pipeline.py` | ★ 4步推理 Pipeline（非 LangGraph） |
| 新建 | `backend/agent/state_machine.py` | 对话状态机 |
| 新建 | `backend/agent/session_manager.py` | 会话管理（内存→Redis） |
| 新建 | `backend/agent/domain_agent.py` | 领域感知路由 + 子集检索 |
| 修改 | `backend/api_server.py` | 新增 /api/agent/chat 等端点 |

### 4.9 前端改动

与 v2 方案 §5.5 相同（AgentChat UI 接入真实逻辑、ChatPanel、AgentResultPanel）。

### 4.10 环境依赖

```
langchain-openai>=0.2.0      # DashScope LLM 调用
openai>=1.0.0                # 兼容 OpenAI SDK
redis>=5.0.0                 # 会话持久化（可选，Phase 3 可先用内存）
hiredis                      # Redis 高性能
sse-starlette>=2.0.0         # SSE 流式响应
```

**删除**（相比 v2）：不引入 LangGraph、langgraph-checkpoint（降低复杂度）。

---

## 五、Phase 4：长期记忆 + 主动建议

**目标**：跨会话记忆 + 用户偏好学习 + 主动建议。

与 v2 方案 Phase 4 保持一致（`memory.py`、`proactive_suggest.py`、Chroma 向量存储），不再重复。

---

## 六、后端目录结构全览（Phase 4 完成态）

```
backend/
├── api_server.py
├── requirements.txt
├── config/
│   └── agent_config.yaml
├── core/
│   ├── model_loader.py              # CNClipModelLoader
│   ├── processor.py                 # 编码器
│   ├── search_engine.py             # FAISS 搜索引擎（★ 适配子目录）
│   ├── domain_registry.py           # 4领域注册中心（★ Phase 1）
│   └── metadata_schema.py           # 元数据 schema（★ Phase 1）
├── agent/
│   ├── __init__.py
│   ├── pipeline.py                  # ★ 4步推理 Pipeline
│   ├── prompts.py                   # ★ 领域感知 Prompt 模板
│   ├── llm_factory.py              # LLM 工厂
│   ├── state_machine.py            # 对话状态机
│   ├── session_manager.py           # 会话管理
│   ├── domain_agent.py             # 领域感知路由 + 子集检索
│   ├── memory.py                    # 长期记忆（Phase 4）
│   └── proactive_suggest.py         # 主动建议（Phase 4）
├── scripts/
│   ├── build_plantnet300k_index.py
│   ├── build_awa2_index.py
│   └── build_caption_index.py
├── data/
│   ├── auto/    (images.index + metadata.json)
│   ├── plant/   (images.index + metadata.json)
│   ├── animal/  (images.index + metadata.json)
│   └── shop/    (images.index + metadata.json)
├── gallery/
│   ├── auto/    (155,070 张，扁平)
│   ├── plant/   (306,146 张，扁平)
│   ├── animal/  (37,322 张，50个子目录)
│   └── shop/    (159,186 张，扁平)
└── model/
    └── epoch_latest.pt
```

---

## 七、前端目录结构全览

与 v2 方案 §八 相同（无 medical 相关内容）。

---

## 八、Phase 1-4 接口对照

| Phase | 接口 | 方法 | 说明 |
|-------|------|------|------|
| 1 | `/api/health` | GET | 健康检查 |
| 1 | `/api/domains` | GET | 4领域列表 ★ |
| 1 | `/api/search/text` | POST | 文搜图（+ domain）★ |
| 1 | `/api/search/image` | POST | 图搜文（+ domain）★ |
| 3 | `/api/agent/chat` | POST | Agent 对话 ★ |
| 3 | `/api/agent/session/new` | POST | 创建会话 ★ |
| 3 | `/api/agent/session/{id}` | DELETE | 删除会话 ★ |

---

## 九、依赖变化

### 后端（相比 v2）

```text
# 删除：
# - langgraph, langgraph-checkpoint（不再使用 LangGraph 复杂图）
# 保留：
openai>=1.0.0
langchain-openai>=0.2.0
redis>=5.0.0
hiredis
sse-starlette>=2.0.0

# Phase 4 新增：
chromadb>=0.5.0
```

### 前端

无变化。

---

## 十、与 v2 的核心差异总结

1. **删除 medical** — 领域从 5 减至 4，代码中去除所有 medical 引用
2. **animal 子目录适配** — DomainRegistry 记录 gallery_style，SearchEngine 正确处理子目录路径
3. **Agent 架构精简** — 从 LangGraph 8节点图 → 4步 Pipeline，LLM 调用从 4~6 次 → 1~2 次
4. **领域感知 Prompt** — plant 有物种过滤、animal 有类别过滤、auto/shop 直接检索
5. **子集检索策略** — 利用 plant/animal 的结构化属性在 FAISS 中做子集过滤，显著缩小搜索空间
6. **对话状态机** — 替代 LangGraph conditional edges，更轻量且更易调试

---

> 文档生成时间：2026-05-03
> 基于：v2 方案 + Agent推理Pipeline优化方案 + Agent推理Prompt模板设计
