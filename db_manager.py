import streamlit as st
import psycopg2
import pandas as pd

@st.cache_resource
def get_db_connection():
    database_url = st.secrets["database_url"]
    return psycopg2.connect(database_url)

def read_data(table_name: str) -> pd.DataFrame:
    conn = get_db_connection()
    try:
        query = f'SELECT * FROM "{table_name}"'
        df = pd.read_sql_query(query, conn)
        if table_name == "members":
            df['phone'] = df['phone'].astype(str)
            df['balance'] = pd.to_numeric(df['balance'], errors='coerce').fillna(0.0)
            df['debt'] = pd.to_numeric(df['debt'], errors='coerce').fillna(0.0)
        elif table_name == "products":
            df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0)
            df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0.0)
        return df
    except Exception as e:
        st.error(f"读取表 {table_name} 失败: {e}")
        return create_empty_df(table_name)
    finally:
        conn.close()

def save_data(table_name: str, df: pd.DataFrame):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY;')
        records = df.to_dict(orient='records')
        for record in records:
            clean = {k: v for k, v in record.items() if pd.notna(v)}
            cols = list(clean.keys())
            vals = [clean[c] for c in cols]
            placeholders = ','.join(['%s'] * len(vals))
            sql = f'INSERT INTO "{table_name}" ({",".join(cols)}) VALUES ({placeholders})'
            cur.execute(sql, vals)
        conn.commit()
        st.toast(f"✅ {table_name} 同步成功")
    except Exception as e:
        st.error(f"保存 {table_name} 失败: {e}")
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
        conn.cursor().execute("SELECT 1")
        conn.close()
        st.success("✅ 数据库连接成功")
    except Exception as e:
        st.error(f"❌ 数据库连接失败: {e}")
