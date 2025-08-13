#!/usr/bin/env python3
"""
使用真实Chrome浏览器进行爬取 - 完全避免检测
"""
import asyncio
import json
import subprocess
import time
from playwright.async_api import async_playwright

async def connect_to_real_chrome():
    """连接到真实的Chrome浏览器"""
    
    # 1. 首先启动Chrome并开启调试端口
    print("🚀 启动Chrome浏览器...")
    print("请手动执行以下命令启动Chrome:")
    print("macOS/Linux:")
    print("google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug")
    print("\nmacOS (如果上面不行):")
    print("/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug")
    print("\nWindows:")
    print('chrome.exe --remote-debugging-port=9222 --user-data-dir=c:\\temp\\chrome-debug')
    
    print("\n⏳ 检测Chrome是否已启动...")
    # 检查Chrome调试端口是否可访问
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:9222/json/version") as response:
                if response.status == 200:
                    print("✅ 检测到Chrome已启动")
                else:
                    print("❌ Chrome未启动或调试端口不可访问")
                    return None, None, None
    except Exception as e:
        print(f"❌ 无法连接到Chrome: {e}")
        print("请确保Chrome已启动并开启调试端口9222")
        return None, None, None
    
    # 2. 连接到Chrome
    playwright = await async_playwright().start()
    
    try:
        # 先获取websocket调试URL
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:9222/json/version") as response:
                if response.status == 200:
                    version_info = await response.json()
                    ws_url = version_info.get('webSocketDebuggerUrl', '')
                    print(f"🔗 WebSocket URL: {ws_url}")
                else:
                    print(f"❌ 获取版本信息失败: {response.status}")
                    return None, None, None
        
        # 尝试不同的连接方式
        try:
            # 方法1: 直接连接到WebSocket URL
            browser = await playwright.chromium.connect_over_cdp(ws_url)
            print("✅ 通过WebSocket成功连接到Chrome浏览器")
        except Exception as ws_error:
            print(f"WebSocket连接失败: {ws_error}")
            try:
                # 方法2: 使用HTTP端点
                browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
                print("✅ 通过HTTP端点成功连接到Chrome浏览器")
            except Exception as http_error:
                print(f"HTTP连接也失败: {http_error}")
                return None, None, None
        
        # 获取现有页面或创建新页面
        contexts = browser.contexts
        if contexts:
            context = contexts[0]
        else:
            context = await browser.new_context()
        
        pages = context.pages
        if pages:
            page = pages[0]
        else:
            page = await context.new_page()
        
        return browser, page, playwright
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print("请确保Chrome已启动并开启调试端口")
        await playwright.stop()
        return None, None, None

async def scrape_with_real_browser():
    """使用真实浏览器进行爬取"""
    print("🔗 连接真实Chrome浏览器...")
    
    browser, page, playwright = await connect_to_real_chrome()
    if not browser:
        return
    
    try:
        print("📖 开始爬取测试...")
        
        # 检查当前页面
        current_url = page.url
        print(f"📍 当前页面: {current_url}")
        
        # 如果不在目标网站，先导航过去
        if "kongfz.com" not in current_url:
            print("🏠 导航到孔夫子旧书网...")
            await page.goto("https://www.kongfz.com")
            await asyncio.sleep(2)
        
        # 导航到店铺页面
        shop_url = "https://shop.kongfz.com/534779"
        print(f"🏪 访问店铺: {shop_url}")
        await page.goto(shop_url)
        await asyncio.sleep(3)
        
        # 检查是否需要登录
        page_content = await page.content()
        if "登录" in await page.title():
            print("🔐 检测到需要登录，请在浏览器中手动登录")
            print("登录完成后按Enter继续...")
            input()
        
        # 查找查看全部按钮
        print("🔍 寻找'查看全部'按钮...")
        try:
            await page.wait_for_selector(".more_goods a", timeout=10000)
            await page.click(".more_goods a")
            print("✅ 成功点击'查看全部'")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"❌ 点击失败: {e}")
            return
        
        # 获取书籍链接
        print("📚 获取书籍链接...")
        book_links = []
        
        # 查找所有书籍链接
        elements = await page.query_selector_all('a[href*="book.kongfz.com"]')
        for element in elements[:5]:  # 只取前5个测试
            href = await element.get_attribute('href')
            if href and href not in book_links:
                book_links.append(href)
        
        print(f"📋 找到 {len(book_links)} 个书籍链接")
        
        results = []
        
        # 爬取书籍详情
        for i, book_url in enumerate(book_links):
            print(f"📖 爬取第 {i+1} 本书: {book_url}")
            
            # 在新标签页打开
            new_page = await page.context.new_page()
            try:
                await new_page.goto(book_url)
                await asyncio.sleep(2)
                
                # 提取信息
                book_info = {'book_url': book_url}
                
                # 提取ISBN
                try:
                    isbn_element = await new_page.query_selector("ul.detail-list1 > li:nth-child(5)")
                    if isbn_element:
                        isbn_text = await isbn_element.inner_text()
                        book_info['isbn'] = isbn_text.strip()
                        print(f"  📄 ISBN: {isbn_text.strip()}")
                except:
                    book_info['isbn'] = "未找到"
                
                # 提取书名
                try:
                    title_element = await new_page.query_selector("h1")
                    if title_element:
                        title = await title_element.inner_text()
                        book_info['title'] = title.strip()
                        print(f"  📚 书名: {title.strip()}")
                except:
                    book_info['title'] = "未找到"
                
                results.append(book_info)
                
            except Exception as e:
                print(f"  ❌ 爬取失败: {e}")
            finally:
                await new_page.close()
            
            # 延迟
            await asyncio.sleep(2)
        
        # 保存结果
        if results:
            with open('real_browser_results.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"💾 结果已保存到 real_browser_results.json")
            
            # 显示结果摘要
            for i, book in enumerate(results):
                print(f"书籍 {i+1}: {book.get('title', '未知')} - {book.get('isbn', '无ISBN')}")
        
        print("🎉 使用真实浏览器爬取完成!")
        print("💡 优势: 完全避免了自动化检测，使用真实浏览器环境")
        
    except Exception as e:
        print(f"❌ 爬取过程出错: {e}")
    
    finally:
        # 注意：不要关闭browser，因为这是用户的真实浏览器
        await playwright.stop()
        print("🔌 已断开连接，浏览器继续运行")

if __name__ == "__main__":
    asyncio.run(scrape_with_real_browser())