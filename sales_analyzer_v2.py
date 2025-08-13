#!/usr/bin/env python3
"""
书籍销售记录分析器 - 数据库版本
从SQLite数据库读取书籍信息，然后爬取孔夫子网的销售记录
分析每本书的售出时间和价格，生成销售统计并保存到数据库
"""
import asyncio
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
from playwright.async_api import async_playwright
import aiohttp

from database import DatabaseManager, BookRepository, SalesRepository

class SalesAnalyzerV2:
    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None
        
        # 数据库操作
        self.book_repo = BookRepository()
        self.sales_repo = SalesRepository()
        
        # 销售数据存储
        self.sales_data = []  # 每条销售记录
        self.daily_stats = defaultdict(int)  # 每日销量统计
        
        # 时间限制 (只分析最近30天的数据)
        self.days_limit = 30
        self.cutoff_date = datetime.now() - timedelta(days=self.days_limit)
        
    async def load_books_from_database(self, limit=None):
        """从数据库加载书籍数据"""
        books = []
        
        try:
            # 初始化数据库
            db_manager = DatabaseManager()
            await db_manager.init_database()
            
            # 这里可以添加更复杂的查询逻辑
            # 暂时返回空列表，实际使用时需要实现具体的查询方法
            print(f"📚 从数据库加载书籍数据...")
            
            # TODO: 实现从数据库获取书籍列表的方法
            # 可以根据ISBN、店铺ID等条件筛选
            
            return books
            
        except Exception as e:
            print(f"❌ 从数据库加载书籍数据失败: {e}")
            return books

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
            else:
                context = await self.browser.new_context()
            
            # 使用现有页面或创建新页面
            pages = context.pages
            if pages:
                self.page = pages[0]
            else:
                self.page = await context.new_page()
            
            return True
            
        except Exception as e:
            print(f"❌ Playwright连接失败: {e}")
            return False

    async def analyze_book_sales(self, book_info):
        """分析单本书的销售记录"""
        isbn = book_info.get('isbn', '')
        title = book_info.get('title', '')
        itemid = book_info.get('itemid', '')
        
        if not isbn:
            print(f"⚠️  书籍 {title} 缺少ISBN，跳过")
            return []
        
        print(f"🔍 分析书籍: {title} (ISBN: {isbn})")
        
        # 构建搜索URL
        search_url = f"https://search.kongfz.com/product/?keyword={isbn}&dataType=1&sortType=10&page=1&actionPath=sortType,quality&quality=90~&quaSelect=2"
        
        all_sales = []
        
        try:
            await self.page.goto(search_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            page_num = 1
            max_pages = 20  # 限制最大页数
            
            while page_num <= max_pages:
                await asyncio.sleep(1)
                
                # 提取当前页面的销售记录
                page_sales = await self.extract_sales_records()
                
                if not page_sales:
                    break
                
                # 检查时间限制并处理数据
                has_old_records = False
                valid_sales = []
                
                for sale in page_sales:
                    sale_date = self.parse_sale_date(sale.get('sold_time', ''))
                    if sale_date and sale_date >= self.cutoff_date:
                        # 补充书籍信息
                        sale['book_isbn'] = isbn
                        sale['book_title'] = title
                        sale['sale_date'] = sale_date.strftime('%Y-%m-%d')
                        sale['display_title'] = title
                        
                        valid_sales.append(sale)
                        
                        # 更新每日统计
                        date_str = sale_date.strftime('%Y-%m-%d')
                        self.daily_stats[date_str] += 1
                    else:
                        has_old_records = True
                
                if valid_sales:
                    all_sales.extend(valid_sales)
                    print(f"  📄 第{page_num}页: 找到 {len(valid_sales)} 条有效销售记录")
                
                # 如果发现超过时间限制的记录，停止翻页
                if has_old_records:
                    print(f"  ⏰ 发现超出时间限制的记录，停止翻页")
                    break
                
                # 尝试翻到下一页
                if not await self.go_to_next_page():
                    break
                
                page_num += 1
                await asyncio.sleep(2)
            
            print(f"  ✅ 完成分析，共找到 {len(all_sales)} 条销售记录")
            return all_sales
            
        except Exception as e:
            print(f"  ❌ 分析失败: {e}")
            return []

    async def extract_sales_records(self):
        """提取当前页面的销售记录"""
        try:
            return await self.page.evaluate("""
                () => {
                    const sales = [];
                    const productItems = document.querySelectorAll('.product-item-wrap');
                    
                    productItems.forEach(item => {
                        try {
                            const record = {};
                            
                            // 提取售出时间
                            const soldTimeElement = item.querySelector('.sold-time');
                            if (soldTimeElement) {
                                record.sold_time = soldTimeElement.textContent.trim();
                            }
                            
                            // 提取价格信息
                            const priceElement = item.querySelector('.price-info');
                            if (priceElement) {
                                const priceInt = item.querySelector('.price-int');
                                const priceFloat = item.querySelector('.price-float');
                                if (priceInt && priceFloat) {
                                    record.price = priceInt.textContent + '.' + priceFloat.textContent;
                                }
                            }
                            
                            // 提取品相
                            const qualityElement = item.querySelector('.quality-info');
                            if (qualityElement) {
                                record.quality = qualityElement.textContent.trim();
                            }
                            
                            // 提取书籍链接
                            const linkElement = item.querySelector('a[href*="book.kongfz.com"]');
                            if (linkElement) {
                                record.book_link = linkElement.href;
                            }
                            
                            // 只保留有售出时间的记录
                            if (record.sold_time && record.sold_time.includes('已售')) {
                                sales.push(record);
                            }
                            
                        } catch (error) {
                            console.log('提取销售记录时出错:', error);
                        }
                    });
                    
                    return sales;
                }
            """)
        except:
            return []

    def parse_sale_date(self, sold_time):
        """解析售出时间字符串"""
        try:
            if not sold_time or '已售' not in sold_time:
                return None
            
            date_str = sold_time.replace(' 已售', '').strip()
            return datetime.strptime(date_str, '%Y-%m-%d')
        except:
            return None

    async def go_to_next_page(self):
        """翻到下一页"""
        try:
            next_selectors = [
                '.pagination .next:not(.disabled)',
                '.pagination a[title="下一页"]',
                '.page-next:not(.disabled)',
                'a:has-text("下一页"):not(.disabled)'
            ]
            
            for selector in next_selectors:
                try:
                    next_btn = await self.page.query_selector(selector)
                    if next_btn:
                        await next_btn.click()
                        await self.page.wait_for_load_state('networkidle')
                        return True
                except:
                    continue
            
            return False
        except:
            return False

    async def save_sales_to_database(self):
        """将销售数据保存到数据库"""
        if not self.sales_data:
            print("📝 没有销售数据需要保存")
            return
        
        try:
            # 保存详细销售记录
            saved_count = await self.sales_repo.save_sales_data(self.sales_data)
            print(f"💾 已保存 {saved_count} 条销售记录到数据库")
            
            # 保存每日统计数据
            await self.save_daily_stats()
            
        except Exception as e:
            print(f"❌ 保存销售数据到数据库失败: {e}")

    async def save_daily_stats(self):
        """保存每日销售统计"""
        if not self.daily_stats:
            return
        
        try:
            # 这里可以实现具体的每日统计保存逻辑
            # 目前只是打印统计信息
            print("\n📊 每日销售统计:")
            for date, count in sorted(self.daily_stats.items()):
                print(f"  {date}: {count} 本")
                
        except Exception as e:
            print(f"❌ 保存每日统计失败: {e}")

    def print_summary(self):
        """打印分析摘要"""
        if not self.sales_data:
            print("📊 没有找到任何销售记录")
            return
        
        print("\n" + "="*50)
        print("📊 销售分析摘要")
        print("="*50)
        
        # 基本统计
        total_records = len(self.sales_data)
        print(f"📚 总销售记录数: {total_records}")
        print(f"📅 分析时间范围: 最近{self.days_limit}天")
        print(f"📆 分析日期区间: {self.cutoff_date.strftime('%Y-%m-%d')} 至 {datetime.now().strftime('%Y-%m-%d')}")
        
        # 价格统计
        prices = []
        for sale in self.sales_data:
            try:
                price = float(sale.get('price', 0))
                if price > 0:
                    prices.append(price)
            except:
                continue
        
        if prices:
            print(f"💰 价格统计:")
            print(f"  最低价: ¥{min(prices):.2f}")
            print(f"  最高价: ¥{max(prices):.2f}")
            print(f"  平均价: ¥{sum(prices)/len(prices):.2f}")
        
        # 每日统计
        if self.daily_stats:
            print(f"📈 每日销量分布: {len(self.daily_stats)} 个销售日")
            avg_daily = sum(self.daily_stats.values()) / len(self.daily_stats)
            print(f"📊 平均日销量: {avg_daily:.1f} 本")
        
        print("="*50)

    async def run(self, book_limit=5):
        """运行销售分析"""
        print(f"🚀 启动书籍销售记录分析器 (数据库版)")
        print(f"⏰ 分析时间范围: 最近{self.days_limit}天")
        
        # 1. 连接到Chrome
        if not await self.connect_to_chrome():
            print("❌ 无法连接到Chrome，请先启动Chrome调试模式")
            return
        
        # 2. 从数据库加载书籍数据
        books = await self.load_books_from_database(limit=book_limit)
        
        if not books:
            print("❌ 没有找到书籍数据，请先运行爬虫收集书籍信息")
            return
        
        print(f"📚 准备分析 {len(books)} 本书籍")
        
        try:
            # 3. 逐本书籍分析
            for i, book in enumerate(books, 1):
                print(f"\n{'='*20} 书籍 {i}/{len(books)} {'='*20}")
                
                # 分析单本书
                book_sales = await self.analyze_book_sales(book)
                
                if book_sales:
                    self.sales_data.extend(book_sales)
                
                # 书籍间等待
                if i < len(books):
                    print("⏳ 等待 3 秒...")
                    await asyncio.sleep(3)
            
            # 4. 保存分析结果
            print(f"\n💾 保存分析结果到数据库...")
            await self.save_sales_to_database()
            
            # 5. 打印分析摘要
            self.print_summary()
            
        except KeyboardInterrupt:
            print("\n⚠️  用户中断分析")
            if self.sales_data:
                await self.save_sales_to_database()
            self.print_summary()
        except Exception as e:
            print(f"\n❌ 分析过程出错: {e}")
            if self.sales_data:
                await self.save_sales_to_database()
            self.print_summary()
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

# 单独分析指定ISBN的便捷函数
async def analyze_single_isbn(isbn: str):
    """分析单个ISBN的销售记录"""
    analyzer = SalesAnalyzerV2()
    
    if not await analyzer.connect_to_chrome():
        print("❌ 无法连接到Chrome")
        return
    
    book_info = {
        'isbn': isbn,
        'title': f'ISBN {isbn}',
        'itemid': isbn
    }
    
    try:
        sales = await analyzer.analyze_book_sales(book_info)
        analyzer.sales_data = sales
        
        await analyzer.save_sales_to_database()
        analyzer.print_summary()
        
    finally:
        await analyzer.cleanup()

async def main():
    """主函数"""
    import sys
    
    if len(sys.argv) > 1:
        # 如果提供了ISBN参数，分析单个ISBN
        isbn = sys.argv[1]
        await analyze_single_isbn(isbn)
    else:
        # 否则分析数据库中的书籍
        analyzer = SalesAnalyzerV2()
        await analyzer.run(book_limit=5)

if __name__ == "__main__":
    asyncio.run(main())