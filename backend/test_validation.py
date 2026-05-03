
import sys
sys.path.insert(0, '.')
from scripts.build_caption_index import extract_image_id, load_caption_map

# Test ID extraction
tests = [
    ('COCO_train2014_000000000036.jpg', (36, 'COCO-CN')),
    ('COCO_val2014_000000000042.jpg', (42, 'COCO-CN')),
    ('Flickr30K_985982384.jpg', (985982384, 'Flickr30k-CN')),
    ('MUGE_100.jpg', (100, 'MUGE')),
    ('MUGE_1000002.jpg', (1000002, 'MUGE')),
]
all_pass = True
for fname, expected in tests:
    result = extract_image_id(fname)
    ok = result == expected
    if not ok:
        print(f'FAIL: {fname} -> {result} (expected {expected})')
        all_pass = False
if all_pass:
    print('All ID extraction tests passed!')

# Test caption loading for shop (MUGE only)
print()
cmap = load_caption_map('E:/Chinese-Clip-datasets', ['MUGE'])
print(f'MUGE caption count: {len(cmap):,}')
sample = list(cmap.items())[:3]
for k, v in sample:
    print(f'  {k}: {v[0][:50]}... ({v[1]})')

# Test caption loading for auto
print()
cmap2 = load_caption_map('E:/Chinese-Clip-datasets', ['COCO-CN', 'Flickr30k-CN'])
print(f'Auto caption count: {len(cmap2):,}')
coco_samples = [(k,v) for k,v in cmap2.items() if v[1]=='COCO-CN'][:2]
print('COCO samples:')
for k, v in coco_samples:
    print(f'  {k}: {v[0][:50]}...')
fk_samples = [(k,v) for k,v in cmap2.items() if v[1]=='Flickr30k-CN'][:2]
print('Flickr30K samples:')
for k, v in fk_samples:
    print(f'  {k}: {v[0][:50]}...')

