# 用于添加 DifyClient 类的脚本
import re

# 读取 main.py 文件
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 定义新的 DifyClient 类
new_dify_client = '''# Dify AI 平台客户端 - 使用 chat-messages API
class DifyClient:
    def __init__(self, api_url: str, api_key: str, user: str = "abc-123"):
        self.api_url = api_url
        self.api_key = api_key
        self.user = user
        self.session = requests.Session()
        
    def chat(self, query: str, conversation_id: str = "", inputs: Dict[str, Any] = None, 
             response_mode: str = "blocking", files: List = None) -> str:
        """
        调用 Dify chat-messages API
        
        Args:
            query: 用户查询
            conversation_id: 会话 ID（可选，用于多轮对话）
            inputs: 额外输入参数（可选）
            response_mode: 响应模式，"blocking" 或 "streaming"
            files: 文件列表（可选）
            
        Returns:
            AI 响应内容
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "inputs": inputs if inputs else {},
            "query": query,
            "response_mode": response_mode,
            "conversation_id": conversation_id,
            "user": self.user
        }
        
        # 如果有文件，添加到请求中
        if files:
            data["files"] = files
        
        try:
            print(f"🤖 调用 Dify API: {query[:50]}...")
            response = self.session.post(
                self.api_url, 
                headers=headers, 
                json=data, 
                timeout=60
            )
            response.raise_for_status()
            
            # 处理流式响应
            if response_mode == "streaming":
                result = ""
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data_str = line[6:]  # 去掉 'data: ' 前缀
                            if data_str.strip() == '[DONE]':
                                break
                            try:
                                data_json = json.loads(data_str)
                                if 'answer' in data_json:
                                    result += data_json['answer']
                            except:
                                continue
                return result
            else:
                # 处理普通响应
                result = response.json()
                if 'answer' in result:
                    print(f"✅ Dify 响应成功")
                    return result['answer']
                elif 'message' in result:
                    return result['message']
                else:
                    print(f"⚠️ Dify 响应格式异常：{result}")
                    return str(result)
                    
        except requests.exceptions.Timeout:
            print("❌ Dify API 请求超时")
            return ""
        except requests.exceptions.RequestException as e:
            print(f"❌ Dify API 请求失败：{type(e).__name__}: {e}")
            return ""
        except Exception as e:
            print(f"❌ Dify API 处理失败：{type(e).__name__}: {e}")
            return ""


'''

# 在 KnowledgeBaseClient 类之前插入 DifyClient 类
pattern = r'# 知识库客户端（保持原有逻辑，适配新端口）\nclass KnowledgeBaseClient:'
replacement = new_dify_client + '# 知识库客户端（保持原有逻辑，适配新端口）\nclass KnowledgeBaseClient:'

# 执行替换
new_content = re.sub(pattern, replacement, content)

# 写回文件
with open('main.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ DifyClient 类已添加")
