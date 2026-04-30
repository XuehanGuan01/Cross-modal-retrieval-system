# Cross-modal Retrieval System — 架构、作用与数据流

## 一、项目概述

本项目是一个**中文跨模态图文检索系统**，基于 CN-CLIP（Chinese CLIP）模型与 FAISS 向量检索引擎，提供以下核心能力：

- **文搜图 (Text-to-Image)**：输入中文描述文本，检索最匹配的图片。
- **图搜文 (Image-to-Text)**：上传图片，检索与之语义最相关的文本描述（或图片）。

底层通过将图片和文本分别编码到同一向量空间（512 维 L2 归一化向量），利用余弦相似度（内积）进行跨模态匹配。

## 二、技术栈

| 层次 | 技术 | 作用 |
|------|------|------|
| 深度学习框架 | PyTorch | 模型推理 |
| 跨模态模型 | CN-CLIP (ViT-B-16) | 图文向量化编码 |
| 向量检索引擎 | FAISS (IndexFlatIP) | 高维向量最近邻搜索 |
| Web 框架 | FastAPI | RESTful API 服务 |
| 图像处理 | PIL/Pillow | 图片加载与预处理 |
| 数值计算 | NumPy | 向量矩阵运算 |
| 前端静态服务 | FastAPI StaticFiles | 图片文件托管 |

## 三、项目目录结构

```
Cross-modal retrieval system/
├── backend/
│   ├── api_server.py           # FastAPI 主入口，定义 /api/search/text 和 /api/search/image 接口
│   ├── core/
│   │   ├── model_loader.py     # CN-CLIP 模型加载器（注入微调权重、L2归一化编码）
│   │   ├── processor.py        # 图像/文本批处理编码（preprocess -> encode -> normalize）
│   │   └── search_engine.py    # FAISS 搜索引擎封装（加载索引、搜索、元数据映射）
│   ├── scripts/
│   │   └── build_index.py      # 离线索引构建脚本（遍历图片 → 提取特征 → 构建 FAISS 索引）
│   ├── data/
│   │   ├── images.index        # FAISS 向量索引文件
│   │   └── metadata.json       # 元数据（图片ID、路径、caption）
│   ├── gallery/                # 原始图片存放目录（通过 StaticFiles 挂载到 /gallery）
│   ├── model/
│   │   └── epoch_latest.pt     # CN-CLIP 微调权重 checkpoint
│   ├── Flickr30K_texts.jsonl   # Flickr30K-CN 数据集文本标注
│   └── MUGE_texts.jsonl        # MUGE 数据集文本标注
├── make_caption.py             # 为 COCO-CN 数据集的 metadata 注入 caption
├── make_caption_fk_m.py        # 为 Flickr30K-CN 和 MUGE 数据集的 metadata 注入 caption
├── time_test.py                # 本地/远程请求延时对比测试
├── 对比实验可视化/
│   ├── MUGE_chart.py           # MUGE 验证集召回率柱状图（CN-CLIP vs Wukong vs R2D2 vs 微调变体）
│   └── creat_chart.py          # Flickr30K-CN 测试集召回率总和对比（含基线与微调标注）
├── 消融实验可视化/
│   └── 消融实验表格.py          # 消融实验：冻结视觉编码器 vs 双端微调（三数据集四图）
└── 项目总览.md                  # 图文检索流程简图
```

## 四、核心模块详解

### 4.1 `core/model_loader.py` — 模型加载器

```
CNClipModelLoader
├── __init__(model_name, checkpoint_path, device)
│   ├── 通过 cn_clip.load_from_name() 加载基础 ViT-B-16 模型
│   ├── 从 epoch_latest.pt 加载微调权重
│   ├── 调用 convert_state_dict() 适配架构差异
│   ├── 剥离 DataParallel 的 "module." 前缀
│   └── strict=False 加载，容忍辅助参数缺失
├── encode_image(image_tensor) → L2归一化向量 [B, D]
│   └── model.encode_image() → L2 normalize
└── encode_text(text_tokens) → L2归一化向量 [B, D]
    └── model.encode_text() → L2 normalize
```

**设计要点**：
- 所有编码输出均做 L2 归一化，使向量点积 = 余弦相似度
- `@torch.no_grad()` 禁用梯度计算，节省推理内存
- `non_blocking=True` 异步数据传输，减少 CPU-GPU 等待

### 4.2 `core/processor.py` — 批处理编码器

- `encode_images(model, preprocess, images)`: PIL.Image 列表 → 预处理 → 批量编码 → NumPy 数组
- `encode_texts(model, texts)`: 中文文本列表 → cn_clip.tokenize → 批量编码 → NumPy 数组
- `encode_single_image()` / `encode_single_text()`: 单条数据的便捷封装

### 4.3 `core/search_engine.py` — FAISS 搜索引擎

```
SearchEngine
├── from_files(index_path, metadata_path)  # 工厂方法：从磁盘加载索引+元数据
└── search(query_vec, top_k) → List[Dict]
    ├── 维度/类型检查（转为 float32, 2D）
    ├── index.search() → scores, indices
    └── 元数据映射：ID → {image_url, caption, score, rank}
```

**索引类型**：`IndexFlatIP`（内积索引），暴力搜索，精度最高，适用于万级数据量。

### 4.4 `api_server.py` — FastAPI 服务入口

```
启动生命周期：
  startup → init_resources()
    ├── CNClipModelLoader("ViT-B-16", "model/epoch_latest.pt")
    └── SearchEngine.from_files("data/images.index", "data/metadata.json")

API 端点：
  GET  /api/health                    # 健康检查
  POST /api/search/text               # 文搜图：{"query": "一只猫", "top_k": 50}
  POST /api/search/image              # 图搜文：multipart form (file + top_k)

静态文件：
  /gallery → backend/gallery/          # 图片直链访问
```

## 五、数据流全景

### 5.1 离线索引构建（数据准备阶段）

```
                    图片目录(gallery/)
                          │
                          ▼
               build_index.py
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   遍历图片     CN-CLIP编码   记录元数据
  (jpg/png)   (L2归一化向量)  (id, path)
        │           │           │
        └───────────┼───────────┘
                    ▼
           FAISS IndexFlatIP
          (内积索引 = 余弦相似度)
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
   images.index            metadata.json
   (向量二进制)            (路径映射JSON)
```

### 5.2 在线检索（推理服务阶段）

**文搜图流程：**
```
Client  ─POST /api/search/text {"query":"一只猫"}──►  FastAPI
                                                        │
                                          encode_single_text()
                                                        │
                                               cn_clip.tokenize → model.encode_text()
                                                        │
                                               L2归一化向量 [1, 512]
                                                        │
                                          SearchEngine.search(vec, top_k=50)
                                                        │
                                          FAISS IndexFlatIP.search()
                                                        │
                                          scores + indices → 元数据映射
                                                        │
                                          [{image_url, caption, score, rank}, ...]
                                                        │
                    ◄────────────────────────────────────┘
                    JSON Response
```

**图搜文流程：**
```
Client  ─POST /api/search/image (upload)──►  FastAPI
                                                │
                                  PIL.Image.open() → RGB
                                                │
                                  encode_single_image()
                                                │
                                  preprocess() → model.encode_image()
                                                │
                                  L2归一化向量 [1, 512]
                                                │
                                  SearchEngine.search(vec, top_k=50)
                                                │
                                  FAISS IndexFlatIP.search()
                                                │
                                  命中图片 → 提取 caption 作为"文本结果"
                                                │
                                  [{text, score, meta}, ...]
                    ◄───────────────────────────┘
                    JSON Response
```

### 5.3 Caption 注入流程（元数据增强）

```
COCO-CN/Flickr30K-CN/MUGE 标注文件 (txt/jsonl)
              │
    ┌─────────┴─────────┐
    ▼                   ▼
make_caption.py    make_caption_fk_m.py
    │                   │
    └─────────┬─────────┘
              ▼
   metadata.json (含 caption 字段)
```

## 六、实验分析体系

项目包含完整的对比实验与消融实验可视化：

### 对比实验
- **模型对比**：CN-CLIP (ViT-B/16) vs Wukong (ViT-L/14) vs R2D2 (ViT-L/14)
- **微调对比**：CN-CLIP 分别在 MUGE / Flickr30K-CN / COCO-CN 上微调 vs 未微调基线
- **关键发现**：Flickr-ft 微调后召回率总和最高(540.89)，超越 ViT-H/14 基线(536.00)

### 消融实验
- **策略对比**：冻结视觉编码器 vs 双端微调
- **关键发现**：
  - Flickr30K-CN：两种策略接近（冻结略优 542.48 vs 540.89）
  - COCO-CN：双端微调严重损害 I2T（下降 15.66%），冻结显著更优
  - MUGE：双端微调全面优于冻结（仅 T2I 场景）

## 七、关键设计决策

1. **IndexFlatIP 而非近似索引**：万级数据量下暴力搜索即可满足实时性，且精度最高，无需牺牲准确度换速度。
2. **L2 归一化 + 内积 = 余弦相似度**：统一在模型输出层做归一化，FAISS 用内积索引，数学上等价于余弦相似度。
3. **strict=False 加载权重**：容忍 checkpoint 与当前模型架构的微小差异（如优化器状态、额外 buffer），避免因辅助参数缺失而失败。
4. **CORS 全开**：`allow_origins=["*"]` 方便前端开发调试。
5. **模型常驻内存**：通过 FastAPI `on_event("startup")` 预加载，避免每次请求重新初始化（模型加载耗时数秒）。

