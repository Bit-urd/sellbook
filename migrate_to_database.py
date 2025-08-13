#!/usr/bin/env python3
"""
CSV到SQLite数据库迁移工具
将现有的CSV文件数据迁移到SQLite数据库中
"""
import asyncio
import os
import csv
from pathlib import Path
from datetime import datetime

from database import DatabaseManager, BookRepository, SalesRepository

class DatabaseMigrator:
    """数据库迁移工具"""
    
    def __init__(self, db_path: str = "sellbook.db"):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        self.book_repo = BookRepository(db_path)
        self.sales_repo = SalesRepository(db_path)
        
        self.migration_stats = {
            'books_migrated': 0,
            'api_sales_migrated': 0,
            'sales_stats_migrated': 0,
            'errors': []
        }
    
    async def migrate_all(self):
        """执行完整的数据迁移"""
        print("🚀 开始CSV到SQLite数据库迁移")
        print("="*50)
        
        # 1. 初始化数据库
        await self.init_database()
        
        # 2. 迁移各类数据
        await self.migrate_books_data()
        await self.migrate_api_sales_data()
        await self.migrate_sales_stats_data()
        
        # 3. 验证迁移结果
        await self.verify_migration()
        
        # 4. 打印迁移摘要
        self.print_migration_summary()
        
        print("\n✅ 数据迁移完成!")
    
    async def init_database(self):
        """初始化数据库结构"""
        print("📊 初始化数据库结构...")
        await self.db_manager.init_database()
        print("✅ 数据库结构初始化完成")
    
    async def migrate_books_data(self):
        """迁移书籍基础数据 (books_data.csv)"""
        csv_file = "books_data.csv"
        print(f"\n📚 迁移书籍数据: {csv_file}")
        
        if not Path(csv_file).exists():
            print(f"⚠️  文件不存在: {csv_file}")
            return
        
        try:
            books_data = []
            
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        book_data = {
                            'itemid': row.get('itemid', ''),
                            'shopid': row.get('shopid', ''),
                            'isbn': row.get('isbn', ''),
                            'title': row.get('title', ''),
                            'author': row.get('author', ''),
                            'publisher': row.get('publisher', ''),
                            'publish_year': row.get('publish_year', ''),
                            'quality': row.get('quality', ''),
                            'price': float(row.get('price', 0)) if row.get('price') else None,
                            'display_price': row.get('display_price', ''),
                            'book_url': row.get('book_url', ''),
                            'catnum': row.get('catnum', ''),
                            'userid': row.get('userid', ''),
                            'scraped_time': row.get('scraped_time', ''),
                            'scraped_shop_id': row.get('scraped_shop_id', ''),
                            'scraped_page': int(row.get('scraped_page', 0)) if row.get('scraped_page') else None,
                        }
                        books_data.append(book_data)
                        
                    except Exception as e:
                        error_msg = f"处理第{row_num}行数据时出错: {e}"
                        print(f"⚠️  {error_msg}")
                        self.migration_stats['errors'].append(error_msg)
                        continue
            
            # 批量保存到数据库
            if books_data:
                saved_count = await self.book_repo.save_books(books_data)
                self.migration_stats['books_migrated'] = saved_count
                print(f"✅ 成功迁移 {saved_count} 条书籍记录")
            else:
                print("📝 没有数据需要迁移")
                
        except Exception as e:
            error_msg = f"迁移书籍数据失败: {e}"
            print(f"❌ {error_msg}")
            self.migration_stats['errors'].append(error_msg)
    
    async def migrate_api_sales_data(self):
        """迁移API销售数据 (api_sales_data.csv)"""
        csv_file = "api_sales_data.csv"
        print(f"\n💰 迁移API销售数据: {csv_file}")
        
        if not Path(csv_file).exists():
            print(f"⚠️  文件不存在: {csv_file}")
            return
        
        try:
            sales_data = []
            
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        sale_data = {
                            'book_isbn': row.get('book_isbn', ''),
                            'sale_date': row.get('sale_date', ''),
                            'sold_time': row.get('sold_time', ''),
                            'price': float(row.get('price', 0)) if row.get('price') else None,
                            'quality': row.get('quality', ''),
                            'analyzed_at': row.get('analyzed_at', ''),
                        }
                        sales_data.append(sale_data)
                        
                    except Exception as e:
                        error_msg = f"处理第{row_num}行销售数据时出错: {e}"
                        print(f"⚠️  {error_msg}")
                        self.migration_stats['errors'].append(error_msg)
                        continue
            
            # 批量保存到数据库
            if sales_data:
                saved_count = await self.sales_repo.save_sales_data(sales_data)
                self.migration_stats['api_sales_migrated'] = saved_count
                print(f"✅ 成功迁移 {saved_count} 条API销售记录")
            else:
                print("📝 没有销售数据需要迁移")
                
        except Exception as e:
            error_msg = f"迁移API销售数据失败: {e}"
            print(f"❌ {error_msg}")
            self.migration_stats['errors'].append(error_msg)
    
    async def migrate_sales_stats_data(self):
        """迁移销售统计数据 (book_sales.csv)"""
        csv_file = "book_sales.csv"
        print(f"\n📈 迁移销售统计数据: {csv_file}")
        
        if not Path(csv_file).exists():
            print(f"⚠️  文件不存在: {csv_file}")
            return
        
        try:
            # 这里可以实现具体的销售统计数据迁移逻辑
            # 目前只是读取并统计
            stats_count = 0
            
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stats_count += 1
            
            self.migration_stats['sales_stats_migrated'] = stats_count
            print(f"✅ 统计了 {stats_count} 条销售统计记录")
            
        except Exception as e:
            error_msg = f"迁移销售统计数据失败: {e}"
            print(f"❌ {error_msg}")
            self.migration_stats['errors'].append(error_msg)
    
    async def verify_migration(self):
        """验证迁移结果"""
        print(f"\n🔍 验证迁移结果...")
        
        try:
            # 获取已存在的itemid数量来验证书籍数据
            existing_itemids = await self.book_repo.get_existing_itemids()
            db_books_count = len(existing_itemids)
            
            print(f"📚 数据库中的书籍记录数: {db_books_count}")
            
            if db_books_count > 0:
                print("✅ 书籍数据迁移验证通过")
            else:
                print("⚠️  数据库中没有书籍数据")
            
        except Exception as e:
            error_msg = f"验证迁移结果失败: {e}"
            print(f"❌ {error_msg}")
            self.migration_stats['errors'].append(error_msg)
    
    def print_migration_summary(self):
        """打印迁移摘要"""
        print("\n" + "="*50)
        print("📊 迁移结果摘要")
        print("="*50)
        
        print(f"📚 书籍记录迁移: {self.migration_stats['books_migrated']} 条")
        print(f"💰 API销售记录迁移: {self.migration_stats['api_sales_migrated']} 条")
        print(f"📈 销售统计记录: {self.migration_stats['sales_stats_migrated']} 条")
        
        if self.migration_stats['errors']:
            print(f"\n⚠️  迁移过程中的错误 ({len(self.migration_stats['errors'])} 个):")
            for i, error in enumerate(self.migration_stats['errors'], 1):
                print(f"  {i}. {error}")
        else:
            print(f"\n✅ 迁移过程无错误")
        
        print("="*50)
    
    async def backup_csv_files(self):
        """备份原始CSV文件"""
        print("\n💾 备份原始CSV文件...")
        
        csv_files = ["books_data.csv", "api_sales_data.csv", "book_sales.csv"]
        backup_dir = Path("csv_backup")
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for csv_file in csv_files:
            if Path(csv_file).exists():
                backup_file = backup_dir / f"{Path(csv_file).stem}_{timestamp}.csv"
                try:
                    import shutil
                    shutil.copy2(csv_file, backup_file)
                    print(f"  ✅ 已备份: {csv_file} -> {backup_file}")
                except Exception as e:
                    print(f"  ❌ 备份失败: {csv_file} - {e}")

class DatabaseManager:
    """数据库管理工具"""
    
    def __init__(self, db_path: str = "sellbook.db"):
        self.db_path = db_path
    
    async def show_database_info(self):
        """显示数据库信息"""
        print(f"📊 数据库信息: {self.db_path}")
        print("="*40)
        
        if not Path(self.db_path).exists():
            print("❌ 数据库文件不存在")
            return
        
        try:
            import aiosqlite
            
            async with aiosqlite.connect(self.db_path) as db:
                # 获取所有表信息
                cursor = await db.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = await cursor.fetchall()
                
                print(f"📋 数据表数量: {len(tables)}")
                
                for table_name, in tables:
                    cursor = await db.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = await cursor.fetchone()
                    print(f"  📊 {table_name}: {count[0]} 条记录")
                
                # 数据库文件大小
                db_size = Path(self.db_path).stat().st_size
                print(f"💾 数据库文件大小: {db_size / 1024:.1f} KB")
                
        except Exception as e:
            print(f"❌ 获取数据库信息失败: {e}")
        
        print("="*40)

async def main():
    """主函数"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "info":
        # 显示数据库信息
        db_manager = DatabaseManager()
        await db_manager.show_database_info()
        return
    
    # 执行数据迁移
    migrator = DatabaseMigrator()
    
    # 可选：备份CSV文件
    await migrator.backup_csv_files()
    
    # 执行迁移
    await migrator.migrate_all()

if __name__ == "__main__":
    print("📦 CSV到SQLite数据库迁移工具")
    print("使用方法:")
    print("  python migrate_to_database.py        # 执行数据迁移")
    print("  python migrate_to_database.py info   # 查看数据库信息")
    print()
    
    asyncio.run(main())