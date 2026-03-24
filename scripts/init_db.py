#!/usr/bin/env python3
"""
数据库初始化脚本 - 首次运行时创建数据库表

用法:
    python scripts/init_db.py
"""
import sys
from pathlib import Path

# 添加 backend 到路径
backend_dir = Path(__file__).parent.parent / 'banana-slides' / 'backend'
sys.path.insert(0, str(backend_dir))

from models import db
from app import create_app

def init_db():
    """初始化数据库"""
    app = create_app()
    
    with app.app_context():
        # 创建所有表
        db.create_all()
        print("[OK] 数据库表创建成功")
        
        # 列出创建的表
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"[INFO] 已创建的表：{', '.join(tables)}")

if __name__ == '__main__':
    init_db()
