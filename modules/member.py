import streamlit as st
import pandas as pd
import time
from datetime import datetime
from db_manager import read_data, save_data


def show(data_bundle):
    st.header("👤 会员中心")
    members_df = data_bundle["members"].copy()
    records_df = data_bundle["records"]
    items_df = data_bundle["salon_items"]
    prods_df = data_bundle["products"]

    # 欠款阈值
    limit = 500.0
    config = data_bundle["sys_config"]
    if not config.empty:
        debt_row = config[config['item'] == 'debt_limit']
        if not debt_row.empty:
            limit = float(debt_row['value'].values[0])

    # 批量删除状态
    if 'batch_delete_mode' not in st.session_state:
        st.session_state.batch_delete_mode = False
    if 'selected_members' not in st.session_state:
        st.session_state.selected_members = []

    # 搜索与筛选
    row1_col1, row1_col2 = st.columns([3, 1])
    search = row1_col1.text_input("搜索", placeholder="姓名/手机号", label_visibility="collapsed")
    only_debt = row1_col2.toggle("🚨 只看超额", value=False)

    c1, c2, c3, c4 = st.columns(4)
    if c1.button("➕ 注册会员", use_container_width=True):
        register_member_dialog()
    if c2.button("📦 项目管理", use_container_width=True):
        from modules.product import add_product_dialog
        add_product_dialog()
    if c3.button("🔥 损耗登记", use_container_width=True):
        from modules.product import deduct_product_dialog
        deduct_product_dialog()
    del_btn_color = "primary" if st.session_state.batch_delete_mode else "secondary"
    if c4.button("🗑️ 批量操作", use_container_width=True, type=del_btn_color):
        st.session_state.batch_delete_mode = not st.session_state.batch_delete_mode
        st.rerun()

    # 筛选
    df = members_df.copy()
    df['debt'] = pd.to_numeric(df['debt'], errors='coerce').fillna(0)
    if only_debt:
        df = df[df['debt'] > limit]
    if search:
        df = df[df['name'].str.contains(search, na=False) | df['phone'].str.contains(search, na=False)]

    if df.empty:
        st.info("暂无符合条件的会员")
        return

    # 展示列表（分页）
    for _, row in df.head(60).iterrows():
        phone = str(row['phone']).split('.')[0]
        is_debt_high = row['debt'] > limit
        with st.container(border=True):
            cols = st.columns([0.5, 1.5, 2, 1, 1] if st.session_state.batch_delete_mode else [1.5, 2, 1, 1, 0.8])
            idx = 0
            if st.session_state.batch_delete_mode:
                if cols[idx].checkbox("", key=f"chk_{phone}"):
                    if phone not in st.session_state.selected_members:
                        st.session_state.selected_members.append(phone)
                idx += 1
            cols[idx].markdown(f"**{'🔴' if is_debt_high else '👤'} {row['name']}**")
            cols[idx].caption(f"📱 {phone}")
            idx += 1
            cols[idx].write(f"📝 {row['skin_info'] if pd.notna(row['skin_info']) else '无备注'}")
            idx += 1
            cols[idx].metric("余额", f"¥{float(row['balance']):.0f}")
            idx += 1
            cols[idx].metric("欠款", f"¥{float(row['debt']):.0f}", delta=f"-{row['debt']}" if row['debt'] > 0 else None,
                             delta_color="inverse")

            with st.expander("账户详情 & 业务办理"):
                t1, t2, t3, t4 = st.tabs(["💰 充值还款", "✨ 剩余资产", "📦 存店登记", "📜 消费历史"])
                with t1:
                    ca, cb = st.columns(2)
                    re_amt = ca.number_input("金额", min_value=0.0, key=f"re_{phone}")
                    if ca.button("充值", key=f"rebtn_{phone}"):
                        members_df.loc[members_df['phone'] == phone, 'balance'] += re_amt
                        new_rec = pd.DataFrame(
                            [{"member_phone": phone, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                              "items": "余额充值", "total_amount": re_amt, "status": "现结", "staff_name": "店长"}])
                        save_data("members", members_df)
                        save_data("records", pd.concat([records_df, new_rec], ignore_index=True))
                        st.cache_data.clear()   # ← 新增：清除缓存
                        st.rerun()
                    if row['debt'] > 0:
                        if cb.button("一键结清", key=f"clr_{phone}"):
                            members_df.loc[members_df['phone'] == phone, 'debt'] = 0
                            save_data("members", members_df)
                            st.cache_data.clear()   # ← 新增：清除缓存
                            st.rerun()
                with t2:
                    active = items_df[(items_df['member_phone'] == phone) & (items_df['status'] == '使用中')]
                    if active.empty:
                        st.caption("暂无可用资产")
                    else:
                        for _, asset in active.iterrows():
                            remains = float(asset['total_qty']) - float(asset['used_qty'])
                            col_left, col_right = st.columns([3, 1])
                            col_left.write(f"**{asset['item_name']}** (余 {remains:.0f} {asset['unit']})")
                            if col_right.button("核销", key=f"use_{asset.name}_{phone}"):
                                items_df.at[asset.name, 'used_qty'] += 1
                                if items_df.at[asset.name, 'used_qty'] >= items_df.at[asset.name, 'total_qty']:
                                    items_df.at[asset.name, 'status'] = '已用完'
                                save_data("salon_items", items_df)
                                st.toast(f"已核销: {asset['item_name']}")
                                time.sleep(0.5)
                                st.cache_data.clear()   # ← 新增：清除缓存
                                st.rerun()
                with t3:
                    if not prods_df.empty:
                        prod_list = prods_df['prod_name'].tolist()
                        add_name = st.selectbox("产品", prod_list, key=f"addn_{phone}")
                        add_q = st.number_input("数量", 1, 100, 1, key=f"addq_{phone}")
                        if st.button("确认存入", key=f"addb_{phone}"):
                            unit = prods_df[prods_df['prod_name'] == add_name]['unit'].values[0]
                            new_item = pd.DataFrame([{
                                "member_phone": phone, "item_name": add_name, "total_qty": add_q,
                                "used_qty": 0, "status": "使用中", "unit": unit,
                                "buy_date": datetime.now().strftime("%Y-%m-%d")
                            }])
                            save_data("salon_items", pd.concat([items_df, new_item], ignore_index=True))
                            st.success("登记成功");
                            st.cache_data.clear()   # ← 新增：清除缓存
                            st.rerun()
                with t4:
                    hist = records_df[records_df['member_phone'] == phone].sort_index(ascending=False)
                    st.dataframe(hist[['date', 'items', 'total_amount', 'status']], hide_index=True,
                                 use_container_width=True)

    # 批量删除确认
    if st.session_state.batch_delete_mode and st.session_state.selected_members:
        st.divider()
        if st.button("⚠️ 确认删除选中会员", type="primary", use_container_width=True):
            confirm_batch_delete()


@st.dialog("👤 注册新会员")
def register_member_dialog():
    members_df = read_data("members")
    with st.form("reg_form"):
        name = st.text_input("姓名*")
        phone = st.text_input("手机号*")
        c1, c2 = st.columns(2)
        balance = c1.number_input("初始余额", 0.0)
        debt = c2.number_input("初始欠款", 0.0)
        skin_info = st.text_area("备注/皮肤情况")
        if st.form_submit_button("确认提交", type="primary"):
            if not name or not phone:
                st.error("请填写姓名和手机号")
                return
            if phone in members_df['phone'].astype(str).values:
                st.error("手机号已存在")
                return
            new_row = pd.DataFrame([{
                "phone": phone, "name": name, "balance": balance, "skin_info": skin_info,
                "debt": debt, "note": "", "reg_date": datetime.now().strftime("%Y-%m-%d")
            }])
            save_data("members", pd.concat([members_df, new_row], ignore_index=True))
            st.cache_data.clear()   # ← 新增：清除缓存
            st.rerun()


@st.dialog("⚠️ 批量清理确认")
def confirm_batch_delete():
    members_df = read_data("members")
    items_df = read_data("salon_items")
    records_df = read_data("records")
    selected = st.session_state.get('selected_members', [])
    if not selected:
        st.warning("未勾选任何会员")
        return
    targets = members_df[members_df['phone'].astype(str).isin(selected)]
    forbidden = targets[(targets['balance'].astype(float) != 0) | (targets['debt'].astype(float) != 0)]
    if not forbidden.empty:
        st.error("有余款或欠款的会员不可删除")
        return
    st.error(f"确认删除 {len(targets)} 名会员及其所有记录？")
    if st.button("🔥 永久清理", type="primary"):
        mask = ~members_df['phone'].astype(str).isin(selected)
        save_data("members", members_df[mask])
        save_data("salon_items", items_df[~items_df['member_phone'].astype(str).isin(selected)])
        save_data("records", records_df[~records_df['member_phone'].astype(str).isin(selected)])
        st.session_state.selected_members = []
        st.session_state.batch_delete_mode = False
        st.cache_data.clear()   # ← 新增：清除缓存
        st.rerun()
