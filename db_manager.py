import streamlit as st
from supabase import create_client, Client
import pandas as pd

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

def read_data(table_name: str) -> pd.DataFrame:
    supabase = get_supabase()
    try:
        response = supabase.table(table_name).select("*").execute()
        data = response.data
        if not data:
            return create_empty_df(table_name)
        df = pd.DataFrame(data)
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

def save_data(table_name: str, df: pd.DataFrame):
    supabase = get_supabase()
    try:
        records = df.to_dict(orient='records')
        for record in records:
            clean_record = {k: v for k, v in record.items() if pd.notna(v)}
            supabase.table(table_name).upsert(clean_record).execute()
        st.toast(f"✅ {table_name} 同步成功")
    except Exception as e:
        st.error(f"❌ 保存 {table_name} 失败: {e}")

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
        supabase = get_supabase()
        supabase.table("members").select("phone").limit(1).execute()
        st.success("✅ Supabase 连接成功")
    except Exception as e:
        st.error(f"❌ Supabase 连接失败: {e}")
