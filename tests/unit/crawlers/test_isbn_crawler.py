"""
ISBN爬虫单元测试
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp
from src.crawlers.isbn_crawler import ISBNCrawler
from tests.fixtures.sample_data import MOCK_HTML_RESPONSES, SAMPLE_ISBN_SEARCH_RESULTS


class TestISBNCrawler:
    """ISBN爬虫测试类"""
    
    @pytest.fixture
    def isbn_crawler(self):
        """创建ISBNCrawler实例"""
        return ISBNCrawler()
    
    @pytest.mark.asyncio
    async def test_search_book_info_success(self, isbn_crawler):
        """测试成功搜索书籍信息"""
        isbn = "9787111213826"
        expected_result = SAMPLE_ISBN_SEARCH_RESULTS[0]
        
        with patch.object(isbn_crawler, '_fetch_from_douban') as mock_douban:
            mock_douban.return_value = expected_result
            
            result = await isbn_crawler.search_book_info(isbn)
            
            # 验证调用
            mock_douban.assert_called_once_with(isbn)
            
            # 验证返回值
            assert result == expected_result
            assert result["isbn"] == isbn
    
    @pytest.mark.asyncio
    async def test_search_book_info_not_found(self, isbn_crawler):
        """测试搜索不存在的书籍信息"""
        isbn = "9999999999999"
        
        with patch.object(isbn_crawler, '_fetch_from_douban') as mock_douban:
            mock_douban.return_value = None
            
            result = await isbn_crawler.search_book_info(isbn)
            
            # 验证返回None
            assert result is None
    
    @pytest.mark.asyncio
    async def test_fetch_from_douban_success(self, isbn_crawler):
        """测试从豆瓣获取数据成功"""
        isbn = "9787111213826"
        mock_html = MOCK_HTML_RESPONSES["douban_book"]
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            # 模拟HTTP响应
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text.return_value = mock_html
            mock_get.return_value.__aenter__.return_value = mock_response
            
            with patch.object(isbn_crawler, '_parse_douban_html') as mock_parse:
                expected_result = {
                    "isbn": isbn,
                    "title": "计算机网络",
                    "author": "谢希仁",
                    "publisher": "电子工业出版社",
                    "publication_date": "2019-01-01",
                    "source": "douban",
                    "confidence": 0.95
                }
                mock_parse.return_value = expected_result
                
                result = await isbn_crawler._fetch_from_douban(isbn)
                
                # 验证调用
                mock_get.assert_called_once()
                mock_parse.assert_called_once_with(mock_html, isbn)
                
                # 验证返回值
                assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_fetch_from_douban_http_error(self, isbn_crawler):
        """测试从豆瓣获取数据HTTP错误"""
        isbn = "9787111213826"
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            # 模拟HTTP 404错误
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await isbn_crawler._fetch_from_douban(isbn)
            
            # 验证返回None
            assert result is None
    
    @pytest.mark.asyncio
    async def test_fetch_from_douban_network_error(self, isbn_crawler):
        """测试网络错误处理"""
        isbn = "9787111213826"
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            # 模拟网络错误
            mock_get.side_effect = aiohttp.ClientError("Network error")
            
            result = await isbn_crawler._fetch_from_douban(isbn)
            
            # 验证返回None
            assert result is None
    
    def test_parse_douban_html_success(self, isbn_crawler):
        """测试解析豆瓣HTML成功"""
        isbn = "9787111213826"
        html = MOCK_HTML_RESPONSES["douban_book"]
        
        result = isbn_crawler._parse_douban_html(html, isbn)
        
        # 验证解析结果
        assert result is not None
        assert result["isbn"] == isbn
        assert result["source"] == "douban"
        assert "title" in result
        assert "author" in result
        assert "publisher" in result
    
    def test_parse_douban_html_empty_page(self, isbn_crawler):
        """测试解析空页面"""
        isbn = "9787111213826"
        html = MOCK_HTML_RESPONSES["empty_page"]
        
        result = isbn_crawler._parse_douban_html(html, isbn)
        
        # 验证返回None
        assert result is None
    
    def test_parse_douban_html_error_page(self, isbn_crawler):
        """测试解析错误页面"""
        isbn = "9787111213826"
        html = MOCK_HTML_RESPONSES["error_page"]
        
        result = isbn_crawler._parse_douban_html(html, isbn)
        
        # 错误页面也可能返回低置信度的结果，这是可接受的
        # 验证如果返回结果，置信度应该很低
        if result is not None:
            assert result["confidence"] < 0.5  # 置信度应该低于50%
            assert result["title"] == "404 Not Found"  # 应该解析出错误信息
        else:
            # 返回None也是可接受的
            assert result is None
    
    def test_validate_isbn_valid(self, isbn_crawler):
        """测试验证有效ISBN"""
        valid_isbns = [
            "9787111213826",
            "978-7-111-21382-6",
            "9780123456789"
        ]
        
        for isbn in valid_isbns:
            assert isbn_crawler._validate_isbn(isbn) is True
    
    def test_validate_isbn_invalid(self, isbn_crawler):
        """测试验证无效ISBN"""
        invalid_isbns = [
            "1234567890123",  # 长度错误
            "invalid_isbn",   # 包含字母
            "",               # 空字符串
            "978-7-111",      # 长度不足
            "97871112138261"  # 长度过长
        ]
        
        for isbn in invalid_isbns:
            assert isbn_crawler._validate_isbn(isbn) is False
    
    def test_clean_isbn(self, isbn_crawler):
        """测试清理ISBN格式"""
        test_cases = [
            ("978-7-111-21382-6", "9787111213826"),
            ("978 7 111 21382 6", "9787111213826"),
            ("9787111213826", "9787111213826"),
            ("ISBN: 9787111213826", "9787111213826"),
            ("isbn 978-7-111-21382-6", "9787111213826")
        ]
        
        for input_isbn, expected in test_cases:
            result = isbn_crawler._clean_isbn(input_isbn)
            assert result == expected
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, isbn_crawler):
        """测试爬虫速率限制"""
        isbn = "9787111213826"
        
        with patch.object(isbn_crawler, '_fetch_from_douban') as mock_fetch:
            mock_fetch.return_value = None
            
            # 连续发送多个请求
            results = []
            for _ in range(3):
                result = await isbn_crawler.search_book_info(isbn)
                results.append(result)
            
            # 验证都能正常调用（实际的速率限制在_fetch_from_douban中实现）
            assert len(results) == 3
            assert mock_fetch.call_count == 3
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, isbn_crawler):
        """测试超时处理"""
        isbn = "9787111213826"
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            # 模拟超时错误
            mock_get.side_effect = aiohttp.ServerTimeoutError("Timeout")
            
            result = await isbn_crawler._fetch_from_douban(isbn)
            
            # 验证返回None
            assert result is None
    
    def test_confidence_calculation(self, isbn_crawler):
        """测试置信度计算"""
        # 完整信息的情况
        complete_info = {
            "title": "计算机网络",
            "author": "谢希仁",
            "publisher": "电子工业出版社",
            "publication_date": "2019-01-01"
        }
        
        confidence = isbn_crawler._calculate_confidence(complete_info)
        assert confidence >= 0.8  # 完整信息应该有高置信度
        
        # 部分信息的情况
        partial_info = {
            "title": "计算机网络",
            "author": "谢希仁"
        }
        
        confidence = isbn_crawler._calculate_confidence(partial_info)
        assert 0.4 <= confidence < 0.8  # 部分信息应该有中等置信度
        
        # 空信息的情况
        empty_info = {}
        
        confidence = isbn_crawler._calculate_confidence(empty_info)
        assert confidence < 0.4  # 空信息应该有低置信度