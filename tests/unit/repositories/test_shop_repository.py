"""
ShopRepository单元测试 (适配stub实现)
"""
import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from src.repositories.shop_repository import ShopRepository
from src.models.shop import Shop
from tests.fixtures.sample_data import SAMPLE_SHOPS


class TestShopRepository:
    """ShopRepository测试类"""
    
    @pytest.fixture
    def mock_session(self):
        """模拟数据库会话"""
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def shop_repository(self, mock_session):
        """创建ShopRepository实例"""
        return ShopRepository(mock_session)
    
    @pytest.mark.asyncio
    async def test_create_shop(self, shop_repository):
        """测试创建店铺"""
        shop_data = {
            "id": "test_shop",
            "name": "测试店铺",
            "description": "测试描述"
        }
        
        result = await shop_repository.create(shop_data)
        
        # 验证返回值
        assert isinstance(result, Shop)
        assert result.id == shop_data["id"]
        assert result.name == shop_data["name"]
    
    @pytest.mark.asyncio
    async def test_get_shop_by_id_returns_none(self, shop_repository):
        """测试获取店铺返回None (stub实现)"""
        result = await shop_repository.get_by_id("any_id")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_all_shops_returns_empty_list(self, shop_repository):
        """测试获取所有店铺返回空列表 (stub实现)"""
        result = await shop_repository.get_all()
        assert result == []
    
    @pytest.mark.asyncio
    async def test_update_shop_returns_none(self, shop_repository):
        """测试更新店铺返回None (stub实现)"""
        result = await shop_repository.update("any_id", {"name": "新名称"})
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_shop_returns_false(self, shop_repository):
        """测试删除店铺返回False (stub实现)"""
        result = await shop_repository.delete("any_id")
        assert result is False