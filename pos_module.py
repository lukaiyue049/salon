import streamlit as st
import pandas as pd
import json
from datetime import datetime
from db_manager import get_conn

def show(staff_list):
    st.header("💰 收银台")
    conn = get_conn()
    if 'cart' not in st.session_state:
        st.session_state.cart = []

    # --- 修复点 1：安全获取红名阈值，防止 index 0 报错 ---
    limit_res = pd.read_sql("SELECT value FROM sys_config WHERE item='debt_limit'", conn)
    limit = float(limit_res.iloc[0, 0]) if not limit_res.empty else 500.0

    # 1. 必须先选会员
    st.subheader("👤 会员搜索")
    q = st.text_input("🔍 搜索会员（姓名/手机号）", key="member_search")
    sel_m = None

    if q:
        m_df = pd.read_sql("SELECT * FROM members WHERE name LIKE ? OR phone LIKE ?", conn, params=(f'%{q}%', f'%{q}%'))

        if not m_df.empty:
            m_df['display'] = m_df.apply(lambda x: f"{x['name']} ({x['phone']}) {'🔴' if x['debt'] > limit else ''}",
                                         axis=1)
            target = st.selectbox("确认选中：", m_df['display'].tolist())
            # 将选中的会员存入 sel_m
            sel_m = m_df[m_df['display'] == target].iloc[0].to_dict()
            st.success(f"✅ 当前选中：{sel_m['name']}")
        else:
            # --- 修改这里：增加快速注册按钮 ---
            st.warning("❌ 未找到该会员")

            # 导入注册模块（如果报错循环引用，就把这行写在 if 里面）
            import query_module

            # 如果输入的正好是手机号（比如长度为11位且全是数字），我们就把它传给注册窗口
            potential_phone = q if (q.isdigit() and len(q) == 11) else ""

            if st.button("➕ 没找到？点击快速注册新会员", type="primary"):
                # 调用 query_module 的注册函数，并传入当前搜索的号码
                query_module.register_dialog(default_phone=potential_phone)

    st.divider()

    # 2. 选购区域
    # --- pos_module.py 选购中心部分 ---

    st.subheader("🛍️ 选购中心")
    
    # 1. 统一获取数据并打标签
    df_prods = pd.read_sql("SELECT prod_name as name, price, stock, unit, '单品' as cat_type FROM products", conn)
    df_acts = pd.read_sql("SELECT name, price, '不限' as stock, '套' as unit, '活动礼包' as cat_type, packages FROM activities", conn)
    
    # 合并展示
    df_all = pd.concat([df_prods, df_acts], ignore_index=True)
    
    # 搜索功能
    search_kv = st.text_input("🔍 搜索产品或活动礼包", placeholder="输入关键词...")
    if search_kv:
        df_all = df_all[df_all['name'].str.contains(search_kv, na=False)]
    
    # 渲染列表
    for _, item in df_all.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1.5])
            
            # 类别标签颜色区分
            tag_color = "blue" if item['cat_type'] == "单品" else "orange"
            c1.markdown(f"**{item['name']}** :{tag_color}[[{item['cat_type']}]]")
            c1.caption(f"单价: ¥{item['price']} | 库存: {item['stock']}")
            
            qty = c2.number_input("数量", min_value=1, step=1, key=f"add_qty_{item['name']}")
            
            if c3.button("➕ 加入", key=f"btn_add_{item['name']}", use_container_width=True):
                # 构建存入购物车的字典
                entry = {
                    "name": item['name'],
                    "price": item['price'],
                    "qty": qty,
                    "unit": item['unit'],
                    "cat_type": item['cat_type'],
                    "is_activity": (item['cat_type'] == "活动礼包")
                }
                # 如果是礼包，解出里面的详细内容
                if entry['is_activity']:
                    import json
                    entry['packages'] = json.loads(item['packages'])
                
                st.session_state.cart.append(entry)
                st.toast(f"已加入购物车: {item['name']}")
    
                else:
                    st.warning(f"⚠️ 库中暂无可用的{p_type}，请先进行补货。")
    
            # pos_module.py 活动礼包部分
            with t2:
                acts = pd.read_sql("SELECT * FROM activities WHERE is_open=1", conn)
                if not acts.empty:
                    an = st.selectbox("选择活动", acts['name'].tolist())
                    
                    # 清晰的大按钮选择
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        use_in_shop = st.button("🏠 在店使用", use_container_width=True, type="primary")
                    with col_btn2:
                        take_away = st.button("📦 直接带走", use_container_width=True)
                    
                    if use_in_shop or take_away:
                        ai = acts[acts['name'] == an].iloc[0]
                        st.session_state.cart.append({
                            "id": datetime.now().timestamp(),
                            "name": f"🎁 {an}",
                            "price": ai['price'],
                            "qty": 1,
                            "type": "act",
                            "act_id": ai['id'],
                            "usage": "store" if use_in_shop else "takeaway"
                        })
                        st.rerun()

    with col_b:
        st.subheader("📋 结算")
        if not st.session_state.cart:
            st.write("购物车是空的")
        else:
            for idx, item in enumerate(st.session_state.cart):
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.write(f"{item['name']} x{item['qty']}")
                c2.write(f"¥{item['price'] * item['qty']}")
                if c3.button("🗑️ 删除", key=f"del_{item['id']}", use_container_width=True):
                    st.session_state.cart.pop(idx)
                st.rerun()

            total = sum(i['price'] * i['qty'] for i in st.session_state.cart)
            st.divider()
            st.markdown(f"### 总额: :red[¥{total:.2f}]")
            # 按钮组：支付方式（三个选项）
            method = st.radio("支付方式", ["现结", "余额扣款", "挂账"], horizontal=True)
            staff = st.selectbox("👤 经办人", staff_list, key="pos_staff")

            # --- 修复点 2：合并确认收银按钮逻辑，并处理库存消耗 ---
            if st.button("🚀 确认收银", type="primary", use_container_width=True):
                if not sel_m:
                    st.error("请先在第一步搜索并确认办理会员！")
                elif method == "余额扣款" and sel_m['balance'] < total:
                    st.error(f"余额不足！当前余额: ¥{sel_m['balance']}")
                else:
                    try:
                        cur = conn.cursor()
                        today_str = datetime.now().strftime("%Y-%m-%d")
                        # 1. 扣款/记账逻辑
                        if method == "余额扣款":
                            cur.execute("UPDATE members SET balance = balance - ? WHERE phone = ?", (total, sel_m['phone']))
                        elif method == "挂账":
                            cur.execute("UPDATE members SET debt = debt + ? WHERE phone = ?", (total, sel_m['phone']))

                        # 2. 处理资产入库与实物库存同步消耗
                        # --- pos_module.py 确认收银循环修正版 ---

                        for i in st.session_state.cart:
                            if i['type'] == 'act':
                                # --- 情况 A：处理优惠活动/礼包 ---
                                act_data = pd.read_sql(f"SELECT packages FROM activities WHERE id={i['act_id']}", conn)
                                if not act_data.empty:
                                    pkg = json.loads(act_data.iloc[0, 0])
                                    for prod_n, prod_q in pkg.items():
                                        # 1. 查询该产品的规格折算率 (防止礼包里的东西也需要翻倍)
                                        spec_res = pd.read_sql("SELECT category FROM products WHERE prod_name=?", conn,
                                                               params=(prod_n,))
                                        p_spec = int(spec_res.iloc[0, 0]) if not spec_res.empty and str(
                                            spec_res.iloc[0, 0]).isdigit() else 1

                                        # 2. 扣除库存 (礼包通常默认扣除的就是实物单位)
                                        cur.execute("UPDATE products SET stock = MAX(0, stock - ?), last_updated = datetime('now','localtime') WHERE prod_name = ?",
                                            (prod_q, prod_n))

                                        # 3. 存入会员资产 (数量 * 折算率)
                                        actual_salon_q = prod_q * p_spec
                                        cur.execute(
                                            "INSERT INTO salon_items (member_phone, item_name, total_qty, status, buy_date) VALUES (?,?,?,?,?)",
                                            (sel_m['phone'], prod_n, actual_salon_q, "使用中", today_str))

                            else:
                                # --- 情况 B：处理普通单品 (对应你改动的地方) ---
                                # 1. 扣除库存：使用 i['qty'] (买 1 盒扣 1 盒)
                                cur.execute("UPDATE products SET stock = MAX(0, stock - ?), last_updated = datetime('now','localtime') WHERE prod_name = ?",
                                    (i['qty'], i['raw_name']))

                                # 2. 存入会员资产：使用 i['salon_qty'] (买 1 盒资产加 10 片)
                                if i.get('is_salon'):
                                    cur.execute(
                                        "INSERT INTO salon_items (member_phone, item_name, total_qty, status, buy_date) VALUES (?,?,?,?,?)",
                                        (sel_m['phone'], i['raw_name'], i['salon_qty'], "使用中", today_str))

                        # 3. 记录流水
                        cur.execute(
                            "INSERT INTO records (member_phone, date, items, total_amount, status, staff_name) VALUES (?, datetime('now','localtime'), ?, ?, ?, ?)",
                            (sel_m['phone'], f"柜台结算", total, method, staff))

                        conn.commit()

                        # --- 核心修改：结算成功反馈 ---
                        st.balloons()  # 撒花特效
                        st.success(f"🎉 结算成功！收款金额：¥{total:.2f}")
                        st.toast(f"✅ 已记录流水并更新会员资产", icon="💰")

                        # 清空购物车
                        st.session_state.cart = []

                        # 强制停留 1.5 秒，让老板看清“结算成功”
                        import time
                        time.sleep(1.5)

                        st.rerun()
                        # ---------------------------

                    except Exception as e:
                        st.error(f"结算出错: {e}")
