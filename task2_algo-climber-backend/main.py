import os
import sys
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
from multi_source_crawler import MultiSourceCrawler

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

# 导入配置
from config import (
    CRAWLER_CONFIG,
    DEEPSEEK_CONFIG,
    DIFY_CONFIG,
    TEXT_SPLITTER_CONFIG,
    EVENT_EXTRACTION_TEMPLATE,
    KNOWLEDGE_BASE_CONFIG,
    INTERNAL_IMPACT_TEMPLATE,
    DYNAMIC_KEYWORDS_TEMPLATE,
    INNER_EVENT_EXTRACTION_TEMPLATE
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

        if files:
            data["files"] = files

        logger.debug("调用 Dify API, response_mode=%s", response_mode)
        try:
            response = self.session.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=60
            )
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Dify API 请求失败")
            raise

        if response_mode == "streaming":
            result = ""
            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    data_json = json.loads(data_str)
                    if "answer" in data_json:
                        result += data_json["answer"]
                except json.JSONDecodeError:
                    logger.debug("streaming chunk 非法 JSON，已跳过")
                    continue
            return result

        result = response.json()
        if "answer" in result:
            logger.debug("Dify 响应成功")
            return result["answer"]
        if "message" in result:
            return result["message"]

        logger.warning("Dify 响应格式异常: %s", result)
        return str(result)



# 知识库客户端（保持原有逻辑，适配新端口）
class KnowledgeBaseClient:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key
        self.session = requests.Session()

    def query(self, query_text: str) -> Dict[str, Any]:
        data = {"query": query_text, "top_k": 3}
        try:
            res = self.session.post(self.api_url, json=data, timeout=10)
            res.raise_for_status()
            return res.json()
        except requests.RequestException:
            logger.exception("KnowledgeBase query request failed: %s", query_text)
            raise
        except ValueError:
            logger.exception("KnowledgeBase query json decode failed: %s", query_text)
            raise

# 战略过滤关键词（与前端保持一致）

# --- 核心爬虫类：已适配战略推演前端 ---


class EventBase(BaseModel):
    name: str
    time: Optional[str] = Field(default=None)
    is_key: bool = Field(default=False)


class SourceBase(BaseModel):
    type: Optional[str] = Field(default=None)
    location: Optional[str] = Field(default=None)


class RiskBase(BaseModel):
    level: Optional[str] = Field(default=None)
    category: Optional[str] = Field(default=None)


class ImpactBase(BaseModel):
    type: Optional[str] = Field(default=None)


class AnalysisBase(BaseModel):
    sentiment: Optional[str] = Field(default=None)
    driver: Optional[str] = Field(default=None)
    trend: Optional[str] = Field(default=None)


class ExtractEvent(BaseModel):
    event: EventBase
    source: Optional[SourceBase] = Field(default_factory=SourceBase)
    risk: Optional[RiskBase] = Field(default_factory=RiskBase)
    impact: Optional[ImpactBase] = Field(default_factory=ImpactBase)
    analysis: Optional[AnalysisBase] = Field(default_factory=AnalysisBase)
    topics: List[str] = Field(default_factory=list)


class StrategicIntelligenceCrawler:

    def __init__(self, 
        output_dir="output",
        task_name="默认任务",
        task_keywords=None,
        task_subjects=None,
        task_depth=1000,
        task_intensity=70,
        crawl_frequency="高"  
    ) -> None:
      
        self.config = copy.deepcopy(CRAWLER_CONFIG)
        # --- 2. 频率控制核心逻辑 ---
        delay_ranges = self.config.get("delay_ranges", {"高": (3, 8)})
        self.delay_range = delay_ranges.get(crawl_frequency, delay_ranges["高"]) 
        self.config["delay_range"] = self.delay_range  # 覆盖配置，传给底层
        
        assert len(task_keywords) > 0, "必须提供至少一个关键词"
        self.keywords = task_keywords
            
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        task_id = f"t-{int(time.time())}"
        # 定义输出路径
        self.output_file = os.path.join(self.output_dir, "task_events", f"{task_id}.json")
        self.raw_events_file = os.path.join(self.output_dir, "task_raw", f"{task_id}.json")
        self.tasks_file = os.path.join(self.output_dir, "tasks.json")

        # 确保存储事件和原始数据的子文件夹存在
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        os.makedirs(os.path.dirname(self.raw_events_file), exist_ok=True)

        # 初始化 Dify AI 引擎
        self.llm = DifyClient(
            api_url=DIFY_CONFIG["api_url"],
            api_key=DIFY_CONFIG["api_key"],
            user=DIFY_CONFIG["user"]
        )

        # 初始化知识库
        self.kb_client = KnowledgeBaseClient(
            api_url=KNOWLEDGE_BASE_CONFIG["api_url"],
            api_key=KNOWLEDGE_BASE_CONFIG["api_key"]
        )

        # 任务信息
        self.task = {
            "id": task_id,
            "name": task_name,
            "status": "running",
            "progress": 0,
            "depth": task_depth,
            "intensity": task_intensity,
            "frequency": crawl_frequency,  # <--- 3. 记录进任务状态
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "keywords": self.keywords,
            "subjects": task_subjects if task_subjects else [],
            "articles": [],
            "intel": []
        }

        self.all_events = []
        self.raw_events: List[Dict[str, Any]] = []

        self.fail_fast = bool(self.config.get("fail_fast", True))

        # 真实多源爬虫
        crawler_cfg = self.config
        crawler_cfg["keywords"] = self.keywords
        self.multi_crawler = MultiSourceCrawler(crawler_cfg)

        self.save_data()

    def _stable_id(self, prefix: str, *parts: str) -> str:
        raw = "|".join([(p or "").strip() for p in parts])
        h = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
        return f"{prefix}-{h}"

    def extract_events(self, raw_text: str, publish_time: Optional[str] = None) -> List[ExtractEvent]:
        """调用 AI 提取符合前端结构的事件"""
        prompt = EVENT_EXTRACTION_TEMPLATE.replace("{content}", raw_text)
        response_text = self.llm.chat(query=prompt)
        logger.debug("LLM 原始响应:", response_text)  # 调试输出原始响应
        content = re.match(r"```json\s*(.*?)\s*```", response_text, re.S)
        events = pydantic.TypeAdapter(List[ExtractEvent]).validate_python(json.loads(content.group(1))) if content else []
        normalized_publish_time = str(publish_time).strip() if publish_time is not None else ""
        if normalized_publish_time:
            for item in events:
                if item.event and not (item.event.time or "").strip():
                    item.event.time = normalized_publish_time
        logger.debug("提取事件: %s", events)
        return events

    def _get_real_data(self, keyword: str) -> bool:
        logger.info("fetching real data by crawler keyword=%s", keyword)

        raw_events: List[Dict[str, Any]] = []
        rss_events = self.multi_crawler.crawl_via_rss(keyword)
        if rss_events:
            raw_events.extend(rss_events)

        so_events = self.multi_crawler.crawl_via_chinaso(keyword, pages=3)
        if so_events:
            raw_events.extend(so_events)

        if not raw_events:
            logger.warning("关键词[%s]未抓到真实数据", keyword)
            return False

        logger.info("关键词[%s]抓取到真实事件 %d 条", keyword, len(raw_events))

        for ev in raw_events:
            ev['task_id'] = self.task["id"]
            ev['raw_id'] = self._stable_id("raw", ev.get("title", ""), ev.get("link", ""))

            self.raw_events.append(ev)
            self.save_raw()

            try:
                cur_events = self.extract_events(
                    ev.get("title", "") + "\n" + ev.get("summary", ""),
                    publish_time=ev.get("publish_time") or ev.get("time"),
                )
                cur_events = [ev.model_dump() for ev in cur_events]
                self.all_events.extend(cur_events)
                logger.info("提取事件[%d] | 当前事件总数=%d", len(cur_events), len(self.all_events))
                self.save_events()
            except Exception as exc:
                logger.warning("原始信息已保存，但事件提纯失败: %s", exc)
                continue

        self.save_data()
        logger.info("真实数据处理完成")
        return True

    def crawl_weibo(self):
        """按关键词抓取真实多源数据"""
        if not self.config.get("enable_weibo", True):
            logger.info("外部抓取已禁用")
            return

        logger.info("开始抓取战略情报，关键词数=%d", len(self.keywords))
        total_keywords = len(self.keywords)

        for i, kw in enumerate(self.keywords):
            logger.info("检索关键词: %s", kw)
            before_raw_count = len(self.raw_events)
            before_event_count = len(self.all_events)
            
            self._get_real_data(kw)
            
            self.task["progress"] = min(100, (i + 1) / total_keywords * 100)
            self.save_data()
            
            logger.info(
                "关键词[%s]处理完成 | progress=%.2f%% | 新增原始=%d | 新增提纯=%d",
                kw,
                self.task["progress"],
                len(self.raw_events) - before_raw_count,
                len(self.all_events) - before_event_count,
            )
            
            # --- 修改这里：使用动态算出的延迟范围 ---
            sleep_time = random.uniform(*self.delay_range)
            logger.info("触发频率控制，休眠 %.2f 秒...", sleep_time)
            time.sleep(sleep_time)

    def save_data(self):
        """保存为前端可直接读取的 JSON"""
        tasks = []
        try:
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                tasks = json.load(f)
                if isinstance(tasks, dict):
                    tasks = [tasks]
        except (FileNotFoundError, json.JSONDecodeError):
            tasks = []

        # 将历史残留 running（同名旧任务）标记为 failed，避免前端长期显示“运行中”
        for t in tasks:
            if t.get("status") == "running" and t.get("id") != self.task["id"]:
                t["status"] = "failed"
            t.pop("articles", None)
            t.pop("intel", None)

        persist_task = dict(self.task)
        persist_task.pop("articles", None)
        persist_task.pop("intel", None)
        persist_task["article_count"] = len(self.raw_events)
        persist_task["intel_count"] = len(self.all_events)

        # upsert 当前任务
        updated = False
        for i, t in enumerate(tasks):
            if t.get("id") == self.task["id"]:
                tasks[i] = persist_task
                updated = True
                break
        if not updated:
            tasks.append(persist_task)

        # 控制文件体积，保留最近 100 条
        tasks = tasks[-100:]

        with open(self.tasks_file, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)

        self.save_raw()
        self.save_events()

        logger.info(
            "任务已保存: %s | progress=%.2f%% | articles=%d | intel=%d",
            self.task["name"], self.task["progress"], len(self.task["articles"]), len(self.task["intel"])
        )

    def save_raw(self):
        with open(self.raw_events_file, "w", encoding="utf-8",) as f:
            json.dump(self.raw_events, f, ensure_ascii=False, indent=2)
    
    def save_events(self):
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(self.all_events, f, ensure_ascii=False, indent=2)

    def run(self):
        """启动主流程"""
        logger.info("系统启动")
        self.crawl_weibo()
        self.task["status"] = "completed"
        self.task["progress"] = 100
        self.save_data()
        logger.info("任务完成")
        logger.info("共收集战略情报: %d 条", len(self.task["intel"]))
        logger.info("结果已保存至: %s", self.output_file)
        logger.info("任务信息已保存至: %s", self.tasks_file)

if __name__ == "__main__":
    try:
        crawler = StrategicIntelligenceCrawler(
    output_dir="output",
    task_name="默认任务",
    task_keywords=["网络安全", "态势感知"]
)
        crawler.run()
    except Exception:
        logger.exception("程序运行失败")
        raise
