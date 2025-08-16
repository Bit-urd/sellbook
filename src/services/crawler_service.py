#!/usr/bin/env python3
"""
爬虫服务模块 - 负责数据抓取逻辑
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import aiohttp
from patchright.async_api import async_playwright, Page
from collections import deque

from ..models.models import Shop, Book, BookInventory, SalesRecord, CrawlTask
from ..models.repositories import (
    ShopRepository, BookRepository, BookInventoryRepository, 
    SalesRepository, CrawlTaskRepository
)
from .window_pool import chrome_pool, WindowPoolManager

logger = logging.getLogger(__name__)

class BrowserManager:
    """兼容旧代码的浏览器管理器（实际使用窗口池）"""
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.pool = chrome_pool
            BrowserManager._initialized = True
    
    async def get_browser_page(self):
        """获取浏览器页面（从窗口池获取）"""
        return await self.pool.get_window()
    
    async def disconnect(self):
        """断开浏览器连接（兼容旧接口，实际不断开池）"""
        # 不断开池连接，因为可能有其他实例在使用
        pass
    
    def is_connected(self):
        """检查连接状态"""
        return self.pool.connected

# 创建全局单例实例（兼容旧代码）
browser_manager = BrowserManager()

class KongfuziCrawler:
    """孔夫子网爬虫"""
    
    # 全局封控等待时间（秒），使用类变量在所有实例间共享
    _rate_limit_wait_time = 0
    _max_wait_time = 24 * 60 * 60  # 最大等待时间：1天（24小时）
    
    def __init__(self):
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
        from .window_pool import chrome_pool
        
        if success:
            # 成功时重置等待时间为0
            cls._rate_limit_wait_time = 0
            logger.info("请求成功，重置封控等待时间为0")
        else:
            # 检查窗口池的封控状态
            rate_limit_status = chrome_pool.get_rate_limit_status()
            
            if rate_limit_status['all_limited']:
                # 所有窗口都被封控，设置等待时间为2分钟
                cls._rate_limit_wait_time = 2 * 60  # 固定2分钟
                logger.error(f"所有 {rate_limit_status['total_windows']} 个窗口都被封控，设置等待时间为2分钟")
            else:
                # 还有窗口可用，不需要等待
                cls._rate_limit_wait_time = 0
                available = rate_limit_status['total_windows'] - rate_limit_status['rate_limited_count']
                logger.info(f"仍有 {available}/{rate_limit_status['total_windows']} 个窗口可用，继续尝试其他窗口")
    
    @classmethod
    def _get_current_wait_time(cls) -> int:
        """获取当前封控等待时间（秒）"""
        return cls._rate_limit_wait_time
    
    async def _safe_page_goto(self, page: Page, url: str, **kwargs):
        """安全的页面跳转，成功时重置封控时间
        
        Args:
            page: 浏览器页面
            url: 目标URL
            **kwargs: goto方法的其他参数
        """
        try:
            result = await page.goto(url, **kwargs)
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
        next_wait_time = min(wait_time * 2, cls._max_wait_time) if wait_time > 0 else 2 * 60
        
        def format_time_display(seconds: int) -> dict:
            """格式化时间显示"""
            minutes = seconds // 60
            if minutes >= 60:
                hours = minutes // 60
                remaining_minutes = minutes % 60
                if remaining_minutes > 0:
                    display_text = f"{hours}小时{remaining_minutes}分钟"
                else:
                    display_text = f"{hours}小时"
            else:
                display_text = f"{minutes}分钟"
            
            return {
                "seconds": seconds,
                "minutes": minutes,
                "hours": minutes // 60 if minutes >= 60 else 0,
                "display_text": display_text
            }
        
        return {
            "is_rate_limited": wait_time > 0,
            "current_wait_time": format_time_display(wait_time),
            "next_wait_time": format_time_display(next_wait_time),
            "max_wait_time": format_time_display(cls._max_wait_time),
            # 保持向后兼容
            "current_wait_time_seconds": wait_time,
            "current_wait_time_minutes": wait_time // 60,
            "max_wait_time_minutes": cls._max_wait_time // 60,
            "next_wait_time_minutes": next_wait_time // 60
        }
    
    async def connect_browser(self):
        """连接到Chrome浏览器（从窗口池获取页面）"""
        try:
            # 确保窗口池已初始化
            if not chrome_pool._initialized:
                await chrome_pool.initialize()
            return chrome_pool.connected
        except Exception as e:
            logger.error(f"Chrome连接失败: {e}")
            return False
    
    async def disconnect_browser(self):
        """断开浏览器连接（兼容旧接口）"""
        # 不断开池连接，因为可能有其他实例在使用
        pass
    
    @WindowPoolManager()
    async def analyze_book_sales(self, isbn: str, days_limit: int = 30, quality_filter: str = "high", page: Page = None) -> Dict:
        """分析单本书的销售记录（用于实时ISBN搜索）
        
        Args:
            isbn: 书籍ISBN号
            days_limit: 天数限制
            quality_filter: 品相过滤 - "high" (九品以上) 或 "all" (全部品相)
            page: 浏览器页面（由装饰器自动注入）
        """
        cutoff_date = datetime.now() - timedelta(days=days_limit)
        all_sales = []
        
        page_num = 1
        max_pages = 20
        
        try:
            while page_num <= max_pages:
                # 根据品相过滤和页码构建搜索URL
                if quality_filter == "high":
                    # 九品以上 (90分以上)
                    search_url = f"https://search.kongfz.com/product/?dataType=1&keyword={isbn}&page={page_num}&sortType=10&actionPath=sortType,quality&quality=90~&quaSelect=1"
                else:
                    # 全部品相
                    search_url = f"https://search.kongfz.com/product/?dataType=1&keyword={isbn}&page={page_num}&sortType=10&actionPath=sortType&quaSelect=1"
                
                logger.info(f"正在爬取第 {page_num} 页: {search_url}")
                
                await page.goto(search_url, wait_until='networkidle')
                await asyncio.sleep(2)
                
                # 第一页检查登录状态
                if page_num == 1:
                    await self._check_page_for_rate_limit(page)
                
                # 提取当前页面的销售记录
                page_sales = await self.extract_sales_records(page)
                
                # 如果第一页就没有数据，可能是登录问题
                if page_num == 1 and not page_sales:
                    # 再次检查页面内容，看是否需要登录
                    await self._check_page_content_for_empty_results(page)
                    break
                elif not page_sales:
                    logger.info(f"第 {page_num} 页没有销售记录，停止翻页")
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
                    logger.info(f"第 {page_num} 页获取了 {len(valid_sales)} 条有效销售记录")
                
                # 如果发现超过时间限制的记录，停止翻页
                if has_old_records:
                    logger.info(f"第 {page_num} 页发现超过 {days_limit} 天的记录，停止翻页")
                    break
                
                page_num += 1
                await asyncio.sleep(2)
            
            # 计算统计数据
            stats = self.calculate_sales_stats(all_sales, isbn)
            return stats
            
        except Exception as e:
            logger.error(f"爬取ISBN {isbn} 销售数据失败: {e}")
            raise
    
    def check_isbn_crawled_recently(self, isbn: str, days_threshold: int = 7) -> bool:
        """检查ISBN是否在最近几天内已被爬取过
        
        Args:
            isbn: 书籍ISBN
            days_threshold: 时间阈值（天数）
        
        Returns:
            True: 已被爬取过，False: 未被爬取或爬取时间较早
        """
        from ..models.database import db
        
        query = """
            SELECT last_sales_update FROM books 
            WHERE isbn = ? AND last_sales_update IS NOT NULL
            AND last_sales_update >= datetime('now', '-{} days')
        """.format(days_threshold)
        
        results = db.execute_query(query, (isbn,))
        return len(results) > 0
    
    async def crawl_single_book_sales(self, isbn: str, shop_id: int, days_limit: int = 30, 
                                    skip_if_recent: bool = True) -> Dict:
        """爬取单本书的销售记录（用于任务执行）
        
        Args:
            isbn: 书籍ISBN
            shop_id: 店铺ID
            days_limit: 爬取天数限制
            skip_if_recent: 是否跳过最近已爬取的书籍
        
        Returns:
            包含爬取结果的字典
        """
        result = {
            'isbn': isbn,
            'status': 'pending',
            'records_saved': 0,
            'message': '',
            'skipped': False
        }
        
        try:
            # 检查是否最近已被爬取过
            if skip_if_recent and self.check_isbn_crawled_recently(isbn, days_threshold=7):
                result['status'] = 'skipped'
                result['skipped'] = True
                result['message'] = f'ISBN {isbn} 在最近7天内已被爬取过，跳过'
                logger.info(result['message'])
                return result
            
            # 执行爬取
            records_saved = await self.analyze_and_save_book_sales(isbn, shop_id, days_limit)
            
            result['status'] = 'completed'
            result['records_saved'] = records_saved
            result['message'] = f'成功爬取ISBN {isbn}，保存了 {records_saved} 条销售记录'
            logger.info(result['message'])
            
        except Exception as e:
            result['status'] = 'failed'
            result['message'] = f'爬取ISBN {isbn} 失败: {str(e)}'
            logger.error(result['message'])
        
        return result

    @WindowPoolManager()
    async def analyze_and_save_book_sales(self, isbn: str, shop_id: int, days_limit: int = 30, page: Page = None) -> int:
        """分析并保存单本书的销售记录到数据库
        
        Args:
            isbn: 书籍ISBN
            shop_id: 店铺ID
            days_limit: 天数限制
            page: 浏览器页面（由装饰器自动注入）
        """
        cutoff_date = datetime.now() - timedelta(days=days_limit)
        total_saved = 0
        
        # 构建搜索URL - 爬取销售记录时使用全部品相
        search_url = f"https://search.kongfz.com/product/?dataType=1&keyword={isbn}&page=1&sortType=10&actionPath=sortType"
        
        try:
            await self._safe_page_goto(page, search_url, wait_until='networkidle')
            await asyncio.sleep(5)
            
            # 检查页面是否出现频率限制
            await self._check_page_for_rate_limit(page)
            
            page_num = 1
            max_pages = 10
            
            while page_num <= max_pages:
                await asyncio.sleep(1)
                
                # 提取当前页面的销售记录
                page_sales = await self.extract_sales_records(page)
                
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
                            sale_price=float(sale.get('sale_price', 0)) if sale.get('sale_price') else 0,
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
                if not await self.go_to_next_page(page):
                    break
                
                page_num += 1
                await asyncio.sleep(5)
            
            logger.info(f"成功保存 {total_saved} 条销售记录")
            
            # 更新书籍的销售记录爬取时间和状态
            from ..models.database import db
            update_query = """
                UPDATE books 
                SET last_sales_update = CURRENT_TIMESTAMP,
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
    
    async def extract_sales_records(self, page: Page):
        """提取当前页面的销售记录
        
        Args:
            page: 浏览器页面
        """
        try:
            return await page.evaluate("""
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
                            
                            // 提取价格信息 - 改进版本
                            const priceElement = item.querySelector('.price-info');
                            if (priceElement) {
                                let priceString = '';
                                
                                // 按顺序提取价格组件
                                const priceInt = priceElement.querySelector('.price-int');
                                const priceDot = priceElement.querySelector('.price-dot');
                                const priceFloat = priceElement.querySelector('.price-float');
                                
                                if (priceInt) {
                                    priceString += priceInt.textContent.trim();
                                }
                                if (priceDot) {
                                    priceString += priceDot.textContent.trim();
                                }
                                if (priceFloat) {
                                    priceString += priceFloat.textContent.trim();
                                }
                                
                                if (priceString) {
                                    record.sale_price = parseFloat(priceString);
                                }
                            }
                            
                            // 如果没有找到价格，尝试其他选择器
                            if (!record.sale_price || record.sale_price === 0) {
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
    
    async def go_to_next_page(self, page: Page):
        """翻到下一页
        
        Args:
            page: 浏览器页面
        """
        try:
            # 查找下一页按钮
            next_button = await page.query_selector('a.next-page:not(.disabled)')
            if next_button:
                await next_button.click()
                await asyncio.sleep(5)
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
            'sales_records': sales[:300]  # 返回最多300条记录用于展示
        }
        
        if not sales:
            return stats
        
        prices = []
        
        for sale in sales:
            sale_date = sale.get('sale_date')
            
            if sale_date:
                # 如果是字符串，转换为datetime对象
                if isinstance(sale_date, str):
                    try:
                        sale_date = datetime.fromisoformat(sale_date.replace('Z', '+00:00'))
                    except:
                        continue
                
                # 更新最新销售日期
                if not stats['latest_sale_date'] or sale_date > datetime.fromisoformat(stats['latest_sale_date'].replace('Z', '+00:00') if 'Z' in stats['latest_sale_date'] else stats['latest_sale_date']):
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
    
    @WindowPoolManager()
    async def crawl_book_sales(self, isbn: str, page: Page = None) -> Dict:
        """爬取单本书籍的销售数据
        
        Args:
            isbn: 书籍ISBN
            page: 浏览器页面（由装饰器自动注入）
        """
        try:
            # 搜索书籍
            search_url = f"https://search.kongfz.com/product/?keyword={isbn}&dataType=1&sortType=10&page=1"
            await self._safe_page_goto(page, search_url, wait_until='networkidle')
            await asyncio.sleep(5)
            
            sales_records = []
            page_num = 1
            max_pages = 10  # 最多爬取10页
            
            while page_num <= max_pages:
                # 提取当前页面的销售记录
                page_sales = await self.extract_sales_records(page)
                
                if not page_sales:
                    break
                
                for sale in page_sales:
                    if sale.get('isbn') == isbn:
                        sales_records.append(sale)
                
                # 尝试翻页
                if not await self.goto_next_page():
                    break
                
                page_num += 1
                await asyncio.sleep(5)
            
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
        """爬取店铺所有书籍的销售数据，基于数据库中该店铺的书籍库存记录
        
        注意：这个方法会多次调用analyze_and_save_book_sales，每次都会从池中获取窗口
        """
        try:
            logger.info(f"开始爬取店铺 {shop_id} 的销售数据")
            
            # 检查当前封控状态
            rate_limit_status = self.get_rate_limit_status()
            if rate_limit_status["is_rate_limited"]:
                current_time_display = rate_limit_status["current_wait_time"]["display_text"]
                logger.info(f"当前处于封控状态，等待时间: {current_time_display}")
            
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
                    # analyze_and_save_book_sales会自动从池中获取窗口
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
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    error_count += 1
                    error_msg = str(e)
                    
                    # 检查是否遇到频率限制
                    if self._is_rate_limit_error(error_msg):
                        # 更新封控等待时间（指数退避）
                        self._update_rate_limit_wait_time(success=False)
                        wait_time = self._get_current_wait_time()
                        
                        # 格式化等待时间显示
                        wait_minutes = wait_time // 60
                        if wait_minutes >= 60:
                            wait_hours = wait_minutes // 60
                            remaining_minutes = wait_minutes % 60
                            if remaining_minutes > 0:
                                time_display = f"{wait_hours}小时{remaining_minutes}分钟"
                            else:
                                time_display = f"{wait_hours}小时"
                        else:
                            time_display = f"{wait_minutes}分钟"
                        
                        logger.warning(f"遇到访问频率限制，等待 {time_display} 后继续: {error_msg}")
                        await asyncio.sleep(wait_time)
                        continue  # 继续处理下一本书
                    
                    logger.error(f"爬取ISBN {isbn} 失败: {e}")
                    continue
            
            logger.info(f"店铺 {shop_id} 销售数据爬取完成: 成功 {success_count} 本，失败 {error_count} 本，总共保存 {total_sales} 条销售记录")
            
            # 显示最终封控状态
            final_status = self.get_rate_limit_status()
            if final_status["is_rate_limited"]:
                current_time_display = final_status["current_wait_time"]["display_text"]
                logger.warning(f"爬取结束时仍处于封控状态，当前等待时间: {current_time_display}")
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
    
    def _is_login_required(self, page_content: str, current_url: str) -> bool:
        """检测是否需要登录"""
        # 检查URL是否跳转到登录页面
        if "login" in current_url.lower() or "signin" in current_url.lower():
            return True
        
        # 更严格的登录检测 - 只检查明确的登录提示
        strict_login_keywords = [
            "请先登录",
            "用户登录",
            "需要登录",
            "登录账号",
            "立即登录",
            "登录孔夫子"
        ]
        
        content_lower = page_content.lower()
        
        # 排除一些正常的页面内容
        if ("搜索结果" in content_lower or 
            "商品列表" in content_lower or
            "暂无商品" in content_lower or
            "无搜索结果" in content_lower):
            return False
        
        # 只有明确包含登录提示才判断为需要登录
        return any(keyword.lower() in content_lower for keyword in strict_login_keywords)
    
    def _is_login_required_error(self, error_message: str) -> bool:
        """检测错误信息是否与登录相关"""
        return "LOGIN_REQUIRED:" in error_message
    
    async def _check_page_content_for_empty_results(self, page: Page) -> None:
        """检查页面内容为空是否是因为未登录
        
        Args:
            page: 浏览器页面
        """
        if not page:
            return
        
        try:
            # 检查页面是否有搜索结果容器但内容为空
            page_analysis = await page.evaluate("""
                () => {
                    // 检查是否有搜索结果容器
                    const searchResults = document.querySelector('.search-results, .result-list, .product-list');
                    const productItems = document.querySelectorAll('.product-item-wrap, .product-item');
                    const noResults = document.querySelector('.no-results, .empty-results');
                    
                    // 检查页面文本内容
                    const bodyText = document.body.innerText || '';
                    const title = document.title || '';
                    
                    // 检查是否有明确的"无搜索结果"提示
                    const noResultsText = bodyText.includes('无搜索结果') || 
                                         bodyText.includes('没有找到') ||
                                         bodyText.includes('暂无商品') ||
                                         bodyText.includes('抱歉，没有找到相关商品');
                    
                    return {
                        hasSearchContainer: !!searchResults,
                        productCount: productItems.length,
                        hasNoResultsMsg: !!noResults,
                        bodyText: bodyText.substring(0, 500), // 只取前500字符用于调试
                        title: title,
                        url: window.location.href,
                        hasNoResultsText: noResultsText
                    };
                }
            """)
            
            # 调试：打印页面分析结果
            logger.info(f"页面分析结果: {page_analysis}")
            
            # 分析结果
            if page_analysis:
                body_text = page_analysis.get('bodyText', '').lower()
                title = page_analysis.get('title', '').lower()
                product_count = page_analysis.get('productCount', 0)
                has_no_results_text = page_analysis.get('hasNoResultsText', False)
                
                # 只有在明确没有"无搜索结果"提示，且页面内容包含登录关键词时才判断为需要登录
                if (product_count == 0 and 
                    not has_no_results_text and
                    ('请登录' in body_text or 
                     '用户登录' in body_text or
                     'login' in body_text)):
                    
                    logger.warning(f"检测到可能需要登录: 商品数={product_count}, 无结果提示={has_no_results_text}, 页面文本包含登录关键词")
                    raise Exception("LOGIN_REQUIRED:页面显示为空，可能需要登录孔夫子旧书网账号。请在浏览器中登录后重试。")
                else:
                    logger.info(f"页面检查通过: 商品数={product_count}, 无结果提示={has_no_results_text}")
                    
        except Exception as e:
            error_str = str(e)
            if "LOGIN_REQUIRED:" in error_str:
                raise
            # 其他异常不处理
    
    async def _check_page_for_rate_limit(self, page: Page) -> None:
        """检查页面内容是否包含频率限制或登录要求
        
        Args:
            page: 浏览器页面
        """
        if not page:
            return
        
        try:
            # 检查页面标题和内容
            page_content = await page.evaluate("""
                () => {
                    return {
                        title: document.title,
                        body: document.body.innerText || '',
                        html: document.documentElement.innerHTML || '',
                        url: window.location.href
                    };
                }
            """)
            
            # 检查所有内容
            all_content = f"{page_content.get('title', '')} {page_content.get('body', '')} {page_content.get('html', '')}"
            current_url = page_content.get('url', '')
            
            # 检查登录状态
            if self._is_login_required(all_content, current_url):
                raise Exception("LOGIN_REQUIRED:需要登录孔夫子旧书网账号才能访问销售数据。请在浏览器中登录后重试。")
            
            # 检查频率限制
            if self._is_rate_limit_error(all_content):
                raise Exception("RATE_LIMITED:很抱歉，您当前的搜索次数已达到上限，请稍后访问！请求错误，请降低访问频次或更换真实账号使用。")
                
        except Exception as e:
            error_str = str(e)
            if self._is_rate_limit_error(error_str) or self._is_login_required_error(error_str):
                raise
            # 其他异常不处理，继续执行
    
    async def extract_book_info_from_current_page(self, page: Page) -> Dict:
        """从当前页面提取书籍信息
        
        Args:
            page: 浏览器页面
        """
        try:
            # 从搜索结果页面提取书籍信息
            return await page.evaluate("""
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
    
    async def extract_shop_sales_records(self, page: Page) -> List[Dict]:
        """提取店铺销售记录页面的数据
        
        Args:
            page: 浏览器页面
        """
        try:
            sales = await page.evaluate("""
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
    
    @WindowPoolManager()
    async def crawl_shop_books(self, shop_id: str, max_pages: int = 50, page: Page = None) -> int:
        """爬取店铺的书籍列表
        
        Args:
            shop_id: 店铺ID
            max_pages: 最大爬取页数
            page: 浏览器页面（由装饰器自动注入）
        """
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
            await self._safe_page_goto(page, url, wait_until='networkidle')
            await asyncio.sleep(5)  # 等待页面加载
            
            while current_page <= max_pages:
                try:
                    # 提取书籍信息
                    books_data = await page.evaluate("""
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
                    has_next_page = await page.evaluate("""
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
                    await page.evaluate("""
                        () => {
                            const nextBtn = document.querySelector('.next-btn') || 
                                           document.querySelector('.pagination .next') ||
                                           document.querySelector('a[title="下一页"]') ||
                                           document.querySelector('.page-next:not(.disabled)');
                            if (nextBtn) nextBtn.click();
                        }
                    """)
                    
                    # 等待新页面加载
                    await asyncio.sleep(5)
                    
                    # 等待页面稳定
                    try:
                        await page.wait_for_load_state('networkidle', timeout=5000)
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
                    await asyncio.sleep(5)
                    continue
            
            # 更新任务为完成
            self.task_repo.update_status(task_id, 'completed', 100)
            logger.info(f"成功爬取店铺 {shop_id} 的 {books_crawled} 本书籍")
            return books_crawled
            
        except Exception as e:
            logger.error(f"爬取店铺失败: {e}")
            self.task_repo.update_status(task_id, 'failed', error_message=str(e))
            raise
    
    @WindowPoolManager()
    async def crawl_book_sales(self, isbn: str, days_limit: int = 30, page: Page = None) -> List[Dict]:
        """爬取书籍的销售记录
        
        Args:
            isbn: 书籍ISBN
            days_limit: 天数限制
            page: 浏览器页面（由装饰器自动注入）
        """
        url = f"https://search.kongfz.com/product/?keyword={isbn}&dataType=1&sortType=10&page=1"
        cutoff_date = datetime.now() - timedelta(days=days_limit)
        all_sales = []
        
        try:
            await self._safe_page_goto(page, url, wait_until='networkidle')
            await asyncio.sleep(5)
            
            # 提取已售记录
            sales_data = await page.evaluate("""
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

class CrawlerTaskExecutor:
    """爬虫任务执行器 - 维护任务类型与执行方法的映射"""
    
    # 任务类型映射：key=任务类型，value=执行方法和必需字段
    TASK_TYPE_MAPPING = {
        'book_sales_crawl': {
            'method': 'crawl_single_book_sales',
            'required_fields': ['target_isbn', 'shop_id'],
            'optional_fields': ['days_limit', 'skip_if_recent'],
            'description': '单本书籍销售记录爬取'
        },
        'shop_books_crawl': {
            'method': 'crawl_shop_books', 
            'required_fields': ['target_url'],
            'optional_fields': ['max_pages'],
            'description': '店铺书籍列表爬取'
        },
        'duozhuayu_price': {
            'method': 'update_book_price',
            'required_fields': ['target_isbn', 'shop_id'],
            'optional_fields': [],
            'description': '多抓鱼价格更新'
        },
        'isbn_analysis': {
            'method': 'analyze_book_sales',
            'required_fields': ['target_isbn'],
            'optional_fields': ['days_limit', 'quality_filter'],
            'description': 'ISBN销售数据分析'
        }
    }
    
    def __init__(self):
        self.kongfuzi = KongfuziCrawler()
        self.duozhuayu = DuozhuayuCrawler()
        self.task_repo = CrawlTaskRepository()
    
    def get_task_method_info(self, task_type: str) -> Dict[str, Any]:
        """获取任务类型对应的方法信息"""
        return self.TASK_TYPE_MAPPING.get(task_type, {})
    
    def validate_task_params(self, task_type: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """验证任务参数是否满足要求，返回提取的参数"""
        mapping = self.get_task_method_info(task_type)
        if not mapping:
            raise ValueError(f"未知的任务类型: {task_type}")
        
        params = {}
        
        # 检查必需字段
        for field in mapping['required_fields']:
            value = task.get(field)
            if value is None:
                raise ValueError(f"任务类型 {task_type} 缺少必需字段: {field}")
            params[field] = value
        
        # 添加可选字段
        for field in mapping['optional_fields']:
            value = task.get(field)
            if value is not None:
                params[field] = value
        
        return params
    
    async def execute_task_by_type(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """根据任务类型执行相应的爬虫方法"""
        task_type = task.get('task_type')
        task_id = task.get('id')
        
        if not task_type:
            raise ValueError("任务缺少task_type字段")
        
        mapping = self.get_task_method_info(task_type)
        if not mapping:
            raise ValueError(f"不支持的任务类型: {task_type}")
        
        # 验证参数
        params = self.validate_task_params(task_type, task)
        method_name = mapping['method']
        
        # 更新任务状态为运行中
        self.task_repo.update_status(task_id, 'running')
        
        try:
            # 根据任务类型选择对应的爬虫实例和方法
            if task_type in ['book_sales_crawl', 'shop_books_crawl', 'isbn_analysis']:
                crawler_instance = self.kongfuzi
            elif task_type == 'duozhuayu_price':
                crawler_instance = self.duozhuayu
            else:
                raise ValueError(f"任务类型 {task_type} 没有对应的爬虫实例")
            
            # 获取方法并执行
            method = getattr(crawler_instance, method_name)
            if not method:
                raise AttributeError(f"爬虫实例没有方法: {method_name}")
            
            # 执行方法
            if task_type == 'book_sales_crawl':
                result = await method(
                    params['target_isbn'], 
                    params['shop_id'],
                    params.get('days_limit', 30),
                    params.get('skip_if_recent', True)
                )
            elif task_type == 'shop_books_crawl':
                # 从target_url提取shop_id
                shop_id = self._extract_shop_id_from_url(params['target_url'])
                result = await method(shop_id, params.get('max_pages', 50))
                result = {'books_crawled': result, 'status': 'completed'}
            elif task_type == 'duozhuayu_price':
                result = await method(params['target_isbn'], params['shop_id'])
                result = {'updated': result, 'status': 'completed' if result else 'failed'}
            elif task_type == 'isbn_analysis':
                result = await method(
                    params['target_isbn'],
                    params.get('days_limit', 30),
                    params.get('quality_filter', 'high')
                )
                result = {'analysis_data': result, 'status': 'completed'}
            else:
                raise ValueError(f"未实现的任务类型执行逻辑: {task_type}")
            
            return result
            
        except Exception as e:
            logger.error(f"执行任务 {task_id} ({task_type}) 失败: {e}")
            raise
    
    def _format_success_message(self, task_type: str, result: Dict[str, Any]) -> str:
        """格式化成功消息"""
        if task_type == 'book_sales_crawl':
            return f"成功爬取销售记录"
        elif task_type == 'shop_books_crawl':
            books_count = result.get('books_crawled', 0)
            return f"成功爬取 {books_count} 本书籍"
        elif task_type == 'duozhuayu_price':
            return "成功更新多抓鱼价格"
        elif task_type == 'isbn_analysis':
            return "成功完成ISBN分析"
        else:
            return "任务执行成功"
    
    def _extract_shop_id_from_url(self, url: str) -> str:
        """从URL中提取店铺ID"""
        import re
        match = re.search(r'/([^/]+)/', url.rstrip('/'))
        if match:
            return match.group(1)
        return url.split('/')[-2] if '/' in url else url
    
    async def execute_incomplete_tasks(self) -> Dict[str, Any]:
        """执行所有未完成的任务"""
        pending_tasks = self.task_repo.get_pending_tasks()
        results = {
            'total_tasks': len(pending_tasks),
            'completed': 0,
            'failed': 0,
            'skipped': 0,
            'task_results': []
        }
        
        for task in pending_tasks:
            task_id = task.get('id')
            task_type = task.get('task_type')
            
            try:
                result = await self.execute_task_by_type(task)
                
                # 根据结果更新任务状态
                if result.get('status') == 'completed':
                    self.task_repo.update_status(
                        task_id, 'completed', 
                        progress=100.0,
                        error_message=self._format_success_message(task_type, result)
                    )
                    results['completed'] += 1
                elif result.get('status') == 'skipped':
                    self.task_repo.update_status(
                        task_id, 'skipped',
                        progress=100.0,
                        error_message=result.get('message', '任务已跳过')
                    )
                    results['skipped'] += 1
                else:
                    self.task_repo.update_status(
                        task_id, 'failed',
                        error_message=result.get('message', '任务执行失败')
                    )
                    results['failed'] += 1
                
                results['task_results'].append({
                    'task_id': task_id,
                    'task_type': task_type,
                    'status': result.get('status'),
                    'result': result
                })
                
            except Exception as e:
                error_msg = str(e)
                self.task_repo.update_status(task_id, 'failed', error_message=error_msg)
                results['failed'] += 1
                results['task_results'].append({
                    'task_id': task_id,
                    'task_type': task_type,
                    'status': 'failed',
                    'error': error_msg
                })
                logger.error(f"执行任务 {task_id} 失败: {e}")
        
        return results
    
    def _format_success_message(self, task_type: str, result: Dict[str, Any]) -> str:
        """格式化成功消息"""
        if task_type == 'book_sales_crawl':
            return f"保存了 {result.get('records_saved', 0)} 条销售记录"
        elif task_type == 'shop_books_crawl':
            return f"爬取了 {result.get('books_crawled', 0)} 本书籍"
        elif task_type == 'shop_sales_batch':
            return f"爬取了 {result.get('sales_crawled', 0)} 条销售记录"
        elif task_type == 'duozhuayu_price':
            return "价格更新成功" if result.get('updated') else "价格更新失败"
        elif task_type == 'isbn_analysis':
            data = result.get('analysis_data', {})
            return f"分析完成，共 {data.get('total_records', 0)} 条记录"
        else:
            return "任务执行成功"


class CrawlerManager:
    """爬虫管理器 - 统一管理所有爬虫（保持向后兼容）"""
    
    def __init__(self):
        self.kongfuzi = KongfuziCrawler()
        self.duozhuayu = DuozhuayuCrawler()
        self.task_repo = CrawlTaskRepository()
        self.executor = CrawlerTaskExecutor()
    
    async def run_pending_tasks(self):
        """运行待执行的任务（使用新的执行器）"""
        return await self.executor.execute_incomplete_tasks()
    
    async def run_pending_tasks_legacy(self):
        """运行待执行的任务（保持旧版本兼容性）"""
        tasks = self.task_repo.get_pending_tasks()
        
        for task in tasks:
            try:
                # 更新任务状态为运行中
                self.task_repo.update_status(task['id'], 'running')
                
                if task['task_type'] == 'book_sales_crawl':
                    # 新的书籍级别销售记录爬取任务
                    isbn = task['target_isbn']
                    shop_id = task['shop_id']
                    
                    if isbn and shop_id:
                        result = await self.kongfuzi.crawl_single_book_sales(
                            isbn, shop_id, skip_if_recent=True
                        )
                        
                        if result['status'] == 'completed':
                            self.task_repo.update_status(
                                task['id'], 'completed', 
                                progress=100.0,
                                error_message=f"保存了 {result['records_saved']} 条记录"
                            )
                        elif result['status'] == 'skipped':
                            self.task_repo.update_status(
                                task['id'], 'skipped',
                                progress=100.0,
                                error_message=result['message']
                            )
                        else:
                            self.task_repo.update_status(
                                task['id'], 'failed',
                                error_message=result['message']
                            )
                    else:
                        self.task_repo.update_status(
                            task['id'], 'failed',
                            error_message="缺少必要参数: ISBN或shop_id"
                        )
                        
                elif task['task_type'] == 'shop_books_crawl':
                    # 店铺书籍爬取任务
                    shop_id = task.get('target_url', '').split('/')[-2] if task.get('target_url') else None
                    if shop_id:
                        books_crawled = await self.kongfuzi.crawl_shop_books(shop_id)
                        self.task_repo.update_status(
                            task['id'], 'completed',
                            progress=100.0,
                            error_message=f"爬取了 {books_crawled} 本书籍"
                        )
                    else:
                        self.task_repo.update_status(
                            task['id'], 'failed',
                            error_message="无法解析店铺ID"
                        )
                        
                elif task['task_type'] == 'shop_books':
                    # 兼容旧版本任务类型
                    await self.kongfuzi.crawl_shop_books(task['target_url'])
                    self.task_repo.update_status(task['id'], 'completed', progress=100.0)
                    
                elif task['task_type'] == 'book_sales':
                    # 兼容旧版本任务类型
                    params = json.loads(task['task_params']) if task['task_params'] else {}
                    isbn = params.get('isbn')
                    if isbn:
                        await self.kongfuzi.crawl_book_sales(isbn)
                        self.task_repo.update_status(task['id'], 'completed', progress=100.0)
                        
                elif task['task_type'] == 'duozhuayu_price':
                    # 更新多抓鱼价格
                    params = json.loads(task['task_params']) if task['task_params'] else {}
                    isbn = params.get('isbn')
                    shop_id = params.get('shop_id')
                    if isbn and shop_id:
                        await self.duozhuayu.update_book_price(isbn, shop_id)
                        self.task_repo.update_status(task['id'], 'completed', progress=100.0)
                        
            except Exception as e:
                logger.error(f"执行任务 {task['id']} 失败: {e}")
                self.task_repo.update_status(task['id'], 'failed', error_message=str(e))
    
    async def cleanup(self):
        """清理资源"""
        await self.kongfuzi.disconnect_browser()


class TaskQueue:
    """内存任务队列管理器（单例模式）"""
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.queue = deque()
            self.running_tasks = set()
            self.task_executor = CrawlerTaskExecutor()
            self.task_repo = CrawlTaskRepository()
            self._lock = asyncio.Lock()
            self._processing = False
            TaskQueue._initialized = True
    
    async def add_tasks(self, task_ids: List[int]) -> int:
        """将任务添加到队列"""
        added_count = 0
        should_start_processing = False
        
        async with self._lock:
            for task_id in task_ids:
                if task_id not in self.running_tasks and task_id not in self.queue:
                    # 只加入内存队列，不更改数据库状态
                    self.queue.append(task_id)
                    added_count += 1
            
            # 如果队列不为空且没有在处理，标记需要启动处理
            if self.queue and not self._processing:
                should_start_processing = True
                self._processing = True  # 立即标记为处理中，避免重复启动
        
        # 在锁外启动处理，避免长时间持有锁
        if should_start_processing:
            asyncio.create_task(self._process_queue())
        
        return added_count
    
    async def add_pending_tasks(self) -> int:
        """将所有待执行任务添加到队列"""
        pending_tasks = self.task_repo.get_pending_tasks()
        task_ids = [task['id'] for task in pending_tasks]
        return await self.add_tasks(task_ids)
    
    async def clear_queue(self) -> int:
        """清空任务队列"""
        async with self._lock:
            # 只清空内存队列，不更改数据库状态
            cleared_count = len(self.queue)
            self.queue.clear()
            
            return cleared_count
    
    async def clear_all_tasks(self) -> Dict[str, int]:
        """清空队列并删除所有待执行任务"""
        async with self._lock:
            # 直接清空队列，不调用clear_queue避免重复获取锁
            queue_count = len(self.queue)
            self.queue.clear()
            
            # 删除所有pending任务
            from ..models.database import db
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM crawl_tasks WHERE status IN ('pending', 'queued')")
                deleted_count = cursor.rowcount
                conn.commit()
            
            return {
                "queue_cleared": queue_count,
                "tasks_deleted": deleted_count
            }

    async def retry_failed_tasks(self) -> int:
        """重试所有失败的任务"""
        async with self._lock:
            from ..models.database import db
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 查找所有失败的任务
                cursor.execute("SELECT id FROM crawl_tasks WHERE status = 'failed'")
                failed_tasks = cursor.fetchall()
                
                if not failed_tasks:
                    return 0
                
                failed_task_ids = [task[0] for task in failed_tasks]
                
                # 更新状态为待执行
                placeholders = ",".join(["?"] * len(failed_task_ids))
                cursor.execute(f"UPDATE crawl_tasks SET status = 'pending' WHERE id IN ({placeholders})", failed_task_ids)
                updated_count = cursor.rowcount
                conn.commit()
                
                # 添加到内存队列
                added_to_queue = 0
                for task_id in failed_task_ids:
                    if task_id not in self.running_tasks and task_id not in self.queue:
                        self.queue.append(task_id)
                        added_to_queue += 1
                
                # 如果队列不为空且没有在处理，启动处理
                if self.queue and not self._processing:
                    asyncio.create_task(self._process_queue())
                
                return updated_count
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return {
            "queue_length": len(self.queue),
            "running_count": len(self.running_tasks),
            "is_processing": self._processing,
            "next_tasks": list(self.queue)[:5]  # 显示前5个任务
        }
    
    async def _process_queue(self):
        """处理队列中的任务"""
        self._processing = True
        logger.info("开始处理任务队列")
        
        try:
            while self.queue:
                async with self._lock:
                    if not self.queue:
                        break
                    task_id = self.queue.popleft()
                    self.running_tasks.add(task_id)
                
                try:
                    # 获取任务详情
                    task = self.task_repo.get_by_id(task_id)
                    if not task:
                        logger.warning(f"任务 {task_id} 不存在")
                        continue
                    
                    if task.get('status') not in ['queued', 'pending']:
                        logger.warning(f"任务 {task_id} 状态不正确: {task.get('status')}")
                        continue
                    
                    # 执行任务
                    logger.info(f"开始执行任务 {task_id}: {task.get('task_name')}")
                    result = await self.task_executor.execute_task_by_type(task)
                    
                    # 更新任务状态
                    if result.get('status') == 'completed':
                        self.task_repo.update_status(
                            task_id, 'completed',
                            progress=100.0,
                            error_message=self.task_executor._format_success_message(task.get('task_type'), result)
                        )
                        logger.info(f"任务 {task_id} 执行成功")
                    elif result.get('status') == 'skipped':
                        self.task_repo.update_status(
                            task_id, 'skipped',
                            progress=100.0,
                            error_message=result.get('message', '任务已跳过')
                        )
                        logger.info(f"任务 {task_id} 已跳过")
                    else:
                        self.task_repo.update_status(
                            task_id, 'failed',
                            error_message=result.get('message', '任务执行失败')
                        )
                        logger.error(f"任务 {task_id} 执行失败: {result.get('message')}")
                
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"处理任务 {task_id} 时发生异常: {e}")
                    
                    # 简单标记为失败
                    try:
                        self.task_repo.update_status(task_id, 'failed', error_message=error_msg)
                    except:
                        pass
                
                finally:
                    async with self._lock:
                        self.running_tasks.discard(task_id)
                
                # 任务间间隔，避免过快执行
                await asyncio.sleep(1)
        
        finally:
            self._processing = False
            logger.info("任务队列处理完成")


# 全局任务队列实例
task_queue = TaskQueue()