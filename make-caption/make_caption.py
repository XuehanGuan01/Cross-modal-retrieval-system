import json
import os

# ================= 配置路径 =================
# JSON 元数据文件路径
json_path = r"C:\Users\Lenovo\Desktop\Cross-modal retrieval system\backend\data\metadata.json"
# COCO-CN 描述文件路径
txt_path = r"C:\Users\Lenovo\Desktop\coco-cn-version1805v1.1\imageid.human-written-caption.txt"# 这是个txt文件
# 输出的新文件路径
output_path = r"C:\Users\Lenovo\Desktop\Cross-modal retrieval system\backend\data\metadata_with_captions.json"


# ===========================================

def build_caption_map(txt_file):
    """
    读取txt文件，构建文件名到描述的映射
    映射结果示例: {"COCO_train2014_000000573854.jpg": "机场跑道的喷气式飞机..." }
    """
    mapping = {}
    print(f"正在处理描述文件: {txt_file}")

    with open(txt_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or '\t' not in line:
                continue

            # 分割 ID部分 和 描述部分
            header, caption = line.split('\t', 1)

            # 处理 ID：COCO_train2014_000000573854#0 -> COCO_train2014_000000573854.jpg
            image_id = header.split('#')[0]
            filename = f"{image_id}.jpg"

            # 如果同一个 ID 有多个描述，这里默认保留第一个（或者你可以改成列表）
            if filename not in mapping:
                mapping[filename] = caption

    return mapping


def update_json():
    # 1. 构建描述映射表
    caption_map = build_caption_map(txt_path)

    # 2. 读取原始 JSON
    print(f"正在读取 JSON 文件: {json_path}")
    if not os.path.exists(json_path):
        print("错误：找不到原始 JSON 文件，请确认路径是否正确。")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # 3. 遍历 JSON 并在匹配项中加入 caption
    match_count = 0
    total_count = len(metadata)

    for item in metadata:
        image_path = item.get("path")  # 获取如 "COCO_train2014_000000000009.jpg"

        # 在映射表中查找
        if image_path in caption_map:
            item["caption"] = caption_map[image_path]
            match_count += 1
        else:
            # 如果没找到描述，可以设为空字符串或跳过
            item["caption"] = ""

    # 4. 写入新文件
    print(f"匹配完成！共 {total_count} 条记录，成功匹配到描述的有 {match_count} 条。")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"新的元数据已保存至: {output_path}")


if __name__ == "__main__":
    update_json()