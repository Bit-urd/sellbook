#!/usr/bin/env python3
"""
测试爬虫服务 V2 - 验证新的自主会话管理架构
"""
import asyncio
import logging
import time
from src.services.crawler_service import crawler_service_v2

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_service_status():
    """测试服务状态"""
    print("=== 测试服务状态 ===")
    
    # 无需初始化，会话管理器会自动启动
    print("会话管理器会自动启动，无需手动初始化")
    
    # 健康检查（这会触发自动启动）
    health = await crawler_service_v2.health_check()
    print(f"健康状态: {'✅ 健康' if health['healthy'] else '❌ 异常'}")
    if not health['healthy']:
        print(f"问题: {health['issues']}")
    
    return health['healthy']

def test_task_management():
    """测试任务管理"""
    print("\n=== 测试任务管理 ===")
    
    # 添加各种类型的任务
    print("添加任务...")
    
    # 添加ISBN分析任务
    isbn = "9787544291200"
    task_ids = crawler_service_v2.quick_crawl_isbn(isbn, include_analysis=True)
    print(f"为ISBN {isbn} 添加了任务: {task_ids}")
    
    # 添加店铺爬取任务
    shop_task = crawler_service_v2.add_shop_books_task(
        shop_url="https://shop123.kongfz.com/",
        max_pages=10,
        priority=6
    )
    print(f"添加店铺任务: {shop_task}")
    
    # 批量添加ISBN任务
    isbn_list = ["9787020002207", "9787108006240", "9787544291200"]
    batch_tasks = crawler_service_v2.batch_add_isbn_tasks(isbn_list, priority=7)
    print(f"批量添加任务: {len(batch_tasks)} 个")
    
    return task_ids + [shop_task] + batch_tasks

async def test_queue_status():
    """测试队列状态查询"""
    print("\n=== 测试队列状态 ===")
    
    # 获取完整状态
    status = await crawler_service_v2.get_queue_status()
    
    print("任务队列状态:")
    task_queue = status['task_queue']
    print(f"  待处理任务: {task_queue['total_pending']}")
    print(f"  运行中任务: {task_queue['total_running']}")
    
    print("平台统计:")
    for platform, stats in task_queue['platform_stats'].items():
        print(f"  {platform}: pending={stats['pending']}, running={stats['running']}")
    
    print("会话管理器状态:")
    session_mgr = status['session_manager']
    print(f"  运行状态: {session_mgr['running']}")
    print(f"  浏览器连接: {session_mgr['connected']}")
    print(f"  总窗口数: {session_mgr['total_windows']}")
    print(f"  可用窗口: {session_mgr['available_windows']}")
    print(f"  队列大小: {session_mgr['queue_size']}")
    print(f"  处理中任务: {session_mgr['processing_tasks']}")
    
    print("各平台可用窗口:")
    for platform, count in session_mgr['available_by_platform'].items():
        print(f"  {platform}: {count} 个窗口")

async def test_platform_status():
    """测试平台状态查询"""
    print("\n=== 测试平台状态 ===")
    
    platforms = ['kongfuzi', 'duozhuayu']
    for platform in platforms:
        status = await crawler_service_v2.get_platform_status(platform)
        print(f"{platform} 平台状态:")
        print(f"  可用窗口: {status['available_windows']}")
        print(f"  待处理任务: {status['pending_tasks']}")
        print(f"  运行中任务: {status['running_tasks']}")
        print(f"  今日完成: {status['completed_today']}")
        print(f"  今日失败: {status['failed_today']}")

def test_task_operations():
    """测试任务操作"""
    print("\n=== 测试任务操作 ===")
    
    # 获取最近任务
    recent_tasks = crawler_service_v2.get_recent_tasks(limit=5)
    print(f"最近任务数: {len(recent_tasks)}")
    
    if recent_tasks:
        task = recent_tasks[0]
        task_id = task['id']
        print(f"最新任务: {task_id} - {task['task_name']} ({task['status']})")
        
        # 测试任务查询
        task_detail = crawler_service_v2.get_task_by_id(task_id)
        if task_detail:
            print(f"任务详情: {task_detail['task_type']} - {task_detail['target_platform']}")

async def test_monitoring():
    """测试监控功能"""
    print("\n=== 测试监控功能 ===")
    
    # 监控一段时间，观察任务处理
    print("开始监控任务处理（30秒）...")
    
    start_time = time.time()
    last_stats = None
    
    for i in range(6):  # 每5秒检查一次，共30秒
        await asyncio.sleep(5)
        
        current_stats = await crawler_service_v2.get_statistics()
        elapsed = time.time() - start_time
        
        print(f"[{elapsed:.0f}s] 统计信息:")
        print(f"  处理任务总数: {current_stats['tasks_processed']}")
        print(f"  完成任务数: {current_stats['tasks_completed']}")
        print(f"  失败任务数: {current_stats['tasks_failed']}")
        print(f"  拒绝任务数: {current_stats['tasks_rejected']}")
        
        if last_stats:
            processed_delta = current_stats['tasks_processed'] - last_stats['tasks_processed']
            completed_delta = current_stats['tasks_completed'] - last_stats['tasks_completed']
            print(f"  增量: 处理+{processed_delta}, 完成+{completed_delta}")
        
        last_stats = current_stats.copy()
        
        # 显示当前队列状态
        queue_status = await crawler_service_v2.get_queue_status()
        session_mgr = queue_status['session_manager']
        print(f"  队列: {session_mgr['queue_size']} 待处理, {session_mgr['processing_tasks']} 处理中")

def test_queue_management():
    """测试队列管理功能"""
    print("\n=== 测试队列管理 ===")
    
    # 测试重试失败任务
    retried = crawler_service_v2.retry_failed_tasks('kongfuzi')
    print(f"重试孔夫子平台失败任务: {retried} 个")
    
    # 测试清理旧任务
    cleaned = crawler_service_v2.cleanup_old_tasks(days_old=30)
    print(f"清理30天前的旧任务: {cleaned} 个")

async def main():
    """主测试函数"""
    print("=== 爬虫服务 V2 完整测试 ===")
    
    try:
        # 1. 测试服务状态（会自动启动）
        if not await test_service_status():
            return
        
        # 2. 测试任务管理
        task_ids = test_task_management()
        
        # 3. 测试状态查询
        await test_queue_status()
        await test_platform_status()
        test_task_operations()
        
        # 4. 测试队列管理
        test_queue_management()
        
        # 5. 监控任务处理
        await test_monitoring()
        
        print("\n=== 最终状态 ===")
        final_health = await crawler_service_v2.health_check()
        print(f"最终健康状态: {'✅ 健康' if final_health['healthy'] else '❌ 异常'}")
        
        final_stats = await crawler_service_v2.get_statistics()
        print(f"最终统计: 处理{final_stats['tasks_processed']}, 完成{final_stats['tasks_completed']}, 失败{final_stats['tasks_failed']}")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\n=== 清理资源 ===")
        await crawler_service_v2.stop()
        print("测试完成")

if __name__ == "__main__":
    asyncio.run(main())