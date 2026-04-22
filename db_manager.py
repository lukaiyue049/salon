import sqlite3
import pandas as pd


def get_conn():
    """获取数据库连接"""
    conn = sqlite3.connect('salon_data.db', check_same_thread=False)
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_conn()
    cursor = conn.cursor()

    # 1. 会员表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            phone TEXT PRIMARY KEY,
            name TEXT,
            balance REAL DEFAULT 0,
            skin_info TEXT,
            debt REAL DEFAULT 0
        )
    ''')

    # 2. 项目库存表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            prod_name TEXT PRIMARY KEY,
            category TEXT,
            price REAL,
            stock INTEGER DEFAULT 0,
            unit TEXT DEFAULT '个',
            type TEXT DEFAULT '实物产品'
        )
    ''')

    # 3. 会员持有资产/次卡表（包含新字段）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS salon_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_phone TEXT,
            item_name TEXT,
            total_qty INTEGER,
            used_qty INTEGER DEFAULT 0,
            status TEXT DEFAULT '使用中',
            unit TEXT DEFAULT '次',
            buy_date TEXT,
            source TEXT DEFAULT 'normal',
            activity_name TEXT,
            usage_type TEXT DEFAULT 'bought'
        )
    ''')

    # 4. 活动礼包表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            packages TEXT, 
            price REAL,
            is_open INTEGER DEFAULT 1,
            note TEXT
        )
    ''')

    # 5. 流水记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_phone TEXT,
            date TEXT,
            items TEXT,
            total_amount REAL,
            status TEXT,
            staff_name TEXT
        )
    ''')

    # 6. 系统配置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sys_config (
            item TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO sys_config VALUES ('debt_limit', '500')")

    # 7. 员工表
    cursor.execute('CREATE TABLE IF NOT EXISTS staffs (name TEXT PRIMARY KEY)')

    conn.commit()

    # 升级旧表结构
    upgrade_db(conn)
    conn.close()


def upgrade_db(conn):
    """检测并补全缺少的列，支持功能动态升级"""
    cursor = conn.cursor()
    
    # members 表
    cursor.execute("PRAGMA table_info(members)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'note' not in columns:
        cursor.execute("ALTER TABLE members ADD COLUMN note TEXT")
    if 'reg_date' not in columns:
        cursor.execute("ALTER TABLE members ADD COLUMN reg_date TEXT")

    # products 表
    cursor.execute("PRAGMA table_info(products)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'unit' not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN unit TEXT DEFAULT '个'")
    if 'type' not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN type TEXT DEFAULT '实物产品'")
    if 'last_updated' not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN last_updated TEXT")
        cursor.execute("UPDATE products SET last_updated = datetime('now','localtime')")

    # salon_items 表（重点）
    cursor.execute("PRAGMA table_info(salon_items)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'unit' not in columns:
        cursor.execute("ALTER TABLE salon_items ADD COLUMN unit TEXT DEFAULT '次'")
    if 'buy_date' not in columns:
        cursor.execute("ALTER TABLE salon_items ADD COLUMN buy_date TEXT")
    if 'source' not in columns:
        cursor.execute("ALTER TABLE salon_items ADD COLUMN source TEXT DEFAULT 'normal'")
    if 'activity_name' not in columns:
        cursor.execute("ALTER TABLE salon_items ADD COLUMN activity_name TEXT")
    if 'usage_type' not in columns:
        cursor.execute("ALTER TABLE salon_items ADD COLUMN usage_type TEXT DEFAULT 'bought'")

    # activities 表
    cursor.execute("PRAGMA table_info(activities)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'note' not in columns:
        cursor.execute("ALTER TABLE activities ADD COLUMN note TEXT")

    conn.commit()


if __name__ == "__main__":
    init_db()
    print("✅ 数据库初始化/升级完成！")
