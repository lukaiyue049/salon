import streamlit as st
import pandas as pd
import json
from datetime import datetime
# 修改：引入云端数据库接口
from db_manager import read_data, save_data
import time

def show(staff_list):
    st.header("💰 收银台")
    
    if 'cart' not in st.session_state:
        st.session_state.cart = []

    # 1. 云端获取配置和基础数据
    config_df = read_data("sys_config")
    limit = 500.0
    if not config_df.empty and 'debt_limit' in config_df['item'].values:
        limit = float(config_df[config_df['item']=='debt_limit']['value'].values[0])

    members_df = read_data("members")
    
    # 2. 会员搜索
    st.subheader("👤 会员搜索")
    q = st.text_input("🔍 搜索会员（姓名/手机号）", key="member_search")
    sel_m = None

    if q and not members_df.empty:
        # 在内存中过滤会员
        m_df = members_df[
            (members_df['name'].str.contains(q, na=False)) | 
            (members_df['phone'].str.contains(q, na=False))
        ].copy()
        
        if not m_df.empty:
            m_df['display'] = m_df.apply(lambda x: f"{x['name']} ({x['phone']}) {'🔴' if float(x['debt']) > limit else ''}", axis=1)
            target = st.selectbox("确认选中：", m_df['display'].tolist())
            sel_m = m_df[m_df['display'] == target].iloc[0].to_dict()
            st.success(f"✅ 当前选中：{sel_m['name']} (余额: ¥{sel_m['balance']})")
        else:
            st.warning("❌ 未找到该会员")
            if st.button("➕ 快速注册新会员"):
                import query_module
                query_module.register_member_dialog()

    st.divider()

    # 3. 布局与选购
    col_a, col_b = st.columns([1, 1.2])

    with col_a:
        st.subheader("🛍️ 业务选购")
        t1, t2, t3 = st.tabs(["🛍️ 实物产品", "💆 服务项目", "🎁 活动礼包"])
        
        products_df = read_data("products")

        with t1: # 实物产品
            prods = products_df[(products_df['type']=='实物产品') & (products_df['stock'].astype(float) > 0)]
            if not prods.empty:
                p_name = st.selectbox("选择产品", prods['prod_name'].tolist(), key="sel_t1")
                usage = st.radio("使用方式", ["直接带走", "在店使用"], horizontal=True, key="usage_t1")
                qty = st.number_input("数量", 1, 100, 1, key="qty_t1")
                if st.button("➕ 加入购物车", key="btn_t1", use_container_width=True):
                    item_info = prods[prods['prod_name'] == p_name].iloc[0]
                    st.session_state.cart.append({
                        "id": time.time(),
                        "name": f"{p_name} ({usage})",
                        "raw_name": p_name,
                        "price": float(item_info['price']),
                        "qty": qty,
                        "is_activity": False,
                        "is_store_use": (usage == "在店使用")
                    })
                    st.rerun()

        with t2: # 服务项目
            items = products_df[products_df['type']=='服务项目']
            if not items.empty:
                i_name = st.selectbox("选择项目", items['prod_name'].tolist(), key="sel_t2")
                qty_i = st.number_input("数量", 1, 100, 1, key="qty_t2")
                if st.button("➕ 加入购物车", key="btn_t2", use_container_width=True):
                    item_info = items[items['prod_name'] == i_name].iloc[0]
                    st.session_state.cart.append({
                        "id": time.time(),
                        "name": f"{i_name} (在店使用)",
                        "raw_name": i_name,
                        "price": float(item_info['price']),
                        "qty": qty_i,
                        "is_activity": False,
                        "is_store_use": True
                    })
                    st.rerun()

        with t3: # 活动礼包
            acts_df = read_data("activities")
            acts = acts_df[acts_df['is_open'].astype(str) == '1']
            if not acts.empty:
                a_name = st.selectbox("选择活动礼包", acts['name'].tolist(), key="sel_t3")
                qty_a = st.number_input("数量", 1, 100, 1, key="qty_t3")
                if st.button("➕ 加入购物车", key="btn_t3", use_container_width=True):
                    ai = acts[acts['name'] == a_name].iloc[0]
                    st.session_state.cart.append({
                        "id": time.time(),
                        "name": f"🎁 {a_name}",
                        "price": float(ai['price']),
                        "qty": qty_a,
                        "is_activity": True,
                        "packages": json.loads(ai['packages']),
                        "is_store_use": True # 礼包默认入库
                    })
                    st.rerun()

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
                    c2.write(f"¥{subtotal:.2f}")
                    if c3.button("🗑️", key=f"del_{item['id']}"):
                        st.session_state.cart.pop(idx)
                        st.rerun()

            st.divider()
            st.markdown(f"### 总金额：:red[¥{total:.2f}]")
            method = st.radio("支付方式", ["现结", "余额扣款", "挂账"], horizontal=True)
            staff = st.selectbox("👤 经办人", staff_list)

            if st.button("🚀 确认结算", type="primary", use_container_width=True):
                if not sel_m:
                    st.error("请先确认会员！")
                elif method == "余额扣款" and float(sel_m['balance']) < total:
                    st.error("余额不足！")
                else:
                    # --- 开始云端同步逻辑 ---
                    with st.spinner("正在同步云端数据..."):
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # A. 更新会员资产 (余额/欠款)
                        all_members = read_data("members")
                        m_idx = all_members[all_members['phone'] == sel_m['phone']].index[0]
                        if method == "余额扣款":
                            all_members.at[m_idx, 'balance'] = float(all_members.at[m_idx, 'balance']) - total
                        elif method == "挂账":
                            all_members.at[m_idx, 'debt'] = float(all_members.at[m_idx, 'debt']) + total
                        save_data("members", all_members)

                        # B. 更新产品库存 & 院装资产
                        all_prods = read_data("products")
                        all_salon = read_data("salon_items")
                        
                        for i in st.session_state.cart:
                            if i['is_activity']:
                                # 礼包拆解逻辑
                                for p_n, p_q in i['packages'].items():
                                    t_qty = p_q * i['qty']
                                    # 扣库存
                                    p_idx_list = all_prods[all_prods['prod_name'] == p_n].index
                                    if not p_idx_list.empty:
                                        p_idx = p_idx_list[0]
                                        new_stock = max(0, float(all_prods.at[p_idx, 'stock']) - t_qty)
                                        all_prods.at[p_idx, 'stock'] = new_stock
                                        # 入库院装资产
                                        spec = float(all_prods.at[p_idx, 'category']) if str(all_prods.at[p_idx, 'category']).replace('.','').isdigit() else 1
                                        new_asset = pd.DataFrame([{
                                            "member_phone": sel_m['phone'], "item_name": p_n,
                                            "total_qty": t_qty * spec, "used_qty": 0,
                                            "status": "使用中", "unit": all_prods.at[p_idx, 'unit'], "buy_date": now_str
                                        }])
                                        all_salon = pd.concat([all_salon, new_asset], ignore_index=True)
                            else:
                                # 单品处理
                                p_idx_list = all_prods[all_prods['prod_name'] == i['raw_name']].index
                                if not p_idx_list.empty:
                                    p_idx = p_idx_list[0]
                                    all_prods.at[p_idx, 'stock'] = max(0, float(all_prods.at[p_idx, 'stock']) - i['qty'])
                                    if i['is_store_use']:
                                        spec = float(all_prods.at[p_idx, 'category']) if str(all_prods.at[p_idx, 'category']).replace('.','').isdigit() else 1
                                        new_asset = pd.DataFrame([{
                                            "member_phone": sel_m['phone'], "item_name": i['raw_name'],
                                            "total_qty": i['qty'] * spec, "used_qty": 0,
                                            "status": "使用中", "unit": all_prods.at[p_idx, 'unit'], "buy_date": now_str
                                        }])
                                        all_salon = pd.concat([all_salon, new_asset], ignore_index=True)

                        save_data("products", all_prods)
                        save_data("salon_items", all_salon)

                        # C. 记录流水
                        all_records = read_data("records")
                        desc = ",".join([item['name'] for item in st.session_state.cart])
                        new_rec = pd.DataFrame([{
                            "member_phone": sel_m['phone'], "date": now_str,
                            "items": desc, "total_amount": total, "status": method, "staff_name": staff
                        }])
                        save_data("records", pd.concat([all_records, new_rec], ignore_index=True))

                        st.balloons()
                        st.success("结算成功！数据已同步云端。")
                        st.session_state.cart = []
                        time.sleep(1.5)
                        st.rerun()
