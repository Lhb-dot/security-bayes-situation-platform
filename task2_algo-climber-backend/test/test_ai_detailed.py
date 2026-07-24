import requests
import json
import sys

print("=" * 60)
print("AI 服务详细诊断")
print("=" * 60)

api_url = "http://10.181.2.17:10801/v1/chat/completions"
model = "Qwen3-8B"

print(f"\n测试 URL: {api_url}")
print(f"测试模型：{model}\n")

# 先测试网络连通性
print("【步骤 1】测试网络连通性...")
try:
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex(('10.181.2.17', 10801))
    sock.close()
    if result == 0:
        print("✓ 端口 10801 可达")
    else:
        print(f"✗ 端口 10801 不可达，错误码：{result}")
        sys.exit(1)
except Exception as e:
    print(f"✗ 网络测试失败：{e}")
    sys.exit(1)

# 发送请求
print("\n【步骤 2】发送 HTTP 请求...")
headers = {"Content-Type": "application/json"}
data = {
    "model": model,
    "messages": [{"role": "user", "content": "你好，请回复我"}],
    "temperature": 0.1,
    "max_tokens": 100
}

print(f"请求数据：{json.dumps(data, ensure_ascii=False)}")

try:
    response = requests.post(api_url, headers=headers, json=data, timeout=30)
    print(f"\n✓ HTTP 请求成功")
    print(f"状态码：{response.status_code}")
    print(f"状态消息：{response.reason}")
    print(f"\n响应头:")
    for key, value in response.headers.items():
        print(f"  {key}: {value}")
    
    print(f"\n【步骤 3】解析响应内容...")
    print(f"响应原始内容 ({len(response.text)} 字符):")
    print(response.text)
    
    try:
        response_json = response.json()
        print(f"\n✓ JSON 解析成功")
        print(f"\n解析后的 JSON 结构:")
        print(json.dumps(response_json, indent=2, ensure_ascii=False))
        
        # 详细检查
        print(f"\n【步骤 4】检查响应结构...")
        if "choices" not in response_json:
            print("✗ 错误：响应中没有 'choices' 字段")
            print(f"   可用字段：{list(response_json.keys())}")
        elif len(response_json["choices"]) == 0:
            print("✗ 错误：'choices' 数组为空")
        else:
            choice = response_json["choices"][0]
            print(f"✓ 'choices' 数组正常，长度：{len(response_json['choices'])}")
            
            if "message" not in choice:
                print("✗ 错误：choice 中没有 'message' 字段")
                print(f"   choice 字段：{choice}")
            else:
                message = choice["message"]
                print(f"✓ 'message' 字段存在")
                
                if "content" not in message:
                    print("✗ 错误：'message' 中没有 'content' 字段")
                    print(f"   message 字段：{message}")
                else:
                    content = message["content"]
                    print(f"✓ 'content' 字段存在")
                    print(f"   content 类型：{type(content)}")
                    print(f"   content 值：{repr(content)}")
                    
                    if content is None:
                        print("\n" + "=" * 60)
                        print("❌ 问题确认：content 字段为 null")
                        print("=" * 60)
                        print("\n可能原因:")
                        print("1. AI 模型加载失败")
                        print("2. 模型推理出错")
                        print("3. 输入 prompt 格式不正确")
                        print("4. 模型服务配置问题")
                        print("\n建议:")
                        print("1. 检查 AI 服务日志")
                        print("2. 确认模型是否正确加载")
                        print("3. 尝试使用其他模型名称")
                    elif content == "":
                        print("\n" + "=" * 60)
                        print("❌ 问题确认：content 字段为空字符串")
                        print("=" * 60)
                    else:
                        print("\n" + "=" * 60)
                        print("✓ AI 服务正常!")
                        print("=" * 60)
                        print(f"\nAI 回复：{content}")
                        
    except json.JSONDecodeError as e:
        print(f"✗ JSON 解析失败：{e}")
        print(f"   响应文本：{response.text[:500]}")
        
except requests.exceptions.Timeout:
    print("✗ 请求超时 (30 秒)")
    print("   可能原因：AI 服务过载、网络延迟、模型推理时间过长")
except requests.exceptions.ConnectionError as e:
    print(f"✗ 连接错误：{e}")
    print("   可能原因：AI 服务未启动、IP 错误、防火墙阻止")
except Exception as e:
    print(f"✗ 未知错误：{type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
