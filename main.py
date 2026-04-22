import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
# 从 db_manager 引入云端函数
from db_manager import init_db, get_conn, read_data, save_data

# 1. 基础配置
st.set_page_config(
    page_title="929皮肤管理中心",
    page_icon="✨",
    layout="wide"
)

# 初始化云端连接检查
init_db()

# --- 核心优化：高性能数据加载（解决慢的问题） ---
@st.cache_data(ttl=300)  # 缓存5分钟，切换页面不再卡顿
def load_all_data_once():
    """将所有高频读取的表一次性加载，减少HTTP握手次数"""
    return {
        "products": read_data("products"),
        "staffs": read_data("staffs"),
        "members": read_data("members"),
        "sys_config": read_data("sys_config")
    }

# 预加载数据包
data_bundle = load_all_data_once()

# --- 注入 CSS 样式 (完全保留并微调对齐) ---
st.markdown("""
    <style>
    .stApp { background-color: #FDFBF9; }
    button, [data-testid="baseButton-secondary"], [data-testid="baseButton-primary"] {
        min-height: 48px !important;
        padding: 0.5rem 1rem !important;
        font-size: 1rem !important;
        white-space: nowrap !important;
    }
    html, body, [class*="st-"] { font-size: 16px; }
    .stExpander, .stContainer { margin-bottom: 0.8rem; }
    .nav-link { font-size: 1.1rem !important; padding: 12px 16px !important; }
    label p { color: #8D6E63 !important; font-weight: 500 !important; font-size: 16px !important; }
    .stButton>button {
        background-color: #C1A088 !important;
        color: white !important;
        border-radius: 20px !important;
        border: none !important;
        min-width: 60px !important;
        display: inline-flex !important;
        justify-content: center !important;
        align-items: center !important;
    }
    .stButton>button:hover { background-color: #A6866D !important; }
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; }
    h1, h2, h3 { color: #8D6E63 !important; font-family: "STKaiti", "楷体", serif; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    
    div[role="radiogroup"] { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
    div[role="radiogroup"] label {
        background-color: #F5EFEA;
        border: 1px solid #E2D1C3;
        border-radius: 24px !important;
        padding: 8px 16px !important;
        white-space: nowrap;
        min-width: 70px;
        font-size: 0.9rem;
    }
    div[role="radiogroup"] label[data-state="checked"] {
        background-color: #C1A088 !important;
        border-color: #A6866D !important;
    }
    /* 表头文字样式 */
    .header-style { color: #8D6E63; font-weight: bold; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

# 导入业务模块
import query_module, pos_module, activity_module, finance_module

# 2. 侧边栏导航
with st.sidebar:
    st.markdown("""
        <div style="text-align: center; padding: 25px 10px; margin-bottom: 25px; 
             background: linear-gradient(135deg, #fdfcfb 0%, #e2d1c3 100%); 
             border-radius: 20px; box-shadow: 0 8px 16px rgba(226, 209, 195, 0.4);">
            <h2 style="color: #8d6e63; margin: 0; font-family: 'STKaiti', 'KaiTi', serif; letter-spacing: 5px;">✨ 929 美容中心</h2>
            <p style="color: #bcaaa4; margin: 5px 0 0 0; font-size: 0.75rem; letter-spacing: 2px;">BEAUTY & RELAXATION</p>
        </div>
    """, unsafe_allow_html=True)

    selected = option_menu(
        menu_title=None,
        options=["消费收银", "会员管理", "营销活动", "项目库存", "财务报表", "系统设置"],
        icons=["cart4", "person-badge", "gift", "box-seam", "graph-up", "tools"],
        default_index=0,
        styles={
            "container": {"background-color": "#FFFFFF", "width": "100%"},
            "nav-link": {"font-size": "16px", "color": "#8d6e63", "margin": "10px 15px", "border-radius": "20px"},
            "nav-link-selected": {"background-color": "#e2d1c3", "color": "#5d4037"}
        }
    )
    
    st.write("---")
    if st.button("🔄 同步最新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 3. 页面路由逻辑
if selected == "消费收银":
    staff_df = data_bundle["staffs"]
    real_staffs = staff_df['name'].tolist() if not staff_df.empty else []
    staff_list_for_pos = ["店长"] + real_staffs
    pos_module.show(staff_list_for_pos)

elif selected == "会员管理":
    query_module.show_member_management()

elif selected == "营销活动":
    activity_module.show_activity_center()

elif selected == "项目库存":
    st.header("📦 项目与产品管理")
    
    # --- 核心优化：解决对齐与美观问题 ---
    def render_product_list_cloud(prod_type, title):
        st.subheader(title)
        full_df = data_bundle["products"]
        if full_df.empty:
            st.info(f"暂无{title}")
            return
        
        df = full_df[full_df['type'] == prod_type].copy()
        if df.empty:
            st.info(f"暂无{title}")
            return

        # 统一精准列宽比例 [名称, 单价, 库存/单位, 最后更新/类型, 操作]
        if prod_type == "实物产品":
            layout = [2.5, 1, 1, 1.2, 0.5]
            titles = ["名称", "单价", "库存", "最后更新", "操作"]
        else:
            layout = [3, 1, 1, 0.5]
            titles = ["名称", "单价", "单位", "操作"]
        
        # 1. 渲染表头
        h_cols = st.columns(layout)
        for col, t in zip(h_cols, titles):
            col.markdown(f"<p class='header-style'>{t}</p>", unsafe_allow_html=True)
        st.divider()

        # 2. 循环渲染每一行 (使用垂直居中对齐)
        for idx, row in df.iterrows():
            c = st.columns(layout, vertical_alignment="center")
            c[0].markdown(f"**{row['prod_name']}**")
            c[1].write(f"¥{float(row['price']):.2f}")
            
            if prod_type == "实物产品":
                c[2].write(f"{row['stock']} {row['unit']}")
                c[3].caption(str(row['last_updated'])[:16])
                del_btn_col = c[4]
            else:
                c[2].write(row['unit'])
                del_btn_col = c[3]
            
            if del_btn_col.button("🗑️", key=f"del_{prod_type}_{idx}"):
                query_module.confirm_delete_product(row['prod_name'], prod_type)
                st.cache_data.clear() # 删除后清缓存

    col_op1, col_op2 = st.columns(2)
    with col_op1:
        if st.button("➕ 登记/进货/调价", use_container_width=True, type="primary"):
            query_module.add_product_dialog()
    with col_op2:
        if st.button("✂️ 损耗/店用", use_container_width=True):
            query_module.deduct_product_dialog()

    st.divider()
    t_product, t_service = st.tabs(["🛍️ 实物产品库存", "💆 服务项目清单"])
    with t_product:
        render_product_list_cloud("实物产品", "实物库存")
    with t_service:
        render_product_list_cloud("服务项目", "服务项目清单")

elif selected == "财务报表":
    st.header("📊 财务报表分析")
    pwd = st.sidebar.text_input("请输入报表查看密码", type="password")
    if pwd == "929888":
        finance_module.show_financial_report()
    else:
        st.warning("🔒 该模块仅限店长查看。")

elif selected == "系统设置":
    st.header("⚙️ 系统管理")

    # 1. 员工维护
    st.subheader("👥 员工维护")
    with st.container(border=True):
        h1, h2, h3 = st.columns([1, 1, 1])
        h1.markdown("<center><b>员工姓名</b></center>", unsafe_allow_html=True)
        h2.markdown("<center><b>状态</b></center>", unsafe_allow_html=True)
        h3.markdown("<center><b>操作</b></center>", unsafe_allow_html=True)
        
        staff_df = data_bundle["staffs"]
        if not staff_df.empty:
            for idx, row in staff_df.iterrows():
                r1, r2, r3 = st.columns([1, 1, 1], vertical_alignment="center")
                r1.markdown(f"<center>{row['name']}</center>", unsafe_allow_html=True)
                r2.markdown("<center>✅ 在职</center>", unsafe_allow_html=True)
                if r3.button("🗑️ 删除", key=f"s_{idx}", use_container_width=True):
                    new_df = staff_df.drop(idx)
                    save_data("staffs", new_df)
                    st.cache_data.clear()
                    st.rerun()

    with st.expander("➕ 添加新员工"):
        ns = st.text_input("员工姓名")
        if st.button("确认添加"):
            if ns:
                new_row = pd.DataFrame([{"name": ns}])
                save_data("staffs", pd.concat([staff_df, new_row], ignore_index=True))
                st.cache_data.clear()
                st.rerun()

    st.divider()
    
    # 2. 阈值设置
    st.subheader("🚩 阈值设置")
    config_df = data_bundle["sys_config"]
    curr_limit = 500.0
    if not config_df.empty and 'debt_limit' in config_df['item'].values:
        curr_limit = float(config_df[config_df['item']=='debt_limit']['value'].values[0])

    v = st.number_input("红名阈值 (欠款超过此数标红)", value=curr_limit)
    if st.button("💾 保存设置"):
        new_config = pd.DataFrame([{"item": "debt_limit", "value": str(v)}])
        save_data("sys_config", new_config)
        st.cache_data.clear()
        st.success("设置已同步至云端")

    st.divider()
    st.subheader("💾 数据备份")
    if st.button("生成备份数据包"):
        m_data = data_bundle["members"]
        st.download_button("点击下载备份 (CSV)", m_data.to_csv(index=False).encode('utf-8-sig'), "backup.csv", "text/csv")
