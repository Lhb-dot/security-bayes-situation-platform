import sys
import json
import os

# 添加父目录到路径，以便导入 config 和 main
sys.path.insert(0, os.path.abspath('..'))

from config import DIFY_CONFIG
from main import DifyClient

print("=" * 60)
print("测试 Dify API 调用")
print("=" * 60)

# 创建客户端
dify_client = DifyClient(
    api_url=DIFY_CONFIG['api_url'],
    api_key=DIFY_CONFIG['api_key'],
    user=DIFY_CONFIG['user']
)

print(f"\n配置信息:")
print(f"  API URL: {DIFY_CONFIG['api_url']}")
print(f"  User: {DIFY_CONFIG['user']}")

print("\n" + "=" * 60)
print("测试：简单问答")
print("=" * 60)

query = "你好，请回复我"
print(f"\n查询：{query}")

try:
    response = dify_client.chat(query=query, response_mode="blocking")
    print(f"\n✓ 调用成功!")
    print(f"响应：{response}")
except Exception as e:
    print(f"\n✗ 调用失败：{type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
