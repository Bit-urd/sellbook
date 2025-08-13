#!/usr/bin/env python3
"""
数据迁移脚本 - 从旧的CSV文件迁移到新的SQLite数据库
"""
import csv
import json
from pathlib import Path
from datetime import datetime
import logging

from src.models.database import db
from src.models.models import Shop, Book, BookInventory, SalesRecord
from src.models.repositories import (
    ShopRepository, BookRepository, BookInventoryRepository, SalesRepository
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_books_from_csv():
    """从books_data.csv迁移书籍数据"""
    csv_file = "books_data.csv"
    if not Path(csv_file).exists():
        logger.warning(f"文件不存在: {csv_file}")
        return
    
    book_repo = BookRepository()
    inventory_repo = BookInventoryRepository()
    shop_repo = ShopRepository()
    
    # 先创建默认店铺
    default_shops = {}
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 创建或获取店铺
            shop_id = row.get('shopid', '') or row.get('scraped_shop_id', '')
            if shop_id and shop_id not in default_shops:
                shop = Shop(
                    shop_id=shop_id,
                    shop_name=f"店铺_{shop_id}",
                    platform="kongfuzi"
                )
                try:
                    shop_db_id = shop_repo.create(shop)
                    default_shops[shop_id] = shop_db_id
                    logger.info(f"创建店铺: {shop_id}")
                except:
                    existing = shop_repo.get_by_id(shop_id)
                    if existing:
                        default_shops[shop_id] = existing['id']
            
            # 创建书籍
            book = Book(
                title=row.get('title', ''),
                isbn=row.get('isbn', ''),
                author=row.get('author', ''),
                publisher=row.get('publisher', ''),
                publish_date=row.get('publish_year', '')
            )
            
            book_id = book_repo.create_or_update(book)
            
            # 创建库存记录
            if shop_id in default_shops:
                try:
                    price = float(row.get('price', 0)) if row.get('price') else None
                except:
                    price = None
                
                inventory = BookInventory(
                    book_id=book_id,
                    shop_id=default_shops[shop_id],
                    kongfuzi_price=price,
                    kongfuzi_condition=row.get('quality', ''),
                    kongfuzi_book_url=row.get('book_url', ''),
                    kongfuzi_item_id=row.get('itemid', '')
                )
                inventory_repo.upsert(inventory)
    
    logger.info(f"书籍数据迁移完成，创建了 {len(default_shops)} 个店铺")

def migrate_sales_from_csv():
    """从api_sales_data.csv迁移销售数据"""
    csv_file = "api_sales_data.csv"
    if not Path(csv_file).exists():
        logger.warning(f"文件不存在: {csv_file}")
        return
    
    book_repo = BookRepository()
    sales_repo = SalesRepository()
    
    sales_records = []
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 根据ISBN查找书籍
            isbn = row.get('book_isbn', '')
            if not isbn:
                continue
            
            book = book_repo.get_by_isbn(isbn)
            if not book:
                # 创建新书籍
                new_book = Book(
                    title=f"ISBN_{isbn}",
                    isbn=isbn
                )
                book_id = book_repo.create_or_update(new_book)
            else:
                book_id = book['id']
            
            # 创建销售记录
            try:
                sale_date = datetime.strptime(row.get('sale_date', ''), '%Y-%m-%d')
            except:
                sale_date = datetime.now()
            
            try:
                price = float(row.get('price', 0))
            except:
                price = 0
            
            sale = SalesRecord(
                book_id=book_id,
                shop_id=1,  # 默认店铺ID
                sale_price=price,
                sale_date=sale_date,
                book_condition=row.get('quality', '')
            )
            sales_records.append(sale)
    
    if sales_records:
        count = sales_repo.batch_create(sales_records)
        logger.info(f"迁移了 {count} 条销售记录")

def migrate_shop_list():
    """从shop_list.txt迁移店铺列表"""
    shop_file = "shop_list.txt"
    if not Path(shop_file).exists():
        logger.warning(f"文件不存在: {shop_file}")
        return
    
    shop_repo = ShopRepository()
    shops = []
    
    with open(shop_file, 'r', encoding='utf-8') as f:
        for line in f:
            shop_id = line.strip()
            if shop_id:
                shop = Shop(
                    shop_id=shop_id,
                    shop_name=f"店铺_{shop_id}",
                    platform="kongfuzi"
                )
                shops.append(shop)
    
    if shops:
        count = shop_repo.batch_create(shops)
        logger.info(f"从shop_list.txt迁移了 {count} 个店铺")

def main():
    """执行数据迁移"""
    logger.info("开始数据迁移...")
    
    # 初始化数据库
    logger.info("数据库已初始化")
    
    # 迁移店铺列表
    migrate_shop_list()
    
    # 迁移书籍数据
    migrate_books_from_csv()
    
    # 迁移销售数据
    migrate_sales_from_csv()
    
    logger.info("数据迁移完成！")

if __name__ == "__main__":
    main()