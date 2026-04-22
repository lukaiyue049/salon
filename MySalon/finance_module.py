import streamlit as st
import pandas as pd
from db_manager import get_conn
import plotly.express as px
from datetime import date


def show_financial_report():
    conn = get_conn()

    # 1. 数据加载与预处理
    df = pd.read_sql("SELECT * FROM records", conn)
    df_members = pd.read_sql("SELECT name, phone FROM members", conn)
    # 获取库存产品列表，用于过滤产品销量表
    df_inventory = pd.read_sql("SELECT prod_name FROM products", conn)
    inventory_items = df_inventory['prod_name'].tolist()

    if df.empty:
        st.info("暂无交易记录")
        return

    # --- 核心逻辑：智能姓名映射 (处理重名) ---
    name_map = {}
    name_counts = df_members['name'].value_counts()
    for _, row in df_members.iterrows():
        p, n = row['phone'], row['name']
        if name_counts.get(n, 0) > 1:
            suffix = p[-4:] if len(p) >= 4 else p
            name_map[p] = f"{n}({suffix})"
        else:
            name_map[p] = n

    df['date'] = pd.to_datetime(df['date'])
    df['日期'] = df['date'].dt.date
    df['客户姓名'] = df['member_phone'].map(name_map).fillna(df['member_phone'])

    # --- 2. 顶部时间范围选择 (默认今天) ---
    with st.container(border=True):
        st.subheader("📅 时间范围选择")
        col_t1, col_t2 = st.columns(2)
        today = date.today()
        start_date = col_t1.date_input("开始日期", today)
        end_date = col_t2.date_input("结束日期", today)

        mask = (df['日期'] >= start_date) & (df['日期'] <= end_date)
        df_filtered = df.loc[mask].copy()

    # --- 3. 经营核心指标 ---
    with st.container(border=True):
        st.subheader("💰 经营核心指标")
        if df_filtered.empty:
            st.warning(f"⚠️ {start_date} 至 {end_date} 期间暂无营业数据")
            total_rev = cash_rev = balance_rev = debt_rev = 0
        else:
            total_rev = df_filtered['total_amount'].sum()
            cash_rev = df_filtered[df_filtered['status'] == '现结']['total_amount'].sum()
            balance_rev = df_filtered[df_filtered['status'] == '余额扣款']['total_amount'].sum()
            debt_rev = df_filtered[df_filtered['status'] == '挂账']['total_amount'].sum()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("总营业额", f"¥{total_rev:,.2f}")
        m2.metric("现金收入", f"¥{cash_rev:,.2f}")
        m3.metric("耗卡金额", f"¥{balance_rev:,.2f}")
        m4.metric("新增挂账", f"¥{debt_rev:,.2f}")

    if df_filtered.empty:
        return

    # --- 4. 销售走势 (Plotly交互图表) ---
    st.divider()
    st.subheader("📈 销售额变动走势")
    trend_data = df_filtered.groupby('日期')['total_amount'].sum().reset_index()
    # 升级为 Plotly 以支持缩放标识并防止滚轮误操作
    fig_trend = px.line(trend_data, x='日期', y='total_amount', markers=True, template="plotly_white")
    fig_trend.update_layout(dragmode='pan', yaxis_tickprefix="¥")
    st.plotly_chart(fig_trend, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': True})


    # --- 6. 库存产品销量分布 (改进版：支持关键词模糊匹配) ---
    st.divider()
    st.subheader("📦 库存产品销量分布")

    # 1. 获取库存列表
    df_inventory = pd.read_sql("SELECT prod_name FROM products", conn)
    inventory_items = df_inventory['prod_name'].tolist()

    # 2. 编写模糊匹配逻辑：检查流水 items 是否包含库存中的任何一个名称
    def map_to_inventory(item_str):
        for p_name in inventory_items:
            if p_name in str(item_str):  # 只要包含“面膜”或“水”就匹配成功
                return p_name
        return None

    # 3. 生成仅含库存产品的数据集，并将名称统一为库存标准名
    df_filtered['标准名称'] = df_filtered['items'].apply(map_to_inventory)
    df_products_only = df_filtered.dropna(subset=['标准名称']).copy()

    if df_products_only.empty:
        st.info("选定期间内暂无匹配库存产品的销售记录。")
    else:
        # 4. 按标准名称重新统计
        product_stats = df_products_only.groupby('标准名称').agg(
            销量=('total_amount', 'count'),
            营收额=('total_amount', 'sum')
        ).reset_index().sort_values('销量', ascending=False)

        col_p1, col_p2 = st.columns([1.5, 1])
        with col_p1:
            # 5. 使用 Plotly 修正横坐标，确保只显示干净的产品名
            fig_bar = px.bar(product_stats, x='标准名称', y='销量', color='销量',
                             labels={'标准名称': '产品名称', '销量': '销售数量'})
            st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})
        with col_p2:
            st.dataframe(product_stats, use_container_width=True, hide_index=True)
        # --- 7. 新增：产品库存实时监控 (直观看板) ---
        st.divider()
        st.subheader("📦 产品库存实时监控")

        # 从数据库获取最新库存数据
        df_inv_status = pd.read_sql("SELECT prod_name, stock, price FROM products", conn)

        if df_inv_status.empty:
            st.info("暂无库存数据")
        else:
            # 1. 顶部核心指标
            idx1, idx2, idx3 = st.columns(3)
            total_items = df_inv_status['stock'].sum()
            total_value = (df_inv_status['stock'] * df_inv_status['price']).sum()
            low_stock_count = len(df_inv_status[df_inv_status['stock'] < 5])  # 假设低于5件为低库存

            idx1.metric("总库存件数", f"{total_items} 件")
            idx2.metric("库存总货值", f"¥{total_value:,.2f}")
            idx3.metric("预警商品数", f"{low_stock_count} 种", delta="-需补货" if low_stock_count > 0 else None,
                        delta_color="inverse")

            # 2. 直观的库存进度表
            # 假设我们设定一个“理想库存量”（比如50），用来计算当前库存的百分比进度
            ideal_stock = 50
            df_inv_status['库存状态'] = (df_inv_status['stock'] / ideal_stock).clip(0, 1)

            st.write("📊 库存余量百分比 (基于满载50件计算)")
            st.dataframe(
                df_inv_status,
                column_config={
                    "prod_name": "产品名称",
                    "stock": st.column_config.NumberColumn("当前库存", format="%d 件"),
                    "price": st.column_config.NumberColumn("单价", format="¥%.2f"),
                    "库存状态": st.column_config.ProgressColumn(
                        "充盈度",
                        help="库存比例示意图",
                        format=" ",
                        min_value=0,
                        max_value=1,
                    ),
                },
                use_container_width=True,
                hide_index=True
            )

            # 3. 库存预警：专门列出库存极低的商品
            if low_stock_count > 0:
                with st.expander("🚨 发现低库存商品，请及时补货"):
                    low_stock_df = df_inv_status[df_inv_status['stock'] < 5][['prod_name', 'stock']]
                    st.table(low_stock_df.rename(columns={"prod_name": "商品名称", "stock": "剩余件数"}))

    # --- 5. 活动营销深度统计 (升级版：点击名单穿透查看会员深度资料卡) ---
    st.divider()
    st.subheader("🎟️ 活动营销深度分析")

    # 获取包含“活动”关键字的原始数据
    df_act_raw = df_filtered[df_filtered['items'].str.contains('活动', na=False)].copy()

    if df_act_raw.empty:
        st.info("选定期间内暂无活动相关记录")
    else:
        # 【1. 名称净化逻辑】
        def clean_act_name(name):
            if ':' in str(name):
                return str(name).split(':')[-1].strip()
            return str(name).strip()

        df_act_raw['活动项目'] = df_act_raw['items'].apply(clean_act_name)

        # 【2. 活动筛选框】
        unique_acts = sorted(df_act_raw['活动项目'].unique().tolist())
        selected_act = st.selectbox("🎯 快速筛选特定活动进行穿透分析", ["全部活动"] + unique_acts)

        # 执行筛选
        df_target = df_act_raw if selected_act == "全部活动" else df_act_raw[
            df_act_raw['活动项目'] == selected_act]

        # 计算统计数据
        summary_data = df_target.groupby('活动项目').agg(
            营收金额=('total_amount', 'sum'),
            参与人次=('total_amount', 'count'),
            平均客单=('total_amount', 'mean')
        ).reset_index().sort_values('营收金额', ascending=False)

        # 【3. 核心指标看板】
        with st.container(border=True):
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("活动总营收", f"¥{summary_data['营收金额'].sum():,.2f}")
            kpi2.metric("总参与人次", f"{summary_data['参与人次'].sum()} 次")
            kpi3.metric("平均客单价", f"¥{summary_data['平均客单'].mean():,.2f}")

        # 【4. 净化后的汇总表】
        st.write("📊 活动汇总看板")
        st.dataframe(
            summary_data,
            column_config={
                "活动项目": st.column_config.TextColumn("活动项目", width="medium"),
                "营收金额": st.column_config.NumberColumn("营收金额", format="¥%.2f"),
                "参与人次": st.column_config.NumberColumn("成交单数", format="%d 单"),
                "平均客单": st.column_config.NumberColumn("单笔均价", format="¥%.2f"),
            },
            use_container_width=True,
            hide_index=True
        )

        # 【5. 详细名单表 (带选中穿透功能)】
        with st.expander(f"📋 查看【{selected_act}】参与会员详细名单", expanded=True):
            list_df = df_target[['date', 'member_phone', 'total_amount', 'staff_name']].copy()
            list_df['姓名'] = list_df['member_phone'].map(name_map).fillna(list_df['member_phone'])
            list_df['办理时间'] = list_df['date'].dt.strftime('%Y-%m-%d %H:%M')

            # 整理显示格式
            display_list = list_df[['办理时间', '姓名', 'member_phone', 'total_amount', 'staff_name']]
            display_list.columns = ["办理时间", "姓名", "手机号", "支付金额", "经办人"]

            selection = st.dataframe(
                display_list,
                column_config={
                    "支付金额": st.column_config.NumberColumn(format="¥%.2f"),
                    "手机号": st.column_config.TextColumn()
                },
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )

            # --- 深度资料卡显示逻辑 ---
            if selection.selection.rows:
                idx = selection.selection.rows[0]
                sel_phone = display_list.iloc[idx]['手机号']
                sel_name = display_list.iloc[idx]['姓名']

                st.markdown(f"### 📇 会员深度资料卡：{sel_name}")

                # 获取实时负债、余额与备注 (从 members 表)
                m_db = pd.read_sql("SELECT balance, debt, skin_info FROM members WHERE phone = ?", conn,
                                   params=(sel_phone,))
                m_db = m_db.iloc[0] if not m_db.empty else {"balance": 0, "debt": 0, "skin_info": ""}

                # 获取该会员全量消费记录 (用于计算累计消费额，不受顶部日期筛选限制)
                user_all_records = df[df['member_phone'] == sel_phone].copy()
                total_spent = user_all_records['total_amount'].sum()

                with st.container(border=True):
                    k1, k2, k3 = st.columns(3)
                    k1.metric("累计消费总额", f"¥{total_spent:,.2f}")
                    k2.metric("当前余额", f"¥{m_db['balance']:,.2f}")
                    k3.metric("当前欠款 (负债)", f"¥{m_db['debt']:,.2f}",
                              delta=f"需回收" if m_db['debt'] > 0 else None,
                              delta_color="inverse")

                    st.divider()

                    st.write("**📦 产品统计**")

                    # 修改后的 SQL：通过 CASE WHEN 确保“使用中”排在最前面，其余按状态排序
                    user_holdings = pd.read_sql(
                        """
                        SELECT item_name, total_qty, status 
                        FROM salon_items 
                        WHERE member_phone = ? AND total_qty > 0
                        ORDER BY (CASE WHEN status = '使用中' THEN 0 ELSE 1 END), status
                        """,
                        conn,
                        params=(sel_phone,)
                    )

                    if user_holdings.empty:
                        st.caption("暂无持有中的剩余项目或产品")
                    else:
                        # 渲染表格
                        st.dataframe(
                            user_holdings.rename(columns={
                                'item_name': '项目名称',
                                'total_qty': '剩余数量',
                                'status': '当前状态'
                            }),
                            use_container_width=True,
                            hide_index=True
                        )

                    if m_db['skin_info']:
                        st.info(f"📝 **系统备注：** {m_db['skin_info']}")
            else:
                st.info("💡 请点击上方名单中的任意一行，即可查看该会员的深度资料卡。")

    # --- 7. 会员消费画像 ---
    st.divider()
    st.subheader("👥 会员消费画像")
    member_profile = df_filtered.groupby('客户姓名').agg(
        消费次数=('total_amount', 'count'),
        消费总额=('total_amount', 'sum')
    ).reset_index()
    fig_member = px.scatter(member_profile, x="消费次数", y="消费总额", size="消费总额",
                            color="消费总额", text="客户姓名", hover_name="客户姓名", template="plotly_white")
    fig_member.update_traces(textposition='top center')
    st.plotly_chart(fig_member, use_container_width=True, config={'scrollZoom': False})

    # --- 8. 核心修改：交易流水明细 (纯销售/支付视角) ---
    st.divider()
    st.subheader("📜 交易流水明细 (仅显示支付/销售)")

    # 【优化1】过滤非销售信息：排除 items 中包含“使用:”或“核销”关键字的记录
    # 确保只看到“支付”类的销售信息
    df_sales_only = df_filtered[
        (~df_filtered['items'].str.contains('使用:|核销|消耗', na=False)) &
        (df_filtered['total_amount'] > 0)
        ].copy()

    # 【优化2】双重筛选：用户搜索 + 支付方式筛选
    col_f1, col_f2 = st.columns([2, 1])

    with col_f1:
        search_n = st.text_input("🔍 搜索客户姓名或手机号")
    with col_f2:
        # 自动获取当前存在的支付状态供筛选
        payment_methods = ["全部支付方式"] + sorted(df_sales_only['status'].unique().tolist())
        selected_method = st.selectbox("💳 支付方式筛选", payment_methods)

    # 执行过滤
    display_df = df_sales_only.copy()
    if search_n:
        display_df = display_df[
            (display_df['客户姓名'].str.contains(search_n, na=False)) |
            (display_df['member_phone'].str.contains(search_n, na=False))
            ]
    if selected_method != "全部支付方式":
        display_df = display_df[display_df['status'] == selected_method]

    # 排序与列名美化
    display_df = display_df.sort_values("date", ascending=False)

    # 动态确定显示列
    show_cols = ['id', '客户姓名', 'date', 'items', 'total_amount', 'status', 'staff_name']
    if 'note' in display_df.columns: show_cols.append('note')

    final_table = display_df[show_cols]
    final_table.columns = ["编号", "客户姓名", "交易时间", "消费内容", "支付金额", "支付方式", "经办人"] + (
        ["备注"] if 'note' in display_df.columns else [])

    if final_table.empty:
        st.caption("没有找到符合条件的支付记录")
    else:
        st.dataframe(
            final_table,
            column_config={
                "支付金额": st.column_config.NumberColumn(format="¥%.2f"),
                "交易时间": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"),
            },
            use_container_width=True,
            hide_index=True
        )

    csv = final_table.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 导出当前支付明细",
        data=csv,
        file_name=f"支付流水_{start_date}.csv",
        mime="text/csv",
        use_container_width=True
    )