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
    
    def get_hot_sales_ranking(self, days: int = 7, limit: int = 20) -> List[Dict]:
        """获取热销排行榜"""
        hot_sales = self.sales_repo.get_hot_sales(days, limit)
        
        # 添加排名
        for i, item in enumerate(hot_sales, 1):
            item['rank'] = i
            # 格式化价格
            item['avg_price'] = round(item['avg_price'], 2) if item['avg_price'] else 0
            item['min_price'] = round(item['min_price'], 2) if item['min_price'] else 0
            item['max_price'] = round(item['max_price'], 2) if item['max_price'] else 0
        
        return hot_sales
    
    def get_profitable_items(self, min_margin: float = 20.0) -> List[Dict]:
        """获取有利润的商品列表"""
        items = self.inventory_repo.get_profitable_items(min_margin)
        
        # 按利润率排序
        items.sort(key=lambda x: x.get('profit_margin_second_hand', 0), reverse=True)
        
        # 格式化数据
        for item in items:
            item['profit_margin_second_hand'] = round(item['profit_margin_second_hand'], 2)
            item['price_diff_second_hand'] = round(item['price_diff_second_hand'], 2)
            item['expected_profit'] = round(
                item['kongfuzi_price'] * item['profit_margin_second_hand'] / 100, 2
            )
        
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
                   COUNT(DISTINCT sr.book_id) as book_count,
                   COUNT(sr.id) as sales_count,
                   SUM(sr.sale_price) as total_revenue,
                   AVG(sr.sale_price) as avg_price
            FROM sales_records sr
            JOIN books b ON sr.book_id = b.id
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
                   COUNT(DISTINCT bi.book_id) as book_count,
                   COUNT(sr.id) as sales_count,
                   COALESCE(SUM(sr.sale_price), 0) as total_revenue,
                   COALESCE(AVG(sr.sale_price), 0) as avg_price
            FROM shops s
            LEFT JOIN book_inventory bi ON s.id = bi.shop_id
            LEFT JOIN sales_records sr ON s.id = sr.shop_id
            WHERE s.status = 'active'
            GROUP BY s.id
            ORDER BY total_revenue DESC
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
            WHERE bi.book_id = ?
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
    
    def get_dashboard_data(self) -> Dict:
        """获取仪表板数据"""
        return {
            'today_stats': self.get_sales_statistics(1),
            'week_stats': self.get_sales_statistics(7),
            'month_stats': self.get_sales_statistics(30),
            'hot_sales': self.get_hot_sales_ranking(7, 10),
            'profitable_items': self.get_profitable_items(20)[:10],
            'sales_trend': self.get_sales_trend(7),
            'shop_performance': self.get_shop_performance()[:5]
        }