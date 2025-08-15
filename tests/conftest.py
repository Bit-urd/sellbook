"""
pytest配置文件，定义全局fixtures和测试配置
"""
import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
import pytest
import aiosqlite
from fastapi.testclient import TestClient
from httpx import AsyncClient

from src.main import app
from src.models.database import Database


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环用于session级别的异步测试"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """创建临时数据库文件路径"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        temp_path = temp_file.name
    yield temp_path
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
async def test_db(temp_db_path: str) -> AsyncGenerator[Database, None]:
    """创建测试数据库实例"""
    test_database = Database(temp_db_path)
    await test_database.init_db()
    yield test_database
    await test_database.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """创建FastAPI测试客户端"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """创建异步HTTP客户端"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_shop_data():
    """示例店铺数据"""
    return {
        "shop_id": "test_shop_001",
        "shop_name": "测试书店",
        "shop_url": "https://example.com/shop/test",
        "platform": "孔夫子",
        "status": "active"
    }


@pytest.fixture
def sample_book_data():
    """示例书籍数据"""
    return {
        "isbn": "9787111213826",
        "title": "代码大全",
        "author": "史蒂夫·迈克康奈尔",
        "publisher": "机械工业出版社",
        "pub_date": "2006-03-01",
        "price": 128.0,
        "condition": "九品",
        "shop_id": "test_shop_001"
    }


@pytest.fixture
def sample_task_data():
    """示例任务数据"""
    return {
        "task_name": "测试爬虫任务",
        "task_type": "shop_crawl",
        "target_data": {"shop_id": "test_shop_001"},
        "priority": 1,
        "status": "pending"
    }


@pytest.fixture
def mock_crawler_response():
    """模拟爬虫响应数据"""
    return {
        "success": True,
        "data": {
            "books": [
                {
                    "title": "Python编程",
                    "author": "作者1",
                    "price": 45.0,
                    "condition": "九品",
                    "isbn": "9787111111111"
                }
            ],
            "total": 1
        }
    }


# 测试标记定义
pytest_plugins = []


def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line(
        "markers", "unit: 单元测试"
    )
    config.addinivalue_line(
        "markers", "integration: 集成测试"
    )
    config.addinivalue_line(
        "markers", "e2e: 端到端测试"
    )
    config.addinivalue_line(
        "markers", "slow: 慢速测试"
    )