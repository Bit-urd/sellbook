"""
店铺业务服务层
"""
from typing import List, Dict, Any
from src.repositories.shop_repository import ShopRepository
from src.models.shop import Shop
from src.exceptions import ShopNotFoundError, DuplicateShopError


class ShopService:
    """店铺服务类"""
    
    def __init__(self, shop_repository: ShopRepository):
        self.shop_repository = shop_repository
    
    async def create_shop(self, shop_data: Dict[str, Any]) -> Shop:
        """创建店铺"""
        # 检查店铺是否已存在
        existing_shop = await self.shop_repository.get_by_id(shop_data["id"])
        if existing_shop:
            raise DuplicateShopError(f"Shop with id {shop_data['id']} already exists")
        
        # 验证数据
        self._validate_shop_data(shop_data)
        
        return await self.shop_repository.create(shop_data)
    
    async def get_shop_by_id(self, shop_id: str) -> Shop:
        """根据ID获取店铺"""
        shop = await self.shop_repository.get_by_id(shop_id)
        if not shop:
            raise ShopNotFoundError(f"Shop with id {shop_id} not found")
        return shop
    
    async def get_all_shops(self) -> List[Shop]:
        """获取所有店铺"""
        return await self.shop_repository.get_all()
    
    async def update_shop(self, shop_id: str, update_data: Dict[str, Any]) -> Shop:
        """更新店铺"""
        shop = await self.shop_repository.update(shop_id, update_data)
        if not shop:
            raise ShopNotFoundError(f"Shop with id {shop_id} not found")
        return shop
    
    async def delete_shop(self, shop_id: str) -> bool:
        """删除店铺"""
        success = await self.shop_repository.delete(shop_id)
        if not success:
            raise ShopNotFoundError(f"Shop with id {shop_id} not found")
        return success
    
    def _validate_shop_data(self, shop_data: Dict[str, Any]) -> None:
        """验证店铺数据"""
        required_fields = ["id", "name"]
        for field in required_fields:
            if field not in shop_data or not shop_data[field]:
                raise ValueError(f"Missing required field: {field}")