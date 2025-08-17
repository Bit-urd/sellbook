#!/usr/bin/env python3
"""
测试解封时间显示功能
"""
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
import time

async def test_unblock_time_display():
    """测试解封时间显示功能"""
    print("=== 测试解封时间显示功能 ===\n")
    
    async with aiohttp.ClientSession() as session:
        # 1. 获取当前窗口池状态
        print("1. 获取当前窗口池状态...")
        async with session.get("http://localhost:8282/window-pool/status") as response:
            if response.status == 200:
                data = await response.json()
                window_details = data['data']['window_details']
                
                print(f"✓ 获取到 {len(window_details)} 个窗口信息")
                print("\n当前窗口状态:")
                print("=" * 80)
                print(f"{'窗口ID':<12} {'状态':<8} {'封控状态':<10} {'解封时间':<20} {'剩余时间'}")
                print("-" * 80)
                
                for window in window_details:
                    window_id = window['window_id']
                    status = "可用" if window['status'] == 'available' else "使用中"
                    
                    # 判断封控状态
                    if window['is_rate_limited']:
                        block_status = "已封控"
                        unblock_time_str = window['blocked_until']
                    elif window['is_login_required']:
                        block_status = "需要登录"
                        unblock_time_str = window['login_required_until']
                    else:
                        block_status = "正常"
                        unblock_time_str = None
                    
                    # 计算剩余时间
                    remaining = "-"
                    if unblock_time_str:
                        try:
                            unblock_time = datetime.strptime(unblock_time_str, "%Y-%m-%d %H:%M:%S")
                            current_time = datetime.now()
                            if unblock_time > current_time:
                                remaining_seconds = (unblock_time - current_time).total_seconds()
                                remaining_minutes = int(remaining_seconds // 60)
                                remaining_seconds = int(remaining_seconds % 60)
                                remaining = f"{remaining_minutes}分{remaining_seconds}秒"
                            else:
                                remaining = "已解封"
                        except:
                            remaining = "解析错误"
                    
                    unblock_display = unblock_time_str if unblock_time_str else "-"
                    
                    print(f"{window_id:<12} {status:<8} {block_status:<10} {unblock_display:<20} {remaining}")
                
                print("=" * 80)
                
                # 2. 统计封控情况
                blocked_count = sum(1 for w in window_details if w['is_rate_limited'])
                login_required_count = sum(1 for w in window_details if w['is_login_required'])
                total_count = len(window_details)
                
                print(f"\n📊 封控统计:")
                print(f"   - 总窗口数: {total_count}")
                print(f"   - 频率限制: {blocked_count}")
                print(f"   - 需要登录: {login_required_count}")
                print(f"   - 正常状态: {total_count - blocked_count - login_required_count}")
                
                # 3. 找出最早解封的窗口
                earliest_unblock = None
                earliest_window = None
                
                for window in window_details:
                    unblock_time_str = window.get('blocked_until') or window.get('login_required_until')
                    if unblock_time_str:
                        try:
                            unblock_time = datetime.strptime(unblock_time_str, "%Y-%m-%d %H:%M:%S")
                            if earliest_unblock is None or unblock_time < earliest_unblock:
                                earliest_unblock = unblock_time
                                earliest_window = window
                        except:
                            pass
                
                if earliest_window:
                    remaining_time = (earliest_unblock - datetime.now()).total_seconds()
                    if remaining_time > 0:
                        print(f"\n⏰ 最早解封:")
                        print(f"   - 窗口ID: {earliest_window['window_id']}")
                        print(f"   - 解封时间: {earliest_unblock.strftime('%H:%M:%S')}")
                        print(f"   - 剩余时间: {int(remaining_time//60)}分{int(remaining_time%60)}秒")
                    else:
                        print(f"\n✅ 窗口 {earliest_window['window_id']} 应该已经解封了")
                
                # 4. 提示如何查看页面
                print(f"\n🌐 查看详细信息:")
                print(f"   在浏览器中访问: http://localhost:8282/window-pool-admin")
                print(f"   用户名: biturd")
                print(f"   密码: biturd")
                print(f"\n   页面会显示:")
                print(f"   - 实时解封时间")
                print(f"   - 剩余封控时间倒计时")
                print(f"   - 自动刷新状态（每10秒）")
                
            else:
                print(f"✗ 获取状态失败: {response.status}")

if __name__ == "__main__":
    print("解封时间显示功能测试")
    print("=" * 50)
    asyncio.run(test_unblock_time_display())