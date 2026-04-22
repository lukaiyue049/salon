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
init_db()
conn = get_conn()

# main.py 约第 11 行插入
# 全局温馨美容院风格微调
# 放到 st.set_page_config(layout="wide") 之后
st.markdown("""
    <style>
    /* 1. 整体大背景：非常淡的奶白色 */
    .stApp {
        background-color: #FDFBF9;
    }

    /* 2. 修复输入框：让它变白、变明显 */
    /* 这里的选择器专门针对文本输入框和密码框 */
    div[data-baseweb="input"] {
        background-color: #FFFFFF !important; /* 纯白背景，确保能看见 */
        border: 1px solid #E2D1C3 !important; /* 奶茶色边框 */
        border-radius: 10px !important;
    }

    /* 输入框内的文字颜色 */
    input {
        color: #4A3F35 !important;
    }

    /* 3. 标签（如“请输入报表查看密码”）颜色 */
    label p {
        color: #8D6E63 !important;
        font-weight: 500 !important;
        font-size: 16px !important;
    }

    /* 4. 按钮美化 */
    .stButton>button {
        background-color: #C1A088 !important;
        color: white !important;
        border-radius: 20px !important;
        border: none !important;
        padding: 5px 20px !important;
    }
    .stButton>button:hover {
        background-color: #A6866D !important;
    }

    /* 5. 侧边栏与标题字体 */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
    }
    h1, h2, h3 {
        color: #8D6E63 !important;
        font-family: "STKaiti", "楷体", serif;
    }

    /* 6. 统一数字和内容颜色 */
    [data-testid="stMetricValue"], .stText {
        color: #8D6E63 !important;
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

# 3. 页面路由逻辑
if selected == "消费收银":
    staff_res = pd.read_sql("SELECT name FROM staffs", conn)
    real_staffs = staff_res['name'].tolist()

    # 手动在第一个位置塞进“店长”，但不要存入数据库
    staff_list_for_pos = ["店长"] + real_staffs

    # 传给收银模块
    pos_module.show(staff_list_for_pos)

elif selected == "会员管理":
    # 每次点击导航或页面刷新，都会重新执行这条 SQL
    query_module.show_member_management()

elif selected == "营销活动":
    activity_module.show_activity_center()

# --- main.py 约第 33 行开始替换 ---
# main.py
# main.py 中 "项目库存" 部分的修改方案

elif selected == "项目库存":
    st.header("📦 项目与产品管理")

    # --- CSS 保持不变 ---
    st.markdown("""
        <style>
        div[data-testid="stDataFrame"] { margin-left: auto; margin-right: auto; display: flex; justify-content: center; }
        div[data-testid="stDataFrame"] td, div[data-testid="stDataFrame"] th { text-align: center !important; }
        </style>
    """, unsafe_allow_html=True)

    # 1. 操作栏：按钮和删除逻辑保持通用
    op_col1, op_col1_2, op_col2, op_col3 = st.columns([1, 1, 1.5, 0.8])  # 增加了一列

    with op_col1:
        if st.button("➕ 登记/进货/调价", use_container_width=True, type="primary"):
            query_module.add_product_dialog()

    with op_col1_2:  # 新增：损耗扣除按钮
        if st.button("✂️ 损耗/店用", use_container_width=True):
            query_module.deduct_product_dialog()  # 调用我们在下一步定义的函数

    with op_col2:
        current_prods = pd.read_sql("SELECT prod_name FROM products", conn)
        prod_list = current_prods['prod_name'].tolist() if not current_prods.empty else []
        del_target = st.selectbox("清理项目", ["选择要删除的项目..."] + prod_list, label_visibility="collapsed")

    with op_col3:
        if st.button("🗑️ 确认删除", use_container_width=True):
            if del_target != "选择要删除的项目...":
                conn.execute("DELETE FROM products WHERE prod_name=?", (del_target,))
                conn.commit()
                st.success(f"已清理")
                st.rerun()

    st.divider()

    # 2. 核心修改：使用 Tabs 分类展示
    t_product, t_service = st.tabs(["🛍️ 实物产品库存", "💆 服务项目清单"])

    with t_product:
        st.subheader("实物库存（如护肤品、耗材）")
        # 增加 WHERE type='实物产品' 过滤
        df_p = pd.read_sql("SELECT prod_name, price, stock, unit FROM products WHERE type='实物产品'", conn)
        if not df_p.empty:
            st.dataframe(
                df_p,
                column_config={
                    "prod_name": "产品名称",
                    "price": st.column_config.NumberColumn("单价", format="¥%.2f"),
                    "stock": st.column_config.ProgressColumn("剩余库存", min_value=0, max_value=100, format="%d"),
                    "unit": "单位"
                },
                use_container_width=True, hide_index=True
            )
        else:
            st.info("暂无实物产品数据")

    with t_service:
        st.subheader("服务项目（如祛痘、按摩、清洁）")
        # 增加 WHERE type='服务项目' 过滤
        df_s = pd.read_sql("SELECT prod_name, price, unit FROM products WHERE type='服务项目'", conn)
        if not df_s.empty:
            st.dataframe(
                df_s,
                column_config={
                    "prod_name": "项目名称",
                    "price": st.column_config.NumberColumn("单次价格", format="¥%.2f"),
                    "unit": "计费单位"
                },
                use_container_width=True, hide_index=True
            )
            st.caption("注：服务项目通常按次计费，无需管理实物库存。")
        else:
            st.info("暂无服务项目数据")

# main.py

elif selected == "财务报表":
    st.header("📊 财务报表分析")
    pwd = st.sidebar.text_input("请输入报表查看密码", type="password")
    if pwd == "929888":
        finance_module.show_financial_report()
    else:
        st.warning("🔒 该模块仅限店长查看，请输入正确的密码。")

elif selected == "系统设置":
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