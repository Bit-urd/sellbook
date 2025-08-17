#!/usr/bin/env python3
"""
测试窗口被封控时的切换逻辑
"""
import asyncio
import sys
import os
import time

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.window_pool import ChromeWindowPool

async def test_blocked_window_switching():
    """测试窗口被封控时的切换逻辑"""
    print("=== 测试窗口被封控时的切换逻辑 ===\n")
    
    # 创建窗口池（2个窗口）
    pool = ChromeWindowPool(pool_size=2)
    
    try:
        # 1. 初始化窗口池
        print("1. 初始化窗口池...")
        if not await pool.initialize():
            print("✗ 窗口池初始化失败")
            return
        print("✓ 窗口池初始化成功")
        
        # 2. 获取第一个窗口（成为首选窗口）
        print("\n2. 获取第一个窗口（设为首选窗口）...")
        page1 = await pool.get_window()
        if not page1:
            print("✗ 无法获取第一个窗口")
            return
        
        window_id1 = id(page1)
        status = pool.get_pool_status()
        print(f"✓ 获取到首选窗口: {window_id1}")
        print(f"   - 首选窗口ID: {status['preferred_window_id']}")
        
        # 3. 归还窗口
        await pool.return_window(page1)
        print("✓ 第一个窗口已归还")
        
        # 4. 手动封控首选窗口
        print(f"\n3. 手动封控首选窗口 {window_id1}...")
        pool._apply_rate_limit_penalty(window_id1)
        print("✓ 首选窗口已被封控")
        
        # 5. 检查窗口状态
        status = pool.get_pool_status()
        print(f"   - 首选窗口ID: {status['preferred_window_id']}")
        for window in status['window_details']:
            print(f"   - 窗口 {window['window_id']}: {window['actual_status']}")
        
        # 6. 再次获取窗口（应该切换到其他窗口）
        print(f"\n4. 再次获取窗口（首选窗口{window_id1}被封控，应切换到其他窗口）...")
        page2 = await pool.get_window()
        if not page2:
            print("✗ 无法获取窗口")
            return
        
        window_id2 = id(page2)
        print(f"✓ 获取到窗口: {window_id2}")
        
        if window_id1 == window_id2:
            print("⚠ 使用了同一个窗口（可能封控没有生效）")
        else:
            print("✓ 成功切换到不同的窗口")
        
        # 7. 检查新的首选窗口
        status = pool.get_pool_status()
        print(f"   - 新的首选窗口ID: {status['preferred_window_id']}")
        print(f"   - 是否为当前使用的窗口: {status['preferred_window_id'] == window_id2}")
        
        # 8. 归还窗口
        await pool.return_window(page2)
        print("✓ 第二个窗口已归还")
        
        # 9. 封控第二个窗口，测试所有窗口都被封控的情况
        print(f"\n5. 封控第二个窗口 {window_id2}，测试所有窗口被封控...")
        pool._apply_rate_limit_penalty(window_id2)
        print("✓ 第二个窗口也被封控")
        
        # 10. 检查所有窗口状态
        status = pool.get_pool_status()
        print("   当前所有窗口状态:")
        for window in status['window_details']:
            print(f"     - 窗口 {window['window_id']}: {window['actual_status']}")
        
        # 11. 尝试获取窗口（应该失败或等待）
        print(f"\n6. 尝试获取窗口（所有窗口都被封控，应该快速返回None）...")
        start_time = time.time()
        page3 = await pool.get_window(timeout=5.0)  # 5秒超时
        elapsed = time.time() - start_time
        
        if page3:
            print(f"⚠ 意外获取到窗口: {id(page3)} (耗时: {elapsed:.2f}秒)")
            await pool.return_window(page3)
        else:
            print(f"✓ 正确返回None，没有可用窗口 (耗时: {elapsed:.2f}秒)")
            if elapsed < 3.0:
                print("✓ 快速响应，没有长时间等待")
            else:
                print("⚠ 响应较慢，可能逻辑有问题")
        
        print("\n=== 测试完成 ===")
        
    except Exception as e:
        print(f"✗ 测试过程中出错: {e}")
    finally:
        # 清理
        print("\n清理窗口池...")
        await pool.close_all_windows()
        await pool.disconnect()
        print("✓ 清理完成")

if __name__ == "__main__":
    print("窗口封控切换逻辑测试")
    print("=" * 50)
    
    # 检查Chrome是否在运行
    import subprocess
    try:
        result = subprocess.run(['lsof', '-i', ':9222'], capture_output=True, text=True)
        if '9222' not in result.stdout:
            print("⚠ 警告: Chrome调试端口(9222)未开启")
            print("请先启动Chrome: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug")
            sys.exit(1)
    except:
        pass
    
    asyncio.run(test_blocked_window_switching())