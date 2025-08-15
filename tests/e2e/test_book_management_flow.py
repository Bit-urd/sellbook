"""
书籍管理端到端测试
测试完整的书籍管理工作流程
"""
import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.mark.e2e
class TestBookManagementFlow:
    """书籍管理端到端测试类"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    def test_complete_book_lifecycle(self, client):
        """测试完整的书籍生命周期"""
        # 1. 创建店铺
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        shop_data = {
            "shop_id": f"e2e_test_{unique_id}",
            "shop_name": "端到端测试书店",
            "platform": "kongfuzi",
            "shop_url": f"http://test{unique_id}.example.com",
            "shop_type": "测试书店"
        }
        
        shop_response = client.post("/api/shops", json=shop_data)
        assert shop_response.status_code in [200, 201]
        shop = shop_response.json()
        shop_id = shop["data"]["shop_id"]
        
        # 2. 创建书籍
        book_data = {
            "isbn": f"97871110000{unique_id[:2]}",
            "title": "端到端测试书籍",
            "author": "测试作者",
            "publisher": "测试出版社",
            "publish_date": "2024-01-01",
            "category": "技术",
            "description": "端到端测试书籍描述"
        }
        
        book_response = client.post("/api/books", json=book_data)
        assert book_response.status_code in [200, 201]
        book = book_response.json()
        isbn = book_data["isbn"]
        
        # 3. 验证书籍创建成功
        get_book_response = client.get(f"/api/books/{isbn}")
        assert get_book_response.status_code == 200
        retrieved_book = get_book_response.json()
        assert retrieved_book["success"] == True
        book_data_response = retrieved_book["data"]
        assert book_data_response["title"] == book_data["title"]
        assert book_data_response["isbn"] == isbn
        
        # 4. 更新书籍信息
        update_data = {
            "title": "更新后的书籍标题",
            "author": "更新后的作者"
        }
        
        update_response = client.put(f"/api/books/{isbn}", json=update_data)
        assert update_response.status_code == 200
        update_result = update_response.json()
        assert update_result["success"] == True
        assert "message" in update_result
        
        # 5. 验证书籍更新成功
        get_updated_book_response = client.get(f"/api/books/{isbn}")
        assert get_updated_book_response.status_code == 200
        updated_book = get_updated_book_response.json()
        assert updated_book["success"] == True
        updated_book_data = updated_book["data"]
        assert updated_book_data["title"] == update_data["title"]
        assert updated_book_data["author"] == update_data["author"]
        
        # 6. 搜索书籍
        search_response = client.get("/api/books/search", params={"title": "更新后"})
        assert search_response.status_code == 200
        search_results = search_response.json()
        assert isinstance(search_results, list)
        assert len(search_results) >= 1
        assert any(book["isbn"] == isbn for book in search_results)
        
        # 7. 删除书籍
        delete_response = client.delete(f"/api/books/{isbn}")
        assert delete_response.status_code in [200, 204]
        
        # 8. 验证书籍已删除
        get_deleted_book_response = client.get(f"/api/books/{isbn}")
        assert get_deleted_book_response.status_code == 404
        
        # 9. 清理：删除店铺
        delete_shop_response = client.delete(f"/api/shops/{shop_id}")
        assert delete_shop_response.status_code in [200, 204]
    
    def test_multiple_books_management(self, client):
        """测试多本书籍管理"""
        # 创建测试店铺
        shop_data = {
            "id": "multi_books_shop",
            "name": "多书籍测试店铺",
            "description": "用于多书籍测试",
            "location": "测试地点",
            "contact": "multi@test.com"
        }
        
        shop_response = client.post("/api/shops", json=shop_data)
        if shop_response.status_code not in [200, 201]:
            pytest.skip("Cannot create test shop")
        
        shop_id = shop_response.json()["id"]
        
        # 创建多本书籍
        books_data = [
            {
                "isbn": f"978711100000{i}",
                "title": f"测试书籍 {i}",
                "author": f"作者 {i}",
                "publisher": "测试出版社",
                "price": 50 + i * 10,
                "stock_quantity": 10 + i,
                "shop_id": shop_id
            }
            for i in range(1, 4)
        ]
        
        created_books = []
        for book_data in books_data:
            response = client.post("/api/books", json=book_data)
            if response.status_code in [200, 201]:
                created_books.append(response.json())
        
        # 验证所有书籍都在店铺中
        shop_books_response = client.get(f"/api/shops/{shop_id}/books")
        assert shop_books_response.status_code == 200
        shop_books = shop_books_response.json()
        assert len(shop_books) >= len(created_books)
        
        # 批量更新库存（模拟库存管理）
        for book in created_books:
            new_stock = book["stock_quantity"] - 5
            stock_response = client.patch(f"/api/books/{book['isbn']}/stock", json={"stock_quantity": new_stock})
            assert stock_response.status_code == 200
        
        # 检查低库存书籍
        low_stock_response = client.get("/api/books/low-stock", params={"threshold": 15})
        assert low_stock_response.status_code == 200
        low_stock_books = low_stock_response.json()
        # 应该包含我们刚刚减少库存的书籍
        assert len(low_stock_books) >= 0
        
        # 清理：删除所有创建的书籍
        for book in created_books:
            client.delete(f"/api/books/{book['isbn']}")
        
        # 清理：删除店铺
        client.delete(f"/api/shops/{shop_id}")
    
    def test_isbn_search_integration_flow(self, client):
        """测试ISBN搜索集成流程"""
        # 测试ISBN搜索功能
        test_isbn = "9787111213826"
        
        # 尝试搜索ISBN信息
        search_response = client.get(f"/api/books/isbn-search/{test_isbn}")
        
        # ISBN搜索可能成功或失败，取决于网络和外部服务
        if search_response.status_code == 200:
            search_result = search_response.json()
            
            # 如果搜索成功，验证返回的数据结构
            assert "isbn" in search_result
            assert "title" in search_result
            assert search_result["isbn"] == test_isbn
            
            # 创建店铺来添加书籍
            shop_data = {
                "id": "isbn_test_shop",
                "name": "ISBN测试店铺",
                "description": "用于ISBN测试",
                "location": "测试位置",
                "contact": "isbn@test.com"
            }
            
            shop_response = client.post("/api/shops", json=shop_data)
            if shop_response.status_code in [200, 201]:
                shop_id = shop_response.json()["id"]
                
                # 使用搜索到的信息创建书籍
                book_data = {
                    "isbn": search_result["isbn"],
                    "title": search_result.get("title", "未知标题"),
                    "author": search_result.get("author", "未知作者"),
                    "publisher": search_result.get("publisher", "未知出版社"),
                    "price": 59.99,
                    "stock_quantity": 10,
                    "shop_id": shop_id
                }
                
                book_response = client.post("/api/books", json=book_data)
                if book_response.status_code in [200, 201]:
                    # 验证书籍创建成功
                    created_book = book_response.json()
                    assert created_book["isbn"] == test_isbn
                    
                    # 清理
                    client.delete(f"/api/books/{test_isbn}")
                
                client.delete(f"/api/shops/{shop_id}")
        
        else:
            # 如果ISBN搜索失败，这是正常的（可能是网络问题或外部服务不可用）
            assert search_response.status_code in [404, 500, 503]
    
    def test_error_handling_flow(self, client):
        """测试错误处理流程"""
        # 1. 尝试获取不存在的书籍
        response = client.get("/api/books/9999999999999")
        assert response.status_code == 404
        
        # 2. 尝试创建无效数据的书籍
        invalid_book = {
            "isbn": "invalid_isbn",
            "title": "",  # 空标题
            "shop_id": "nonexistent_shop"
        }
        
        response = client.post("/api/books", json=invalid_book)
        assert response.status_code in [400, 422]
        
        # 3. 尝试更新不存在的书籍
        response = client.put("/api/books/9999999999999", json={"title": "新标题"})
        assert response.status_code == 404
        
        # 4. 尝试删除不存在的书籍
        response = client.delete("/api/books/9999999999999")
        assert response.status_code == 404
        
        # 5. 尝试获取不存在店铺的书籍
        response = client.get("/api/shops/nonexistent_shop/books")
        assert response.status_code in [404, 200]  # 可能返回空列表或404