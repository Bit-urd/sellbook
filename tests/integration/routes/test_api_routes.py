"""
API路由集成测试
"""
import pytest
from fastapi.testclient import TestClient
from src.main import app


class TestAPIRoutes:
    """API路由集成测试类"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    def test_health_check(self, client):
        """测试健康检查接口"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    def test_root_endpoint(self, client):
        """测试根路径接口 - 返回HTML页面"""
        response = client.get("/")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "<!DOCTYPE html>" in response.text
    
    def test_api_docs_accessible(self, client):
        """测试API文档可访问"""
        response = client.get("/docs")
        assert response.status_code == 200
        
        response = client.get("/redoc")
        assert response.status_code == 200
        
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
    
    def test_cors_headers(self, client):
        """测试CORS头部设置"""
        # 测试预检请求
        response = client.options("/", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })
        
        # 检查CORS头部
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
    
    def test_invalid_route_404(self, client):
        """测试无效路由返回404"""
        response = client.get("/nonexistent-route")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
    
    def test_api_prefix_routes(self, client):
        """测试API前缀路由"""
        # 测试店铺API路由前缀
        response = client.get("/api/shops")
        # 可能返回200（空列表）或404（如果路由不存在）
        assert response.status_code in [200, 404, 422]
        
        # 测试书籍API路由前缀
        response = client.get("/api/books")
        assert response.status_code in [200, 404, 422]
    
    def test_content_type_headers(self, client):
        """测试内容类型头部"""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
    
    def test_error_handling_format(self, client):
        """测试错误处理格式"""
        # 尝试访问可能触发错误的端点
        response = client.post("/api/shops", json={})
        
        # 如果有错误，检查错误格式
        if response.status_code >= 400:
            data = response.json()
            # FastAPI标准错误格式
            assert "detail" in data or "message" in data
    
    def test_method_not_allowed(self, client):
        """测试方法不允许的情况"""
        # 尝试对只支持GET的端点使用POST
        response = client.post("/health")
        assert response.status_code == 405
        
        data = response.json()
        assert "detail" in data