from openai import OpenAI

print("=" * 60)
print("测试 OpenAI SDK 调用")
print("=" * 60)

# 初始化客户端
client = OpenAI(
    api_key="EMPTY",
    base_url="http://10.181.2.17:10801/v1",
    timeout=60.0
)

print("\n正在调用 AI 服务...")
try:
    response = client.chat.completions.create(
        model="Qwen3-8B",
        messages=[{"role": "user", "content": "你好，请用一句话介绍你自己"}],
        temperature=0.1,
        max_tokens=200
    )
    
    print(f"\n✓ 调用成功!")
    print(f"模型：{response.model}")
    print(f"使用 tokens: {response.usage}")
    print(f"\nAI 回复：{response.choices[0].message.content}")
    
except Exception as e:
    print(f"\n✗ 调用失败：{type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
