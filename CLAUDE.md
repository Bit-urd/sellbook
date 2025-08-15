# CLAUDE.md - 项目开发指南

## 项目概览
这是一个基于孔夫子旧书网的书籍销售数据分析系统，采用FastAPI + SQLite架构，提供实时ISBN查询、销售数据分析和可视化展示功能。

### 核心功能
- **实时ISBN搜索**: 输入ISBN即可获取销量排行、价格分布等统计数据
- **智能去重机制**: 采用孔夫子网item_id作为主键，确保销售记录唯一性
- **品相智能筛选**: 支持"九品以上"和"全部品相"两种数据源
- **动态价格分区**: 自动计算5个价格区间，适用于任意价位书籍
- **成本价格对比**: 集成多抓鱼收购价作为成本参考
- **可视化展示**: 饼状图价格分布、销量排行表、销售趋势图

## 🧪 测试开发重要原则

### 测试顺序的黄金法则
**永远按照以下顺序进行测试开发：**

1. **READ（查询）→ CREATE（创建）→ UPDATE（更新）→ DELETE（删除）**
2. **先了解生产数据 → 再编写测试**

### 数据驱动测试方法

#### ✅ 正确的测试开发流程
```bash
# 步骤1：查看生产数据库真实结构（关注新架构）
sqlite3 data/sellbook.db ".schema sales_records"
sqlite3 data/sellbook.db "SELECT * FROM sales_records LIMIT 3;"
sqlite3 data/sellbook.db ".schema book_inventory"

# 步骤2：测试ISBN搜索API响应格式
curl "http://localhost:8282/api/isbn/9787544291200/analysis?quality=九品以上"

# 步骤3：验证item_id去重机制
sqlite3 data/sellbook.db "SELECT COUNT(*), COUNT(DISTINCT item_id) FROM sales_records;"

# 步骤4：测试价格分布和销量聚合
sqlite3 data/sellbook.db "SELECT isbn, COUNT(*) as sale_count FROM sales_records GROUP BY isbn;"
```

#### ❌ 错误的方法
- 假设API数据格式而不验证
- 忽略item_id去重机制的测试
- 硬编码价格区间而不动态计算
- 不验证品相筛选逻辑
- 使用过时的复合主键假设

### 核心测试注意事项

#### 1. ISBN分析API测试
```python
# ⚠️ 测试ISBN分析API的响应格式：
response = client.get("/api/isbn/9787544291200/analysis?quality=九品以上")
print("实际响应:", response.json())

# ISBN分析API返回格式：
{
    "success": true,
    "data": {
        "hot_sales": [...],      # 销量排行（含min/max/cost价格）
        "price_distribution": {  # 动态价格分布
            "buckets": [...],
            "counts": [...]
        },
        "sales_trend": [...],    # 销售趋势
        "quality_stats": {...}  # 品相统计
    }
}
```

#### 2. 数据库字段映射
**真实数据库结构：**
- 店铺表：`shop_id`, `shop_name`, `platform`, `shop_type`
- 书籍表：`isbn`, `title`, `author`, `publisher`, `is_crawled`
- 销售记录表：`item_id (主键)`, `isbn`, `title`, `sale_price`, `sale_time`, `quality`, `shop_id`
- 库存表：`isbn`, `duozhuayu_new_price`, `duozhuayu_second_hand_price`

**测试中必须使用真实字段名，不能假设！**
**重要：sales_records使用item_id作为主键，而不是复合主键！**

#### 3. 去重机制测试
```python
# 测试item_id去重机制
def test_sales_record_deduplication():
    # 插入相同item_id的记录，应该被忽略
    record1 = SalesRecord(
        item_id="8032832601",  # 孔夫子网的真实item_id
        isbn="9787544291200",
        title="测试书籍",
        sale_price=25.0,
        quality="九品",
        shop_id="test_shop"
    )
    
    # 重复插入应该被INSERT OR IGNORE处理
    result1 = repository.create_sales_record(record1)
    result2 = repository.create_sales_record(record1)  # 应该被忽略
    
    # 验证只有一条记录
    records = repository.get_sales_records_by_isbn("9787544291200")
    assert len(records) == 1
```

#### 4. 价格分布测试
```python
# 测试动态价格分区算法
def test_price_distribution():
    # 创建测试数据
    sales_data = [
        {"sale_price": 10.0}, {"sale_price": 25.0}, 
        {"sale_price": 40.0}, {"sale_price": 55.0}, 
        {"sale_price": 70.0}
    ]
    
    # 测试动态分区计算
    buckets, counts = calculate_price_distribution(sales_data)
    
    # 验证返回5个区间
    assert len(buckets) == 5
    assert len(counts) == 5
    
    # 验证区间覆盖完整价格范围
    assert "10-" in buckets[0]  # 最低价在第一个区间
    assert "-70" in buckets[-1]  # 最高价在最后一个区间
```

#### 5. 错误处理验证
- 422错误：ISBN格式不正确或品相参数无效
- 404错误：指定ISBN没有销售记录
- 500错误：爬虫服务异常或数据库连接问题

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
├── routes/          # API路由层
│   └── api_routes.py       # 统一API接口
├── models/          # 数据模型层
│   ├── database.py         # 数据库连接和初始化
│   ├── models.py          # 数据模型定义
│   └── repositories.py    # 数据访问层
├── services/        # 业务逻辑层
│   ├── crawler_service.py  # 爬虫服务（核心）
│   ├── analysis_service.py # 数据分析服务
│   ├── book_service.py     # 书籍管理服务
│   └── shop_service.py     # 店铺管理服务
├── static/          # 前端文件
│   └── index.html          # 主界面（包含所有功能）
└── crawlers/        # 专用爬虫模块
    └── isbn_crawler.py     # ISBN专用爬虫

data/
└── sellbook.db            # SQLite数据库

tests/
├── unit/           # 单元测试
├── integration/    # 集成测试
├── e2e/           # 端到端测试
└── fixtures/      # 测试数据
```

### 核心功能模块
1. **实时ISBN分析**: 基于ISBN搜索销售记录和价格分布
2. **销售数据爬取**: 智能爬取孔夫子网销售记录，支持品相筛选
3. **去重存储机制**: 使用item_id主键确保数据唯一性
4. **数据可视化**: 销量排行、价格分布图表、销售趋势分析
5. **成本利润分析**: 对比孔夫子售价与多抓鱼收购价

### 关键技术特性
- **URL解析算法**: 从孔夫子网页链接提取唯一item_id
- **品相映射系统**: 自动识别和分类书籍品相等级
- **动态价格分区**: 根据实际价格范围自动计算5个区间
- **JavaScript注入**: 使用Playwright在浏览器中执行DOM解析

## 💻 开发工作流

### 1. ISBN分析功能开发
```bash
# 1. 检查销售记录数据结构
sqlite3 data/sellbook.db "SELECT * FROM sales_records LIMIT 5;"
sqlite3 data/sellbook.db "SELECT isbn, COUNT(*) FROM sales_records GROUP BY isbn LIMIT 5;"

# 2. 测试ISBN搜索API
pytest tests/integration/test_isbn_analysis.py::test_get_isbn_analysis -v

# 3. 验证去重机制
sqlite3 data/sellbook.db "SELECT item_id, COUNT(*) FROM sales_records GROUP BY item_id HAVING COUNT(*) > 1;"

# 4. 测试价格分布算法
pytest tests/unit/test_price_distribution.py -v

# 5. 测试品相筛选
curl "http://localhost:8282/api/isbn/test/analysis?quality=九品以上"
```

### 2. 爬虫问题排查流程
```bash
# 1. 检查item_id提取是否正常
sqlite3 data/sellbook.db "SELECT item_id FROM sales_records WHERE item_id IS NULL;"

# 2. 验证价格数据有效性
sqlite3 data/sellbook.db "SELECT * FROM sales_records WHERE sale_price <= 0 LIMIT 5;"

# 3. 检查时间解析错误
sqlite3 data/sellbook.db "SELECT sale_time FROM sales_records WHERE sale_time > '2024-12-31';"

# 4. 测试品相字段数据质量
sqlite3 data/sellbook.db "SELECT DISTINCT quality FROM sales_records;"

# 5. 验证修复后运行完整测试
pytest tests/integration/test_crawler_service.py -v
```

### 3. 数据完整性检查
```bash
# 检查sales_records表的item_id主键约束
sqlite3 data/sellbook.db ".schema sales_records"

# 验证去重机制有效性
sqlite3 data/sellbook.db "SELECT COUNT(*), COUNT(DISTINCT item_id) FROM sales_records;"

# 检查价格分布数据质量
sqlite3 data/sellbook.db "SELECT MIN(sale_price), MAX(sale_price), AVG(sale_price) FROM sales_records;"

# 验证成本价格关联
sqlite3 data/sellbook.db "SELECT sr.isbn, COUNT(*), bi.duozhuayu_second_hand_price FROM sales_records sr LEFT JOIN book_inventory bi ON sr.isbn = bi.isbn GROUP BY sr.isbn LIMIT 5;"

# 重置数据库（谨慎使用）
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
uvicorn src.main:app --reload --port 8282

# 访问API文档
open http://localhost:8282/docs
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
- **API文档**: http://localhost:8282/docs
- **数据库模式**: `src/models/database.py`
- **主界面**: http://localhost:8282/ (包含所有分析功能)
- **管理界面**: http://localhost:8282/shop-admin (店铺管理)

## 🔍 核心爬虫机制

### item_id提取逻辑
```javascript
// 从孔夫子网页面链接提取item_id
const match = linkElement.href.match(/book\.kongfz\.com\/\d+\/(\d+)\//);
if (match) {
    itemId = match[1];  // 用作sales_records主键
}
```

### 品相筛选策略
- **实时分析**: 默认使用"九品以上"筛选，获取高品质商品数据
- **销售记录爬取**: 使用"全部品相"确保数据完整性
- **品相映射**: 自动将文本品相转换为数值等级

### 价格分区算法
```python
# 动态计算5个价格区间
price_range = max_price - min_price
bucket_size = price_range / 5
buckets = [
    f"{min_price + i*bucket_size:.0f}-{min_price + (i+1)*bucket_size:.0f}"
    for i in range(5)
]
```

## ⚠️ 重要提醒

### 开发原则
1. **永远不要假设数据格式** - 先查看真实数据！
2. **测试顺序很重要** - 查询→创建→更新→删除
3. **使用唯一ID** - 避免测试之间的冲突
4. **基于真实场景** - 测试应该反映实际使用情况
5. **记录问题和解决方案** - 帮助未来的开发

### 爬虫开发注意事项
1. **item_id是关键** - 所有去重逻辑都基于item_id主键
2. **品相筛选有策略** - 实时分析用"九品以上"，爬取用"全部品相"
3. **价格分区要动态** - 不能硬编码价格区间，要根据实际数据计算
4. **DOM解析要稳定** - 使用Playwright的JavaScript注入确保可靠性

### 数据完整性检查
- 定期检查sales_records表的item_id唯一性
- 验证价格数据的合理性（不应为0或负数）
- 确保时间解析正确（2024年数据不应解析为2025年）
- 监控品相字段的数据质量

---

**记住：好的测试来自于对真实数据的深刻理解！**
**核心：item_id去重机制是系统的基础，必须确保其稳定性！**

*最后更新: 2025-08-15*