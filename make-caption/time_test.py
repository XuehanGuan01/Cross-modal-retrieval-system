# 测试代码示例
import time
import requests

# 测试本地请求（localhost）
start = time.time()
response = requests.get('http://localhost:8000/api/test')
print(f"本地请求耗时: {time.time() - start:.4f}秒")
# 输出：本地请求耗时: 0.0023秒（2.3毫秒）

# 对比远程请求（假设访问真实服务器）
start = time.time()
response = requests.get('https://example.com/api/test')
print(f"远程请求耗时: {time.time() - start:.4f}秒")
# 输出：远程请求耗时: 0.2345秒（234毫秒）

# localhost 快 100 倍以上！