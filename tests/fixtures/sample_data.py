"""
测试用的样本数据
"""
from datetime import datetime
from typing import Dict, List, Any

# 样本店铺数据
SAMPLE_SHOPS = [
    {
        "id": "shop1",
        "name": "测试书店1",
        "description": "这是一个测试书店",
        "location": "北京市朝阳区",
        "contact": "13800138001",
        "created_at": datetime(2024, 1, 1),
        "updated_at": datetime(2024, 1, 1)
    },
    {
        "id": "shop2", 
        "name": "测试书店2",
        "description": "另一个测试书店",
        "location": "上海市浦东新区",
        "contact": "13800138002",
        "created_at": datetime(2024, 1, 2),
        "updated_at": datetime(2024, 1, 2)
    }
]

# 样本书籍数据
SAMPLE_BOOKS = [
    {
        "isbn": "9787111213826",
        "title": "计算机网络",
        "author": "谢希仁",
        "publisher": "电子工业出版社",
        "publication_date": "2019-01-01",
        "price": 59.00,
        "stock_quantity": 10,
        "shop_id": "shop1",
        "created_at": datetime(2024, 1, 1),
        "updated_at": datetime(2024, 1, 1)
    },
    {
        "isbn": "9787302159742",
        "title": "数据结构与算法分析",
        "author": "Mark Allen Weiss",
        "publisher": "清华大学出版社", 
        "publication_date": "2018-06-01",
        "price": 79.00,
        "stock_quantity": 5,
        "shop_id": "shop1",
        "created_at": datetime(2024, 1, 2),
        "updated_at": datetime(2024, 1, 2)
    },
    {
        "isbn": "9787121091906",
        "title": "Python编程快速上手",
        "author": "Al Sweigart",
        "publisher": "人民邮电出版社",
        "publication_date": "2020-03-01", 
        "price": 69.00,
        "stock_quantity": 8,
        "shop_id": "shop2",
        "created_at": datetime(2024, 1, 3),
        "updated_at": datetime(2024, 1, 3)
    }
]

# 样本ISBN搜索结果
SAMPLE_ISBN_SEARCH_RESULTS = [
    {
        "isbn": "9787111213826",
        "title": "计算机网络",
        "author": "谢希仁",
        "publisher": "电子工业出版社",
        "publication_date": "2019-01-01",
        "source": "douban",
        "confidence": 0.95
    }
]

# 无效的ISBN用于测试
INVALID_ISBN = "1234567890123"

# 爬虫测试用的模拟HTML响应
MOCK_HTML_RESPONSES = {
    "douban_book": """
    <html>
        <body>
            <div class="subject">
                <h1>计算机网络</h1>
                <div class="author">谢希仁</div>
                <div class="publisher">电子工业出版社</div>
                <div class="pub">2019-1</div>
            </div>
        </body>
    </html>
    """,
    "empty_page": "<html><body></body></html>",
    "error_page": "<html><body><h1>404 Not Found</h1></body></html>"
}