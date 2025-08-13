#!/usr/bin/env python3
"""
增量式多店铺爬虫 - 数据库版本
- 支持断点续爬和去重
- 每页数据立即保存到SQLite数据库
- 启动时从数据库加载已有数据，自动去重
"""
import asyncio
import os
import time
from datetime import datetime
from playwright.async_api import async_playwright
import aiohttp

from database import DatabaseManager, BookRepository

class IncrementalScraperV2:
    def __init__(self, shop_list_file="shop_list.txt"):
        self.shop_list_file = shop_list_file
        self.browser = None
        self.page = None
        self.playwright = None
        
        # 数据库操作
        self.book_repo = BookRepository()
        
        # 已爬取的书籍集合(用于快速去重)
        self.scraped_itemids = set()
        self.scraped_count = 0
        
        # 统计信息
        self.stats = {
            'existing_records': 0,
            'new_records': 0,
            'duplicate_skipped': 0,
            'shops_processed': 0,
            'pages_processed': 0
        }

    async def load_existing_data(self):
        """从数据库加载已有数据，构建去重集合"""
        print("📂 检查数据库中的已有数据...")
        
        try:
            # 初始化数据库
            db_manager = DatabaseManager()
            await db_manager.init_database()
            
            # 获取已存在的itemid
            self.scraped_itemids = await self.book_repo.get_existing_itemids()
            self.scraped_count = len(self.scraped_itemids)
            self.stats['existing_records'] = self.scraped_count
            
            if self.scraped_count > 0:
                print(f"📊 从数据库加载已有数据: {self.scraped_count} 条记录")
                print(f"🔍 去重集合大小: {len(self.scraped_itemids)} 个ItemID")
            else:
                print("📝 数据库为空，将开始全新爬取")
                
        except Exception as e:
            print(f"❌ 加载数据库数据失败: {e}")
            self.scraped_itemids = set()

    def load_shop_list(self):
        """加载店铺ID列表"""
        shops = []
        
        if not os.path.exists(self.shop_list_file):
            print(f"❌ 店铺列表文件不存在: {self.shop_list_file}")
            return shops
        
        with open(self.shop_list_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        shop_id = line.strip()
                        shops.append(shop_id)
                    except ValueError:
                        continue
        
        print(f"📋 加载了 {len(shops)} 个店铺ID")
        return shops

    async def connect_to_chrome(self):
        """连接到现有的Chrome调试会话"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:9222/json/version") as response:
                    if response.status == 200:
                        version_info = await response.json()
                        ws_url = version_info.get('webSocketDebuggerUrl', '')
                        print("✅ Chrome调试端口连接成功")
                    else:
                        print("❌ Chrome调试端口无响应")
                        return False
        except Exception as e:
            print(f"❌ 连接Chrome调试端口失败: {e}")
            return False
        
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(ws_url)
            
            # 使用现有浏览器上下文
            contexts = self.browser.contexts
            if contexts:
                context = contexts[0]
                print("🔄 使用现有浏览器上下文")
            else:
                context = await self.browser.new_context()
                print("🆕 创建新的浏览器上下文")
            
            # 使用现有页面或创建新页面
            pages = context.pages
            if pages:
                self.page = pages[0]
                print("🔄 使用现有页面")
            else:
                self.page = await context.new_page()
                print("🆕 创建新页面")
            
            return True
            
        except Exception as e:
            print(f"❌ Playwright连接失败: {e}")
            return False

    async def extract_page_data(self, shop_id: str, page_num: int):
        """提取当前页面的书籍数据"""
        try:
            books = await self.page.evaluate("""
                () => {
                    const books = [];
                    const bookItems = document.querySelectorAll('.item-info, .shopLineBookItem');
                    
                    bookItems.forEach(item => {
                        try {
                            const book = {};
                            
                            // 书籍链接和itemid
                            const linkElement = item.querySelector('a[href*="book.kongfz.com"]');
                            if (linkElement) {
                                book.book_url = linkElement.href;
                                const urlMatch = book.book_url.match(/\\/(\\d+)\\//);
                                if (urlMatch) {
                                    book.itemid = urlMatch[1];
                                }
                            }
                            
                            // 书名
                            const titleElement = item.querySelector('.title, .title-link, h3 a, .bookTitle');
                            if (titleElement) {
                                book.title = titleElement.textContent.trim();
                            }
                            
                            // 作者
                            const authorElement = item.querySelector('.author, .bookAuthor');
                            if (authorElement) {
                                book.author = authorElement.textContent.trim();
                            }
                            
                            // 出版社和出版年份
                            const publishElement = item.querySelector('.publish, .bookPub, .publisher');
                            if (publishElement) {
                                const publishText = publishElement.textContent.trim();
                                book.publisher = publishText.split(' ')[0] || '';
                                const yearMatch = publishText.match(/(\\d{4})/);
                                if (yearMatch) {
                                    book.publish_year = yearMatch[1];
                                }
                            }
                            
                            // ISBN
                            const isbnElement = item.querySelector('.isbn, [class*="isbn"]');
                            if (isbnElement) {
                                book.isbn = isbnElement.textContent.replace(/[^\\d]/g, '');
                            }
                            
                            // 价格
                            const priceElement = item.querySelector('.price, .bookPrice, .itemPrice');
                            if (priceElement) {
                                const priceText = priceElement.textContent.trim();
                                const priceMatch = priceText.match(/(\\d+\\.?\\d*)/);
                                if (priceMatch) {
                                    book.price = priceMatch[1];
                                    book.display_price = priceText;
                                }
                            }
                            
                            // 品相
                            const qualityElement = item.querySelector('.quality, .bookQuality');
                            if (qualityElement) {
                                book.quality = qualityElement.textContent.trim();
                            }
                            
                            // 其他信息
                            const catnumElement = item.querySelector('.catnum');
                            if (catnumElement) {
                                book.catnum = catnumElement.textContent.trim();
                            }
                            
                            const useridElement = item.querySelector('[data-userid]');
                            if (useridElement) {
                                book.userid = useridElement.getAttribute('data-userid');
                            }
                            
                            if (book.itemid && book.title) {
                                books.push(book);
                            }
                            
                        } catch (error) {
                            console.log('提取书籍信息时出错:', error);
                        }
                    });
                    
                    return books;
                }
            """)
            
            # 补充爬取信息
            current_time = datetime.now().isoformat()
            for book in books:
                book['shopid'] = shop_id
                book['scraped_time'] = current_time
                book['scraped_shop_id'] = shop_id
                book['scraped_page'] = page_num
            
            return books
            
        except Exception as e:
            print(f"❌ 提取页面数据失败: {e}")
            return []

    async def save_books_to_database(self, books_data):
        """保存书籍数据到数据库"""
        if not books_data:
            return 0
        
        try:
            saved_count = await self.book_repo.save_books(books_data)
            return saved_count
        except Exception as e:
            print(f"❌ 保存到数据库失败: {e}")
            return 0

    async def scrape_shop(self, shop_id: str):
        """爬取单个店铺的所有书籍"""
        print(f"\n🏪 开始爬取店铺 {shop_id}")
        
        shop_url = f"https://shop{shop_id}.kongfz.com/book/"
        
        try:
            await self.page.goto(shop_url, wait_until='networkidle')
            await asyncio.sleep(3)
            
            page_num = 1
            max_pages = 1000  # 设置最大页数限制
            consecutive_empty_pages = 0
            
            while page_num <= max_pages and consecutive_empty_pages < 3:
                print(f"📚 正在爬取第 {page_num} 页...")
                
                # 提取当前页面数据
                page_books = await self.extract_page_data(shop_id, page_num)
                
                if not page_books:
                    consecutive_empty_pages += 1
                    print(f"⚠️  第 {page_num} 页无数据，连续空页: {consecutive_empty_pages}")
                    if consecutive_empty_pages >= 3:
                        print("🔚 连续3页无数据，结束当前店铺爬取")
                        break
                else:
                    consecutive_empty_pages = 0
                
                # 去重处理
                new_books = []
                duplicate_count = 0
                
                for book in page_books:
                    itemid = book.get('itemid', '')
                    if itemid and itemid not in self.scraped_itemids:
                        new_books.append(book)
                        self.scraped_itemids.add(itemid)
                    else:
                        duplicate_count += 1
                
                # 保存新书籍到数据库
                if new_books:
                    saved_count = await self.save_books_to_database(new_books)
                    self.stats['new_records'] += saved_count
                    print(f"📚 第 {page_num} 页: {len(page_books)} 本书，新增 {len(new_books)} 本")
                    print(f"💾 成功保存 {saved_count} 条记录到数据库")
                else:
                    print(f"📚 第 {page_num} 页: {len(page_books)} 本书，新增 0 本")
                
                if duplicate_count > 0:
                    self.stats['duplicate_skipped'] += duplicate_count
                    print(f"🔄 跳过 {duplicate_count} 条重复记录")
                
                self.stats['pages_processed'] += 1
                
                # 如果整页都是重复数据，可能已经爬完了
                if duplicate_count == len(page_books) and len(page_books) > 0:
                    print("✅ 当前页全部为重复数据，可能已爬取完成")
                    break
                
                # 尝试翻到下一页
                if not await self.go_to_next_page():
                    print("📄 无法翻到下一页，结束当前店铺")
                    break
                
                page_num += 1
                await asyncio.sleep(2)  # 页面间隔
            
            self.stats['shops_processed'] += 1
            print(f"✅ 店铺 {shop_id} 爬取完成")
            
        except Exception as e:
            print(f"❌ 爬取店铺 {shop_id} 失败: {e}")

    async def go_to_next_page(self):
        """尝试翻到下一页"""
        try:
            # 常见的下一页选择器
            next_selectors = [
                'a.next:not(.disabled)',
                'a[title="下一页"]:not(.disabled)',
                '.pagination a.next',
                'a:has-text("下一页")',
                '.page-next:not(.disabled)'
            ]
            
            for selector in next_selectors:
                try:
                    next_btn = await self.page.query_selector(selector)
                    if next_btn:
                        await next_btn.click()
                        await self.page.wait_for_load_state('networkidle')
                        await asyncio.sleep(1)
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            print(f"翻页失败: {e}")
            return False

    def print_final_stats(self):
        """打印最终统计信息"""
        print("\n" + "="*50)
        print("📊 爬取完成统计")
        print("="*50)
        print(f"🏪 处理店铺数: {self.stats['shops_processed']}")
        print(f"📄 处理页面数: {self.stats['pages_processed']}")
        print(f"📚 原有记录数: {self.stats['existing_records']}")
        print(f"🆕 新增记录数: {self.stats['new_records']}")
        print(f"🔄 跳过重复数: {self.stats['duplicate_skipped']}")
        print(f"📊 总记录数: {self.stats['existing_records'] + self.stats['new_records']}")
        print("="*50)

    async def run(self):
        """运行增量爬虫"""
        print("🚀 启动增量式多店铺爬虫 (数据库版)")
        
        # 1. 加载已有数据
        await self.load_existing_data()
        
        # 2. 加载店铺列表
        shop_list = self.load_shop_list()
        if not shop_list:
            print("❌ 没有有效的店铺ID，退出")
            return
        
        # 3. 连接到Chrome
        if not await self.connect_to_chrome():
            print("❌ 无法连接到Chrome，请先启动Chrome调试模式")
            return
        
        try:
            # 4. 逐个店铺爬取
            for i, shop_id in enumerate(shop_list, 1):
                print(f"\n{'='*20} 店铺 {i}/{len(shop_list)} {'='*20}")
                await self.scrape_shop(shop_id)
                
                # 店铺间等待
                if i < len(shop_list):
                    print("⏳ 店铺间等待 5 秒...")
                    await asyncio.sleep(5)
            
            # 5. 打印最终统计
            self.print_final_stats()
            
        except KeyboardInterrupt:
            print("\n⚠️  用户中断爬取")
            self.print_final_stats()
        except Exception as e:
            print(f"\n❌ 爬取过程出错: {e}")
            self.print_final_stats()
        finally:
            await self.cleanup()

    async def cleanup(self):
        """清理资源"""
        try:
            if self.playwright:
                await self.playwright.stop()
                print("🧹 浏览器连接已关闭")
        except:
            pass

async def main():
    scraper = IncrementalScraperV2()
    await scraper.run()

if __name__ == "__main__":
    asyncio.run(main())