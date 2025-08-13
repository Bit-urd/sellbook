#!/usr/bin/env python3
"""
增量式多店铺爬虫 - 支持断点续爬和去重
- 每页数据立即保存到CSV
- 启动时加载已有数据，自动去重
- 已爬取的书籍不再重复爬取
"""
import asyncio
import csv
import os
import time
from datetime import datetime
from playwright.async_api import async_playwright
import aiohttp

class IncrementalScraper:
    def __init__(self, shop_list_file="shop_list.txt", data_file="books_data.csv"):
        self.shop_list_file = shop_list_file
        self.data_file = data_file
        self.browser = None
        self.page = None
        self.playwright = None
        
        # 已爬取的书籍集合(用于快速去重)
        self.scraped_itemids = set()
        self.scraped_count = 0
        
        # CSV字段定义
        self.fieldnames = [
            'itemid', 'shopid', 'isbn', 'title', 'author', 'publisher', 
            'publish_year', 'quality', 'price', 'display_price', 
            'book_url', 'catnum', 'userid', 'scraped_time', 'scraped_shop_id', 'scraped_page'
        ]
        
        # 统计信息
        self.stats = {
            'existing_records': 0,
            'new_records': 0,
            'duplicate_skipped': 0,
            'shops_processed': 0,
            'pages_processed': 0
        }

    def load_existing_data(self):
        """加载已有的CSV数据，构建去重集合"""
        print("📂 检查已有数据文件...")
        
        if not os.path.exists(self.data_file):
            print(f"📝 数据文件不存在，将创建新文件: {self.data_file}")
            self.create_csv_file()
            return
        
        try:
            with open(self.data_file, 'r', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    itemid = row.get('itemid', '').strip()
                    if itemid:
                        self.scraped_itemids.add(itemid)
                        self.scraped_count += 1
            
            self.stats['existing_records'] = self.scraped_count
            print(f"📊 加载已有数据: {self.scraped_count} 条记录")
            print(f"🔍 去重集合大小: {len(self.scraped_itemids)} 个ItemID")
            
        except Exception as e:
            print(f"❌ 加载已有数据失败: {e}")
            print("🔄 将创建新的数据文件")
            self.create_csv_file()

    def create_csv_file(self):
        """创建新的CSV文件并写入表头"""
        try:
            with open(self.data_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                writer.writeheader()
            print(f"✅ 创建新数据文件: {self.data_file}")
        except Exception as e:
            print(f"❌ 创建CSV文件失败: {e}")

    def append_to_csv(self, books_data):
        """追加新数据到CSV文件"""
        if not books_data:
            return 0
        
        new_records = 0
        duplicates = 0
        
        try:
            with open(self.data_file, 'a', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                
                for book in books_data:
                    itemid = book.get('itemid', '').strip()
                    
                    # 去重检查
                    if itemid in self.scraped_itemids:
                        duplicates += 1
                        continue
                    
                    # 添加时间戳
                    book['scraped_time'] = datetime.now().isoformat()
                    
                    # 确保所有字段都存在
                    row = {field: book.get(field, '') for field in self.fieldnames}
                    writer.writerow(row)
                    
                    # 更新去重集合
                    self.scraped_itemids.add(itemid)
                    new_records += 1
            
            self.stats['new_records'] += new_records
            self.stats['duplicate_skipped'] += duplicates
            
            if new_records > 0:
                print(f"💾 新增 {new_records} 条记录到 {self.data_file}")
            if duplicates > 0:
                print(f"🔄 跳过 {duplicates} 条重复记录")
            
            return new_records
            
        except Exception as e:
            print(f"❌ 追加数据到CSV失败: {e}")
            return 0

    def load_shop_list(self):
        """从文件加载店铺ID列表"""
        shop_ids = []
        
        if not os.path.exists(self.shop_list_file):
            print(f"❌ 店铺列表文件不存在: {self.shop_list_file}")
            return shop_ids
        
        try:
            with open(self.shop_list_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    if line.isdigit():
                        shop_ids.append(line)
                    else:
                        print(f"⚠️ 第{line_num}行格式错误，跳过: {line}")
            
            print(f"📋 加载了 {len(shop_ids)} 个店铺ID")
            return shop_ids
            
        except Exception as e:
            print(f"❌ 读取店铺列表失败: {e}")
            return shop_ids

    async def connect_to_chrome(self):
        """连接到真实Chrome浏览器"""
        print("🔗 连接真实Chrome浏览器...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:9222/json/version") as response:
                    if response.status == 200:
                        version_info = await response.json()
                        ws_url = version_info.get('webSocketDebuggerUrl', '')
                        print("✅ 检测到Chrome已启动")
                    else:
                        self.print_chrome_instructions()
                        return False
        except Exception as e:
            print(f"❌ Chrome连接失败: {e}")
            self.print_chrome_instructions()
            return False
        
        self.playwright = await async_playwright().start()
        
        try:
            self.browser = await self.playwright.chromium.connect_over_cdp(ws_url)
            context = await self.browser.new_context()
            self.page = await context.new_page()
            print("✅ 成功连接到Chrome浏览器")
            return True
            
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            if self.playwright:
                await self.playwright.stop()
            return False

    def print_chrome_instructions(self):
        """打印Chrome启动指令"""
        print("\n❌ Chrome未启动，请先启动Chrome调试模式:")
        print("macOS:")
        print("/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug-session")

    async def scrape_single_shop(self, shop_id):
        """爬取单个店铺的所有页面，实时保存每页数据"""
        shop_url = f"https://shop.kongfz.com/{shop_id}/all/"
        
        try:
            print(f"\n🏪 开始爬取店铺 {shop_id}")
            print(f"📍 访问: {shop_url}")
            
            await self.page.goto(shop_url, wait_until='networkidle')
            await asyncio.sleep(3)
            
            # 检查页面是否正确加载
            page_title = await self.page.title()
            if "404" in page_title or "找不到" in page_title:
                print(f"❌ 店铺 {shop_id} 不存在或无法访问")
                return
            
            try:
                await self.page.wait_for_selector("#listBox", timeout=10000)
            except:
                print(f"⚠️ 店铺 {shop_id} 列表页面加载异常，尝试继续")
            
            current_page = 1
            consecutive_empty_pages = 0
            max_empty_pages = 3
            
            while True:
                print(f"📄 爬取店铺 {shop_id} 第 {current_page} 页...")
                await asyncio.sleep(2)
                
                # 提取当前页面数据
                books_on_page = await self.extract_book_items()
                
                if not books_on_page:
                    consecutive_empty_pages += 1
                    print(f"📋 第 {current_page} 页没有数据")
                    
                    if consecutive_empty_pages >= max_empty_pages:
                        print(f"⏹️ 连续{max_empty_pages}页无数据，结束店铺 {shop_id}")
                        break
                else:
                    consecutive_empty_pages = 0
                    
                    # 为每本书添加爬取信息
                    for book in books_on_page:
                        book['scraped_shop_id'] = shop_id
                        book['scraped_page'] = current_page
                    
                    # 立即保存到CSV
                    new_count = self.append_to_csv(books_on_page)
                    print(f"📚 第 {current_page} 页: {len(books_on_page)} 本书，新增 {new_count} 本")
                    
                    self.stats['pages_processed'] += 1
                
                # 尝试翻页
                if not await self.go_to_next_page():
                    print(f"📄 店铺 {shop_id} 已达到最后一页")
                    break
                
                current_page += 1
                
                if current_page > 1000:  # 防止无限翻页
                    print(f"⚠️ 店铺 {shop_id} 达到最大页数限制")
                    break
                
                await asyncio.sleep(3)  # 翻页延迟
            
            self.stats['shops_processed'] += 1
            print(f"✅ 店铺 {shop_id} 爬取完成")
            
        except Exception as e:
            print(f"❌ 爬取店铺 {shop_id} 时出错: {e}")

    async def extract_book_items(self):
        """提取当前页面的书籍信息"""
        try:
            books_data = await self.page.evaluate("""
                () => {
                    const books = [];
                    const itemRows = document.querySelectorAll('.item-row');
                    
                    itemRows.forEach(row => {
                        try {
                            const book = {
                                shopid: row.getAttribute('shopid') || '',
                                itemid: row.getAttribute('itemid') || '',
                                isbn: row.getAttribute('isbn') || '',
                                catnum: row.getAttribute('catnum') || '',
                                userid: row.getAttribute('userid') || '',
                                price: row.getAttribute('price') || '',
                                title: '',
                                book_url: '',
                                author: '',
                                publisher: '',
                                publish_year: '',
                                quality: '',
                                display_price: ''
                            };
                            
                            const nameLink = row.querySelector('.row-name');
                            if (nameLink) {
                                book.title = nameLink.textContent.trim();
                                book.book_url = nameLink.href;
                            }
                            
                            const author = row.querySelector('.row-author');
                            if (author) book.author = author.textContent.trim();
                            
                            const publisher = row.querySelector('.row-press');
                            if (publisher) book.publisher = publisher.textContent.trim();
                            
                            const year = row.querySelector('.row-years');
                            if (year) book.publish_year = year.textContent.trim();
                            
                            const quality = row.querySelector('.row-quality');
                            if (quality) book.quality = quality.textContent.trim();
                            
                            const priceElement = row.querySelector('.row-price .bold');
                            if (priceElement) book.display_price = priceElement.textContent.trim();
                            
                            books.push(book);
                            
                        } catch (error) {
                            console.log('提取书籍信息时出错:', error);
                        }
                    });
                    
                    return books;
                }
            """)
            
            return books_data
            
        except Exception as e:
            print(f"❌ 提取书籍信息失败: {e}")
            return []

    async def go_to_next_page(self):
        """翻到下一页"""
        try:
            next_btn = await self.page.query_selector("#pagerBox > a.next-btn")
            
            if next_btn:
                class_name = await next_btn.get_attribute('class') or ''
                if 'disabled' not in class_name.lower():
                    await next_btn.click()
                    await self.page.wait_for_load_state('networkidle')
                    return True
            
            return False
            
        except Exception as e:
            print(f"❌ 翻页失败: {e}")
            return False

    def print_final_stats(self):
        """打印最终统计信息"""
        print("\n" + "="*60)
        print("📊 增量爬取完成统计")
        print("="*60)
        print(f"已有记录数: {self.stats['existing_records']}")
        print(f"新增记录数: {self.stats['new_records']}")
        print(f"跳过重复数: {self.stats['duplicate_skipped']}")
        print(f"处理店铺数: {self.stats['shops_processed']}")
        print(f"处理页面数: {self.stats['pages_processed']}")
        print(f"总记录数: {self.stats['existing_records'] + self.stats['new_records']}")
        print(f"数据文件: {self.data_file}")
        print("="*60)

    async def run(self):
        """主运行方法"""
        try:
            print("🚀 启动增量式多店铺爬虫...")
            
            # 加载已有数据
            self.load_existing_data()
            
            # 加载店铺列表
            shop_ids = self.load_shop_list()
            if not shop_ids:
                print("❌ 没有可爬取的店铺")
                return
            
            # 连接Chrome
            if not await self.connect_to_chrome():
                return
            
            # 逐个爬取店铺
            for i, shop_id in enumerate(shop_ids, 1):
                print(f"\n{'='*20} 进度: {i}/{len(shop_ids)} {'='*20}")
                
                try:
                    await self.scrape_single_shop(shop_id)
                    
                    # 店铺间延迟
                    if i < len(shop_ids):
                        print("⏳ 等待5秒后继续下一个店铺...")
                        await asyncio.sleep(5)
                        
                except Exception as e:
                    print(f"❌ 店铺 {shop_id} 爬取失败: {e}")
            
            # 打印统计信息
            self.print_final_stats()
            
        except KeyboardInterrupt:
            print("\n⏹️ 用户中断爬取")
            self.print_final_stats()
            
        except Exception as e:
            print(f"❌ 程序执行出错: {e}")
            
        finally:
            if self.playwright:
                await self.playwright.stop()
            print("🔌 已断开连接")

async def main():
    """程序入口"""
    scraper = IncrementalScraper()
    await scraper.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序已退出")
    except Exception as e:
        print(f"❌ 程序异常退出: {e}")