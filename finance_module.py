import streamlit as st
import pandas as pd
import json
import time
import plotly.express as px
from datetime import date, datetime
from db_manager import read_data

def show_financial_report(data_bundle=None):
    st.header("📊 报表与统计中心")

    # --- 1. 数据加载优化 (优先使用传入的内存数据) ---
    if data_bundle:
        df = data_bundle.get("records") if data_bundle.get("records") is not None else read_data("records")
        df_members = data_bundle.get("members") if data_bundle.get("members") is not None else read_data("members")
        df_inventory = data_bundle.get("products") if data_bundle.get("products") is not None else read_data("products")
        # salon_items 通常在 main 里的 bundle 也有预加载
        df_salon_items = data_bundle.get("salon_items") if data_bundle.get("salon_items") is not None else read_data("salon_items")
    else:
        # 兼容性兜底
        df = read_data("records")
        df_members = read_data("members")
        df_inventory = read_data("products")
        df_salon_items = read_data("salon_items")

    if df.empty:
        st.info("暂无交易记录")
        return

    # --- 核心逻辑：智能姓名映射 ---
    name_map = {}
    if not df_members.empty:
        name_counts = df_members['name'].value_counts()
        for _, row in df_members.iterrows():
            p, n = str(row['phone']), row['name']
            if name_counts.get(n, 0) > 1:
                suffix = p[-4:] if len(p) >= 4 else p
                name_map[p] = f"{n}({suffix})"
            else:
                name_map[p] = n

    # 预处理数据格式
    df['date'] = pd.to_datetime(df['date'])
    df['日期'] = df['date'].dt.date
    df['member_phone'] = df['member_phone'].astype(str).str.replace('.0', '', regex=False)
    df['客户姓名'] = df['member_phone'].map(name_map).fillna(df['member_phone'])

    # --- 2. 时间范围选择 ---
    with st.container(border=True):
        st.subheader("📅 时间范围选择")
        col_t1, col_t2 = st.columns(2)
        today = date.today()
        start_date = col_t1.date_input("开始日期", today, key="rep_start")
        end_date = col_t2.date_input("结束日期", today, key="rep_end")

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

    # --- 4. 销售走势 ---
    st.divider()
    st.subheader("📈 销售额变动走势")
    trend_data = df_filtered.groupby('日期')['total_amount'].sum().reset_index()
    fig_trend = px.line(trend_data, x='日期', y='total_amount', markers=True, template="plotly_white", color_discrete_sequence=['#C1A088'])
    fig_trend.update_layout(dragmode='pan', yaxis_tickprefix="¥")
    st.plotly_chart(fig_trend, use_container_width=True, config={'displayModeBar': False})

    # --- 5. 产品销量分布 ---
    st.divider()
    st.subheader("📦 库存产品销量分布")
    inventory_items = df_inventory['prod_name'].tolist() if not df_inventory.empty else []

    def map_to_inventory(item_str):
        for p_name in inventory_items:
            if p_name in str(item_str):
                return p_name
        return None

    df_filtered['标准名称'] = df_filtered['items'].apply(map_to_inventory)
    df_products_only = df_filtered.dropna(subset=['标准名称']).copy()

    if df_products_only.empty:
        st.info("选定期间内暂无匹配库存产品的销售记录。")
    else:
        product_stats = df_products_only.groupby('标准名称').agg(
            销量=('total_amount', 'count'),
            营收额=('total_amount', 'sum')
        ).reset_index().sort_values('销量', ascending=False)

        col_p1, col_p2 = st.columns([1.5, 1])
        with col_p1:
            fig_bar = px.bar(product_stats, x='标准名称', y='销量', color='销量', color_continuous_scale='Brwnyl')
            st.plotly_chart(fig_bar, use_container_width=True)
        with col_p2:
            st.dataframe(product_stats, use_container_width=True, hide_index=True)

    # --- 6. 产品库存实时监控 ---
    st.divider()
    st.subheader("📦 产品库存实时监控")
    if df_inventory.empty:
        st.info("暂无库存数据")
    else:
        idx1, idx2, idx3 = st.columns(3)
        total_items = df_inventory['stock'].sum()
        df_inventory['price'] = pd.to_numeric(df_inventory['price'], errors='coerce').fillna(0)
        total_value = (df_inventory['stock'] * df_inventory['price']).sum()
        low_stock_count = len(df_inventory[df_inventory['stock'].astype(float) < 5])

        idx1.metric("总库存件数", f"{total_items} 件")
        idx2.metric("库存总货值", f"¥{total_value:,.2f}")
        idx3.metric("预警商品数", f"{low_stock_count} 种", delta="-需补货" if low_stock_count > 0 else None, delta_color="inverse")

        df_inv_show = df_inventory.copy()
        df_inv_show['库存状态'] = (df_inv_show['stock'].astype(float) / 50).clip(0, 1)
        st.dataframe(
            df_inv_show,
            column_config={
                "prod_name": "产品名称",
                "stock": st.column_config.NumberColumn("当前库存", format="%d 件"),
                "price": st.column_config.NumberColumn("单价", format="¥%.2f"),
                "库存状态": st.column_config.ProgressColumn("充盈度", min_value=0, max_value=1),
            },
            use_container_width=True, hide_index=True
        )

    # --- 7. 活动营销统计 (含穿透) ---
    st.divider()
    st.subheader("🎟️ 活动营销分析")
    # 兼容原版筛选逻辑
    df_act_raw = df_filtered[df_filtered['items'].str.contains('活动|🎁', na=False)].copy()

    if df_act_raw.empty:
        st.info("选定期间内暂无活动记录")
    else:
        df_act_raw['活动项目'] = df_act_raw['items'].str.extract(r'([活动|🎁][^,，]+)')
        unique_acts = sorted(df_act_raw['活动项目'].dropna().unique().tolist())
        selected_act = st.selectbox("🎯 筛选特定活动", ["全部活动"] + unique_acts, key="act_filter")

        df_target = df_act_raw if selected_act == "全部活动" else df_act_raw[df_act_raw['活动项目'] == selected_act]

        summary_data = df_target.groupby('活动项目').agg(
            营收金额=('total_amount', 'sum'),
            参与人次=('total_amount', 'count'),
            平均客单=('total_amount', 'mean')
        ).reset_index().sort_values('营收金额', ascending=False)

        st.dataframe(summary_data, use_container_width=True, hide_index=True)

        with st.expander(f"📋 查看【{selected_act}】参与会员名单", expanded=True):
            display_list = df_target[['date', '客户姓名', 'member_phone', 'total_amount', 'staff_name']].copy()
            display_list['date'] = display_list['date'].dt.strftime('%Y-%m-%d %H:%M')
            display_list.columns = ["办理时间", "姓名", "手机号", "支付金额", "经办人"]

            selection = st.dataframe(
                display_list,
                use_container_width=True, hide_index=True,
                on_select="rerun", selection_mode="single-row",
                key="act_selection"
            )

            if selection.selection.rows:
                idx = selection.selection.rows[0]
                sel_phone = str(display_list.iloc[idx]['手机号'])
                sel_name = display_list.iloc[idx]['姓名']

                st.markdown(f"#### 📇 会员深度资料：{sel_name}")
                m_info = df_members[df_members['phone'].astype(str).str.contains(sel_phone)]
                m_row = m_info.iloc[0] if not m_info.empty else {"balance": 0, "debt": 0}

                k1, k2, k3 = st.columns(3)
                k1.metric("累计消费", f"¥{df[df['member_phone']==sel_phone]['total_amount'].sum():,.2f}")
                k2.metric("当前余额", f"¥{float(m_row['balance']):,.2f}")
                k3.metric("当前欠款", f"¥{float(m_row['debt']):,.2f}")

                st.write("**📦 当前持有院装资产**")
                user_items = df_salon_items[df_salon_items['member_phone'].astype(str).str.contains(sel_phone)]
                if not user_items.empty:
                    st.dataframe(user_items[['item_name', 'total_qty', 'status']].rename(
                        columns={'item_name':'名称', 'total_qty':'剩余', 'status':'状态'}), 
                        use_container_width=True, hide_index=True)

    # --- 8. 交易流水明细 ---
    st.divider()
    st.subheader("📜 交易流水明细")
    df_sales_only = df_filtered[
        (~df_filtered['items'].str.contains('使用:|核销|消耗', na=False)) & (df_filtered['total_amount'] > 0)
    ].copy()

    col_f1, col_f2 = st.columns([2, 1])
    search_n = col_f1.text_input("🔍 搜索姓名或手机号", key="flow_search")
    pay_methods = ["全部支付方式"] + sorted(df_sales_only['status'].unique().tolist())
    selected_method = col_f2.selectbox("💳 支付方式", pay_methods, key="flow_pay")

    display_df = df_sales_only.copy()
    if search_n:
        display_df = display_df[(display_df['客户姓名'].str.contains(search_n)) | (display_df['member_phone'].str.contains(search_n))]
    if selected_method != "全部支付方式":
        display_df = display_df[display_df['status'] == selected_method]

    st.dataframe(display_df[['date', '客户姓名', 'items', 'total_amount', 'status', 'staff_name']].sort_values("date", ascending=False),
                 use_container_width=True, hide_index=True)
