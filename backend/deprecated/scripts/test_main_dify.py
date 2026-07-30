import sys
import os
import io

# 设置 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加父目录到路径
sys.path.insert(0, os.path.abspath('..'))

# 导入配置和客户端
from config import DIFY_CONFIG
from main import DifyClient

print("=" * 60)
print("测试 Dify API 集成")
print("=" * 60)

print(f"\n配置信息:")
print(f"  API URL: {DIFY_CONFIG['api_url']}")
print(f"  API Key: {DIFY_CONFIG['api_key'][:20]}...")
print(f"  User: {DIFY_CONFIG['user']}")

# 创建 Dify 客户端
dify_client = DifyClient(
    api_url=DIFY_CONFIG['api_url'],
    api_key=DIFY_CONFIG['api_key'],
    user=DIFY_CONFIG['user']
)

print("\n" + "=" * 60)
print("测试: 简单问答")
print("=" * 60)

query = "你好，请用一句话回复我"
print(f"\n查询: {query}")

try:
    response = dify_client.chat(query=query, response_mode="blocking")
    print(f"\n✓ 调用成功!")
    print(f"响应: {response}")
except Exception as e:
    print(f"\n✗ 调用失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
