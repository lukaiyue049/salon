import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
from db_manager import init_db, get_conn
import query_module, pos_module, activity_module, finance_module

# 1. 基础配置
st.set_page_config(
    page_title="929皮肤管理中心",
    page_icon="✨",  # 这里可以换成任何你喜欢的 Emoji，比如 🌸, 💄, 🌿
    layout="wide"
)
# ---------- 新增：手机模式状态初始化 ----------
if "is_mobile" not in st.session_state:
    st.session_state.is_mobile = False
init_db()
conn = get_conn()

# main.py 约第 11 行插入
# 全局温馨美容院风格微调
# 放到 st.set_page_config(layout="wide") 之后
st.markdown("""
    <style>
    /* ========== 全局基础样式 ========== */
    .stApp {
        background-color: #FDFBF9;
    }

    /* ========== 平板触屏优化：按钮更大（但不强制等宽） ========== */
    button, [data-testid="baseButton-secondary"], [data-testid="baseButton-primary"] {
        min-height: 48px !important;
        padding: 0.5rem 1rem !important;
        font-size: 1rem !important;
        white-space: nowrap !important;   /* 防止按钮文字折行 */
    }

    /* 统一字体大小 */
    html, body, [class*="st-"] {
        font-size: 16px;
    }

    /* 增加行间距 */
    .stExpander, .stContainer {
        margin-bottom: 0.8rem;
    }

    /* 侧边栏菜单文字更大 */
    .nav-link {
        font-size: 1.1rem !important;
        padding: 12px 16px !important;
    }

    /* ========== 标签文字颜色 ========== */
    label p {
        color: #8D6E63 !important;
        font-weight: 500 !important;
        font-size: 16px !important;
    }

    /* ========== 按钮美化 ========== */
    .stButton>button {
        background-color: #C1A088 !important;
        color: white !important;
        border-radius: 20px !important;
        border: none !important;
        padding: 5px 12px !important;      /* 左右内边距适中 */
        min-width: 60px !important;        /* 保证所有按钮都有足够宽度，避免挤压 */
        display: inline-flex !important;
        justify-content: center !important;
        align-items: center !important;
        gap: 4px !important;
        white-space: nowrap !important;
    }
    
    .stButton>button:hover {
        background-color: #A6866D !important;
    }

    /* ========== 侧边栏与标题 ========== */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
    }
    h1, h2, h3 {
        color: #8D6E63 !important;
        font-family: "STKaiti", "楷体", serif;
    }

    /* ========== 数字和内容颜色 ========== */
    [data-testid="stMetricValue"], .stText {
        color: #8D6E63 !important;
    }

    /* ========== 隐藏Streamlit自带菜单 ========== */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* ========== radio 按钮组样式：自适应宽度，不强制等宽 ========== */
    div[role="radiogroup"] {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;      /* 空间不足时换行，但每个按钮内文字不折行 */
        margin-bottom: 10px;
    }
    div[role="radiogroup"] label {
        background-color: #F5EFEA;
        border: 1px solid #E2D1C3;
        border-radius: 24px !important;
        padding: 8px 16px !important;
        margin: 0 !important;
        cursor: pointer;
        white-space: nowrap;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        min-width: 70px;          /* 保证最小宽度，防止文字被截断 */
        font-size: 0.9rem;        /* 稍微缩小字体，留出空间 */
    }
    div[role="radiogroup"] label:hover {
        background-color: #E2D1C3;
    }
    /* 选中状态 */
    div[role="radiogroup"] label[data-state="checked"] {
        background-color: #C1A088 !important;
        border-color: #A6866D !important;
    }
    div[role="radiogroup"] label[data-state="checked"] div {
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)
# 2. 侧边栏导航
with st.sidebar:
    # --- 美容院温馨风格标题：保持居中但更有质感 ---
    st.markdown("""
        <div style="
            text-align: center; 
            padding: 25px 10px; 
            margin-bottom: 25px; 
            background: linear-gradient(135deg, #fdfcfb 0%, #e2d1c3 100%); 
            border-radius: 20px;
            box-shadow: 0 8px 16px rgba(226, 209, 195, 0.4);
            border: 1px solid #f5eee6;
        ">
            <h2 style="
                color: #8d6e63; 
                margin: 0; 
                font-family: 'STKaiti', 'KaiTi', serif; 
                letter-spacing: 5px;
                font-weight: 600;
            ">✨ 929 美容中心</h2>
            <p style="
                color: #bcaaa4; 
                margin: 5px 0 0 0; 
                font-size: 0.75rem; 
                letter-spacing: 2px;
                font-family: 'Arial';
            ">BEAUTY & RELAXATION</p>
        </div>
    """, unsafe_allow_html=True)

    # --- 导航菜单：完全保留原有的文字和图标 ---
    selected = option_menu(
        menu_title=None,
        options=["消费收银", "会员管理", "营销活动", "项目库存", "财务报表", "系统设置"],
        icons=["cart4", "person-badge", "gift", "box-seam", "graph-up", "tools"],
        default_index=0,
        styles={
            "container": {
                "padding": "0px!important",  # 去掉内边距
                "margin": "0px!important",  # 去掉外边距
                "background-color": "#FFFFFF",  # 设为白色
                "border-radius": "0px",  # 这里设为0，防止露出背景
                "width": "100%"  # 强制占满
            },
            "icon": {"color": "#bcaaa4", "font-size": "18px"},
            "nav-link": {
                "font-size": "16px",
                "text-align": "left",
                "margin": "10px 15px",  # 左右留出一点空隙，更美观
                "border-radius": "20px",  # 按钮保持大圆角
                "color": "#8d6e63",
                "--hover-color": "#fdf5f2"
            },
            "nav-link-selected": {
                "background-color": "#e2d1c3",
                "color": "#5d4037",
                "border-radius": "20px",
                "font-weight": "600"
            },
        }
    )
        # ---------- 新增：手机模式切换开关 ----------
    st.divider()
    mobile_mode = st.toggle("📱 手机模式（底部导航）", value=st.session_state.is_mobile)
    if mobile_mode != st.session_state.is_mobile:
        st.session_state.is_mobile = mobile_mode
        st.rerun()

# ---------- 新增：根据手机模式获取当前页面 ----------
if st.session_state.is_mobile:
    # 手机模式下，从 session_state 读取选中的索引
    if "mobile_selected" not in st.session_state:
        st.session_state.mobile_selected = 0
    page_map = ["消费收银", "会员管理", "营销活动", "项目库存", "财务报表", "系统设置"]
    current_page = page_map[st.session_state.mobile_selected]
else:
    current_page = selected
# 3. 页面路由逻辑
if current_page == "消费收银":
    staff_res = pd.read_sql("SELECT name FROM staffs", conn)
    real_staffs = staff_res['name'].tolist()

    # 手动在第一个位置塞进“店长”，但不要存入数据库
    staff_list_for_pos = ["店长"] + real_staffs

    # 传给收银模块
    pos_module.show(staff_list_for_pos)

elif current_page == "会员管理":
    # 每次点击导航或页面刷新，都会重新执行这条 SQL
    query_module.show_member_management()

elif current_page == "营销活动":
    activity_module.show_activity_center()

# --- main.py 约第 33 行开始替换 ---
# main.py
# main.py 中 "项目库存" 部分的修改方案

elif current_page == "项目库存":
    st.header("📦 项目与产品管理")


    # 辅助函数：渲染带删除按钮的列表
    def render_product_list(conn, prod_type, title):
        st.subheader(title)
        if prod_type == "实物产品":
            df = pd.read_sql("SELECT prod_name, price, stock, unit, last_updated FROM products WHERE type='实物产品'", conn)
        else:
            df = pd.read_sql("SELECT prod_name, price, unit FROM products WHERE type='服务项目'", conn)

        if df.empty:
            st.info(f"暂无{title}")
            return

        # 表头
        if prod_type == "实物产品":
            header_cols = st.columns([2.5, 1, 1, 1.2, 0.5])  # 名称,单价,库存,更新时间,操作
            header_cols[0].markdown("**名称**")
            header_cols[1].markdown("**单价**")
            header_cols[2].markdown("**库存**")
            header_cols[3].markdown("**最后更新**")
            header_cols[4].markdown("**操作**")
        else:
            header_cols = st.columns([3, 1, 0.5])
            header_cols[0].markdown("**名称**")
            header_cols[1].markdown("**单价**")
            header_cols[2].markdown("**操作**")

        # 数据行（无分割线）
        for idx, row in df.iterrows():
            if prod_type == "实物产品":
                cols = st.columns([2.5, 1, 1, 1.2, 0.5])
                cols[0].write(row['prod_name'])
                cols[1].write(f"¥{row['price']:.2f}")
                cols[2].write(f"{row['stock']} {row['unit']}")
                cols[3].write(row['last_updated'][:16] if row['last_updated'] else "未知")
                if cols[4].button("🗑️", key=f"del_{prod_type}_{row['prod_name']}_{idx}", help="删除"):
                    query_module.confirm_delete_product(row['prod_name'], prod_type)
            else:
                cols = st.columns([3, 1, 0.5])
                cols[0].write(row['prod_name'])
                cols[1].write(f"¥{row['price']:.2f}")
                if cols[2].button("🗑️", key=f"del_{prod_type}_{row['prod_name']}_{idx}", help="删除"):
                    query_module.confirm_delete_product(row['prod_name'], prod_type)


    # 操作栏（保留两个主要按钮）
    col_op1, col_op2 = st.columns(2)
    with col_op1:
        if st.button("➕ 登记/进货/调价", use_container_width=True, type="primary"):
            query_module.add_product_dialog()
    with col_op2:
        if st.button("✂️ 损耗/店用", use_container_width=True):
            query_module.deduct_product_dialog()

    st.divider()

    # 两个 Tab 分别展示实物产品和服务项目
    t_product, t_service = st.tabs(["🛍️ 实物产品库存", "💆 服务项目清单"])
    with t_product:
        render_product_list(conn, "实物产品", "实物库存（如护肤品、耗材）")
    with t_service:
        render_product_list(conn, "服务项目", "服务项目（如祛痘、按摩、清洁）")
        st.caption("注：服务项目通常按次计费，无需管理实物库存。")

elif current_page == "财务报表":
    st.header("📊 财务报表分析")
    pwd = st.sidebar.text_input("请输入报表查看密码", type="password")
    if pwd == "929888":
        finance_module.show_financial_report()
    else:
        st.warning("🔒 该模块仅限店长查看，请输入正确的密码。")

elif current_page == "系统设置":
    st.header("⚙️ 系统管理")

    # 1. 员工维护（改为列表+行内删除）
    st.subheader("👥 员工维护")

    # 使用容器包裹，增加层次感
    with st.container(border=True):
        # --- 修改这里：将原本的 st.write 改为居中的 markdown ---
        h_col1, h_col2, h_col3 = st.columns([1, 1, 1])
        h_col1.markdown("<div style='text-align: center; font-weight: bold;'>员工姓名</div>", unsafe_allow_html=True)
        h_col2.markdown("<div style='text-align: center; font-weight: bold;'>状态</div>", unsafe_allow_html=True)
        h_col3.markdown("<div style='text-align: center; font-weight: bold;'>操作</div>", unsafe_allow_html=True)
        # ---------------------------------------------------

        st.divider()

        # 读取员工数据并循环显示
        staff_data = pd.read_sql("SELECT name FROM staffs", conn)
        if not staff_data.empty:
            for _, row in staff_data.iterrows():
                staff_name = row['name']
                r_col1, r_col2, r_col3 = st.columns([1, 1, 1])

                # 使用 HTML 标签 居中显示姓名
                r_col1.markdown(f"<div style='text-align: center;'>{staff_name}</div>", unsafe_allow_html=True)

                # 状态也居中
                r_col2.markdown("<div style='text-align: center;'>✅ 在职</div>", unsafe_allow_html=True)

                # 按钮会自动占满宽度，只需要设置 key 即可
                if r_col3.button("🗑️ 删除", key=f"del_{staff_name}", type="secondary", use_container_width=True):
                    conn.execute("DELETE FROM staffs WHERE name=?", (staff_name,))
                    conn.commit()
                    st.rerun()
        else:
            st.info("暂无员工信息")

    # 添加新员工（紧随列表下方）
    with st.expander("➕ 添加新员工"):
        ns = st.text_input("请输入新员工姓名", placeholder="例如：小张")
        if st.button("确认添加", type="primary"):
            if ns:
                conn.execute("INSERT OR IGNORE INTO staffs VALUES (?)", (ns,))
                conn.commit()
                st.success(f"已成功添加员工：{ns}")
                st.rerun()

    st.divider()  # --- 分隔线 ---

    # 2. 阈值设置（保持在中间）
    st.subheader("🚩 阈值设置")
    tc1, tc2, tc3 = st.columns([1, 1.5, 1])
    with tc2:
        curr_res = pd.read_sql("SELECT value FROM sys_config WHERE item='debt_limit'", conn)
        curr = curr_res.iloc[0, 0] if not curr_res.empty else 500.0
        v = st.number_input("红名阈值 (欠款超过此数名字标红)", value=float(curr))
        if st.button("💾 更新全局设置", use_container_width=True):
            conn.execute("UPDATE sys_config SET value=? WHERE item='debt_limit'", (str(v),))
            conn.commit()
            st.success("阈值已更新")

    st.divider()

    st.subheader("💾 数据安全与备份")
    # 创建三列布局，[1, 1, 1] 表示三列等宽
    col_left, col_mid, col_right = st.columns([1, 1, 1])

    with col_mid:  # 在中间一列放置内容
        m_data = pd.read_sql("SELECT * FROM members", conn)
        csv = m_data.to_csv(index=False).encode('utf-8-sig')

        # 直接使用 st.download_button 替代 st.button + st.download_button 的两步逻辑
        # use_container_width=True 确保按钮填满中间这一列的宽度，达到完美居中效果
        st.download_button(
            label="📁 导出所有会员数据",
            data=csv,
            file_name="members_backup.csv",
            mime="text/csv",
            use_container_width=True
        )

    st.info("建议定期导出一次数据存放在 U 盘或电脑桌面，防止数据丢失。")
# ---------- 新增：手机模式底部导航栏 ----------
if st.session_state.is_mobile:
    st.divider()
    cols = st.columns(6)
    page_names = ["💰 收银", "👤 会员", "🎁 活动", "📦 库存", "📊 财务", "⚙️ 设置"]
    page_map = ["消费收银", "会员管理", "营销活动", "项目库存", "财务报表", "系统设置"]
    
    for idx, col in enumerate(cols):
        if col.button(page_names[idx], key=f"nav_{idx}", use_container_width=True,
                      type="primary" if st.session_state.mobile_selected == idx else "secondary"):
            st.session_state.mobile_selected = idx
            st.rerun()
    st.caption("👇 点击按钮切换功能")
