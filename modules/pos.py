import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
from db_manager import save_data

def show(data_bundle):
    st.header("💰 收银台")
    if 'cart' not in st.session_state:
        st.session_state.cart = []

    products_df = data_bundle["products"]
    members_df = data_bundle["members"]
    acts_df = data_bundle["activities"]
    config_df = data_bundle["sys_config"]
    staff_list = data_bundle["staffs"]['name'].tolist() if not data_bundle["staffs"].empty else ["店长"]

    # 欠款阈值
    limit = 500.0
    if not config_df.empty:
        debt_row = config_df[config_df['item'] == 'debt_limit']
        if not debt_row.empty:
            limit = float(debt_row['value'].values[0])

    # 会员搜索
    st.subheader("👤 会员搜索")
    q = st.text_input("🔍 搜索会员（姓名/手机号）", key="member_search")
    sel_m = None
    if q and not members_df.empty:
        members_df['phone'] = members_df['phone'].astype(str)
        mask = members_df['name'].str.contains(q, na=False) | members_df['phone'].str.contains(q, na=False)
        m_df = members_df[mask].copy()
        if not m_df.empty:
            m_df['display'] = m_df.apply(lambda x: f"{x['name']} ({x['phone']}) {'🔴' if float(x['debt']) > limit else ''}", axis=1)
            target = st.selectbox("确认选中：", m_df['display'].tolist())
            sel_m = m_df[m_df['display'] == target].iloc[0].to_dict()
            st.success(f"✅ 当前选中：{sel_m['name']} (余额: ¥{sel_m['balance']})")
        else:
            st.warning("❌ 未找到该会员")
            if st.button("➕ 快速注册新会员"):
                from modules.member import register_member_dialog
                register_member_dialog()

    st.divider()
    col_a, col_b = st.columns([1, 1.2])

    # 购物车添加逻辑（与原 pos_module 一致，略作简化）
    with col_a:
        st.subheader("🛍️ 业务选购")
        t1, t2, t3 = st.tabs(["实物产品", "服务项目", "活动礼包"])
        with t1:
            prods = products_df[(products_df['type']=='实物产品') & (products_df['stock'].astype(float) > 0)]
            if not prods.empty:
                p_name = st.selectbox("选择产品", prods['prod_name'].tolist(), key="t1")
                usage = st.radio("使用方式", ["直接带走", "在店使用"], horizontal=True, key="u1")
                qty = st.number_input("数量", 1, 100, 1, key="q1")
                if st.button("➕ 加入购物车", key="b1"):
                    item = prods[prods['prod_name'] == p_name].iloc[0]
                    st.session_state.cart.append({
                        "id": time.time(), "name": f"{p_name} ({usage})", "raw_name": p_name,
                        "price": float(item['price']), "qty": qty, "is_activity": False,
                        "is_store_use": (usage == "在店使用")
                    })
                    st.rerun()
        with t2:
            items = products_df[products_df['type']=='服务项目']
            if not items.empty:
                i_name = st.selectbox("选择项目", items['prod_name'].tolist(), key="t2")
                qty_i = st.number_input("数量", 1, 100, 1, key="q2")
                if st.button("➕ 加入购物车", key="b2"):
                    item = items[items['prod_name'] == i_name].iloc[0]
                    st.session_state.cart.append({
                        "id": time.time(), "name": f"{i_name} (在店使用)", "raw_name": i_name,
                        "price": float(item['price']), "qty": qty_i, "is_activity": False, "is_store_use": True
                    })
                    st.rerun()
        with t3:
            acts = acts_df[acts_df['is_open'].astype(str) == '1']
            if not acts.empty:
                a_name = st.selectbox("选择活动礼包", acts['name'].tolist(), key="t3")
                qty_a = st.number_input("数量", 1, 100, 1, key="q3")
                if st.button("➕ 加入购物车", key="b3"):
                    ai = acts[acts['name'] == a_name].iloc[0]
                    st.session_state.cart.append({
                        "id": time.time(), "name": f"🎁 {a_name}", "price": float(ai['price']),
                        "qty": qty_a, "is_activity": True, "packages": json.loads(ai['packages']),
                        "is_store_use": True
                    })
                    st.rerun()

    # 购物车展示与结算
    with col_b:
        st.subheader("📋 待结算清单")
        if not st.session_state.cart:
            st.info("购物车是空的")
        else:
            total = 0
            for idx, item in enumerate(st.session_state.cart):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1.5, 1], vertical_alignment="center")
                    c1.write(f"**{item['name']}**")
                    subtotal = item['price'] * item['qty']
                    total += subtotal
                    c2.write(f"¥{subtotal:.2f}")
                    if c3.button("🗑️", key=f"del_{item['id']}"):
                        st.session_state.cart.pop(idx)
                        st.rerun()
            st.divider()
            st.markdown(f"### 总金额：:red[¥{total:.2f}]")
            method = st.radio("支付方式", ["现结", "余额扣款", "挂账"], horizontal=True)
            staff = st.selectbox("经办人", staff_list)

            if st.button("🚀 确认结算", type="primary", use_container_width=True):
                if not sel_m:
                    st.error("请先确认会员！")
                elif method == "余额扣款" and float(sel_m['balance']) < total:
                    st.error("余额不足！")
                else:
                    with st.spinner("结算中..."):
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        # 重新读取最新数据（避免并发冲突）
                        from db_manager import read_data
                        members_df = read_data("members")
                        products_df = read_data("products")
                        salon_df = read_data("salon_items")
                        records_df = read_data("records")

                        # 更新会员
                        m_idx = members_df[members_df['phone'] == sel_m['phone']].index[0]
                        if method == "余额扣款":
                            members_df.at[m_idx, 'balance'] = float(members_df.at[m_idx, 'balance']) - total
                        elif method == "挂账":
                            members_df.at[m_idx, 'debt'] = float(members_df.at[m_idx, 'debt']) + total

                        # 处理购物车：扣库存，增加院装资产
                        for item in st.session_state.cart:
                            if item['is_activity']:
                                for p_n, p_q in item['packages'].items():
                                    t_qty = p_q * item['qty']
                                    p_idx = products_df[products_df['prod_name'] == p_n].index
                                    if not p_idx.empty:
                                        products_df.at[p_idx[0], 'stock'] = max(0, float(products_df.at[p_idx[0], 'stock']) - t_qty)
                                        spec = float(products_df.at[p_idx[0], 'category']) if str(products_df.at[p_idx[0], 'category']).replace('.','').isdigit() else 1
                                        new_asset = pd.DataFrame([{
                                            "member_phone": sel_m['phone'], "item_name": p_n,
                                            "total_qty": t_qty * spec, "used_qty": 0,
                                            "status": "使用中", "unit": products_df.at[p_idx[0], 'unit'], "buy_date": now_str
                                        }])
                                        salon_df = pd.concat([salon_df, new_asset], ignore_index=True)
                            else:
                                p_idx = products_df[products_df['prod_name'] == item['raw_name']].index
                                if not p_idx.empty:
                                    products_df.at[p_idx[0], 'stock'] = max(0, float(products_df.at[p_idx[0], 'stock']) - item['qty'])
                                    if item['is_store_use']:
                                        spec = float(products_df.at[p_idx[0], 'category']) if str(products_df.at[p_idx[0], 'category']).replace('.','').isdigit() else 1
                                        new_asset = pd.DataFrame([{
                                            "member_phone": sel_m['phone'], "item_name": item['raw_name'],
                                            "total_qty": item['qty'] * spec, "used_qty": 0,
                                            "status": "使用中", "unit": products_df.at[p_idx[0], 'unit'], "buy_date": now_str
                                        }])
                                        salon_df = pd.concat([salon_df, new_asset], ignore_index=True)

                        # 保存更新
                        save_data("members", members_df)
                        save_data("products", products_df)
                        save_data("salon_items", salon_df)

                        # 记录流水
                        desc = ",".join([i['name'] for i in st.session_state.cart])
                        new_rec = pd.DataFrame([{
                            "member_phone": sel_m['phone'], "date": now_str,
                            "items": desc, "total_amount": total, "status": method, "staff_name": staff
                        }])
                        save_data("records", pd.concat([records_df, new_rec], ignore_index=True))

                        st.balloons()
                        st.success("结算成功！")
                        st.session_state.cart = []
                        time.sleep(1)
                        st.rerun()