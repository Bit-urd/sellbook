#!/usr/bin/env python3
"""
测试窗口池并发功能
"""
import asyncio
import aiohttp
import json
from datetime import datetime

async def test_isbn_analysis(session, isbn, task_id):
    """测试单个ISBN分析"""
    start_time = datetime.now()
    url = f"http://localhost:8282/api/isbn/{isbn}/analysis?quality=九品以上"
    
    try:
        print(f"[任务 {task_id}] 开始分析 ISBN: {isbn}")
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                elapsed = (datetime.now() - start_time).total_seconds()
                print(f"[任务 {task_id}] ✓ 成功完成 ISBN: {isbn}，耗时: {elapsed:.2f}秒")
                return {"success": True, "isbn": isbn, "time": elapsed}
            else:
                print(f"[任务 {task_id}] ✗ 失败 ISBN: {isbn}, 状态码: {response.status}")
                return {"success": False, "isbn": isbn, "status": response.status}
    except Exception as e:
        print(f"[任务 {task_id}] ✗ 错误 ISBN: {isbn}, 异常: {e}")
        return {"success": False, "isbn": isbn, "error": str(e)}

async def check_window_pool_status(session):
    """检查窗口池状态"""
    url = "http://localhost:8282/window-pool/status"
    async with session.get(url) as response:
        if response.status == 200:
            data = await response.json()
            return data["data"]
    return None

async def main():
    """主测试函数"""
    # 测试用的ISBN列表
    test_isbns = [
        "9787544291200",
        "9787544270878",
        "9787020002207"
    ]
    
    async with aiohttp.ClientSession() as session:
        # 1. 检查初始窗口池状态
        print("\n=== 窗口池初始状态 ===")
        status = await check_window_pool_status(session)
        if status:
            print(f"总窗口数: {status['total_windows']}")
            print(f"可用窗口: {status['available_count']}")
            print(f"忙碌窗口: {status['busy_count']}")
        
        # 2. 并发测试ISBN分析（测试窗口池）
        print("\n=== 开始并发测试 ===")
        print(f"测试ISBN数量: {len(test_isbns)}")
        print(f"窗口池大小: {status['pool_size']}")
        print("预期：前2个任务并发执行，第3个任务等待窗口释放\n")
        
        # 创建并发任务
        tasks = []
        for i, isbn in enumerate(test_isbns, 1):
            task = test_isbn_analysis(session, isbn, i)
            tasks.append(task)
        
        # 执行并发任务
        start_time = datetime.now()
        results = await asyncio.gather(*tasks)
        total_time = (datetime.now() - start_time).total_seconds()
        
        # 3. 检查测试后窗口池状态
        print("\n=== 测试完成后窗口池状态 ===")
        status = await check_window_pool_status(session)
        if status:
            print(f"可用窗口: {status['available_count']}")
            print(f"忙碌窗口: {status['busy_count']}")
            for window in status['window_details']:
                print(f"  窗口 {window['window_id']}: 状态={window['status']}, 使用次数={window['used_count']}")
        
        # 4. 统计结果
        print("\n=== 测试结果统计 ===")
        success_count = sum(1 for r in results if r["success"])
        print(f"成功: {success_count}/{len(results)}")
        print(f"总耗时: {total_time:.2f}秒")
        print(f"平均耗时: {total_time/len(results):.2f}秒/任务")
        
        # 显示详细结果
        print("\n任务详情:")
        for i, result in enumerate(results, 1):
            if result["success"]:
                print(f"  任务{i}: ✓ {result['isbn']} - {result['time']:.2f}秒")
            else:
                print(f"  任务{i}: ✗ {result['isbn']} - 失败")

if __name__ == "__main__":
    print("窗口池并发测试程序")
    print("=" * 50)
    asyncio.run(main())