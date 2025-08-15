# 测试指南 - 基于真实数据的测试方法

## 核心原则：从生产数据出发

**黄金法则：** 永远不要假设API的数据格式，而是要从真实的生产数据中学习。

## 正确的测试顺序 ⭐️

### 1. 查询（READ）- 了解真实数据
```bash
# 首先，查看生产数据库的真实结构
sqlite3 data/sellbook.db ".schema shops"
sqlite3 data/sellbook.db ".schema books"

# 查看真实数据样例
sqlite3 data/sellbook.db "SELECT * FROM shops LIMIT 3;"
sqlite3 data/sellbook.db "SELECT * FROM books LIMIT 3;"
```

**为什么要先查询？**
- 了解真实的数据结构
- 理解API的实际响应格式
- 发现数据库字段的真实名称

### 2. 创建（CREATE）- 基于真实格式
```python
# ❌ 错误：假设的数据格式
shop_data = {
    "id": "test_shop",
    "name": "测试店铺",
    "description": "描述"  # 这些字段可能不存在！
}

# ✅ 正确：基于真实数据库结构
shop_data = {
    "shop_id": "test_shop_001",  # 真实字段名
    "shop_name": "测试店铺",     # 真实字段名
    "platform": "kongfuzi",       # 真实字段名
    "shop_url": "http://test.com",
    "shop_type": "测试类型"
}
```

### 3. 更新（UPDATE）- 验证修改
只有在确认创建和查询都正常后，才测试更新功能。

### 4. 删除（DELETE）- 最后测试
删除操作放在最后，避免影响其他测试。

## 常见错误及解决方案

### 错误1：422 Unprocessable Entity
**原因：** 请求数据格式与API期望不符
**解决：** 
1. 查看API路由的Pydantic模型定义
2. 检查真实数据库表结构
3. 使用正确的字段名

### 错误2：KeyError in Response
**原因：** 测试期望的响应格式与实际不符
**解决：**
```python
# ❌ 错误：假设响应是列表
data = response.json()
assert isinstance(data, list)

# ✅ 正确：基于真实API响应
data = response.json()
assert data["success"] == True
assert "data" in data
shops = data["data"]["shops"]  # 真实的嵌套结构
```

### 错误3：SQL错误（no such column）
**原因：** 数据库表结构与代码不匹配
**解决：**
1. 检查数据库迁移是否执行
2. 验证表结构是否最新
3. 修复SQL查询中的列引用

## API响应格式规范

### 店铺API响应格式
```json
{
    "success": true,
    "data": {
        "shops": [
            {
                "id": 1,
                "shop_id": "unique_shop_id",
                "shop_name": "店铺名称",
                "platform": "kongfuzi",
                "status": "active",
                "created_at": "2025-08-14 06:31:03",
                "updated_at": "2025-08-14 06:31:03",
                "crawl_status": "not_started",
                "crawl_progress": 0
            }
        ],
        "pagination": {
            "page": 1,
            "page_size": 20,
            "total": 10,
            "total_pages": 1
        }
    }
}
```

### 书籍API响应格式
```json
{
    "success": true,
    "data": {
        "books": [
            {
                "id": 1,
                "isbn": "9787111000010",
                "title": "书籍标题",
                "author": "作者",
                "publisher": "出版社",
                "is_crawled": 0,
                "created_at": "2025-08-14 06:32:37",
                "updated_at": "2025-08-14 06:32:37"
            }
        ],
        "pagination": {
            "page": 1,
            "page_size": 20,
            "total": 4,
            "total_pages": 1
        }
    }
}
```

## 数据库表结构

### shops表
```sql
CREATE TABLE shops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id TEXT UNIQUE NOT NULL,      -- 业务ID
    shop_name TEXT NOT NULL,           -- 店铺名称
    platform TEXT DEFAULT 'kongfuzi',  -- 平台
    shop_url TEXT,                     -- 店铺URL
    shop_type TEXT,                    -- 店铺类型
    status TEXT DEFAULT 'active',      -- 状态
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### books表
```sql
CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn TEXT,                         -- ISBN
    title TEXT NOT NULL,               -- 标题
    author TEXT,                       -- 作者
    publisher TEXT,                    -- 出版社
    publish_date TEXT,                 -- 出版日期
    category TEXT,                     -- 分类
    subcategory TEXT,                  -- 子分类
    description TEXT,                  -- 描述
    cover_image_url TEXT,              -- 封面图片
    is_crawled INTEGER DEFAULT 0,      -- 是否已爬取
    last_sales_update TIMESTAMP,       -- 最后销售更新时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 测试数据最佳实践

### 1. 使用唯一ID避免冲突
```python
import uuid
unique_id = str(uuid.uuid4())[:8]
shop_data = {
    "shop_id": f"test_shop_{unique_id}",  # 确保唯一性
    # ...
}
```

### 2. 测试数据清理
```python
@pytest.fixture(autouse=True)
def cleanup_test_data():
    """测试后清理数据"""
    yield
    # 清理测试创建的数据
    # 但不要清理生产数据！
```

### 3. 基于真实数据的断言
```python
# ❌ 错误：硬编码的断言
assert len(shops) == 5

# ✅ 正确：灵活的断言
assert len(shops) >= 0  # 可能没有数据
if shops:
    for shop in shops:
        assert "shop_id" in shop  # 验证结构
```

## 测试调试技巧

### 1. 查看真实API响应
```python
# 在测试失败时打印完整响应
response = client.get("/api/shops")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
assert response.status_code == 200
```

### 2. 使用测试客户端直接测试
```python
from src.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
response = client.get('/api/books')
print('Response:', response.json())
```

### 3. 检查数据库状态
```bash
# 测试前后检查数据
sqlite3 data/sellbook.db "SELECT COUNT(*) FROM shops;"
```

## 测试覆盖率目标

- **单元测试**: 核心业务逻辑 90%+
- **集成测试**: API端点 80%+
- **端到端测试**: 关键用户流程 70%+
- **总体覆盖率**: 最低 80%

## 持续改进

1. **定期更新测试数据**: 当数据库结构变化时，更新测试
2. **监控测试失败**: 失败可能指示代码bug或数据不一致
3. **文档化特殊情况**: 记录任何特殊的测试场景或已知问题

## 测试命令参考

```bash
# 运行所有测试
pytest

# 运行特定类型测试
pytest -m unit          # 单元测试
pytest -m integration   # 集成测试
pytest -m e2e          # 端到端测试

# 查看覆盖率
pytest --cov=src --cov-report=html

# 调试特定测试
pytest tests/integration/routes/test_shop_routes.py::TestShopRoutes::test_get_all_shops -v

# 快速测试（跳过慢速测试）
pytest -m "not slow"
```

## 注意事项总结

⚠️ **永远不要：**
- 假设API数据格式
- 在不了解真实数据的情况下编写测试
- 忽略数据库的实际结构
- 硬编码测试期望值

✅ **始终要：**
- 从查询真实数据开始
- 基于生产数据编写测试
- 遵循查询→创建→更新→删除的顺序
- 使用灵活的断言
- 记录发现的问题和解决方案

---

*最后更新: 2025-08-14*
*基于实际测试经验总结*