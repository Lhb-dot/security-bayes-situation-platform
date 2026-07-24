# 用于更新 LocalVLLMClient 类的脚本
import re

# 读取 main.py 文件
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 定义新的 LocalVLLMClient 类
new_client = '''# 自定义本地 LLM 客户端 - 使用 OpenAI SDK
class LocalVLLMClient:
    def __init__(self, api_key: str, api_url: str, model: str, temperature: float, max_tokens: int, **kwargs):
        from openai import OpenAI
        
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # 提取 base_url（去掉 /chat/completions 后缀）
        base_url = api_url.replace('/chat/completions', '')
        
        # 初始化 OpenAI 客户端
        self.client = OpenAI(
            api_key=api_key if api_key and api_key != "your_api_key" else "EMPTY",
            base_url=base_url,
            timeout=60.0  # 增加超时时间到 60 秒
        )

    def invoke(self, input_data: Dict[str, Any]) -> str:
        # 这里的 input_data 实际上是模板填充后的内容
        # 兼容 LangChain 的调用方式
        prompt = ""
        if isinstance(input_data, dict):
            # 如果是字典，说明是链式调用的中间态
            prompt = str(input_data)
        else:
            prompt = str(input_data)

        try:
            # 使用 OpenAI SDK 调用
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # 检查响应
            if response is None:
                print("❌ AI 响应为 None")
                return ""
            
            if not response.choices or len(response.choices) == 0:
                print("❌ AI 响应 choices 为空")
                return ""
            
            content = response.choices[0].message.content
            if content is None:
                print("❌ AI 响应 content 为 null")
                return ""
            
            return content
            
        except Exception as e:
            print(f"❌ AI 调用失败：{type(e).__name__}: {e}")
            return ""'''

# 使用正则表达式找到并替换 LocalVLLMClient 类
pattern = r'# 自定义本地 LLM 客户端\nclass LocalVLLMClient:.*?(?=\n# 知识库客户端)'
replacement = new_client + '\n\n'

# 执行替换
new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# 写回文件
with open('main.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ LocalVLLMClient 类已更新为使用 OpenAI SDK")
