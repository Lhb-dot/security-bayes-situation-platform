import os
import dotenv

dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

try:
    # [二期归档] KB_QUERIES 爬虫配置
    DEFAULT_KB_QUERIES = [
        "军事演习",
        "外交交涉", 
        "航行自由",
        "海空对峙",
        "防务合作"
    ]

    KB_QUERIES = (
        [ t.strip() for t in os.environ['KB_QUERIES'].split(',') if t.strip()]
        if os.environ.get('KB_QUERIES') is not None
        else DEFAULT_KB_QUERIES
    )

    # [二期归档] 爬虫配置 CRAWLER_CONFIG 已禁用
    # CRAWLER_CONFIG = {
    # # 知识库检索query列表，可选择获取的业务环节，会被用于结合风险因子和知识库内容生成动态关键词
    # "kb_queries": KB_QUERIES,
    # # 默认搜索关键词列表，当无法从风险因子和知识库内容生成动态关键词时，会使用此列表
    # "default_keywords": [
    # "自卫队", "解放军", 
    # "海警巡航", "联合军演", "越线", "防卫省", "防空识别区",
    # "战机拦截", "护卫舰", "驱逐舰", "美日同盟", "印太战略",
    # "航行自由", "专属经济区", "外交部抗议", "防务预算", "台湾海峡"
    # ],
    # # 传入风险因子文件，必须为.csv文件或.xlsx文件
    # "risk_factors_file": os.environ['RISK_FACTORS_FILE'],
    # # 每个关键词最多爬取的页数
    # "max_pages": int(os.environ['MAX_PAGES']),
    # # 外部事件单次程序运行最大提取事件数量（0表示无限制）
    # "max_events_per_run": int(os.environ['MAX_EVENTS_PER_RUN']),
    # # 微博事件最大提取数量（默认为总事件数的一半）
    # "max_events_weibo": int(os.environ.get('MAX_EVENTS_WEIBO', int(os.environ['MAX_EVENTS_PER_RUN']) // 2)),
    # # 外部事件输出文件路径
    # "output_file": "strait_events.json",
    # # 外部事件输出CSV文件路径
    # "csv_file": "strait_events.csv",
    # # 请求头 - 移动版微博
    # "headers": {
    # 'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
    # 'Accept': 'application/json, text/plain, */*',
    # 'Accept-Language': 'zh-CN,zh;q=0.9',
    # 'Referer': 'https://m.weibo.cn/',
    # 'Connection': 'keep-alive',
    # 'X-Requested-With': 'XMLHttpRequest',
    # 'MWeibo-Pwa': '1'
    # },
    # # 移动版微博Cookie (需要替换为您的实际Cookie)
    # "cookies": "XSRF-TOKEN=776302;SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9W5_HFoJlvLzZT4Svrfed9Th5NHD95QNe0McSK-4eKeRWs4Dqcj6i--fi-z7iKysi--4iK.4iKnRi--fiKysi-8Wi--NiKnRi-zpi--fiK.ciKL2i--Ni-iWi-8si--fi-2fi-zc;MLOGIN=1;SUB=_2A25K5dmsDeRhGeFN7FQU9SfNyDSIHXVpm1NkrDV6PUJbktANLUf7kW1NQ8MemRjLmvIZkIC7hxyI6QaJBuMesmQC;ALF=1745434364;_T_WM=96334028590;M_WEIBOCN_PARAMS=lfid%3D100103type%253D1%2526q%253D%25E8%25A3%2585%25E5%25A4%2587%25E5%2588%25B6%25E9%2580%25A0%26luicode%3D20000174%26fid%3D100103type%253D3%2526q%253D%25E8%25A3%2585%25E5%25A4%2587%25E5%2588%25B6%25E9%2580%25A0%2526t%253D%26uicode%3D20000174;SCF=AqiSG_P4ZMOp6XSzNLvspBONwdIB9aqNFCeIE7fJ9i8-wO4cXSXAeNJ7SHV-rhY_UfpulWufyptWMQqW0ei5oNs.;SSOLoginState=1742842364;WEIBOCN_FROM=1110006030",
    # # 请求延迟范围（秒）
    # # 爬虫频率配置：适配前端传入的低中高频率（元组表示秒数范围：最小延迟，最大延迟）
    # "delay_ranges": {
    # "低": (15, 20),  # 频率低，延迟长，最安全
    # "中": (8, 15),   # 频率中等，均衡
    # "高": (3, 8)    # 频率高，延迟短，抓取快但容易被风控
    # },
    # # 保留默认配置以防兼容性问题
    # "delay_range": (3, 8),
    # # 是否使用代理
    # "use_proxy": False,
    # # 代理设置 (如果use_proxy为True则使用)
    # "proxies": {
    # "http": "",
    # "https": ""
    # },
    # # 最大重试次数
    # "max_retries": 3,
    # # 重试间隔（秒）
    # "retry_delay": 5,
    # # 默认开启微博外部事件抓取
    # "enable_weibo": bool(os.environ.get('ENABLE_WEIBO', True)),
    # "enable_legacy_html_parsers": True
    # }
    CRAWLER_CONFIG = {}  # [二期归档] 空占位，避免引用报错

    # [二期归档] 知识库API配置 KNOWLEDGE_BASE_CONFIG 已禁用
    # KNOWLEDGE_BASE_CONFIG = {
    # "kb_url": f"http://localhost:{os.environ['PORT']}",
    # "api_url": f"http://localhost:{os.environ['PORT']}/query",
    # "api_key": os.environ['EMBEDDING_BINDING_API_KEY'],
    # # 知识图谱相关配置
    # "graph_port": str(os.environ['PORT']),
    # "graph_labels_url": f"http://localhost:{os.environ['PORT']}/graph/label/list",
    # "graph_subgraph_url": f"http://localhost:{os.environ['PORT']}/graphs",
    # # Embedding API配置
    # "embedding_url": os.environ['EMBEDDING_BINDING_HOST'] + '/embeddings',
    # "embedding_model": os.environ['EMBEDDING_MODEL'],
    # # 内部事件提取配置
    # "max_entities_for_inner_events": 30,  # 最多使用30个实体进行内部事件凝练
    # "similarity_threshold": float(os.environ['INNER_SIMILARITY_THRESHOLD']),  # embedding相似度阈值
    # # 并行配置
    # "kg_subgraph_parallel": int(os.environ['MAX_ASYNC']),  # 知识图谱子图获取并发数
    # "inner_events_parallel_enabled": True,  # 是否启用内部事件并行处理
    # }
    KNOWLEDGE_BASE_CONFIG = {}  # [二期归档] 空占位

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

    # [二期归档] Dify AI 平台配置 DIFY_CONFIG 已禁用
    # DIFY_CONFIG = {
    # "api_url": os.environ['DIFY_BACKEND'] + '/chat-messages',
    # "api_key": os.environ['DIFY_API_KEY'],
    # "user": os.environ.get('DIFY_USER', 'abc-123')
    # }
    DIFY_CONFIG = {}  # [二期归档] 空占位

    # [二期归档] 文本分割器配置 TEXT_SPLITTER_CONFIG 已禁用
    # TEXT_SPLITTER_CONFIG = {
        # 分隔符
    # "separator": "\n",
    # # 块大小
    # "chunk_size": 1200,
    # # 块重叠
    # "chunk_overlap": 50
    # }
except KeyError as e:
    print(f"环境变量配置项{e}未设置，请检查.env文件")
    exit(1)

# [二期归档] 事件提取提示模板
EVENT_EXTRACTION_TEMPLATE = ""  # 已归档"""
# """
EVENT_EXTRACTION_TEMPLATE_ARCHIVED = """
请从以下内容中提取与中日台海地缘政治、军事安全或外交博弈相关的事件信息，并按照指定JSON格式返回。

如果内容与中日台海局势或军事外交无关，请返回空JSON数组 []。

内容:
{content}

请提取并映射为如下结构字段：

1. event:
   - name: 事件名称
   - time: 事件发生时间（如有，格式尽量为YYYY-MM-DD，没有就不返回）
   - is_key: 是否为关键事件（根据事件重要性判断，true/false）

2. source:
   - type: 来源类型，从以下选项中选择：政府/官方机构、新闻媒体、网络论坛、自媒体
   - location: 事件发生地点（如有）
     * 国内请使用标准省市名称（如北京市、广东省等）
     * 国外按实际国家或城市填写
     * 只能填写一个地点

3. risk:
   - level: 风险等级（高/中/低，根据事件影响判断）
   - category: 风险类别（如：武装冲突、海空对峙、外交降级、经济制裁、航道封锁等）

4. impact:
   - type: 影响类型（积极/消极/中性）

5. analysis:
   - sentiment: 舆论或事件倾向（如：支持、反对、中立、支持强硬等）
   - driver: 主要驱动因素（如：主权宣示、军事政策、军事安全、技术发展、防务政策调整、地缘博弈等）
   - trend: 发展趋势（积极/消极/不确定）

6. topics:
   - 关键词标签（与地缘战略相关，如：台海危机、东海争端、反介入/区域拒止、兵力推演等，多个用数组表示）

返回格式（可能包含多个事件）：
```json
[
  {
    "event": {
      "name": "事件名称",
      "time": "事件时间",
      "is_key": true
    },
    "source": {
      "type": "政府/官方机构",
      "location": "中国"
    },
    "risk": {
      "level": "高",
      "category": "军事行动"
    },
    "impact": {
      "type": "消极"
    },
    "analysis": {
      "sentiment": "支持强硬",
      "driver": "军事安全动作",
      "trend": "消极"
    },
    "topics": ["关键词1", "关键词2"]
  }
  ```

只返回JSON数据，不要有任何额外说明文字。
"""

# [二期归档] 内部分析提示模板
INTERNAL_IMPACT_TEMPLATE = ""  # 已归档"""
# """
INTERNAL_IMPACT_TEMPLATE_ARCHIVED = """
请分析以下外部事件和知识库提供的战略情报，评估该事件对我方战略态势及相关决策机构可能产生的影响。

外部事件:
事件名称: {event_name}
事件描述: {description}
相关军事力量/武器装备: {equipment}
地缘影响: {economy_impact}

知识库相关信息:
{knowledge_base_info}

注意：如果知识库信息显示"知识库查询无内容，请自主进行分析"，请基于事件本身的信息和地缘政治/军事战略的一般规律进行推演分析。

请分析该外部事件对我方总体战略部署的影响，包括但不限于:
1. 潜在战略机遇，从以下类型中选择一个填写: 主权宣示, 军事威慑, 外交突破, 联盟巩固, 战术试探。
2. 潜在风险类别，从以下类型中选择一个填写: 武装冲突, 外交危机, 经济制裁, 舆论反噬, 军备竞赛。
3. 对国家安全/地区稳定的影响，从以下分类中选择一个填写: 积极影响, 消极影响, 中性影响。
4. 对总体地缘战略的影响，从以下分类中选择一个填写: 需要升级应对, 维持战略定力, 需要调整部署。
5. 建议采取的战略应对措施，从以下分类中选择一个进行填写：加强实兵演练, 提出严正交涉, 增加前沿武力部署, 寻求国际机制斡旋, 实施对等反制裁。
6. 战略威慑指数，取值在0~1之间，表示我方可藉此事件形成的威慑力大小，0表示无威慑，1表示威慑力极大，精确到小数点后一位。
7. 冲突升级风险指数，取值在0~1之间，表示事件引发实质性武装冲突的风险大小，0表示无风险，1表示风险极高，精确到小数点后一位。
8. 综合战略态势分数，取值在-1~1之间，表示从劣势到优势，0表示均势/中立，精确到小数点后一位即可。

分析结果应当客观、具体且有可行性。JSON格式返回，不要有其他文字，按照以下内容：
```json
{{
    "potential_business_opportunities": "潜在战略机遇，注意从提供的分类中选择一个填写",
    "potential_risks_category": "潜在风险，注意从提供的分类中选择一个填写",
    "impact_on_products_services": "对国家安全/地区稳定的影响，注意从提供的分类中选择一个填写",
    "impact_on_strategy": "对总体地缘战略的影响，注意从提供的分类中选择一个填写",
    "suggested_actions": "建议采取的战略应对措施",
    "business_opportunity_factor": <战略威慑指数>,
    "potential_risks_factor": <冲突升级风险指数>,
    "internal_impact_factor": <综合战略态势分数>
}}
```
"""

# [二期归档] 动态关键词生成提示模板
DYNAMIC_KEYWORDS_TEMPLATE = ""  # 已归档"""
# """
DYNAMIC_KEYWORDS_TEMPLATE_ARCHIVED = """
请根据以下地缘风险活动数据和知识库信息，为中日台海战略情报微博爬虫生成合适的搜索关键词。

地缘风险活动数据分析:
{risk_analysis}

知识库相关信息:
{knowledge_base_info}

目标：生成10-15个与中日台海局势相关的搜索关键词，这些关键词应该：

1. 涵盖高风险冲突领域，重点关注海空摩擦较多的区域
2. 结合知识库信息，关注近期外军动向和防务政策演变
3. 包含军事部署、外交表态、同盟演习等多个维度
4. 适合在微博等社交媒体平台搜索相关突发事件情报

请按照重要性排序，以JSON数组格式返回关键词列表：
```json
["关键词1", "关键词2", "关键词3", ...]
```

只返回JSON数据，不要有其他文字。
"""

# [二期归档] 内部事件凝练提示模板
INNER_EVENT_EXTRACTION_TEMPLATE = ""  # 已归档"""
# """
INNER_EVENT_EXTRACTION_TEMPLATE_ARCHIVED = """
请基于以下相关战略主体的内部情报知识图谱信息，凝练出战略/军事内部的重要事件。

战略行动环节背景:
{business_context}

地缘风险因子信息:
{risk_analysis}

知识图谱实体和关系信息:
节点信息:
{nodes_info}

关系信息:
{edges_info}

请根据上述信息凝练出相关方内部的重要军事/外交行动事件，每个事件应该包含以下信息:
1. event_name: 行动/事件名称（基于知识图谱中的实体和关系推断）
2. time: 事件发生时间（如果无法确定，可以设为"未知"）
3. location: 事件发生海域或地点（从地理位置实体中推断）
4. people: 相关防务长官或军事组织（从组织实体中提取）
5. equipment: 相关武器装备或兵力（从装备类实体中提取）
6. economy_impact: 战略地缘影响描述（基于实体关系推断）
7. description: 战术行动或外交事件的简要描述（综合多个实体关系描述）
8. internal_impact: 这是内部推演事件，不需要知识库查询，直接进行战略战术意图分析
9. business_context: 从以下四个环节中选择一个填写：【情报侦察、兵力部署、实兵演习、外交行动】（只能四选一）

注意事项:
- 重点关注战机拦截、舰艇跟踪、防务会谈、军演调动等地缘事件
- 基于实体间的关系推断合理的战术或战略意图
- 优先提取与冲突风险因子直接相关的行动
- 确保事件描述符合军语规范和地缘分析逻辑
- business_context 字段必须严格从【情报侦察、兵力部署、实兵演习、外交行动】中四选一，不可输出其他值或多选。

JSON格式返回（可能包含多个事件）:
```json
[
    {{
        "event_name": "事件名称",
        "time": "事件时间",
        "location": "事件地点",
        "people": ["相关组织或人物"],
        "equipment": ["相关武器装备或兵力"],
        "economy_impact": "战略地缘影响描述",
        "description": "基于情报图谱的行动详细描述",
        "internal_impact": "战略战术意图分析（后续填充）",
        "business_context": "情报侦察/兵力部署/实兵演习/外交行动（四选一）"
    }}
]
```

只返回JSON数据，不要有其他文字。
"""

STRATEGIC_FILTER = ["强硬", "驱逐舰", "拦截", "演习", "部署", "制裁", "预警", "关切", "战略", "冲突", "空袭", "无人机", "核武"]



if __name__ == "__main__":
    print(DEEPSEEK_CONFIG)