import streamlit as st
import pandas as pd
import time
import re
from datetime import datetime
from db_manager import read_data, save_data

def show_member_management():
    st.header("👤 会员中心")

    # --- 1. 获取云端最新数据 ---
    # 强制 ttl=0 获取最新，防止多人操作冲突
    members_df = read_data("members")
    records_df = read_data("records")
    items_df = read_data("salon_items")
    prods_df = read_data("products")
    
    # 获取红名阈值
    config_df = read_data("sys_config")
    try:
        limit = float(config_df[config_df['item'] == 'debt_limit']['value'].values[0])
    except:
        limit = 500.0

    # --- 2. 状态初始化与顶部栏 ---
    if 'batch_delete_mode' not in st.session_state:
        st.session_state.batch_delete_mode = False
    if 'selected_members' not in st.session_state:
        st.session_state.selected_members = []

    row1_col1, row1_col2 = st.columns([3, 1])
    search = row1_col1.text_input("搜索", placeholder="🔍 姓名/手机号", label_visibility="collapsed")
    only_debt = row1_col2.toggle("🚨 只看超额", value=False)

    # 按钮栏
    r2_c1, r2_c2, r2_c3 = st.columns(3)
    if r2_c1.button("➕ 注册会员", use_container_width=True):
        st.info("请在注册函数中调用 save_data 写回 members 表")
    
    if r2_c2.button("📥 批量导入", use_container_width=True):
        st.session_state.show_batch = not st.session_state.get('show_batch', False)
        st.rerun()

    if r2_c3.button("🗑️ 批量删除", use_container_width=True):
        st.session_state.batch_delete_mode = not st.session_state.batch_delete_mode
        st.rerun()

    # --- 3. 筛选逻辑 ---
    df = members_df.copy()
    if only_debt:
        df = df[df['debt'] > limit]
    if search:
        df = df[df['name'].astype(str).contains(search) | df['phone'].astype(str).contains(search)]

    if df.empty:
        st.info("🔍 暂无符合条件的会员记录")
        return

    # --- 4. 列表渲染 ---
    for _, row in df.iterrows():
        is_debt_high = row['debt'] > limit
        with st.container(border=True):
            # 这里的布局根据删除模式切换
            col_layout = [0.5, 1.5, 2, 1, 1] if st.session_state.batch_delete_mode else [1.5, 2, 1, 1, 0.8]
            cols = st.columns(col_layout)
            
            idx = 0
            if st.session_state.batch_delete_mode:
                if cols[idx].checkbox("", key=f"chk_{row['phone']}"):
                    if row['phone'] not in st.session_state.selected_members:
                        st.session_state.selected_members.append(row['phone'])
                idx += 1

            # 基础信息
            cols[idx].markdown(f"**{'🔴' if is_debt_high else '👤'} {row['name']}**")
            cols[idx].caption(f"📱 {row['phone']}")
            idx += 1
            
            cols[idx].write(f"📝 {row['skin_info'] if pd.notna(row['skin_info']) else '暂无备注'}")
            idx += 1
            
            cols[idx].metric("余额", f"¥{row['balance']}")
            idx += 1
            
            cols[idx].metric("欠款", f"¥{row['debt']}", delta=f"-{row['debt']}" if row['debt'] > 0 else None, delta_color="inverse")

            # --- 详情折叠面板 (核心业务) ---
            with st.expander("👑 资料详情 & 操作"):
                t1, t2, t3, t4 = st.tabs(["💰 充值还款", "✨ 剩余资产", "📦 存店登记", "📜 消费历史"])

                # --- T1: 充值还款 (内存计算后覆盖) ---
                with t1:
                    ca, cb = st.columns(2)
                    re_amt = ca.number_input("金额", min_value=0.0, key=f"re_in_{row['phone']}")
                    if ca.button("充值", key=f"re_btn_{row['phone']}", use_container_width=True):
                        # 修改内存中的 members_df
                        members_df.loc[members_df['phone'] == row['phone'], 'balance'] += re_amt
                        # 生成记录
                        new_rec = pd.DataFrame([{"member_phone": row['phone'], "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "items": "余额充值", "total_amount": re_amt, "status": "现结", "staff_name": "店长"}])
                        save_data("members", members_df)
                        save_data("records", pd.concat([records_df, new_rec]))
                        st.rerun()

                    if row['debt'] > 0:
                        if cb.button("一键结清", key=f"clr_{row['phone']}", use_container_width=True):
                            members_df.loc[members_df['phone'] == row['phone'], 'debt'] = 0
                            save_data("members", members_df)
                            st.rerun()

                # --- T2: 剩余资产与核销 (FIFO逻辑) ---
                with t2:
                    active_items = items_df[(items_df['member_phone'] == row['phone']) & (items_df['status'] == '使用中')]
                    if active_items.empty:
                        st.caption("暂无可用资产")
                    else:
                        for _, item in active_items.iterrows():
                            c_left, c_right = st.columns([3, 1])
                            remains = item['total_qty'] - item['used_qty']
                            c_left.write(f"**{item['item_name']}** (余 {remains} {item['unit']})")
                            
                            if c_right.button("核销", key=f"use_{item['item_name']}_{row['phone']}"):
                                # 找到 items_df 中对应的这一行（通过 item_name 和 phone 且状态在使用中的第一个）
                                item_idx = items_df[(items_df['member_phone'] == row['phone']) & 
                                                   (items_df['item_name'] == item['item_name']) & 
                                                   (items_df['status'] == '使用中')].index[0]
                                
                                items_df.loc[item_idx, 'used_qty'] += 1
                                if items_df.loc[item_idx, 'used_qty'] >= items_df.loc[item_idx, 'total_qty']:
                                    items_df.loc[item_idx, 'status'] = '已用完'
                                
                                # 同时扣减物理库存
                                prods_df.loc[prods_df['prod_name'] == item['item_name'], 'stock'] -= 1
                                
                                save_data("salon_items", items_df)
                                save_data("products", prods_df)
                                st.toast(f"已使用: {item['item_name']}")
                                time.sleep(0.5)
                                st.rerun()

                # --- T3: 存店登记 ---
                with t3:
                    add_name = st.selectbox("产品", prods_df['prod_name'].tolist(), key=f"add_p_{row['phone']}")
                    add_q = st.number_input("数量", 1, 100, 1, key=f"add_q_{row['phone']}")
                    if st.button("确认存入", key=f"add_b_{row['phone']}"):
                        unit = prods_df[prods_df['prod_name'] == add_name]['unit'].values[0]
                        new_item = pd.DataFrame([{
                            "member_phone": row['phone'], "item_name": add_name, "total_qty": add_q, 
                            "used_qty": 0, "status": "使用中", "unit": unit, "buy_date": datetime.now().strftime("%Y-%m-%d")
                        }])
                        save_data("salon_items", pd.concat([items_df, new_item]))
                        st.success("登记成功")
                        st.rerun()

                # --- T4: 消费历史 ---
                with t4:
                    personal_history = records_df[records_df['member_phone'] == row['phone']].sort_index(ascending=False)
                    st.dataframe(personal_history[['date', 'items', 'total_amount', 'status']], hide_index=True)

    # --- 5. 批量操作底栏 ---
    if st.session_state.batch_delete_mode and st.session_state.selected_members:
        st.divider()
        if st.button("⚠️ 确认删除选中会员", type="primary"):
            # 过滤掉这些手机号对应的行
            new_members = members_df[~members_df['phone'].isin(st.session_state.selected_members)]
            save_data("members", new_members)
            st.session_state.selected_members = []
            st.session_state.batch_delete_mode = False
            st.rerun()

@st.dialog("👤 注册新会员")
def register_member_dialog():
    members_df = read_data("members")
    
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
            phone_pattern = r"^1[3-9]\d{9}$"
            clean_p = "".join(p.split()).replace("-", "").replace(".0", "")

            if not n:
                st.error("请输入姓名")
                return
            if not re.match(phone_pattern, clean_p):
                st.error("❌ 手机号格式不正确")
                return

            # 云端查重
            if clean_p in members_df['phone'].astype(str).values:
                existing_name = members_df[members_df['phone'].astype(str) == clean_p]['name'].values[0]
                st.error(f"❌ 手机号已存在！会员：{existing_name}")
            else:
                new_row = pd.DataFrame([{
                    "phone": clean_p,
                    "name": n,
                    "balance": b,
                    "skin_info": s,
                    "debt": d,
                    "reg_date": datetime.now().strftime("%Y-%m-%d"),
                    "note": "" # 适配你之前报错过的 note 字段
                }])
                save_data("members", pd.concat([members_df, new_row], ignore_index=True))
                st.success(f"✅ 会员 {n} 注册成功！")
                time.sleep(0.8)
                st.rerun()

# --- 2. 产品/项目入库弹窗 ---
@st.dialog("项目管理 / 录入与进货")
def add_product_dialog():
    # 获取基础表
    prods_df = read_data("products")

    if 'batch_list' not in st.session_state:
        st.session_state.batch_list = []

    menu = st.tabs(["✨ 单个连续录入", "📦 批量清单/确认"])

    with menu[0]:
        p_type = st.radio("业务类别", ["实物产品", "服务项目"], horizontal=True, key="dlg_type")
        mode = st.radio("录入类型", ["新登记录入", "现有补货/调价"], horizontal=True, key="dlg_mode")

        with st.container(border=True):
            if mode == "新登记录入":
                prod_name = st.text_input(f"{p_type}名称*", key="in_name")
                if p_type == "服务项目":
                    price = st.number_input("项目定价", min_value=0.0, step=10.0, key="in_price")
                    u, qty, spec = "次", 999.0, 1
                else:
                    u = st.selectbox("计量单位", ["盒", "瓶", "支", "个", "套"], key="in_unit")
                    price = st.number_input("销售单价", min_value=0.0, key="in_price")
                    qty = st.number_input(f"初始库存({u})", min_value=0.0, key="in_qty")
                    # 规格系数逻辑
                    spec = 10 if u == "盒" else (5 if u == "套" else 1)
                    spec = st.number_input("规格系数(1盒含几片)", min_value=1, value=spec, key="in_spec")
            else:
                # 筛选已有
                filtered_prods = prods_df[prods_df['type'] == p_type]
                p_list = filtered_prods['prod_name'].tolist()
                if not p_list:
                    st.warning(f"⚠️ 暂无已登记的{p_type}")
                    prod_name = None
                else:
                    prod_name = st.selectbox(f"选择已有{p_type}", p_list, key="sel_name")
                    price = st.number_input("更新单价 (0为不改)", 0.0, key="up_price")
                    u = "次" if p_type == "服务项目" else "原单位"
                    qty = st.number_input("增加数量", min_value=0.0, key="up_qty")
                    spec = 1

            c_btn1, c_btn2 = st.columns(2)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if c_btn1.button("📥 直接提交", use_container_width=True, type="primary"):
                if prod_name:
                    if mode == "新登记录入":
                        if prod_name in prods_df['prod_name'].values:
                            st.error("名称已存在")
                        else:
                            new_p = pd.DataFrame([{
                                "prod_name": prod_name, "category": str(spec), "price": price,
                                "stock": qty, "unit": u, "type": p_type, "last_updated": now_str
                            }])
                            save_data("products", pd.concat([prods_df, new_p], ignore_index=True))
                            st.toast(f"✅ {prod_name} 录入成功")
                            st.rerun()
                    else:
                        idx = prods_df[prods_df['prod_name'] == prod_name].index
                        prods_df.loc[idx, 'stock'] += qty
                        if price > 0:
                            prods_df.loc[idx, 'price'] = price
                        prods_df.loc[idx, 'last_updated'] = now_str
                        save_data("products", prods_df)
                        st.toast("✅ 更新成功")
                        st.rerun()

            if c_btn2.button("➕ 加入批量清单", use_container_width=True):
                if prod_name:
                    st.session_state.batch_list.append({
                        "名称": prod_name, "类型": p_type, "单价": price,
                        "数量": qty, "单位": u, "模式": mode, "规格": spec
                    })
                    st.toast("已加入清单")

  with menu[1]:
        if st.session_state.batch_list:
            # 1. 定义固定的列宽比例 [名称, 类型, 单价, 数量, 单位]
            # 这能保证在 iPad 上上下绝对对齐
            batch_col_layout = [2.5, 1.5, 1.5, 1.5, 1]
            
            # 2. 手动渲染表头
            h_cols = st.columns(batch_col_layout)
            h_cols[0].write("**名称**")
            h_cols[1].write("**类型**")
            h_cols[2].write("**单价**")
            h_cols[3].write("**数量**")
            h_cols[4].write("**单位**")
            st.divider()

            # 3. 循环渲染清单每一行
            for idx, item in enumerate(st.session_state.batch_list):
                r_cols = st.columns(batch_col_layout)
                r_cols[0].write(item['名称'])
                r_cols[1].write(item['类型'])
                r_cols[2].write(f"¥{item['单价']:.2f}")
                r_cols[3].write(str(item['数量']))
                r_cols[4].write(item['单位'])
            
            st.markdown("---") # 底部线

            # 4. 提交逻辑（保持你原有的逻辑，但确保 save_data 写入）
            if st.button("🚀 确认全部入库", use_container_width=True, type="primary"):
                for item in st.session_state.batch_list:
                    if item['模式'] == "新登记录入":
                        # 再次检查 prod_name 是否存在，防止 Key 冲突
                        if item['名称'] not in prods_df['prod_name'].values:
                            new_row = pd.DataFrame([{
                                "prod_name": item['名称'], "category": str(item['规格']),
                                "price": item['单价'], "stock": item['数量'], "unit": item['单位'],
                                "type": item['类型'], "last_updated": now_str
                            }])
                            prods_df = pd.concat([prods_df, new_row], ignore_index=True)
                    else:
                        idx_list = prods_df[prods_df['prod_name'] == item['名称']].index
                        prods_df.loc[idx_list, 'stock'] += item['数量']
                        if item['单价'] > 0:
                            prods_df.loc[idx_list, 'price'] = item['单价']
                
                save_data("products", prods_df)
                st.session_state.batch_list = []
                st.rerun()
        else:
            st.info("💡 暂无待入库项目")

# --- 3. 非销售扣除弹窗 ---
@st.dialog("非销售扣除登记")
def deduct_product_dialog():
    prods_df = read_data("products")
    records_df = read_data("records")

    prods = prods_df[(prods_df['type'] == '实物产品') & (prods_df['stock'] > 0)]
    if prods.empty:
        st.warning("暂无库存产品")
        return

    sel_p = st.selectbox("选择产品", prods['prod_name'].tolist())
    info = prods[prods['prod_name'] == sel_p].iloc[0]
    db_unit = info['unit']
    db_spec = int(info['category']) if str(info['category']).isdigit() else 1

    col1, col2 = st.columns(2)
    deduct_type = col1.radio("扣除单位", [f"按{db_unit}扣除", "按片/支/次扣除"])
    num = col2.number_input("扣除数量", min_value=0.1, value=1.0)

    reason = st.selectbox("扣除原因", ["店用消耗", "产品过期", "破损丢弃", "其他原因"])
    note = st.text_input("备注说明")

    if st.button("🔥 确认扣除", use_container_width=True, type="primary"):
        final_deduct = num / db_spec if "按片/支/次" in deduct_type else num
        
        if final_deduct > info['stock']:
            st.error(f"库存不足！剩余 {info['stock']} {db_unit}")
        else:
            # 更新库存
            idx = prods_df[prods_df['prod_name'] == sel_p].index
            prods_df.loc[idx, 'stock'] -= final_deduct
            
            # 记录流水
            new_rec = pd.DataFrame([{
                "member_phone": "SYSTEM", "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "items": f"{reason}: {sel_p} {num}{'片/支' if '片' in deduct_type else db_unit}",
                "total_amount": 0, "status": "非销售损耗", "staff_name": note if note else "后台扣除"
            }])
            
            save_data("products", prods_df)
            save_data("records", pd.concat([records_df, new_rec]))
            st.success("✅ 扣除成功")
            time.sleep(0.8)
            st.rerun()

# --- 4. 批量删除弹窗 ---
@st.dialog("⚠️ 确认批量删除")
def confirm_batch_delete():
    members_df = read_data("members")
    items_df = read_data("salon_items")
    records_df = read_data("records")
    
    selected_phones = st.session_state.get('selected_members', [])
    if not selected_phones:
        st.warning("未勾选会员")
        return

    # 过滤选中的会员信息
    targets = members_df[members_df['phone'].astype(str).isin([str(p) for p in selected_phones])]
    
    # 财务校验
    forbidden = targets[(targets['balance'] != 0) | (targets['debt'] != 0)]
    if not forbidden.empty:
        st.error("以下会员尚有余款或欠款，无法删除：")
        st.dataframe(forbidden[['name', 'phone', 'balance', 'debt']], hide_index=True)
        return

    st.warning(f"即将永久删除 {len(targets)} 位会员的所有资料、持有资产和消费历史。")
    confirm = st.text_input("请输入 '确认删除' 以执行操作")
    
    if st.button("🔥 确认永久删除", type="primary", use_container_width=True):
        if confirm == "确认删除":
            # 逻辑：保留“不在选中列表”中的行
            new_members = members_df[~members_df['phone'].astype(str).isin([str(p) for p in selected_phones])]
            new_items = items_df[~items_df['member_phone'].astype(str).isin([str(p) for p in selected_phones])]
            new_records = records_df[~records_df['member_phone'].astype(str).isin([str(p) for p in selected_phones])]
            
            save_data("members", new_members)
            save_data("salon_items", new_items)
            save_data("records", new_records)
            
            st.session_state.selected_members = []
            st.session_state.batch_delete_mode = False
            st.success("✅ 会员及关联数据已清理")
            time.sleep(1)
            st.rerun()
        else:
            st.error("验证码输入错误")

# --- 5. 删除产品弹窗 ---
@st.dialog("⚠️ 确认删除产品")
def confirm_delete_product(prod_name):
    prods_df = read_data("products")
    
    st.warning(f"确认删除产品 **{prod_name}** 吗？")
    st.caption("注意：若该产品已有销售记录，建议保留以维护报表完整性。")
    
    c1, c2 = st.columns(2)
    if c1.button("🗑️ 确认", type="primary", use_container_width=True):
        new_prods = prods_df[prods_df['prod_name'] != prod_name]
        save_data("products", new_prods)
        st.success("已删除")
        time.sleep(0.5)
        st.rerun()
    if c2.button("取消", use_container_width=True):
        st.rerun()
