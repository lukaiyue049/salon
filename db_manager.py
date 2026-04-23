import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
from datetime import datetime, date
import json

@st.cache_resource
def get_db_connection():
    """从 secrets 读取 DATABASE_URL 并建立连接"""
    database_url = st.secrets["supabase"]["database_url"]
    if not database_url:
        st.error("❌ 请在 secrets 中配置 supabase.database_url")
        st.stop()
    return psycopg2.connect(database_url)

def read_data(table_name: str) -> pd.DataFrame:
    conn = get_db_connection()
    try:
        # 注意：表名如果是小写，不需要双引号；但如果包含大写或特殊字符，需要加双引号
        query = f'SELECT * FROM "{table_name}"'
        df = pd.read_sql_query(query, conn)
        
        # 类型转换（保持与原代码兼容）
        if table_name == "members":
            df['phone'] = df['phone'].astype(str)
            df['balance'] = pd.to_numeric(df['balance'], errors='coerce').fillna(0.0)
            df['debt'] = pd.to_numeric(df['debt'], errors='coerce').fillna(0.0)
        elif table_name == "products":
            df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0)
            df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0.0)
        return df
    except Exception as e:
        st.error(f"❌ 读取表 {table_name} 失败: {e}")
        return create_empty_df(table_name)
    finally:
        conn.close()

def save_data(table_name: str, df: pd.DataFrame):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 清空表（根据你的业务逻辑可能需要 upsert，这里简化处理）
        cur.execute(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY;')
        records = df.to_dict(orient='records')
        for record in records:
            # 过滤掉 NaN 和 None
            clean_record = {k: v for k, v in record.items() if pd.notna(v)}
            columns = list(clean_record.keys())
            values = [clean_record[col] for col in columns]
            placeholders = ','.join(['%s'] * len(values))
            insert_sql = f'INSERT INTO "{table_name}" ({",".join(columns)}) VALUES ({placeholders})'
            cur.execute(insert_sql, values)
        conn.commit()
        st.toast(f"✅ {table_name} 同步成功")
    except Exception as e:
        st.error(f"❌ 保存 {table_name} 失败: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def create_empty_df(table_name: str) -> pd.DataFrame:
    cols = {
        "members": ["phone", "name", "balance", "skin_info", "debt", "note", "reg_date"],
        "products": ["prod_name", "category", "price", "stock", "unit", "type", "last_updated"],
        "records": ["member_phone", "date", "items", "total_amount", "status", "staff_name"],
        "salon_items": ["member_phone", "item_name", "total_qty", "used_qty", "status", "unit", "buy_date"],
        "staffs": ["name"],
        "sys_config": ["item", "value"],
        "activities": ["id", "name", "price", "packages", "is_open", "note"]
    }
    return pd.DataFrame(columns=cols.get(table_name, []))

def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        st.success("✅ Supabase 连接成功")
    except Exception as e:
        st.error(f"❌ Supabase 连接失败: {e}")
