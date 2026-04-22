import streamlit as st
import pandas as pd
from db_manager import get_conn
import time
import re

def show_member_management():
    st.header("👤 会员中心")
    conn = get_conn()

    # --- 必须添加这几行初始化 ---
    if 'show_reg' not in st.session_state:
        st.session_state.show_reg = False
    if 'show_batch' not in st.session_state:
        st.session_state.show_batch = False
    # 批量删除相关状态
    if 'batch_delete_mode' not in st.session_state:
        st.session_state.batch_delete_mode = False
    if 'selected_members' not in st.session_state:
        st.session_state.selected_members = []

    # 获取红名阈值
    limit_res = pd.read_sql("SELECT value FROM sys_config WHERE item='debt_limit'", conn)
    limit = float(limit_res.iloc[0, 0]) if not limit_res.empty else 500.0

    # 顶部操作栏
    # query_module.py
    # 找到顶部操作栏部分并替换
    # --- 1. 重新定义顶部操作栏 (由 2 列改为 4 列) ---
    # --- 1. 重新定义顶部操作栏 (4列布局：搜索、状态开关、注册按钮、批量按钮) ---
    # 第一行：搜索框 + 只看超额开关
row1_col1, row1_col2 = st.columns([3, 1])
with row1_col1:
    search = st.text_input("搜索", placeholder="🔍 姓名/手机号", label_visibility="collapsed")
with row1_col2:
    only_debt = st.toggle("🚨 只看超额", value=False)

# 第二行：三个操作按钮
row2_col1, row2_col2, row2_col3 = st.columns(3)
with row2_col1:
    if st.button("➕ 注册会员", use_container_width=True):
        register_member_dialog()
with row2_col2:
    if st.button("📥 批量导入", use_container_width=True):
        st.session_state.show_batch = not st.session_state.get('show_batch', False)
        st.rerun()
with row2_col3:
    if st.button("🗑️ 批量删除", use_container_width=True, type="secondary"):
        st.session_state.batch_delete_mode = not st.session_state.batch_delete_mode
        if not st.session_state.batch_delete_mode:
            st.session_state.selected_members = []
        st.rerun()

    # B. 批量导入界面
    if st.session_state.get('show_batch', False):
        with st.container(border=True):
            st.subheader("👥 会员批量导入中心")
            tab_manual, tab_file = st.tabs(["✍️ 手动录入/粘贴", "📁 拖拽上传文件"])

            with tab_manual:
                st.info("💡 提示：请确保手机号为11位数字。系统将自动跳过格式不正确的号码。")
                init_df = pd.DataFrame([{"姓名": "", "手机号": "", "余额": 0.0, "欠款": 0.0, "备注": ""}] * 15)
                edited_df = st.data_editor(init_df, num_rows="dynamic", use_container_width=True,
                                           key="member_batch_editor")

                if st.button("🚀 确认提交手动录入内容", type="primary"):
                    # 1. 过滤掉姓名为空的行
                    temp_df = edited_df[edited_df['姓名'].astype(str).str.strip() != ""].copy()

                    if not temp_df.empty:
                        # 2. 手机号清洗：去空格、去横杠、去浮点数尾缀(.0)
                        temp_df['手机号'] = temp_df['手机号'].astype(str).str.replace(r'\s+|-', '',
                                                                                      regex=True).str.replace(r'\.0$',
                                                                                                              '',
                                                                                                              regex=True)

                        # 3. 手机号校验：1开头，第2位3-9，后面9位数字
                        phone_pattern = r"^1[3-9]\d{9}$"
                        final_df = temp_df[temp_df['手机号'].str.match(phone_pattern)]

                        # 计算跳过的行数
                        skip_count = len(temp_df) - len(final_df)

                        if not final_df.empty:
                            save_batch_to_db(final_df, conn)
                            if skip_count > 0:
                                st.warning(
                                    f"✅ 导入完成！已录入 {len(final_df)} 条数据，但有 {skip_count} 条因手机号格式错误被跳过。")
                                time.sleep(2)
                            else:
                                st.success(f"✅ 全部 {len(final_df)} 条会员数据已成功录入！")
                            st.session_state.show_batch = False
                            st.rerun()
                        else:
                            st.error("❌ 提交失败：表格中没有符合 11 位中国手机号格式的数据。")
                    else:
                        st.warning("表格为空，请输入数据")

            with tab_file:
                st.write("请将 Excel 或 CSV 文件拖到下方：")
                uploaded_file = st.file_uploader("文件上传", type=["xlsx", "csv"], label_visibility="collapsed")
                if uploaded_file:
                    try:
                        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(
                            uploaded_file)
                        st.write("预览前5行：")
                        st.dataframe(df.head(5), use_container_width=True)

                        if st.button("✅ 确认导入文件数据", use_container_width=True):
                            # 自动寻找手机号列名
                            phone_col = next((c for c in df.columns if '号' in c or '话' in c), None)

                            if phone_col:
                                # 清洗文件中的手机号
                                df[phone_col] = df[phone_col].astype(str).str.replace(r'\s+|-', '',
                                                                                      regex=True).str.replace(r'\.0$',
                                                                                                              '',
                                                                                                              regex=True)
                                phone_pattern = r"^1[3-9]\d{9}$"
                                valid_df = df[df[phone_col].str.match(phone_pattern)]

                                if not valid_df.empty:
                                    save_batch_to_db(valid_df, conn)
                                    st.success(f"✅ 成功从文件导入 {len(valid_df)} 条有效会员数据！")
                                    time.sleep(1)
                                    st.session_state.show_batch = False
                                    st.rerun()
                                else:
                                    st.error("❌ 文件中没有符合格式的手机号，请检查数据。")
                            else:
                                st.error("❌ 未在文件中找到包含“手机”或“电话”字样的列头。")
                    except Exception as e:
                        st.error(f"解析出错：{e}")

            if st.button("❌ 关闭导入中心", use_container_width=True):
                st.session_state.show_batch = False
                st.rerun()

        # 保持专注模式：开启批量导入时停止渲染下方列表
        st.stop()

    # --- 2. 依次执行筛选逻辑 (已移除 category 相关逻辑) ---
    # 获取原始会员数据
    df = pd.read_sql("SELECT * FROM members", conn)

    # A. 筛选挂账超额 (使用函数开头获取到的 limit 变量)
    if only_debt:
        df = df[df['debt'] > limit]

    # B. 搜索关键词筛选 (去重并保留一个即可)
    if search:
        # 使用 na=False 处理可能存在的空值，防止程序报错
        df = df[
            df['name'].str.contains(search, na=False) |
            df['phone'].str.contains(search, na=False)
            ]

    # --- C. 结果检查 ---
    if df.empty:
        st.info("🔍 暂无符合条件的会员记录")
        return

    # 遍历显示会员资料卡
        # --- 替换开始（对应 query_module.py 中的会员列表循环） ---
    for _, row in df.iterrows():
        is_debt_high = row['debt'] > limit

        with st.container(border=True):
            # 根据是否批量删除模式，显示不同列数
            if st.session_state.batch_delete_mode:
                cols = st.columns([0.5, 1.5, 2, 1, 1])  # 复选框 + 姓名 + 备注 + 余额 + 欠款
            else:
                cols = st.columns([1.5, 2, 1, 1, 0.5])  # 姓名 + 备注 + 余额 + 欠款 + 删除按钮

            idx_col = 0

            # 批量模式：复选框
            if st.session_state.batch_delete_mode:
                checked = cols[idx_col].checkbox("", key=f"chk_{row['phone']}",
                                                 value=row['phone'] in st.session_state.selected_members)
                if checked and row['phone'] not in st.session_state.selected_members:
                    st.session_state.selected_members.append(row['phone'])
                elif not checked and row['phone'] in st.session_state.selected_members:
                    st.session_state.selected_members.remove(row['phone'])
                idx_col += 1

            # 姓名列
            with cols[idx_col]:
                name_prefix = "🔴 " if is_debt_high else "👤 "
                st.markdown(f"#### {name_prefix}{row['name']}")
                st.caption(f"📱 {row['phone']}")
            idx_col += 1

            # 备注列
            with cols[idx_col]:
                st.caption("📝 备注/肤质")
                st.write(row['skin_info'] if row['skin_info'] else "暂无备注")
            idx_col += 1

            # 余额列
            with cols[idx_col]:
                st.metric("账户余额", f"¥{row['balance']}")
            idx_col += 1

            # 欠款列
            with cols[idx_col]:
                st.metric("当前欠款", f"¥{row['debt']}", delta=f"-{row['debt']}" if row['debt'] > 0 else None,
                          delta_color="inverse")
            idx_col += 1

            # 非批量模式：删除按钮（垃圾桶图标）
            if not st.session_state.batch_delete_mode:
                with cols[idx_col]:
                    if st.button("🗑️", key=f"del_icon_{row['phone']}", help="删除会员"):
                        confirm_delete_member(row['phone'], row['name'])

            # 2. 将原本复杂的管理功能收纳进折叠面板，保持界面整洁
            with st.expander("👑 资料卡"):
                t1, t2, t3, t4 = st.tabs(["📋 基本资料", "💰 账户详情", "🎫 购入产品", "🕒 消费记录"])

                with t1:
                    c1_sub, c2_sub = st.columns(2)
                    c1_sub.markdown(f"**姓名:** {row['name']}")
                    c1_sub.markdown(f"**联系电话:** {row['phone']}")
                    c2_sub.markdown(f"**皮肤/备注:**")
                    c2_sub.info(row['skin_info'] or "暂无备注信息")

                with t2:
                    # --- 账户概览 ---
                    c_bal, c_debt = st.columns(2)
                    with c_bal:
                        st.metric("钱包余额", f"¥{row['balance']}", help="当前账户可用于消费的预存金额")
                    with c_debt:
                        st.metric("待结欠款", f"¥{row['debt']}",
                                  delta=f"需还 ¥{row['debt']}" if row['debt'] > 0 else None,
                                  delta_color="inverse")

                    st.divider()  # 添加分割线

                    # --- 操作区域 ---
                    col_recharge, col_repay = st.columns(2, gap="large")

                    # 左侧：余额充值
                    with col_recharge:
                        with st.container(border=True):
                            st.markdown("#### 💰 余额充值")
                            recharge_amt = st.number_input("输入金额", min_value=0.0, step=100.0,
                                                           key=f"re_{row['phone']}")

                            if st.button("立即充值", key=f"btn_re_{row['phone']}", use_container_width=True,
                                         type="primary"):
                                if recharge_amt > 0:
                                    conn.execute("UPDATE members SET balance = balance + ? WHERE phone = ?",
                                                 (recharge_amt, row['phone']))
                                    conn.execute(
                                        "INSERT INTO records (member_phone, date, items, total_amount, status, staff_name) VALUES (?, datetime('now','localtime'), '余额充值', ?, '现结', '店长')",
                                        (row['phone'], recharge_amt))
                                    conn.commit()
                                    st.success(f"已存入 ¥{recharge_amt}")
                                    time.sleep(0.5)
                                    st.rerun()

                    # 右侧：欠款还款
                    with col_repay:
                        with st.container(border=True):
                            st.markdown("#### 🔴 欠款结清")
                            if row['debt'] > 0:
                                repay_amt = st.number_input("归还金额", min_value=0.0, max_value=float(row['debt']),
                                                            step=10.0, key=f"repay_val_{row['phone']}")

                                # 分两列放还款按钮
                                r_btn1, r_btn2 = st.columns(2)
                                with r_btn1:
                                    if st.button("部分还款", key=f"btn_repay_{row['phone']}", use_container_width=True):
                                        if repay_amt > 0:
                                            conn.execute("UPDATE members SET debt = MAX(0, debt - ?) WHERE phone = ?",
                                                         (repay_amt, row['phone']))
                                            conn.execute(
                                                "INSERT INTO records (member_phone, date, items, total_amount, status, staff_name) VALUES (?, datetime('now','localtime'), '偿还欠款', ?, '现结', '店长')",
                                                (row['phone'], repay_amt))
                                            conn.commit()
                                            st.rerun()
                                with r_btn2:
                                    if st.button("一键结清", key=f"debt_full_{row['phone']}", use_container_width=True,
                                                 type="secondary"):
                                        conn.execute("UPDATE members SET debt = 0 WHERE phone = ?", (row['phone'],))
                                        conn.execute(
                                            "INSERT INTO records (member_phone, date, items, total_amount, status, staff_name) VALUES (?, datetime('now','localtime'), '全额还欠', ?, '现结', '店长')",
                                            (row['phone'], row['debt']))
                                        conn.commit()
                                        st.rerun()
                            else:
                                st.write("")
                                st.success("当前无欠款，信用良好！")

                with t3:
                    # 1. 查询所有资产（包含使用中和已用完），关联 products 表获取类型(type)
                    # 同时通过 MAX(buy_date) 获取最新日期，SUM 统计总量
                    items_query = """
                        SELECT 
                            s.item_name, 
                            SUM(s.total_qty) as total_qty, 
                            SUM(s.used_qty) as used_qty,
                            MAX(s.buy_date) as last_buy_date,
                            s.unit,
                            s.status,
                            p.type as item_type
                        FROM salon_items s
                        LEFT JOIN products p ON s.item_name = p.prod_name
                        WHERE s.member_phone=?
                        GROUP BY s.item_name, s.unit, s.status
                    """
                    all_items = pd.read_sql(items_query, conn, params=(row['phone'],))

                    if all_items.empty:
                        st.info("暂无持有资产记录")
                    else:
                        # 分为两个大的逻辑板块：剩余资产 vs 历史资产
                        tab_active, tab_history = st.tabs(["✨ 当前剩余资产", "📔 已核销/历史"])

                        # --- 板块 A：当前剩余资产 ---
                        with tab_active:
                            active_df = all_items[all_items['status'] == '使用中']
                            if active_df.empty:
                                st.caption("暂无可用资产")
                            else:
                                # 内部细分为：服务项目 与 实物产品
                                for it_type in ["服务项目", "实物产品"]:
                                    type_df = active_df[active_df['item_type'] == it_type]
                                    if not type_df.empty:
                                        st.markdown(f"**【{it_type}】**")
                                        for _, it in type_df.iterrows():
                                            with st.container(border=True):
                                                left, right = st.columns([3, 1])
                                                remains = it['total_qty'] - it['used_qty']
                                                u = it['unit'] if it['unit'] else "次"

                                                left.write(
                                                    f"**{it['item_name']}** (余 {remains} {u} / 总 {it['total_qty']} {u})")
                                                left.caption(f"📅 最新购入: {it['last_buy_date']}")

                                                if right.button(f"核销 1 {u}",
                                                                key=f"use_act_{row['phone']}_{it['item_name']}"):
                                                    # 这里的核销逻辑保持之前的先进先出(ORDER BY id ASC)
                                                    target = pd.read_sql(
                                                        "SELECT id, used_qty, total_qty FROM salon_items WHERE member_phone=? AND item_name=? AND status='使用中' ORDER BY id ASC LIMIT 1",
                                                        conn, params=(row['phone'], it['item_name'])
                                                    )
                                                    if not target.empty:
                                                        tid, u_qty, t_qty = target.iloc[0]
                                                        new_u, new_s = u_qty + 1, (
                                                            "已用完" if u_qty + 1 >= t_qty else "使用中")
                                                        conn.execute(
                                                            "UPDATE salon_items SET used_qty=?, status=? WHERE id=?",
                                                            (new_u, new_s, tid))
                                                        conn.execute(
                                                            "UPDATE products SET stock = MAX(0, stock - 1) WHERE prod_name = ?",
                                                            (it['item_name'],))
                                                        conn.execute(
                                                            "INSERT INTO records (member_phone, date, items, total_amount, status, staff_name) VALUES (?, datetime('now','localtime'), ?, 0, '次卡核销', '店长')",
                                                            (row['phone'], f"使用:{it['item_name']}"))
                                                        conn.commit()
                                                        st.rerun()

                        # --- 板块 B：已核销/历史 ---
                        with tab_history:
                            history_df = all_items[all_items['status'] == '已用完']
                            if history_df.empty:
                                st.caption("暂无历史核销记录")
                            else:
                                # 历史记录通常只需要简单列表展示
                                for _, it in history_df.iterrows():
                                    u = it['unit'] if it['unit'] else "次"
                                    st.text(f"⚪ {it['item_name']} - 已全部核销 (共 {it['total_qty']} {u})")
                                    st.caption(f"最后一次购入时间: {it['last_buy_date']}")

                with t4:
                    history = pd.read_sql(
                        "SELECT date, items, total_amount, status, staff_name FROM records WHERE member_phone=? ORDER BY id DESC",
                        conn, params=(row['phone'],))
                    if history.empty:
                        st.write("该会员暂无消费记录")
                    else:
                        history.columns = ["时间", "消费内容", "金额", "支付方式", "经办人"]
                        st.dataframe(history, use_container_width=True, hide_index=True)
    # 批量删除操作栏（仅在批量模式下显示）
    if st.session_state.batch_delete_mode and st.session_state.selected_members:
        st.divider()
        st.warning(f"已选中 {len(st.session_state.selected_members)} 位会员")

        col_confirm, col_cancel = st.columns(2)
        with col_confirm:
            if st.button("⚠️ 批量删除选中会员", type="primary", use_container_width=True):
                # 二次确认对话框
                confirm_batch_delete()
        with col_cancel:
            if st.button("取消批量模式", use_container_width=True):
                st.session_state.batch_delete_mode = False
                st.session_state.selected_members = []
                st.rerun()

@st.dialog("👤 注册新会员")
def register_member_dialog():
    conn = get_conn()
    with st.form("single_reg", clear_on_submit=True):
        c1, c2 = st.columns(2)
        n = c1.text_input("姓名*").strip()
        p = c2.text_input("手机号*").strip()

        c3, c4 = st.columns([1, 2])
        b = c3.number_input("初始余额", min_value=0.0, step=100.0)
        s = c4.text_input("备注/肤质")

        d = st.number_input("初始欠款", min_value=0.0, step=10.0)

        submit = st.form_submit_button("确认录入", type="primary", use_container_width=True)

        if submit:
            # 1. 预处理与校验
            phone_pattern = r"^1[3-9]\d{9}$"
            clean_p = "".join(p.split()).replace("-", "")

            if not n:
                st.error("请输入姓名")
                st.stop()  # 停止后续逻辑执行

            if not re.match(phone_pattern, clean_p):
                st.error("❌ 手机号格式不正确，请输入11位中国手机号")
                st.stop()

            # 2. 预检查：手机号是否存在 (这是防止两个提示同时出现的关键)
            check_exist = pd.read_sql("SELECT name FROM members WHERE phone=?", conn, params=(clean_p,))

            if not check_exist.empty:
                st.error(f"❌ 手机号已存在！对应会员：{check_exist.iloc[0, 0]}")
            else:
                # 3. 只有不存在时才执行插入
                try:
                    conn.execute(
                        "INSERT INTO members (phone, name, balance, skin_info, debt) VALUES (?,?,?,?,?)",
                        (clean_p, n, b, s, d)
                    )
                    conn.commit()
                    st.success(f"✅ 会员 {n} 注册成功！")
                    time.sleep(0.8)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 写入数据库失败: {e}")


@st.dialog("项目管理 / 录入与进货")
def add_product_dialog():
    conn = get_conn()

    # 1. 初始化批量清单暂存
    if 'batch_list' not in st.session_state:
        st.session_state.batch_list = []

    menu = st.tabs(["✨ 单个连续录入", "📦 批量清单/确认"])

    # --- 标签页1：单个连续录入 ---
    with menu[0]:

        p_type = st.radio("业务类别", ["实物产品", "服务项目"], horizontal=True, key="dlg_type")
        mode = st.radio("录入类型", ["新登记录入", "现有补货/调价"], horizontal=True, key="dlg_mode")

        with st.container(border=True):
            if mode == "新登记录入":
                prod_name = st.text_input(f"{p_type}名称*", key="in_name")
                if p_type == "服务项目":
                    price = st.number_input("项目定价", min_value=0.0, step=10.0, key="in_price")
                    u, qty, spec = "次", 999, 1
                else:
                    u = st.selectbox("计量单位", ["盒", "瓶", "支", "个", "套"], key="in_unit")
                    price = st.number_input("销售单价（每单位）", min_value=0.0, key="in_price")
                    qty = st.number_input(f"初始库存({u})", min_value=0, key="in_qty")
                    # 规格判定
                    if u == "盒":
                        spec = st.number_input("规格", min_value=1, value=10, key="in_spec")
                    elif u == "套":
                        spec = st.number_input("规格", min_value=1, value=5, key="in_spec")
                    else:
                        spec = 1
            else:
                all_prods = pd.read_sql("SELECT prod_name FROM products WHERE type=?", conn, params=(p_type,))
                p_list = all_prods['prod_name'].tolist() if not all_prods.empty else []
                if not p_list:
                    st.warning(f"⚠️ 当前分类【{p_type}】下暂无已登记的项目")
                    prod_name = None
                else:
                    prod_name = st.selectbox(f"选择已有{p_type}", p_list, key="sel_name")
                    price = st.number_input("更新单价 (0为不改)", 0.0, key="up_price")
                    u = "次" if p_type == "服务项目" else "原单位"
                    qty = st.number_input("增加数量", min_value=0, key="up_qty") if p_type == "实物产品" else 0
                    spec = 1 # 补货模式下不改规格

            c_btn1, c_btn2 = st.columns(2)
            if c_btn1.button("📥 直接提交", use_container_width=True, type="primary"):
                if prod_name:
                    if mode == "新登记录入":
                        check = pd.read_sql("SELECT prod_name FROM products WHERE prod_name=?", conn, params=(prod_name,))
                        if not check.empty: st.error("名称已存在")
                        else:
                            # 核心：直接存入 qty，不乘 spec
                            conn.execute(
                                "INSERT INTO products (prod_name, category, price, stock, unit, type, last_updated) VALUES (?, ?, ?, ?, ?, ?, datetime('now','localtime'))",
                                (prod_name, str(spec), price, qty, u, p_type))
                            conn.commit()
                            st.toast(f"✅ {prod_name} 录入成功")
                            st.rerun()
                    else:
                        # 补货：直接增加原始数量
                        conn.execute(
                            "UPDATE products SET stock = stock + ?, price = CASE WHEN ?>0 THEN ? ELSE price END, last_updated = datetime('now','localtime') WHERE prod_name = ?",
                            (qty, price, price, prod_name))
                        conn.commit()
                        st.toast("✅ 更新成功")
                        st.rerun()

            if c_btn2.button("➕ 加入批量清单", use_container_width=True):
                if prod_name:
                    st.session_state.batch_list.append({
                        "名称": prod_name, "类型": p_type, "单价": price,
                        "数量": qty, "单位": u, "模式": mode, "规格": spec
                    })
                    st.toast("已加入清单")

    # --- 标签页2：批量处理 ---
    with menu[1]:
        if st.session_state.batch_list:
            df_batch = pd.DataFrame(st.session_state.batch_list)
            st.dataframe(df_batch, use_container_width=True, hide_index=True)
            if st.button("🚀 确认全部入库", use_container_width=True, type="primary"):
                for item in st.session_state.batch_list:
                    if item['模式'] == "新登记录入":
                        conn.execute(
                            "INSERT OR IGNORE INTO products (prod_name, category, price, stock, unit, type, last_updated) VALUES (?, ?, ?, ?, ?, ?, datetime('now','localtime'))",
                            (item['名称'], str(item['规格']), item['单价'], item['数量'], item['单位'], item['类型']))
                    else:
                        conn.execute(
                            "UPDATE products SET stock = stock + ?, price = CASE WHEN ?>0 THEN ? ELSE price END, last_updated = datetime('now','localtime') WHERE prod_name = ?",
                            (item['数量'], item['单价'], item['单价'], item['名称']))
                conn.commit()
                st.session_state.batch_list = []
                st.rerun()


# query_module.py

@st.dialog("非销售扣除登记")
def deduct_product_dialog():
    conn = get_conn()

    # 1. 获取产品信息
    prods = pd.read_sql("SELECT prod_name, stock, category, unit FROM products WHERE type='实物产品' AND stock > 0",
                        conn)

    if prods.empty:
        st.warning("当前没有可扣除的库存产品")
        return

    # 2. 选择界面
    p_names = prods['prod_name'].tolist()
    sel_p = st.selectbox("选择要扣除的产品", p_names)

    info = prods[prods['prod_name'] == sel_p].iloc[0]
    db_unit = info['unit']  # 数据库中的原始单位，如“盒”或“套”
    db_spec = int(info['category']) if str(info['category']).isdigit() else 1  # 规格系数

    col1, col2 = st.columns(2)
    with col1:
        # --- 修改点：动态显示单位选项 ---
        # 选项 1: 原始单位（盒/套/瓶）
        # 选项 2: 拆分单位（片/支/次）

        unit_options = [f"按{db_unit}扣除", "按片/支/次扣除"]
        deduct_type = st.radio("扣除单位", unit_options)

    with col2:
        num = st.number_input("扣除数量", min_value=0.1 if "按" + db_unit in deduct_type else 1.0, value=1.0, step=1.0)

    reason = st.selectbox("扣除原因", ["店用消耗", "产品过期", "破损丢弃", "其他原因"])
    note = st.text_input("备注说明")

    if st.button("🔥 确认扣除", use_container_width=True, type="primary"):
        # --- 修改点：完善计算逻辑 ---
        if "按片/支/次扣除" in deduct_type:
            # 如果按片扣，需要除以规格转化回“盒”
            # 例如：扣 5 片，规格 10，则库存减 0.5 盒
            final_deduct = num / db_spec
            display_unit = "片/支/次"
        else:
            # 如果按盒扣，直接减去输入的数字
            final_deduct = num
            display_unit = db_unit

        if final_deduct > info['stock']:
            st.error(f"库存不足！剩余 {info['stock']} {db_unit}")
        else:
            try:
                cur = conn.cursor()
                # 更新库存：使用 MAX(0, ...) 确保不会减成负数
                cur.execute("UPDATE products SET stock = MAX(0, stock - ?), last_updated = datetime('now','localtime') WHERE prod_name = ?", (final_deduct, sel_p))

                # 写入系统记录
                cur.execute(
                    "INSERT INTO records (member_phone, date, items, total_amount, status, staff_name) VALUES (?, datetime('now','localtime'), ?, 0, '非销售损耗', ?)",
                    ("SYSTEM", f"{reason}: {sel_p} {num}{display_unit}", note if note else "后台扣除")
                )
                conn.commit()
                st.success(f"✅ 成功扣除 {num} {display_unit}")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"操作失败: {e}")


# --- 核心入库函数（请务必放在上面逻辑的下方或上方） ---
def save_batch_to_db(df, conn):
    cur = conn.cursor()
    count = 0
    # 自动识别列名（兼容：手机、电话、联系方式等）
    col_map = {
        'name': next((c for c in df.columns if '名' in c), '姓名'),
        'phone': next((c for c in df.columns if '号' in c or '话' in c), '手机号')
    }

    for _, row in df.iterrows():
        try:
            name = str(row[col_map['name']]).strip()
            phone = str(row[col_map['phone']]).strip()
            if name == 'nan' or phone == 'nan': continue

            balance = row.get('余额', 0.0)
            debt = row.get('欠款', 0.0)
            note = row.get('备注', "")

            # INSERT OR IGNORE 确保手机号重复时不会报错
            cur.execute("""
                INSERT OR IGNORE INTO members (name, phone, balance, debt, note, reg_date)
                VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))
            """, (name, phone, balance, debt, note))
            if cur.rowcount > 0: count += 1
        except:
            continue

    conn.commit()
    st.toast(f"✅ 成功导入 {count} 位新会员！", icon="🎊")


@st.dialog("⚠️ 确认删除会员")
def confirm_delete_member(phone, name):
    st.warning(f"你正在尝试删除会员 **{name}**（{phone}）")
    st.caption("此操作将永久删除该会员的所有信息，包括：\n- 个人资料\n- 所有购买记录\n- 所有持有资产（次卡/产品）")

    # 再次检查余额和欠款（防止在弹出对话框期间被修改）
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT balance, debt FROM members WHERE phone=?", (phone,))
    row = cur.fetchone()
    if row is None:
        st.error("会员不存在，可能已被删除")
        return

    balance, debt = row
    if balance != 0 or debt != 0:
        st.error(f"❌ 无法删除：该会员尚有余额 ¥{balance:.2f} 或欠款 ¥{debt:.2f}，请先结清。")
        return

    st.write("### 请输入会员姓名以确认删除")
    confirm_name = st.text_input("输入会员姓名", placeholder=name)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 永久删除", type="primary", use_container_width=True):
            if confirm_name.strip() != name:
                st.error("姓名输入错误，删除已取消")
                return
            try:
                cur.execute("DELETE FROM salon_items WHERE member_phone=?", (phone,))
                cur.execute("DELETE FROM records WHERE member_phone=?", (phone,))
                cur.execute("DELETE FROM members WHERE phone=?", (phone,))
                conn.commit()
                st.success(f"✅ 会员 {name} 已永久删除")
                import time
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"删除失败：{e}")
    with col2:
        if st.button("取消", use_container_width=True):
            st.rerun()


@st.dialog("⚠️ 批量删除会员")
def confirm_batch_delete():
    conn = get_conn()
    cur = conn.cursor()

    phones = st.session_state.selected_members
    # 获取这些会员的信息
    placeholders = ','.join(['?'] * len(phones))
    df_members = pd.read_sql(f"SELECT phone, name, balance, debt FROM members WHERE phone IN ({placeholders})", conn,
                             params=phones)

    # 分类：可删除 vs 不可删除
    can_delete = []
    cannot_delete = []
    for _, row in df_members.iterrows():
        if row['balance'] == 0 and row['debt'] == 0:
            can_delete.append((row['phone'], row['name']))
        else:
            cannot_delete.append((row['phone'], row['name'], row['balance'], row['debt']))

    if cannot_delete:
        st.error("以下会员因余额或欠款不为0，无法删除：")
        for phone, name, bal, debt in cannot_delete:
            st.write(f"- {name} ({phone}) : 余额 ¥{bal}, 欠款 ¥{debt}")
        st.info("请先结清欠款或清空余额后再试。")
        return

    if not can_delete:
        st.info("没有可删除的会员")
        return

    st.warning(f"即将永久删除以下 {len(can_delete)} 位会员的所有信息：")
    for phone, name in can_delete:
        st.write(f"- {name} ({phone})")

    st.write("### 请输入 `确认删除` 以继续")
    confirm_text = st.text_input("", placeholder="确认删除")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 永久删除", type="primary", use_container_width=True):
            if confirm_text.strip() != "确认删除":
                st.error("输入错误，删除已取消")
                return
            try:
                cur = conn.cursor()
                for phone, name in can_delete:
                    cur.execute("DELETE FROM salon_items WHERE member_phone=?", (phone,))
                    cur.execute("DELETE FROM records WHERE member_phone=?", (phone,))
                    cur.execute("DELETE FROM members WHERE phone=?", (phone,))
                conn.commit()
                st.success(f"✅ 已成功删除 {len(can_delete)} 位会员")
                # 清理批量模式状态
                st.session_state.batch_delete_mode = False
                st.session_state.selected_members = []
                import time
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"删除失败：{e}")
    with col2:
        if st.button("取消", use_container_width=True):
            st.rerun()


@st.dialog("⚠️ 确认删除产品")
def confirm_delete_product(prod_name, prod_type):
    conn = get_conn()
    cur = conn.cursor()

    # 1. 检查是否被活动礼包引用
    acts = pd.read_sql("SELECT id, name, packages FROM activities", conn)
    referenced_acts = []
    for _, row in acts.iterrows():
        try:
            pkg = json.loads(row['packages'])
            if prod_name in pkg:
                referenced_acts.append(row['name'])
        except:
            pass
    if referenced_acts:
        st.error(f"无法删除：产品已被以下活动礼包引用：{', '.join(referenced_acts)}")
        return

    # 2. 检查是否有销售记录（可选，保留建议）
    records = pd.read_sql("SELECT COUNT(*) as cnt FROM records WHERE items LIKE ?", conn, params=(f'%{prod_name}%',))
    if records.iloc[0]['cnt'] > 0:
        st.error(f"无法删除：有销售记录关联该产品（{records.iloc[0]['cnt']} 条），无法删除")
        return

    # 注意：不再检查 salon_items（会员持有），允许删除
    st.warning(f"确认删除产品 **{prod_name}** 吗？此操作不可恢复。")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 确认删除", type="primary", use_container_width=True):
            try:
                cur.execute("DELETE FROM products WHERE prod_name=?", (prod_name,))
                conn.commit()
                st.success(f"✅ 产品 {prod_name} 已删除")
                import time
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"删除失败: {e}")
    with col2:
        if st.button("取消", use_container_width=True):
            st.rerun()
