#!/usr/bin/env python3
"""
测试首选窗口机制
"""
import asyncio
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.window_pool import ChromeWindowPool

async def test_preferred_window_mechanism():
    """测试首选窗口机制"""
    print("=== 测试首选窗口机制 ===\n")
    
    # 创建窗口池（2个窗口）
    pool = ChromeWindowPool(pool_size=2)
    
    try:
        # 1. 初始化窗口池
        print("1. 初始化窗口池...")
        if not await pool.initialize():
            print("✗ 窗口池初始化失败")
            return
        print("✓ 窗口池初始化成功")
        
        # 2. 获取初始状态
        status = pool.get_pool_status()
        print(f"   - 总窗口数: {status['total_windows']}")
        print(f"   - 首选窗口ID: {status['preferred_window_id']}")
        print()
        
        # 3. 第一次获取窗口（应该设置为首选窗口）
        print("2. 第一次获取窗口...")
        page1 = await pool.get_window()
        if page1:
            window_id1 = id(page1)
            print(f"✓ 获取到窗口: {window_id1}")
            
            status = pool.get_pool_status()
            print(f"   - 首选窗口ID: {status['preferred_window_id']}")
            print(f"   - 是否为首选窗口: {status['preferred_window_id'] == window_id1}")
        else:
            print("✗ 无法获取窗口")
            return
        print()
        
        # 4. 归还窗口
        print("3. 归还窗口...")
        await pool.return_window(page1)
        print("✓ 窗口已归还")
        print()
        
        # 5. 再次获取窗口（应该使用同一个首选窗口）
        print("4. 再次获取窗口（应该使用首选窗口）...")
        page2 = await pool.get_window()
        if page2:
            window_id2 = id(page2)
            print(f"✓ 获取到窗口: {window_id2}")
            print(f"   - 是否为同一个窗口: {window_id1 == window_id2}")
            
            if window_id1 == window_id2:
                print("✓ 成功使用首选窗口")
            else:
                print("⚠ 使用了不同的窗口")
        else:
            print("✗ 无法获取窗口")
            return
        print()
        
        # 6. 获取第二个窗口（并发测试）
        print("5. 获取第二个窗口（并发测试）...")
        page3 = await pool.get_window()
        if page3:
            window_id3 = id(page3)
            print(f"✓ 获取到第二个窗口: {window_id3}")
            print(f"   - 与首选窗口不同: {window_id2 != window_id3}")
        else:
            print("✗ 无法获取第二个窗口")
            return
        print()
        
        # 7. 检查状态
        print("6. 检查当前状态...")
        status = pool.get_pool_status()
        print(f"   - 首选窗口ID: {status['preferred_window_id']}")
        print(f"   - 忙碌窗口数: {status['busy_count']}")
        print(f"   - 可用窗口数: {status['available_count']}")
        print()
        
        # 8. 归还所有窗口
        print("7. 归还所有窗口...")
        await pool.return_window(page2)
        await pool.return_window(page3)
        print("✓ 所有窗口已归还")
        print()
        
        # 9. 最终状态检查
        print("8. 最终状态检查...")
        status = pool.get_pool_status()
        print(f"   - 首选窗口ID: {status['preferred_window_id']}")
        print(f"   - 忙碌窗口数: {status['busy_count']}")
        print(f"   - 可用窗口数: {status['available_count']}")
        
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
    print("首选窗口机制测试")
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
    
    asyncio.run(test_preferred_window_mechanism())