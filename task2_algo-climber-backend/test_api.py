import requests
import json

# 测试 LLM API
llm_url = "http://10.181.2.17:10801/v1/chat/completions"
llm_data = {
    "model": "Qwen3-8B-FP8",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.1,
    "max_tokens": 100
}

print("测试 LLM API...")
try:
    llm_response = requests.post(llm_url, json=llm_data, timeout=10)
    print(f"LLM API 状态码: {llm_response.status_code}")
    print(f"LLM API 响应: {llm_response.json()}")
except Exception as e:
    print(f"LLM API 连接失败: {e}")

# 测试 Embedding API
embedding_url = "http://10.181.2.17:10802/v1/embeddings"
embedding_data = {
    "model": "Qwen3-Embedding-0.6B",
    "input": "测试文本"
}

print("\n测试 Embedding API...")
try:
    embedding_response = requests.post(embedding_url, json=embedding_data, timeout=10)
    print(f"Embedding API 状态码: {embedding_response.status_code}")
    print(f"Embedding API 响应: {embedding_response.json()}")
except Exception as e:
    print(f"Embedding API 连接失败: {e}")

# 测试知识库 API
kb_url = "http://localhost:9621/query"
kb_data = {
    "query": "测试查询"
}

print("\n测试知识库 API...")
try:
    kb_response = requests.post(kb_url, json=kb_data, timeout=10)
    print(f"知识库 API 状态码: {kb_response.status_code}")
    print(f"知识库 API 响应: {kb_response.json()}")
except Exception as e:
    print(f"知识库 API 连接失败: {e}")
