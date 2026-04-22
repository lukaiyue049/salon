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
                query_module.register_dialog(default_phone=potential_phone)

    st.divider()

    # 2. 选购区域与结算区域布局
    col_a, col_b = st.columns([1, 1.2])

    with col_a:
        st.subheader("🛍️ 业务选购")
        
        # --- 核心修改：合并单品与活动礼包数据 ---
        # 获取单品
        df_prods = pd.read_sql("SELECT prod_name as name, price, stock, unit, '单品' as cat_type, category FROM products", conn)
        # 获取礼包
        df_acts = pd.read_sql("SELECT name, price, '不限' as stock, '套' as unit, '活动礼包' as cat_type, packages, id as act_id FROM activities WHERE is_open=1", conn)
        
        # 合并展示
        df_all = pd.concat([df_prods, df_acts], ignore_index=True)
        
        # 搜索框
        search_item = st.text_input("🔍 输入名称快速搜索产品或礼包", placeholder="如：补水、套餐...")
        if search_item:
            df_all = df_all[df_all['name'].str.contains(search_item, na=False)]

        # 循环渲染选购清单
        for _, item in df_all.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1.5])
                
                # 样式区分
                is_act = (item['cat_type'] == "活动礼包")
                tag_color = "orange" if is_act else "blue"
                c1.markdown(f"**{item['name']}** :{tag_color}[[{item['cat_type']}]]")
                c1.caption(f"单价: ¥{item['price']} | 库存: {item['stock']}")
                
                # 数量选择
                qty = c2.number_input("数量", min_value=1, step=1, key=f"qty_{item['name']}")
                
                if c3.button("➕ 加入", key=f"btn_{item['name']}", use_container_width=True):
                    entry = {
                        "id": datetime.now().timestamp(),
                        "name": item['name'],
                        "price": item['price'],
                        "qty": qty,
                        "unit": item['unit'],
                        "cat_type": item['cat_type'],
                        "is_activity": is_act,
                        "is_store_use": True # 默认开启存店
                    }
                    # 礼包解析内容，单品记录原始名
                    if is_act:
                        entry['packages'] = json.loads(item['packages'])
                        entry['act_id'] = item['act_id']
                    else:
                        entry['raw_name'] = item['name']
                    
                    st.session_state.cart.append(entry)
                    st.toast(f"已加入购物车: {item['name']}")
                    st.rerun()

    with col_b:
        st.subheader("📋 结算清单")
        if not st.session_state.cart:
            st.info("购物车是空的，请从左侧选购")
        else:
            total = 0
            for idx, item in enumerate(st.session_state.cart):
                with st.container(border=True):
                    # 第一行：名称与删除
                    line1_1, line1_2 = st.columns([4, 1])
                    line1_1.write(f"**{item['name']}**")
                    if line1_2.button("🗑️", key=f"del_{item['id']}"):
                        st.session_state.cart.pop(idx)
                        st.rerun()
                    
                    # 第二行：价格数量与存店开关
                    line2_1, line2_2 = st.columns([1, 1])
                    subtotal = item['price'] * item['qty']
                    total += subtotal
                    line2_1.write(f"¥{item['price']} x {item['qty']} = :red[¥{subtotal}]")
                    item['is_store_use'] = line2_2.toggle("存店使用", value=item['is_store_use'], key=f"st_{item['id']}")
                    
                    # 如果是礼包，显示内容清单
                    if item.get('is_activity'):
                        with st.expander("📝 礼包详细清单", expanded=False):
                            for p_name, p_qty in item['packages'].items():
                                st.caption(f"• {p_name} x {p_qty * item['qty']}")

            st.divider()
            st.markdown(f"### 总金额：:red[¥{total:.2f}]")
            
            method = st.radio("支付方式", ["现结", "余额扣款", "挂账"], horizontal=True)
            staff = st.selectbox("👤 经办人", staff_list)

            if st.button("🚀 确认收银结算", type="primary", use_container_width=True):
                if not sel_m:
                    st.error("❌ 请先搜索并确认会员！")
                elif method == "余额扣款" and sel_m['balance'] < total:
                    st.error(f"❌ 余额不足！当前余额: ¥{sel_m['balance']}")
                else:
                    cur = conn.cursor()
                    try:
                        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # 1. 扣款/记账逻辑
                        if method == "余额扣款":
                            cur.execute("UPDATE members SET balance = balance - ? WHERE phone = ?", (total, sel_m['phone']))
                        elif method == "挂账":
                            cur.execute("UPDATE members SET debt = debt + ? WHERE phone = ?", (total, sel_m['phone']))

                        # 2. 遍历购物车处理库存与资产
                        for i in st.session_state.cart:
                            is_store = i.get('is_store_use', True)
                            
                            # 情况 A：礼包
                            if i.get('is_activity'):
                                for prod_n, prod_q in i['packages'].items():
                                    total_physical = prod_q * i['qty']
                                    # 扣库存
                                    cur.execute("UPDATE products SET stock = MAX(0, stock - ?), last_updated = datetime('now','localtime') WHERE prod_name = ?", (total_physical, prod_n))
                                    # 存资产
                                    if is_store:
                                        res = pd.read_sql("SELECT category, unit FROM products WHERE prod_name=?", conn, params=(prod_n,))
                                        p_spec = int(res.iloc[0, 0]) if not res.empty and str(res.iloc[0, 0]).isdigit() else 1
                                        p_unit = res.iloc[0, 1] if not res.empty and res.iloc[0, 1] else "次"
                                        actual_salon_q = total_physical * p_spec
                                        cur.execute("INSERT INTO salon_items (member_phone, item_name, total_qty, used_qty, status, unit, buy_date) VALUES (?, ?, ?, 0, ?, ?, ?)",
                                                    (sel_m['phone'], prod_n, actual_salon_q, "使用中", p_unit, today_str))
                            
                            # 情况 B：单品
                            else:
                                # 扣库存
                                cur.execute("UPDATE products SET stock = MAX(0, stock - ?), last_updated = datetime('now','localtime') WHERE prod_name = ?", (i['qty'], i['name']))
                                # 存资产
                                if is_store:
                                    res = pd.read_sql("SELECT category, unit FROM products WHERE prod_name=?", conn, params=(i['name'],))
                                    p_spec = int(res.iloc[0, 0]) if not res.empty and str(res.iloc[0, 0]).isdigit() else 1
                                    p_unit = res.iloc[0, 1] if not res.empty and res.iloc[0, 1] else "次"
                                    actual_salon_q = i['qty'] * p_spec
                                    cur.execute("INSERT INTO salon_items (member_phone, item_name, total_qty, used_qty, status, unit, buy_date) VALUES (?, ?, ?, 0, ?, ?, ?)",
                                                (sel_m['phone'], i['name'], actual_salon_q, "使用中", p_unit, today_str))

                        # 3. 记录流水
                        items_summary = ",".join([f"{item['name']}x{item['qty']}" for item in st.session_state.cart])
                        cur.execute("INSERT INTO records (member_phone, date, items, total_amount, status, staff_name) VALUES (?, datetime('now','localtime'), ?, ?, ?, ?)",
                                    (sel_m['phone'], items_summary, total, method, staff))
                        
                        conn.commit()
                        st.balloons()
                        st.success(f"🎉 结算成功！收款：¥{total:.2f}")
                        st.session_state.cart = []
                        time.sleep(1.5)
                        st.rerun()

                    except Exception as e:
                        conn.rollback()
                        st.error(f"结算失败: {e}")
