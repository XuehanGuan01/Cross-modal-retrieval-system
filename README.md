# 多领域跨模态 · 智能搜物 Agent

基于 **CN-CLIP + FAISS** 的跨模态图片检索系统，集成 **Qwen3-max** 大模型实现自然语言智能搜物，覆盖**植物、动物、电商商品、通用图片**四大领域，共 **55万+** 可检索图片。

---

## 功能概览

### 两大功能板块

| 板块 | 功能 | 说明 |
|------|------|------|
| **直接检索** | 文搜图 / 图搜文 | 选择领域 → 输入文本或上传图片 → 返回 Top-K 结果 |
| **智能搜物 Agent** | 多轮对话检索 | 自然语言描述需求 → LLM 理解意图 → CLIP+FAISS 检索 → 展示结果 + 追问引导 + 物种科普 |

### Agent 推理流程（4 步 Pipeline）

```
用户输入 "帮我找一种开黄色小花、叶子心形的植物"
       │
       ▼
 Step 1: LLM 领域感知特征提取  ← Qwen3-max（plant/animal 有结构化过滤）
       │
 Step 2: 文本浓缩（规则引擎）  ← 对齐 CLIP caption 格式
       │
 Step 3: CLIP + FAISS 检索     ← 子集过滤（有候选时）或全量检索
       │
 Step 4: 结果反馈 + 对话循环    ← 展示 Top-K + 追问建议 + 物种科普
```

---

## 四大领域数据

| 领域 | 图片数 | 向量数 | 数据来源 | 属性字段 |
|------|:---:|:---:|------|------|
| **auto**（泛化图片） | 155,070 | 52,077 | COCO-CN + Flickr30k-CN | `dataset` |
| **plant**（植物识别） | 306,146 | 306,146 | PlantNet300K（1,081 物种） | `species_id`, `organ`, `author`, `license` |
| **animal**（动物识别） | 37,322 | 37,322 | AWA2（50 类别，85 属性） | `class_name`, `class_name_cn`, `predicates_en`, `predicates_cn` |
| **shop**（电商商品） | 159,186 | 159,186 | MUGE（阿里巴巴电商） | `dataset` |
| **合计** | **657,724** | **554,731** | | |

---

## 技术架构

```
┌─────────────────────────────────────────────────────┐
│                    前端 (Vue 3)                      │
│  Element Plus + Pinia + Axios + Vite + TypeScript   │
│  ┌────────────────┐  ┌───────────────────────────┐  │
│  │  直接检索 Tab   │  │  智能搜物 Agent Tab        │  │
│  └────────────────┘  └───────────────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP REST
┌──────────────────────▼──────────────────────────────┐
│                 后端 (FastAPI)                       │
│  ┌────────────┐ ┌────────────┐ ┌─────────────────┐  │
│  │ /api/search │ │ /api/agent │ │ /api/domains    │  │
│  │ /text|image │ │ /chat      │ │                 │  │
│  └──────┬──────┘ └─────┬──────┘ └─────────────────┘  │
│         │              │                              │
│  ┌──────▼──────────────▼───────────────────────────┐ │
│  │  core/                          agent/          │ │
│  │  ├─ model_loader (CN-CLIP)      ├─ pipeline     │ │
│  │  ├─ processor   (编码器)        ├─ prompts      │ │
│  │  ├─ search_engine (FAISS)       ├─ state_machine│ │
│  │  ├─ domain_registry             ├─ domain_agent │ │
│  │  └─ multi_domain_router         └─ session_mgr  │ │
│  └─────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  本地 GPU: CN-CLIP ViT-B-16 (dim=512)               │
│  云端 LLM: 阿里云 DashScope Qwen3-max                │
│  向量库: FAISS IndexFlatIP (内积相似度)              │
└─────────────────────────────────────────────────────┘
```

---

## 项目结构

```
Cross-modal retrieval system/
├── backend/
│   ├── api_server.py              # FastAPI 主入口
│   ├── requirements.txt           # Python 依赖
│   ├── agent/
│   │   ├── pipeline.py            # ★ 4步推理 Pipeline
│   │   ├── prompts.py             # 领域感知 Prompt 模板
│   │   ├── llm_factory.py         # Qwen3-max LLM 工厂
│   │   ├── state_machine.py       # 对话状态机
│   │   ├── domain_agent.py        # 领域知识库 + 子集过滤
│   │   └── session_manager.py     # 会话管理（内存模式）
│   ├── core/
│   │   ├── model_loader.py        # CN-CLIP 模型加载
│   │   ├── processor.py           # 图像/文本编码器
│   │   ├── search_engine.py       # FAISS 搜索引擎（含子集检索）
│   │   ├── domain_registry.py     # 4领域自动发现注册中心
│   │   ├── metadata_schema.py     # 元数据 TypedDict
│   │   └── multi_domain_router.py # 跨领域路由 + 关键词建议
│   ├── scripts/
│   │   ├── build_plantnet300k_index.py  # plant 索引构建
│   │   ├── build_awa2_index.py          # animal 索引构建
│   │   └── build_caption_index.py       # auto/shop 索引构建
│   ├── data/   {auto,plant,animal,shop}/ # FAISS索引 + 元数据
│   ├── gallery/{auto,plant,animal,shop}/ # 原始图片（657,724张）
│   └── model/epoch_latest.pt            # CN-CLIP 微调权重
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── DirectSearch.vue          # 直接检索板块
│   │   │   └── AgentChat.vue             # Agent 对话板块
│   │   ├── components/
│   │   │   ├── SearchBar.vue             # 搜索栏（含领域选择）
│   │   │   ├── ResultGallery.vue         # 结果瀑布流
│   │   │   ├── ImageCard.vue             # 图片卡片
│   │   │   ├── ImagePreviewDialog.vue    # 图片预览弹窗
│   │   │   ├── ChatPanel.vue             # 聊天面板
│   │   │   ├── ChatMessage.vue           # 消息气泡
│   │   │   ├── AgentResultPanel.vue      # Agent 结果展示
│   │   │   └── SpeciesDetailDialog.vue   # 物种科普弹窗
│   │   ├── stores/ (search.ts, agent.ts)
│   │   ├── api/ (search.ts, agent.ts)
│   │   └── styles/global.scss
│   ├── package.json
│   └── vite.config.ts
└── manual/                              # 设计文档与实现记录
    ├── 迭代方案_Agent系统_v2.md          # v2 完整方案（5领域 → 4领域）
    ├── 迭代方案_Agent系统_v2pro.md        # v2pro 优化方案（精简Pipeline）
    ├── Phase1/2/3_实现记录*.md           # 各阶段实现记录
    ├── Agent推理Pipeline优化方案.md       # Pipeline 架构设计
    ├── Agent推理Prompt模板设计.md         # 领域感知 Prompt 设计
    └── PlantNet300K/AWA/auto+shop_*.md   # 各领域数据处理记录
```

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查（返回加载领域数、Agent 状态） |
| GET | `/api/domains` | 获取 4 领域列表 |
| POST | `/api/search/text` | 文搜图（`query` + `top_k` + `domain`） |
| POST | `/api/search/image` | 图搜文（`file` + `top_k` + `domain`） |
| POST | `/api/agent/chat` | Agent 对话（`message` + `session_id`） |
| POST | `/api/agent/session/new` | 创建新会话 |
| POST | `/api/agent/educate` | 获取物种科普 + 同物种图片 |
| DELETE | `/api/agent/session/{id}` | 删除会话 |

---

## 快速上手

### 环境要求

- **Python 3.9+** + conda 环境（`pt_env`）
- **Node.js 18+**
- **阿里云 DashScope API Key**（环境变量 `DASHSCOPE_API_KEY`）
- CN-CLIP 模型权重（`backend/model/epoch_latest.pt`）
- 领域数据（FAISS 索引 + 元数据 + 图片，约需 10GB 磁盘空间）

### 1. 安装后端依赖

```bash
conda activate pt_env
pip install fastapi uvicorn torch faiss-cpu numpy Pillow cn_clip
pip install langchain-community openai
```

### 2. 配置 LLM

设置阿里云 DashScope API Key：

```bash
# Windows PowerShell
$env:DASHSCOPE_API_KEY = "your-api-key"

# 或写入 ~/.bashrc / ~/.zshrc
export DASHSCOPE_API_KEY="your-api-key"
```

### 3. 构建领域索引（如数据已就位可跳过）

```bash
cd backend

# Plant（植物）
python scripts/build_plantnet300k_index.py --device cuda --batch-size 64

# Animal（动物）
python scripts/build_awa2_index.py --device cuda --batch-size 64

# Auto（泛化图片）
python scripts/build_caption_index.py --domain auto --device cuda --batch-size 64

# Shop（电商商品）
python scripts/build_caption_index.py --domain shop --device cuda --batch-size 64
```

### 4. 启动后端

```bash
cd backend
conda activate pt_env
python api_server.py
# → http://localhost:8000
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

---

## 迭代历程

| 阶段 | 目标 | 关键产出 |
|------|------|---------|
| **Phase 1** | 多领域隔离 + API 适配 | `domain_registry.py`、`metadata_schema.py`、领域选择器、`/api/domains` |
| **Phase 2** | 前端双板块 + Agent UI | `App.vue` 双 Tab、`AgentChat.vue`、`ChatPanel.vue`、`AgentResultPanel.vue` |
| **Phase 3** | Agent 推理 Pipeline | 4步 Pipeline（LLM提取→文本浓缩→CLIP+FAISS→结果反馈）、对话状态机、`/api/agent/*`、物种科普弹窗 |
| **Phase 4** | 长期记忆 + 主动建议 | 已规划，暂不实施（当前系统不需要记忆功能） |

### 架构决策

- **精简 Pipeline 替代 LangGraph**：LLM 调用从 4~6 次降至 1~2 次，降低延迟和复杂度
- **子集过滤检索**：plant/animal 领域利用结构化属性在 FAISS 中做候选过滤，缩小搜索空间
- **领域感知 Prompt**：plant 有物种过滤、animal 有类别过滤、auto/shop 直接检索
- **对话状态机**：IDLE → EXTRACTING → SEARCHING → PRESENTING，支持 REFINING / EXPANDING 分支
- **animal 子目录适配**：`DomainRegistry` 记录 `gallery_style`（flat / class_subdirs），`SearchEngine` 正确处理路径拼接

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3, Element Plus, Pinia, Axios, TypeScript, Vite, Sass |
| 后端 | FastAPI, Uvicorn, Pydantic |
| 视觉模型 | CN-CLIP ViT-B-16 (dim=512) + 自训练微调权重 |
| 向量库 | FAISS IndexFlatIP（内积相似度） |
| LLM | 阿里云 DashScope Qwen3-max（ChatTongyi） |
| 图像处理 | Pillow, PyTorch |
