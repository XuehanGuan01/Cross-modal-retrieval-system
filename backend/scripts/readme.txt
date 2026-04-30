build_index.py —— 离线构建索引脚本
预先用模型处理你的图片/文本库，提取出特征向量（Embedding），存入向量数据库。

终端代码：
python -m scripts.build_index
结果：
[build_index] 构建 FAISS IndexFlatIP, 向量维度: 512
[build_index] 写入索引到 data\images.index
[build_index] 写入元数据到 data\metadata.json
[build_index] 索引构建完成 ✅

现在的状态是：已经把所有的图片“浓缩”成了数学向量，存放在了 data\images.index 中，并且建立了 ID 与路径的映射表 data\metadata.json。