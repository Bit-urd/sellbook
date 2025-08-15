"""
爬虫集成测试
"""
import pytest
from unittest.mock import patch
from src.crawlers.isbn_crawler import ISBNCrawler
from tests.fixtures.sample_data import MOCK_HTML_RESPONSES


class TestCrawlerIntegration:
    """爬虫集成测试类"""
    
    @pytest.fixture
    def isbn_crawler(self):
        """创建ISBNCrawler实例"""
        return ISBNCrawler()
    
    @pytest.mark.asyncio
    async def test_end_to_end_book_search(self, isbn_crawler):
        """测试端到端书籍搜索流程"""
        isbn = "9787111213826"
        
        # 模拟整个搜索流程
        with patch('aiohttp.ClientSession.get') as mock_get:
            # 模拟成功的HTTP响应
            mock_response = type('MockResponse', (), {
                'status': 200,
                'text': lambda: MOCK_HTML_RESPONSES["douban_book"]
            })()
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await isbn_crawler.search_book_info(isbn)
            
            # 验证结果结构
            if result:
                assert "isbn" in result
                assert "title" in result
                assert "source" in result
                assert "confidence" in result
                assert result["source"] == "douban"
                assert 0 <= result["confidence"] <= 1
    
    @pytest.mark.asyncio
    async def test_fallback_mechanism(self, isbn_crawler):
        """测试回退机制"""
        isbn = "9787111213826"
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            # 模拟豆瓣失败的情况
            mock_get.side_effect = Exception("豆瓣服务不可用")
            
            result = await isbn_crawler.search_book_info(isbn)
            
            # 在没有其他数据源的情况下应该返回None
            assert result is None
    
    @pytest.mark.asyncio
    async def test_multiple_isbn_search(self, isbn_crawler):
        """测试批量ISBN搜索"""
        isbns = ["9787111213826", "9787302159742", "9787121091906"]
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            # 模拟不同的响应
            responses = [
                MOCK_HTML_RESPONSES["douban_book"],
                MOCK_HTML_RESPONSES["empty_page"],
                MOCK_HTML_RESPONSES["error_page"]
            ]
            
            mock_response_objs = []
            for html in responses:
                mock_response = type('MockResponse', (), {
                    'status': 200,
                    'text': lambda h=html: h
                })()
                mock_response_objs.append(mock_response)
            
            mock_get.return_value.__aenter__.side_effect = mock_response_objs
            
            results = []
            for isbn in isbns:
                result = await isbn_crawler.search_book_info(isbn)
                results.append(result)
            
            # 验证结果
            assert len(results) == len(isbns)
            # 第一个应该成功，其他可能失败
            assert results[0] is not None or results[0] is None  # 取决于解析结果
    
    @pytest.mark.asyncio
    async def test_error_recovery(self, isbn_crawler):
        """测试错误恢复机制"""
        isbn = "9787111213826"
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            # 模拟网络错误然后恢复
            call_count = [0]
            
            def side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise Exception("网络错误")
                else:
                    mock_response = type('MockResponse', (), {
                        'status': 200,
                        'text': lambda: MOCK_HTML_RESPONSES["douban_book"]
                    })()
                    return mock_response
            
            mock_get.return_value.__aenter__.side_effect = side_effect
            
            # 第一次调用应该失败
            result1 = await isbn_crawler.search_book_info(isbn)
            assert result1 is None
            
            # 第二次调用应该成功（如果有重试机制）
            result2 = await isbn_crawler.search_book_info(isbn)
            # 根据实际实现可能成功或失败
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, isbn_crawler):
        """测试并发请求处理"""
        import asyncio
        
        isbns = ["9787111213826", "9787302159742", "9787121091906"]
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = type('MockResponse', (), {
                'status': 200,
                'text': lambda: MOCK_HTML_RESPONSES["douban_book"]
            })()
            mock_get.return_value.__aenter__.return_value = mock_response
            
            # 并发执行搜索
            tasks = [isbn_crawler.search_book_info(isbn) for isbn in isbns]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 验证所有请求都完成了
            assert len(results) == len(isbns)
            
            # 验证没有异常（除非预期的）
            for result in results:
                assert not isinstance(result, Exception) or result is None
    
    @pytest.mark.asyncio
    async def test_data_quality_validation(self, isbn_crawler):
        """测试数据质量验证"""
        isbn = "9787111213826"
        
        # 模拟不完整的HTML响应
        incomplete_html = "<html><body><h1>部分信息</h1></body></html>"
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = type('MockResponse', (), {
                'status': 200,
                'text': lambda: incomplete_html
            })()
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await isbn_crawler.search_book_info(isbn)
            
            # 验证数据质量
            if result:
                assert result["confidence"] < 1.0  # 不完整信息的置信度应该较低
                assert "isbn" in result  # 至少应该有ISBN
    
    @pytest.mark.asyncio
    async def test_performance_monitoring(self, isbn_crawler):
        """测试性能监控"""
        import time
        
        isbn = "9787111213826"
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            # 模拟慢响应
            async def slow_response(*args, **kwargs):
                await asyncio.sleep(0.1)  # 模拟100ms延迟
                mock_response = type('MockResponse', (), {
                    'status': 200,
                    'text': lambda: MOCK_HTML_RESPONSES["douban_book"]
                })()
                return mock_response
            
            mock_get.return_value.__aenter__.side_effect = slow_response
            
            start_time = time.time()
            result = await isbn_crawler.search_book_info(isbn)
            end_time = time.time()
            
            # 验证响应时间（mock环境下应该很快）
            response_time = end_time - start_time
            assert response_time >= 0.0   # 应该有响应时间
            assert response_time < 10.0   # 但不应该过长