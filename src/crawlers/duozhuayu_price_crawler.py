"""
多抓鱼价格爬虫
爬取指定ISBN的多抓鱼最低价格
"""
import asyncio
import aiohttp
from typing import Optional, Dict
from bs4 import BeautifulSoup
import re
import json
import requests
import logging

from ..services.window_pool import chrome_pool

logger = logging.getLogger(__name__)


class DuozhuayuPriceCrawler:
    """多抓鱼价格爬虫"""
    
    def __init__(self):
        self.search_url = "https://www.duozhuayu.com/search/book/"
        self.base_url = "https://www.duozhuayu.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
    
    async def fetch_lowest_price(self, isbn: str) -> Optional[float]:
        """
        获取多抓鱼最低价格
        
        Args:
            isbn: ISBN号
            
        Returns:
            最低价格，如果获取失败返回None
        """
        try:
            # 尝试使用Playwright获取动态内容
            try:
                from patchright.async_api import async_playwright
                return await self._fetch_with_playwright(isbn)
            except ImportError:
                # 使用requests作为备选方案
                return await self._fetch_with_requests(isbn)
        except Exception as e:
            print(f"获取多抓鱼价格失败: {e}")
            return None
    
    async def _fetch_with_playwright(self, isbn: str) -> Optional[float]:
        """使用Playwright获取价格（通过窗口池）"""
        # 从窗口池获取页面
        page = await chrome_pool.get_window()
        if not page:
            logger.error("无法从窗口池获取页面")
            return None
        
        try:
            # 第一步：访问搜索页面
            search_url = f"{self.search_url}{isbn}"
            await page.goto(search_url, wait_until="networkidle")
            
            # 第二步：等待搜索结果加载并点击第一个结果
            search_result_selector = ".search_result_item"
            await page.wait_for_selector(search_result_selector, timeout=10000)
            
            # 获取第一个搜索结果的链接
            first_result = await page.query_selector(search_result_selector)
            if not first_result:
                logger.error("未找到搜索结果")
                return None
            
            # 点击第一个搜索结果
            await first_result.click()
            
            # 第三步：等待详情页面加载，获取价格
            await page.wait_for_load_state("networkidle")
            
            # 等待价格容器加载，使用更精确的选择器
            # 先尝试找到包含jsx类和plain bordered的div
            price_container_selector = "div[class*='jsx'][class*='plain'][class*='bordered']"
            await page.wait_for_selector(price_container_selector, timeout=10000)
            
            # 获取价格容器
            container_element = await page.query_selector(price_container_selector)
            if container_element:
                # 在这个容器内直接查找价格元素
                price_element = await container_element.query_selector(".Price.Price--clay")
                if price_element:
                    price_text = await price_element.text_content()
                    logger.info(f"直接找到价格元素: {price_text}")
                    
                    # 提取数字价格
                    price_match = re.search(r'¥?(\d+\.\d+)', price_text)
                    if price_match:
                        price = float(price_match.group(1))
                        logger.info(f"解析出价格: {price}")
                        return price
                
                # 如果没找到Price元素，尝试在容器文本中查找
                container_text = await container_element.text_content()
                logger.info(f"价格容器文本: {container_text[:200]}...")
                
                # 在容器文本中查找价格模式
                price_patterns = [
                    r'¥(\d+\.\d+)',  # ¥7.80
                    r'(\d+\.\d+)',   # 7.80
                ]
                
                for pattern in price_patterns:
                    matches = re.findall(pattern, container_text)
                    if matches:
                        for match in matches:
                            price = float(match)
                            if price > 1.0:  # 过滤掉明显不是价格的数字
                                logger.info(f"从容器文本中解析出价格: {price}")
                                return price
            
            # 尝试查找价格区间容器
            price_range_selector = f"{price_container_selector} .book-price-section .price-range-with-discount .Price"
            price_elements = await page.query_selector_all(price_range_selector)
            
            if price_elements and len(price_elements) > 0:
                # 取第一个价格作为最低价
                first_price_element = price_elements[0]
                price_text = await first_price_element.text_content()
                logger.info(f"找到价格区间文本: {price_text}")
                
                # 提取数字价格 - 确保至少有一个数字
                price_match = re.search(r'¥?(\d+\.?\d*)', price_text)
                if price_match:
                    price_str = price_match.group(1)
                    # 确保不是只有小数点
                    if price_str != '.' and price_str:
                        price = float(price_str)
                        logger.info(f"解析出最低价格: {price}")
                        return price
            
            # 如果没找到价格区间，尝试查找所有价格元素
            all_price_elements = await page.query_selector_all(f"{price_container_selector} .Price")
            
            if all_price_elements and len(all_price_elements) > 0:
                # 遍历所有价格元素，找到有效的价格
                for price_element in all_price_elements:
                    price_text = await price_element.text_content()
                    logger.info(f"检查价格文本: {price_text}")
                    
                    # 提取数字价格 - 确保至少有一个数字且大于1
                    price_match = re.search(r'¥?(\d+\.?\d*)', price_text)
                    if price_match:
                        price_str = price_match.group(1)
                        # 确保不是只有小数点且价格合理
                        if price_str != '.' and price_str:
                            price = float(price_str)
                            if price > 1.0:  # 过滤掉可能是折扣数字的价格
                                logger.info(f"解析出有效价格: {price}")
                                return price
            
            # 如果没找到价格区间，尝试查找单一价格
            single_price_element = await page.query_selector(f"{price_container_selector} .Price.Price--clay")
            if single_price_element:
                price_text = await single_price_element.text_content()
                logger.info(f"找到单一价格文本: {price_text}")
                
                price_match = re.search(r'¥?(\d+\.?\d*)', price_text)
                if price_match:
                    price_str = price_match.group(1)
                    # 确保不是只有小数点
                    if price_str != '.' and price_str:
                        price = float(price_str)
                        logger.info(f"解析出单一价格: {price}")
                        return price
            
            logger.warning("未找到价格元素")
            return None
                
        except Exception as e:
            logger.error(f"Playwright获取价格失败: {e}")
            return None
        
        finally:
            # 归还窗口到池中
            await chrome_pool.return_window(page)
    
    async def _fetch_with_requests(self, isbn: str) -> Optional[float]:
        """使用requests获取价格（备选方案）"""
        url = f"{self.base_url}{isbn}"
        
        try:
            # 使用aiohttp异步请求
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status != 200:
                        return None
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # 尝试查找价格元素
                    # 注意：多抓鱼使用React，价格可能在JavaScript中动态渲染
                    # 这里尝试从HTML中查找，但可能无法获取到
                    price_elements = soup.find_all('span', class_=re.compile(r'Price.*Price--clay'))
                    
                    if price_elements:
                        price_text = price_elements[0].get_text()
                        price_match = re.search(r'¥?([\d.]+)', price_text)
                        if price_match:
                            return float(price_match.group(1))
                    
                    # 尝试从页面的JSON数据中提取
                    scripts = soup.find_all('script', type='application/json')
                    for script in scripts:
                        try:
                            data = json.loads(script.string)
                            # 遍历查找价格信息
                            price = self._extract_price_from_json(data)
                            if price:
                                return price
                        except:
                            continue
                    
                    return None
                    
        except Exception as e:
            print(f"Requests获取价格失败: {e}")
            return None
    
    def _extract_price_from_json(self, data: dict, depth: int = 0) -> Optional[float]:
        """从JSON数据中递归提取价格"""
        if depth > 10:  # 防止递归过深
            return None
        
        if isinstance(data, dict):
            # 查找包含价格的键
            for key in ['price', 'lowestPrice', 'minPrice', 'salePrice']:
                if key in data:
                    value = data[key]
                    if isinstance(value, (int, float)):
                        return float(value)
                    elif isinstance(value, str):
                        price_match = re.search(r'[\d.]+', value)
                        if price_match:
                            return float(price_match.group())
            
            # 递归查找
            for value in data.values():
                price = self._extract_price_from_json(value, depth + 1)
                if price:
                    return price
        
        elif isinstance(data, list):
            for item in data:
                price = self._extract_price_from_json(item, depth + 1)
                if price:
                    return price
        
        return None
    
    async def get_price_info(self, isbn: str) -> Dict:
        """
        获取价格信息
        
        Args:
            isbn: ISBN号
            
        Returns:
            包含价格信息的字典
        """
        lowest_price = await self.fetch_lowest_price(isbn)
        
        return {
            "duozhuayu_lowest_price": lowest_price,
            "duozhuayu_url": f"{self.search_url}{isbn}",
            "price_source": "duozhuayu"
        }


# 测试代码
if __name__ == "__main__":
    async def test():
        crawler = DuozhuayuPriceCrawler()
        
        # 测试ISBN
        test_isbn = "9787544291200"
        
        print(f"正在获取ISBN {test_isbn} 的多抓鱼价格...")
        price_info = await crawler.get_price_info(test_isbn)
        
        print(f"\n价格信息:")
        print(f"  最低价格: ¥{price_info['duozhuayu_lowest_price']:.2f}" if price_info['duozhuayu_lowest_price'] else "  最低价格: 未获取到")
        print(f"  商品链接: {price_info['duozhuayu_url']}")
        print(f"  数据来源: {price_info['price_source']}")
    
    asyncio.run(test())