"""应用配置：从 backend/app/.env 读取环境变量。

仍在使用的配置只有 ``DEEPSEEK_CONFIG``（报告自然语言润色，见
app/services/report_nl.py）。其余名字均为二期归档产物，本轮已全部删除。

已删除的归档内容（零引用，证据见 docs/全项目代码审查/报告/B6b-1.md 与 X1 报告）：
- 旧 ``CRAWLER_CONFIG`` 注释块：内含第三方平台（微博）会话 Cookie 明文，
  属提交进版本库的凭据泄漏，必须清除；
- ``KNOWLEDGE_BASE_CONFIG`` / ``DIFY_CONFIG`` 注释块、``KB_QUERIES`` /
  ``DEFAULT_KB_QUERIES``；
- 四个 ``*_ARCHIVED`` 提示词模板正文与 ``STRATEGIC_FILTER``；
- ``CRAWLER_CONFIG`` / ``KNOWLEDGE_BASE_CONFIG`` / ``DIFY_CONFIG`` 三个空占位字典与
  ``EVENT_EXTRACTION_TEMPLATE`` / ``INTERNAL_IMPACT_TEMPLATE`` /
  ``DYNAMIC_KEYWORDS_TEMPLATE`` / ``INNER_EVENT_EXTRACTION_TEMPLATE`` 四个空串：
  它们唯一的用途是让 ``backend/deprecated/**`` 能 import 成功；该目录已于本轮审查
  整体删除（``git rm -r backend/deprecated``），占位符随之删除。
需要正文时用 ``git show <commit>:backend/app/config.py`` 从历史取回。
"""
import os

import dotenv

dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

try:
    # 硅基流动 DeepSeek API 配置 - 改为本地 vLLM
    DEEPSEEK_CONFIG = {
        # 本地 vLLM 不需要 API 密钥
        "api_key": os.environ['LLM_BINDING_API_KEY'],
        # 本地 vLLM API URL
        "api_url": os.environ['LLM_BINDING_HOST']+'/chat/completions',
        # 模型名称 - 使用本地加载的模型名
        "model": os.environ['LLM_MODEL'],
        # 温度参数
        "temperature": 0.1,
        # 最大生成 token 数
        "max_tokens": os.environ['MAX_TOKENS'],
        # 模型并行访问数量
        "llm_parallel": int(os.environ['MAX_ASYNC'])
    }
except KeyError as e:
    print(f"环境变量配置项{e}未设置，请检查.env文件")
    exit(1)
