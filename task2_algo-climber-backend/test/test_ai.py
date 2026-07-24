import requests
import json

print("=" * 60)
print("AI 服务诊断测试")
print("=" * 60)

# 测试配置
api_url = "http://10.181.2.17:10801/v1/chat/completions"
model = "Qwen3-8B"

print(f"\n测试 URL: {api_url}")
print(f"测试模型：{model}\n")

# 测试 1: 简单请求
print("【测试 1】发送简单请求...")
print("正在连接 AI 服务，请稍候...")
try:
    response = requests.post(
        api_url,
        json={
            "model": model,
            "messages": [{"role": "user", "content": "你好，请回复我"}],
            "temperature": 0.1,
            "max_tokens": 100
        },
        timeout=30  # 增加到 30 秒超时
    )
    print(f"\n状态码：{response.status_code}")
    print(f"响应头：{dict(response.headers)}")
    
    try:
        response_json = response.json()
        print(f"\n完整响应内容:")
        print(json.dumps(response_json, indent=2, ensure_ascii=False))
        
        # 检查响应结构
        if "choices" in response_json:
            print(f"\n✓ 响应包含 choices 字段")
            if len(response_json["choices"]) > 0:
                print(f"✓ choices 数组不为空，长度：{len(response_json['choices'])}")
                choice = response_json["choices"][0]
                if "message" in choice:
                    print(f"✓ choice 包含 message 字段")
                    message = choice["message"]
                    if "content" in message:
                        content = message["content"]
                        if content is None:
                            print(f"\n✗ 问题发现：content 字段为 null!")
                            print(f"   这是 AI 服务返回的问题，content 字段应该是字符串但返回了 null")
                        elif content == "":
                            print(f"\n✗ 问题发现：content 字段为空字符串!")
                        else:
                            print(f"\n✓ content 字段正常：{content[:50]}...")
                    else:
                        print(f"\n✗ 问题发现：message 中没有 content 字段!")
                        print(f"   message 字段内容：{message}")
                else:
                    print(f"\n✗ 问题发现：choice 中没有 message 字段!")
                    print(f"   choice 字段内容：{choice}")
            else:
                print(f"\n✗ 问题发现：choices 数组为空!")
        else:
            print(f"\n✗ 问题发现：响应中没有 choices 字段!")
            print(f"   响应内容：{response_json}")
    except json.JSONDecodeError as e:
        print(f"\n✗ 响应不是有效的 JSON: {e}")
        print(f"   响应文本：{response.text[:500]}")
        
except requests.exceptions.Timeout:
    print("✗ 请求超时 (30 秒)! AI 服务可能过载或网络不通")
except requests.exceptions.ConnectionError as e:
    print(f"✗ 连接错误：{e}")
    print("   可能原因：AI 服务未启动、IP 地址错误、端口被防火墙阻止")
except Exception as e:
    print(f"✗ 其他错误：{type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
