# 卖书网站价差数据分析系统 v2.0

一个专门用于分析孔夫子旧书网和多抓鱼两个平台书籍价差的数据分析系统。通过爬取两个平台的数据，自动计算价差和利润率，帮助用户发现套利机会。

## 核心模块架构

### 模块1：FastAPI分析服务 (`book_analysis_api.py`)
**功能**：提供Web API和前端界面，实时分析书籍销售数据
- **核心特性**：
  - RESTful API接口设计
  - 实时ISBN销售数据分析
  - Playwright浏览器自动化
  - 多维度销售统计（1天/7天/30天）
  - 价格分析（最高/最低/平均价格）
  - 可视化图表展示

- **技术实现**：
  - FastAPI框架 + Pydantic数据模型
  - 异步浏览器连接管理
  - Chrome调试协议集成
  - 数据持久化到CSV

### 模块2：店铺书籍爬取器 (`incremental_scraper.py`)
**功能**：批量爬取指定店铺的书籍基础信息
- **核心特性**：
  - 多店铺并发爬取
  - 增量式断点续爬
  - 自动去重机制
  - 实时数据保存
  - 爬取进度统计

- **技术实现**：
  - 基于店铺ID列表批量处理
  - Playwright页面自动化
  - CSV增量写入策略
  - itemid去重算法

### 模块3：销售记录分析器 (`sales_analyzer.py`)
**功能**：基于书籍数据，深度分析每本书的销售记录
- **核心特性**：
  - ISBN维度销售分析
  - 时间范围过滤（30天内）
  - 销售趋势统计
  - 价格波动分析
  - 详细销售记录导出

- **技术实现**：
  - 从books_data.csv读取书籍列表
  - 搜索页面销售记录提取
  - 时间戳解析和过滤
  - 销售数据聚合统计

### 模块4：辅助工具
- **`findbook.py`**：单本书籍搜索和数据提取工具
- **`real_browser_scraper.py`**：真实浏览器环境爬取工具
- **`shop_list.txt`**：目标店铺ID配置文件

## 技术栈

- **后端框架**：FastAPI + Python 3.9+
- **浏览器自动化**：Playwright (Chrome CDP)
- **前端**：原生HTML/CSS/JavaScript + Chart.js
- **数据存储**：CSV文件 (计划迁移至SQLite)
- **异步处理**：asyncio + aiohttp

## 快速开始

### 1. 环境准备

```bash
# 使用uv包管理器（推荐）
uv install

# 或使用pip
pip install fastapi uvicorn playwright aiohttp pydantic

# 安装浏览器
playwright install chromium
```

### 2. 启动Chrome调试模式

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug

# Windows
chrome.exe --remote-debugging-port=9222 --user-data-dir=c:\temp\chrome-debug

# Linux
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug
```

### 3. 数据收集流程

```bash
# 步骤1：配置店铺列表
echo "534779" >> shop_list.txt

# 步骤2：爬取店铺书籍数据
python incremental_scraper.py

# 步骤3：分析销售记录（可选）
python sales_analyzer.py

# 步骤4：启动API服务
python book_analysis_api.py
```

### 4. 访问服务

- **主页面**：http://localhost:8000
- **API文档**：http://localhost:8000/docs  
- **健康检查**：http://localhost:8000/health

## API接口说明

### 核心分析接口

```http
POST /analyze
Content-Type: application/json

{
    "book_isbn": "9787521724493"
}
```

**响应数据结构：**

```json
{
    "isbn": "9787521724493",
    "stats": {
        "sales_1_day": 0,
        "sales_7_days": 2, 
        "sales_30_days": 15,
        "total_records": 15,
        "latest_sale_date": "2025-08-13",
        "average_price": 45.67,
        "price_range": {
            "min": 30.0,
            "max": 69.0
        }
    },
    "message": "成功分析ISBN 9787521724493，找到 15 条销售记录",
    "success": true
}
```

### 健康检查接口

```http
GET /health
```

## 数据流架构

```
shop_list.txt → incremental_scraper.py → books_data.csv
                                               ↓
sales_analyzer.py → sales_detail_*.csv + book_sales.csv
                                               ↓
book_analysis_api.py → Chrome Debug → 孔夫子网站 → api_sales_data.csv
                    ↓
                Web Frontend
```

## 项目结构

```
sellbook/
├── book_analysis_api.py    # 模块1：FastAPI分析服务
├── incremental_scraper.py  # 模块2：店铺书籍爬取器  
├── sales_analyzer.py       # 模块3：销售记录分析器
├── findbook.py            # 辅助：单书搜索工具
├── real_browser_scraper.py # 辅助：浏览器爬取工具
├── static/
│   └── index.html         # 前端用户界面
├── shop_list.txt          # 配置：店铺ID列表
├── books_data.csv         # 数据：书籍基础信息
├── api_sales_data.csv     # 数据：API销售记录
├── book_sales.csv         # 数据：销售统计汇总
├── pyproject.toml         # Python项目配置
└── uv.lock               # 依赖版本锁定
```

## 版本说明

### 📊 数据库版本 (v2.0) - 推荐
**已完成的数据库迁移功能**：
- ✅ SQLite轻量级数据库集成
- ✅ 统一的数据模型设计
- ✅ 完整的数据库操作API
- ✅ CSV到SQLite自动迁移工具
- ✅ 数据库版本的三大核心模块

**新增文件**：
- `database.py` - 数据库管理核心
- `book_analysis_api_v2.py` - 数据库版API服务
- `incremental_scraper_v2.py` - 数据库版爬虫
- `sales_analyzer_v2.py` - 数据库版销售分析器
- `migrate_to_database.py` - 数据迁移工具
- `run.py` - 统一启动脚本

### 📁 CSV版本 (v1.0) - 兼容保留
保持原有CSV文件格式的完整功能，确保向后兼容。

## 快速启动 🚀

### 方法1：使用统一启动脚本 (推荐)
```bash
python run.py
```
然后根据菜单选择对应功能模块。

### 方法2：直接运行数据库版本
```bash
# 1. 数据迁移 (首次使用)
python migrate_to_database.py

# 2. 启动API服务
python book_analysis_api_v2.py

# 3. 运行爬虫
python incremental_scraper_v2.py

# 4. 分析销售记录
python sales_analyzer_v2.py
```

## 数据库架构

### SQLite表结构
```sql
-- 书籍基础信息表
CREATE TABLE books (
    itemid TEXT PRIMARY KEY,
    shopid TEXT NOT NULL,
    isbn TEXT,
    title TEXT,
    author TEXT,
    publisher TEXT,
    -- 更多字段...
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 销售记录详情表  
CREATE TABLE sales_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_isbn TEXT NOT NULL,
    sale_date TEXT,
    price REAL,
    quality TEXT,
    -- 更多字段...
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- API销售数据表
CREATE TABLE api_sales_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_isbn TEXT NOT NULL,
    sale_date TEXT,
    -- 更多字段...
);
```

### 数据操作API
```python
from database import BookRepository, SalesRepository

# 书籍数据操作
book_repo = BookRepository()
await book_repo.save_books(books_data)
existing_ids = await book_repo.get_existing_itemids()

# 销售数据操作
sales_repo = SalesRepository()
await sales_repo.save_sales_data(sales_data)
sales = await sales_repo.get_sales_by_isbn(isbn)
```

## 开发计划

### 第一阶段：数据库迁移 ✅ 已完成
- ✅ 选择SQLite轻量级数据库
- ✅ 设计统一的数据模型  
- ✅ 重构CSV读写逻辑为数据库操作
- ✅ CSV自动迁移脚本

### 第二阶段：性能优化
- [ ] 并发爬取优化
- [ ] 缓存机制实现
- [ ] API响应优化
- [ ] 错误重试机制

### 第三阶段：功能扩展
- [ ] 用户管理系统
- [ ] 批量分析功能
- [ ] 数据导出功能
- [ ] 监控告警机制

## 注意事项

- **Chrome调试**：需要手动启动Chrome调试模式连接
- **爬取规范**：请遵守网站robots.txt和使用条款
- **频率控制**：建议添加适当请求间隔避免被限制
- **数据合规**：仅用于合法的数据分析用途

## 许可证

MIT License