import streamlit as st
import pandas as pd
import json
from datetime import datetime
from db_manager import get_conn
import time

def show(staff_list):
    st.header("💰 收银台")
    conn = get_conn()
    if 'cart' not in st.session_state:
        st.session_state.cart = []

    # 获取红名阈值
    limit_res = pd.read_sql("SELECT value FROM sys_config WHERE item='debt_limit'", conn)
    limit = float(limit_res.iloc[0, 0]) if not limit_res.empty else 500.0

    # 1. 会员搜索
    st.subheader("👤 会员搜索")
    q = st.text_input("🔍 搜索会员（姓名/手机号）", key="member_search")
    sel_m = None

    if q:
        m_df = pd.read_sql("SELECT * FROM members WHERE name LIKE ? OR phone LIKE ?", conn, params=(f'%{q}%', f'%{q}%'))
        if not m_df.empty:
            m_df['display'] = m_df.apply(lambda x: f"{x['name']} ({x['phone']}) {'🔴' if x['debt'] > limit else ''}", axis=1)
            target = st.selectbox("确认选中：", m_df['display'].tolist())
            sel_m = m_df[m_df['display'] == target].iloc[0].to_dict()
            st.success(f"✅ 当前选中：{sel_m['name']}")
        else:
            st.warning("❌ 未找到该会员")
            import query_module
            potential_phone = q if (q.isdigit() and len(q) == 11) else ""
            if st.button("➕ 快速注册新会员", type="primary"):
                query_module.register_member_dialog()

    st.divider()

    # 2. 布局
    col_a, col_b = st.columns([1, 1.2])

    with col_a:
        st.subheader("🛍️ 业务选购")
        # 按照你的要求分类：单品 / 项目 / 礼包
        t1, t2, t3 = st.tabs(["💊 实物产品", "💆 服务项目", "🎁 活动礼包"])

        # --- 分类1：实物产品 ---
        with t1:
            prods = pd.read_sql("SELECT * FROM products WHERE type='实物产品' AND stock > 0", conn)
            if not prods.empty:
                p_name = st.selectbox("选择产品", prods['prod_name'].tolist(), key="sel_t1")
                usage = st.radio("使用方式", ["直接带走", "在店使用"], horizontal=True, key="usage_t1")
                qty = st.number_input("数量", 1, 100, 1, key="qty_t1")
                if st.button("➕ 加入购物车", key="btn_t1", use_container_width=True, type="primary"):
                    item_info = prods[prods['prod_name'] == p_name].iloc[0]
                    st.session_state.cart.append({
                        "id": datetime.now().timestamp(),
                        "name": f"{p_name} ({usage})",
                        "raw_name": p_name,
                        "price": item_info['price'],
                        "qty": qty,
                        "is_activity": False,
                        "is_store_use": True if usage == "在店使用" else False
                    })
                    st.rerun()
            else:
                st.info("库中暂无实物产品")

        # --- 分类2：服务项目 ---
        with t2:
            items = pd.read_sql("SELECT * FROM products WHERE type='服务项目'", conn)
            if not items.empty:
                i_name = st.selectbox("选择项目", items['prod_name'].tolist(), key="sel_t2")
                # 项目通常默认在店用，但也可以带走（如代金券性质）
                usage_i = st.radio("使用方式", ["在店使用", "直接带走"], horizontal=True, key="usage_t2")
                qty_i = st.number_input("数量", 1, 100, 1, key="qty_t2")
                if st.button("➕ 加入购物车", key="btn_t2", use_container_width=True, type="primary"):
                    item_info = items[items['prod_name'] == i_name].iloc[0]
                    st.session_state.cart.append({
                        "id": datetime.now().timestamp(),
                        "name": f"{i_name} ({usage_i})",
                        "raw_name": i_name,
                        "price": item_info['price'],
                        "qty": qty_i,
                        "is_activity": False,
                        "is_store_use": True if usage_i == "在店使用" else False
                    })
                    st.rerun()

        # --- 分类3：活动礼包 ---
        with t3:
            acts = pd.read_sql("SELECT * FROM activities WHERE is_open=1", conn)
            if not acts.empty:
                a_name = st.selectbox("选择活动礼包", acts['name'].tolist(), key="sel_t3")
                usage_a = st.radio("使用方式", ["在店使用", "直接带走"], horizontal=True, key="usage_t3")
                qty_a = st.number_input("数量", 1, 100, 1, key="qty_t3")
                if st.button("➕ 加入购物车", key="btn_t3", use_container_width=True, type="primary"):
                    ai = acts[acts['name'] == a_name].iloc[0]
                    st.session_state.cart.append({
                        "id": datetime.now().timestamp(),
                        "name": f"🎁 {a_name} ({usage_a})",
                        "price": ai['price'],
                        "qty": qty_a,
                        "is_activity": True,
                        "packages": json.loads(ai['packages']),
                        "is_store_use": True if usage_a == "在店使用" else False
                    })
                    st.rerun()
            else:
                st.info("当前没有开放的活动礼包")

    with col_b:
        st.subheader("📋 待结算清单")
        if not st.session_state.cart:
            st.info("购物车是空的")
        else:
            total = 0
            for idx, item in enumerate(st.session_state.cart):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1.5, 1])
                    c1.write(f"**{item['name']}**")
                    subtotal = item['price'] * item['qty']
                    total += subtotal
                    c2.write(f"¥{subtotal}")
                    
                    # 只能整项删除
                    if c3.button("🗑️", key=f"del_{item['id']}"):
                        st.session_state.cart.pop(idx)
                        st.rerun()
                    
                    # 如果是礼包，折叠展示内容
                    if item.get('is_activity'):
                        with st.expander("查看包含项目"):
                            for p_n, p_q in item['packages'].items():
                                st.caption(f"• {p_n} x {p_q * item['qty']}")

            st.divider()
            st.markdown(f"### 总金额：:red[¥{total:.2f}]")
            method = st.radio("支付方式", ["现结", "余额扣款", "挂账"], horizontal=True)
            staff = st.selectbox("👤 经办人", staff_list)

            if st.button("🚀 确认结算", type="primary", use_container_width=True):
                if not sel_m:
                    st.error("请先确认会员！")
                elif method == "余额扣款" and sel_m['balance'] < total:
                    st.error("余额不足！")
                else:
                    cur = conn.cursor()
                    try:
                        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # 1. 扣款逻辑
                        if method == "余额扣款":
                            cur.execute("UPDATE members SET balance = balance - ? WHERE phone = ?", (total, sel_m['phone']))
                        elif method == "挂账":
                            cur.execute("UPDATE members SET debt = debt + ? WHERE phone = ?", (total, sel_m['phone']))

                        # 2. 处理资产与库存
                        for i in st.session_state.cart:
                            is_store = i['is_store_use']
                            
                            if i['is_activity']:
                                # 礼包拆解
                                for prod_n, prod_q in i['packages'].items():
                                    t_qty = prod_q * i['qty']
                                    cur.execute("UPDATE products SET stock = MAX(0, stock - ?) WHERE prod_name = ?", (t_qty, prod_n))
                                    if is_store:
                                        res = pd.read_sql("SELECT category, unit FROM products WHERE prod_name=?", conn, params=(prod_n,))
                                        spec = int(res.iloc[0,0]) if not res.empty and str(res.iloc[0,0]).isdigit() else 1
                                        unit = res.iloc[0,1] if not res.empty else "次"
                                        cur.execute("INSERT INTO salon_items (member_phone, item_name, total_qty, used_qty, status, unit, buy_date) VALUES (?,?,?,0,'使用中',?,?)",
                                                    (sel_m['phone'], prod_n, t_qty * spec, unit, today_str))
                            else:
                                # 单品处理
                                cur.execute("UPDATE products SET stock = MAX(0, stock - ?) WHERE prod_name = ?", (i['qty'], i['raw_name']))
                                if is_store:
                                    res = pd.read_sql("SELECT category, unit FROM products WHERE prod_name=?", conn, params=(i['raw_name'],))
                                    spec = int(res.iloc[0,0]) if not res.empty and str(res.iloc[0,0]).isdigit() else 1
                                    unit = res.iloc[0,1] if not res.empty else "次"
                                    cur.execute("INSERT INTO salon_items (member_phone, item_name, total_qty, used_qty, status, unit, buy_date) VALUES (?,?,?,0,'使用中',?,?)",
                                                (sel_m['phone'], i['raw_name'], i['qty'] * spec, unit, today_str))

                        # 3. 记录流水
                        desc = ",".join([i['name'] for i in st.session_state.cart])
                        cur.execute("INSERT INTO records (member_phone, date, items, total_amount, status, staff_name) VALUES (?, datetime('now','localtime'), ?, ?, ?, ?)",
                                    (sel_m['phone'], desc, total, method, staff))
                        
                        conn.commit()
                        st.balloons()
                        st.success("结算成功！")
                        st.session_state.cart = []
                        time.sleep(1.2)
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"出错: {e}")
