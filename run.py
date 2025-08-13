#!/usr/bin/env python3
"""
SellBook项目统一启动脚本
提供数据库版本和CSV版本的模块选择
"""
import asyncio
import sys
import os
from pathlib import Path

def print_banner():
    """打印项目横幅"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                     📚 SellBook 项目                         ║
║                孔夫子旧书网销售数据分析系统                    ║
║                                                              ║
║  🔄 数据库版本 (推荐) - 使用SQLite替代CSV                     ║
║  📁 CSV版本 (兼容) - 保持原有CSV文件格式                      ║
╚══════════════════════════════════════════════════════════════╝
    """)

def print_main_menu():
    """打印主菜单"""
    print("\n🚀 请选择要运行的模块:")
    print()
    print("=" * 60)
    print("📊 数据库版本 (推荐)")
    print("=" * 60)
    print("1.  🌐 启动FastAPI分析服务 (数据库版)")
    print("2.  🏪 运行店铺书籍爬虫 (数据库版)")
    print("3.  📈 运行销售记录分析器 (数据库版)")
    print("4.  🔄 CSV数据迁移到数据库")
    print("5.  📊 查看数据库信息")
    print()
    print("=" * 60)
    print("📁 CSV版本 (兼容)")
    print("=" * 60)
    print("6.  🌐 启动FastAPI分析服务 (CSV版)")
    print("7.  🏪 运行店铺书籍爬虫 (CSV版)")
    print("8.  📈 运行销售记录分析器 (CSV版)")
    print()
    print("=" * 60)
    print("🛠️ 工具和帮助")
    print("=" * 60)
    print("9.  📖 查看项目帮助文档")
    print("10. 🔧 环境检查")
    print("0.  ❌ 退出")
    print()

async def run_fastapi_v2():
    """启动数据库版FastAPI服务"""
    print("🚀 启动FastAPI分析服务 (数据库版)...")
    
    try:
        from book_analysis_api_v2 import app
        import uvicorn
        
        print("📖 API文档地址: http://localhost:8000/docs")
        print("🔍 健康检查: http://localhost:8000/health")
        print("📊 数据迁移: http://localhost:8000/migrate")
        print("🌐 主页面: http://localhost:8000")
        print("\n按 Ctrl+C 停止服务")
        
        uvicorn.run(
            "book_analysis_api_v2:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
        print("请确保已安装所有依赖: uv sync")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

async def run_scraper_v2():
    """运行数据库版爬虫"""
    print("🏪 启动增量式店铺爬虫 (数据库版)...")
    
    try:
        from incremental_scraper_v2 import IncrementalScraperV2
        scraper = IncrementalScraperV2()
        await scraper.run()
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
    except Exception as e:
        print(f"❌ 运行失败: {e}")

async def run_analyzer_v2():
    """运行数据库版分析器"""
    print("📈 启动销售记录分析器 (数据库版)...")
    
    # 询问是否分析特定ISBN
    isbn = input("请输入要分析的ISBN (留空则分析数据库中的书籍): ").strip()
    
    try:
        if isbn:
            from sales_analyzer_v2 import analyze_single_isbn
            await analyze_single_isbn(isbn)
        else:
            from sales_analyzer_v2 import SalesAnalyzerV2
            analyzer = SalesAnalyzerV2()
            await analyzer.run(book_limit=5)
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
    except Exception as e:
        print(f"❌ 运行失败: {e}")

async def run_migration():
    """执行数据迁移"""
    print("🔄 开始CSV数据迁移...")
    
    try:
        from migrate_to_database import DatabaseMigrator
        migrator = DatabaseMigrator()
        await migrator.migrate_all()
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
    except Exception as e:
        print(f"❌ 迁移失败: {e}")

async def show_database_info():
    """显示数据库信息"""
    print("📊 查看数据库信息...")
    
    try:
        from migrate_to_database import DatabaseManager
        db_manager = DatabaseManager()
        await db_manager.show_database_info()
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
    except Exception as e:
        print(f"❌ 查看失败: {e}")

def run_fastapi_v1():
    """启动CSV版FastAPI服务"""
    print("🚀 启动FastAPI分析服务 (CSV版)...")
    
    try:
        import uvicorn
        print("📖 API文档地址: http://localhost:8000/docs")
        print("🔍 健康检查: http://localhost:8000/health")
        print("🌐 主页面: http://localhost:8000")
        print("\n按 Ctrl+C 停止服务")
        
        uvicorn.run(
            "book_analysis_api:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

async def run_scraper_v1():
    """运行CSV版爬虫"""
    print("🏪 启动增量式店铺爬虫 (CSV版)...")
    
    try:
        from incremental_scraper import IncrementalScraper
        scraper = IncrementalScraper()
        await scraper.run()
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
    except Exception as e:
        print(f"❌ 运行失败: {e}")

async def run_analyzer_v1():
    """运行CSV版分析器"""
    print("📈 启动销售记录分析器 (CSV版)...")
    
    try:
        from sales_analyzer import SalesAnalyzer
        analyzer = SalesAnalyzer()
        await analyzer.run(book_limit=5)
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
    except Exception as e:
        print(f"❌ 运行失败: {e}")

def show_help():
    """显示帮助文档"""
    print("""
📖 SellBook项目帮助文档
=======================

🔧 环境准备:
1. 安装依赖: uv sync
2. 启动Chrome调试模式:
   macOS: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug
3. 验证Chrome连接: curl http://localhost:9222/json/version

📊 模块说明:
- 🌐 FastAPI服务: 提供Web界面和API接口，分析书籍销售数据
- 🏪 店铺爬虫: 批量爬取孔夫子网店铺的书籍基础信息
- 📈 销售分析器: 分析具体书籍的销售记录和价格趋势

💡 使用建议:
1. 首次使用建议先运行数据迁移 (选项4)
2. 然后使用数据库版本的模块 (选项1-3)
3. CSV版本保持向后兼容，但建议升级到数据库版本

🔄 数据流:
shop_list.txt → 店铺爬虫 → SQLite数据库 → 销售分析器 → FastAPI服务

⚠️ 注意事项:
- 确保Chrome调试模式正常运行
- 遵守网站使用条款，控制爬取频率
- 定期备份数据库文件
    """)

def check_environment():
    """检查环境依赖"""
    print("🔧 环境检查")
    print("=" * 40)
    
    # 检查Python版本
    python_version = sys.version_info
    if python_version >= (3, 11):
        print(f"✅ Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
    else:
        print(f"❌ Python版本过低: {python_version.major}.{python_version.minor}.{python_version.micro} (需要3.11+)")
    
    # 检查关键文件
    required_files = [
        "shop_list.txt",
        "database.py",
        "book_analysis_api_v2.py",
        "incremental_scraper_v2.py",
        "sales_analyzer_v2.py"
    ]
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} (缺失)")
    
    # 检查关键依赖
    required_modules = [
        "fastapi",
        "playwright",
        "aiosqlite",
        "aiohttp",
        "pydantic"
    ]
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError:
            print(f"❌ {module} (未安装)")
    
    # 检查Chrome调试端口
    try:
        import aiohttp
        async def check_chrome():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("http://localhost:9222/json/version", timeout=aiohttp.ClientTimeout(total=3)) as response:
                        if response.status == 200:
                            print("✅ Chrome调试端口连接正常")
                        else:
                            print("❌ Chrome调试端口响应异常")
            except:
                print("❌ Chrome调试端口无法连接")
        
        asyncio.run(check_chrome())
    except ImportError:
        print("❌ aiohttp模块未安装，无法检查Chrome连接")
    
    print("=" * 40)

async def main():
    """主函数"""
    print_banner()
    
    while True:
        try:
            print_main_menu()
            choice = input("请选择操作 (0-10): ").strip()
            
            if choice == "0":
                print("👋 感谢使用SellBook！")
                break
            elif choice == "1":
                await run_fastapi_v2()
            elif choice == "2":
                await run_scraper_v2()
            elif choice == "3":
                await run_analyzer_v2()
            elif choice == "4":
                await run_migration()
            elif choice == "5":
                await show_database_info()
            elif choice == "6":
                run_fastapi_v1()
            elif choice == "7":
                await run_scraper_v1()
            elif choice == "8":
                await run_analyzer_v1()
            elif choice == "9":
                show_help()
            elif choice == "10":
                check_environment()
            else:
                print("❌ 无效选择，请输入0-10之间的数字")
            
            if choice != "0":
                input("\n按回车键返回主菜单...")
                
        except KeyboardInterrupt:
            print("\n\n👋 用户中断，退出程序")
            break
        except Exception as e:
            print(f"\n❌ 运行出错: {e}")
            input("按回车键返回主菜单...")

if __name__ == "__main__":
    asyncio.run(main())