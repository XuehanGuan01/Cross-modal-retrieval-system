import json
import os
from typing import Dict, List


def load_texts(jsonl_path: str) -> Dict[int, str]:
    """
    从JSONL文件加载文本数据，返回字典 {image_id: caption}
    只取每个image_id的第一个text
    """
    image_caption_map = {}

    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                image_ids = data.get('image_ids', [])
                text = data.get('text', '')

                # 对于每个image_id，只记录第一次出现的text
                for img_id in image_ids:
                    if img_id not in image_caption_map:
                        image_caption_map[img_id] = text

    return image_caption_map


def update_metadata(metadata_path: str, caption_map: Dict[int, str], prefix: str):
    """
    更新metadata.json文件中的caption字段
    prefix: 图片路径前缀，如"Flickr30K_"或"MUGE_"
    """
    # 读取现有metadata
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # 统计更新数量
    updated_count = 0
    not_found_count = 0

    # 更新caption
    for item in metadata:
        path = item.get('path', '')
        if path.startswith(prefix):
            # 从路径中提取图片ID（去除前缀和扩展名）
            # 路径格式示例: "Flickr30K_1000092795.jpg" 或 "MUGE_158.jpg"
            filename = os.path.basename(path)
            if filename.startswith(prefix):
                # 移除前缀和扩展名，获取ID
                img_id_str = filename[len(prefix):]
                # 移除扩展名
                img_id_str = os.path.splitext(img_id_str)[0]

                try:
                    img_id = int(img_id_str)
                    if img_id in caption_map:
                        item['caption'] = caption_map[img_id]
                        updated_count += 1
                    else:
                        not_found_count += 1
                        print(f"警告: 未找到ID {img_id} 对应的文本（路径: {path}）")
                except ValueError:
                    print(f"警告: 无法解析图片ID（路径: {path}）")

    # 保存更新后的metadata
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"处理完成 (前缀: {prefix})")
    print(f"  - 成功更新: {updated_count} 条")
    print(f"  - 未找到对应文本: {not_found_count} 条")


def main():
    # 文件路径配置
    backend_dir = r"C:\Users\Lenovo\Desktop\Cross-modal retrieval system\backend"
    metadata_path = r"C:\Users\Lenovo\Desktop\Cross-modal retrieval system\backend\data\metadata.json"

    flickr_texts_path = os.path.join(backend_dir, "Flickr30K_texts.jsonl")
    muge_texts_path = os.path.join(backend_dir, "MUGE_texts.jsonl")

    # 检查文件是否存在
    if not os.path.exists(metadata_path):
        print(f"错误: metadata.json 不存在于 {metadata_path}")
        return

    # 处理 Flickr30K 数据集
    print("正在处理 Flickr30K 数据集...")
    if os.path.exists(flickr_texts_path):
        flickr_caption_map = load_texts(flickr_texts_path)
        print(f"  - 加载了 {len(flickr_caption_map)} 条唯一图片ID的文本")
        update_metadata(metadata_path, flickr_caption_map, "Flickr30K_")
    else:
        print(f"警告: Flickr30K_texts.jsonl 不存在于 {flickr_texts_path}")

    print("\n" + "=" * 50 + "\n")

    # 处理 MUGE 数据集
    print("正在处理 MUGE 数据集...")
    if os.path.exists(muge_texts_path):
        muge_caption_map = load_texts(muge_texts_path)
        print(f"  - 加载了 {len(muge_caption_map)} 条唯一图片ID的文本")
        update_metadata(metadata_path, muge_caption_map, "MUGE_")
    else:
        print(f"警告: MUGE_texts.jsonl 不存在于 {muge_texts_path}")

    print("\n所有处理完成！")


if __name__ == "__main__":
    main()