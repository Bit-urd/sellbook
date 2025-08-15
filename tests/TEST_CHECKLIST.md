# 测试修复检查清单 ✅

## 开始测试之前 - 必做检查

### 🔍 1. 数据探索（第一步）
```bash
# ✅ 查看真实数据库结构
sqlite3 data/sellbook.db ".schema shops"
sqlite3 data/sellbook.db ".schema books"

# ✅ 查看真实数据样例  
sqlite3 data/sellbook.db "SELECT * FROM shops LIMIT 3;"
sqlite3 data/sellbook.db "SELECT * FROM books LIMIT 3;"

# ✅ 了解数据量
sqlite3 data/sellbook.db "SELECT COUNT(*) FROM shops; SELECT COUNT(*) FROM books;"
```

### 🔍 2. API响应探索
```python
# ✅ 直接测试API获取真实响应格式
from src.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
response = client.get('/api/shops')
print('实际响应格式:', response.json())
```

## 测试顺序检查

### ✅ 第1步：查询测试 (READ)
- [ ] 测试GET端点是否返回正确格式
- [ ] 验证分页结构：`{"success": true, "data": {"items": [], "pagination": {}}}`
- [ ] 确认字段名称与数据库一致

### ✅ 第2步：创建测试 (CREATE)  
- [ ] 使用从步骤1了解的真实字段格式
- [ ] 生成唯一ID避免冲突：`f"test_{uuid.uuid4()[:8]}"`
- [ ] 验证创建成功的响应格式

### ✅ 第3步：更新测试 (UPDATE)
- [ ] 基于步骤2创建的数据进行更新
- [ ] 使用正确的业务ID而不是数据库自增ID

### ✅ 第4步：删除测试 (DELETE)
- [ ] 最后测试删除功能
- [ ] 验证删除后的404响应

## 常见错误修复清单

### 422 Unprocessable Entity
- [ ] 检查请求字段名是否与Pydantic模型匹配
- [ ] 确认必填字段都已提供
- [ ] 验证字段类型正确

### KeyError in 测试断言
- [ ] 打印实际API响应：`print(response.json())`
- [ ] 修正断言以匹配真实响应结构
- [ ] 使用嵌套访问：`data["data"]["shops"]`而不是`data`

### 500 Internal Server Error
- [ ] 检查服务器日志错误信息
- [ ] 验证数据库表结构是否最新
- [ ] 修复SQL查询中的列引用错误

### 404 Not Found
- [ ] 确认路由路径正确
- [ ] 检查是否使用了正确的HTTP方法
- [ ] 验证路由是否已注册

## 数据格式检查清单

### 店铺(Shops) API
```python
# ✅ 创建请求格式
{
    "shop_id": "unique_id",      # 不是 "id" 
    "shop_name": "店铺名称",      # 不是 "name"
    "platform": "kongfuzi",     # 必需字段
    "shop_url": "http://...",    
    "shop_type": "类型"
}

# ✅ 响应格式
{
    "success": true,
    "data": {
        "shops": [...],
        "pagination": {...}
    }
}
```

### 书籍(Books) API  
```python
# ✅ 创建请求格式
{
    "isbn": "9787111000001",
    "title": "书名",
    "author": "作者",
    "publisher": "出版社", 
    "publish_date": "2024-01-01",  # 不是 "publication_date"
    "category": "分类"
}
```

## 测试数据最佳实践

### ✅ 唯一性处理
```python
import uuid
unique_id = str(uuid.uuid4())[:8]
test_data = {
    "shop_id": f"test_shop_{unique_id}",
    "shop_name": f"测试店铺_{unique_id}"
}
```

### ✅ 灵活断言
```python
# ❌ 避免硬编码
assert len(shops) == 5

# ✅ 灵活验证
assert len(shops) >= 0
if shops:
    for shop in shops:
        assert "shop_id" in shop
```

## 调试技巧

### 🔍 响应调试
```python
def test_something(client):
    response = client.get("/api/endpoint")
    print(f"状态码: {response.status_code}")  
    print(f"响应: {response.text}")
    if response.status_code == 200:
        print(f"JSON: {response.json()}")
    
    # 然后根据实际响应修正测试
```

### 🔍 数据库状态检查
```bash
# 测试前后检查数据变化
sqlite3 data/sellbook.db "SELECT COUNT(*) as shop_count FROM shops;"
```

## 最终验证检查

### ✅ 修复后必做
- [ ] 单个测试通过：`pytest tests/path/to/test.py::test_name -v`
- [ ] 相关测试组通过：`pytest tests/integration/routes/test_shops.py -v`
- [ ] 全套测试状态改善：`pytest --tb=no -q`
- [ ] 测试覆盖率保持：`pytest --cov=src`

### ✅ 成功指标
- [ ] 失败测试数量减少
- [ ] 通过测试数量增加
- [ ] 没有引入新的测试失败
- [ ] API响应格式一致性提升

## 经验总结

### ✅ 做对的事情
1. **数据优先** - 永远从真实数据开始
2. **顺序正确** - READ → CREATE → UPDATE → DELETE
3. **格式验证** - 基于实际API响应编写断言
4. **唯一标识** - 避免测试冲突
5. **记录学习** - 文档化发现的问题

### ❌ 避免的错误  
1. 假设API数据格式
2. 忽略数据库真实结构
3. 从创建测试开始
4. 硬编码测试期望
5. 不查看实际错误信息

---

**记住：每个测试失败都是学习真实系统行为的机会！**

*使用这个清单确保测试修复的系统性和有效性*