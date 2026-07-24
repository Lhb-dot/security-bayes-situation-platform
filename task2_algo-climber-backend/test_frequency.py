import random
import time
from config import CRAWLER_CONFIG
from multi_source_crawler import MultiSourceCrawler

def run_frequency_test():
    # 模拟前端可能传来的三种频率选项
    test_frequencies = {
        "低": "最安全，降低封IP风险", 
        "中": "默认设置，速度与安全的平衡", 
        "高": "速度最快，适合短时间急需数据"
    }
    
    print("🕵️‍♂️ 开始进行爬虫频率控制测试...\n")

    for freq, desc in test_frequencies.items():
        print(f"{'='*50}")
        print(f"🚀 测试模式: [{freq}] - {desc}")
        print(f"{'='*50}")
        
        # 1. 完全模拟 main.py 里的解析和传参逻辑
        delay_ranges = CRAWLER_CONFIG.get("delay_ranges", {"中": (3, 8)})
        current_delay = delay_ranges.get(freq, delay_ranges["中"]) 
        
        test_config = dict(CRAWLER_CONFIG)
        test_config["delay_range"] = current_delay
        
        # 2. 初始化底层爬虫
        crawler = MultiSourceCrawler(config=test_config)
        print(f"✅ 底层爬虫初始化成功！读取到的休眠区间为: {crawler.delay_range} 秒\n")
        
        # 3. 模拟底层抓取循环时的随机休眠行为
        print("模拟连续 5 次网页抓取：")
        for i in range(1, 6):
            # 这就是你在 multi_source_crawler.py 里刚改的代码逻辑
            sleep_time = random.uniform(*crawler.delay_range)
            print(f"  [第 {i}/5 次抓取] 数据提取完毕 -> 触发频率控制，将休眠 {sleep_time:.2f} 秒")
            
            # 为了让测试脚本瞬间跑完，我们用 time.sleep(0.1) 替代真实的 sleep_time
            # 真实运行环境请去掉这个 0.1 的写死逻辑
            time.sleep(0.1) 
            
        print("\n")

if __name__ == "__main__":
    run_frequency_test()