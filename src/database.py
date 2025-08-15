"""
数据库配置
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 创建基础模型类
Base = declarative_base()

# 数据库引擎和会话（用于测试）
engine = None
SessionLocal = None

def get_database_url():
    """获取数据库URL"""
    return "sqlite:///./sellbook.db"

def init_database():
    """初始化数据库"""
    global engine, SessionLocal
    database_url = get_database_url()
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)