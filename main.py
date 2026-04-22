import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
from db_manager import init_db, read_data, save_data

st.set_page_config(page_title="929皮肤管理中心", page_icon="✨", layout="wide")
init_db()

# ---------- 全局数据缓存（TTL=10秒，实现准实时同步）----------
@st.cache_data(ttl=10, show_spinner="正在同步云端数据...")
def load_all_data():
    try:
        return {
            "products": read_data("products"),
            "members": read_data("members"),
            "staffs": read_data("staffs"),
            "sys_config": read_data("sys_config"),
            "activities": read_data("activities"),
            "records": read_data("records"),
            "salon_items": read_data("salon_items"),
        }
    except Exception as e:
        if "429" in str(e):
            st.error("⚠️ 云端限流，数据可能不是最新的。请稍后自动重试。")
            # 返回空数据，但不要停止程序
            return {k: pd.DataFrame() for k in ["products","members","staffs","sys_config","activities","records","salon_items"]}
        else:
            raise

# 导入模块
from modules import pos, member, product, activity, finance, settings

# ---------- CSS 样式（保持不变）----------
st.markdown("""
<style>
.stApp { background-color: #FDFBF9; }
button, [data-testid="baseButton-secondary"], [data-testid="baseButton-primary"] {
    min-height: 48px !important; padding: 0.5rem 1rem !important;
    font-size: 1rem !important; white-space: nowrap !important;
}
.stButton>button {
    background-color: #C1A088 !important; color: white !important;
    border-radius: 20px !important; border: none !important;
}
.stButton>button:hover { background-color: #A6866D !important; }
h1, h2, h3 { color: #8D6E63 !important; font-family: "STKaiti", "楷体", serif; }
div[role="radiogroup"] label {
    background-color: #F5EFEA; border: 1px solid #E2D1C3;
    border-radius: 24px !important; padding: 8px 16px !important;
}
div[role="radiogroup"] label[data-state="checked"] {
    background-color: #C1A088 !important; border-color: #A6866D !important;
}
</style>
""", unsafe_allow_html=True)

# ---------- 侧边栏 ----------
with st.sidebar:
    st.markdown("""
        <div style="text-align: center; padding: 25px 10px; margin-bottom: 25px;
             background: linear-gradient(135deg, #fdfcfb 0%, #e2d1c3 100%);
             border-radius: 20px;">
            <h2 style="color: #8d6e63;">✨ 929 美容中心</h2>
        </div>
    """, unsafe_allow_html=True)
    
    selected = option_menu(
        menu_title=None,
        options=["消费收银", "会员管理", "项目库存", "营销活动", "财务报表", "系统设置"],
        icons=["cart4", "person-badge", "box-seam", "gift", "graph-up", "tools"],
        default_index=0,
        styles={
            "container": {"background-color": "#FFFFFF"},
            "nav-link": {"font-size": "16px", "color": "#8d6e63", "margin": "10px 15px", "border-radius": "20px"},
            "nav-link-selected": {"background-color": "#e2d1c3", "color": "#5d4037"}
        }
    )
    st.write("---")
    # 移除手动刷新按钮，因为会自动同步
    st.caption("💡 数据将自动同步（最多延迟10秒）")

# ---------- 加载数据 ----------
data_bundle = load_all_data()

# 如果数据为空（429错误），显示警告但不停止
if all(df.empty for df in data_bundle.values()):
    st.warning("⚠️ 暂时无法连接云端，请检查网络或稍后刷新页面。")

# ---------- 路由 ----------
if selected == "消费收银":
    pos.show(data_bundle)
elif selected == "会员管理":
    member.show(data_bundle)
elif selected == "项目库存":
    product.show(data_bundle)
elif selected == "营销活动":
    activity.show(data_bundle)
elif selected == "财务报表":
    pwd = st.sidebar.text_input("报表密码", type="password")
    if pwd == "929888":
        finance.show(data_bundle)
    else:
        st.warning("🔒 仅限店长查看。")
elif selected == "系统设置":
    settings.show(data_bundle)
