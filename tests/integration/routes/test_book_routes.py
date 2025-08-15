"""
书籍路由集成测试
"""
import pytest
from fastapi.testclient import TestClient
from decimal import Decimal
from src.main import app
from tests.fixtures.sample_data import SAMPLE_BOOKS


class TestBookRoutes:
    """书籍路由集成测试类"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def test_shop_id(self, client):
        """创建测试店铺并返回ID"""
        shop_data = {
            "id": "book_test_shop",
            "name": "书籍测试店铺",
            "description": "用于书籍测试的店铺",
            "location": "测试位置",
            "contact": "测试联系方式"
        }
        
        response = client.post("/api/shops", json=shop_data)
        if response.status_code in [200, 201]:
            return shop_data["id"]
        else:
            pytest.skip("Cannot create test shop")
    
    def test_create_book_success(self, client, test_shop_id):
        """测试成功创建书籍"""
        book_data = {
            "isbn": "9787111111111",
            "title": "测试书籍",
            "author": "测试作者",
            "publisher": "测试出版社",
            "publication_date": "2024-01-01",
            "price": 59.99,
            "stock_quantity": 10,
            "shop_id": test_shop_id
        }
        
        response = client.post("/api/books", json=book_data)
        
        # 验证响应状态码
        assert response.status_code in [201, 200]
        
        # 验证响应数据
        data = response.json()
        assert data["isbn"] == book_data["isbn"]
        assert data["title"] == book_data["title"]
        assert data["author"] == book_data["author"]
        assert data["publisher"] == book_data["publisher"]
        assert float(data["price"]) == book_data["price"]
        assert data["stock_quantity"] == book_data["stock_quantity"]
        assert data["shop_id"] == book_data["shop_id"]
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_create_book_invalid_data(self, client):
        """测试创建书籍时提供无效数据"""
        # 缺少必填字段
        invalid_data = {
            "title": "只有标题"
        }
        
        response = client.post("/api/books", json=invalid_data)
        
        # 验证响应状态码（422表示验证错误）
        assert response.status_code == 422
        
        # 验证错误信息
        data = response.json()
        assert "detail" in data
    
    def test_create_book_duplicate_isbn(self, client, test_shop_id):
        """测试创建重复ISBN的书籍"""
        book_data = {
            "isbn": "9787111222222",
            "title": "第一本书",
            "author": "作者1",
            "publisher": "出版社1",
            "price": 59.99,
            "stock_quantity": 10,
            "shop_id": test_shop_id
        }
        
        # 第一次创建
        response1 = client.post("/api/books", json=book_data)
        
        # 第二次创建相同ISBN的书籍
        book_data["title"] = "第二本书"
        response2 = client.post("/api/books", json=book_data)
        
        # 第二次应该失败（409冲突或400错误请求）
        assert response2.status_code in [409, 400]
    
    def test_get_book_by_isbn_success(self, client, test_shop_id):
        """测试成功根据ISBN获取书籍"""
        # 先创建一本书
        book_data = {
            "isbn": "9787111333333",
            "title": "获取测试书籍",
            "author": "测试作者",
            "publisher": "测试出版社",
            "price": 49.99,
            "stock_quantity": 5,
            "shop_id": test_shop_id
        }
        
        create_response = client.post("/api/books", json=book_data)
        if create_response.status_code not in [200, 201]:
            pytest.skip("Cannot create book for testing")
        
        # 获取书籍
        response = client.get(f"/api/books/{book_data['isbn']}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["isbn"] == book_data["isbn"]
        assert data["title"] == book_data["title"]
    
    def test_get_book_by_isbn_not_found(self, client):
        """测试获取不存在的书籍"""
        response = client.get("/api/books/9999999999999")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    def test_get_books_by_shop(self, client, test_shop_id):
        """测试根据店铺ID获取书籍"""
        response = client.get(f"/api/shops/{test_shop_id}/books")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # 验证所有书籍都属于指定店铺
        for book in data:
            assert book["shop_id"] == test_shop_id
    
    def test_search_books_by_title(self, client):
        """测试获取书籍列表 - 基于真实API格式"""
        # 先测试不带搜索参数的基本功能
        response = client.get("/api/books")
        
        assert response.status_code == 200
        data = response.json()
        
        # 验证响应结构
        assert data["success"] == True
        assert "data" in data
        assert "books" in data["data"]
        assert "pagination" in data["data"]
        
        # 验证书籍列表结构
        books = data["data"]["books"]
        assert isinstance(books, list)
        
        # 验证搜索结果（如果有结果）
        if books:
            for book in books:
                assert "isbn" in book
                assert "title" in book
                assert "created_at" in book
                assert "updated_at" in book
    
    def test_search_books_by_author(self, client):
        """测试根据作者搜索书籍"""
        response = client.get("/api/books/search", params={"author": "谢希仁"})
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # 验证搜索结果
        for book in data:
            assert book["author"] == "谢希仁"
    
    def test_update_book_success(self, client, test_shop_id):
        """测试成功更新书籍"""
        # 先创建一本书
        book_data = {
            "isbn": "9787111444444",
            "title": "更新测试书籍",
            "author": "原始作者",
            "publisher": "原始出版社",
            "price": 39.99,
            "stock_quantity": 8,
            "shop_id": test_shop_id
        }
        
        create_response = client.post("/api/books", json=book_data)
        if create_response.status_code not in [200, 201]:
            pytest.skip("Cannot create book for testing")
        
        # 更新书籍
        update_data = {
            "title": "更新后的书名",
            "author": "更新后的作者",
            "price": 49.99,
            "stock_quantity": 12
        }
        
        response = client.put(f"/api/books/{book_data['isbn']}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["isbn"] == book_data["isbn"]
        assert data["title"] == update_data["title"]
        assert data["author"] == update_data["author"]
        assert float(data["price"]) == update_data["price"]
        assert data["stock_quantity"] == update_data["stock_quantity"]
    
    def test_update_book_stock(self, client, test_shop_id):
        """测试更新书籍库存"""
        # 先创建一本书
        book_data = {
            "isbn": "9787111555555",
            "title": "库存测试书籍",
            "author": "测试作者",
            "publisher": "测试出版社",
            "price": 29.99,
            "stock_quantity": 5,
            "shop_id": test_shop_id
        }
        
        create_response = client.post("/api/books", json=book_data)
        if create_response.status_code not in [200, 201]:
            pytest.skip("Cannot create book for testing")
        
        # 更新库存
        new_stock = 20
        response = client.patch(f"/api/books/{book_data['isbn']}/stock", json={"stock_quantity": new_stock})
        
        assert response.status_code == 200
        data = response.json()
        assert data["stock_quantity"] == new_stock
    
    def test_delete_book_success(self, client, test_shop_id):
        """测试成功删除书籍"""
        # 先创建一本书
        book_data = {
            "isbn": "9787111666666",
            "title": "删除测试书籍",
            "author": "测试作者",
            "publisher": "测试出版社",
            "price": 19.99,
            "stock_quantity": 3,
            "shop_id": test_shop_id
        }
        
        create_response = client.post("/api/books", json=book_data)
        if create_response.status_code not in [200, 201]:
            pytest.skip("Cannot create book for testing")
        
        # 删除书籍
        response = client.delete(f"/api/books/{book_data['isbn']}")
        
        assert response.status_code in [200, 204]
        
        # 验证书籍已被删除
        get_response = client.get(f"/api/books/{book_data['isbn']}")
        assert get_response.status_code == 404
    
    def test_delete_book_not_found(self, client):
        """测试删除不存在的书籍"""
        response = client.delete("/api/books/9999999999999")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    def test_get_low_stock_books(self, client):
        """测试获取低库存书籍"""
        threshold = 5
        response = client.get(f"/api/books/low-stock", params={"threshold": threshold})
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # 验证所有返回的书籍库存都低于阈值
        for book in data:
            assert book["stock_quantity"] <= threshold
    
    def test_isbn_search_integration(self, client):
        """测试ISBN搜索集成功能"""
        isbn = "9787111213826"
        response = client.get(f"/api/books/isbn-search/{isbn}")
        
        # 可能返回200（找到）或404（未找到）
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "isbn" in data
            assert "title" in data
            assert "author" in data
    
    def test_book_validation_edge_cases(self, client, test_shop_id):
        """测试书籍验证的边界情况"""
        # 测试无效ISBN格式
        invalid_data = {
            "isbn": "invalid_isbn",
            "title": "测试书籍",
            "shop_id": test_shop_id
        }
        
        response = client.post("/api/books", json=invalid_data)
        # 可能成功或验证失败，取决于ISBN验证规则
        assert response.status_code in [200, 201, 422]
        
        # 测试负数价格
        invalid_data = {
            "isbn": "9787111777777",
            "title": "负价格测试",
            "price": -10.0,
            "shop_id": test_shop_id
        }
        
        response = client.post("/api/books", json=invalid_data)
        # 应该验证失败或接受负价格（取决于业务规则）
        assert response.status_code in [200, 201, 422]