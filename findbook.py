import asyncio
import json
import csv
from playwright.async_api import async_playwright
import time
import random
from urllib.parse import urljoin
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KongfzShopScraper:
    def __init__(self, headless=False, slow_mo=1000):
        self.headless = headless
        self.slow_mo = slow_mo
        self.results = []
        self.browser = None
        self.context = None

    async def pre_login_setup(self):
        """预处理设置 - 让用户登录"""
        async with async_playwright() as p:
            # 启动浏览器
            self.browser = await p.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo
            )

            # 创建浏览器上下文
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            # 创建登录页面
            login_page = await self.context.new_page()

            # 打开孔夫子旧书网登录页
            await login_page.goto('https://www.kongfz.com/user/login/', wait_until='networkidle')

            print("\n" + "="*60)
            print("🔐 请在浏览器中完成以下操作:")
            print("1. 登录您的孔夫子旧书网账号")
            print("2. 确保登录成功")
            print("3. 在控制台输入 'ok' 并按回车开始爬取")
            print("4. 或者输入 'quit' 退出程序")
            print("="*60)

            # 等待用户确认
            while True:
                user_input = input("\n请输入指令 (ok/quit): ").strip().lower()

                if user_input == 'ok':
                    logger.info("用户确认开始爬取")
                    await login_page.close()
                    return True
                elif user_input == 'quit':
                    logger.info("用户选择退出")
                    await login_page.close()
                    await self.context.close()
                    await self.browser.close()
                    return False
                else:
                    print("❌ 无效输入，请输入 'ok' 开始爬取或 'quit' 退出")

    async def scrape_shops(self, shop_urls):
        """爬取多个店铺 - 使用已建立的浏览器上下文"""
        try:
            for shop_url in shop_urls:
                logger.info(f"开始爬取店铺: {shop_url}")
                await self.scrape_single_shop(self.context, shop_url)

                # 随机延迟，避免过快请求
                await asyncio.sleep(random.uniform(2, 5))

        except Exception as e:
            logger.error(f"爬取过程中出现错误: {e}")
        finally:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()

        return self.results

    async def scrape_single_shop(self, context, shop_url):
        """爬取单个店铺"""
        page = await context.new_page()

        try:
            # 访问店铺页面
            logger.info(f"访问店铺页面: {shop_url}")
            await page.goto(shop_url, wait_until='networkidle')
            await asyncio.sleep(2)

            # 点击"查看全部"按钮
            view_all_selector = "body > div.main-box > div:nth-child(16) > div.content.clearfix > div.content-main > div:nth-child(8) > div > div.more_goods > a"

            try:
                await page.wait_for_selector(view_all_selector, timeout=10000)
                await page.click(view_all_selector)
                logger.info("已点击查看全部按钮")
                await asyncio.sleep(3)

                # 等待列表页面加载
                await page.wait_for_load_state('networkidle')

                # 开始爬取分页数据
                await self.scrape_paginated_books(page, shop_url)

            except Exception as e:
                logger.error(f"点击查看全部按钮失败: {e}")
                # 尝试其他可能的选择器
                alternative_selectors = [
                    "a[href*='itemlist']",
                    ".more_goods a",
                    "a:has-text('查看全部')",
                    "a:has-text('更多')"
                ]

                for selector in alternative_selectors:
                    try:
                        await page.click(selector)
                        logger.info(f"使用备用选择器 {selector} 成功")
                        await asyncio.sleep(3)
                        await self.scrape_paginated_books(page, shop_url)
                        break
                    except:
                        continue
                else:
                    logger.error("所有选择器都失败了")

        except Exception as e:
            logger.error(f"爬取店铺 {shop_url} 时出错: {e}")
        finally:
            await page.close()

    async def scrape_paginated_books(self, page, shop_url):
        """爬取分页的书籍列表"""
        current_page = 1
        max_pages = 50  # 设置最大页数限制，避免无限循环

        while current_page <= max_pages:
            logger.info(f"正在爬取第 {current_page} 页")

            try:
                # 等待书籍列表加载
                await page.wait_for_selector("#listBox", timeout=15000)
                await asyncio.sleep(2)

                # 获取当前页面的所有书籍链接
                book_links = await self.get_book_links(page)

                if not book_links:
                    logger.info("没有找到更多书籍，结束爬取")
                    break

                logger.info(f"第 {current_page} 页找到 {len(book_links)} 本书籍")

                # 爬取每本书的详情
                for i, book_link in enumerate(book_links):
                    logger.info(f"正在爬取第 {current_page} 页第 {i+1} 本书: {book_link}")
                    await self.scrape_book_detail(page.context, book_link, shop_url)

                    # 随机延迟
                    await asyncio.sleep(random.uniform(1, 3))

                # 尝试翻到下一页
                if not await self.go_to_next_page(page):
                    logger.info("没有下一页，结束爬取")
                    break

                current_page += 1
                await asyncio.sleep(random.uniform(2, 4))

            except Exception as e:
                logger.error(f"爬取第 {current_page} 页时出错: {e}")
                break

    async def get_book_links(self, page):
        """获取当前页面的所有书籍链接"""
        try:
            # 等待列表容器加载
            await page.wait_for_selector("#listBox", timeout=10000)

            # 获取所有书籍链接
            book_elements = await page.query_selector_all("#listBox .item-info .title a")

            book_links = []
            for element in book_elements:
                href = await element.get_attribute('href')
                if href:
                    # 转换为绝对URL
                    absolute_url = urljoin(page.url, href)
                    book_links.append(absolute_url)

            return book_links

        except Exception as e:
            logger.error(f"获取书籍链接失败: {e}")
            return []

    async def scrape_book_detail(self, context, book_url, shop_url):
        """爬取书籍详情页"""
        detail_page = await context.new_page()

        try:
            # 访问书籍详情页
            await detail_page.goto(book_url, wait_until='networkidle')
            await asyncio.sleep(2)

            # 目标选择器
            target_selector = "body > div.main-box > div.main.content > div.main-bot.clear-fix > div.right-block > ul > li.item-detail-page > div.major-info.clear-fix > div.major-info-main > div.major-info-text > div > ul.detail-list1 > li:nth-child(5)"

            book_info = {
                'shop_url': shop_url,
                'book_url': book_url,
                'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }

            try:
                # 等待目标元素加载
                await detail_page.wait_for_selector(target_selector, timeout=10000)
                target_element = await detail_page.query_selector(target_selector)

                if target_element:
                    target_text = await target_element.inner_text()
                    book_info['target_info'] = target_text.strip()
                    logger.info(f"成功提取目标信息: {target_text.strip()}")
                else:
                    book_info['target_info'] = "未找到目标元素"
                    logger.warning("未找到目标元素")

            except Exception as e:
                book_info['target_info'] = f"提取失败: {str(e)}"
                logger.error(f"提取目标信息失败: {e}")

            # 尝试提取其他有用信息
            try:
                # 书名
                title_selectors = [
                    "h1.title",
                    ".book-title",
                    ".item-title",
                    "h1"
                ]

                for selector in title_selectors:
                    try:
                        title_element = await detail_page.query_selector(selector)
                        if title_element:
                            book_info['title'] = await title_element.inner_text()
                            break
                    except:
                        continue

                # 价格
                price_selectors = [
                    ".price",
                    ".book-price",
                    "[class*='price']"
                ]

                for selector in price_selectors:
                    try:
                        price_element = await detail_page.query_selector(selector)
                        if price_element:
                            book_info['price'] = await price_element.inner_text()
                            break
                    except:
                        continue

                # 作者
                author_selectors = [
                    ".author",
                    "[class*='author']",
                    "ul.detail-list1 li:nth-child(1)",
                    "ul.detail-list1 li:nth-child(2)"
                ]

                for selector in author_selectors:
                    try:
                        author_element = await detail_page.query_selector(selector)
                        if author_element:
                            author_text = await author_element.inner_text()
                            if '作者' in author_text or '著' in author_text:
                                book_info['author'] = author_text.strip()
                                break
                    except:
                        continue

            except Exception as e:
                logger.error(f"提取额外信息失败: {e}")

            # 添加到结果列表
            self.results.append(book_info)
            logger.info(f"成功爬取书籍信息: {book_info.get('title', '未知书名')}")

        except Exception as e:
            logger.error(f"爬取书籍详情 {book_url} 失败: {e}")
        finally:
            await detail_page.close()

    async def go_to_next_page(self, page):
        """翻到下一页"""
        try:
            # 寻找下一页按钮
            next_page_selectors = [
                "a:has-text('下一页')",
                ".next",
                "[class*='next']",
                "a[href*='page']",
                ".pagination a:last-child"
            ]

            for selector in next_page_selectors:
                try:
                    next_button = await page.query_selector(selector)
                    if next_button:
                        # 检查按钮是否可点击
                        is_disabled = await next_button.get_attribute('disabled')
                        class_name = await next_button.get_attribute('class') or ''

                        if not is_disabled and 'disabled' not in class_name:
                            await next_button.click()
                            logger.info("成功翻到下一页")
                            await page.wait_for_load_state('networkidle')
                            return True
                except Exception as e:
                    logger.debug(f"选择器 {selector} 失败: {e}")
                    continue

            logger.info("没有找到下一页按钮或已到最后一页")
            return False

        except Exception as e:
            logger.error(f"翻页失败: {e}")
            return False

    def save_results(self, filename_prefix="kongfz_books"):
        """保存结果到文件"""
        if not self.results:
            logger.warning("没有数据可保存")
            return

        timestamp = time.strftime('%Y%m%d_%H%M%S')

        # 保存为JSON
        json_filename = f"{filename_prefix}_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        logger.info(f"结果已保存到 {json_filename}")

        # 保存为CSV
        csv_filename = f"{filename_prefix}_{timestamp}.csv"
        if self.results:
            fieldnames = self.results[0].keys()
            with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.results)
            logger.info(f"结果已保存到 {csv_filename}")

        logger.info(f"总共爬取了 {len(self.results)} 本书籍的信息")

async def main():
    """主函数"""
    # 店铺URL列表 - 用户输入
    shop_urls = [
        "https://shop.kongfz.com/534779",
        "https://shop.kongfz.com/726495",
        "https://shop.kongfz.com/269228"
    ]

    # 创建爬虫实例
    scraper = KongfzShopScraper(
        headless=False,  # 有头模式，用户可以看到浏览器
        slow_mo=1000     # 放慢操作速度，避免被检测
    )

    try:
        print("🚀 启动孔夫子旧书网爬虫...")

        # 预处理 - 用户登录
        if not await scraper.pre_login_setup():
            print("❌ 用户取消操作，程序退出")
            return

        # 开始爬取
        logger.info("开始爬取孔夫子旧书网店铺...")
        results = await scraper.scrape_shops(shop_urls)

        # 保存结果
        scraper.save_results()

        print("\n" + "="*60)
        print(f"🎉 爬取完成! 总共获取了 {len(scraper.results)} 本书籍信息")
        print("📁 数据已保存为 JSON 和 CSV 格式")
        print("="*60)

    except Exception as e:
        logger.error(f"程序执行出错: {e}")
        print(f"❌ 程序执行出错: {e}")

# 添加一个独立的测试登录功能
async def test_login_only():
    """仅测试登录功能"""
    scraper = KongfzShopScraper(headless=False, slow_mo=1000)

    print("🧪 测试登录功能...")
    success = await scraper.pre_login_setup()

    if success:
        print("✅ 登录测试成功!")
    else:
        print("❌ 登录测试失败或用户取消")

# 添加一个快速爬取功能（跳过登录）
async def quick_scrape():
    """快速爬取（跳过登录步骤）"""
    shop_urls = [
        "https://shop.kongfz.com/534779",
        "https://shop.kongfz.com/726495",
        "https://shop.kongfz.com/269228"
    ]

    scraper = KongfzShopScraper(headless=False, slow_mo=1000)

    # 直接启动浏览器
    async with async_playwright() as p:
        scraper.browser = await p.chromium.launch(headless=False, slow_mo=1000)
        scraper.context = await scraper.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        print("🚀 快速模式启动，跳过登录直接爬取...")
        results = await scraper.scrape_shops(shop_urls)
        scraper.save_results()
        print(f"🎉 快速爬取完成! 获取了 {len(results)} 本书籍信息")

if __name__ == "__main__":
    import sys

    print("🌟 孔夫子旧书网爬虫程序")
    print("请选择运行模式:")
    print("1. 完整模式 (包含登录步骤)")
    print("2. 快速模式 (跳过登录)")
    print("3. 仅测试登录")

    choice = input("\n请输入选择 (1/2/3): ").strip()

    if choice == "1":
        print("🔐 启动完整模式...")
        asyncio.run(main())
    elif choice == "2":
        print("⚡ 启动快速模式...")
        asyncio.run(quick_scrape())
    elif choice == "3":
        print("🧪 启动登录测试...")
        asyncio.run(test_login_only())
    else:
        print("❌ 无效选择，使用默认完整模式")
        asyncio.run(main())
