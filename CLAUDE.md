# CLAUDE.md - 项目开发指南

## 项目概览
这是一个书籍销售数据管理系统，基于FastAPI + SQLite构建，包含店铺管理、书籍管理和爬虫功能。

## 🧪 测试开发重要原则

### 测试顺序的黄金法则
**永远按照以下顺序进行测试开发：**

1. **READ（查询）→ CREATE（创建）→ UPDATE（更新）→ DELETE（删除）**
2. **先了解生产数据 → 再编写测试**

### 数据驱动测试方法

#### ✅ 正确的测试开发流程
```bash
# 步骤1：查看生产数据库真实结构
sqlite3 data/sellbook.db ".schema shops"
sqlite3 data/sellbook.db "SELECT * FROM shops LIMIT 3;"

# 步骤2：基于真实数据编写查询测试
# 步骤3：基于查询结果编写创建测试
# 步骤4：测试更新和删除功能
```

#### ❌ 错误的方法
- 假设API数据格式而不验证
- 直接从创建测试开始
- 用测试数据去"适配"API

### 核心测试注意事项

#### 1. API响应格式验证
```python
# ⚠️ 在修复测试前，先查看真实API响应：
response = client.get("/api/shops")
print("实际响应:", response.json())

# 大多数API返回结构化格式：
{
    "success": true,
    "data": {
        "shops": [...],
        "pagination": {...}
    }
}
```

#### 2. 数据库字段映射
**真实数据库结构：**
- 店铺表：`shop_id`, `shop_name`, `platform`, `shop_type`
- 书籍表：`isbn`, `title`, `author`, `publisher`, `is_crawled`

**测试中必须使用真实字段名，不能假设！**

#### 3. 唯一性处理
```python
# 总是生成唯一ID避免测试冲突
import uuid
unique_id = str(uuid.uuid4())[:8]
test_data = {
    "shop_id": f"test_shop_{unique_id}",
    # ...
}
```

#### 4. 错误处理验证
- 422错误通常表示数据格式不匹配
- 400错误通常表示业务逻辑冲突（如重复ID）
- 500错误表示服务器内部错误（需要修复代码）

## 🏗️ 项目架构

### 技术栈
- **后端框架**: FastAPI
- **数据库**: SQLite
- **异步处理**: asyncio/aiohttp
- **网页抓取**: Playwright + BeautifulSoup
- **测试框架**: pytest

### 目录结构
```
src/
├── routes/          # API路由
├── models/          # 数据模型
├── services/        # 业务逻辑
├── repositories/    # 数据访问层
└── crawlers/        # 网页爬虫

tests/
├── unit/           # 单元测试
├── integration/    # 集成测试
├── e2e/           # 端到端测试
└── fixtures/      # 测试数据
```

### 核心功能模块
1. **店铺管理**: 店铺CRUD、状态管理
2. **书籍管理**: 书籍信息、库存管理
3. **爬虫系统**: 自动抓取销售数据
4. **数据分析**: 销售统计和报告

## 💻 开发工作流

### 1. 新功能开发
```bash
# 1. 分析需求，查看现有数据
sqlite3 data/sellbook.db "SELECT * FROM relevant_table LIMIT 5;"

# 2. 先编写查询测试（了解现有数据格式）
pytest tests/integration/routes/test_new_feature.py::test_get_data -v

# 3. 基于真实格式编写业务逻辑
# 4. 编写创建/更新测试
# 5. 运行完整测试套件
pytest
```

### 2. Bug修复流程
```bash
# 1. 重现问题
pytest failing_test.py -v

# 2. 检查数据库状态
sqlite3 data/sellbook.db "SELECT * FROM affected_table;"

# 3. 修复代码
# 4. 验证修复
pytest failing_test.py -v

# 5. 运行回归测试
pytest
```

### 3. 数据库相关开发
```bash
# 检查当前数据库状态
sqlite3 data/sellbook.db ".tables"
sqlite3 data/sellbook.db ".schema table_name"

# 如果需要清理测试数据
rm -f data/sellbook.db
python -c "from src.models.database import db; db.init_database()"
```

## 🔧 常用命令

### 测试命令
```bash
# 运行所有测试
pytest

# 按类型运行测试
pytest -m unit          # 单元测试
pytest -m integration   # 集成测试
pytest -m e2e           # 端到端测试

# 查看测试覆盖率
pytest --cov=src --cov-report=html

# 调试特定测试
pytest path/to/test.py::TestClass::test_method -v -s
```

### 数据库命令
```bash
# 查看数据库结构
sqlite3 data/sellbook.db ".schema"

# 查看表数据
sqlite3 data/sellbook.db "SELECT * FROM shops LIMIT 5;"

# 重置数据库
rm -f data/sellbook.db && python -c "from src.models.database import db; db.init_database()"
```

### 开发服务器
```bash
# 启动开发服务器
uvicorn src.main:app --reload --port 8000

# 访问API文档
open http://localhost:8000/docs
```

## 📊 代码质量标准

### 测试覆盖率要求
- 核心业务逻辑: 90%+
- API端点: 80%+
- 总体覆盖率: 最低80%

### 代码风格
- 遵循PEP 8
- 使用类型提示
- 编写清晰的docstring
- 保持函数简短和专一

## 🐛 常见问题解决

### 1. 测试失败排查
```python
# 在测试中添加调试信息
def test_something(client):
    response = client.get("/api/endpoint")
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {response.json()}")
    # 然后检查期望是否合理
```

### 2. 数据库问题
- 检查表结构是否最新
- 确认字段名称正确
- 验证数据类型匹配

### 3. API格式问题
- 总是先查看真实API响应
- 不要假设响应格式
- 使用真实数据库字段名

## 📚 相关文档

- **详细测试指南**: `tests/TESTING_GUIDE.md`
- **API文档**: http://localhost:8000/docs
- **数据库模式**: `src/models/database.py`

## ⚠️ 重要提醒

1. **永远不要假设数据格式** - 先查看真实数据！
2. **测试顺序很重要** - 查询→创建→更新→删除
3. **使用唯一ID** - 避免测试之间的冲突
4. **基于真实场景** - 测试应该反映实际使用情况
5. **记录问题和解决方案** - 帮助未来的开发

---

**记住：好的测试来自于对真实数据的深刻理解！**

*最后更新: 2025-08-14*