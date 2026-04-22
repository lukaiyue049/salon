import streamlit as st
import pandas as pd
import json
from db_manager import get_conn


def show_activity_center():
    st.header("🎯 活动礼包")
    conn = get_conn()
    t1, t2, t3 = st.tabs(["设置活动礼包", "批量办理活动", "活动列表管理"])

    # --- t1: 设置活动礼包 ---
    # activity_module.py

    # --- t1: 设置活动礼包 ---
    with t1:
        st.subheader("🎁 新增活动礼包")
        col_n, col_p = st.columns([2, 1])
        n = col_n.text_input("活动名称", placeholder="如：焕颜补水套装")
        p = col_p.number_input("礼包总价格", min_value=0.0)

        # --- 【新增：分类选择布局】 ---
        cat_col, search_col = st.columns([1, 2])
        with cat_col:
            # 添加内容类型下拉框
            gift_cat = st.selectbox("内容类型", ["全部", "实物产品", "服务项目"], key="gift_cat_filter")

        with search_col:
            # 根据类型查询数据库
            if gift_cat == "全部":
                prods_df = pd.read_sql("SELECT prod_name, unit, type FROM products", conn)
            else:
                prods_df = pd.read_sql("SELECT prod_name, unit, type FROM products WHERE type=?", conn,
                                       params=(gift_cat,))

            # 构造带前缀的列表
            prod_list = [f"[{row['type']}] {row['prod_name']}" for _, row in prods_df.iterrows()]

            # 【重要】为了防止切换分类时已选中的项丢失，unit_map 需要包含所有产品
            full_df = pd.read_sql("SELECT prod_name, unit, type FROM products", conn)
            unit_map = {f"[{row['type']}] {row['prod_name']}": row['unit'] for _, row in full_df.iterrows()}

            # 搜索框
            sel = st.multiselect("选择内含产品/服务", prod_list)
        # ----------------------------

        extra = st.text_input("➕ 自定义福利 (如：赠送头部按摩)", placeholder="不填则不加")

        counts = {}
        if sel or extra:
            st.write("--- 设定数量 ---")
            all_to_show = sel + ([extra] if extra else [])
            # 设定每行最多显示 4 个项目，防止列数过多导致排版混乱
            cols = st.columns(4)
            for idx, it in enumerate(all_to_show):
                u = unit_map.get(it, "次")
                # 使用取模运算循环分配到 4 列中
                counts[it] = cols[idx % 4].number_input(f"{it}({u})", 1, 100, 1, key=f"act_{it}")

        note = st.text_area("📝 活动备注", placeholder="在此填写活动规则、有效期等...")

        if st.button("🚀 立即发布活动", type="primary", use_container_width=True):
            if n and counts:
                pkg_json = json.dumps(counts, ensure_ascii=False)
                conn.execute("INSERT INTO activities (name, packages, price, is_open, note) VALUES (?,?,?,1,?)",
                             (n, pkg_json, p, note))
                conn.commit()

                st.toast(f"✅ 活动【{n}】已成功发布！", icon="🎁")
                import time
                time.sleep(1.5)
                st.rerun()

    # --- t2: 批量办理活动 ---
    with t2:
        st.info("注意：批量办理仅支持现金/转账扣款（现结），将自动生成财务流水")
        acts = pd.read_sql("SELECT * FROM activities WHERE is_open=1", conn)
        if not acts.empty:
            sel_act = st.selectbox("选择活动", acts['name'].tolist())
            ad = acts[acts['name'] == sel_act].iloc[0]
            pkg = json.loads(ad['packages'])

            ms = pd.read_sql("SELECT phone, name FROM members", conn)
            targs = st.multiselect("选择办理会员", ms['phone'].tolist(),
                                   format_func=lambda x: f"{ms[ms['phone'] == x]['name'].values[0]}({x})")

            staff_df = pd.read_sql("SELECT name FROM staffs", conn)
            staff_list = staff_df['name'].tolist() if not staff_df.empty else ["店长"]
            staff = st.selectbox("经办人", staff_list)

            if st.button("🚀 批量确认办理", type="primary"):
                if not targs:
                    st.warning("请至少选择一个会员")
                else:
                    cur = conn.cursor()
                    for p_phone in targs:
                        for it_name, it_qty in pkg.items():
                            cur.execute("UPDATE products SET stock = MAX(0, stock - ?), last_updated = datetime('now','localtime') WHERE prod_name = ?",
                                (it_qty, it_name))
                            cur.execute(
                                "INSERT INTO salon_items (member_phone, item_name, total_qty, status) VALUES (?,?,?,?)",
                                (p_phone, it_name, it_qty, "使用中"))
                        cur.execute(
                            "INSERT INTO records (member_phone, date, items, total_amount, status, staff_name) VALUES (?, datetime('now','localtime'), ?, ?, '现结', ?)",
                            (p_phone, f"批量办理活动:{sel_act}", ad['price'], staff))
                    conn.commit()
                    st.success(f"已成功办理！")
                    st.rerun()

    # --- t3: 活动列表管理 (包含实时详情) ---
    with t3:
        st.subheader("📋 已发布活动管理")
        df_acts = pd.read_sql("SELECT * FROM activities", conn)

        if df_acts.empty:
            st.info("暂无活动记录。")
        else:
            # 1. 列表展示与操作
            for _, row in df_acts.iterrows():
                status_icon = "🟢" if row['is_open'] == 1 else "⚪"
                with st.expander(f"{status_icon} {row['name']} | 价格: ¥{row['price']}"):
                    if row.get('note'):
                        st.info(f"📝 **活动备注/福利：**\n\n{row['note']}")

                    st.write("**🎁 礼包内容：**")
                    pkg_data = json.loads(row['packages'])
                    if pkg_data:
                        prods_df = pd.read_sql("SELECT prod_name, unit FROM products", conn)
                        unit_map = dict(zip(prods_df.prod_name, prods_df.unit))
                        it_cols = st.columns(4)
                        for i, (name, count) in enumerate(pkg_data.items()):
                            u = unit_map.get(name, "次")
                            with it_cols[i % 4]:
                                st.info(f"**{name}**\n\n{count}{u}")

                    st.write("---")
                    c_btn1, c_btn2 = st.columns(2)
                    btn_txt = "停用该活动" if row['is_open'] else "启用该活动"
                    if c_btn1.button(btn_txt, key=f"btn_sw_{row['id']}", use_container_width=True):
                        new_stat = 0 if row['is_open'] == 1 else 1
                        conn.execute("UPDATE activities SET is_open=? WHERE id=?", (new_stat, row['id']))
                        conn.commit()
                        st.rerun()

                    if c_btn2.button("🗑️ 删除活动", key=f"btn_del_{row['id']}", type="secondary",
                                     use_container_width=True):
                        conn.execute("DELETE FROM activities WHERE id=?", (row['id'],))
                        conn.commit()
                        st.rerun()
"""""
            # 2. 活动详情统计部分 (现在放在 t3 底部)
            st.divider()
            st.subheader("📈 活动参与详情")

            stats_sql = """"""
            stats_df = pd.read_sql(stats_sql, conn)

            col_summary, col_select = st.columns([1, 1])
            with col_summary:
                st.dataframe(stats_df, use_container_width=True, hide_index=True)

            with col_select:
                sel_stat = st.selectbox("🎯 选择活动查看参与名单", ["请选择活动..."] + stats_df['活动名称'].tolist())

            if sel_stat != "请选择活动...":
                st.write(f"👥 **{sel_stat}** 的参与名单 (点击行查看资料卡)")
                members_sql = """"""
                detailed_members_df = pd.read_sql(members_sql, conn, params=(f'%{sel_stat}%',))

                if not detailed_members_df.empty:
                    display_df = detailed_members_df[['姓名', '手机号', '购买日期', '支付金额']]
                    selection = st.dataframe(display_df, use_container_width=True, hide_index=True, on_select="rerun",
                                             selection_mode="single-row")

                    if selection.selection.rows:
                        idx = selection.selection.rows[0]
                        m_info = detailed_members_df.iloc[idx]
                        sel_phone = m_info['手机号']

                        st.markdown(f"#### 🛍️ 会员持有产品卡：{m_info['姓名']}")

                        # 【核心增加】：查询该用户的所有非核销购买记录，解析出持有产品
                        # 逻辑：查询该手机号的所有流水，排除“使用/核销”字样
                        holdings_sql = """"""
                        df_holdings = pd.read_sql(holdings_sql, conn, params=(sel_phone,))

                        with st.container(border=True):
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                st.write("**👤 客户概览**")
                                st.write(f"**姓名:** {m_info['姓名']}")
                                st.write(f"**手机:** {sel_phone}")
                                st.write(f"**累计订单:** {len(df_holdings)} 单")
                                # 保持原有的备注信息显示
                                st.write("**备注:**")
                                st.caption(m_info['备注信息'] if m_info['备注信息'] else "暂无备注")

                            with c2:
                                st.write("**📦 已购产品/服务清单**")
                                if df_holdings.empty:
                                    st.caption("暂无购买记录")
                                else:
                                    # 格式化日期和金额显示
                                    df_holdings['date'] = pd.to_datetime(df_holdings['date']).dt.strftime('%Y-%m-%d')
                                    st.dataframe(
                                        df_holdings,
                                        column_config={
                                            "date": "购买日期",
                                            "items": "项目名称",
                                            "total_amount": st.column_config.NumberColumn("支付金额", format="¥%.2f"),
                                            "status": "支付方式"
                                        },
                                        hide_index=True,
                                        use_container_width=True
                                    )
                else:
                    st.info("该活动暂无购买记录。")
                                            """