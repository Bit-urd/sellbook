# 卖书网站价差数据分析系统

## 系统简介

专门分析孔夫子旧书网和多抓鱼两个平台书籍价差的数据系统，通过爬取对比发现套利机会。

## 快速开始

### 1. 安装依赖
```bash
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

- **主页**: http://127.0.0.1:8000/ - 数据展示和分析
- **爬虫控制**: http://127.0.0.1:8000/crawler-admin - 管理爬虫任务（隐藏入口）
- **API文档**: http://127.0.0.1:8000/docs

## 核心功能

### 数据展示（主页）
- 销售统计（1/3/7/30天）
- 价格分析（去异常值的平均值/中位数/众数）
- 热销排行榜
- 利润商品排行（价差分析）
- 分类统计
- 店铺业绩

### 爬虫控制（管理页）
- 批量添加店铺
- 更新店铺书籍数据
- 更新多抓鱼价格
- 查看任务状态
- 手动触发爬虫

## 项目结构

```
sellbook/
├── src/
│   ├── models/          # 数据模型
│   ├── services/        # 业务服务
│   ├── routes/          # API路由
│   ├── static/          # 前端文件
│   └── main.py          # 应用入口
├── data/
│   └── sellbook.db      # SQLite数据库
├── app.py               # 启动脚本
├── migrate_data.py      # 数据迁移
└── requirements.txt     # 依赖包
```

## 技术栈

- 后端：FastAPI + SQLite
- 爬虫：Playwright + Aiohttp  
- 前端：原生HTML/CSS/JavaScript

## 注意事项

1. 爬虫需要Chrome浏览器调试模式
2. 所有爬虫手动触发，无定时任务
3. 爬虫控制页面建议仅管理员使用
4. 定期备份`data/sellbook.db`数据库