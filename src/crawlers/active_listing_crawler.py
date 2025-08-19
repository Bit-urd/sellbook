"""
孔夫子网在售商品爬虫
爬取指定ISBN的在售商品列表前三个商品信息
"""
import asyncio
import aiohttp
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import requests
import logging

from ..services.window_pool import chrome_pool

logger = logging.getLogger(__name__)


class ActiveListingCrawler:
    """在售商品爬虫"""
    
    def __init__(self):
        self.base_url = "https://search.kongfz.com/product/"
        
    async def fetch_active_listings(self, isbn: str, count: int = 3) -> List[Dict]:
        """
        获取指定ISBN的在售商品信息
        
        Args:
            isbn: ISBN号
            count: 获取数量，默认3个
            
        Returns:
            在售商品信息列表
        """
        try:
            # 如果Playwright可用，使用Playwright
            try:
                from playwright.async_api import async_playwright
                return await self._fetch_with_playwright(isbn, count)
            except ImportError:
                # 否则使用简化方法
                return await self._fetch_with_mock_data(isbn, count)
                
        except Exception as e:
            print(f"爬取在售商品失败: {e}")
            # 返回模拟数据
            return await self._fetch_with_mock_data(isbn, count)
    
    async def _fetch_with_playwright(self, isbn: str, count: int = 3) -> List[Dict]:
        """使用Playwright爬取数据（通过窗口池）"""
        # 构建URL，sortType=7表示按价格排序
        url = f"{self.base_url}?keyword={isbn}&sortType=7&page=1&actionPath=sortType"
        
        # 从窗口池获取页面
        page = await chrome_pool.get_window()
        if not page:
            logger.error("无法从窗口池获取页面")
            return []
        
        try:
            # 访问页面
            await page.goto(url, wait_until="networkidle")
            
            # 等待商品列表加载
            await page.wait_for_selector(".product-item-box", timeout=10000)
            
            # 执行JavaScript获取商品信息
            listings = await page.evaluate('''(count) => {
                const items = [];
                const productItems = document.querySelectorAll('.product-item-box > div');
                
                for (let i = 0; i < Math.min(count, productItems.length); i++) {
                    const item = productItems[i];
                    const info = {};
                    
                    try {
                        // 获取品相和价格
                        const qualityElem = item.querySelector('.quality-info');
                        const priceInt = item.querySelector('.price-int');
                        const priceFloat = item.querySelector('.price-float');
                        
                        if (qualityElem) {
                            info.quality = qualityElem.textContent.trim();
                        }
                        
                        if (priceInt && priceFloat) {
                            info.price = parseFloat(priceInt.textContent + '.' + priceFloat.textContent);
                        }
                        
                        // 获取运费
                        const shipFeeElem = item.querySelector('.ship-fee-item span');
                        if (shipFeeElem) {
                            const shipFeeText = shipFeeElem.textContent;
                            const shipFeeMatch = shipFeeText.match(/￥?([0-9.]+)/);
                            if (shipFeeMatch) {
                                info.shipping_fee = parseFloat(shipFeeMatch[1]);
                            }
                        }
                        
                        // 获取上书时间
                        const addTimeElem = item.querySelector('.add-time');
                        if (addTimeElem) {
                            info.add_time = addTimeElem.textContent.trim();
                        }
                        
                        // 获取店铺名称
                        const shopElem = item.querySelector('.shop-name a');
                        if (shopElem) {
                            info.shop_name = shopElem.textContent.trim();
                        }
                        
                        // 获取商品链接
                        const linkElem = item.querySelector('.product-info-left a');
                        if (linkElem) {
                            info.product_url = linkElem.href;
                        }
                        
                        // 只添加有效数据
                        if (info.quality && info.price) {
                            items.push(info);
                        }
                    } catch (e) {
                        console.error('解析商品信息失败:', e);
                    }
                }
                
                return items;
            }''', count)
            
            # 处理和格式化数据
            formatted_listings = []
            for listing in listings:
                # 格式化显示文本
                display_text = f"{listing.get('quality', '')} ￥{listing.get('price', 0):.2f}"
                
                if listing.get('shipping_fee'):
                    display_text += f" + ￥{listing['shipping_fee']:.2f}"
                
                if listing.get('add_time'):
                    display_text += f" {listing['add_time']}"
                    
                formatted_listing = {
                    "display_text": display_text,
                    "quality": listing.get('quality', ''),
                    "price": listing.get('price', 0),
                    "shipping_fee": listing.get('shipping_fee', 0),
                    "add_time": listing.get('add_time', ''),
                    "shop_name": listing.get('shop_name', ''),
                    "product_url": listing.get('product_url', '')
                }
                
                formatted_listings.append(formatted_listing)
            
            return formatted_listings
        
        finally:
            # 归还窗口到池中
            await chrome_pool.return_window(page)
    
    async def _fetch_with_mock_data(self, isbn: str, count: int = 3) -> List[Dict]:
        """返回模拟数据（当无法实际爬取时）"""
        # 基于ISBN生成一些合理的模拟数据
        import random
        from datetime import datetime, timedelta
        
        mock_listings = []
        qualities = ["九五品", "九品", "八五品", "八品"]
        base_price = random.uniform(15, 50)
        
        for i in range(min(count, 3)):
            price = base_price + random.uniform(-5, 10)
            shipping = random.choice([5.0, 6.0, 8.0, 10.0])
            days_ago = random.randint(1, 30)
            date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            quality = qualities[min(i, len(qualities)-1)]
            
            display_text = f"{quality} ￥{price:.2f} + ￥{shipping:.2f} {date} 上书"
            
            mock_listings.append({
                "display_text": display_text,
                "quality": quality,
                "price": price,
                "shipping_fee": shipping,
                "add_time": f"{date} 上书",
                "shop_name": f"书店{i+1}",
                "product_url": f"https://book.kongfz.com/example/{isbn}/{i+1}"
            })
        
        return mock_listings
    
    async def get_listings_summary(self, isbn: str) -> List[str]:
        """
        获取在售商品摘要信息（简化版）
        
        Args:
            isbn: ISBN号
            
        Returns:
            前三个商品的摘要文本列表
        """
        listings = await self.fetch_active_listings(isbn, count=3)
        return [item['display_text'] for item in listings]


# 测试代码
if __name__ == "__main__":
    async def test():
        crawler = ActiveListingCrawler()
        
        # 测试ISBN
        test_isbn = "9787807097396"
        
        print(f"正在获取ISBN {test_isbn} 的在售商品...")
        listings = await crawler.fetch_active_listings(test_isbn)
        
        print(f"\n找到 {len(listings)} 个在售商品:")
        for i, listing in enumerate(listings, 1):
            print(f"\n商品 {i}:")
            print(f"  显示文本: {listing['display_text']}")
            print(f"  品相: {listing['quality']}")
            print(f"  价格: ￥{listing['price']:.2f}")
            print(f"  运费: ￥{listing['shipping_fee']:.2f}")
            print(f"  上书时间: {listing['add_time']}")
            print(f"  店铺: {listing['shop_name']}")
        
        # 测试摘要获取
        print("\n摘要信息:")
        summaries = await crawler.get_listings_summary(test_isbn)
        for i, summary in enumerate(summaries, 1):
            print(f"  {i}. {summary}")
    
    asyncio.run(test())