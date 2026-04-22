import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- 核心连接函数 ---
def get_conn():
    """获取 Google Sheets 连接"""
    # ttl=0 极其重要：确保收银时 iPad 看到的是云端最新数据，不使用本地缓存
    return st.connection("gsheets", type=GSheetsConnection)

def read_data(worksheet_name):
    """读取指定标签页的数据"""
    conn = get_conn()
    try:
        # 清除缓存强制读取
        st.cache_data.clear() 
        return conn.read(worksheet=worksheet_name, ttl=0)
    except Exception as e:
        st.error(f"读取表格 {worksheet_name} 失败，请检查名称是否一致。")
        return pd.DataFrame()

def save_data(worksheet_name, df):
    """将整个 DataFrame 写回 Google Sheets"""
    conn = get_conn()
    # 这一步会直接覆盖对应的 Worksheet
    conn.update(worksheet=worksheet_name, data=df)

# --- 兼容旧代码的逻辑 ---
def init_db():
    """
    云端模式下，无需执行 CREATE TABLE。
    它的作用变为：检查表格标题行是否齐全（尤其是你之前报错过的 note 字段）。
    """
    st.info("正在同步云端数据库配置...")
    
    # 检查会员表关键列
    members_df = read_data("members")
    required_cols = ['phone', 'name', 'balance', 'skin_info', 'debt', 'note', 'reg_date']
    
    missing = [c for c in required_cols if c not in members_df.columns]
    if missing:
        st.warning(f"云端表格缺少以下列，请手动在 Google 表格首行补齐: {missing}")
    else:
        st.success("✅ 云端数据库连接成功！")

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
