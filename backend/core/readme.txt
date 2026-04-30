核心逻辑core
model_loader.py —— 模型加载逻辑
processor.py —— 预处理/特征处理等核心流程
search_engine.py—— 检索核心逻辑

【model_loader.py】
步骤	组件	model_loader.py 的作用
1. 索引阶段	build_index.py	调用它把本地所有图片转成向量Image Encoding，存入 FAISS。
2. 搜索阶段	search_test.py	调用它把用户的搜索词转成向量Text Encoding，去 FAISS 里比对。

1. 模型初始化与“换脑” (Weight Injection)该模块不仅仅是加载一个原始的 CN-CLIP 模型，它还负责把你**微调（Fine-tune）**后的成果装载进去。基础架构加载：根据你指定的名称（如 ViT-B-16）搭建模型的骨架。权重注入：读取你训练生成的 checkpoint.pt 文件。它能聪明地处理 state_dict，甚至能自动修正在多 GPU 训练时产生的命名差异（如 module. 前缀）。

2. 图像特征提取 (Image Encoding)这是构建向量库的关键。它接收经过预处理的图片张量（Tensor）。通过视觉神经网络（Vision Encoder）计算，输出一个代表该图片“含义”的高维向量。输出示例：一张猫的图片进去，出来的是一个 $1 \times 512$ 维的数字数组。

3. 文本特征提取 (Text Encoding)这是实现“中文搜索”的关键。它接收经过分词（Tokenize）后的中文文本。通过文本神经网络（Text Encoder）计算，输出一个同样维度的向量。神奇之处：它确保了“猫”这个词的向量，在空间位置上非常接近“猫的图片”的向量。

4. 特征归一化 (L2 Normalization)这是最容易被忽视但极其重要的功能。它将所有输出的向量长度缩减为 1。目的：在搜索阶段，我们通常使用“内积”来衡量相似度。如果向量都经过了归一化，内积就等同于余弦相似度。这保证了搜索结果的准确性，不会因为图片亮度或对比度产生的数值偏差而干扰排名。

【search_engine.py】
1. 索引与元数据的“粘合剂” (Loading & Binding)在向量数据库中，特征向量（一串数字）和图片路径（如 C:/gallery/dog.jpg）通常是分开存储的。
功能：它将 faiss 索引文件和 metadata.json 同时加载进内存。
意义：FAISS 只能告诉你“第 5 号向量最匹配”，而 SearchEngine 会帮你查表，告诉你“第 5 号向量对应的其实是那张‘小狗’图片”。

2. 高效的近邻搜索 (Vector Retrieval)当你给出一个查询向量（Query Vector）时，它负责调用 FAISS 底层的 C++ 加速算法进行计算。
数学逻辑：它在多维空间中计算你的搜索词向量与库中所有图片向量的距离（通常是余弦相似度或内积）。
Top-K 过滤：它不会返回所有图片，而是只选出得分最高的前 $K$ 个结果（例如最像的前 10 张图）。

3. 数据清洗与 URL 构建 (Data Post-processing)这是该文件最实用的功能，它把原始的计算结果转换成前端可以直接显示的格式：路径纠正：由于你在 Windows 上构建索引，路径里可能带有反斜杠 \（如 data\img.jpg）。search_engine.py 会把它统一转换成 Web 通用的正斜杠 /。
地址拼接：它会自动把基础 URL（如 http://localhost:5000/static）和图片相对路径拼接在一起，生成完整的 image_url，让前端直接能展示图片。
格式转换：将 numpy 特有的数值类型（如 float32）转换为 Python 标准类型，防止在生成 JSON 接口时报错。

【processor.py】
利用 Hugging Face 的 transformers 库接口，将原始的图片和文字转化成可以存入 FAISS 的标准向量。
核心功能解析

数据标准化：使用 CLIPProcessor 将不同尺寸的图片和变长的文本统一成模型能读懂的 Tensor（张量）。

特征提取：调用模型的视觉/文本编码器（Encoder）提取语义特征。

L2 归一化：确保所有向量长度为 1，这对于后续使用 FAISS 进行相似度计算至关重要。

这个 processor.py 看起来更像是针对标准的 OpenAI CLIP 或 Hugging Face 权重编写的。如果两者混合使用，可能会因为模型架构定义不同而报错。