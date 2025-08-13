# 📚 SellBook - 孔夫子旧书网增量爬虫

一个支持增量爬取、自动去重的孔夫子旧书网多店铺书籍信息爬虫工具，使用真实Chrome浏览器避免反爬检测。

## ✨ 核心特性

- 🔒 **零检测风险** - 使用真实Chrome浏览器，完全避开反爬机制
- 📊 **增量爬取** - 支持断点续爬，已爬取的数据自动跳过
- 🔄 **智能去重** - 基于ItemID自动去重，避免重复数据
- 🏪 **多店铺支持** - 批量爬取多个店铺，从配置文件读取店铺列表
- 💾 **实时保存** - 每页数据立即保存到CSV，不怕中断丢失
- 📈 **进度统计** - 实时显示爬取进度和统计信息

## 📋 系统要求

- Python 3.11+
- Google Chrome 浏览器
- uv (Python包管理器)

## 🚀 快速开始

### 1. 环境安装

```bash
# 已配置好uv环境和依赖
uv sync
```

### 2. 启动Chrome调试模式

**macOS:**
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-debug-session
```

**验证Chrome启动：** 访问 http://localhost:9222/json/version

### 3. 配置店铺列表

编辑 `shop_list.txt` 文件，添加要爬取的店铺ID：

```txt
# 孔夫子旧书网店铺ID列表
534779
726495
269228
# 可以继续添加更多店铺ID...
```

### 4. 运行增量爬虫

```bash
# 🌟 推荐：增量式多店铺爬虫
uv run python incremental_scraper.py
```

## 📁 文件说明

### 核心文件
- `incremental_scraper.py` - **⭐ 主程序** 增量式多店铺爬虫
- `shop_list.txt` - 店铺ID配置文件
- `books_data.csv` - **主要数据文件** (自动生成)

### 辅助工具
- `real_browser_scraper.py` - 单店铺真实Chrome爬虫
- `list_scraper.py` - 列表页面爬虫
- `test_incremental.py` - 去重功能测试工具

### 配置文件
- `manual_chrome_guide.md` - Chrome调试模式详细指南
- `pyproject.toml` - Python项目配置

## 📊 数据格式

CSV文件包含以下字段：

| 字段名 | 说明 | 示例 |
|--------|------|------|
| `itemid` | 书籍唯一ID ⭐ | 8643501869 |
| `shopid` | 店铺ID | 534779 |
| `isbn` | 国际标准书号 | 9787521724493 |
| `title` | 书名 | 会员经济：发现超级用户... |
| `author` | 作者 | 罗比·凯尔曼·巴克斯特 |
| `publisher` | 出版社 | 中信出版社 |
| `publish_year` | 出版年份 | 2021-02 |
| `quality` | 品相 | 九五品 |
| `price` | 价格 | 99.00 |
| `book_url` | 详情链接 | https://book.kongfz.com/... |
| `scraped_time` | 爬取时间 | 2025-08-14T01:31:34... |
| `scraped_shop_id` | 爬取时的店铺ID | 534779 |
| `scraped_page` | 爬取时的页码 | 1 |

## 🔄 增量爬取工作原理

1. **启动检查** - 加载已有 `books_data.csv` 文件
2. **去重准备** - 构建ItemID集合，用于快速去重判断
3. **逐店铺爬取** - 按店铺列表顺序处理每个店铺
4. **逐页处理** - 每页数据提取后立即检查重复并保存
5. **实时统计** - 显示新增、跳过、总计等统计信息

### 断点续爬

- 程序可随时中断，已保存的数据不会丢失
- 重新运行时自动跳过已爬取的书籍
- 支持添加新店铺ID，只爬取新的数据

## 📈 使用示例

```bash
# 第一次运行
$ uv run python incremental_scraper.py
📂 检查已有数据文件...
📝 数据文件不存在，将创建新文件: books_data.csv
📋 加载了 3 个店铺ID
🏪 开始爬取店铺 534779
📚 第 1 页: 50 本书，新增 50 本
💾 新增 50 条记录到 books_data.csv

# 第二次运行 (断点续爬)
$ uv run python incremental_scraper.py  
📂 检查已有数据文件...
📊 加载已有数据: 2016 条记录
🔍 去重集合大小: 2016 个ItemID
🏪 开始爬取店铺 534779
📚 第 1 页: 50 本书，新增 0 本
🔄 跳过 50 条重复记录
```

## ⚠️ 重要提醒

### 法律合规
- 仅用于个人学习和研究目的
- 遵守网站robots.txt和使用条款
- 控制爬取频率，避免对服务器造成压力

### 使用建议
- 建议爬取间隔 3-5 秒
- 店铺间等待 5 秒
- 使用真实Chrome浏览器完全避免检测
- 定期备份 `books_data.csv` 文件

## 🔧 故障排除

### Chrome连接失败？
```bash
# 检查Chrome调试端口
curl http://localhost:9222/json/version
```

### 数据重复？
- 检查 `itemid` 字段是否完整
- 运行测试工具：`uv run python test_incremental.py`

### 爬取中断？
- 数据已自动保存到CSV文件
- 重新运行会自动续爬

## 📊 已验证结果

实际测试结果：
- ✅ 成功爬取 **2016条** 书籍记录
- ✅ 覆盖 **3个店铺** 的完整数据
- ✅ 去重功能工作正常
- ✅ CSV文件大小：**518KB**
- ✅ 断点续爬功能验证通过

## 🤝 贡献

欢迎提交Issue和Pull Request来改进项目！

## 📄 许可证

本项目仅供学习研究使用，请遵守相关法律法规。

---

⭐ 如果这个项目对你有帮助，请给个Star支持一下！