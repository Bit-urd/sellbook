"""
ISBN爬虫模块
"""
import re
from typing import Optional, Dict, Any
import aiohttp
from bs4 import BeautifulSoup


class ISBNCrawler:
    """ISBN爬虫类"""
    
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=10)
    
    async def search_book_info(self, isbn: str) -> Optional[Dict[str, Any]]:
        """搜索书籍信息"""
        if not self._validate_isbn(isbn):
            return None
        
        # 尝试从豆瓣获取
        result = await self._fetch_from_douban(isbn)
        return result
    
    async def _fetch_from_douban(self, isbn: str) -> Optional[Dict[str, Any]]:
        """从豆瓣获取书籍信息"""
        try:
            url = f"https://book.douban.com/isbn/{isbn}/"
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        return self._parse_douban_html(html, isbn)
                    return None
        except Exception:
            return None
    
    def _parse_douban_html(self, html: str, isbn: str) -> Optional[Dict[str, Any]]:
        """解析豆瓣HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 查找标题
            title_elem = soup.find('h1')
            if not title_elem:
                return None
            
            title = title_elem.get_text().strip()
            
            # 查找作者
            author_elem = soup.find('div', {'class': 'author'})
            author = author_elem.get_text().strip() if author_elem else None
            
            # 查找出版社
            publisher_elem = soup.find('div', {'class': 'publisher'})
            publisher = publisher_elem.get_text().strip() if publisher_elem else None
            
            # 查找出版日期
            pub_date_elem = soup.find('div', {'class': 'pub'})
            pub_date = pub_date_elem.get_text().strip() if pub_date_elem else None
            
            info = {
                "isbn": isbn,
                "title": title,
                "author": author,
                "publisher": publisher,
                "publication_date": pub_date,
                "source": "douban"
            }
            
            # 计算置信度
            confidence = self._calculate_confidence(info)
            info["confidence"] = confidence
            
            return info
            
        except Exception:
            return None
    
    def _validate_isbn(self, isbn: str) -> bool:
        """验证ISBN格式"""
        if not isbn:
            return False
        
        clean_isbn = self._clean_isbn(isbn)
        
        # 检查长度
        if len(clean_isbn) != 13:
            return False
        
        # 检查是否全为数字
        if not clean_isbn.isdigit():
            return False
        
        # 检查前缀
        return clean_isbn.startswith('978') or clean_isbn.startswith('979')
    
    def _clean_isbn(self, isbn: str) -> str:
        """清理ISBN格式"""
        # 移除所有非数字字符
        return re.sub(r'\D', '', isbn)
    
    def _calculate_confidence(self, info: Dict[str, Any]) -> float:
        """计算置信度"""
        score = 0
        total = 4
        
        if info.get('title'):
            score += 1
        if info.get('author'):
            score += 1
        if info.get('publisher'):
            score += 1
        if info.get('publication_date'):
            score += 1
        
        return score / total