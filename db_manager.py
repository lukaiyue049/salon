import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- 核心连接函数 ---
def get_conn():
    """获取 Google Sheets 连接"""
    # ttl=0 极其重要：确保收银时 iPad 看到的是云端最新数据，不使用本地缓存
    return st.connection("gsheets", type=GSheetsConnection)

# db_manager.py

def read_data(table_name):
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet=table_name, ttl="0")
        if df is None or df.empty:
            # 如果读到的是空表，手动创建一个带正确标题的空 DataFrame
            return create_empty_df(table_name)
        return df
    except Exception:
        return create_empty_df(table_name)

def create_empty_df(table_name):
    # 为各个表定义标准的列名
    cols = {
        "members": ["phone", "name", "balance", "skin_info", "debt", "note", "reg_date"],
        "products": ["prod_name", "category", "price", "stock", "unit", "type", "last_updated"],
        "records": ["member_phone", "date", "items", "total_amount", "status", "staff_name"],
        "salon_items": ["member_phone", "item_name", "total_qty", "used_qty", "status", "unit", "buy_date"]
    }
    return pd.DataFrame(columns=cols.get(table_name, []))
def save_data(table_name, df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        # 清洗数据，确保没有不支持的格式
        df = df.astype(str) 
        conn.update(worksheet=table_name, data=df)
        st.toast(f"云端 {table_name} 同步成功")
    except Exception as e:
        st.error(f"同步云端失败: {e}")
        
# --- 兼容旧代码的逻辑 ---
def init_db():
    """
    云端模式下，无需执行 CREATE TABLE。
    它的作用变为：检查表格标题行是否齐全（尤其是你之前报错过的 note 字段）。
    """
    # 检查会员表关键列
    members_df = read_data("members")
    required_cols = ['phone', 'name', 'balance', 'skin_info', 'debt', 'note', 'reg_date']
    
    missing = [c for c in required_cols if c not in members_df.columns]
    if missing:
        st.warning(f"云端表格缺少以下列，请手动在 Google 表格首行补齐: {missing}")
    

# --- 升级/维护逻辑 ---
def upgrade_db(conn=None):
    """
    在云端模式中，不再通过代码 ALTER TABLE。
    直接建议你在 Google Sheets 网页端手动插入列，这比写代码稳妥得多。
    """
    pass 

# 如果直接运行此脚本，测试连接
if __name__ == "__main__":
    init_db()
