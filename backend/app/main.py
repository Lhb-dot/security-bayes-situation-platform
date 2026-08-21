import os
import sys
# 确保 backend/ 在 sys.path 中，支持 python app/main.py 和 python -m app.main 两种启动方式
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hashlib
import logging
import re
import json
import time
import random  # <- 补上这个导入
import csv
import pydantic
import copy
from pathlib import Path
from pydantic import BaseModel, Field


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

root_logger = logging.getLogger()
root_logger.handlers.clear()
root_logger.setLevel(LOG_LEVEL)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(LOG_LEVEL)
stream_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
)
stream_handler.terminator = "\n"  # 强制每条日志换行，避免粘连
root_logger.addHandler(stream_handler)

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    import numpy as np
except ImportError as e:
    logger.warning("无法导入 pandas 或 numpy 库，将使用模拟数据: %s", e)
    pd = None
    np = None
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
# [二期] 舆情爬虫模块已归档至 backend/deprecated/
# from app.multi_source_crawler import MultiSourceCrawler

def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """从模型返回文本中提取首个 JSON 对象"""
    if not text or not isinstance(text, str):
        return None

    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.debug("extract_json failed: invalid json", exc_info=True)
        return None

# 导入配置（二期舆情爬虫相关 CRAWLER_CONFIG / DIFY_CONFIG / KNOWLEDGE_BASE_CONFIG 已归档）
from app.config import (
    # CRAWLER_CONFIG,       # [二期] 归档
    DEEPSEEK_CONFIG,
    # DIFY_CONFIG,           # [二期] 归档
    # TEXT_SPLITTER_CONFIG,  # [二期] 归档
    # EVENT_EXTRACTION_TEMPLATE,      # [二期] 归档
    # KNOWLEDGE_BASE_CONFIG,          # [二期] 归档
    # INTERNAL_IMPACT_TEMPLATE,       # [二期] 归档
    # DYNAMIC_KEYWORDS_TEMPLATE,      # [二期] 归档
    # INNER_EVENT_EXTRACTION_TEMPLATE # [二期] 归档
)

# 自定义本地 LLM 客户端 - 使用 OpenAI SDK
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
        prompt = str(input_data)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            if not response or not response.choices:
                raise RuntimeError("LLM response.choices is empty")
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("LLM response content is null")
            return content
        except Exception:
            logger.exception("AI invoke failed")
            raise  # 不吞异常，直接抛出完整堆栈


# Dify AI 平台客户端 - 使用 chat-messages API
# class DifyClient:
#     def __init__(self, api_url: str, api_key: str, user: str = "abc-123"):
#         self.api_url = api_url
#         self.api_key = api_key
#         self.user = user
#         self.session = requests.Session()
#         
#     def chat(self, query: str, conversation_id: str = "", inputs: Dict[str, Any] = None, 
#              response_mode: str = "blocking", files: List = None) -> str:
#         """
#         调用 Dify chat-messages API
#         
#         Args:
#             query: 用户查询
#             conversation_id: 会话 ID（可选，用于多轮对话）
#             inputs: 额外输入参数（可选）
#             response_mode: 响应模式，"blocking" 或 "streaming"
#             files: 文件列表（可选）
#             
#         Returns:
#             AI 响应内容
#         """
#         headers = {
#             "Authorization": f"Bearer {self.api_key}",
#             "Content-Type": "application/json"
#         }
# 
#         data = {
#             "inputs": inputs if inputs else {},
#             "query": query,
#             "response_mode": response_mode,
#             "conversation_id": conversation_id,
#             "user": self.user
#         }
# 
#         if files:
#             data["files"] = files
# 
#         logger.debug("调用 Dify API, response_mode=%s", response_mode)
#         try:
#             response = self.session.post(
#                 self.api_url,
#                 headers=headers,
#                 json=data,
#                 timeout=60
#             )
#             response.raise_for_status()
#         except requests.RequestException:
#             logger.exception("Dify API 请求失败")
#             raise
# 
#         if response_mode == "streaming":
#             result = ""
#             for line in response.iter_lines():
#                 if not line:
#                     continue
#                 line = line.decode("utf-8")
#                 if not line.startswith("data: "):
#                     continue
#                 data_str = line[6:]
#                 if data_str.strip() == "[DONE]":
#                     break
#                 try:
#                     data_json = json.loads(data_str)
#                     if "answer" in data_json:
#                         result += data_json["answer"]
#                 except json.JSONDecodeError:
#                     logger.debug("streaming chunk 非法 JSON，已跳过")
#                     continue
#             return result
# 
#         result = response.json()
#         if "answer" in result:
#             logger.debug("Dify 响应成功")
#             return result["answer"]
#         if "message" in result:
#             return result["message"]
# 
#         logger.warning("Dify 响应格式异常: %s", result)
#         return str(result)
# 
# 
# 
# 知识库客户端（保持原有逻辑，适配新端口）
# class KnowledgeBaseClient:
#     def __init__(self, api_url: str, api_key: str):
#         self.api_url = api_url
#         self.api_key = api_key
#         self.session = requests.Session()
# 
#     def query(self, query_text: str) -> Dict[str, Any]:
#         data = {"query": query_text, "top_k": 3}
#         try:
#             res = self.session.post(self.api_url, json=data, timeout=10)
#             res.raise_for_status()
#             return res.json()
#         except requests.RequestException:
#             logger.exception("KnowledgeBase query request failed: %s", query_text)
#             raise
#         except ValueError:
#             logger.exception("KnowledgeBase query json decode failed: %s", query_text)
#             raise
# 
# 战略过滤关键词（与前端保持一致）
# 
# --- 核心爬虫类：已适配战略推演前端 ---
# 
# 
# class EventBase(BaseModel):
#     name: str
#     time: Optional[str] = Field(default=None)
#     is_key: bool = Field(default=False)
# 
# 
# class SourceBase(BaseModel):
#     type: Optional[str] = Field(default=None)
#     location: Optional[str] = Field(default=None)
# 
# 
# class RiskBase(BaseModel):
#     level: Optional[str] = Field(default=None)
#     category: Optional[str] = Field(default=None)
# 
# 
# class ImpactBase(BaseModel):
#     type: Optional[str] = Field(default=None)
# 
# 
# class AnalysisBase(BaseModel):
#     sentiment: Optional[str] = Field(default=None)
#     driver: Optional[str] = Field(default=None)
#     trend: Optional[str] = Field(default=None)
# 
# 
# class ExtractEvent(BaseModel):
#     event: EventBase
#     source: Optional[SourceBase] = Field(default_factory=SourceBase)
#     risk: Optional[RiskBase] = Field(default_factory=RiskBase)
#     impact: Optional[ImpactBase] = Field(default_factory=ImpactBase)
#     analysis: Optional[AnalysisBase] = Field(default_factory=AnalysisBase)
#     topics: List[str] = Field(default_factory=list)
# 
# 
# class StrategicIntelligenceCrawler:
# 
#     def __init__(self, 
#         output_dir="output",
#         task_name="默认任务",
#         task_keywords=None,
#         task_subjects=None,
#         task_depth=1000,
#         task_intensity=70,
#         crawl_frequency="高"  
#     ) -> None:
#       
#         self.config = copy.deepcopy(CRAWLER_CONFIG)
        # --- 2. 频率控制核心逻辑 ---
#         delay_ranges = self.config.get("delay_ranges", {"高": (3, 8)})
#         self.delay_range = delay_ranges.get(crawl_frequency, delay_ranges["高"]) 
#         self.config["delay_range"] = self.delay_range  # 覆盖配置，传给底层
#         
#         assert len(task_keywords) > 0, "必须提供至少一个关键词"
#         self.keywords = task_keywords
#             
#         self.output_dir = output_dir
#         os.makedirs(self.output_dir, exist_ok=True)
#         
#         task_id = f"t-{int(time.time())}"
        # 定义输出路径
#         self.output_file = os.path.join(self.output_dir, "task_events", f"{task_id}.json")
#         self.raw_events_file = os.path.join(self.output_dir, "task_raw", f"{task_id}.json")
#         self.tasks_file = os.path.join(self.output_dir, "tasks.json")
# 
        # 确保存储事件和原始数据的子文件夹存在
#         os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
#         os.makedirs(os.path.dirname(self.raw_events_file), exist_ok=True)
# 
        # 初始化 Dify AI 引擎
#         self.llm = DifyClient(
#             api_url=DIFY_CONFIG["api_url"],
#             api_key=DIFY_CONFIG["api_key"],
#             user=DIFY_CONFIG["user"]
#         )
# 
        # 初始化知识库
#         self.kb_client = KnowledgeBaseClient(
#             api_url=KNOWLEDGE_BASE_CONFIG["api_url"],
#             api_key=KNOWLEDGE_BASE_CONFIG["api_key"]
#         )
# 
        # 任务信息
#         self.task = {
#             "id": task_id,
#             "name": task_name,
#             "status": "running",
#             "progress": 0,
#             "depth": task_depth,
#             "intensity": task_intensity,
#             "frequency": crawl_frequency,  # <--- 3. 记录进任务状态
#             "time": time.strftime("%Y-%m-%d %H:%M:%S"),
#             "keywords": self.keywords,
#             "subjects": task_subjects if task_subjects else [],
#             "articles": [],
#             "intel": []
#         }
# 
#         self.all_events = []
#         self.raw_events: List[Dict[str, Any]] = []
# 
#         self.fail_fast = bool(self.config.get("fail_fast", True))
# 
        # 真实多源爬虫
#         crawler_cfg = self.config
#         crawler_cfg["keywords"] = self.keywords
#         self.multi_crawler = MultiSourceCrawler(crawler_cfg)
# 
#         self.save_data()
# 
#     def _stable_id(self, prefix: str, *parts: str) -> str:
#         raw = "|".join([(p or "").strip() for p in parts])
#         h = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
#         return f"{prefix}-{h}"
# 
#     def extract_events(self, raw_text: str, publish_time: Optional[str] = None) -> List[ExtractEvent]:
#         """调用 AI 提取符合前端结构的事件"""
#         prompt = EVENT_EXTRACTION_TEMPLATE.replace("{content}", raw_text)
#         response_text = self.llm.chat(query=prompt)
#         logger.debug("LLM 原始响应:", response_text)  # 调试输出原始响应
#         content = re.match(r"```json\s*(.*?)\s*```", response_text, re.S)
#         events = pydantic.TypeAdapter(List[ExtractEvent]).validate_python(json.loads(content.group(1))) if content else []
#         normalized_publish_time = str(publish_time).strip() if publish_time is not None else ""
#         if normalized_publish_time:
#             for item in events:
#                 if item.event and not (item.event.time or "").strip():
#                     item.event.time = normalized_publish_time
#         logger.debug("提取事件: %s", events)
#         return events
# 
#     def _get_real_data(self, keyword: str) -> bool:
#         logger.info("fetching real data by crawler keyword=%s", keyword)
# 
#         raw_events: List[Dict[str, Any]] = []
#         rss_events = self.multi_crawler.crawl_via_rss(keyword)
#         if rss_events:
#             raw_events.extend(rss_events)
# 
#         so_events = self.multi_crawler.crawl_via_chinaso(keyword, pages=3)
#         if so_events:
#             raw_events.extend(so_events)
# 
#         if not raw_events:
#             logger.warning("关键词[%s]未抓到真实数据", keyword)
#             return False
# 
#         logger.info("关键词[%s]抓取到真实事件 %d 条", keyword, len(raw_events))
# 
#         for ev in raw_events:
#             ev['task_id'] = self.task["id"]
#             ev['raw_id'] = self._stable_id("raw", ev.get("title", ""), ev.get("link", ""))
# 
#             self.raw_events.append(ev)
#             self.save_raw()
# 
#             try:
#                 cur_events = self.extract_events(
#                     ev.get("title", "") + "\n" + ev.get("summary", ""),
#                     publish_time=ev.get("publish_time") or ev.get("time"),
#                 )
#                 cur_events = [ev.model_dump() for ev in cur_events]
#                 self.all_events.extend(cur_events)
#                 logger.info("提取事件[%d] | 当前事件总数=%d", len(cur_events), len(self.all_events))
#                 self.save_events()
#             except Exception as exc:
#                 logger.warning("原始信息已保存，但事件提纯失败: %s", exc)
#                 continue
# 
#         self.save_data()
#         logger.info("真实数据处理完成")
#         return True
# 
#     def crawl_weibo(self):
#         """按关键词抓取真实多源数据"""
#         if not self.config.get("enable_weibo", True):
#             logger.info("外部抓取已禁用")
#             return
# 
#         logger.info("开始抓取战略情报，关键词数=%d", len(self.keywords))
#         total_keywords = len(self.keywords)
# 
#         for i, kw in enumerate(self.keywords):
#             logger.info("检索关键词: %s", kw)
#             before_raw_count = len(self.raw_events)
#             before_event_count = len(self.all_events)
#             
#             self._get_real_data(kw)
#             
#             self.task["progress"] = min(100, (i + 1) / total_keywords * 100)
#             self.save_data()
#             
#             logger.info(
#                 "关键词[%s]处理完成 | progress=%.2f%% | 新增原始=%d | 新增提纯=%d",
#                 kw,
#                 self.task["progress"],
#                 len(self.raw_events) - before_raw_count,
#                 len(self.all_events) - before_event_count,
#             )
#             
            # --- 修改这里：使用动态算出的延迟范围 ---
#             sleep_time = random.uniform(*self.delay_range)
#             logger.info("触发频率控制，休眠 %.2f 秒...", sleep_time)
#             time.sleep(sleep_time)
# 
#     def save_data(self):
#         """保存为前端可直接读取的 JSON"""
#         tasks = []
#         try:
#             with open(self.tasks_file, "r", encoding="utf-8") as f:
#                 tasks = json.load(f)
#                 if isinstance(tasks, dict):
#                     tasks = [tasks]
#         except (FileNotFoundError, json.JSONDecodeError):
#             tasks = []
# 
        # 将历史残留 running（同名旧任务）标记为 failed，避免前端长期显示“运行中”
#         for t in tasks:
#             if t.get("status") == "running" and t.get("id") != self.task["id"]:
#                 t["status"] = "failed"
#             t.pop("articles", None)
#             t.pop("intel", None)
# 
#         persist_task = dict(self.task)
#         persist_task.pop("articles", None)
#         persist_task.pop("intel", None)
#         persist_task["article_count"] = len(self.raw_events)
#         persist_task["intel_count"] = len(self.all_events)
# 
        # upsert 当前任务
#         updated = False
#         for i, t in enumerate(tasks):
#             if t.get("id") == self.task["id"]:
#                 tasks[i] = persist_task
#                 updated = True
#                 break
#         if not updated:
#             tasks.append(persist_task)
# 
        # 控制文件体积，保留最近 100 条
#         tasks = tasks[-100:]
# 
#         with open(self.tasks_file, "w", encoding="utf-8") as f:
#             json.dump(tasks, f, ensure_ascii=False, indent=2)
# 
#         self.save_raw()
#         self.save_events()
# 
#         logger.info(
#             "任务已保存: %s | progress=%.2f%% | articles=%d | intel=%d",
#             self.task["name"], self.task["progress"], len(self.task["articles"]), len(self.task["intel"])
#         )
# 
#     def save_raw(self):
#         with open(self.raw_events_file, "w", encoding="utf-8",) as f:
#             json.dump(self.raw_events, f, ensure_ascii=False, indent=2)
#     
#     def save_events(self):
#         with open(self.output_file, "w", encoding="utf-8") as f:
#             json.dump(self.all_events, f, ensure_ascii=False, indent=2)
# 
#     def run(self):
#         """启动主流程"""
#         logger.info("系统启动")
#         self.crawl_weibo()
#         self.task["status"] = "completed"
#         self.task["progress"] = 100
#         self.save_data()
#         logger.info("任务完成")
#         logger.info("共收集战略情报: %d 条", len(self.task["intel"]))
#         logger.info("结果已保存至: %s", self.output_file)
        logger.info("任务信息已保存至: %s", self.tasks_file)

# ==================== FastAPI App & Routes ====================
import threading
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.algorithms.pmwnb_demo import (
    save_threshold_sim, get_all_exp, del_exp_by_id, append_exp_record
)
import app.algorithms.pmwnb_demo as pmwnb_demo
from app.services.model_sim import get_dataset_list, train_bayes_sim, infer_bayes_sim, check_service_health
from app.api.deps import get_current_user, require_scenario_admin



app = FastAPI()

# ============ 数据库 CRUD API v1 路由挂载（Service 层 /api/v1） ============
from app.api.v1 import api_router

app.include_router(api_router)

train_record = {
    "is_trained": False,
    "dataset": ""
}

# 全局训练状态管控，强制先训练后预测
train_global_status = {
    "is_trained": False,
    "current_dataset": "",
    "model_path": ""
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ 跨域中间件下方，PMWNB 贝叶斯接口 ============
# [二期归档] 设备事件接口已禁用
# @app.get("/equipment_events.json")
# async def get_equipment_events():
#     if not EQUIPMENT_EVENTS_FILE.exists():
#         raise HTTPException(status_code=404, detail="设备事件数据文件缺失")
#     return FileResponse(EQUIPMENT_EVENTS_FILE, media_type="application/json")

@app.get("/china-map.json")
async def get_map_json():
    map_file = OUTPUT_DIR / "china-map.json"
    if not map_file.exists():
        raise HTTPException(status_code=404, detail="地图数据文件缺失")
    return FileResponse(map_file, media_type="application/json")

# ===================== 大创项目：PMWNB 矩阵加权贝叶斯接口 =====================

@app.get("/api/model/dataset-list")
async def get_ds(current_user=Depends(get_current_user)):  # noqa: ARG001
    return {"code": 200, "data": get_dataset_list()}


@app.post("/api/model/save-threshold")
async def save_thr(high: float, mid: float, low: float, current_user=Depends(require_scenario_admin)):  # noqa: ARG001
    ok = save_threshold_sim(high, mid, low)
    if not ok:
        raise HTTPException(status_code=400, detail="阈值规则错误，必须满足 高>中>低")
    return {"code": 200, "msg": "全局告警阈值保存成功"}


@app.post("/api/model/train")
def api_train_bayes_model(dataset_name: str, algo_type: str = "", discrete_method: str = "", current_user=Depends(require_scenario_admin)):  # noqa: ARG001
    global train_global_status
    train_result = train_bayes_sim(dataset_name, algo_type, discrete_method)
    train_global_status["is_trained"] = True
    train_global_status["current_dataset"] = dataset_name

    # 写入实验记录（线程安全，供前端历史记录展示）
    append_exp_record({
        "dataset_name": dataset_name,
        "algo_type": algo_type or "PMWNB",
        "discrete_method": discrete_method or "EWD+MDLP",
        "accuracy": train_result["accuracy"],
        "f1": train_result["f1"],
        "recall": train_result["recall"],
        "train_time_s": train_result["train_time_s"],
        "train_time": train_result["train_time_s"],
    })

    return {"code": 200, "msg": f"{dataset_name} PMWNB训练完成", "data": train_result}


@app.post("/api/model/infer")
def api_bayes_infer(flowLength: float, duration: float, accessFreq: float, current_user=Depends(get_current_user)):  # noqa: ARG001
    global train_global_status
    if not train_global_status["is_trained"]:
        raise HTTPException(status_code=400, detail="禁止预测：请先选择数据集执行模型训练")
    input_data = {"flowLength": flowLength, "duration": duration, "accessFreq": accessFreq}
    infer_result = infer_bayes_sim(input_data)
    return {"code": 200, "msg": "AI研判完成", "data": infer_result}


@app.get("/api/model/exp-records")
async def get_exp(current_user=Depends(get_current_user)):  # noqa: ARG001
    return {"code": 200, "data": get_all_exp()}


@app.delete("/api/model/exp/{record_id}")
async def del_exp(record_id: int, current_user=Depends(require_scenario_admin)):  # noqa: ARG001
    del_exp_by_id(record_id)
    return {"code": 200, "msg": "实验记录删除完成"}
# ==================================================================

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/ (up from backend/app/)
PROJECT_ROOT = BASE_DIR.parent                      # security-bayes-platform/
OUTPUT_DIR = BASE_DIR / "storage" / "output"        # backend/storage/output/
INPUT_DIR = PROJECT_ROOT / "data"                   # data/ at project root
WEB_DIR = PROJECT_ROOT / "frontend"                 # frontend/ at project root
TASKS_FILE = OUTPUT_DIR / "tasks.json"
EQUIPMENT_EVENTS_FILE = OUTPUT_DIR / "equipment_events.json"
TASK_EVENTS_DIR = OUTPUT_DIR / "task_events"
TASK_RAW_DIR = OUTPUT_DIR / "task_raw"

STRATEGIC_FILTER = ["强硬", "驱逐舰", "拦截", "演习", "部署", "制裁", "预警", "关切", "战略", "冲突", "空袭", "无人机", "核武"]
COUNTRIES = ["中国", "美国", "伊朗", "日本", "俄罗斯", "乌克兰", "韩国", "朝鲜", "台湾"]
VIRTUAL_TITLE_FRAGMENTS = [
    "局势最新进展",
    "专家解读",
    "相关动态",
    "问题最新发展",
    "事件影响分析",
    "国际社会高度关注",
    "相关新闻：国际社会高度关注",
    "相关新闻: 国际社会对此表示关注",
]
VIRTUAL_SOURCES = {"模拟新闻源", "模拟情报源"}


# 
# class CrawlStartRequest(BaseModel):
#     task_name: str = Field(default="默认任务")
#     task_keywords: List[str] = Field(default_factory=list)
#     task_subjects: List[str] = Field(default_factory=list)
#     task_depth: int = Field(default=1000, ge=1, le=100000)
#     task_intensity: int = Field(default=70, ge=1, le=100)
#     output_dir: str = Field(default="output")
#     frequency: str = Field(default="高")
# 
# 
# class CreateOpinionTaskRequest(BaseModel):
#     task_name: str = Field(default="默认任务")
#     keywords: List[str] = Field(default_factory=list)
#     subjects: List[str] = Field(default_factory=list)
#     depth: int = Field(default=1000, ge=1, le=100000)
#     intensity: int = Field(default=70, ge=1, le=100)
#     output_dir: str = Field(default="output")
#     frequency: str = Field(default="高")
# 
# 
# class TaskEventsRequest(BaseModel):
#     task_id: str
#     limit: int = Field(default=200, ge=1, le=2000)
# 
# 
# class TaskRawRequest(BaseModel):
#     task_id: str
#     limit: int = Field(default=200, ge=1, le=5000)
# 
# 
crawl_state_lock = threading.Lock()
crawl_state: Dict[str, Any] = {
    "running": False,
    "task_id": None,
    "task_name": None,
    "started_at": None,
    "finished_at": None,
    "last_error": None,
}

ai_client_lock = threading.Lock()
ai_client = None
ai_type_cache: Dict[str, str] = {}

INFO_TYPE_OPTIONS = ["国际", "地区", "国内", "行业", "科技", "军事", "经济", "社会"]


def _read_json_file(path: Path, default: Any) -> Any:
    if not path.exists() or not path.is_file():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    return _fix_mojibake(str(value).strip())


def _is_virtual_text(title: Any, source: Any) -> bool:
    text = _to_text(title)
    src = _to_text(source)
    if src in VIRTUAL_SOURCES:
        return True
    return any(fragment in text for fragment in VIRTUAL_TITLE_FRAGMENTS)

# 
# def _get_ai_client() -> Any:
#     global ai_client
#     if ai_client is not None:
#         return ai_client
# 
#     with ai_client_lock:
#         if ai_client is not None:
#             return ai_client
#         try:
#             from config import DIFY_CONFIG
            # DifyClient is defined above in this file
# 
#             ai_client = DifyClient(
#                 api_url=DIFY_CONFIG["api_url"],
#                 api_key=DIFY_CONFIG["api_key"],
#                 user=DIFY_CONFIG["user"],
#             )
#         except Exception:
#             ai_client = None
#     return ai_client
# 
# 
# def _infer_info_type_by_rules(text: str) -> str:
#     content = _to_text(text)
#     if any(k in content for k in ["联合国", "北约", "欧盟", "全球", "国际", "多国"]):
#         return "国际"
#     if any(k in content for k in ["中东", "红海", "台海", "边境", "地区", "周边"]):
#         return "地区"
#     if any(k in content for k in ["国务院", "发改委", "国内", "本土", "省", "市"]):
#         return "国内"
#     if any(k in content for k in ["工业", "制造", "产业", "供应链", "企业"]):
#         return "行业"
#     if any(k in content for k in ["AI", "人工智能", "芯片", "算法", "数据", "网络安全"]):
#         return "科技"
#     if any(k in content for k in ["军", "导弹", "空袭", "演习", "部队", "舰", "无人机"]):
#         return "军事"
#     if any(k in content for k in ["经济", "贸易", "投资", "货币", "金融", "通胀"]):
#         return "经济"
#     if any(k in content for k in ["舆情", "民生", "教育", "医疗", "治安"]):
#         return "社会"
#     return "国际"
# 
# 
# def _ai_classify_info_type(title: str, source: str, country: str) -> str:
#     key = f"{_to_text(title)}|{_to_text(source)}|{_to_text(country)}"
#     if key in ai_type_cache:
#         return ai_type_cache[key]
# 
#     fallback = _infer_info_type_by_rules(key)
#     client = _get_ai_client()
#     if client is None:
#         ai_type_cache[key] = fallback
#         return fallback
# 
#     prompt = (
#         "你是态势感知分类器。请基于事件信息只输出一个类型，不要解释。\n"
#         f"可选类型：{', '.join(INFO_TYPE_OPTIONS)}\n"
#         f"标题：{_to_text(title)}\n"
#         f"来源：{_to_text(source)}\n"
#         f"国家：{_to_text(country)}\n"
#         "输出格式：只输出一个类型词。"
#     )
# 
#     try:
#         result = _to_text(client.chat(query=prompt))
#         for option in INFO_TYPE_OPTIONS:
#             if option in result:
#                 ai_type_cache[key] = option
#                 return option
#     except Exception:
#         pass
# 
#     ai_type_cache[key] = fallback
#     return fallback
# 
# 
# def _apply_ai_classification_to_task(task: Dict[str, Any]) -> bool:
#     updated = False
#     articles = task.get("articles") if isinstance(task.get("articles"), list) else []
#     intel = task.get("intel") if isinstance(task.get("intel"), list) else []
# 
#     for article in articles:
#         if not isinstance(article, dict):
#             continue
#         title = _to_text(article.get("title"))
#         source = _to_text(article.get("source"))
#         country = _to_text(article.get("country")) or _country_from_text(title)
#         info_type = _ai_classify_info_type(title, source, country)
#         if _to_text(article.get("info_type")) != info_type:
#             article["info_type"] = info_type
#             updated = True
# 
#     for intel_item in intel:
#         if not isinstance(intel_item, dict):
#             continue
#         title = _to_text(intel_item.get("title"))
#         source = _to_text(intel_item.get("source"))
#         country = _country_from_text(title)
#         info_type = _ai_classify_info_type(title, source, country)
#         if _to_text(intel_item.get("info_type")) != info_type:
#             intel_item["info_type"] = info_type
#             updated = True
# 
#     return updated
# 
# 
# def _persist_ai_enriched_task(task_id: Optional[str]) -> None:
#     if not task_id:
#         return
#     tasks = _load_tasks()
#     changed = False
#     for task in tasks:
#         if _to_text(task.get("id")) != _to_text(task_id):
#             continue
#         changed = _apply_ai_classification_to_task(task) or changed
#         break
# 
    if changed:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with TASKS_FILE.open("w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)


def _looks_like_mojibake(text: str) -> bool:
    if not text:
        return False
    explicit_tokens = [
        "鑸杩", "娓鍙", "鐗规湕", "鍖楀栨哗", "鏆傛椂璞", "锝2025骞",
        "鎴樹簤", "娌℃湁", "璧㈠", "鐜", "缃戝", "瀹樻柟", "璐﹀彿",
    ]
    if any(token in text for token in explicit_tokens):
        return True
    suspicious_tokens = ["Ã", "Â", "Ð", "Ñ", "å", "ä", "ç", "è", "é", "ï", "ö", "ü", "æ", "œ", "¤", "¦", "±", "¼", "½", "¿", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]
    if any(token in text for token in suspicious_tokens):
        return True

    # 常见“UTF-8 被按 GBK 解码”后出现的高频乱码汉字
    gbk_mojibake_chars = set("鐨鍦鍥鍙鍚鍒鍔鍩鍥鏃鏄鏉鏋楠彂灞曡涓氶噺鏈鏂版崯鎶樼瓑閫氶亾杞ㄨ澶囧競鎴簤娌璧讹紵缃戝瀹樻柟璐﹀彿")
    if text:
        hit = sum(1 for ch in text if ch in gbk_mojibake_chars)
        ratio = hit / max(len(text), 1)
        if ratio >= 0.18 and hit >= 6:
            return True

    # 常见乱码子串指纹（UTF-8/GBK 混乱后的高频片段）
    mojibake_fragments = [
        "鍗", "涓", "鏃", "鏈", "閬", "杞", "澶", "鍙", "鍥", "鍩", "鍔", "鍐", "鍞", "瑙", "婀", "浣", "鈥", "锛", "銆", "缃", "瀹", "鐪", "鍟", "鏍",
        "鑸杩", "娓鍙", "鐗规湕", "鏆傛椂", "鍥介檯", "绾挎媺", "鎴愬", "璞佸厤", "缁忚锤", "鍙樺寲",
        "鎴樹簤", "娌℃湁", "璧㈠", "缃戝", "瀹樻柟", "璐﹀彿",
    ]
    frag_hits = sum(text.count(fragment) for fragment in mojibake_fragments)
    if frag_hits >= 2:
        return True

    return False


def _text_quality_score(text: str) -> int:
    if not text:
        return -10_000
    length = max(len(text), 1)
    cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    suspicious_count = sum(1 for ch in text if ch in {"Ã", "Â", "Ð", "Ñ", "å", "ä", "ç", "è", "é", "ï", "ö", "ü", "æ", "œ", "¤", "¦", "±", "¼", "½", "¿"})
    control_count = sum(1 for ch in text if (0 <= ord(ch) < 32 and ch not in "\t\n\r") or (127 <= ord(ch) <= 159))
    replacement_count = text.count("�")
    printable_count = sum(1 for ch in text if ch.isprintable() or ch in "\t\n\r")
    printable_ratio = int((printable_count / length) * 100)
    return cjk_count * 8 + printable_ratio - suspicious_count * 6 - control_count * 12 - replacement_count * 10


def _fix_mojibake(text: str) -> str:
    if not text:
        return text
    if not _looks_like_mojibake(text):
        try:
            forced = text.encode("gb18030", errors="strict").decode("utf-8", errors="strict")
            if forced and _text_quality_score(forced) > _text_quality_score(text) + 12:
                return forced
        except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
            pass
        return text

    mojibake_fragments = [
        "鍗", "涓", "鏃", "鏈", "閬", "杞", "澶", "鍙", "鍥", "鍩", "鍔", "鍐", "鍞", "瑙", "婀", "浣", "鈥", "锛", "銆", "缃", "瀹", "鐪", "鍟", "鏍",
        "鑸杩", "娓鍙", "鐗规湕", "鏆傛椂", "鍥介檯", "绾挎媺", "鎴愬", "璞佸厤", "缁忚锤", "鍙樺寲",
    ]
    frag_hits = sum(text.count(fragment) for fragment in mojibake_fragments)
    if frag_hits >= 2:
        try:
            forced = text.encode("gb18030", errors="ignore").decode("utf-8", errors="ignore")
            if forced and forced != text:
                text = forced
        except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
            pass

    candidates = [text]

    def add_candidate(src_encoding: str, dst_encoding: str, error_mode: str) -> None:
        try:
            transformed = text.encode(src_encoding, errors=error_mode).decode(dst_encoding, errors=error_mode)
            if transformed:
                candidates.append(transformed)
        except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
            return

    for src in ("latin1", "cp1252"):
        for dst in ("utf-8", "gb18030"):
            add_candidate(src, dst, "strict")
            add_candidate(src, dst, "ignore")

    # 逆向修复：文本本身已是“GBK误解码后的乱码汉字”时，尝试回转到 UTF-8
    for src in ("gbk", "gb18030"):
        add_candidate(src, "utf-8", "ignore")

    best = max(candidates, key=_text_quality_score)
    return best


def _is_readable_text(text: str) -> bool:
    cleaned = _to_text(text)
    if not cleaned:
        return False
    if "�" in cleaned:
        return False
    if _looks_like_mojibake(cleaned):
        return False

    length = max(len(cleaned), 1)
    cjk_count = sum(1 for ch in cleaned if "\u4e00" <= ch <= "\u9fff")
    suspicious_set = {"Ã", "Â", "Ð", "Ñ", "å", "ä", "ç", "è", "é", "ï", "ö", "ü", "æ", "œ", "¤", "¦", "±", "¼", "½", "¿"}
    suspicious_count = sum(1 for ch in cleaned if ch in suspicious_set)
    control_count = sum(1 for ch in cleaned if (0 <= ord(ch) < 32 and ch not in "\t\n\r") or (127 <= ord(ch) <= 159))

    gbk_mojibake_chars = set("鐨鍦鍥鍙鍚鍒鍔鍩鍥鏃鏄鏉鏋楠彂灞曡涓氶噺鏈鏂版崯鎶樼瓑閫氶亾杞ㄨ澶囧競璇璁鍏鍏憡鎴簤娌璧讹紵缃戝瀹樻柟璐﹀彿")
    gbk_mojibake_count = sum(1 for ch in cleaned if ch in gbk_mojibake_chars)

    cjk_ratio = cjk_count / length
    suspicious_ratio = suspicious_count / length
    control_ratio = control_count / length
    gbk_mojibake_ratio = gbk_mojibake_count / length

    if control_ratio > 0:
        return False
    if suspicious_ratio > 0.08:
        return False
    if gbk_mojibake_ratio > 0.22 and cjk_ratio > 0.5:
        return False
    if cjk_ratio < 0.25:
        return False
    return _text_quality_score(cleaned) >= 40


def _is_complete_title(text: str) -> bool:
    title = _to_text(text)
    if not title:
        return False
    if _is_noise_title(title):
        return False
    if "..." in title or "…" in title:
        return False
    if title[0] in "。！？,，:：;；、·":
        return False
    if title[-1] in "，,:：;；、(（《[【":
        return False
    if len(title) < 10:
        return False
    return True


def _is_noise_title(text: str) -> bool:
    title = _to_text(text)
    if not title:
        return True

    noise_prefix = (
        "来源", "特别声明", "打开APP", "打开网易", "责任编辑", "编辑", "作者", "·", "原标题", "声明"
    )
    noise_contains = (
        "优质财经领域创作", "点击底部", "即将网页分至朋友圈", "网易媒体平台", "仅代表该作者",
        "本文来源", "免责声明", "打开客户端", "下载APP", "分享至", "扫码下载",
        "仅提供信息发布平台", "展商推介", "莅临", "展位",
    )

    if title.startswith(noise_prefix):
        return True
    if any(token in title for token in noise_contains):
        return True

    punctuation_count = sum(1 for ch in title if ch in "，。！？；：,.!?;:、·()（）【】[]《》")
    if punctuation_count / max(len(title), 1) > 0.35:
        return True

    return False


def _extract_title_from_content(content: Any) -> str:
    body = _to_text(content)
    if not body:
        return ""

    for line in body.splitlines():
        candidate = _to_text(line)
        if not candidate:
            continue

        sentence_parts = re.split(r"[。！？]", candidate)
        for part in sentence_parts:
            part = _to_text(part)
            if not part:
                continue
            if "|" in part:
                part = part.split("|", 1)[0].strip()
            part = " ".join(part.split())
            if _is_readable_text(part) and _is_complete_title(part):
                return part

    return ""


def _normalize_title(title: Any, content: Any = None) -> str:
    cleaned = _to_text(title)

    if cleaned:
        if "|" in cleaned:
            cleaned = cleaned.split("|", 1)[0].strip()
        if "_" in cleaned:
            left, right = cleaned.rsplit("_", 1)
            if any(k in right for k in ["网易", "搜狐", "新浪", "中新网", "腾讯", "央视"]):
                cleaned = left.strip()
            elif 1 <= len(right) <= 16:
                cleaned = left.strip()
        cleaned = cleaned.lstrip("·•-—_。！？,，:：;；、 ")
        cleaned = " ".join(cleaned.split())

    if _is_readable_text(cleaned) and _is_complete_title(cleaned):
        return cleaned

    fallback = _extract_title_from_content(content)
    if fallback:
        return fallback

    return cleaned


def _classify_source_type(origin: str) -> str:
    mapping = {
        "政府公告": "中央咨询",
        "新闻网站": "公共媒体",
        "网络论坛": "民生新闻",
        "自媒体": "民生新闻",
        "central": "中央咨询",
        "media": "公共媒体",
        "social": "民生新闻",
    }
    cleaned = _to_text(origin)
    return mapping.get(cleaned, "公共媒体")


def _country_from_text(text: str) -> str:
    text = _to_text(text)
    for country in COUNTRIES:
        if country in text:
            return country
    if "中东" in text:
        return "伊朗"
    return "未知"


def _normalize_time(value: Any) -> str:
    if value is None:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts = ts / 1000.0
        if ts <= 0:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

    text = _to_text(value)
    if not text:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if _looks_like_mojibake(text):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    text = text.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2})?)?", text):
        return text
    if re.fullmatch(r"\d{2}\.\d{2} \d{2}:\d{2}", text):
        return text
    if re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", text):
        return text

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _is_strategic(text: str) -> bool:
    return any(k in _to_text(text) for k in STRATEGIC_FILTER)

# 
# def _events_from_task(task: Dict[str, Any]) -> List[Dict[str, Any]]:
#     articles = task.get("articles", []) if isinstance(task.get("articles", []), list) else []
#     intel = task.get("intel", []) if isinstance(task.get("intel", []), list) else []
# 
#     title_country_map: Dict[str, str] = {}
#     for article in articles:
#         if _is_virtual_text(article.get("title"), article.get("source")):
#             continue
#         title = _to_text(article.get("title"))
#         if not title:
#             continue
#         country = _to_text(article.get("country")) or _country_from_text(title)
#         title_country_map[title] = country
# 
#     events: List[Dict[str, Any]] = []
# 
#     for intel_item in intel:
#         if _is_virtual_text(intel_item.get("title"), intel_item.get("source")):
#             continue
#         title = _normalize_title(intel_item.get("title"), intel_item.get("description"))
#         if not title or not _is_readable_text(title) or not _is_complete_title(title):
#             continue
#         source = _to_text(intel_item.get("source")) or "未知来源"
#         source_type = _to_text(intel_item.get("sourceType")) or "公共媒体"
#         level = _to_text(intel_item.get("level")) or ("STRATEGIC" if _is_strategic(title) else "TACTICAL")
#         time_text = _normalize_time(intel_item.get("time") or task.get("time"))
#         country = title_country_map.get(title) or _country_from_text(title)
# 
#         events.append(
#             {
#                 "event_name": title,
#                 "source": source,
#                 "source_type": source_type,
#                 "country": country,
#                 "time": time_text,
#                 "level": level,
#                 "info_type": _to_text(intel_item.get("info_type")) or _ai_classify_info_type(title, source, country),
#             }
#         )
# 
#     for article in articles:
#         if _is_virtual_text(article.get("title"), article.get("source")):
#             continue
#         title = _normalize_title(article.get("title"), article.get("description"))
#         if not title or not _is_readable_text(title) or not _is_complete_title(title):
#             continue
#         source = _to_text(article.get("source")) or "未知来源"
#         country = _to_text(article.get("country")) or _country_from_text(title)
#         time_text = _normalize_time(article.get("time") or task.get("time"))
# 
#         events.append(
#             {
#                 "event_name": title,
#                 "source": source,
#                 "source_type": "公共媒体",
#                 "country": country,
#                 "time": time_text,
#                 "level": "STRATEGIC" if _is_strategic(title) else "TACTICAL",
#                 "info_type": _to_text(article.get("info_type")) or _ai_classify_info_type(title, source, country),
#             }
#         )
# 
    # 去重：标题+来源+时间
#     unique_events: List[Dict[str, Any]] = []
#     seen = set()
#     for item in events:
#         key = (item.get("event_name"), item.get("source"), item.get("time"))
#         if key in seen:
#             continue
#         seen.add(key)
#         unique_events.append(item)
# 
#     return unique_events
# 
# 
# def _events_from_equipment_events() -> List[Dict[str, Any]]:
#     raw = _read_json_file(EQUIPMENT_EVENTS_FILE, default=[])
#     if not isinstance(raw, list):
#         return []
# 
#     events: List[Dict[str, Any]] = []
#     for item in raw:
#         if not isinstance(item, dict):
#             continue
#         title = _normalize_title(item.get("event_name") or item.get("title"), item.get("description"))
#         if not title or not _is_readable_text(title) or not _is_complete_title(title):
#             continue
#         source_data = item.get("source")
#         source = "未知来源"
#         if isinstance(source_data, dict):
#             source = _to_text(source_data.get("user") or source_data.get("platform")) or "未知来源"
#         elif source_data:
#             source = _to_text(source_data)
# 
#         origin = _to_text(item.get("origin"))
#         description = _to_text(item.get("description"))
#         location = _to_text(item.get("location"))
# 
#         events.append(
#             {
#                 "event_name": title,
#                 "source": source,
#                 "source_type": _classify_source_type(origin),
#                 "country": _country_from_text(f"{location}\n{title}\n{description}"),
#                 "time": _normalize_time(item.get("time") or item.get("crawled_at")),
#                 "level": "STRATEGIC" if _is_strategic(f"{title}\n{description}") else "TACTICAL",
#             }
#         )
# 
#     return events
# 
# 
# def _events_from_task_events_file(task_id: str) -> List[Dict[str, Any]]:
#     task_id_text = _to_text(task_id)
#     if not task_id_text:
#         return []
# 
#     file_path = TASK_EVENTS_DIR / f"{task_id_text}.json"
#     events = _read_json_file(file_path, default=[])
# 
#     return events
# 
# 
# def _raw_from_task_raw_file(task_id: str) -> List[Dict[str, Any]]:
#     task_id_text = _to_text(task_id)
#     if not task_id_text:
#         return []
# 
#     file_path = TASK_RAW_DIR / f"{task_id_text}.json"
#     raw = _read_json_file(file_path, default=[])
#     if not isinstance(raw, list):
#         return []
# 
#     rows: List[Dict[str, Any]] = []
#     seen = set()
#     for item in raw:
#         if not isinstance(item, dict):
#             continue
#         rid = _to_text(item.get("raw_id"))
#         title = _normalize_title(item.get("title"), item.get("content"))
#         if not rid or not title:
#             continue
#         if rid in seen:
#             continue
#         seen.add(rid)
# 
#         rows.append(
#             {
#                 "raw_id": rid,
#                 "task_id": task_id_text,
#                 "task_name": _to_text(item.get("task_name")),
#                 "keyword": _to_text(item.get("keyword")),
#                 "title": title,
#                 "content": _to_text(item.get("content")),
#                 "url": _to_text(item.get("url")),
#                 "source": _to_text(item.get("source")) or "未知来源",
#                 "origin": _to_text(item.get("origin")),
#                 "publish_time": _normalize_time(item.get("publish_time")),
#                 "crawled_at": _normalize_time(item.get("crawled_at")),
#             }
#         )
# 
#     return rows
# 
# 
# def _build_task_raw_items(
#     task_id: str,
#     title: Optional[str] = None,
#     keyword: Optional[str] = None,
#     source: Optional[str] = None,
#     readable_only: bool = True,
#     limit: int = 200,
# ) -> List[Dict[str, Any]]:
#     rows = _raw_from_task_raw_file(task_id)
# 
#     if readable_only:
#         rows = [x for x in rows if _is_readable_text(x.get("title"))]
# 
#     if title:
#         title_filter = title.strip()
#         if title_filter:
#             rows = [x for x in rows if title_filter in _to_text(x.get("title"))]
# 
#     if keyword:
#         keyword_filter = keyword.strip()
#         if keyword_filter:
#             rows = [
#                 x
#                 for x in rows
#                 if keyword_filter in _to_text(x.get("title"))
#                 or keyword_filter in _to_text(x.get("content"))
#                 or keyword_filter in _to_text(x.get("keyword"))
#             ]
# 
#     if source:
#         source_filter = source.strip()
#         if source_filter:
#             rows = [x for x in rows if source_filter in _to_text(x.get("source"))]
# 
#     return rows[:limit]
# 
# 
# def _load_tasks() -> List[Dict[str, Any]]:
#     tasks = _read_json_file(TASKS_FILE, default=[])
#     if isinstance(tasks, dict):
#         tasks = [tasks]
#     if not isinstance(tasks, list):
#         return []
#     normalized_tasks = [x for x in tasks if isinstance(x, dict)]
# 
#     cleaned = False
#     with crawl_state_lock:
#         is_running = bool(crawl_state.get("running"))
#         active_task_id = _to_text(crawl_state.get("task_id"))
# 
#     for task in normalized_tasks:
#         original_name = task.get("name")
#         normalized_name = _to_text(original_name)
#         if normalized_name != original_name:
#             task["name"] = normalized_name
#             cleaned = True
# 
#         original_keywords = task.get("keywords") if isinstance(task.get("keywords"), list) else []
#         normalized_keywords = [_to_text(item) for item in original_keywords]
#         if normalized_keywords != original_keywords:
#             task["keywords"] = normalized_keywords
#             cleaned = True
# 
#         original_subjects = task.get("subjects") if isinstance(task.get("subjects"), list) else []
#         normalized_subjects = [_to_text(item) for item in original_subjects]
#         if normalized_subjects != original_subjects:
#             task["subjects"] = normalized_subjects
#             cleaned = True
# 
#         original_time = task.get("time")
#         normalized_time = _normalize_time(original_time)
#         if normalized_time != original_time:
#             task["time"] = normalized_time
#             cleaned = True
# 
#         if "articles" in task or "intel" in task:
#             task.pop("articles", None)
#             task.pop("intel", None)
#             cleaned = True
# 
#         if _to_text(task.get("status")) == "running":
#             task_id = _to_text(task.get("id"))
#             if not is_running or (active_task_id and task_id != active_task_id):
#                 task["status"] = "failed"
#                 task["progress"] = 100
#                 cleaned = True
# 
#     if cleaned:
#         try:
#             with TASKS_FILE.open("w", encoding="utf-8") as f:
#                 json.dump(normalized_tasks, f, ensure_ascii=False, indent=2)
#         except OSError:
#             pass
# 
#     return normalized_tasks
# 
# 
# def _mark_task_failed(task_id: Optional[str], error_message: str) -> None:
#     task_id_text = _to_text(task_id)
#     if not task_id_text:
#         return
# 
#     tasks = _load_tasks()
#     updated = False
#     for task in tasks:
#         if _to_text(task.get("id")) != task_id_text:
#             continue
#         task["status"] = "failed"
#         task["progress"] = 100
#         task["last_error"] = _to_text(error_message)
#         updated = True
#         break
# 
#     if not updated:
#         return
# 
#     OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
#     with TASKS_FILE.open("w", encoding="utf-8") as f:
#         json.dump(tasks, f, ensure_ascii=False, indent=2)
# 
# 
# def _task_to_summary(task: Dict[str, Any]) -> Dict[str, Any]:
#     article_count = task.get("article_count") if isinstance(task.get("article_count"), int) else 0
#     intel_count = task.get("intel_count") if isinstance(task.get("intel_count"), int) else 0
#     return {
#         "id": task.get("id"),
#         "name": task.get("name"),
#         "status": task.get("status"),
#         "progress": task.get("progress"),
#         "depth": task.get("depth"),
#         "intensity": task.get("intensity"),
#         "frequency": task.get("frequency"),
#         "time": task.get("time"),
#         "keywords": task.get("keywords") if isinstance(task.get("keywords"), list) else [],
#         "subjects": task.get("subjects") if isinstance(task.get("subjects"), list) else [],
#         "article_count": article_count,
#         "intel_count": intel_count,
#     }
# 
# 
# def _latest_task(tasks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
#     if not tasks:
#         return None
    # 优先返回最近且包含事件文件的任务，避免前端因最新空任务出现空白
#     for task in reversed(tasks):
#         task_id = _to_text(task.get("id"))
#         if task_id and (TASK_EVENTS_DIR / f"{task_id}.json").is_file():
#             return task
#     return tasks[-1]
# 
# 
# def _find_task_by_id(task_id: str) -> Optional[Dict[str, Any]]:
#     tasks = _load_tasks()
#     for task in tasks:
#         if _to_text(task.get("id")) == _to_text(task_id):
#             return task
#     return None
# 
# 
# def _build_strategic_events(
#     task_id: Optional[str] = None,
#     keyword: Optional[str] = None,
#     source_type: Optional[str] = None,
#     level: Optional[str] = None,
#     limit: int = 200,
# ) -> List[Dict[str, Any]]:
#     tasks = _load_tasks()
# 
#     selected_task: Optional[Dict[str, Any]] = None
#     if task_id:
#         for t in tasks:
#             if _to_text(t.get("id")) == task_id:
#                 selected_task = t
#                 break
#     else:
#         selected_task = _latest_task(tasks)
# 
#     if selected_task:
#         selected_task_id = _to_text(selected_task.get("id"))
#         events = _events_from_task_events_file(selected_task_id)
#         if not events:
#             events = _events_from_task(selected_task)
#         if not events:
#             events = _events_from_equipment_events()
#     else:
#         events = _events_from_equipment_events()
# 
#     if keyword:
#         kw = keyword.strip()
#         if kw:
#             events = [
#                 x
#                 for x in events
#                 if kw in _to_text(x.get("event_name"))
#                 or kw in _to_text(x.get("source"))
#                 or kw in _to_text(x.get("country"))
#             ]
# 
#     if source_type:
#         source_filter = source_type.strip()
#         if source_filter:
#             events = [x for x in events if _to_text(x.get("source_type")) == source_filter]
# 
#     if level:
#         level_filter = level.strip().upper()
#         if level_filter:
#             events = [x for x in events if _to_text(x.get("level")).upper() == level_filter]
# 
#     return events[:limit]
# 
# 
# def _risk_level_from_event(level: str) -> str:
#     normalized = _to_text(level).upper()
#     if normalized == "STRATEGIC":
#         return "高"
#     return "中"
# 
# 
# def _risk_category_from_event(info_type: str, event_name: str) -> str:
#     info = _to_text(info_type)
#     title = _to_text(event_name)
# 
#     if info == "军事" or any(k in title for k in ["演训", "军演", "空袭", "导弹", "部署", "无人机", "舰", "战机"]):
#         return "军事行动"
#     if info == "经济" or any(k in title for k in ["制裁", "关税", "贸易", "投资", "金融", "通胀"]):
#         return "经济波动"
#     if info == "科技" or any(k in title for k in ["芯片", "网络安全", "AI", "人工智能"]):
#         return "科技竞争"
#     if info == "社会":
#         return "社会舆情"
#     if info == "国内":
#         return "国内政策"
#     if info == "地区":
#         return "地区安全"
#     if info == "国际":
#         return "国际关系"
#     return "综合风险"
# 
# 
# def _impact_type_from_event(level: str, info_type: str) -> str:
#     normalized_level = _to_text(level).upper()
#     normalized_info = _to_text(info_type)
#     if normalized_level == "STRATEGIC" or normalized_info in {"军事", "经济"}:
#         return "消极"
#     return "中性"
# 
# 
# def _analysis_sentiment_from_event(level: str) -> str:
#     normalized = _to_text(level).upper()
#     if normalized == "STRATEGIC":
#         return "支持强硬"
#     return "谨慎观望"
# 
# 
# def _analysis_driver_from_event(info_type: str, event_name: str) -> str:
#     category = _risk_category_from_event(info_type, event_name)
#     mapping = {
#         "军事行动": "军事安全动作",
#         "经济波动": "经济政策变化",
#         "科技竞争": "科技竞争升温",
#         "社会舆情": "舆论情绪变化",
#         "国内政策": "政策调整信号",
#         "地区安全": "地区局势变化",
#         "国际关系": "国际关系调整",
#         "综合风险": "多因素叠加",
#     }
#     return mapping.get(category, "多因素叠加")
# 
# 
# def _collect_topics_for_event(event: Dict[str, Any], task: Optional[Dict[str, Any]]) -> List[str]:
#     event_name = _to_text(event.get("event_name"))
#     source = _to_text(event.get("source"))
#     country = _to_text(event.get("country"))
#     source_type = _to_text(event.get("source_type"))
#     info_type = _to_text(event.get("info_type"))
# 
#     corpus = f"{event_name}\n{source}\n{country}\n{source_type}\n{info_type}"
#     candidates: List[str] = []
# 
#     if task:
#         keywords = task.get("keywords") if isinstance(task.get("keywords"), list) else []
#         subjects = task.get("subjects") if isinstance(task.get("subjects"), list) else []
#         for item in [*keywords, *subjects]:
#             text = _to_text(item)
#             if text and text in corpus:
#                 candidates.append(text)
# 
#     for item in [country, source_type, info_type]:
#         if item:
#             candidates.append(item)
# 
#     if any(k in event_name for k in ["演训", "军演", "部署", "空袭", "导弹"]):
#         candidates.append("军事行动")
#     if any(k in event_name for k in ["制裁", "关税", "贸易", "投资"]):
#         candidates.append("经济风险")
#     if any(k in event_name for k in ["芯片", "网络安全", "AI", "人工智能"]):
#         candidates.append("科技竞争")
# 
#     topics: List[str] = []
#     for topic in candidates:
#         if topic and topic not in topics:
#             topics.append(topic)
# 
#     if not topics:
#         topics = ["态势感知"]
# 
#     return topics[:8]
# 
# 
# def _format_event_summary(event: Dict[str, Any], task: Optional[Dict[str, Any]]) -> Dict[str, Any]:
#     event_name = _to_text(event.get("event_name"))
#     event_time = _to_text(event.get("time"))
#     level = _to_text(event.get("level"))
#     country = _to_text(event.get("country"))
#     source_type = _to_text(event.get("source_type"))
#     info_type = _to_text(event.get("info_type"))
# 
    # topics归纳更智能，优先关键词/主体、类型、国家、事件高频词
#     topics = []
#     if task:
#         for k in (task.get("keywords") or []):
#             if k and k in event_name and k not in topics:
#                 topics.append(k)
#         for s in (task.get("subjects") or []):
#             if s and s in event_name and s not in topics:
#                 topics.append(s)
#     for t in [info_type, country, source_type]:
#         if t and t not in topics:
#             topics.append(t)
#     for word in ["演训", "军演", "部署", "空袭", "导弹", "制裁", "贸易", "芯片", "AI", "网络安全"]:
#         if word in event_name and word not in topics:
#             topics.append(word)
#     if not topics:
#         topics = ["态势感知"]
#     topics = topics[:8]
# 
    # risk/impact/analysis字段更贴合业务
#     risk_level = "高" if level.upper() == "STRATEGIC" else "中"
#     risk_category = _risk_category_from_event(info_type, event_name)
#     impact_type = "消极" if risk_level == "高" else "中性"
#     sentiment = "支持强硬" if risk_level == "高" else "谨慎观望"
#     driver = _analysis_driver_from_event(info_type, event_name)
#     trend = impact_type
# 
#     return {
#         "event": {
#             "name": event_name,
#             "time": event_time,
#             "is_key": risk_level == "高",
#         },
#         "source": {
#             "type": source_type or "公共媒体",
#             "location": country or "未知",
#         },
#         "risk": {
#             "level": risk_level,
#             "category": risk_category,
#         },
#         "impact": {
#             "type": impact_type,
#         },
#         "analysis": {
#             "sentiment": sentiment,
#             "driver": driver,
#             "trend": trend,
#         },
#         "topics": topics,
#     }
# 
# 
# def _run_crawler_in_background(payload: CrawlStartRequest) -> None:
#     with crawl_state_lock:
#         crawl_state["running"] = True
#         crawl_state["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         crawl_state["finished_at"] = None
#         crawl_state["last_error"] = None
# 
#     try:
        # StrategicIntelligenceCrawler is defined above in this file
# 
#         crawler = StrategicIntelligenceCrawler(
#             output_dir=payload.output_dir,
#             task_name=payload.task_name,
#             task_keywords=payload.task_keywords,
#             task_subjects=payload.task_subjects,
#             task_depth=payload.task_depth,
#             task_intensity=payload.task_intensity,
#             crawl_frequency=payload.frequency,
#         )
# 
#         with crawl_state_lock:
#             crawl_state["task_id"] = crawler.task.get("id")
#             crawl_state["task_name"] = crawler.task.get("name")
# 
#         crawler.run()
#         _persist_ai_enriched_task(crawler.task.get("id"))
#     except BaseException as e:  # <--- 注意这里改成了 BaseException！
#         import traceback
#         traceback.print_exc()  
#         task_id = None
# 
# 
#         with crawl_state_lock:
#             task_id = crawl_state.get("task_id")
#         _mark_task_failed(task_id, str(e))
#         with crawl_state_lock:
#             crawl_state["last_error"] = str(e)
#     finally:
#         with crawl_state_lock:
#             crawl_state["running"] = False
#             crawl_state["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
# 
# 
# def _wait_for_task_id(timeout_seconds: float = 5.0, interval_seconds: float = 0.05) -> Dict[str, Any]:
#     deadline = time.monotonic() + max(timeout_seconds, 0.0)
#     snapshot: Dict[str, Any] = {}
# 
#     while time.monotonic() <= deadline:
#         with crawl_state_lock:
#             snapshot = dict(crawl_state)
#             if _to_text(snapshot.get("task_id")):
#                 return snapshot
#         time.sleep(max(interval_seconds, 0.01))
# 
#     with crawl_state_lock:
#         return dict(crawl_state)
# 
# 
# app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "public")), name="assets")
# 
# @app.get("/{filename}.json", include_in_schema=False)
# async def get_json_file(filename: str):
#     if filename == "strategic_events":
#         return _build_strategic_events(limit=200)
# 
    # 拼接完整的文件路径
#     file_path = OUTPUT_DIR / f"{filename}.json"
#     
    # 检查文件是否存在
#     if not file_path.is_file():
        # 如果文件不存在，返回404错误
#         raise HTTPException(status_code=404, detail="JSON file not found")
#     
#     return FileResponse(
#         path=str(file_path),
#         media_type='application/json',
#         filename=f"{filename}.json"  # 这会影响浏览器下载时的默认文件名
#     )
# 
# 
# @app.get("/{filename}.csv", include_in_schema=False)
# async def get_csv_file(filename: str):
    # 拼接完整的文件路径
#     file_path = INPUT_DIR / f"{filename}.csv"
#     
    # 检查文件是否存在
#     if not file_path.is_file():
        # 如果文件不存在，返回404错误
#         raise HTTPException(status_code=404, detail="CSV file not found")
#     
#     return FileResponse(
#         path=str(file_path),
#         media_type='text/csv',
#         filename=f"{filename}.csv"
#     )
# 
# 
# @app.get("/strategic_events.json", include_in_schema=False)
# async def strategic_events(
#     task_id: Optional[str] = Query(default=None),
#     keyword: Optional[str] = Query(default=None),
#     source_type: Optional[str] = Query(default=None),
#     level: Optional[str] = Query(default=None),
#     limit: int = Query(default=200, ge=1, le=2000),
# ):
#     return _build_strategic_events(
#         task_id=task_id,
#         keyword=keyword,
#         source_type=source_type,
#         level=level,
#         limit=limit,
#     )
# 
# 
# @app.post("/api/start_crawl", include_in_schema=False)
# async def start_crawl(payload: Optional[CrawlStartRequest] = None):
#     req = payload or CrawlStartRequest()
# 
#     with crawl_state_lock:
#         if crawl_state.get("running"):
#             return {
#                 "success": False,
#                 "message": "已有采集任务正在运行",
#                 "state": crawl_state,
#             }
# 
#     thread = threading.Thread(target=_run_crawler_in_background, args=(req,), daemon=True)
#     thread.start()
# 
    # 等待任务 ID 注入，避免前端拿到空 task_id
#     state_snapshot = _wait_for_task_id(timeout_seconds=5.0)
# 
#     return {
#         "success": True,
#         "message": "采集任务已启动",
#         "task": {
#             "task_id": state_snapshot.get("task_id"),
#             "task_name": req.task_name,
#             "status": "running",
#         },
#         "state": state_snapshot,
#     }
# 
# 
# @app.get("/api/crawl_status", include_in_schema=False)
# async def crawl_status():
#     with crawl_state_lock:
#         state_snapshot = dict(crawl_state)
# 
#     tasks = _load_tasks()
#     latest = _latest_task(tasks)
# 
#     return {
#         "success": True,
#         "state": state_snapshot,
#         "latest_task": latest,
#     }
# 
# 
# @app.get("/api/tasks", include_in_schema=False)
# async def list_tasks(limit: int = Query(default=20, ge=1, le=200)):
#     tasks = _load_tasks()
#     return tasks[-limit:]
# 
# 
# @app.get("/api/opinion/tasks", summary="Get Current Task List")
# async def get_current_task_list(limit: int = Query(default=50, ge=1, le=500)):
#     """
#     1) GET 获取当前运行任务列表
#     {} -> {tasks: [...]}（仅任务列表）
#     """
#     tasks = _load_tasks()
#     tasks = [_task_to_summary(task) for task in tasks[-limit:]]
# 
#     return {
#         "success": True,
#         "tasks": tasks,
#         "total": len(tasks),
#     }
# 
# 
# @app.post("/api/opinion/tasks", summary="Create Opinion Task")
# async def create_opinion_task(payload: CreateOpinionTaskRequest):
#     """
#     2) POST 创建舆情感知任务
#     {任务名称、关键词、主体...} -> {task_id}
#     """
#     task_name = payload.task_name
#     task_keywords = payload.keywords
#     task_subjects = payload.subjects
# 
#     req = CrawlStartRequest(
#         task_name=task_name,
#         task_keywords=task_keywords,
#         task_subjects=task_subjects,
#         task_depth=payload.depth,
#         task_intensity=payload.intensity,
#         output_dir=payload.output_dir,
#         frequency=payload.frequency,
#     )
# 
#     with crawl_state_lock:
#         if crawl_state.get("running"):
#             return {
#                 "success": False,
#                 "message": "已有采集任务正在运行",
#                 "state": dict(crawl_state),
#             }
# 
#     thread = threading.Thread(target=_run_crawler_in_background, args=(req,), daemon=True)
#     thread.start()
# 
    # 等待任务 ID 注入，避免返回空 task_id
#     state_snapshot = _wait_for_task_id(timeout_seconds=5.0)
# 
#     return {
#         "success": True,
#         "task_id": state_snapshot.get("task_id"),
#         "task_name": task_name,
#         "message": "舆情感知任务已创建并启动",
#     }
# 
# 
# @app.post("/api/opinion/events", summary="Get Events By Task")
# async def get_events_by_task(payload: TaskEventsRequest):
#     """
#     3) POST 根据任务ID获取感知事件列表
#     {task_id} -> {events: [...]}
#     """
#     task = _find_task_by_id(payload.task_id)
#     if not task:
#         raise HTTPException(status_code=404, detail=f"任务不存在: {payload.task_id}")
# 
#     return _events_from_task_events_file(payload.task_id)[:payload.limit]
# 
# @app.post("/api/opinion/raw", summary="Get Raw Streams By Task")
# async def get_raw_streams_by_task(payload: TaskRawRequest):
#     """
#     4) POST 根据任务ID获取原始信息流
#     {task_id, limit} -> {raw_items: [...]}
#     """
#     task = _find_task_by_id(payload.task_id)
#     if not task:
#         raise HTTPException(status_code=404, detail=f"任务不存在: {payload.task_id}")
# 
#     rows = _raw_from_task_raw_file(payload.task_id)[: payload.limit]
# 
#     return {
#         "success": True,
#         "task_id": payload.task_id,
#         "task_name": task.get("name"),
#         "raw_items": rows,
#         "total": len(rows),
#     }
# 
# 
# @app.get("/inner-events", include_in_schema=False)
# async def inner_events_page():
#     return FileResponse(str(WEB_DIR / "index.html"))
# 
# 
# @app.get("/events-net", include_in_schema=False)
# async def events_network_page():
    return FileResponse(str(WEB_DIR / "index.html"))




# 大屏贝叶斯批量统计接口
@app.get("/api/model/risk_statistics")
def get_bayes_risk_stat(current_user=Depends(get_current_user)):  # noqa: ARG001
    return {
        "topSourceIps": [
            {"name": "110.25.33.12", "score": 96},
            {"name": "45.89.12.56", "score": 88},
            {"name": "192.168.1.33", "score": 84},
        ],
        "attackTrend": [
            {"label":"00点","value":8,"blocked":3,"sources":2,"primaryType":"暴力破解"},
            {"label":"02点","value":15,"blocked":6,"sources":4,"primaryType":"DDoS攻击"},
        ],
        "attackTypes": [
            {"label":"暴力破解","value":35,"color":"#ff7b72"},
            {"label":"DDoS攻击","value":45,"color":"#5ba6ff"},
            {"label":"异常访问","value":20,"color":"#53e5c8"},
        ],
        "sourceMap": {
            "china": {
                "points": [
                    {"label":"北京","x":12,"y":-14,"value":"44次","delay":0.6},
                    {"label":"上海","x":12,"y":-12,"value":"38次","delay":1.2},
                ]
            }
        },
        "model_metric":{"accuracy":0.86,"f1":0.84,"recall":0.82}
    }


app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=12312)
