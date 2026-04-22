import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- 1. 核心连接池优化 ---
@st.cache_resource
def get_conn():
    """使用 cache_resource 确保整个应用生命周期只建立一个连接池"""
    return st.connection("gsheets", type=GSheetsConnection)

# --- 2. 增强型读取逻辑 ---
def read_data(table_name):
    conn = get_conn()
    try:
        # ttl="0" 确保读到的是最新，但我们配合 main.py 的外层缓存
        df = conn.read(worksheet=table_name, ttl="0")
        
        if df is None or df.empty:
            return create_empty_df(table_name)
        
        # --- 数据强制清洗 (解决常见 Bug) ---
        if table_name == "members":
            # 彻底解决手机号 138...0.0 问题
            df['phone'] = df['phone'].astype(str).str.split('.').str[0].str.strip()
            # 确保数值列是数字，不是字符串
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
        "activities": ["name", "price", "packages", "is_open"]
    }
    return pd.DataFrame(columns=cols.get(table_name, []))

# --- 3. 增强型保存逻辑 ---
def save_data(table_name, df):
    conn = get_conn()
    try:
        # 在保存前，确保所有数据转为字符串，避免 Google Sheets 无法识别
        # 但要注意保留空字符串，而不是转成 "nan"
        write_df = df.copy()
        for col in write_df.columns:
            write_df[col] = write_df[col].apply(lambda x: "" if pd.isna(x) else str(x))
            
        conn.update(worksheet=table_name, data=write_df)
        
        # --- 核心：保存成功后，立即清理 main.py 中的缓存 ---
        # 这样下一次 load_all_data_once 就会从云端抓取最新的
        st.cache_data.clear() 
        
        st.toast(f"✅ 云端 {table_name} 更新成功")
    except Exception as e:
        st.error(f"❌ 同步云端失败: {e}")

# --- 4. 自动化维护 ---
def init_db():
    """检查表结构，如果缺少关键列（如 note）则报警"""
    try:
        members_df = read_data("members")
        required_cols = ['phone', 'name', 'balance', 'skin_info', 'debt', 'note', 'reg_date']
        missing = [c for c in required_cols if c not in members_df.columns]
        if missing:
            st.error(f"🚨 警告：云端 'members' 表缺少列: {missing}。请在 Google 表格中手动插入这些列标题！")
    except:
        st.info("首次连接云端，请确保 Google Sheets 工作表名称已设置正确。")

def upgrade_db(conn=None):
    pass 

if __name__ == "__main__":
    init_db()
