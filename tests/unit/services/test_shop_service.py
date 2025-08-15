"""
ShopService单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.shop_service import ShopService
from src.repositories.shop_repository import ShopRepository
from src.models.shop import Shop
from src.exceptions import ShopNotFoundError, DuplicateShopError
from tests.fixtures.sample_data import SAMPLE_SHOPS


class TestShopService:
    """ShopService测试类"""
    
    @pytest.fixture
    def mock_shop_repository(self):
        """模拟ShopRepository"""
        return AsyncMock(spec=ShopRepository)
    
    @pytest.fixture
    def shop_service(self, mock_shop_repository):
        """创建ShopService实例"""
        return ShopService(mock_shop_repository)
    
    @pytest.mark.asyncio
    async def test_create_shop_success(self, shop_service, mock_shop_repository):
        """测试成功创建店铺"""
        shop_data = {
            "id": "new_shop",
            "name": "新店铺",
            "description": "新店铺描述",
            "location": "北京市",
            "contact": "13800138000"
        }
        
        # 模拟仓库层返回
        mock_shop_repository.get_by_id.return_value = None  # 店铺不存在
        mock_shop_repository.create.return_value = Shop(**shop_data)
        
        result = await shop_service.create_shop(shop_data)
        
        # 验证调用
        mock_shop_repository.get_by_id.assert_called_once_with(shop_data["id"])
        mock_shop_repository.create.assert_called_once_with(shop_data)
        
        # 验证返回值
        assert isinstance(result, Shop)
        assert result.id == shop_data["id"]
        assert result.name == shop_data["name"]
    
    @pytest.mark.asyncio
    async def test_create_shop_duplicate_error(self, shop_service, mock_shop_repository):
        """测试创建重复店铺抛出异常"""
        shop_data = SAMPLE_SHOPS[0].copy()
        existing_shop = Shop(**shop_data)
        
        # 模拟店铺已存在
        mock_shop_repository.get_by_id.return_value = existing_shop
        
        with pytest.raises(DuplicateShopError):
            await shop_service.create_shop(shop_data)
        
        # 验证只调用了检查方法，没有调用创建方法
        mock_shop_repository.get_by_id.assert_called_once()
        mock_shop_repository.create.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_shop_by_id_success(self, shop_service, mock_shop_repository):
        """测试成功获取店铺"""
        shop_id = "shop1"
        expected_shop = Shop(**SAMPLE_SHOPS[0])
        
        mock_shop_repository.get_by_id.return_value = expected_shop
        
        result = await shop_service.get_shop_by_id(shop_id)
        
        # 验证调用
        mock_shop_repository.get_by_id.assert_called_once_with(shop_id)
        
        # 验证返回值
        assert result == expected_shop
    
    @pytest.mark.asyncio
    async def test_get_shop_by_id_not_found(self, shop_service, mock_shop_repository):
        """测试获取不存在的店铺抛出异常"""
        shop_id = "nonexistent"
        
        mock_shop_repository.get_by_id.return_value = None
        
        with pytest.raises(ShopNotFoundError):
            await shop_service.get_shop_by_id(shop_id)
    
    @pytest.mark.asyncio
    async def test_get_all_shops(self, shop_service, mock_shop_repository):
        """测试获取所有店铺"""
        expected_shops = [Shop(**shop_data) for shop_data in SAMPLE_SHOPS]
        
        mock_shop_repository.get_all.return_value = expected_shops
        
        result = await shop_service.get_all_shops()
        
        # 验证调用
        mock_shop_repository.get_all.assert_called_once()
        
        # 验证返回值
        assert result == expected_shops
        assert len(result) == len(SAMPLE_SHOPS)
    
    @pytest.mark.asyncio
    async def test_update_shop_success(self, shop_service, mock_shop_repository):
        """测试成功更新店铺"""
        shop_id = "shop1"
        update_data = {"name": "更新后的店铺", "description": "更新后的描述"}
        updated_shop = Shop(**{**SAMPLE_SHOPS[0], **update_data})
        
        mock_shop_repository.update.return_value = updated_shop
        
        result = await shop_service.update_shop(shop_id, update_data)
        
        # 验证调用
        mock_shop_repository.update.assert_called_once_with(shop_id, update_data)
        
        # 验证返回值
        assert result == updated_shop
        assert result.name == update_data["name"]
    
    @pytest.mark.asyncio
    async def test_update_shop_not_found(self, shop_service, mock_shop_repository):
        """测试更新不存在的店铺抛出异常"""
        shop_id = "nonexistent"
        update_data = {"name": "更新后的店铺"}
        
        mock_shop_repository.update.return_value = None
        
        with pytest.raises(ShopNotFoundError):
            await shop_service.update_shop(shop_id, update_data)
    
    @pytest.mark.asyncio
    async def test_delete_shop_success(self, shop_service, mock_shop_repository):
        """测试成功删除店铺"""
        shop_id = "shop1"
        
        mock_shop_repository.delete.return_value = True
        
        result = await shop_service.delete_shop(shop_id)
        
        # 验证调用
        mock_shop_repository.delete.assert_called_once_with(shop_id)
        
        # 验证返回值
        assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_shop_not_found(self, shop_service, mock_shop_repository):
        """测试删除不存在的店铺抛出异常"""
        shop_id = "nonexistent"
        
        mock_shop_repository.delete.return_value = False
        
        with pytest.raises(ShopNotFoundError):
            await shop_service.delete_shop(shop_id)
    
    @pytest.mark.asyncio
    async def test_validate_shop_data(self, shop_service):
        """测试店铺数据验证"""
        # 测试有效数据
        valid_data = {
            "id": "test_shop",
            "name": "测试店铺",
            "description": "描述",
            "location": "位置",
            "contact": "联系方式"
        }
        
        # 不应该抛出异常
        try:
            shop_service._validate_shop_data(valid_data)
        except Exception:
            pytest.fail("Valid data should not raise exception")
        
        # 测试无效数据（缺少必填字段）
        invalid_data = {"description": "只有描述"}
        
        with pytest.raises(ValueError):
            shop_service._validate_shop_data(invalid_data)