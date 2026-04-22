import streamlit as st
import pandas as pd
import json
from datetime import datetime
from db_manager import read_data, save_data
import time

# 修改：增加 products_df, members_df 等参数，由 main.py 统一传入
def show(staff_list, products_df=None, members_df=None, acts_df=None, config_df=None):
    st.header("💰 收银台")
    
    if 'cart' not in st.session_state:
        st.session_state.cart = []

    # --- 1. 优先使用传入的数据，如果没有（比如直接运行该模块）再读取 ---
    if config_df is None: config_df = read_data("sys_config")
    if members_df is None: members_df = read_data("members")
    if products_df is None: products_df = read_data("products")
    if acts_df is None: acts_df = read_data("activities")

    # 配置项提取
    limit = 500.0
    if not config_df.empty and 'item' in config_df.columns:
        debt_row = config_df[config_df['item'] == 'debt_limit']
        if not debt_row.empty:
            limit = float(debt_row['value'].values[0])

    # 强制转换 phone 为字符串
    if not members_df.empty:
        members_df['phone'] = members_df['phone'].astype(str).str.replace('.0', '', regex=False)
    
    # 2. 会员搜索
    st.subheader("👤 会员搜索")
    q = st.text_input("🔍 搜索会员（姓名/手机号）", key="member_search")
    sel_m = None

    if q and not members_df.empty:
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
            # 安全清理列名
            acts_df.columns = [c.strip().lower() for c in acts_df.columns]
            acts = acts_df[acts_df['is_open'].astype(str) == '1'] if 'is_open' in acts_df.columns else acts_df
            
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
                        "is_store_use": True 
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
            staff = st.selectbox("👤 经办人", staff_list)

            if st.button("🚀 确认结算", type="primary", use_container_width=True):
                if not sel_m:
                    st.error("请先确认会员！")
                elif method == "余额扣款" and float(sel_m['balance']) < total:
                    st.error("余额不足！")
                else:
                    # --- 开始云端写入 ---
                    with st.spinner("正在提交结算..."):
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # 1. 更新会员
                        m_idx = members_df[members_df['phone'] == sel_m['phone']].index[0]
                        if method == "余额扣款":
                            members_df.at[m_idx, 'balance'] = float(members_df.at[m_idx, 'balance']) - total
                        elif method == "挂账":
                            members_df.at[m_idx, 'debt'] = float(members_df.at[m_idx, 'debt']) + total
                        save_data("members", members_df)

                        # 2. 更新库存与院装资产
                        all_salon = read_data("salon_items") # 院装资产表还是得读一次
                        
                        for i in st.session_state.cart:
                            if i['is_activity']:
                                for p_n, p_q in i['packages'].items():
                                    t_qty = p_q * i['qty']
                                    p_idx_list = products_df[products_df['prod_name'] == p_n].index
                                    if not p_idx_list.empty:
                                        p_idx = p_idx_list[0]
                                        products_df.at[p_idx, 'stock'] = max(0, float(products_df.at[p_idx, 'stock']) - t_qty)
                                        spec = float(products_df.at[p_idx, 'category']) if str(products_df.at[p_idx, 'category']).replace('.','').isdigit() else 1
                                        new_asset = pd.DataFrame([{
                                            "member_phone": sel_m['phone'], "item_name": p_n,
                                            "total_qty": t_qty * spec, "used_qty": 0,
                                            "status": "使用中", "unit": products_df.at[p_idx, 'unit'], "buy_date": now_str
                                        }])
                                        all_salon = pd.concat([all_salon, new_asset], ignore_index=True)
                            else:
                                p_idx_list = products_df[products_df['prod_name'] == i['raw_name']].index
                                if not p_idx_list.empty:
                                    p_idx = p_idx_list[0]
                                    products_df.at[p_idx, 'stock'] = max(0, float(products_df.at[p_idx, 'stock']) - i['qty'])
                                    if i['is_store_use']:
                                        spec = float(products_df.at[p_idx, 'category']) if str(products_df.at[p_idx, 'category']).replace('.','').isdigit() else 1
                                        new_asset = pd.DataFrame([{
                                            "member_phone": sel_m['phone'], "item_name": i['raw_name'],
                                            "total_qty": i['qty'] * spec, "used_qty": 0,
                                            "status": "使用中", "unit": products_df.at[p_idx, 'unit'], "buy_date": now_str
                                        }])
                                        all_salon = pd.concat([all_salon, new_asset], ignore_index=True)

                        save_data("products", products_df)
                        save_data("salon_items", all_salon)

                        # 3. 记录流水
                        all_records = read_data("records")
                        desc = ",".join([item['name'] for item in st.session_state.cart])
                        new_rec = pd.DataFrame([{
                            "member_phone": sel_m['phone'], "date": now_str,
                            "items": desc, "total_amount": total, "status": method, "staff_name": staff
                        }])
                        save_data("records", pd.concat([all_records, new_rec], ignore_index=True))

                        st.balloons()
                        st.success("结算成功！")
                        st.session_state.cart = []
                        st.cache_data.clear() # 关键：清空缓存，让下一次加载拿到最新数据
                        time.sleep(1)
                        st.rerun()
