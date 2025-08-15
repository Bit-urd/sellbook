#!/usr/bin/env python3
"""
爬虫服务模块 - 负责数据抓取逻辑
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
from playwright.async_api import async_playwright, Page

from ..models.models import Shop, Book, BookInventory, SalesRecord, CrawlTask
from ..models.repositories import (
    ShopRepository, BookRepository, BookInventoryRepository, 
    SalesRepository, CrawlTaskRepository
)

logger = logging.getLogger(__name__)

class KongfuziCrawler:
    """孔夫子网爬虫"""
    
    # 全局封控等待时间（秒），使用类变量在所有实例间共享
    _rate_limit_wait_time = 0
    _max_wait_time = 16 * 60  # 最大等待时间：16分钟
    
    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None
        self.connected = False
        self.shop_repo = ShopRepository()
        self.book_repo = BookRepository()
        self.inventory_repo = BookInventoryRepository()
        self.sales_repo = SalesRepository()
        self.task_repo = CrawlTaskRepository()
    
    @classmethod
    def _update_rate_limit_wait_time(cls, success: bool = False):
        """更新全局封控等待时间
        
        Args:
            success: True表示请求成功，False表示遇到封控
        """
        if success:
            # 成功时重置等待时间为0
            cls._rate_limit_wait_time = 0
            logger.info("请求成功，重置封控等待时间为0")
        else:
            # 失败时使用指数退避：2分钟 -> 4分钟 -> 8分钟 -> 16分钟
            if cls._rate_limit_wait_time == 0:
                cls._rate_limit_wait_time = 2 * 60  # 首次封控：2分钟
            else:
                cls._rate_limit_wait_time = min(cls._rate_limit_wait_time * 2, cls._max_wait_time)
            
            logger.warning(f"遇到封控，更新等待时间为 {cls._rate_limit_wait_time // 60} 分钟")
    
    @classmethod
    def _get_current_wait_time(cls) -> int:
        """获取当前封控等待时间（秒）"""
        return cls._rate_limit_wait_time
    
    async def _safe_page_goto(self, url: str, **kwargs):
        """安全的页面跳转，成功时重置封控时间"""
        try:
            result = await self.page.goto(url, **kwargs)
            # 页面加载成功，重置封控等待时间
            self._update_rate_limit_wait_time(success=True)
            return result
        except Exception as e:
            # 如果是封控错误，会在上层处理
            raise e
    
    @classmethod
    def get_rate_limit_status(cls) -> dict:
        """获取当前封控状态信息"""
        wait_time = cls._rate_limit_wait_time
        return {
            "is_rate_limited": wait_time > 0,
            "current_wait_time_seconds": wait_time,
            "current_wait_time_minutes": wait_time // 60,
            "max_wait_time_minutes": cls._max_wait_time // 60,
            "next_wait_time_minutes": min(wait_time * 2, cls._max_wait_time) // 60 if wait_time > 0 else 2
        }
    
    async def connect_browser(self):
        """连接到Chrome浏览器"""
        if self.connected:
            return True
        
        try:
            # 尝试连接到已打开的Chrome调试端口
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:9222/json/version") as response:
                    if response.status == 200:
                        version_info = await response.json()
                        ws_url = version_info.get('webSocketDebuggerUrl', '')
                    else:
                        logger.error("无法获取Chrome调试信息")
                        return False
            
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
            
            self.connected = True
            logger.info("成功连接到Chrome浏览器")
            return True
            
        except Exception as e:
            logger.error(f"Chrome连接失败: {e}")
            return False
    
    async def disconnect_browser(self):
        """断开浏览器连接"""
        if self.playwright:
            await self.playwright.stop()
            self.connected = False
    
    async def analyze_book_sales(self, isbn: str, days_limit: int = 30, quality_filter: str = "high") -> Dict:
        """分析单本书的销售记录（用于实时ISBN搜索）
        
        Args:
            isbn: 书籍ISBN号
            days_limit: 天数限制
            quality_filter: 品相过滤 - "high" (九品以上) 或 "all" (全部品相)
        """
        if not await self.connect_browser():
            raise Exception("无法连接到Chrome浏览器")
        
        cutoff_date = datetime.now() - timedelta(days=days_limit)
        all_sales = []
        
        # 根据品相过滤构建搜索URL
        if quality_filter == "high":
            # 九品以上 (90分以上)
            search_url = f"https://search.kongfz.com/product/?dataType=1&keyword={isbn}&page=1&sortType=10&actionPath=sortType,quality&quality=90~&quaSelect=2"
        else:
            # 全部品相
            search_url = f"https://search.kongfz.com/product/?dataType=1&keyword={isbn}&page=1&sortType=10&actionPath=sortType"
        
        try:
            await self.page.goto(search_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            page_num = 1
            max_pages = 20
            
            while page_num <= max_pages:
                await asyncio.sleep(1)
                
                # 提取当前页面的销售记录
                page_sales = await self.extract_sales_records()
                
                if not page_sales:
                    break
                
                # 检查时间限制
                has_old_records = False
                valid_sales = []
                
                for sale in page_sales:
                    sale_date = self.parse_sale_date(sale.get('sold_time', ''))
                    if sale_date and sale_date >= cutoff_date:
                        sale['book_isbn'] = isbn
                        sale['sale_date'] = sale_date
                        valid_sales.append(sale)
                    else:
                        has_old_records = True
                
                if valid_sales:
                    all_sales.extend(valid_sales)
                
                # 如果发现超过时间限制的记录，停止翻页
                if has_old_records:
                    break
                
                # 尝试翻到下一页
                if not await self.go_to_next_page():
                    break
                
                page_num += 1
                await asyncio.sleep(2)
            
            # 计算统计数据
            stats = self.calculate_sales_stats(all_sales, isbn)
            return stats
            
        except Exception as e:
            logger.error(f"爬取ISBN {isbn} 销售数据失败: {e}")
            raise
    
    async def analyze_and_save_book_sales(self, isbn: str, shop_id: int, days_limit: int = 30) -> int:
        """分析并保存单本书的销售记录到数据库"""
        if not await self.connect_browser():
            raise Exception("无法连接到Chrome浏览器")
        
        cutoff_date = datetime.now() - timedelta(days=days_limit)
        total_saved = 0
        
        # 构建搜索URL - 爬取销售记录时使用全部品相
        search_url = f"https://search.kongfz.com/product/?dataType=1&keyword={isbn}&page=1&sortType=10&actionPath=sortType"
        
        try:
            await self._safe_page_goto(search_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            # 检查页面是否出现频率限制
            await self._check_page_for_rate_limit()
            
            page_num = 1
            max_pages = 10
            
            while page_num <= max_pages:
                await asyncio.sleep(1)
                
                # 提取当前页面的销售记录
                page_sales = await self.extract_sales_records()
                
                if not page_sales:
                    break
                
                # 处理和保存销售记录
                for sale in page_sales:
                    try:
                        sale_date = self.parse_sale_date(sale.get('sold_time', ''))
                        if not sale_date or sale_date < cutoff_date:
                            continue
                        
                        # 检查必需字段
                        item_id = sale.get('item_id', '')
                        if not item_id:
                            continue  # 跳过没有item_id的记录
                        
                        # 创建销售记录
                        sale_record = SalesRecord(
                            item_id=item_id,
                            isbn=isbn,
                            shop_id=shop_id,
                            sale_price=float(sale.get('price', 0)) if sale.get('price') else 0,
                            sale_date=sale_date,
                            sale_platform='kongfuzi',
                            book_condition=sale.get('quality', '')
                        )
                        
                        # 保存到数据库
                        self.sales_repo.create(sale_record)
                        total_saved += 1
                        
                        logger.debug(f"保存销售记录: ISBN={isbn}, 价格={sale_record.sale_price}, 时间={sale_date}")
                        
                    except Exception as e:
                        logger.error(f"保存销售记录失败: {e}")
                        continue
                
                # 尝试翻到下一页
                if not await self.go_to_next_page():
                    break
                
                page_num += 1
                await asyncio.sleep(2)
            
            logger.info(f"成功保存 {total_saved} 条销售记录")
            
            # 更新书籍的销售记录爬取时间和状态
            from ..models.database import db
            update_query = """
                UPDATE books 
                SET is_crawled = 1,
                    last_sales_update = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE isbn = ?
            """
            rows_updated = db.execute_update(update_query, (isbn,))
            
            if rows_updated > 0:
                logger.info(f"已更新ISBN {isbn} 的销售记录爬取状态和时间")
            else:
                logger.warning(f"未找到ISBN {isbn} 的书籍记录，无法更新爬取状态")
            
            return total_saved
            
        except Exception as e:
            logger.error(f"分析并保存ISBN {isbn} 销售数据失败: {e}")
            raise
    
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
                            
                            // 提取商品ID（优先级：data-id > href中的ID > 其他属性）
                            let itemId = '';
                            
                            // 方法1: 从data-id属性提取
                            if (item.dataset && item.dataset.id) {
                                itemId = item.dataset.id;
                            }
                            
                            // 方法2: 从链接href中提取商品ID
                            if (!itemId) {
                                const linkElement = item.querySelector('a[href*="book.kongfz.com"]');
                                if (linkElement && linkElement.href) {
                                    // 匹配孔夫子网的商品URL格式: book.kongfz.com/0/8032832601/
                                    const match = linkElement.href.match(/book\.kongfz\.com\/\d+\/(\d+)\//);
                                    if (match) {
                                        itemId = match[1];
                                    }
                                }
                            }
                            
                            // 方法3: 从其他可能的属性中提取
                            if (!itemId) {
                                const idMatch = item.outerHTML.match(/data-item[_-]?id=["']?(\d+)["']?/i);
                                if (idMatch) {
                                    itemId = idMatch[1];
                                }
                            }
                            
                            // 方法4: 从类名或其他属性中提取
                            if (!itemId) {
                                const classList = item.className;
                                const classIdMatch = classList.match(/item[_-]?(\d+)/);
                                if (classIdMatch) {
                                    itemId = classIdMatch[1];
                                }
                            }
                            
                            record.item_id = itemId;
                            
                            // 提取售出时间
                            const soldTimeElement = item.querySelector('.sold-time');
                            if (soldTimeElement) {
                                record.sold_time = soldTimeElement.textContent.trim();
                            }
                            
                            // 提取价格信息
                            const priceElement = item.querySelector('.price-info');
                            if (priceElement) {
                                const priceInt = priceElement.querySelector('.price-int');
                                const priceFloat = priceElement.querySelector('.price-float');
                                if (priceInt && priceFloat) {
                                    const intPart = priceInt.textContent.trim();
                                    const floatPart = priceFloat.textContent.trim();
                                    record.sale_price = parseFloat(intPart + '.' + floatPart);
                                }
                            }
                            
                            // 如果没有找到价格，尝试其他选择器
                            if (!record.sale_price) {
                                const priceSpan = item.querySelector('.price, .sale-price, .money');
                                if (priceSpan) {
                                    const priceText = priceSpan.textContent.replace(/[^0-9.]/g, '');
                                    if (priceText) {
                                        record.sale_price = parseFloat(priceText);
                                    }
                                }
                            }
                            
                            // 提取品相
                            const qualityElement = item.querySelector('.quality-info');
                            if (qualityElement) {
                                record.quality = qualityElement.textContent.trim();
                            }
                            
                            // 只保留有售出时间的记录，item_id可选
                            if (record.sold_time && record.sold_time.includes('已售')) {
                                // 如果没有item_id，生成一个临时ID
                                if (!record.item_id) {
                                    record.item_id = 'temp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                                }
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
    
    async def go_to_next_page(self):
        """翻到下一页"""
        try:
            # 查找下一页按钮
            next_button = await self.page.query_selector('a.next-page:not(.disabled)')
            if next_button:
                await next_button.click()
                await asyncio.sleep(2)
                return True
            return False
        except:
            return False
    
    def parse_sale_date(self, sold_time: str) -> Optional[datetime]:
        """解析售出时间字符串"""
        if not sold_time:
            return None
        
        try:
            # 清理时间字符串
            time_str = sold_time.replace('已售', '').replace('售出', '').strip()
            logger.debug(f"解析时间字符串: '{time_str}'")
            
            now = datetime.now()
            
            # 解析相对时间格式
            if '分钟前' in time_str:
                minutes_match = re.search(r'(\d+)分钟前', time_str)
                if minutes_match:
                    minutes = int(minutes_match.group(1))
                    result = now - timedelta(minutes=minutes)
                    logger.debug(f"解析为 {minutes} 分钟前: {result}")
                    return result
            elif '小时前' in time_str:
                hours_match = re.search(r'(\d+)小时前', time_str)
                if hours_match:
                    hours = int(hours_match.group(1))
                    result = now - timedelta(hours=hours)
                    logger.debug(f"解析为 {hours} 小时前: {result}")
                    return result
            elif '天前' in time_str:
                days_match = re.search(r'(\d+)天前', time_str)
                if days_match:
                    days = int(days_match.group(1))
                    result = now - timedelta(days=days)
                    logger.debug(f"解析为 {days} 天前: {result}")
                    return result
            elif '月前' in time_str:
                months_match = re.search(r'(\d+)月前', time_str)
                if months_match:
                    months = int(months_match.group(1))
                    # 使用更准确的月份计算
                    result = now - timedelta(days=months*30.44)  # 平均每月30.44天
                    logger.debug(f"解析为 {months} 月前: {result}")
                    return result
            elif '年前' in time_str:
                years_match = re.search(r'(\d+)年前', time_str)
                if years_match:
                    years = int(years_match.group(1))
                    result = now - timedelta(days=years*365.25)  # 考虑闰年
                    logger.debug(f"解析为 {years} 年前: {result}")
                    return result
            else:
                # 尝试解析具体日期格式
                date_formats = [
                    '%Y-%m-%d',
                    '%Y年%m月%d日',
                    '%m-%d',
                    '%m月%d日'
                ]
                
                for fmt in date_formats:
                    try:
                        result = datetime.strptime(time_str, fmt)
                        # 如果是月-日格式，补充当前年份
                        if fmt in ['%m-%d', '%m月%d日']:
                            result = result.replace(year=now.year)
                            # 如果日期在未来，说明是去年的
                            if result > now:
                                result = result.replace(year=now.year - 1)
                        logger.debug(f"解析为具体日期: {result}")
                        return result
                    except ValueError:
                        continue
            
            logger.warning(f"无法解析时间字符串: '{time_str}'")
            return None
            
        except Exception as e:
            logger.error(f"解析时间失败: '{sold_time}', 错误: {e}")
            return None
    
    def calculate_sales_stats(self, sales: List[Dict], isbn: str) -> Dict:
        """计算销售统计数据"""
        now = datetime.now()
        
        # 初始化统计
        stats = {
            'isbn': isbn,
            'sales_3_days': 0,
            'sales_7_days': 0,
            'sales_30_days': 0,
            'total_records': len(sales),
            'latest_sale_date': None,
            'average_price': None,
            'price_range': {'min': None, 'max': None},
            'sales_records': sales[:50]  # 返回前50条记录用于展示
        }
        
        if not sales:
            return stats
        
        prices = []
        
        for sale in sales:
            sale_date = sale.get('sale_date')
            
            if sale_date:
                # 更新最新销售日期
                if not stats['latest_sale_date'] or sale_date > datetime.fromisoformat(stats['latest_sale_date']):
                    stats['latest_sale_date'] = sale_date.isoformat()
                
                # 统计不同时间段的销量
                days_diff = (now - sale_date).days
                if days_diff <= 3:
                    stats['sales_3_days'] += 1
                if days_diff <= 7:
                    stats['sales_7_days'] += 1
                if days_diff <= 30:
                    stats['sales_30_days'] += 1
            
            # 收集价格信息
            try:
                price = sale.get('sale_price') or sale.get('price', 0)
                if isinstance(price, str):
                    price = float(price.replace('¥', '').replace(',', ''))
                else:
                    price = float(price or 0)
                if price > 0:
                    prices.append(price)
            except:
                pass
        
        # 计算价格统计
        if prices:
            stats['average_price'] = round(sum(prices) / len(prices), 2)
            stats['price_range']['min'] = min(prices)
            stats['price_range']['max'] = max(prices)
        
        return stats
    
    async def crawl_book_sales(self, isbn: str) -> Dict:
        """爬取单本书籍的销售数据"""
        if not await self.connect_browser():
            raise Exception("无法连接到Chrome浏览器")
        
        try:
            # 搜索书籍
            search_url = f"https://search.kongfz.com/product/?keyword={isbn}&dataType=1&sortType=10&page=1"
            await self._safe_page_goto(search_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            sales_records = []
            page_num = 1
            max_pages = 10  # 最多爬取10页
            
            while page_num <= max_pages:
                # 提取当前页面的销售记录
                page_sales = await self.extract_sales_records()
                
                if not page_sales:
                    break
                
                for sale in page_sales:
                    if sale.get('isbn') == isbn:
                        sales_records.append(sale)
                
                # 尝试翻页
                if not await self.goto_next_page():
                    break
                
                page_num += 1
                await asyncio.sleep(2)
            
            # 保存销售记录到数据库
            for sale in sales_records:
                try:
                    # 需要找到或创建店铺
                    shop_id_str = sale.get('shop_id', '')
                    shop = self.shop_repo.get_by_shop_id(shop_id_str) if shop_id_str else None
                    
                    if shop:
                        sale_record = SalesRecord(
                            isbn=isbn,
                            shop_id=shop['id'],
                            sale_price=sale.get('price', 0),
                            sale_date=sale.get('sale_date', datetime.now()),
                            original_price=sale.get('original_price'),
                            sale_platform='kongfuzi',
                            book_condition=sale.get('condition')
                        )
                        self.sales_repo.create(sale_record)
                except Exception as e:
                    logger.error(f"保存销售记录失败: {e}")
            
            return {
                'total_records': len(sales_records),
                'success': True
            }
            
        except Exception as e:
            logger.error(f"爬取书籍 {isbn} 失败: {e}")
            raise
    
    async def crawl_shop_sales(self, shop_id: str) -> int:
        """爬取店铺所有书籍的销售数据，基于数据库中该店铺的书籍库存记录"""
        try:
            logger.info(f"开始爬取店铺 {shop_id} 的销售数据")
            
            # 检查当前封控状态
            rate_limit_status = self.get_rate_limit_status()
            if rate_limit_status["is_rate_limited"]:
                logger.info(f"当前处于封控状态，等待时间: {rate_limit_status['current_wait_time_minutes']} 分钟")
            
            # 获取店铺信息
            shop = self.shop_repo.get_by_shop_id(shop_id)
            if not shop:
                raise Exception(f"店铺 {shop_id} 不存在")
            
            # 从数据库查询该店铺的所有书籍ISBN
            from ..models.database import db
            query = """
                SELECT DISTINCT bi.isbn, b.title
                FROM book_inventory bi
                LEFT JOIN books b ON bi.isbn = b.isbn
                WHERE bi.shop_id = ? AND bi.isbn IS NOT NULL
                ORDER BY bi.crawled_at DESC
            """
            shop_books = db.execute_query(query, (shop['id'],))
            
            if not shop_books:
                logger.warning(f"店铺 {shop_id} 没有书籍库存记录，请先爬取书籍信息")
                return 0
            
            logger.info(f"店铺 {shop_id} 共有 {len(shop_books)} 本书，开始爬取销售数据")
            total_sales = 0
            success_count = 0
            error_count = 0
            
            for i, book in enumerate(shop_books, 1):
                isbn = book['isbn']
                title = book.get('title', '未知书名')
                
                try:
                    logger.info(f"[{i}/{len(shop_books)}] 正在爬取《{title}》(ISBN: {isbn}) 的销售数据")
                    sales_count = await self.analyze_and_save_book_sales(isbn, shop['id'], days_limit=30)
                    total_sales += sales_count
                    success_count += 1
                    
                    # 成功时重置封控等待时间
                    self._update_rate_limit_wait_time(success=True)
                    
                    if sales_count > 0:
                        logger.info(f"ISBN {isbn} 爬取完成，保存了 {sales_count} 条记录，已更新爬取时间")
                    else:
                        logger.info(f"ISBN {isbn} 爬取完成，暂无销售记录，已更新爬取时间")
                    
                    # 间隔避免过于频繁的请求
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    error_count += 1
                    error_msg = str(e)
                    
                    # 检查是否遇到频率限制
                    if self._is_rate_limit_error(error_msg):
                        # 更新封控等待时间（指数退避）
                        self._update_rate_limit_wait_time(success=False)
                        wait_time = self._get_current_wait_time()
                        
                        logger.warning(f"遇到访问频率限制，等待 {wait_time // 60} 分钟后继续: {error_msg}")
                        await asyncio.sleep(wait_time)
                        continue  # 继续处理下一本书
                    
                    logger.error(f"爬取ISBN {isbn} 失败: {e}")
                    continue
            
            logger.info(f"店铺 {shop_id} 销售数据爬取完成: 成功 {success_count} 本，失败 {error_count} 本，总共保存 {total_sales} 条销售记录")
            
        # 显示最终封控状态
        final_status = self.get_rate_limit_status()
        if final_status["is_rate_limited"]:
            logger.warning(f"爬取结束时仍处于封控状态，当前等待时间: {final_status['current_wait_time_minutes']} 分钟")
        else:
            logger.info("爬取结束时封控状态已重置")
            
        return total_sales
            
        except Exception as e:
            logger.error(f"爬取店铺 {shop_id} 销售数据失败: {e}")
            raise
    
    def _is_rate_limit_error(self, error_message: str) -> bool:
        """检测是否为访问频率限制错误"""
        rate_limit_keywords = [
            "搜索次数已达到上限",
            "请求错误，请降低访问频次",
            "更换真实账号使用",
            "访问频率过高",
            "rate limit",
            "too many requests",
            "请稍后访问",
            "访问受限"
        ]
        
        error_lower = error_message.lower()
        return any(keyword.lower() in error_lower for keyword in rate_limit_keywords)
    
    async def _check_page_for_rate_limit(self) -> None:
        """检查页面内容是否包含频率限制信息"""
        if not self.page:
            return
        
        try:
            # 检查页面标题和内容
            page_content = await self.page.evaluate("""
                () => {
                    return {
                        title: document.title,
                        body: document.body.innerText || '',
                        html: document.documentElement.innerHTML || ''
                    };
                }
            """)
            
            # 检查所有内容
            all_content = f"{page_content.get('title', '')} {page_content.get('body', '')} {page_content.get('html', '')}"
            
            if self._is_rate_limit_error(all_content):
                raise Exception("很抱歉，您当前的搜索次数已达到上限，请稍后访问！请求错误，请降低访问频次或更换真实账号使用。")
                
        except Exception as e:
            if self._is_rate_limit_error(str(e)):
                raise
            # 其他异常不处理，继续执行
    
    async def extract_book_info_from_current_page(self) -> Dict:
        """从当前页面提取书籍信息"""
        try:
            # 从搜索结果页面提取书籍信息
            return await self.page.evaluate("""
                () => {
                    const productItems = document.querySelectorAll('.product-item-wrap');
                    const books = [];
                    
                    productItems.forEach(item => {
                        try {
                            // 提取书籍标题
                            const titleElem = item.querySelector('.detail-name a, .book-title a');
                            const title = titleElem ? titleElem.innerText.trim() : '';
                            
                            // 提取ISBN - 从链接href或详情文本中
                            const linkElem = item.querySelector('.detail-name a, .book-title a');
                            let isbn = '';
                            if (linkElem && linkElem.href) {
                                const isbnMatch = linkElem.href.match(/\\/product\\/(\\d+)/);
                                if (isbnMatch) {
                                    isbn = isbnMatch[1];
                                }
                            }
                            
                            // 从详情文本中提取ISBN
                            if (!isbn) {
                                const detailText = item.innerText || '';
                                const isbnMatch = detailText.match(/ISBN[：:]\s*([0-9X-]+)/i) || 
                                                 detailText.match(/([0-9]{10,13})/);
                                if (isbnMatch) {
                                    isbn = isbnMatch[1].replace(/-/g, '');
                                }
                            }
                            
                            // 提取作者
                            const authorElem = item.querySelector('.detail-author, .author');
                            const author = authorElem ? authorElem.innerText.trim() : '';
                            
                            // 提取出版社
                            const publisherElem = item.querySelector('.detail-publisher, .publisher');
                            const publisher = publisherElem ? publisherElem.innerText.trim() : '';
                            
                            if (title && isbn) {
                                books.push({
                                    isbn: isbn,
                                    title: title,
                                    author: author,
                                    publisher: publisher
                                });
                            }
                        } catch (error) {
                            console.log('提取书籍信息时出错:', error);
                        }
                    });
                    
                    // 返回第一本书的信息
                    return books.length > 0 ? books[0] : {};
                }
            """)
        except Exception:
            return {}
    
    async def extract_book_info_from_sale(self, sale: Dict) -> Dict:
        """从销售记录中提取书籍信息"""
        try:
            # 这个函数可以根据需要从页面中提取更多书籍详情
            # 目前先返回基本信息，后续可以扩展
            return {
                'isbn': '',  # 需要从页面HTML中提取
                'title': '',  # 需要从页面HTML中提取
                'author': '',
                'publisher': '',
                'original_price': None
            }
        except Exception:
            return {}
    
    async def extract_shop_sales_records(self) -> List[Dict]:
        """提取店铺销售记录页面的数据"""
        try:
            sales = await self.page.evaluate("""
                () => {
                    const items = [];
                    const bookItems = document.querySelectorAll('.book-item, .item, .sold-item');
                    
                    bookItems.forEach(item => {
                        try {
                            // 提取书籍标题
                            const titleElem = item.querySelector('.title a, .name a, h3 a');
                            const title = titleElem ? titleElem.innerText.trim() : '';
                            
                            // 提取ISBN
                            const detailText = item.innerText || '';
                            const isbnMatch = detailText.match(/ISBN[：:]\s*([0-9X-]+)/i) || 
                                             detailText.match(/([0-9]{10,13})/);
                            const isbn = isbnMatch ? isbnMatch[1].replace(/-/g, '') : '';
                            
                            // 提取价格
                            const priceElem = item.querySelector('.price, .sell-price, .money');
                            const priceText = priceElem ? priceElem.innerText : '';
                            const price = parseFloat(priceText.replace(/[^0-9.]/g, '')) || 0;
                            
                            // 提取售出时间
                            const soldTimeElem = item.querySelector('.sold-time, .time, .date');
                            const soldTime = soldTimeElem ? soldTimeElem.innerText.trim() : '';
                            
                            // 提取品相
                            const conditionElem = item.querySelector('.quality, .condition');
                            const condition = conditionElem ? conditionElem.innerText.trim() : '';
                            
                            // 提取作者
                            const authorElem = item.querySelector('.author');
                            const author = authorElem ? authorElem.innerText.trim() : '';
                            
                            // 提取出版社
                            const publisherElem = item.querySelector('.publisher');
                            const publisher = publisherElem ? publisherElem.innerText.trim() : '';
                            
                            if (title && price > 0) {
                                items.push({
                                    title: title,
                                    isbn: isbn,
                                    price: price,
                                    sold_time: soldTime,
                                    condition: condition,
                                    author: author,
                                    publisher: publisher
                                });
                            }
                        } catch (e) {
                            console.error('提取单个商品失败:', e);
                        }
                    });
                    
                    return items;
                }
            """)
            
            # 解析售出时间并转换为日期
            processed_sales = []
            for sale in sales:
                sale_date = self.parse_sale_date(sale.get('sold_time', ''))
                if sale_date:
                    sale['sale_date'] = sale_date
                    processed_sales.append(sale)
            
            return processed_sales
            
        except Exception as e:
            logger.error(f"提取销售记录失败: {e}")
            return []
    
    async def crawl_shop_books(self, shop_id: str, max_pages: int = 50) -> int:
        """爬取店铺的书籍列表"""
        if not await self.connect_browser():
            raise Exception("无法连接到浏览器")
        
        # 创建爬虫任务
        task = CrawlTask(
            task_name=f"爬取店铺 {shop_id} 的书籍",
            task_type="shop_books",
            target_platform="kongfuzi",
            target_url=f"https://shop.kongfz.com/{shop_id}/all/0_50_0_0_1_newItem_desc_0_0/",
            status="running"
        )
        task_id = self.task_repo.create(task)
        
        try:
            books_crawled = 0
            current_page = 1
            
            # 访问店铺首页
            url = f"https://shop.kongfz.com/{shop_id}/all/0_50_0_0_1_newItem_desc_0_0/"
            await self._safe_page_goto(url, wait_until='networkidle')
            await asyncio.sleep(2)  # 等待页面加载
            
            while current_page <= max_pages:
                try:
                    # 提取书籍信息
                    books_data = await self.page.evaluate("""
                    () => {
                        const items = [];
                        // 查找item-row元素，它包含了itemid和isbn属性
                        document.querySelectorAll('.item-row').forEach(item => {
                            const titleEl = item.querySelector('.row-name');
                            const authorEl = item.querySelector('.row-author');
                            const pressEl = item.querySelector('.row-press');
                            const priceEl = item.querySelector('.row-price');
                            const qualityEl = item.querySelector('.row-quality');
                            
                            // 获取item的属性
                            const itemId = item.getAttribute('itemid');
                            const isbn = item.getAttribute('isbn');
                            const shopId = item.getAttribute('shopid');
                            
                            if (titleEl) {
                                // 处理价格，移除所有货币符号
                                let price = '';
                                if (priceEl) {
                                    const boldPrice = priceEl.querySelector('.bold');
                                    if (boldPrice) {
                                        price = boldPrice.textContent.trim();
                                    } else {
                                        price = priceEl.textContent
                                            .replace(/[¥￥]/g, '')  // 移除半角和全角￥
                                            .replace(/[^\d.]/g, '')  // 只保留数字和小数点
                                            .trim();
                                    }
                                }
                                
                                items.push({
                                    title: titleEl.textContent.trim(),
                                    url: titleEl.href,
                                    author: authorEl ? authorEl.textContent.trim() : '',
                                    publisher: pressEl ? pressEl.textContent.trim() : '',
                                    price: price,
                                    quality: qualityEl ? qualityEl.textContent.trim() : '',
                                    itemId: itemId || '',
                                    isbn: isbn || '',
                                    shopId: shopId || ''
                                });
                            }
                        });
                        
                        // 如果item-row选择器没有找到元素，尝试使用.item选择器（兼容旧版页面）
                        if (items.length === 0) {
                            document.querySelectorAll('.item').forEach(item => {
                                const titleEl = item.querySelector('.title a');
                                const priceEl = item.querySelector('.price');
                                const qualityEl = item.querySelector('.quality');
                                
                                if (titleEl) {
                                    let price = '';
                                    if (priceEl) {
                                        price = priceEl.textContent
                                            .replace(/[¥￥]/g, '')
                                            .replace(/[^\d.]/g, '')
                                            .trim();
                                    }
                                    
                                    // 从URL提取ID作为备用
                                    let bookId = '';
                                    if (titleEl.href) {
                                        const matches = titleEl.href.match(/\/(\d+)\/(\d+)\//);
                                        if (matches && matches[2]) {
                                            bookId = matches[2];
                                        }
                                    }
                                    
                                    items.push({
                                        title: titleEl.textContent.trim(),
                                        url: titleEl.href,
                                        author: '',
                                        publisher: '',
                                        price: price,
                                        quality: qualityEl ? qualityEl.textContent.trim() : '',
                                        itemId: bookId,
                                        isbn: '',
                                        shopId: ''
                                    });
                                }
                            });
                        }
                        
                        return items;
                    }
                """)
                    
                    if not books_data:
                        logger.info(f"第 {current_page} 页没有书籍数据")
                        break
                    
                    # 保存书籍数据
                    for book_data in books_data:
                        # 优先使用真实的ISBN，如果没有则使用itemId作为唯一标识
                        isbn = book_data.get('isbn') or book_data.get('itemId')
                        if not isbn:
                            logger.warning(f"无法获取书籍唯一标识: {book_data['title']}")
                            continue
                        
                        # 创建或更新书籍
                        book = Book(
                            isbn=isbn,  # 使用真实ISBN或itemId作为唯一标识
                            title=book_data['title'],
                            author=book_data.get('author'),
                            publisher=book_data.get('publisher')
                        )
                        book_isbn = self.book_repo.create_or_update(book)
                        
                        if not book_isbn:
                            logger.error(f"无法保存书籍: {book_data['title']}")
                            continue
                        
                        # 获取店铺信息
                        shop_info = self.shop_repo.get_by_id(shop_id)
                        if not shop_info:
                            continue
                        
                        # 安全解析价格
                        price = None
                        if book_data['price']:
                            try:
                                price = float(book_data['price'])
                            except (ValueError, TypeError) as e:
                                logger.warning(f"无法解析价格 '{book_data['price']}': {e}")
                                price = None
                        
                        # 创建库存记录
                        inventory = BookInventory(
                            isbn=book_isbn,
                            shop_id=shop_info['id'],
                            kongfuzi_price=price,
                            kongfuzi_condition=book_data.get('quality'),
                            kongfuzi_book_url=book_data.get('url'),
                            kongfuzi_item_id=book_data.get('itemId')  # 保存原始的itemId
                        )
                        self.inventory_repo.upsert(inventory)
                        books_crawled += 1
                    
                    logger.info(f"第 {current_page} 页爬取了 {len(books_data)} 本书籍")
                    
                    # 更新任务进度
                    progress = (current_page / max_pages) * 100
                    self.task_repo.update_status(task_id, 'running', progress)
                    
                    # 检查是否有下一页
                    has_next_page = await self.page.evaluate("""
                        () => {
                            // 查找下一页按钮，可能有多种selector
                            const nextBtn = document.querySelector('.next-btn') || 
                                           document.querySelector('.pagination .next') ||
                                           document.querySelector('a[title="下一页"]') ||
                                           document.querySelector('.page-next:not(.disabled)');
                            return nextBtn && !nextBtn.classList.contains('disabled') && 
                                   !nextBtn.classList.contains('inactive');
                        }
                    """)
                    
                    if not has_next_page or current_page >= max_pages:
                        logger.info(f"没有下一页或已达到最大页数限制 {max_pages}")
                        break
                    
                    # 点击下一页
                    await self.page.evaluate("""
                        () => {
                            const nextBtn = document.querySelector('.next-btn') || 
                                           document.querySelector('.pagination .next') ||
                                           document.querySelector('a[title="下一页"]') ||
                                           document.querySelector('.page-next:not(.disabled)');
                            if (nextBtn) nextBtn.click();
                        }
                    """)
                    
                    # 等待新页面加载
                    await asyncio.sleep(3)
                    
                    # 等待页面稳定
                    try:
                        await self.page.wait_for_load_state('networkidle', timeout=5000)
                    except:
                        # 如果等待超时，继续执行
                        pass
                    
                    current_page += 1
                    
                except Exception as e:
                    logger.warning(f"第 {current_page} 页处理出错: {e}")
                    # 如果出错，尝试继续下一页
                    current_page += 1
                    if current_page > max_pages:
                        break
                    # 等待一下再继续
                    await asyncio.sleep(3)
                    continue
            
            # 更新任务为完成
            self.task_repo.update_status(task_id, 'completed', 100)
            logger.info(f"成功爬取店铺 {shop_id} 的 {books_crawled} 本书籍")
            return books_crawled
            
        except Exception as e:
            logger.error(f"爬取店铺失败: {e}")
            self.task_repo.update_status(task_id, 'failed', error_message=str(e))
            raise
    
    async def crawl_book_sales(self, isbn: str, days_limit: int = 30) -> List[Dict]:
        """爬取书籍的销售记录"""
        if not await self.connect_browser():
            raise Exception("无法连接到浏览器")
        
        url = f"https://search.kongfz.com/product/?keyword={isbn}&dataType=1&sortType=10&page=1"
        cutoff_date = datetime.now() - timedelta(days=days_limit)
        all_sales = []
        
        try:
            await self._safe_page_goto(url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            # 提取已售记录
            sales_data = await self.page.evaluate("""
                () => {
                    const sales = [];
                    document.querySelectorAll('.sold-item').forEach(item => {
                        const priceEl = item.querySelector('.price');
                        const dateEl = item.querySelector('.date');
                        const qualityEl = item.querySelector('.quality');
                        
                        if (priceEl && dateEl) {
                            sales.push({
                                price: priceEl.textContent.replace('¥', '').trim(),
                                date: dateEl.textContent.trim(),
                                quality: qualityEl ? qualityEl.textContent.trim() : ''
                            });
                        }
                    });
                    return sales;
                }
            """)
            
            # 获取书籍信息
            book = self.book_repo.get_by_isbn(isbn)
            if not book:
                logger.warning(f"找不到ISBN为 {isbn} 的书籍")
                return []
            
            # 保存销售记录
            sales_records = []
            for sale in sales_data:
                try:
                    sale_date = datetime.strptime(sale['date'], '%Y-%m-%d')
                    if sale_date < cutoff_date:
                        continue
                    
                    record = SalesRecord(
                        isbn=isbn,  # 使用ISBN作为外键
                        shop_id=1,  # 默认店铺ID，实际应该从页面获取
                        sale_price=float(sale['price']),
                        sale_date=sale_date,
                        book_condition=sale['quality']
                    )
                    sales_records.append(record)
                    all_sales.append(sale)
                except Exception as e:
                    logger.error(f"处理销售记录失败: {e}")
                    continue
            
            if sales_records:
                self.sales_repo.batch_create(sales_records)
            
            logger.info(f"成功爬取 {isbn} 的 {len(all_sales)} 条销售记录")
            return all_sales
            
        except Exception as e:
            logger.error(f"爬取销售记录失败: {e}")
            raise

class DuozhuayuCrawler:
    """多抓鱼爬虫"""
    
    def __init__(self):
        self.inventory_repo = BookInventoryRepository()
    
    async def search_book_price(self, isbn: str) -> Dict[str, any]:
        """搜索多抓鱼的书籍价格"""
        # 多抓鱼API接口（示例，实际需要根据网站分析）
        search_url = f"https://www.duozhuayu.com/api/search?q={isbn}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(search_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and data.get('items'):
                            item = data['items'][0]
                            return {
                                'new_price': item.get('new_price'),
                                'second_hand_price': item.get('second_hand_price'),
                                'in_stock': item.get('in_stock', False),
                                'url': item.get('url')
                            }
            except Exception as e:
                logger.error(f"查询多抓鱼价格失败: {e}")
        
        return {}
    
    async def update_book_price(self, isbn: str, shop_id: int) -> bool:
        """更新书籍的多抓鱼价格"""
        # 获取书籍信息
        from ..models.repositories import BookRepository
        book_repo = BookRepository()
        book = book_repo.get_by_isbn(isbn)
        
        if not book:
            return False
        
        # 查询多抓鱼价格
        price_info = await self.search_book_price(isbn)
        
        if price_info:
            # 获取现有库存信息
            inventory = self.inventory_repo.get_by_book_shop(isbn, shop_id)
            
            if inventory:
                # 更新多抓鱼价格信息
                inventory['duozhuayu_new_price'] = price_info.get('new_price')
                inventory['duozhuayu_second_hand_price'] = price_info.get('second_hand_price')
                inventory['duozhuayu_in_stock'] = price_info.get('in_stock', False)
                inventory['duozhuayu_book_url'] = price_info.get('url')
                
                # 重新计算价差
                if inventory['kongfuzi_price'] and inventory['duozhuayu_second_hand_price']:
                    inventory['price_diff_second_hand'] = inventory['duozhuayu_second_hand_price'] - inventory['kongfuzi_price']
                    inventory['profit_margin_second_hand'] = (inventory['price_diff_second_hand'] / inventory['kongfuzi_price']) * 100
                    inventory['is_profitable'] = inventory['price_diff_second_hand'] > 0
                
                # 保存更新
                from ..models.models import BookInventory
                inv_model = BookInventory(**inventory)
                self.inventory_repo.upsert(inv_model)
                return True
        
        return False

class CrawlerManager:
    """爬虫管理器 - 统一管理所有爬虫"""
    
    def __init__(self):
        self.kongfuzi = KongfuziCrawler()
        self.duozhuayu = DuozhuayuCrawler()
        self.task_repo = CrawlTaskRepository()
    
    async def run_pending_tasks(self):
        """运行待执行的任务"""
        tasks = self.task_repo.get_pending_tasks()
        
        for task in tasks:
            try:
                if task['task_type'] == 'shop_books':
                    # 爬取店铺书籍
                    await self.kongfuzi.crawl_shop_books(task['target_url'])
                elif task['task_type'] == 'book_sales':
                    # 爬取销售记录
                    params = json.loads(task['task_params']) if task['task_params'] else {}
                    isbn = params.get('isbn')
                    if isbn:
                        await self.kongfuzi.crawl_book_sales(isbn)
                elif task['task_type'] == 'duozhuayu_price':
                    # 更新多抓鱼价格
                    params = json.loads(task['task_params']) if task['task_params'] else {}
                    isbn = params.get('isbn')
                    shop_id = params.get('shop_id')
                    if isbn and shop_id:
                        await self.duozhuayu.update_book_price(isbn, shop_id)
            except Exception as e:
                logger.error(f"执行任务 {task['id']} 失败: {e}")
                self.task_repo.update_status(task['id'], 'failed', error_message=str(e))
    
    async def cleanup(self):
        """清理资源"""
        await self.kongfuzi.disconnect_browser()