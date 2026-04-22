import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
from functools import wraps

# ---------- 重试装饰器（处理 429 限流）----------
def retry_on_quota(max_retries=3, initial_delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                        if attempt < max_retries - 1:
                            st.warning(f"⚠️ API 配额超限，{delay}秒后重试... (第 {attempt+1} 次)")
                            time.sleep(delay)
                            delay *= 2
                        else:
                            st.error("❌ 云端读取失败：请求次数过多，请稍后手动点击侧边栏「同步最新数据」按钮。")
                            raise
                    else:
                        raise
            return None
        return wrapper
    return decorator

@st.cache_resource
def get_conn():
    return st.connection("gsheets", type=GSheetsConnection)

@retry_on_quota()
def read_data(table_name):
    conn = get_conn()
    try:
        df = conn.read(worksheet=table_name, ttl="0")
        if df is None or df.empty:
            return create_empty_df(table_name)
        
        # 数据清洗
        if table_name == "members":
            df['phone'] = df['phone'].astype(str).str.split('.').str[0].str.strip()
            df['balance'] = pd.to_numeric(df['balance'], errors='coerce').fillna(0.0)
            df['debt'] = pd.to_numeric(df['debt'], errors='coerce').fillna(0.0)
        elif table_name == "products":
            df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0)
            df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0.0)
        return df
    except Exception as e:
        st.error(f"读取云端表 {table_name} 失败: {e}")
        return create_empty_df(table_name)

def create_empty_df(table_name):
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

@retry_on_quota()
def save_data(table_name, df):
    conn = get_conn()
    try:
        write_df = df.copy()
        for col in write_df.columns:
            write_df[col] = write_df[col].apply(lambda x: "" if pd.isna(x) else str(x))
        conn.update(worksheet=table_name, data=write_df)
        # 注意：不清除全局缓存，留给用户手动刷新或等待自然过期
        st.toast(f"✅ 云端 {table_name} 更新成功")
    except Exception as e:
        st.error(f"❌ 同步云端失败: {e}")

def init_db():
    try:
        members_df = read_data("members")
        required_cols = ['phone', 'name', 'balance', 'skin_info', 'debt', 'note', 'reg_date']
        missing = [c for c in required_cols if c not in members_df.columns]
        if missing:
            st.error(f"🚨 警告：云端 'members' 表缺少列: {missing}。请在 Google 表格中手动插入这些列标题！")
    except:
        st.info("首次连接云端，请确保 Google Sheets 工作表名称已设置正确。")
