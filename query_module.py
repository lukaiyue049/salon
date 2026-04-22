import streamlit as st
import pandas as pd
import time
import re
from datetime import datetime
from db_manager import read_data, save_data

def show_member_management(data_bundle=None):
    st.header("👤 会员中心")

    # --- 1. 数据获取 (优先使用 bundle 提速) ---
    if data_bundle:
        members_df = data_bundle.get("members")
        records_df = data_bundle.get("records")
        items_df = data_bundle.get("salon_items")
        prods_df = data_bundle.get("products")
    else:
        members_df = read_data("members")
        records_df = read_data("records")
        items_df = read_data("salon_items")
        prods_df = read_data("products")
    
    # 欠款红名限额
    limit = 500.0

    # --- 2. 状态初始化 ---
    if 'batch_delete_mode' not in st.session_state:
        st.session_state.batch_delete_mode = False
    if 'selected_members' not in st.session_state:
        st.session_state.selected_members = []

    # --- 3. 顶部操作栏 ---
    row1_col1, row1_col2 = st.columns([3, 1])
    search = row1_col1.text_input("搜索", placeholder="🔍 姓名/手机号", label_visibility="collapsed")
    only_debt = row1_col2.toggle("🚨 只看超额", value=False)

    # 功能按钮矩阵
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("➕ 注册会员", use_container_width=True): register_member_dialog()
    if c2.button("📦 项目管理", use_container_width=True): add_product_dialog()
    if c3.button("🔥 损耗登记", use_container_width=True): deduct_product_dialog()
    
    del_btn_color = "primary" if st.session_state.batch_delete_mode else "secondary"
    if c4.button("🗑️ 批量操作", use_container_width=True, type=del_btn_color):
        st.session_state.batch_delete_mode = not st.session_state.batch_delete_mode
        st.rerun()

    # --- 4. 筛选逻辑 ---
    df = members_df.copy()
    df['debt'] = pd.to_numeric(df['debt'], errors='coerce').fillna(0)
    if only_debt:
        df = df[df['debt'] > limit]
    if search:
        df = df[df['name'].astype(str).str.contains(search) | df['phone'].astype(str).str.contains(search)]

    if df.empty:
        st.info("🔍 暂无符合条件的会员记录")
        return

    # --- 5. 会员列表渲染 (iPad 性能优化版) ---
    display_df = df.head(60) # 限制单次渲染数量
    for _, row in display_df.iterrows():
        p_phone = str(row['phone']).split('.')[0]
        is_debt_high = row['debt'] > limit
        
        with st.container(border=True):
            col_layout = [0.5, 1.5, 2, 1, 1] if st.session_state.batch_delete_mode else [1.5, 2, 1, 1, 0.8]
            cols = st.columns(col_layout)
            
            idx = 0
            if st.session_state.batch_delete_mode:
                if cols[idx].checkbox("", key=f"chk_{p_phone}"):
                    if p_phone not in st.session_state.selected_members:
                        st.session_state.selected_members.append(p_phone)
                idx += 1

            cols[idx].markdown(f"**{'🔴' if is_debt_high else '👤'} {row['name']}**")
            cols[idx].caption(f"📱 {p_phone}")
            idx += 1
            
            cols[idx].write(f"📝 {row['skin_info'] if pd.notna(row['skin_info']) else '无备注'}")
            idx += 1
            
            cols[idx].metric("余额", f"¥{float(row['balance']):.0f}")
            idx += 1
            
            cols[idx].metric("欠款", f"¥{float(row['debt']):.0f}", delta=f"-{row['debt']}" if row['debt'] > 0 else None, delta_color="inverse")

            with st.expander("👑 账户详情 & 业务办理"):
                t1, t2, t3, t4 = st.tabs(["💰 充值还款", "✨ 剩余资产", "📦 存店登记", "📜 消费历史"])

                with t1: # 充值还款
                    ca, cb = st.columns(2)
                    re_amt = ca.number_input("金额", min_value=0.0, key=f"re_in_{p_phone}")
                    if ca.button("充值", key=f"re_btn_{p_phone}", use_container_width=True):
                        members_df.loc[members_df['phone'].astype(str).str.contains(p_phone), 'balance'] += re_amt
                        new_rec = pd.DataFrame([{"member_phone": p_phone, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "items": "余额充值", "total_amount": re_amt, "status": "现结", "staff_name": "店长"}])
                        save_data("members", members_df)
                        save_data("records", pd.concat([records_df, new_rec]))
                        st.rerun()

                    if row['debt'] > 0:
                        if cb.button("一键结清", key=f"clr_{p_phone}", use_container_width=True):
                            members_df.loc[members_df['phone'].astype(str).str.contains(p_phone), 'debt'] = 0
                            save_data("members", members_df)
                            st.rerun()

                with t2: # 资产核销
                    active_items = items_df[(items_df['member_phone'].astype(str).str.contains(p_phone)) & (items_df['status'] == '使用中')]
                    if active_items.empty:
                        st.caption("暂无可用资产")
                    else:
                        for i_idx, item in active_items.iterrows():
                            c_left, c_right = st.columns([3, 1])
                            remains = float(item['total_qty']) - float(item['used_qty'])
                            c_left.write(f"**{item['item_name']}** (余 {remains:.0f} {item['unit']})")
                            
                            if c_right.button("核销", key=f"use_{i_idx}_{p_phone}"):
                                items_df.at[i_idx, 'used_qty'] += 1
                                if items_df.at[i_idx, 'used_qty'] >= items_df.at[i_idx, 'total_qty']:
                                    items_df.at[i_idx, 'status'] = '已用完'
                                if not prods_df.empty:
                                    prods_df.loc[prods_df['prod_name'] == item['item_name'], 'stock'] -= 1
                                save_data("salon_items", items_df)
                                save_data("products", prods_df)
                                st.toast(f"已核销: {item['item_name']}")
                                time.sleep(0.5); st.rerun()

                with t3: # 存店登记
                    add_name = st.selectbox("产品", prods_df['prod_name'].tolist(), key=f"add_p_{p_phone}")
                    add_q = st.number_input("数量", 1, 100, 1, key=f"add_q_{p_phone}")
                    if st.button("确认存入", key=f"add_b_{p_phone}", use_container_width=True):
                        u_val = prods_df[prods_df['prod_name'] == add_name]['unit'].values[0] if add_name in prods_df['prod_name'].values else "个"
                        new_item = pd.DataFrame([{
                            "member_phone": p_phone, "item_name": add_name, "total_qty": add_q, 
                            "used_qty": 0, "status": "使用中", "unit": u_val, "buy_date": datetime.now().strftime("%Y-%m-%d")
                        }])
                        save_data("salon_items", pd.concat([items_df, new_item]))
                        st.success("登记成功"); time.sleep(0.5); st.rerun()

                with t4: # 消费历史
                    p_history = records_df[records_df['member_phone'].astype(str).str.contains(p_phone)].sort_index(ascending=False)
                    st.dataframe(p_history[['date', 'items', 'total_amount', 'status']], hide_index=True, use_container_width=True)

    # --- 6. 批量操作底栏 ---
    if st.session_state.batch_delete_mode and st.session_state.selected_members:
        st.divider()
        if st.button("⚠️ 确认删除选中会员", type="primary", use_container_width=True):
            confirm_batch_delete()

# --- 所有弹窗对话框 (Dialogs) ---

@st.dialog("👤 注册新会员")
def register_member_dialog():
    members_df = read_data("members")
    with st.form("reg_form"):
        n = st.text_input("姓名*")
        p = st.text_input("手机号*")
        c1, c2 = st.columns(2)
        b = c1.number_input("初始余额", 0.0)
        d = col2.number_input("初始欠款", 0.0)
        s = st.text_area("备注/皮肤情况")
        if st.form_submit_button("确认提交", type="primary"):
            # 查重与保存逻辑...
            save_data("members", pd.concat([members_df, pd.DataFrame([...])]))
            st.rerun()

# --- 1. 项目管理弹窗 (一键提交版) ---
@st.dialog("项目管理 / 录入与进货")
def add_product_dialog():
    prods_df = read_data("products")
    
    if 'batch_list' not in st.session_state:
        st.session_state.batch_list = []

    menu = st.tabs(["✨ 单次录入", "📦 批量清单"])

    with menu[0]:
        p_type = st.radio("业务类别", ["实物产品", "服务项目"], horizontal=True)
        mode = st.radio("录入类型", ["新登记", "现有补货"], horizontal=True)

        with st.container(border=True):
            if mode == "新登记":
                prod_name = st.text_input(f"{p_type}名称*", key="in_name").strip()
                if p_type == "服务项目":
                    price = st.number_input("定价", min_value=0.0, step=10.0)
                    u, qty, spec = "次", 9999.0, 1
                else:
                    u = st.selectbox("单位", ["盒", "瓶", "支", "个", "套"])
                    price = st.number_input("单价", min_value=0.0)
                    qty = st.number_input(f"初始库存({u})", min_value=0.0)
                    def_spec = 10 if u == "盒" else (5 if u == "套" else 1)
                    spec = st.number_input("规格系数", min_value=1, value=def_spec)
            else:
                filtered = prods_df[prods_df['type'] == p_type]
                if filtered.empty: st.warning("暂无记录"); return
                prod_name = st.selectbox(f"选择已有{p_type}", filtered['prod_name'].tolist())
                price = st.number_input("更新单价 (0为不改)", 0.0)
                qty = st.number_input("增加数量", min_value=0.0)
                u, spec = "原单位", 1

            c_btn1, c_btn2 = st.columns(2)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if c_btn1.button("🚀 立即录入", use_container_width=True, type="primary"):
                if not prod_name: return
                if mode == "新登记":
                    new_p = pd.DataFrame([{"prod_name": prod_name, "category": str(spec), "price": price, "stock": qty, "unit": u, "type": p_type, "last_updated": now_str}])
                    save_data("products", pd.concat([prods_df, new_p], ignore_index=True))
                else:
                    idx = prods_df[prods_df['prod_name'] == prod_name].index
                    prods_df.loc[idx, 'stock'] += qty
                    if price > 0: prods_df.loc[idx, 'price'] = price
                    prods_df.loc[idx, 'last_updated'] = now_str
                    save_data("products", prods_df)
                st.rerun()

            if c_btn2.button("➕ 加入清单", use_container_width=True):
                st.session_state.batch_list.append({
                    "名称": prod_name, "类型": p_type, "单价": price, "数量": qty, "单位": u, "模式": mode, "规格": spec
                })
                st.toast("已加入清单")

    with menu[1]:
        if st.session_state.batch_list:
            st.dataframe(pd.DataFrame(st.session_state.batch_list), use_container_width=True, hide_index=True)
            if st.button("🚀 全部入库", type="primary", use_container_width=True):
                for item in st.session_state.batch_list:
                    if item['模式'] == "新登记":
                        new_row = pd.DataFrame([{"prod_name": item['名称'], "category": str(item['规格']), "price": item['单价'], "stock": item['数量'], "unit": item['单位'], "type": item['类型'], "last_updated": now_str}])
                        prods_df = pd.concat([prods_df, new_row], ignore_index=True)
                    else:
                        idx = prods_df[prods_df['prod_name'] == item['名称']].index
                        prods_df.loc[idx, 'stock'] += item['数量']
                        if item['单价'] > 0: prods_df.loc[idx, 'price'] = item['单价']
                save_data("products", prods_df)
                st.session_state.batch_list = []; st.rerun()
        else:
            st.info("清单为空")

# --- 2. 损耗登记弹窗 (一键版) ---
@st.dialog("损耗登记")
def deduct_product_dialog():
    prods_df = read_data("products")
    records_df = read_data("records")

    items = prods_df[(prods_df['type'] == '实物产品') & (prods_df['stock'] > 0)]
    if items.empty: return

    sel_p = st.selectbox("产品", items['prod_name'].tolist())
    info = items[items['prod_name'] == sel_p].iloc[0]
    
    col1, col2 = st.columns(2)
    mode = col1.radio("单位", [f"按{info['unit']}", "按片/支"])
    num = col2.number_input("数量", min_value=0.1, value=1.0)
    reason = st.selectbox("原因", ["店用消耗", "过期处理", "破损/丢弃"])

    if st.button("🔥 确认扣除", type="primary", use_container_width=True):
        spec = int(info['category']) if str(info['category']).isdigit() else 1
        real_deduct = num / spec if "片/支" in mode else num
        
        prods_df.loc[prods_df['prod_name'] == sel_p, 'stock'] -= real_deduct
        new_rec = pd.DataFrame([{
            "member_phone": "SYSTEM", "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "items": f"【{reason}】{sel_p} {num}{mode.replace('按','')}",
            "total_amount": 0, "status": "非销售损耗", "staff_name": "后台"
        }])
        save_data("products", prods_df)
        save_data("records", pd.concat([records_df, new_rec], ignore_index=True))
        st.rerun()

# --- 3. 批量删除 (一键清理版) ---
@st.dialog("⚠️ 批量清理确认")
def confirm_batch_delete():
    members_df = read_data("members")
    items_df = read_data("salon_items")
    records_df = read_data("records")
    selected_phones = st.session_state.get('selected_members', [])
    
    if not selected_phones:
        st.warning("未勾选"); return

    targets = members_df[members_df['phone'].astype(str).str.split('.').str[0].isin(selected_phones)]
    
    # 仍保留基础财务校验，防止把欠钱的会员删了收不回账
    forbidden = targets[(targets['balance'].astype(float) != 0) | (targets['debt'].astype(float) != 0)]
    if not forbidden.empty:
        st.error("有余款或欠款，不可删除")
        return

    st.error(f"确认删除选中 {len(targets)} 名会员及其所有记录？")
    
    if st.button("🔥 立即永久清理", type="primary", use_container_width=True):
        mask_m = ~members_df['phone'].astype(str).str.split('.').str[0].isin(selected_phones)
        mask_si = ~items_df['member_phone'].astype(str).str.split('.').str[0].isin(selected_phones)
        mask_r = ~records_df['member_phone'].astype(str).str.split('.').str[0].isin(selected_phones)
        
        save_data("members", members_df[mask_m])
        save_data("salon_items", items_df[mask_si])
        save_data("records", records_df[mask_r])
        
        st.session_state.selected_members = []
        st.session_state.batch_delete_mode = False
        st.rerun()
