# 交互式跨模态检索 Agent — 系统迭代方案

> 本文档仅输出方案，不做任何代码修改。待确认后逐 Phase 执行。

---

## 〇、当前系统基线

基于对项目代码的完整阅读，当前系统状态：

```
backend/
├── api_server.py              # FastAPI, 2个检索端点, 1个健康检查
├── core/
│   ├── model_loader.py        # CNClipModelLoader (ViT-B-16 + 微调权重)
│   ├── processor.py           # encode_images / encode_texts / 单条封装
│   └── search_engine.py       # SearchEngine (FAISS IndexFlatIP + metadata)
├── scripts/
│   └── build_index.py         # 离线构建：遍历gallery → 编码 → FAISS索引 + metadata.json
├── data/
│   ├── images.index           # 单一 FAISS 索引
│   └── metadata.json          # [{id, path, caption}, ...]
├── gallery/                   # 原始图片
└── model/
    └── epoch_latest.pt        # CN-CLIP 微调权重
```

**核心限制（阻碍 Agent 化的点）**：
1. 单一索引 — 无法按领域隔离检索
2. 无状态 — 每次请求独立，无法多轮对话
3. 无 LLM 集成 — 检索结果直接返回，无推理/重排序
4. metadata 结构简单 — 缺少领域标签、属性等结构化信息
5. 前端无领域切换入口

---

## 一、总体架构演进

```
Phase 1-2                          Phase 3-4                               Phase 5
┌─────────────────┐          ┌─────────────────────────┐          ┌─────────────────────────┐
│  FastAPI         │          │  FastAPI                 │          │  FastAPI                 │
│  ├─ /search/text │   ──►    │  ├─ /search/text (保留)  │   ──►    │  ├─ /search/*  (保留)     │
│  ├─ /search/img  │          │  ├─ /agent/chat       NEW│          │  ├─ /agent/chat           │
│  └─ /health      │          │  ├─ /agent/session NEW  │          │  ├─ /agent/session        │
└─────────────────┘          │  └─ /agent/history NEW  │          │  ├─ /agent/preferences NEW│
                              │  LangGraph Agent         │          │  └─ /domain/ *         NEW│
                              │  ├─ Router               │          │                           │
                              │  ├─ RetrievalTool        │          │  LangGraph Agent v2        │
                              │  ├─ RAGChain             │          │  ├─ + LongTermMemory       │
                              │  └─ ReflectNode          │          │  ├─ + ProactiveSuggest     │
                              └─────────────────────────┘          │  └─ + UserProfile          │
                                                                   └─────────────────────────┘
```

---

## 二、Phase 1：基础跨模态检索加固

**目标**：确保单领域检索的稳定性与可扩展性，为后续多领域打基础。

### 需要改动的文件

#### 2.1 新建：`backend/core/domain_registry.py`

```text
作用：领域注册中心，管理各领域的索引路径、metadata路径、gallery路径
内容：
  - DomainRegistry 类
    - domains: Dict[str, DomainConfig]   # { "medical": DomainConfig(...), ... }
    - get_domain(name) → DomainConfig
    - list_domains() → List[str]
  - DomainConfig 数据类：
    - name: str
    - index_path: Path
    - metadata_path: Path
    - gallery_dir: Path
    - description: str
```

#### 2.2 新建：`backend/core/metadata_schema.py`

```text
作用：统一 metadata 数据结构规范，为多领域扩展做准备
内容：
  - MetadataItem(TypedDict):
    - id: int
    - path: str           # 相对图片路径
    - caption: str        # 图片描述（必填）
    - domain: str         # 所属领域（新增）
    - attributes: dict    # 扩展属性（颜色、大小、类别等，可选）
    - source: str         # 数据集来源（COCO / MUGE / 自定义）
```

#### 2.3 修改：`backend/core/search_engine.py`

```text
改动：
  - SearchEngine.search() 增加 domain_filter: Optional[str] 参数
  - 当指定 domain 时，仅在 metadata 中 domain 匹配的候选中搜索
  - 新增 search_all_domains() 方法：跨领域检索时，返回按领域分组的结果

具体改动量：
  - search() 方法：约 +15 行（过滤逻辑）
  - 新增 _filter_by_domain() 私有方法：约 +10 行
```

#### 2.4 修改：`backend/scripts/build_index.py`

```text
改动：
  - 增加 --domain 参数，指定构建哪个领域的索引
  - 增加 --metadata-schema 参数，生成符合新 schema 的 metadata
  - 输出路径动态化：data/{domain}/images.index / metadata.json
  - gallery 输入路径动态化：gallery/{domain}/

具体改动量：
  - build_index() 函数签名增加 domain 参数
  - find_images() 无变化
  - metadata 生成逻辑增加 domain 字段填充
  - argparse 增加 --domain 参数
```

#### 2.5 修改：`backend/api_server.py`

```text
改动（保持向后兼容）：
  - /api/search/text 增加可选 domain 参数
  - /api/search/image 增加可选 domain 参数
  - 新增 GET /api/domains 返回可用领域列表
```

### Phase 1 产出物

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `backend/core/domain_registry.py` | 领域注册中心 |
| 新建 | `backend/core/metadata_schema.py` | 元数据结构定义 |
| 修改 | `backend/core/search_engine.py` | 增加 domain_filter |
| 修改 | `backend/scripts/build_index.py` | 支持 --domain |
| 修改 | `backend/api_server.py` | 增加 domain 参数 + 领域列表接口 |

---

## 三、Phase 2：多领域 + 前端分类

**目标**：支持4个领域独立检索，前端按领域隔离。

### 需要改动的文件

#### 3.1 修改：`backend/core/domain_registry.py`

```text
基于 Phase 1 的 DomainRegistry，增加：
  - auto_discover() 方法：自动扫描 data/ 下的子目录，发现已有领域
  - domain_index_map: Dict[str, SearchEngine]  # 预加载所有领域的 SearchEngine 实例
  - get_engine(domain) → SearchEngine
```

#### 3.2 新建：`backend/core/multi_domain_router.py`

```text
作用：多领域检索路由器，根据 query 自动选择领域或跨领域检索
内容：
  - MultiDomainRouter 类
    - route(query_text: str) → List[str]  # 基于关键词/语义判断目标领域
    - search_across_domains(query_vec, domains, top_k) → 合并结果
    - merge_and_rerank(domain_results: Dict[str, List]) → List  # 跨领域结果重排序
```

#### 3.3 修改：`backend/api_server.py`（与 Phase 1 合并）

```text
新增端点：
  - GET  /api/domains                          # 返回领域列表（名称+描述+图片数）
  - POST /api/search/text?domain=medical       # 按领域检索
  - POST /api/search/text?domain=auto          # 自动识别领域
  - GET  /api/domain/{name}/stats              # 单领域统计（图片数、向量维度等）
```

#### 3.4 修改：前端（不在本次后端范围，仅标注）

```text
改动位置：Vue+Vite 前端（当前项目中暂无前端代码，需新建）
  - 路由结构：/search/medical, /search/ecommerce, /search/plant, /search/animal
  - 顶部导航栏增加领域切换 Tab
  - 检索结果展示：图片卡片 + caption + 相似度分数
```

### Phase 2 产出物

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 修改 | `backend/core/domain_registry.py` | 预加载多领域引擎 |
| 新建 | `backend/core/multi_domain_router.py` | 多领域路由 + 结果合并 |
| 修改 | `backend/api_server.py` | 领域统计 + auto 路由 |

---

## 四、Phase 3：对话式检索（第一版 Agent）

**目标**：封装检索为 LangChain Tool，支持简单多轮对话与条件过滤。

### 架构变化

```
用户消息 ──► FastAPI ──► LangChain AgentExecutor
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         SearchTool      FilterTool       RAGChain
    (跨模态向量检索)   (结果条件过滤)   (检索增强生成)
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                         LLM 推理
                              │
                              ▼
                    最终回复 + Top-3 图片
```

### 需要改动的文件

#### 4.1 新建：`backend/agent/__init__.py`

```text
Agent 模块入口，导出 create_agent()
```

#### 4.2 新建：`backend/agent/tools.py`

```text
作用：定义 LangChain Tool，将现有检索能力封装为标准 Tool 接口
内容：
  - create_crossmodal_search_tool(search_engine, model_loader) → BaseTool
    - name: "crossmodal_search"
    - description: "在图片库中搜索与文本描述或图片相似的图片。输入: 中文描述文本或图片路径"
    - func: 调用 encode_single_text → search_engine.search → 返回 Top-K caption + score
  - create_domain_search_tool(domain_router) → BaseTool
    - name: "domain_search"
    - description: "在指定领域（医疗/电商/植物/动物）中检索"
    - func: domain_router.route → search_engine.search(domain=...)
  - create_image_upload_tool() → BaseTool
    - name: "image_search"  
    - description: "以图搜图，上传图片找到相似图片"
    - func: encode_single_image → search_engine.search
  - create_filter_tool() → BaseTool
    - name: "filter_results"
    - description: "根据属性（颜色/大小/类别）过滤已有检索结果"
    - func: 对已有 results 做条件筛选
```

**技术细节**：
- 使用 `langchain_core.tools.BaseTool` 或 `@tool` 装饰器
- 每个 Tool 需定义清晰的 `args_schema`（Pydantic model），以便 LLM 理解调用方式

#### 4.3 新建：`backend/agent/rag_chain.py`

```text
作用：RAG 检索增强生成链，将 Top-K caption 作为上下文注入 LLM
内容：
  - RAGChain 类
    - __init__(llm, prompt_template)
    - run(query: str, retrieval_results: List[Dict], conversation_history: List) → str
  - Prompt 模板设计（关键）：

    SYSTEM_PROMPT = """
    你是一个跨模态检索助手。用户正在搜索图片，以下是向量检索返回的 Top-{K} 候选结果：
    
    {retrieval_context}
    
    请根据用户的查询意图，从上述候选中选出最匹配的 Top-3 结果，并给出：
    1. 排序依据（为什么这个最匹配）
    2. 每个结果的匹配置信度（高/中/低）
    3. 如果所有结果都不太匹配，请诚实告知并建议调整搜索条件
    
    历史对话：
    {conversation_history}
    """
```

**技术细节**：
- LLM 选择：建议先支持 Qwen2.5-7B（本地部署）和 GPT-4o API（云端）两种后端
- Prompt 需要将检索分数（score）也传入，让 LLM 结合向量相似度做判断

#### 4.4 新建：`backend/agent/llm_factory.py`

```text
作用：LLM 工厂，统一创建 LLM 实例
内容：
  - get_llm(provider: str, model_name: str, **kwargs) → BaseChatModel
    - provider="openai"  → ChatOpenAI(model=model_name)
    - provider="local"   → ChatOllama / vLLM 本地模型
    - provider="claude"  → ChatAnthropic(model=model_name)
  - 从配置文件/环境变量读取 API Key 和 endpoint
```

#### 4.5 新建：`backend/agent/conversation_state.py`

```text
作用：对话状态管理（单会话生命周期内）
内容：
  - ConversationState(TypedDict):
    - session_id: str
    - current_domain: Optional[str]      # 当前锁定领域
    - last_query_type: str               # "text" | "image"
    - last_retrieval_results: List[Dict] # 上一轮检索结果（供过滤用）
    - history: List[Message]             # 对话历史
    - user_feedback: List[str]           # 用户反馈记录
    - iteration_count: int               # 当前会话检索次数
```

#### 4.6 修改：`backend/api_server.py`

```text
新增端点：
  - POST /api/agent/chat
    请求体: { "session_id": "xxx", "message": "有更小号的红色款吗？", "domain": "ecommerce" }
    响应体: {
      "reply": "根据您的需求，我找到了以下3款红色小号商品...",
      "results": [{ "image_url": "...", "caption": "...", "score": 0.92, "confidence": "高" }, ...],
      "session_id": "xxx",
      "suggestions": ["缩小筛选范围", "查看全部结果"]
    }
  
  - POST /api/agent/session/new
    响应: { "session_id": "uuid-xxxx" }
  
  - GET  /api/agent/session/{session_id}
    响应: 返回当前会话状态（history、当前领域等）

compatibility: 保留原有 /api/search/text 和 /api/search/image 端点不变
```

#### 4.7 新建：`backend/config/agent_config.yaml`

```text
作用：Agent 相关配置集中管理
内容：
  llm:
    provider: "openai"           # openai | local | claude
    model: "gpt-4o"
    temperature: 0.1
    max_tokens: 1024
  retrieval:
    default_top_k: 5             # 向量检索返回数
    rag_top_k: 5                 # 注入 RAG 上下文数
    final_top_n: 3               # 最终返回给用户的结果数
  conversation:
    max_history_turns: 10        # 最大保留对话轮次
    session_ttl_minutes: 30      # 会话超时时间
  domains:
    - medical
    - ecommerce  
    - plant
    - animal
```

### Phase 3 产出物

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `backend/agent/__init__.py` | 模块入口 |
| 新建 | `backend/agent/tools.py` | LangChain Tool 定义（4个Tool） |
| 新建 | `backend/agent/rag_chain.py` | RAG 检索增强生成链 |
| 新建 | `backend/agent/llm_factory.py` | LLM 工厂 |
| 新建 | `backend/agent/conversation_state.py` | 对话状态管理 |
| 新建 | `backend/config/agent_config.yaml` | Agent 配置 |
| 修改 | `backend/api_server.py` | 新增 /api/agent/* 端点 |
| 新建 | `backend/requirements.txt` | 增加 langchain, langchain-core, langchain-openai 等依赖 |

---

## 五、Phase 4：LangGraph 多步推理

**目标**：用 LangGraph 构建有状态的、可分支的多步检索推理图。

### 图结构设计

```
                    ┌─────────┐
                    │  START   │
                    └────┬─────┘
                         ▼
               ┌─────────────────┐
               │  IntentParser   │  ← 理解用户意图（搜索/过滤/追问/切换领域）
               │  (LLM Node)     │
               └────────┬────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        ┌─────────┐ ┌────────┐ ┌──────────┐
        │ SEARCH  │ │ FILTER │ │ CLARIFY  │  ← 路由分支
        └────┬────┘ └───┬────┘ └────┬─────┘
             │          │           │
             ▼          │           ▼
    ┌────────────────┐  │   ┌──────────────┐
    │ CrossModalRet  │  │   │ AskUserNode  │  ← 置信度低时追问
    │ (Tool Node)    │  │   └──────────────┘
    └───────┬────────┘  │
            │           │
            ▼           │
    ┌────────────────┐  │
    │   RAG Node     │  │  ← 检索结果注入 LLM
    │ (LLM Node)     │  │
    └───────┬────────┘  │
            │           │
            ▼           │
    ┌────────────────┐  │
    │  Reflect Node  │  │  ← 反思：结果够好吗？
    │  (LLM Node)    │◄─┘
    └───────┬────────┘
            │
     ┌──────┼──────┐
     ▼      ▼      ▼
  ┌─────┐ ┌────┐ ┌──────────┐
  │PASS │ │RETRY│ │REFINE   │  ← 反思后的决策
  └──┬──┘ └──┬─┘ └────┬─────┘
     │       │         │
     │       └────► (回到 SEARCH，调整查询)
     │                │
     ▼                ▼
  ┌──────────┐
  │ RESPONSE │  ← 生成最终回复
  │ (LLM)    │
  └────┬─────┘
       ▼
  ┌──────────┐
  │   END    │
  └──────────┘
```

### 需要改动的文件

#### 5.1 新建：`backend/agent/graph.py`

```text
作用：LangGraph 状态图定义（核心文件）
内容：
  - RetrievalAgentState(TypedDict):
    - messages: List[BaseMessage]           # 完整对话
    - domain: Optional[str]                 # 当前领域
    - user_intent: str                      # "search" | "filter" | "clarify" | "switch_domain"
    - retrieval_query: str                  # 优化后的检索 query
    - retrieval_results: List[Dict]         # 向量检索原始结果
    - rag_context: str                      # 格式化后的 RAG 上下文
    - reflection: str                       # 反思结果
    - final_results: List[Dict]             # 最终 Top-3
    - final_response: str                   # 最终文本回复
    - confidence: float                     # 整体置信度
    - needs_clarification: bool             # 是否需要追问
    - retry_count: int                      # 重试次数

  - 节点函数（每个一个 async def）：
    - parse_intent(state) → state           # LLM 节点：解析用户意图
    - route_by_intent(state) → str          # 条件边：根据意图路由
    - crossmodal_retrieve(state) → state    # Tool 节点：执行向量检索
    - rag_augment(state) → state            # LLM 节点：RAG 增强
    - reflect(state) → state                # LLM 节点：反思结果质量
    - should_retry(state) → str             # 条件边：决策重试/通过/优化
    - generate_response(state) → state      # LLM 节点：生成最终回复
    - ask_clarification(state) → state      # LLM 节点：生成追问

  - build_graph() → StateGraph:
    graph = StateGraph(RetrievalAgentState)
    graph.add_node("parse_intent", parse_intent)
    graph.add_node("retrieve", crossmodal_retrieve)
    graph.add_node("rag", rag_augment)
    graph.add_node("reflect", reflect)
    graph.add_node("respond", generate_response)
    graph.add_node("clarify", ask_clarification)
    
    graph.add_edge(START, "parse_intent")
    graph.add_conditional_edges("parse_intent", route_by_intent, {
        "search": "retrieve",
        "filter": "rag",          # 直接对已有结果过滤+反思
        "clarify": "clarify"
    })
    graph.add_edge("retrieve", "rag")
    graph.add_edge("rag", "reflect")
    graph.add_conditional_edges("reflect", should_retry, {
        "pass": "respond",
        "retry": "retrieve",      # 调整 query 重新检索
        "refine": "rag"           # 用新视角重新分析已有结果
    })
    graph.add_edge("respond", END)
    graph.add_edge("clarify", END)
    
    return graph.compile(checkpointer=MemorySaver())
```

**技术细节**：
- 使用 `langgraph.graph.StateGraph` 和 `langgraph.checkpoint.MemorySaver`
- 条件边是关键：IntentParser → 3路分支, Reflect → 3路分支
- 设置 `retry_count` 上限（3次），防止无限循环

#### 5.2 新建：`backend/agent/prompts.py`

```text
作用：集中管理所有 LLM 节点的 Prompt 模板
内容：
  - INTENT_PARSE_PROMPT      # 意图解析
  - RAG_AUGMENT_PROMPT       # RAG 推理
  - REFLECT_PROMPT           # 反思评估
  - RESPONSE_PROMPT          # 生成回复
  - CLARIFY_PROMPT           # 追问生成
```

#### 5.3 修改：`backend/agent/rag_chain.py`（基于 Phase 3）

```text
改动：
  - 不再作为独立链运行，改为 LangGraph 中的一个 Node
  - 输入/输出适配 RetrievalAgentState
  - 增加结构化输出：不仅给文本，还要给出 confidence score
```

#### 5.4 修改：`backend/api_server.py`

```text
改动：
  - /api/agent/chat 端点内部改为调用 graph.invoke() 或 graph.astream()
  - 支持 SSE 流式返回：graph.astream_events() 让前端看到实时推理过程
  - 新增 GET /api/agent/chat/{session_id}/state 查看当前图状态（调试用）
```

#### 5.5 新建：`backend/agent/graph_debug.py`

```text
作用：开发调试工具，可视化图执行过程
内容：
  - 打印每次节点执行前后的状态变化
  - 记录各节点耗时
  - 可视化图结构（Mermaid 格式输出）
```

### Phase 4 产出物

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `backend/agent/graph.py` | LangGraph 状态图（核心） |
| 新建 | `backend/agent/prompts.py` | 所有 Prompt 模板集中管理 |
| 修改 | `backend/agent/rag_chain.py` | 适配为 Graph Node |
| 修改 | `backend/api_server.py` | 集成 graph + SSE 流式 |
| 新建 | `backend/agent/graph_debug.py` | 图调试工具 |

---

## 六、Phase 5：完整交互式 Agent

**目标**：长期记忆 + 主动建议 + 用户偏好学习。

### 需要改动的文件

#### 6.1 新建：`backend/agent/memory.py`

```text
作用：长期记忆管理（跨会话）
内容：
  - LongTermMemory 类
    - 存储后端：SQLite（轻量）或 Chroma（向量记忆）
    - save_session_summary(session_id, summary)  # 会话结束后总结关键信息
    - get_user_preferences(user_id) → UserProfile
    - search_similar_past_queries(query_vec) → List[PastQuery]
  
  - UserProfile(TypedDict):
    - user_id: str
    - preferred_domains: List[str]             # 偏好的领域
    - search_history_summary: str              # 历史搜索摘要
    - attribute_preferences: Dict[str, Any]    # 属性偏好（如"喜欢红色"）

  - 实现逻辑：
    - 每次会话结束，调用 LLM 生成一句话总结
    - 总结 + 用户反馈向量化存入 Chroma
    - 新会话开始时检索相关历史，注入 system prompt
```

#### 6.2 新建：`backend/agent/proactive_suggest.py`

```text
作用：主动建议引擎
内容：
  - ProactiveSuggestEngine 类
    - analyze(user_profile, current_query, current_results) → List[Suggestion]
    - 建议类型：
      - "related"：基于当前结果的相关推荐
      - "refine"：建议缩小/扩大搜索范围
      - "history"：基于历史偏好的推荐（"你上次搜过的..."）
      - "discover"：发现新领域（"你对植物感兴趣，要不要试试动物领域？"）
```

#### 6.3 修改：`backend/agent/graph.py`（基于 Phase 4）

```text
改动：
  - 增加 ProactiveSuggestNode：检索完成后，在 Respond 前插入
  - 增加 MemoryRecallNode：会话开始时，从长期记忆中检索相关上下文
  - 图结构更新：
    START → MemoryRecall → IntentParser → ...
    ... → Reflect → Respond → ProactiveSuggest → END
```

#### 6.4 修改：`backend/agent/conversation_state.py`

```text
改动：
  - 增加 user_id 字段（关联长期记忆）
  - 增加 memory_context: str 字段（从长期记忆注入的上下文）
  - 增加 proactive_suggestions: List[Suggestion] 字段
```

#### 6.5 新建：`backend/agent/session_manager.py`

```text
作用：会话生命周期管理
内容：
  - SessionManager 类
    - create_session(user_id) → session_id
    - get_session(session_id) → ConversationState
    - end_session(session_id) → 触发记忆存储
    - cleanup_expired_sessions()  # 定时任务清理过期会话
    - session_store: Dict[str, ConversationState]  # 内存存储（可换 Redis）
```

### Phase 5 产出物

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `backend/agent/memory.py` | 长期记忆（SQLite + Chroma） |
| 新建 | `backend/agent/proactive_suggest.py` | 主动建议引擎 |
| 修改 | `backend/agent/graph.py` | 增加 Memory + Suggest 节点 |
| 修改 | `backend/agent/conversation_state.py` | 增加 user_id / memory_context |
| 新建 | `backend/agent/session_manager.py` | 会话生命周期管理 |

---

## 七、依赖变化汇总

### requirements.txt 演进

```text
# Phase 1-2（当前 + 微增）
fastapi
uvicorn
torch
cn-clip
faiss-cpu          # 或 faiss-gpu
Pillow
numpy
pydantic
python-multipart
pyyaml

# Phase 3 新增
langchain>=0.3.0
langchain-core>=0.3.0
langchain-openai>=0.2.0     # 如果用 OpenAI
langchain-community>=0.3.0
openai

# Phase 4 新增
langgraph>=0.2.0
langgraph-checkpoint>=2.0.0
sse-starlette>=2.0.0         # SSE 流式支持

# Phase 5 新增
chromadb>=0.5.0              # 向量记忆
aiosqlite>=0.20.0            # 异步 SQLite
```

---

## 八、待确认 / 模糊问题汇总

以下是我在设计方案过程中遇到的、需要你明确的问题：

### A. LLM 选型
1. **LLM 用哪个？** 本地部署（Qwen2.5-7B / ChatGLM）还是云端 API（GPT-4o / Claude）？这直接影响 `llm_factory.py` 的实现方式和硬件需求。
2. **是否需要支持多 LLM 后端切换？** 即同一套代码支持 local + openai + claude 三种。

### B. 向量数据库
3. **是否要从 FAISS 迁移到 Milvus？** 技术栈文档提到 Milvus，当前用 FAISS IndexFlatIP。Milvus 的优势在于分布式/增量写入/属性过滤，但对于万级数据量 FAISS 已足够。建议 Phase 4 之前保持 FAISS，Phase 5 视数据量决定。

### C. 数据集
4. **4个领域的数据集目前有哪些？** 当前只看到 Flickr30K-CN、MUGE、COCO-CN 三个通用数据集。医疗/电商/植物/动物的领域数据需要额外收集——是否有计划？
5. **metadata 中的 caption 质量要求？** 是否每个图片都必须有高质量中文描述？当前 `make_caption.py` 和 `make_caption_fk_m.py` 仅做文本匹配注入。

### D. 前端
6. **前端是否已存在？** 当前项目仓库中未看到 Vue+Vite 代码。Phase 2 的前端工作是否由其他开发者负责，还是也需要后端开发者完成？
7. **前端交互细节**：检索结果是以瀑布流展示还是列表？Agent 对话界面是聊天框形式吗？

### E. 架构决策
8. **Phase 3 的 Agent 是否必须用 LangChain AgentExecutor？** 还是可以直接跳到 Phase 4 用 LangGraph？LangChain AgentExecutor 的灵活性较差，如果你确定要做多步推理，建议 Phase 3 直接上 LangGraph，跳过 AgentExecutor。
9. **对话状态持久化**：会话存储用内存（重启丢失）还是 Redis/DB？Phase 3/4 可用内存，Phase 5 建议换 Redis。

### F. 部署
10. **最终部署环境**：单机 GPU 服务器还是云服务？这影响 LLM 选型和向量库选择。
11. **CN-CLIP 模型与 LLM 是否共存在同一 GPU？** 如果显存不足，可能需要模型卸载策略。

---

## 九、建议的下一步

1. **确认上述问题** → 我根据答复调整方案细节
2. **优先启动 Phase 1 + 2**（风险低、改动明确、无需 LLM 依赖）
3. **Phase 3 时同步调研 LangGraph**，评估是否直接跳过 LangChain AgentExecutor
4. **Phase 4 的 Graph 设计可提前评审**，因为这个结构决定了整个 Agent 的行为模式

---

> 文档生成时间：2026-04-30
> 基线代码 commit：无（非 Git 仓库）
