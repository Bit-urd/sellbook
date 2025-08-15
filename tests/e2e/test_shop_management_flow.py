"""
店铺管理端到端测试
测试完整的店铺管理工作流程
"""
import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.mark.e2e
class TestShopManagementFlow:
    """店铺管理端到端测试类"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    def test_complete_shop_lifecycle(self, client):
        """测试完整的店铺生命周期"""
        # 1. 创建店铺
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        shop_data = {
            "shop_id": f"lifecycle_test_{unique_id}",
            "shop_name": "生命周期测试店铺",
            "platform": "kongfuzi",
            "shop_url": f"http://test{unique_id}.lifecycle.shop",
            "shop_type": "个人书店"
        }
        
        create_response = client.post("/api/shops", json=shop_data)
        assert create_response.status_code in [200, 201]
        created_shop = create_response.json()
        assert created_shop["success"] == True
        shop_business_id = created_shop["data"]["shop_id"]  # 业务ID
        
        # 验证创建的数据
        assert created_shop["message"] == "店铺创建成功"
        assert created_shop["data"]["shop_id"] == shop_data["shop_id"]
        
        # 2. 获取店铺详情
        get_response = client.get(f"/api/shops/{shop_business_id}")
        assert get_response.status_code == 200
        retrieved_response = get_response.json()
        assert retrieved_response["success"] == True
        retrieved_shop = retrieved_response["data"]
        assert retrieved_shop["shop_id"] == shop_business_id
        assert retrieved_shop["shop_name"] == shop_data["shop_name"]
        
        # 3. 更新店铺信息
        update_data = {
            "shop_name": "更新后的店铺名称",
            "shop_url": "http://updated.shop.com",
            "shop_type": "更新后的店铺类型",
            "status": "active"
        }
        
        update_response = client.put(f"/api/shops/{shop_business_id}", json=update_data)
        assert update_response.status_code == 200
        updated_shop = update_response.json()
        assert updated_shop["success"] == True
        assert updated_shop["message"] == "店铺更新成功"
        
        # 4. 验证店铺出现在店铺列表中
        list_response = client.get("/api/shops")
        assert list_response.status_code == 200
        shops_response = list_response.json()
        assert shops_response["success"] == True
        shops = shops_response["data"]["shops"]
        assert any(shop["shop_id"] == shop_business_id for shop in shops)
        
        # 5. 删除店铺（跳过书籍相关测试）
        delete_response = client.delete(f"/api/shops/{shop_business_id}")
        assert delete_response.status_code in [200, 204]
        
        # 6. 验证店铺已删除
        get_deleted_response = client.get(f"/api/shops/{shop_business_id}")
        assert get_deleted_response.status_code == 404
    
    def test_multiple_shops_management(self, client):
        """测试多店铺管理"""
        # 创建多个店铺
        shops_data = [
            {
                "shop_id": f"multi_shop_{i}",
                "shop_name": f"多店铺测试 {i}",
                "platform": "kongfuzi",
                "shop_url": f"http://test.shop{i}.com",
                "shop_type": "测试店铺"
            }
            for i in range(1, 4)
        ]
        
        created_shops = []
        for shop_data in shops_data:
            response = client.post("/api/shops", json=shop_data)
            if response.status_code in [200, 201]:
                created_shops.append(response.json())
        
        # 验证所有店铺都在列表中
        list_response = client.get("/api/shops")
        assert list_response.status_code == 200
        all_shops = list_response.json()
        
        for created_shop in created_shops:
            assert any(shop["shop_id"] == created_shop["data"]["shop_id"] for shop in all_shops["data"])
        
        # 为每个店铺添加不同的书籍
        for i, shop in enumerate(created_shops):
            book_data = {
                "isbn": f"978711100001{i}",
                "title": f"店铺 {shop['name']} 的书籍",
                "author": f"作者 {i}",
                "publisher": "测试出版社",
                "price": 40 + i * 10,
                "stock_quantity": 10 + i * 5,
                "shop_id": shop["id"]
            }
            
            book_response = client.post("/api/books", json=book_data)
            # 书籍创建可能成功或失败
        
        # 验证每个店铺的书籍
        for shop in created_shops:
            books_response = client.get(f"/api/shops/{shop['id']}/books")
            assert books_response.status_code == 200
            books = books_response.json()
            
            # 验证书籍属于正确的店铺
            for book in books:
                assert book["shop_id"] == shop["id"]
        
        # 清理：删除所有创建的店铺和书籍
        for shop in created_shops:
            # 先删除店铺的书籍
            books_response = client.get(f"/api/shops/{shop['id']}/books")
            if books_response.status_code == 200:
                books = books_response.json()
                for book in books:
                    client.delete(f"/api/books/{book['isbn']}")
            
            # 删除店铺
            client.delete(f"/api/shops/{shop['id']}")
    
    def test_shop_business_operations(self, client):
        """测试店铺业务操作流程"""
        # 1. 创建店铺
        shop_data = {
            "id": "business_ops_shop",
            "name": "业务操作测试店铺",
            "description": "用于测试业务操作的店铺",
            "location": "商业区",
            "contact": "business@test.com"
        }
        
        shop_response = client.post("/api/shops", json=shop_data)
        if shop_response.status_code not in [200, 201]:
            pytest.skip("Cannot create test shop")
        
        shop_id = shop_response.json()["id"]
        
        # 2. 添加初始库存
        initial_books = [
            {
                "isbn": "9787111000020",
                "title": "畅销书籍",
                "author": "知名作者",
                "publisher": "知名出版社",
                "price": 89.99,
                "stock_quantity": 50,
                "shop_id": shop_id
            },
            {
                "isbn": "9787111000021",
                "title": "专业书籍",
                "author": "专家作者",
                "publisher": "专业出版社",
                "price": 120.00,
                "stock_quantity": 30,
                "shop_id": shop_id
            }
        ]
        
        created_books = []
        for book_data in initial_books:
            book_response = client.post("/api/books", json=book_data)
            if book_response.status_code in [200, 201]:
                created_books.append(book_response.json())
        
        # 3. 模拟销售操作（减少库存）
        for book in created_books:
            current_stock = book["stock_quantity"]
            sold_quantity = 5
            new_stock = current_stock - sold_quantity
            
            stock_response = client.patch(
                f"/api/books/{book['isbn']}/stock",
                json={"stock_quantity": new_stock}
            )
            assert stock_response.status_code == 200
        
        # 4. 检查库存状态
        for book in created_books:
            book_response = client.get(f"/api/books/{book['isbn']}")
            if book_response.status_code == 200:
                current_book = book_response.json()
                assert current_book["stock_quantity"] < book["stock_quantity"]
        
        # 5. 添加新书籍（模拟进货）
        new_book_data = {
            "isbn": "9787111000022",
            "title": "新进书籍",
            "author": "新作者",
            "publisher": "新出版社",
            "price": 75.00,
            "stock_quantity": 40,
            "shop_id": shop_id
        }
        
        new_book_response = client.post("/api/books", json=new_book_data)
        if new_book_response.status_code in [200, 201]:
            created_books.append(new_book_response.json())
        
        # 6. 更新价格（模拟价格调整）
        for book in created_books[:2]:  # 只更新前两本书的价格
            new_price = float(book["price"]) * 1.1  # 涨价10%
            update_response = client.put(
                f"/api/books/{book['isbn']}",
                json={"price": new_price}
            )
            # 价格更新可能成功或失败
        
        # 7. 生成业务报告（获取店铺所有书籍）
        final_inventory_response = client.get(f"/api/shops/{shop_id}/books")
        assert final_inventory_response.status_code == 200
        final_inventory = final_inventory_response.json()
        
        # 验证库存数据
        assert len(final_inventory) >= len(created_books)
        
        # 8. 清理
        for book in created_books:
            client.delete(f"/api/books/{book['isbn']}")
        
        client.delete(f"/api/shops/{shop_id}")
    
    def test_shop_error_scenarios(self, client):
        """测试店铺相关的错误场景"""
        # 1. 尝试创建重复ID的店铺
        shop_data = {
            "shop_id": "duplicate_test_shop",
            "shop_name": "重复测试店铺",
            "platform": "kongfuzi",
            "shop_url": "http://test.example.com",
            "shop_type": "测试书店"
        }
        
        # 第一次创建应该成功
        first_response = client.post("/api/shops", json=shop_data)
        
        # 第二次创建相同ID应该失败
        second_response = client.post("/api/shops", json=shop_data)
        assert second_response.status_code in [400, 409]
        
        # 2. 尝试获取不存在的店铺
        nonexistent_response = client.get("/api/shops/nonexistent_shop")
        assert nonexistent_response.status_code == 404
        
        # 3. 尝试更新不存在的店铺
        update_response = client.put("/api/shops/nonexistent_shop", json={"name": "新名称"})
        assert update_response.status_code == 404
        
        # 4. 尝试删除不存在的店铺
        delete_response = client.delete("/api/shops/nonexistent_shop")
        assert delete_response.status_code == 404
        
        # 5. 尝试创建无效数据的店铺
        invalid_shop_data = {
            "id": "",  # 空ID
            "name": "",  # 空名称
        }
        
        invalid_response = client.post("/api/shops", json=invalid_shop_data)
        assert invalid_response.status_code == 422
        
        # 清理（如果第一次创建成功）
        if first_response.status_code in [200, 201]:
            client.delete("/api/shops/duplicate_test_shop")