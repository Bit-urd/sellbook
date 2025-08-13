#!/usr/bin/env python3
"""
书籍销售记录分析器
从books_data.csv读取书籍信息，然后爬取孔夫子网的销售记录
分析每本书的售出时间和价格，生成销售统计
"""
import asyncio
import csv
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
from playwright.async_api import async_playwright
import aiohttp

class SalesAnalyzer:
    def __init__(self, books_file="books_data.csv", sales_file="book_sales.csv"):
        self.books_file = books_file
        self.sales_file = sales_file
        self.browser = None
        self.page = None
        self.playwright = None
        
        # 销售数据存储
        self.sales_data = []  # 每条销售记录
        self.daily_stats = defaultdict(int)  # 每日销量统计
        
        # 时间限制 (只分析最近30天的数据)
        self.days_limit = 30
        self.cutoff_date = datetime.now() - timedelta(days=self.days_limit)
        
    def load_books_data(self, limit=5):
        """加载书籍数据，用于测试只加载前5条"""
        books = []
        
        if not os.path.exists(self.books_file):
            print(f"❌ 书籍数据文件不存在: {self.books_file}")
            return books
        
        try:
            with open(self.books_file, 'r', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for i, row in enumerate(reader):
                    if limit and i >= limit:
                        break
                    
                    isbn = row.get('isbn', '').strip()
                    title = row.get('title', '').strip()
                    itemid = row.get('itemid', '').strip()
                    
                    if isbn and title:
                        books.append({
                            'isbn': isbn,
                            'title': title,
                            'itemid': itemid,
                            'shopid': row.get('shopid', ''),
                            'price': row.get('price', '')
                        })
                
                print(f"📚 加载了 {len(books)} 本书的信息")
                return books
                
        except Exception as e:
            print(f"❌ 加载书籍数据失败: {e}")
            return books

    async def connect_to_chrome(self):
        """连接到Chrome浏览器"""
        print("🔗 连接Chrome浏览器...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:9222/json/version") as response:
                    if response.status == 200:
                        version_info = await response.json()
                        ws_url = version_info.get('webSocketDebuggerUrl', '')
                        print("✅ Chrome已启动")
                    else:
                        print("❌ Chrome未启动")
                        return False
        except Exception as e:
            print(f"❌ Chrome连接失败: {e}")
            return False
        
        self.playwright = await async_playwright().start()
        
        try:
            self.browser = await self.playwright.chromium.connect_over_cdp(ws_url)
            
            # 使用现有的浏览器上下文，不创建新的
            contexts = self.browser.contexts
            if contexts:
                context = contexts[0]
                print("✅ 使用现有浏览器上下文")
            else:
                context = await self.browser.new_context()
                print("✅ 创建新的浏览器上下文")
            
            # 使用现有页面或创建新页面
            pages = context.pages
            if pages:
                self.page = pages[0]
                print("✅ 使用现有页面标签")
            else:
                self.page = await context.new_page()
                print("✅ 创建新页面标签")
            
            print("✅ 成功连接到Chrome")
            return True
            
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            if self.playwright:
                await self.playwright.stop()
            return False

    async def analyze_book_sales(self, book):
        """分析单本书的销售记录"""
        isbn = book['isbn']
        title = book['title']
        
        print(f"\n📖 分析书籍: {title}")
        print(f"📄 ISBN: {isbn}")
        
        # 构建搜索URL
        search_url = f"https://search.kongfz.com/product/?keyword={isbn}&dataType=1&sortType=10&page=1&actionPath=sortType,quality&quality=90~&quaSelect=2"
        
        try:
            print(f"🔍 访问搜索页面...")
            await self.page.goto(search_url, wait_until='networkidle')
            await asyncio.sleep(3)
            
            book_sales = []
            page_num = 1
            max_pages = 20  # 最大翻页数
            
            while page_num <= max_pages:
                print(f"📄 分析第 {page_num} 页...")
                
                # 等待页面加载
                await asyncio.sleep(2)
                
                # 提取当前页面的销售记录
                page_sales = await self.extract_sales_records()
                
                if not page_sales:
                    print(f"📋 第 {page_num} 页没有销售记录")
                    break
                
                # 检查时间限制
                has_old_records = False
                valid_sales = []
                
                for sale in page_sales:
                    sale_date = self.parse_sale_date(sale.get('sold_time', ''))
                    if sale_date and sale_date >= self.cutoff_date:
                        sale['book_isbn'] = isbn
                        sale['sale_date'] = sale_date
                        valid_sales.append(sale)
                    else:
                        has_old_records = True
                
                if valid_sales:
                    book_sales.extend(valid_sales)
                    print(f"📚 第 {page_num} 页找到 {len(valid_sales)} 条有效销售记录")
                else:
                    print(f"📋 第 {page_num} 页没有有效销售记录")
                
                # 如果发现超过时间限制的记录，停止翻页
                if has_old_records:
                    print(f"⏰ 发现超过{self.days_limit}天的记录，停止翻页")
                    break
                
                # 尝试翻到下一页
                if not await self.go_to_next_page():
                    print(f"📄 已达到最后一页")
                    break
                
                page_num += 1
                await asyncio.sleep(3)
            
            # 保存这本书的销售数据
            self.sales_data.extend(book_sales)
            
            # 更新每日统计
            for sale in book_sales:
                date_str = sale['sale_date'].strftime('%Y-%m-%d')
                self.daily_stats[date_str] += 1
            
            print(f"✅ 书籍 {title} 分析完成，找到 {len(book_sales)} 条销售记录")
            
        except Exception as e:
            print(f"❌ 分析书籍 {title} 时出错: {e}")

    async def extract_sales_records(self):
        """提取当前页面的销售记录"""
        try:
            sales_records = await self.page.evaluate("""
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
                            
                            // 不再提取书籍链接和显示标题
                            
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
            
            return sales_records
            
        except Exception as e:
            print(f"❌ 提取销售记录失败: {e}")
            return []

    def parse_sale_date(self, sold_time):
        """解析售出时间字符串"""
        try:
            # 格式: "2025-08-13 已售"
            if not sold_time or '已售' not in sold_time:
                return None
            
            date_str = sold_time.replace(' 已售', '').strip()
            return datetime.strptime(date_str, '%Y-%m-%d')
            
        except Exception as e:
            print(f"⚠️ 解析时间失败: {sold_time}, 错误: {e}")
            return None

    async def go_to_next_page(self):
        """翻到下一页"""
        try:
            # 查找下一页按钮
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
            
        except Exception as e:
            print(f"❌ 翻页失败: {e}")
            return False

    def save_sales_data(self):
        """保存销售数据到CSV文件"""
        if not self.sales_data:
            print("❌ 没有销售数据可保存")
            return
        
        # 保存详细销售记录
        detail_filename = f"sales_detail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        fieldnames = ['book_isbn', 'sale_date', 'sold_time', 'price', 'quality']
        
        try:
            with open(detail_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for sale in self.sales_data:
                    row = {field: sale.get(field, '') for field in fieldnames}
                    writer.writerow(row)
            
            print(f"💾 详细销售记录已保存到 {detail_filename}")
            
        except Exception as e:
            print(f"❌ 保存详细记录失败: {e}")
        
        # 保存每日统计
        if self.daily_stats:
            try:
                with open(self.sales_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['date', 'sales_count'])
                    
                    # 按日期排序
                    sorted_dates = sorted(self.daily_stats.keys())
                    for date in sorted_dates:
                        writer.writerow([date, self.daily_stats[date]])
                
                print(f"📊 每日销售统计已保存到 {self.sales_file}")
                
            except Exception as e:
                print(f"❌ 保存统计数据失败: {e}")

    def print_statistics(self):
        """打印统计信息"""
        print("\n" + "="*60)
        print("📊 销售分析统计")
        print("="*60)
        print(f"总销售记录: {len(self.sales_data)} 条")
        print(f"统计天数: {len(self.daily_stats)} 天")
        
        if self.daily_stats:
            total_sales = sum(self.daily_stats.values())
            avg_daily = total_sales / len(self.daily_stats)
            print(f"总销量: {total_sales} 本")
            print(f"日均销量: {avg_daily:.1f} 本")
            
            # 显示最近5天的数据
            recent_dates = sorted(self.daily_stats.keys())[-5:]
            print(f"\n📈 最近销售情况:")
            for date in recent_dates:
                print(f"  {date}: {self.daily_stats[date]} 本")
        
        print("="*60)

    async def run(self):
        """主运行方法"""
        try:
            print("📊 启动书籍销售分析器...")
            
            # 加载书籍数据 (测试模式：只加载前5本)
            books = self.load_books_data(limit=5)
            if not books:
                print("❌ 没有书籍数据可分析")
                return
            
            # 连接Chrome
            if not await self.connect_to_chrome():
                print("❌ 无法连接Chrome，请先启动Chrome调试模式")
                return
            
            # 逐本分析书籍销售记录
            for i, book in enumerate(books, 1):
                print(f"\n{'='*20} 进度: {i}/{len(books)} {'='*20}")
                
                try:
                    await self.analyze_book_sales(book)
                    
                    # 书籍间延迟
                    if i < len(books):
                        print("⏳ 等待3秒后继续下一本书...")
                        await asyncio.sleep(3)
                        
                except Exception as e:
                    print(f"❌ 分析书籍失败: {e}")
            
            # 保存结果
            self.save_sales_data()
            
            # 打印统计信息
            self.print_statistics()
            
        except KeyboardInterrupt:
            print("\n⏹️ 用户中断分析")
            if self.sales_data:
                print("💾 保存已分析的数据...")
                self.save_sales_data()
                self.print_statistics()
            
        except Exception as e:
            print(f"❌ 程序执行出错: {e}")
            
        finally:
            if self.playwright:
                await self.playwright.stop()
            print("🔌 已断开连接")

async def main():
    """程序入口"""
    analyzer = SalesAnalyzer()
    await analyzer.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序已退出")
    except Exception as e:
        print(f"❌ 程序异常退出: {e}")