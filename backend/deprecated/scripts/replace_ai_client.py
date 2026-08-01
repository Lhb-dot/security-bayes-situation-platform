# 用于替换 main.py 中 AI 调用方式的脚本
import re

# 读取 main.py 文件
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 替换导入语句，添加 DIFY_CONFIG 导入
old_import = '''from config import (
    CRAWLER_CONFIG,
    DEEPSEEK_CONFIG,
    TEXT_SPLITTER_CONFIG,
    EVENT_EXTRACTION_TEMPLATE,
    KNOWLEDGE_BASE_CONFIG,
    INTERNAL_IMPACT_TEMPLATE,
    DYNAMIC_KEYWORDS_TEMPLATE,
    INNER_EVENT_EXTRACTION_TEMPLATE
)'''

new_import = '''from config import (
    CRAWLER_CONFIG,
    DEEPSEEK_CONFIG,
    DIFY_CONFIG,
    TEXT_SPLITTER_CONFIG,
    EVENT_EXTRACTION_TEMPLATE,
    KNOWLEDGE_BASE_CONFIG,
    INTERNAL_IMPACT_TEMPLATE,
    DYNAMIC_KEYWORDS_TEMPLATE,
    INNER_EVENT_EXTRACTION_TEMPLATE
)'''

content = content.replace(old_import, new_import)

# 2. 替换 StrategicIntelligenceCrawler 的 __init__ 方法中的初始化代码
old_init = '''        # 初始化 AI 引擎
        self.llm = LocalVLLMClient(
            api_key=DEEPSEEK_CONFIG["api_key"],
            api_url=DEEPSEEK_CONFIG["api_url"],
            model=DEEPSEEK_CONFIG["model"],
            temperature=DEEPSEEK_CONFIG["temperature"],
            max_tokens=DEEPSEEK_CONFIG["max_tokens"]
        )

        # 初始化知识库
        self.kb_client = KnowledgeBaseClient(
            api_url=KNOWLEDGE_BASE_CONFIG["api_url"],
            api_key=KNOWLEDGE_BASE_CONFIG["api_key"]
        )'''

new_init = '''        # 初始化 Dify AI 引擎
        self.llm = DifyClient(
            api_url=DIFY_CONFIG["api_url"],
            api_key=DIFY_CONFIG["api_key"],
            user=DIFY_CONFIG["user"]
        )

        # 初始化知识库
        self.kb_client = KnowledgeBaseClient(
            api_url=KNOWLEDGE_BASE_CONFIG["api_url"],
            api_key=KNOWLEDGE_BASE_CONFIG["api_key"]
        )'''

content = content.replace(old_init, new_init)

# 3. 替换 extract_events 方法中的调用方式
old_extract = '''    def extract_events(self, raw_text: str) -> List[Dict[str, Any]]:
        """调用 AI 提取符合前端结构的事件"""
        prompt = EVENT_EXTRACTION_TEMPLATE.replace("{content}", raw_text)
        response_text = self.llm.invoke(prompt)'''

new_extract = '''    def extract_events(self, raw_text: str) -> List[Dict[str, Any]]:
        """调用 AI 提取符合前端结构的事件"""
        prompt = EVENT_EXTRACTION_TEMPLATE.replace("{content}", raw_text)
        response_text = self.llm.chat(query=prompt)'''

content = content.replace(old_extract, new_extract)

# 4. 替换 analyze_strategic_impact 方法中的调用方式
old_analyze = '''    def analyze_strategic_impact(self, event: Dict[str, Any]):
        """调用 AI 进行战略推演分析"""
        kb_info = self.kb_client.query(event.get("event_name", ""))["response"]
        
        # 填充模板
        prompt = INTERNAL_IMPACT_TEMPLATE.replace("{event_name}", event.get("event_name", ""))'''

new_analyze = '''    def analyze_strategic_impact(self, event: Dict[str, Any]):
        """调用 AI 进行战略推演分析"""
        kb_info = self.kb_client.query(event.get("event_name", ""))["response"]
        
        # 填充模板
        prompt = INTERNAL_IMPACT_TEMPLATE.replace("{event_name}", event.get("event_name", ""))'''

# 这个方法中可能还有其他调用，需要查找所有 self.llm.invoke 的调用
content = content.replace(old_analyze, new_analyze)

# 5. 替换所有 self.llm.invoke 为 self.llm.chat
content = content.replace('self.llm.invoke(', 'self.llm.chat(query=')

# 写回文件
with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ AI 调用方式已替换为 Dify API")
