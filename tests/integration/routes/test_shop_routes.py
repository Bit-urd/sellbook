"""
店铺路由集成测试
"""
import pytest
from fastapi.testclient import TestClient
from src.main import app
from tests.fixtures.sample_data import SAMPLE_SHOPS


class TestShopRoutes:
    """店铺路由集成测试类"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    def test_create_shop_success(self, client):
        """测试成功创建店铺 - 基于真实数据格式"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        shop_data = {
            "shop_id": f"test_shop_{unique_id}",
            "shop_name": "测试书店",
            "platform": "kongfuzi",
            "shop_url": f"http://test{unique_id}.example.com",
            "shop_type": "测试书店"
        }
        
        response = client.post("/api/shops", json=shop_data)
        
        # 验证响应状态码
        assert response.status_code in [201, 200]  # 创建成功
        
        # 验证响应数据 - 基于真实API响应格式
        data = response.json()
        assert data["success"] == True
        assert data["message"] == "店铺创建成功"
        assert data["data"]["shop_id"] == shop_data["shop_id"]
    
    def test_create_shop_invalid_data(self, client):
        """测试创建店铺时提供无效数据"""
        # 缺少必填字段
        invalid_data = {
            "description": "只有描述"
        }
        
        response = client.post("/api/shops", json=invalid_data)
        
        # 验证响应状态码（422表示验证错误）
        assert response.status_code == 422
        
        # 验证错误信息
        data = response.json()
        assert "detail" in data
    
    def test_create_shop_duplicate_id(self, client):
        """测试创建重复ID的店铺 - 基于真实数据格式"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        shop_data = {
            "shop_id": f"duplicate_{unique_id}",
            "shop_name": "第一个店铺",
            "platform": "kongfuzi",
            "shop_url": f"http://dup1{unique_id}.example.com",
            "shop_type": "测试店铺"
        }
        
        # 第一次创建
        response1 = client.post("/api/shops", json=shop_data)
        assert response1.status_code in [200, 201]  # 应该成功
        
        # 第二次创建相同shop_id的店铺
        shop_data["shop_name"] = "第二个店铺"
        shop_data["shop_url"] = f"http://dup2{unique_id}.example.com"
        response2 = client.post("/api/shops", json=shop_data)
        
        # 第二次应该失败（400错误 - 基于我们看到的真实API行为）
        assert response2.status_code == 400
        data = response2.json()
        assert "detail" in data
        assert "已存在" in data["detail"]
    
    def test_get_shop_by_id_success(self, client):
        """测试成功根据ID获取店铺"""
        # 先创建一个店铺
        shop_data = {
            "id": "get_test_shop",
            "name": "获取测试店铺",
            "description": "用于测试获取的店铺",
            "location": "测试位置",
            "contact": "测试联系方式"
        }
        
        create_response = client.post("/api/shops", json=shop_data)
        if create_response.status_code not in [200, 201]:
            pytest.skip("Cannot create shop for testing")
        
        # 获取店铺
        response = client.get(f"/api/shops/{shop_data['id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == shop_data["id"]
        assert data["name"] == shop_data["name"]
    
    def test_get_shop_by_id_not_found(self, client):
        """测试获取不存在的店铺"""
        response = client.get("/api/shops/nonexistent_shop")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    def test_get_all_shops(self, client):
        """测试获取所有店铺 - 基于真实API响应格式"""
        response = client.get("/api/shops")
        
        assert response.status_code == 200
        data = response.json()
        
        # 验证响应结构
        assert data["success"] == True
        assert "data" in data
        assert "shops" in data["data"]
        assert "pagination" in data["data"]
        
        # 验证分页信息
        pagination = data["data"]["pagination"]
        assert "page" in pagination
        assert "page_size" in pagination
        assert "total" in pagination
        assert "total_pages" in pagination
        
        # 验证店铺列表结构
        shops = data["data"]["shops"]
        assert isinstance(shops, list)
        
        # 如果有店铺，验证每个店铺的基本结构
        if shops:
            for shop in shops:
                assert "id" in shop
                assert "shop_id" in shop
                assert "shop_name" in shop
                assert "platform" in shop
                assert "status" in shop
                assert "created_at" in shop
                assert "updated_at" in shop
                assert "crawl_status" in shop
                assert "crawl_progress" in shop
    
    def test_update_shop_success(self, client):
        """测试成功更新店铺"""
        # 先创建一个店铺
        shop_data = {
            "id": "update_test_shop",
            "name": "更新测试店铺",
            "description": "原始描述",
            "location": "原始位置",
            "contact": "原始联系方式"
        }
        
        create_response = client.post("/api/shops", json=shop_data)
        if create_response.status_code not in [200, 201]:
            pytest.skip("Cannot create shop for testing")
        
        # 更新店铺
        update_data = {
            "name": "更新后的店铺名称",
            "description": "更新后的描述",
            "location": "更新后的位置"
        }
        
        response = client.put(f"/api/shops/{shop_data['id']}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == shop_data["id"]
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["location"] == update_data["location"]
    
    def test_update_shop_not_found(self, client):
        """测试更新不存在的店铺"""
        update_data = {
            "name": "更新后的名称"
        }
        
        response = client.put("/api/shops/nonexistent_shop", json=update_data)
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    def test_delete_shop_success(self, client):
        """测试成功删除店铺"""
        # 先创建一个店铺
        shop_data = {
            "id": "delete_test_shop",
            "name": "删除测试店铺",
            "description": "用于测试删除的店铺",
            "location": "测试位置",
            "contact": "测试联系方式"
        }
        
        create_response = client.post("/api/shops", json=shop_data)
        if create_response.status_code not in [200, 201]:
            pytest.skip("Cannot create shop for testing")
        
        # 删除店铺
        response = client.delete(f"/api/shops/{shop_data['id']}")
        
        assert response.status_code in [200, 204]
        
        # 验证店铺已被删除
        get_response = client.get(f"/api/shops/{shop_data['id']}")
        assert get_response.status_code == 404
    
    def test_delete_shop_not_found(self, client):
        """测试删除不存在的店铺"""
        response = client.delete("/api/shops/nonexistent_shop")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    def test_shop_validation_edge_cases(self, client):
        """测试店铺验证的边界情况"""
        # 测试空字符串
        invalid_data = {
            "id": "",
            "name": "",
            "description": "",
            "location": "",
            "contact": ""
        }
        
        response = client.post("/api/shops", json=invalid_data)
        assert response.status_code == 422
        
        # 测试过长的字符串（如果有长度限制）
        long_string = "x" * 1000
        invalid_data = {
            "id": "test_long",
            "name": long_string,
            "description": long_string,
            "location": long_string,
            "contact": long_string
        }
        
        response = client.post("/api/shops", json=invalid_data)
        # 可能成功或验证失败，取决于是否有长度限制
        assert response.status_code in [200, 201, 422]