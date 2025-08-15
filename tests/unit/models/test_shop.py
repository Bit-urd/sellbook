"""
Shop模型单元测试
"""
import pytest
from datetime import datetime
from src.models.shop import Shop


class TestShop:
    """Shop模型测试类"""
    
    def test_shop_creation(self):
        """测试Shop对象创建"""
        shop = Shop(
            id="test_shop",
            name="测试书店",
            description="这是一个测试书店",
            location="北京市朝阳区",
            contact="13800138000"
        )
        
        assert shop.id == "test_shop"
        assert shop.name == "测试书店"
        assert shop.description == "这是一个测试书店"
        assert shop.location == "北京市朝阳区"
        assert shop.contact == "13800138000"
        assert isinstance(shop.created_at, datetime)
        assert isinstance(shop.updated_at, datetime)
    
    def test_shop_repr(self):
        """测试Shop对象字符串表示"""
        shop = Shop(
            id="test_shop",
            name="测试书店",
            description="这是一个测试书店", 
            location="北京市朝阳区",
            contact="13800138000"
        )
        
        repr_str = repr(shop)
        assert "Shop" in repr_str
        assert "test_shop" in repr_str
        assert "测试书店" in repr_str
    
    def test_shop_validation(self):
        """测试Shop字段验证"""
        # 测试必填字段
        with pytest.raises(TypeError):
            Shop()
        
        # 测试部分字段
        shop = Shop(
            id="test_shop",
            name="测试书店"
        )
        assert shop.id == "test_shop"
        assert shop.name == "测试书店"
        assert shop.description is None
        assert shop.location is None
        assert shop.contact is None
    
    def test_shop_timestamps(self):
        """测试时间戳字段"""
        shop = Shop(
            id="test_shop",
            name="测试书店"
        )
        
        created_time = shop.created_at
        updated_time = shop.updated_at
        
        # 验证时间戳是datetime对象
        assert isinstance(created_time, datetime)
        assert isinstance(updated_time, datetime)
        
        # 验证创建时间和更新时间相近（在同一秒内）
        time_diff = abs((updated_time - created_time).total_seconds())
        assert time_diff < 1.0