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
    col_a, col_b = st.columns([1, 1.2])
    with col_a:
        st.subheader("🛍️ 选购")
        t1, t2 = st.tabs(["单品/项目", "活动礼包"])
        with t1:
            # 1. 业务类别选择

            p_type = st.radio("业务类别", ["实物产品", "服务项目"], horizontal=True, key="pos_p_type")

            # 2. 获取数据与用途筛选
            if p_type == "实物产品":
                # 新增：实物产品区分用途
                usage = st.radio("使用方式", ["带走", "在店用"], horizontal=True, key="pos_usage")
                prods = pd.read_sql("SELECT * FROM products WHERE type='实物产品' AND stock > 0", conn)
            else:
                usage = None
                prods = pd.read_sql("SELECT * FROM products WHERE type='服务项目'", conn)

            if not prods.empty:
                # 3. 选择名称
                p_names = prods['prod_name'].tolist()
                p = st.selectbox(f"选择{p_type}名称", p_names, key="pos_sel_p")

                selected_info = prods[prods['prod_name'] == p].iloc[0]
                st.caption(
                    f"💰 单价: ¥{selected_info['price']} | 📦 当前库存: {selected_info['stock']} {selected_info['unit']}")

                qty = st.number_input("数量", 1, 100, 1, key="pos_qty")

                # 4. 自动逻辑判定
                if p_type == "实物产品":
                    # “在店用”强制存为次卡，“带走”则不存
                    is_s = True if usage == "在店用" else False
                    st.info(f"💡 模式：{usage}（{'结算后存入会员资产' if is_s else '仅扣除店内库存'}）")
                else:
                    is_s = st.checkbox("存为次卡", value=True, key="pos_is_s")

                # pos_module.py

                if st.button("➕ 加入购物车", use_container_width=True, type="primary"):
                    # 1. 获取规格折算系数
                    try:
                        product_spec = int(selected_info['category']) if str(selected_info['category']).isdigit() else 1
                    except:
                        product_spec = 1

                    # --- 核心改进：统一名称处理 ---
                    # display_name 仅用于购物车列表显示，带上“(在店用)”方便你看
                    display_name = f"{p} ({usage})" if (p_type == "实物产品" and usage) else p

                    st.session_state.cart.append({
                        "id": datetime.now().timestamp(),
                        "name": display_name,  # 购物车显示的名称
                        "raw_name": p,  # 关键：存入数据库的名称必须是原始名，不带后缀
                        "price": selected_info['price'],
                        "qty": qty,  # 扣库存用量
                        "salon_qty": qty * product_spec,  # 存入次卡的实际片数/次数
                        "type": "prod",
                        "is_salon": is_s
                    })
                    # ------------------------------------

                    st.success(f"已加入清单")
                    st.rerun()

            else:
                st.warning(f"⚠️ 库中暂无可用的{p_type}，请先进行补货。")

        with t2:
            acts = pd.read_sql("SELECT * FROM activities WHERE is_open=1", conn)
            if not acts.empty:
                an = st.selectbox("选择活动", acts['name'].tolist())
                if st.button("🎁 购买活动"):
                    ai = acts[acts['name'] == an].iloc[0]
                    st.session_state.cart.append(
                        {"id": datetime.now().timestamp(), "name": f"🎁 {an}", "price": ai['price'], "qty": 1,
                         "type": "act", "act_id": ai['id']})
                    st.rerun()

    with col_b:
        st.subheader("📋 结算")
        if not st.session_state.cart:
            st.write("购物车是空的")
        else:
            for idx, item in enumerate(st.session_state.cart):
                c1, c2, c3 = st.columns([3, 1, 0.8])
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
