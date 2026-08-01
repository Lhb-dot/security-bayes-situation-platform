import os
import time
import json
import random
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Callable, Tuple
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from bs4 import BeautifulSoup
import feedparser

# 导入配置
from app.config import CRAWLER_CONFIG

class MultiSourceCrawler:
    def __init__(self, config=None):
        """
        初始化多源爬虫
        
        Args:
            config: 爬虫配置字典，如果为None则使用默认配置
        """
        if config is None:
            config = CRAWLER_CONFIG
            
        self.keywords = config.get("keywords", [])
        self.max_pages = config.get("max_pages", 50)
        self.output_file = "multi_source_events.json"
        self.csv_file = "multi_source_events.csv"
        self.headers = config.get("headers", {})
        self.cookies = config.get("cookies", "")
        self.delay_range = config.get("delay_range", (1, 3))
        self.use_proxy = config.get("use_proxy", False)
        self.proxies = config.get("proxies", {})
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 5)
        # 新增：RSS源（推荐使用，较为稳定）。格式：[{"name":"X", "url":"https://...rss"}]
        self.rss_sources: List[Dict[str, str]] = config.get("rss_sources", [])
        # 控制是否启用旧的站点解析（默认关闭，原因：频繁改版/反爬导致不稳定）
        self.enable_legacy_html_parsers: bool = config.get("enable_legacy_html_parsers", False)
        # ChinaSo 抓取开关（当RSS为空或抓取为0时，自动回退使用）
        self.enable_chinaso_fallback: bool = True
        
        # 存储所有爬取的数据
        self.all_events = []
        
        # 创建会话对象，设置重试策略
        self.session = self._create_session()
        # 确保有可用UA
        if 'User-Agent' not in self.session.headers or not self.session.headers.get('User-Agent'):
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            })
        
        # 移除遗留站点配置，统一通过ChinaSo获取链接
        self.news_sources = []
        self.gov_sources = []
        self.forum_sources = []

    def _text_quality_score(self, text: str) -> int:
        if not text:
            return -10000
        length = max(len(text), 1)
        cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        suspicious = {"Ã", "Â", "Ð", "Ñ", "å", "ä", "ç", "è", "é", "ï", "ö", "ü", "æ", "œ", "¤", "¦", "±", "¼", "½", "¿"}
        suspicious_count = sum(1 for ch in text if ch in suspicious)
        control_count = sum(1 for ch in text if (0 <= ord(ch) < 32 and ch not in "\t\n\r") or (127 <= ord(ch) <= 159))
        replacement_count = text.count("�")
        printable_count = sum(1 for ch in text if ch.isprintable() or ch in "\t\n\r")
        printable_ratio = int((printable_count / length) * 100)
        return cjk_count * 8 + printable_ratio - suspicious_count * 6 - control_count * 12 - replacement_count * 10

    def _clean_text(self, value: Any) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            return ""

        candidates = [text]

        def add_candidate(src_encoding: str, dst_encoding: str, error_mode: str) -> None:
            try:
                transformed = text.encode(src_encoding, errors=error_mode).decode(dst_encoding, errors=error_mode)
                if transformed:
                    candidates.append(transformed)
            except Exception:
                return

        for src in ("latin1", "cp1252"):
            for dst in ("utf-8", "gb18030"):
                add_candidate(src, dst, "ignore")

        for src in ("gbk", "gb18030"):
            add_candidate(src, "utf-8", "ignore")

        best = max(candidates, key=self._text_quality_score)
        return best.strip()

    def _decode_response_text(self, response: requests.Response) -> str:
        raw = response.content or b""
        if not raw:
            return ""

        candidate_encodings = []
        if response.encoding:
            candidate_encodings.append(response.encoding)
        if response.apparent_encoding:
            candidate_encodings.append(response.apparent_encoding)
        candidate_encodings.extend(["utf-8", "gb18030", "gbk"])

        decoded_candidates = []
        for enc in dict.fromkeys(candidate_encodings):
            try:
                decoded = raw.decode(enc)
                if decoded:
                    decoded_candidates.append(decoded)
            except Exception:
                continue

        if not decoded_candidates:
            return response.text

        best = max(decoded_candidates, key=self._text_quality_score)
        return self._clean_text(best)
    
    def _create_session(self) -> requests.Session:
        """创建带有重试机制的会话对象"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        session.headers.update(self.headers)
        
        if self.cookies:
            if isinstance(self.cookies, str):
                cookie_dict = {}
                for item in self.cookies.split(';'):
                    if '=' in item:
                        key, value = item.strip().split('=', 1)
                        cookie_dict[key] = value
                session.cookies.update(cookie_dict)
            elif isinstance(self.cookies, dict):
                session.cookies.update(self.cookies)
        
        if self.use_proxy and self.proxies:
            session.proxies.update(self.proxies)
        
        return session
    
    def crawl_news_websites(self, keyword: str, max_pages: int = 5) -> List[Dict[str, Any]]:
        return []
    
    def _crawl_people_news(self, keyword: str, max_pages: int) -> List[Dict[str, Any]]:
        """爬取人民网新闻"""
        events = []
        
        for page in range(1, max_pages + 1):
            try:
                url = "http://search.people.cn/search-platform/front/search"
                params = {
                    "keyword": keyword,
                    "pageNo": page,
                    "pageSize": 20,
                    "hasTitle": True,
                    "hasContent": True,
                    "sortType": 2
                }
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                if data.get("code") == 200 and "data" in data:
                    records = data["data"].get("records", [])
                    
                    for record in records:
                        event = {
                            "id": f"people_{record.get('id', '')}",
                            "title": record.get("title", ""),
                            "content": record.get("content", ""),
                            "url": record.get("url", ""),
                            "publish_time": record.get("publishTime", ""),
                            "source": "人民网",
                            "keyword": keyword,
                            "origin": "news_website",
                            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        events.append(event)
                
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"爬取人民网第 {page} 页时发生错误: {e}")
                continue
        
        return events
    
    def _crawl_xinhua_news(self, keyword: str, max_pages: int) -> List[Dict[str, Any]]:
        """爬取新华网新闻"""
        events = []
        
        for page in range(1, max_pages + 1):
            try:
                url = "http://www.xinhuanet.com/search.htm"
                params = {
                    "keyword": keyword,
                    "page": page
                }
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                news_items = soup.find_all("div", class_="news-item")
                
                for item in news_items:
                    title_elem = item.find("h3")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.find("a")
                        url = link.get("href") if link else ""
                        
                        content_elem = item.find("p", class_="summary")
                        content = content_elem.get_text(strip=True) if content_elem else ""
                        
                        time_elem = item.find("span", class_="time")
                        publish_time = time_elem.get_text(strip=True) if time_elem else ""
                        
                        event = {
                            "id": f"xinhua_{hash(url)}",
                            "title": title,
                            "content": content,
                            "url": url,
                            "publish_time": publish_time,
                            "source": "新华网",
                            "keyword": keyword,
                            "origin": "news_website",
                            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        events.append(event)
                
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"爬取新华网第 {page} 页时发生错误: {e}")
                continue
        
        return events
    
    def _crawl_jjckb_news(self, keyword: str, max_pages: int) -> List[Dict[str, Any]]:
        """爬取经济参考报新闻"""
        events = []
        
        for page in range(1, max_pages + 1):
            try:
                url = "http://www.jjckb.cn/search"
                params = {
                    "keyword": keyword,
                    "page": page
                }
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                news_items = soup.find_all("div", class_="news-item")
                
                for item in news_items:
                    title_elem = item.find("h3")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.find("a")
                        url = link.get("href") if link else ""
                        
                        content_elem = item.find("p", class_="summary")
                        content = content_elem.get_text(strip=True) if content_elem else ""
                        
                        time_elem = item.find("span", class_="time")
                        publish_time = time_elem.get_text(strip=True) if time_elem else ""
                        
                        event = {
                            "id": f"jjckb_{hash(url)}",
                            "title": title,
                            "content": content,
                            "url": url,
                            "publish_time": publish_time,
                            "source": "经济参考报",
                            "keyword": keyword,
                            "origin": "news_website",
                            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        events.append(event)
                
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"爬取经济参考报第 {page} 页时发生错误: {e}")
                continue
        
        return events
    
    def crawl_government_announcements(self, keyword: str, max_pages: int = 5) -> List[Dict[str, Any]]:
        return []
    
    def _crawl_gov_announcements(self, keyword: str, max_pages: int) -> List[Dict[str, Any]]:
        """爬取中国政府网公告"""
        events = []
        
        for page in range(1, max_pages + 1):
            try:
                url = "http://www.gov.cn/search.htm"
                params = {
                    "keyword": keyword,
                    "page": page
                }
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                announcement_items = soup.find_all("div", class_="announcement-item")
                
                for item in announcement_items:
                    title_elem = item.find("h3")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.find("a")
                        url = link.get("href") if link else ""
                        
                        content_elem = item.find("p", class_="summary")
                        content = content_elem.get_text(strip=True) if content_elem else ""
                        
                        time_elem = item.find("span", class_="time")
                        publish_time = time_elem.get_text(strip=True) if time_elem else ""
                        
                        event = {
                            "id": f"gov_{hash(url)}",
                            "title": title,
                            "content": content,
                            "url": url,
                            "publish_time": publish_time,
                            "source": "中国政府网",
                            "keyword": keyword,
                            "origin": "government_announcement",
                            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        events.append(event)
                
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"爬取中国政府网第 {page} 页时发生错误: {e}")
                continue
        
        return events
    
    def _crawl_miit_announcements(self, keyword: str, max_pages: int) -> List[Dict[str, Any]]:
        """爬取工信部公告"""
        events = []
        
        for page in range(1, max_pages + 1):
            try:
                url = "http://www.miit.gov.cn/search"
                params = {
                    "keyword": keyword,
                    "page": page
                }
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                announcement_items = soup.find_all("div", class_="announcement-item")
                
                for item in announcement_items:
                    title_elem = item.find("h3")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.find("a")
                        url = link.get("href") if link else ""
                        
                        content_elem = item.find("p", class_="summary")
                        content = content_elem.get_text(strip=True) if content_elem else ""
                        
                        time_elem = item.find("span", class_="time")
                        publish_time = time_elem.get_text(strip=True) if time_elem else ""
                        
                        event = {
                            "id": f"miit_{hash(url)}",
                            "title": title,
                            "content": content,
                            "url": url,
                            "publish_time": publish_time,
                            "source": "工信部",
                            "keyword": keyword,
                            "origin": "government_announcement",
                            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        events.append(event)
                
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"爬取工信部第 {page} 页时发生错误: {e}")
                continue
        
        return events
    
    def _crawl_ndrc_announcements(self, keyword: str, max_pages: int) -> List[Dict[str, Any]]:
        """爬取发改委公告"""
        events = []
        
        for page in range(1, max_pages + 1):
            try:
                url = "http://www.ndrc.gov.cn/search"
                params = {
                    "keyword": keyword,
                    "page": page
                }
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                announcement_items = soup.find_all("div", class_="announcement-item")
                
                for item in announcement_items:
                    title_elem = item.find("h3")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.find("a")
                        url = link.get("href") if link else ""
                        
                        content_elem = item.find("p", class_="summary")
                        content = content_elem.get_text(strip=True) if content_elem else ""
                        
                        time_elem = item.find("span", class_="time")
                        publish_time = time_elem.get_text(strip=True) if time_elem else ""
                        
                        event = {
                            "id": f"ndrc_{hash(url)}",
                            "title": title,
                            "content": content,
                            "url": url,
                            "publish_time": publish_time,
                            "source": "发改委",
                            "keyword": keyword,
                            "origin": "government_announcement",
                            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        events.append(event)
                
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"爬取发改委第 {page} 页时发生错误: {e}")
                continue
        
        return events
    
    def crawl_forum_posts(self, keyword: str, max_pages: int = 5) -> List[Dict[str, Any]]:
        return []
    
    def _crawl_tianya_forum(self, keyword: str, max_pages: int) -> List[Dict[str, Any]]:
        """爬取天涯论坛帖子"""
        events = []
        
        for page in range(1, max_pages + 1):
            try:
                url = "http://bbs.tianya.cn"
                params = {
                    "keyword": keyword,
                    "page": page
                }
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                post_items = soup.find_all("div", class_="post-item")
                
                for item in post_items:
                    title_elem = item.find("h3")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.find("a")
                        url = link.get("href") if link else ""
                        
                        content_elem = item.find("p", class_="summary")
                        content = content_elem.get_text(strip=True) if content_elem else ""
                        
                        author_elem = item.find("span", class_="author")
                        author = author_elem.get_text(strip=True) if author_elem else ""
                        
                        time_elem = item.find("span", class_="time")
                        publish_time = time_elem.get_text(strip=True) if time_elem else ""
                        
                        event = {
                            "id": f"tianya_{hash(url)}",
                            "title": title,
                            "content": content,
                            "url": url,
                            "author": author,
                            "publish_time": publish_time,
                            "source": "天涯论坛",
                            "keyword": keyword,
                            "origin": "network_forum",
                            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        events.append(event)
                
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"爬取天涯论坛第 {page} 页时发生错误: {e}")
                continue
        
        return events
    
    def _crawl_baidu_tieba(self, keyword: str, max_pages: int) -> List[Dict[str, Any]]:
        """爬取百度贴吧帖子"""
        events = []
        
        for page in range(1, max_pages + 1):
            try:
                url = "https://tieba.baidu.com"
                params = {
                    "keyword": keyword,
                    "page": page
                }
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                post_items = soup.find_all("div", class_="post-item")
                
                for item in post_items:
                    title_elem = item.find("h3")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.find("a")
                        url = link.get("href") if link else ""
                        
                        content_elem = item.find("p", class_="summary")
                        content = content_elem.get_text(strip=True) if content_elem else ""
                        
                        author_elem = item.find("span", class_="author")
                        author = author_elem.get_text(strip=True) if author_elem else ""
                        
                        time_elem = item.find("span", class_="time")
                        publish_time = time_elem.get_text(strip=True) if time_elem else ""
                        
                        event = {
                            "id": f"tieba_{hash(url)}",
                            "title": title,
                            "content": content,
                            "url": url,
                            "author": author,
                            "publish_time": publish_time,
                            "source": "百度贴吧",
                            "keyword": keyword,
                            "origin": "network_forum",
                            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        events.append(event)
                
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"爬取百度贴吧第 {page} 页时发生错误: {e}")
                continue
        
        return events
    
    def crawl_all_sources(self):
        """执行所有来源的爬取"""
        try:
            print("开始多源数据爬取...")
            
            for keyword in self.keywords:
                print(f"正在爬取关键词: {keyword}")
                # 1) 优先使用RSS抓取（推荐稳定方案）
                if self.rss_sources:
                    print("  通过RSS源抓取...")
                    rss_events = self.crawl_via_rss(keyword)
                    self.all_events.extend(rss_events)
                    print(f"  RSS抓取完成，获取 {len(rss_events)} 条数据")
                else:
                    print("  未配置RSS源，跳过RSS抓取")

                # 2) 忽略遗留解析，统一ChinaSo

                # 3) 回退：ChinaSo通用网页搜索（强力兜底）
                if self.enable_chinaso_fallback:
                    print("  通过ChinaSo通用搜索抓取...")
                    so_events = self.crawl_via_chinaso(keyword, pages=3)
                    self.all_events.extend(so_events)
                    print(f"  ChinaSo抓取完成，获取 {len(so_events)} 条数据")
                
                # 保存数据
                self.save_data()
                
                print(f"关键词 {keyword} 爬取完成")
            
            print(f"所有来源爬取完成，共获取 {len(self.all_events)} 条数据")
            
        except Exception as e:
            print(f"爬取过程中发生错误: {e}")
            if self.all_events:
                self.save_data()
            raise

    def crawl_via_chinaso(self, keyword: str, pages: int = 3, page_size: int = 15) -> List[Dict[str, Any]]:
        """通过ChinaSo搜索抓取网页，并抽取正文。"""
        collected: List[Dict[str, Any]] = []
        for pn in range(1, pages + 1):
            try:
                results = self._search_chinaso(keyword, pn, page_size)
                if not results:
                    if pn == 1:
                        print("    ChinaSo：第一页即无结果")
                    break
                for item in results:
                    url = item.get("url", "")
                    if not url:
                        continue
                    text, title, publish_time = self._fetch_page_text(url)
                    if not text:
                        continue
                    # 使用ChinaSo返回的source字段，让大模型判断来源类型
                    chinaso_source = item.get("site", "")
                    event = {
                        "id": f"so_{hash(url)}",
                        "title": title or item.get("title", ""),
                        "content": text,
                        "url": url,
                        "publish_time": publish_time or item.get("publish_time", ""),
                        "source": chinaso_source,  # 保留ChinaSo的原始source字段
                        "keyword": keyword,
                        "origin": "外部来源",  # 先设为默认值，后续由大模型分析
                        "chinaso_source": chinaso_source,  # 新增字段，供大模型分析使用
                        "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    collected.append(event)
                sleep_time = random.uniform(*self.delay_range)
                print(f"    ChinaSo触发频率控制，休眠 {sleep_time:.2f} 秒")
                time.sleep(sleep_time)
            except Exception as e:
                print(f"    ChinaSo抓取失败: 第{pn}页 -> {e}")
                continue
        return collected

    def _search_chinaso(self, keyword: str, pn: int = 1, ps: int = 15) -> List[Dict[str, Any]]:
        try:
            url = f'https://www.chinaso.com/v5/general/v1/web/search?q=\'{keyword}\'&pn={pn}&ps={ps}'
            
            print(f"    请求ChinaSo: {url}")
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            print(f"    ChinaSo响应状态: {resp.status_code}")
            print(f"    ChinaSo响应数据结构: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            
            items: List[Dict[str, Any]] = []
            if isinstance(data, dict):
                container = data.get("data") or {}
                print(f"    ChinaSo数据容器: {list(container.keys()) if isinstance(container, dict) else type(container)}")
                # 官方示例中数据在 data.data 数组
                raw_items = container.get("items") or container.get("list") or container.get("data") or []
                print(f"    ChinaSo原始条目数: {len(raw_items) if isinstance(raw_items, list) else 0}")
                if isinstance(raw_items, list):
                    for it in raw_items:
                        if not isinstance(it, dict):
                            continue
                        link = it.get("url") or it.get("link") or ""
                        title = self._clean_text(it.get("title") or "")
                        # snippet 字段包含 <em>...
                        summary = self._clean_text(it.get("snippet") or it.get("summary") or it.get("desc") or it.get("content") or "")
                        source = self._clean_text(it.get("source") or it.get("site") or "")
                        ts = it.get("timestamp") or it.get("pubtime") or it.get("publish_time") or it.get("time") or ""
                        if link:
                            items.append({
                                "url": link,
                                "title": title,
                                "summary": summary,
                                "site": source,
                                "publish_time": ts
                            })
                            print(f"      找到条目: {title[:30]}... (来源: {source})")
            print(f"    ChinaSo最终返回 {len(items)} 个条目")
            return items
        except Exception as e:
            print(f"    ChinaSo搜索失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_page_text(self, url: str) -> Tuple[str, str, str]:
        try:
            # ChinaSo 结果可能是跳转链接，打开后自动跟随
            r = self.session.get(url, timeout=15, allow_redirects=True)
            r.raise_for_status()
            html = self._decode_response_text(r)
            soup = BeautifulSoup(html, 'lxml')
            title = ""
            if soup.title and soup.title.string:
                title = self._clean_text(soup.title.string)
            candidates = []
            selectors = [
                'article', 'div.article', 'div#article', 'div.content', 'div#content',
                'div.main-content', 'div.article-content', 'section.article'
            ]
            for sel in selectors:
                node = soup.select_one(sel)
                if node and node.get_text(strip=True):
                    candidates.append(self._clean_text(node.get_text("\n", strip=True)))
            if not candidates:
                paragraphs = [self._clean_text(p.get_text(" ", strip=True)) for p in soup.find_all('p')]
                body_text = "\n".join([p for p in paragraphs if len(p) > 20])
            else:
                body_text = max(candidates, key=len)
            body_text = body_text.strip()
            publish_time = ""
            for time_sel in ['time', 'span.time', 'div.time', 'p.time', 'span.pubtime', 'div.pubtime']:
                tn = soup.select_one(time_sel)
                if tn and tn.get_text(strip=True):
                    publish_time = self._clean_text(tn.get_text(strip=True))
                    break
            
            print(f"      页面抓取成功: {title[:30]}... (内容长度: {len(body_text)})")
            return body_text, title, publish_time
        except Exception as e:
            print(f"    抓取页面失败: {url} -> {e}")
            return "", "", ""

    def crawl_via_rss(self, keyword: str) -> List[Dict[str, Any]]:
        """
        通过RSS/Atom源抓取，并按关键词进行筛选。
        需要在配置中提供 rss_sources = [{"name":"X", "url":"..."}]。
        """
        collected: List[Dict[str, Any]] = []
        if not self.rss_sources:
            return collected

        kw = (keyword or "").strip()
        for src in self.rss_sources:
            try:
                url = src.get("url", "").strip()
                name = src.get("name", "RSS")
                if not url:
                    continue
                print(f"    RSS解析: {name} -> {url}")
                feed = feedparser.parse(url)
                if feed.bozo:
                    print(f"    RSS解析失败: {name} ({feed.bozo_exception})")
                    continue

                entries = feed.entries or []
                for entry in entries:
                    title = self._clean_text(getattr(entry, 'title', '') or '')
                    summary = self._clean_text(getattr(entry, 'summary', '') or getattr(entry, 'description', '') or '')
                    link = getattr(entry, 'link', '') or ''
                    published = self._clean_text(getattr(entry, 'published', '') or getattr(entry, 'updated', '') or '')

                    text_for_match = f"{title}\n{summary}"
                    if kw and kw not in text_for_match:
                        continue

                    origin = self._infer_origin_by_url(link)
                    event = {
                        "id": f"rss_{hash(link)}",
                        "title": title,
                        "content": summary,
                        "url": link,
                        "publish_time": published,
                        "source": name,
                        "keyword": keyword,
                        "origin": origin,
                        "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    collected.append(event)
                # 限速
                sleep_time = random.uniform(*self.delay_range)
                print(f"    RSS触发频率控制，休眠 {sleep_time:.2f} 秒")
                time.sleep(sleep_time)
            except Exception as e:
                print(f"    RSS源处理失败: {src}: {e}")
                continue
        return collected

    def _infer_origin_by_url(self, url: str) -> str:
        """基于域名简单推断来源类型 -> 新闻网站/政府公告/网络论坛"""
        try:
            host = ""
            if url:
                from urllib.parse import urlparse
                host = (urlparse(url).netloc or '').lower()
            if any(x in host for x in ["gov.cn", "miit.gov.cn", "ndrc.gov.cn"]):
                return "政府公告"
            if any(x in host for x in ["tieba.baidu.com", "bbs.", "forum."]):
                return "网络论坛"
            return "新闻网站"
        except Exception:
            return "新闻网站"
    
    def save_data(self):
        """保存爬取的数据到文件"""
        try:
            # 保存JSON格式
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.all_events, f, ensure_ascii=False, indent=2)
            
            print(f"多源数据已保存到 {self.output_file}")
            
            # 保存CSV格式
            if self.all_events:
                df = pd.DataFrame(self.all_events)
                df.to_csv(self.csv_file, index=False, encoding='utf-8')
                print(f"多源数据已转换为CSV格式并保存到 {self.csv_file}")
                
        except Exception as e:
            print(f"保存数据时发生错误: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    # 创建多源爬虫实例
    crawler = MultiSourceCrawler()
    
    # 执行爬取
    crawler.crawl_all_sources()
