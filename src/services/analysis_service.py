#!/usr/bin/env python3
"""
数据分析服务模块 - 负责数据统计和分析
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics
import logging

from ..models.repositories import (
    BookRepository, BookInventoryRepository, 
    SalesRepository, StatisticsRepository
)

logger = logging.getLogger(__name__)

class AnalysisService:
    """数据分析服务"""
    
    def __init__(self):
        self.book_repo = BookRepository()
        self.inventory_repo = BookInventoryRepository()
        self.sales_repo = SalesRepository()
        self.stats_repo = StatisticsRepository()
        # 添加简单的内存缓存
        self._cache = {}
        self._cache_ttl = {}
    
    def get_sales_statistics(self, days: int) -> Dict:
        """获取销售统计数据"""
        sales = self.sales_repo.get_sales_by_period(days)
        
        if not sales:
            return {
                'total_sales': 0,
                'total_revenue': 0,
                'avg_price': 0,
                'median_price': 0,
                'mode_price': 0,
                'min_price': 0,
                'max_price': 0
            }
        
        prices = [s['sale_price'] for s in sales if s['sale_price']]
        
        # 计算统计数据
        result = {
            'total_sales': len(sales),
            'total_revenue': sum(prices),
            'avg_price': statistics.mean(prices) if prices else 0,
            'median_price': statistics.median(prices) if prices else 0,
            'min_price': min(prices) if prices else 0,
            'max_price': max(prices) if prices else 0
        }
        
        # 计算众数（可能有多个）
        try:
            result['mode_price'] = statistics.mode(prices)
        except statistics.StatisticsError:
            # 如果没有唯一众数，取中位数
            result['mode_price'] = result['median_price']
        
        return result
    
    def get_price_statistics_with_outlier_removal(self, prices: List[float], 
                                                  percentile: float = 0.1) -> Dict:
        """去除异常值后的价格统计"""
        if not prices:
            return {
                'avg_price': 0,
                'median_price': 0,
                'mode_price': 0,
                'min_price': 0,
                'max_price': 0
            }
        
        # 排序价格
        sorted_prices = sorted(prices)
        
        # 去除首尾异常值
        trim_count = int(len(sorted_prices) * percentile)
        if trim_count > 0 and len(sorted_prices) > 2 * trim_count:
            trimmed_prices = sorted_prices[trim_count:-trim_count]
        else:
            trimmed_prices = sorted_prices
        
        result = {
            'avg_price': statistics.mean(trimmed_prices),
            'median_price': statistics.median(trimmed_prices),
            'min_price': min(trimmed_prices),
            'max_price': max(trimmed_prices),
            'original_count': len(prices),
            'trimmed_count': len(trimmed_prices)
        }
        
        # 计算众数
        try:
            result['mode_price'] = statistics.mode(trimmed_prices)
        except statistics.StatisticsError:
            result['mode_price'] = result['median_price']
        
        return result
    
    def get_hot_sales_ranking(self, days: int = 7, limit: int = 20, offset: int = 0, sort_by: str = "sale_count", sort_order: str = "desc") -> List[Dict]:
        """获取热销排行榜"""
        hot_sales = self.sales_repo.get_hot_sales(days, limit, offset, sort_by, sort_order)
        
        # 添加排名
        for i, item in enumerate(hot_sales, 1):
            item['rank'] = offset + i  # 排名要加上offset
            # 格式化价格
            item['avg_price'] = round(item['avg_price'], 2) if item['avg_price'] else 0
            item['min_price'] = round(item['min_price'], 2) if item['min_price'] else 0
            item['max_price'] = round(item['max_price'], 2) if item['max_price'] else 0
        
        return hot_sales
    
    def get_profitable_items(self, min_margin: float = 20.0, limit: int = 20, offset: int = 0, sort_by: str = "price_diff", sort_order: str = "desc") -> List[Dict]:
        """获取有利润的商品列表"""
        items = self.inventory_repo.get_profitable_items(min_margin, limit, offset, sort_by, sort_order)
        
        # 格式化数据
        for i, item in enumerate(items):
            item['rank'] = offset + i + 1
            item['profit_margin_second_hand'] = round(item.get('profit_margin_second_hand', 0), 2)
            item['price_diff_second_hand'] = round(item.get('price_diff_second_hand', 0), 2)
            item['expected_profit'] = round(
                item.get('kongfuzi_price', 0) * item.get('profit_margin_second_hand', 0) / 100, 2
            )
            # 为前端重命名字段
            item['kongfuzi_price'] = item.get('kongfuzi_price', 0)
            item['duozhuayu_price'] = item.get('duozhuayu_second_hand_price', 0)
            item['price_diff'] = item['price_diff_second_hand']
            item['profit_rate'] = item['profit_margin_second_hand']
        
        return items
    
    def get_sales_trend(self, days: int = 30) -> List[Dict]:
        """获取销售趋势数据"""
        trend_data = []
        
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            
            # 获取当天的销售数据
            query = """
                SELECT COUNT(*) as sales_count, 
                       COALESCE(SUM(sale_price), 0) as total_revenue
                FROM sales_records
                WHERE DATE(sale_date) = ?
            """
            from ..models.database import db
            results = db.execute_query(query, (date_str,))
            
            if results:
                trend_data.append({
                    'date': date_str,
                    'sales_count': results[0]['sales_count'],
                    'total_revenue': round(results[0]['total_revenue'], 2)
                })
        
        # 反转列表，使最早的日期在前
        trend_data.reverse()
        return trend_data
    
    def get_category_statistics(self) -> List[Dict]:
        """获取分类统计数据"""
        query = """
            SELECT b.category, 
                   COUNT(DISTINCT sr.isbn) as book_count,
                   COUNT(sr.item_id) as sales_count,
                   SUM(sr.sale_price) as total_revenue,
                   AVG(sr.sale_price) as avg_price
            FROM sales_records sr
            JOIN books b ON sr.isbn = b.isbn
            WHERE b.category IS NOT NULL
            GROUP BY b.category
            ORDER BY sales_count DESC
        """
        
        from ..models.database import db
        results = db.execute_query(query)
        
        # 格式化数据
        for item in results:
            item['total_revenue'] = round(item['total_revenue'], 2) if item['total_revenue'] else 0
            item['avg_price'] = round(item['avg_price'], 2) if item['avg_price'] else 0
        
        return results
    
    def get_shop_performance(self) -> List[Dict]:
        """获取店铺业绩统计"""
        query = """
            SELECT s.shop_name, s.shop_id,
                   COUNT(DISTINCT bi.isbn) as book_count,
                   COUNT(sr.item_id) as sales_count,
                   COALESCE(SUM(sr.sale_price), 0) as total_revenue,
                   COALESCE(AVG(sr.sale_price), 0) as avg_price
            FROM shops s
            LEFT JOIN book_inventory bi ON s.id = bi.shop_id
            LEFT JOIN sales_records sr ON s.id = sr.shop_id
            WHERE s.status = 'active'
            GROUP BY s.id
            ORDER BY book_count DESC
        """
        
        from ..models.database import db
        results = db.execute_query(query)
        
        # 格式化数据
        for item in results:
            item['total_revenue'] = round(item['total_revenue'], 2)
            item['avg_price'] = round(item['avg_price'], 2)
            # 计算平均利润率
            if item['sales_count'] > 0:
                item['avg_profit_per_sale'] = round(
                    item['total_revenue'] / item['sales_count'], 2
                )
            else:
                item['avg_profit_per_sale'] = 0
        
        return results
    
    def get_price_comparison(self, isbn: str) -> Dict:
        """获取价格对比数据"""
        # 获取书籍信息
        book = self.book_repo.get_by_isbn(isbn)
        if not book:
            return {}
        
        # 获取所有店铺的库存信息
        query = """
            SELECT bi.*, s.shop_name
            FROM book_inventory bi
            JOIN shops s ON bi.shop_id = s.id
            WHERE bi.isbn = ?
            ORDER BY bi.kongfuzi_price ASC
        """
        
        from ..models.database import db
        inventories = db.execute_query(query, (book['id'],))
        
        result = {
            'book': book,
            'inventories': inventories,
            'price_range': {
                'kongfuzi': {
                    'min': min([i['kongfuzi_price'] for i in inventories if i['kongfuzi_price']], default=0),
                    'max': max([i['kongfuzi_price'] for i in inventories if i['kongfuzi_price']], default=0),
                    'avg': statistics.mean([i['kongfuzi_price'] for i in inventories if i['kongfuzi_price']]) if inventories else 0
                },
                'duozhuayu': {
                    'new_price': inventories[0]['duozhuayu_new_price'] if inventories and inventories[0]['duozhuayu_new_price'] else 0,
                    'second_hand_price': inventories[0]['duozhuayu_second_hand_price'] if inventories and inventories[0]['duozhuayu_second_hand_price'] else 0
                }
            }
        }
        
        # 计算最佳套利机会
        if inventories:
            best_arbitrage = max(
                inventories, 
                key=lambda x: x.get('profit_margin_second_hand', 0)
            )
            result['best_arbitrage'] = {
                'shop_name': best_arbitrage['shop_name'],
                'buy_price': best_arbitrage['kongfuzi_price'],
                'sell_price': best_arbitrage['duozhuayu_second_hand_price'],
                'profit': best_arbitrage['price_diff_second_hand'],
                'profit_margin': best_arbitrage['profit_margin_second_hand']
            }
        
        return result
    
    def calculate_daily_statistics(self):
        """计算每日统计数据"""
        # 计算各种周期的统计
        for period in ['daily', 'weekly', 'monthly']:
            self.stats_repo.calculate_and_save_statistics('sales', period)
            logger.info(f"完成 {period} 销售统计计算")
    
    def get_business_opportunity_statistics(self) -> Dict:
        """获取商机分析统计数据"""
        from ..models.database import db
        
        # 获取商机分析统计
        opportunity_stats = db.execute_query("""
            SELECT 
                COUNT(DISTINCT bi.isbn) as total_books_monitored,
                AVG(bi.kongfuzi_price) as avg_market_price,
                MIN(bi.kongfuzi_price) as min_price,
                MAX(bi.kongfuzi_price) as max_price,
                COUNT(DISTINCT bi.shop_id) as monitored_shops,
                COUNT(CASE WHEN bi.duozhuayu_second_hand_price > 0 AND bi.kongfuzi_price > 0 
                          AND bi.duozhuayu_second_hand_price > bi.kongfuzi_price 
                          THEN 1 END) as profitable_opportunities,
                AVG(CASE WHEN bi.duozhuayu_second_hand_price > bi.kongfuzi_price 
                         THEN ((bi.duozhuayu_second_hand_price - bi.kongfuzi_price) / bi.kongfuzi_price * 100) 
                         ELSE 0 END) as avg_profit_margin
            FROM book_inventory bi
            WHERE bi.kongfuzi_price > 0
        """)
        
        # 获取书籍统计
        book_stats = db.execute_query("""
            SELECT 
                COUNT(*) as total_books,
                SUM(CASE WHEN last_sales_update IS NOT NULL THEN 1 ELSE 0 END) as crawled_books
            FROM books
        """)
        
        # 获取店铺统计
        shop_stats = db.execute_query("""
            SELECT 
                COUNT(*) as total_shops,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_shops
            FROM shops
        """)
        
        opportunity_data = opportunity_stats[0] if opportunity_stats else {}
        book_data = book_stats[0] if book_stats else {}
        shop_data = shop_stats[0] if shop_stats else {}
        
        # 计算商机分析指标
        total_monitored = opportunity_data.get('total_books_monitored', 0)
        profitable_count = opportunity_data.get('profitable_opportunities', 0)
        profit_rate = (profitable_count / total_monitored * 100) if total_monitored > 0 else 0
        
        return {
            'total_books_monitored': total_monitored,
            'profitable_opportunities': profitable_count,
            'profit_discovery_rate': round(profit_rate, 1),
            'avg_profit_margin': round(opportunity_data.get('avg_profit_margin', 0), 2),
            'monitored_shops': opportunity_data.get('monitored_shops', 0),
            'active_shops': shop_data.get('active_shops', 0),
            'avg_market_price': round(opportunity_data.get('avg_market_price', 0), 2),
            'min_price': round(opportunity_data.get('min_price', 0), 2),
            'max_price': round(opportunity_data.get('max_price', 0), 2),
            'price_range': f"{opportunity_data.get('min_price', 0):.2f}-{opportunity_data.get('max_price', 0):.2f}"
        }
    
    def _get_cached_data(self, key: str, ttl_seconds: int = 300):
        """获取缓存数据，5分钟TTL"""
        import time
        current_time = time.time()
        
        if key in self._cache and key in self._cache_ttl:
            if current_time - self._cache_ttl[key] < ttl_seconds:
                return self._cache[key]
        
        return None
    
    def _set_cached_data(self, key: str, data):
        """设置缓存数据"""
        import time
        self._cache[key] = data
        self._cache_ttl[key] = time.time()

    def get_dashboard_data(self) -> Dict:
        """获取仪表板数据 - 优化版本"""
        # 检查缓存
        cached_data = self._get_cached_data('dashboard_data', 180)  # 3分钟缓存
        if cached_data:
            return cached_data
        
        try:
            # 获取基础销售统计（快速查询）
            from ..models.database import db
            
            # 优化：使用单次查询获取多天统计
            quick_stats_query = """
                SELECT 
                    COUNT(*) as total_sales,
                    AVG(sale_price) as avg_price,
                    MIN(sale_price) as min_price,
                    MAX(sale_price) as max_price,
                    SUM(sale_price) as total_revenue,
                    COUNT(DISTINCT isbn) as unique_books,
                    COUNT(DISTINCT shop_id) as active_shops
                FROM sales_records 
                WHERE sale_date >= datetime('now', '-30 days')
            """
            
            quick_stats = db.execute_query(quick_stats_query)
            base_stats = quick_stats[0] if quick_stats else {}
            
            # 构建轻量级仪表板数据
            dashboard_data = {
                'today_stats': {
                    'total_sales': base_stats.get('total_sales', 0),
                    'avg_price': base_stats.get('avg_price', 0),
                    'min_price': base_stats.get('min_price', 0),
                    'max_price': base_stats.get('max_price', 0),
                    'total_revenue': base_stats.get('total_revenue', 0),
                    'books_monitored': base_stats.get('unique_books', 0),
                    'shops_count': base_stats.get('active_shops', 0),
                    'profitable_opportunities': 0,  # 简化，避免复杂计算
                },
                'business_opportunity_stats': {
                    'total_books_monitored': base_stats.get('unique_books', 0),
                    'profitable_opportunities': 0,
                    'active_shops': base_stats.get('active_shops', 0),
                    'discovery_rate': 0,
                    'avg_profit_margin': 0
                },
                # 简化这些复杂查询，使用缓存或延迟加载
                'hot_sales': [],  # 将在前端单独加载
                'profitable_items': [],  # 将在前端单独加载
                'sales_trend': [],  # 将在前端单独加载
                'shop_performance': []  # 将在前端单独加载
            }
            
            # 缓存结果
            self._set_cached_data('dashboard_data', dashboard_data)
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"获取仪表板数据失败: {e}")
            # 返回默认数据，避免页面崩溃
            return {
                'today_stats': {
                    'total_sales': 0,
                    'avg_price': 0,
                    'min_price': 0,
                    'max_price': 0,
                    'total_revenue': 0,
                    'books_monitored': 0,
                    'shops_count': 0,
                    'profitable_opportunities': 0,
                },
                'business_opportunity_stats': {
                    'total_books_monitored': 0,
                    'profitable_opportunities': 0,
                    'active_shops': 0,
                    'discovery_rate': 0,
                    'avg_profit_margin': 0
                },
                'hot_sales': [],
                'profitable_items': [],
                'sales_trend': [],
                'shop_performance': []
            }
    
    def calculate_price_distribution(self, isbn: str) -> Dict:
        """计算价格分布（动态5个区间）"""
        from ..models.database import db
        
        # 获取该ISBN的所有销售记录价格
        query = """
            SELECT sale_price FROM sales_records 
            WHERE isbn = ? AND sale_price > 0
            ORDER BY sale_price
        """
        results = db.execute_query(query, (isbn,))
        
        if not results or len(results) < 2:
            return {"buckets": [], "counts": []}
        
        prices = [r['sale_price'] for r in results]
        min_price = min(prices)
        max_price = max(prices)
        
        # 动态计算5个价格区间
        price_range = max_price - min_price
        if price_range == 0:  # 所有价格相同
            return {
                "buckets": [f"{min_price:.0f}"],
                "counts": [len(prices)]
            }
        
        bucket_size = price_range / 5
        buckets = []
        counts = [0] * 5
        
        # 创建区间标签
        for i in range(5):
            start = min_price + i * bucket_size
            end = min_price + (i + 1) * bucket_size
            if i == 4:  # 最后一个区间包含最大值
                buckets.append(f"{start:.0f}-{end:.0f}")
            else:
                buckets.append(f"{start:.0f}-{end:.0f}")
        
        # 分配价格到区间
        for price in prices:
            bucket_idx = min(int((price - min_price) / bucket_size), 4)
            counts[bucket_idx] += 1
        
        return {
            "buckets": buckets,
            "counts": counts
        }