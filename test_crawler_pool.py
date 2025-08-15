#!/usr/bin/env python3
"""
测试窗口池的真实爬虫功能
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.crawler_service import KongfuziCrawler
from src.services.window_pool import chrome_pool

async def test_concurrent_crawling():
    """测试并发爬取"""
    print("=== 并发爬取测试 ===\n")
    
    # 初始化窗口池
    print("1. 初始化窗口池...")
    success = await chrome_pool.initialize()
    if not success:
        print("窗口池初始化失败")
        return
    
    status = chrome_pool.get_pool_status()
    print(f"   窗口池已初始化: {status['total_windows']} 个窗口")
    print(f"   可用: {status['available_count']}, 忙碌: {status['busy_count']}\n")
    
    # 创建爬虫实例
    crawler1 = KongfuziCrawler()
    crawler2 = KongfuziCrawler()
    crawler3 = KongfuziCrawler()
    
    # 定义测试任务
    async def crawl_task(crawler, isbn, task_name):
        """爬取任务"""
        print(f"[{task_name}] 开始爬取 ISBN: {isbn}")
        
        # 查看爬取前的窗口池状态
        status_before = chrome_pool.get_pool_status()
        print(f"[{task_name}] 爬取前 - 可用窗口: {status_before['available_count']}, 忙碌: {status_before['busy_count']}")
        
        try:
            # 使用analyze_book_sales方法，它会自动从池中获取窗口
            result = await crawler.analyze_book_sales(isbn, days_limit=7, quality_filter="high")
            print(f"[{task_name}] ✓ 完成! 获取到 {result.get('total_records', 0)} 条记录")
            
            # 查看爬取后的窗口池状态
            status_after = chrome_pool.get_pool_status()
            print(f"[{task_name}] 爬取后 - 可用窗口: {status_after['available_count']}, 忙碌: {status_after['busy_count']}")
            
            return True
        except Exception as e:
            print(f"[{task_name}] ✗ 失败: {e}")
            return False
    
    # 并发执行3个爬取任务（窗口池只有2个窗口）
    print("2. 启动3个并发爬取任务（窗口池只有2个窗口）...")
    print("   预期：前2个任务立即执行，第3个任务等待窗口释放\n")
    
    tasks = [
        crawl_task(crawler1, "9787544291200", "任务1"),
        crawl_task(crawler2, "9787544270878", "任务2"),
        crawl_task(crawler3, "9787020002207", "任务3")
    ]
    
    # 并发执行
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 输出结果
    print("\n3. 测试结果:")
    success_count = sum(1 for r in results if r is True)
    print(f"   成功: {success_count}/3")
    
    # 最终窗口池状态
    final_status = chrome_pool.get_pool_status()
    print(f"\n4. 最终窗口池状态:")
    print(f"   可用窗口: {final_status['available_count']}")
    print(f"   忙碌窗口: {final_status['busy_count']}")
    print(f"   窗口使用情况:")
    for window in final_status['window_details']:
        print(f"     - 窗口 {window['window_id']}: {window['status']}, 使用次数: {window['used_count']}")
    
    # 不关闭窗口，保持登录状态
    print("\n5. 保持窗口打开...")
    print("   窗口将继续保持登录状态，供后续爬虫使用")
    print("   测试完成!")

if __name__ == "__main__":
    print("窗口池真实爬虫并发测试")
    print("=" * 50)
    asyncio.run(test_concurrent_crawling())