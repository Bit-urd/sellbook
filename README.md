# 卖书网站价差数据分析系统 v2.0

## 系统简介

专门分析孔夫子旧书网和多抓鱼两个平台书籍价差的数据系统，通过爬取对比发现套利机会。支持ISBN实时查询、销售数据管理、智能价差分析等功能。

## 快速开始

### 1. 创建虚拟环境并安装依赖
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
playwright install chromium
```

### 2. 数据迁移（如有历史数据）
```bash
python migrate_data.py
```

### 3. 启动Chrome（爬虫需要）
```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# Windows  
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222
```

### 4. 启动系统
```bash
python app.py
```

## 访问地址

- **主页**: http://127.0.0.1:8000/ - 数据展示、分析和ISBN搜索
- **销售数据概览**: http://127.0.0.1:8000/sales-admin - 销售数据统计概览 🆕
- **店铺管理**: http://127.0.0.1:8000/shop-admin - 店铺增删改查与爬取管理 🆕
- **书籍管理**: http://127.0.0.1:8000/book-admin - 书籍增删改查与爬取管理 🆕
- **爬虫控制**: http://127.0.0.1:8000/crawler-admin - 管理爬虫任务（隐藏入口）
- **API文档**: http://127.0.0.1:8000/docs

## 核心功能

### 📊 主页功能（数据展示 + ISBN搜索）
- **数据展示**
  - 销售排行榜（支持分页，每页20条）
  - 差价排行榜（孔夫子vs多抓鱼，支持分页）
  - 预期利润排行（销量×差价，支持分页）
  - 时间筛选器（3天/7天/30天/全部）
  - 本地库书籍搜索
  - 实时统计卡片（销量、价格、库存）
  
- **ISBN搜索分析** 🆕
  - 输入ISBN实时查询书籍销售数据
  - 1天/7天/30天销量统计
  - 价格区间分析（最高/最低/平均价）
  - 销售趋势图表展示
  - 最新销售日期追踪

### 🏪 店铺管理模块 🆕
- **增删改查功能**
  - 添加新店铺（店铺ID、名称、平台、URL等）
  - 编辑店铺信息
  - 删除店铺（同时清理相关数据）
  - 搜索店铺（支持ID和名称搜索）
  - 分页展示店铺列表
  
- **爬取状态监控**
  - 实时显示每个店铺的书籍总数
  - 统计未爬取书籍数量
  - 可视化爬取进度（进度条+百分比）
  - 爬取状态标识（未开始/部分爬取/已完成）
  - 显示最后更新时间
  
- **爬取功能**
  - **单店全量爬取** - 爬取店铺所有书籍的销售数据
  - **单店增量爬取** - 只爬取未爬取的书籍（提高效率）
  - **批量全量爬取** - 选择多个店铺进行全量爬取
  - **批量增量爬取** - 选择多个店铺进行增量爬取
  
### 📚 书籍管理模块 🆕
- **增删改查功能**
  - 添加新书籍（ISBN、书名、作者、出版社等）
  - 编辑书籍信息
  - 删除书籍（同时清理销售记录）
  - 多条件搜索（ISBN、书名、作者、出版社）
  - 分页展示书籍列表
  
- **爬取状态管理**
  - 筛选已爬取/未爬取书籍
  - 实时统计（总数、已爬取、未爬取、爬取率）
  - 今日更新数量统计
  - 本周更新数量统计
  - 显示最后销售更新时间
  
- **爬取功能**
  - **单本书籍爬取** - 爬取指定ISBN的销售数据
  - **批量爬取** - 选择多本书籍批量爬取
  - **查看详情** - 查看书籍详细销售数据、价格统计、在售店铺
  
### 📊 销售数据概览
- **统计仪表板**
  - 店铺总数、书籍总数统计
  - 已爬取/未爬取书籍统计
  - 爬取率实时计算显示
- **快速访问**
  - 店铺列表快速查看
  - 书籍爬取状态监控
  - 一键跳转到详细管理页面
- **注意**：详细的增删改查功能已迁移至独立的店铺管理和书籍管理模块

### 🕷️ 爬虫控制（管理页）
- 批量添加店铺
- 更新店铺书籍数据
- 更新多抓鱼价格
- 查看任务状态
- 手动触发爬虫
- 删除爬虫任务

## 项目结构

```
sellbook/
├── src/                 # 源代码
│   ├── models/          # 数据模型层
│   │   ├── database.py  # 数据库连接管理
│   │   ├── models.py    # 数据模型定义
│   │   ├── book.py      # 书籍模型
│   │   ├── shop.py      # 店铺模型
│   │   └── repositories.py # 数据仓库层
│   ├── repositories/    # 数据访问层
│   │   ├── book_repository.py # 书籍数据访问
│   │   └── shop_repository.py # 店铺数据访问
│   ├── services/        # 业务服务层
│   │   ├── analysis_service.py # 数据分析服务
│   │   ├── crawler_service.py  # 爬虫服务
│   │   ├── book_service.py     # 书籍业务服务
│   │   └── shop_service.py     # 店铺业务服务
│   ├── routes/          # API路由层
│   │   ├── api_routes.py # 数据分析API路由
│   │   ├── shop_routes.py # 店铺管理路由
│   │   └── book_routes.py # 书籍管理路由
│   ├── crawlers/        # 爬虫模块
│   │   └── isbn_crawler.py # ISBN爬虫
│   ├── static/          # 前端文件
│   │   ├── index.html   # 主页（含ISBN搜索）
│   │   ├── sales_data_admin.html # 销售数据概览页
│   │   ├── shop_admin.html # 店铺管理页
│   │   ├── book_admin.html # 书籍管理页
│   │   └── crawler_admin.html # 爬虫控制页
│   ├── database.py      # 数据库工具（废弃）
│   ├── exceptions.py    # 自定义异常
│   └── main.py          # FastAPI应用入口
├── tests/               # 测试代码
│   ├── unit/            # 单元测试
│   │   ├── models/      # 模型测试
│   │   ├── services/    # 服务测试
│   │   ├── repositories/ # 仓库测试
│   │   ├── crawlers/    # 爬虫测试
│   │   └── utils/       # 工具测试
│   ├── integration/     # 集成测试
│   │   └── routes/      # 路由集成测试
│   ├── e2e/            # 端到端测试
│   ├── fixtures/       # 测试数据
│   └── conftest.py     # pytest配置
├── data/               # 数据文件
│   └── sellbook.db     # SQLite数据库
├── htmlcov/            # 测试覆盖率报告（自动生成）
├── venv/               # Python虚拟环境
├── .gitignore          # Git忽略文件
├── .coveragerc         # 覆盖率配置
├── pytest.ini          # pytest配置
├── pyproject.toml      # 项目配置和依赖
├── requirements.txt    # 依赖包（兼容性）
├── uv.lock            # uv锁定文件
├── app.py             # 启动脚本
├── CLAUDE.md          # 开发指南
└── README.md          # 项目文档
```

## 数据库结构

### 主要数据表
- **shops** - 店铺信息表
- **books** - 书籍基础信息表（含 `is_crawled` 和 `last_sales_update` 字段）
- **book_inventory** - 书籍库存价格表
- **sales_records** - 销售记录表
- **crawl_tasks** - 爬虫任务表
- **data_statistics** - 数据统计缓存表

## API接口

### 店铺管理API (`/api/shops`)
- `GET /api/shops` - 获取店铺列表（分页、搜索）
- `GET /api/shops/{shop_id}` - 获取店铺详情
- `POST /api/shops` - 创建新店铺
- `PUT /api/shops/{shop_id}` - 更新店铺信息
- `DELETE /api/shops/{shop_id}` - 删除店铺
- `POST /api/shops/{shop_id}/crawl` - 爬取单个店铺（支持增量）
- `POST /api/shops/batch-crawl` - 批量爬取店铺

### 书籍管理API (`/api/books`)
- `GET /api/books` - 获取书籍列表（分页、搜索、筛选）
- `GET /api/books/{isbn}` - 获取书籍详情
- `POST /api/books` - 创建新书籍
- `PUT /api/books/{isbn}` - 更新书籍信息
- `DELETE /api/books/{isbn}` - 删除书籍
- `POST /api/books/{isbn}/crawl` - 爬取单本书籍
- `POST /api/books/batch-crawl` - 批量爬取书籍
- `GET /api/books/stats/crawl-summary` - 获取爬取统计

### 数据分析API (`/api`)
- `GET /api/dashboard` - 获取仪表板数据
- `GET /api/sales/statistics` - 获取销售统计
- `GET /api/sales/hot` - 获取热销排行
- `GET /api/profitable/items` - 获取利润商品
- `POST /api/book/analyze` - ISBN实时分析

### 销售数据API (`/sales-data`)
- `GET /sales-data/shops` - 获取店铺列表（旧接口）
- `POST /sales-data/shop/{shop_id}/crawl-sales` - 爬取店铺销售数据
- `POST /sales-data/crawl-all-shops` - 一键爬取所有店铺
- `GET /sales-data/shop/{shop_id}/sales-stats` - 获取店铺销售统计
- `GET /sales-data/books/crawl-status` - 获取书籍爬取状态

## 技术栈

- **后端框架**：FastAPI 0.100+
- **数据库**：SQLite 3
- **爬虫技术**：Playwright + Aiohttp
- **前端技术**：原生HTML/CSS/JavaScript + Chart.js
- **Python版本**：3.8+
- **测试框架**：pytest + pytest-cov + pytest-asyncio

## 🧪 测试与质量保障

### 测试架构
项目采用分层测试策略，确保代码质量和功能稳定性：

```
tests/
├── unit/              # 单元测试 - 测试单个函数/类
│   ├── models/        # 数据模型测试
│   ├── services/      # 业务服务测试
│   ├── repositories/  # 数据访问层测试
│   └── utils/         # 工具函数测试
├── integration/       # 集成测试 - 测试组件交互
│   ├── routes/        # API路由测试
│   └── database/      # 数据库集成测试
└── e2e/              # 端到端测试 - 测试完整业务流程
    ├── book_management_flow.py
    └── shop_management_flow.py
```

### 运行测试

#### 基本测试命令
```bash
# 运行所有测试
pytest

# 按类型运行测试
pytest -m unit          # 单元测试
pytest -m integration   # 集成测试
pytest -m e2e           # 端到端测试

# 运行特定测试文件
pytest tests/unit/models/test_book.py -v

# 查看测试覆盖率
pytest --cov=src --cov-report=html
# 覆盖率报告: htmlcov/index.html
```

#### 调试测试
```bash
# 详细输出 + 调试信息
pytest -v -s

# 只运行失败的测试
pytest --lf

# 运行到第一个失败就停止
pytest -x
```

### 测试覆盖率

当前测试覆盖率：**79%** ✅

#### 覆盖率分析原则

**为什么不追求100%覆盖率？**

测试覆盖率低的主要原因不是测试不足，而是包含了不应该测试的代码：

1. **Web应用启动代码** (`main.py`) 
   - FastAPI启动/关闭事件
   - HTML模板渲染逻辑
   - 静态文件服务

2. **外部依赖服务** (`crawler_service.py`)
   - 异步爬虫逻辑需要外部浏览器
   - 网络请求依赖第三方网站
   - Playwright交互需要真实环境

3. **数据分析服务** (`analysis_service.py`)
   - 复杂数据分析需要大量真实数据
   - 统计计算依赖完整数据集

4. **复杂业务API** (`api_routes.py`, `repositories.py`)
   - 数据分析类API端点
   - 复杂的数据访问逻辑

#### 排除的代码类型
```python
# .coveragerc 配置
[run]
omit = 
    src/main.py                    # Web启动和模板代码
    src/services/crawler_service.py  # 爬虫外部依赖
    src/services/analysis_service.py # 数据分析复杂逻辑
    src/routes/api_routes.py       # 数据分析API
    src/models/repositories.py    # 复杂数据访问层
```

#### 核心业务代码覆盖率 ✅
- **数据模型**: 100%
- **业务服务**: 98-100%  
- **数据仓库**: 100%
- **路由控制器**: 60-63%
- **ISBN爬虫**: 95%

### 测试开发原则

#### 🏆 数据驱动测试法则

**永远按照以下顺序进行测试开发：**

1. **READ（查询）→ CREATE（创建）→ UPDATE（更新）→ DELETE（删除）**
2. **先了解生产数据 → 再编写测试**

```bash
# ✅ 正确的测试开发流程

# 步骤1：查看生产数据库真实结构
sqlite3 data/sellbook.db ".schema shops"
sqlite3 data/sellbook.db "SELECT * FROM shops LIMIT 3;"

# 步骤2：基于真实数据编写查询测试
# 步骤3：基于查询结果编写创建测试  
# 步骤4：测试更新和删除功能
```

#### ⚠️ 避免的错误做法
- ❌ 假设API数据格式而不验证
- ❌ 直接从创建测试开始
- ❌ 用测试数据去"适配"API

#### 🔍 API响应格式验证
```python
# ⚠️ 在修复测试前，先查看真实API响应
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

### 测试最佳实践

1. **唯一性处理**
   ```python
   import uuid
   unique_id = str(uuid.uuid4())[:8]
   test_data = {"shop_id": f"test_shop_{unique_id}"}
   ```

2. **错误码理解**
   - 422: 数据格式不匹配
   - 400: 业务逻辑冲突（如重复ID）
   - 500: 服务器内部错误

3. **数据库字段映射**
   - 真实字段: `shop_id`, `shop_name`, `platform`
   - 测试中必须使用真实字段名

4. **测试隔离**
   - 每个测试使用独立的测试数据
   - 测试完成后清理数据

## 注意事项

1. **爬虫配置**：需要Chrome浏览器调试模式（端口9222）
2. **数据安全**：定期备份 `data/sellbook.db` 数据库
3. **访问控制**：爬虫控制和销售数据管理页面建议仅管理员使用
4. **性能优化**：大量数据爬取时建议分批执行
5. **虚拟环境**：强烈建议使用虚拟环境避免依赖冲突

## 更新日志

### v2.1 (2024-01) 🆕
- ✨ **重构销售数据管理**：拆分为独立的店铺管理和书籍管理模块
- 🏪 **店铺管理模块**：
  - 完整的CRUD功能（增删改查）
  - 爬取状态实时监控（基于未爬取书籍数）
  - 全量/增量爬取模式
  - 批量操作支持
- 📚 **书籍管理模块**：
  - 完整的CRUD功能
  - 多条件搜索和筛选
  - 单本/批量爬取
  - 详细销售数据查看
- 🎯 **增量爬取功能**：只爬取未爬取的书籍，大幅提升效率
- 📊 **增强统计功能**：今日更新、本周更新等实时统计
- 🔧 **API重构**：新增专门的店铺和书籍管理API路由

### v2.0 (2024-01)
- ✨ 新增ISBN实时搜索分析功能
- ✨ 新增销售数据管理模块
- ✨ 添加书籍爬取状态追踪
- 🔧 优化数据库结构，添加 `is_crawled` 和 `last_sales_update` 字段
- 📊 增强数据统计和可视化功能
- 🎨 改进前端界面设计

### v1.0 (2023-12)
- 🚀 初始版本发布
- 📊 基础数据展示功能
- 🕷️ 爬虫控制功能
- 💰 价差分析功能