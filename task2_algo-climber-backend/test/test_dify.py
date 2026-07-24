import sys
sys.path.insert(0, '.')

from config import DIFY_CONFIG

print("=" * 60)
print("测试 Dify API 调用")
print("=" * 60)

print(f"\nDify 配置:")
print(f"  API URL: {DIFY_CONFIG['api_url']}")
print(f"  API Key: {DIFY_CONFIG['api_key'][:20]}...")
print(f"  User: {DIFY_CONFIG['user']}")

# 导入 DifyClient
from main import DifyClient

# 创建客户端
dify_client = DifyClient(
    api_url=DIFY_CONFIG['api_url'],
    api_key=DIFY_CONFIG['api_key'],
    user=DIFY_CONFIG['user']
)

print("\n" + "=" * 60)
print("测试 1: 简单问答")
print("=" * 60)

query = "请用一句话介绍你自己"
print(f"\n查询：{query}")
response = dify_client.chat(query=query)
print(f"\n响应：{response}")

print("\n" + "=" * 60)
print("测试 2: 战略情报分析")
print("=" * 60)

query = "请为我提供关于伊朗的最新战略情报信息，包括最新的相关新闻文章和战略情报分析"
print(f"\n查询：{query[:50]}...")
response = dify_client.chat(query=query)
print(f"\n响应长度：{len(response) if response else 0} 字符")
if response:
    print(f"响应前 200 字符：{response[:200]}...")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
