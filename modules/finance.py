import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

def show(data_bundle):
    st.header("📊 报表与统计中心")
    df = data_bundle["records"]
    df_members = data_bundle["members"]
    df_inventory = data_bundle["products"]
    df_salon_items = data_bundle["salon_items"]

    if df.empty:
        st.info("暂无交易记录")
        return

    # 姓名映射
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

    df['date'] = pd.to_datetime(df['date'])
    df['日期'] = df['date'].dt.date
    df['member_phone'] = df['member_phone'].astype(str).str.replace('.0', '', regex=False)
    df['客户姓名'] = df['member_phone'].map(name_map).fillna(df['member_phone'])

    # 时间筛选
    with st.container(border=True):
        st.subheader("📅 时间范围")
        col1, col2 = st.columns(2)
        start = col1.date_input("开始日期", date.today())
        end = col2.date_input("结束日期", date.today())
        mask = (df['日期'] >= start) & (df['日期'] <= end)
        df_filtered = df.loc[mask].copy()

    # 核心指标
    with st.container(border=True):
        st.subheader("💰 经营核心指标")
        if df_filtered.empty:
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

    # 销售走势
    st.subheader("📈 销售额变动走势")
    trend = df_filtered.groupby('日期')['total_amount'].sum().reset_index()
    fig = px.line(trend, x='日期', y='total_amount', markers=True, template="plotly_white", color_discrete_sequence=['#C1A088'])
    fig.update_layout(yaxis_tickprefix="¥")
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # 产品销量分布
    st.subheader("📦 库存产品销量分布")
    inventory_items = df_inventory['prod_name'].tolist() if not df_inventory.empty else []
    def map_inv(item_str):
        for p in inventory_items:
            if p in str(item_str):
                return p
        return None
    df_filtered['标准名称'] = df_filtered['items'].apply(map_inv)
    df_prod = df_filtered.dropna(subset=['标准名称'])
    if df_prod.empty:
        st.info("选定期间内无产品销量")
    else:
        stats = df_prod.groupby('标准名称').agg(销量=('total_amount','count'), 营收额=('total_amount','sum')).reset_index().sort_values('销量', ascending=False)
        col_p1, col_p2 = st.columns([1.5,1])
        with col_p1:
            fig_bar = px.bar(stats, x='标准名称', y='销量', color='销量', color_continuous_scale='Brwnyl')
            st.plotly_chart(fig_bar, use_container_width=True)
        with col_p2:
            st.dataframe(stats, use_container_width=True, hide_index=True)

    # 库存实时监控
    st.subheader("📦 产品库存实时监控")
    if not df_inventory.empty:
        total_items = df_inventory['stock'].sum()
        df_inventory['price'] = pd.to_numeric(df_inventory['price'], errors='coerce').fillna(0)
        total_value = (df_inventory['stock'] * df_inventory['price']).sum()
        low_stock = len(df_inventory[df_inventory['stock'].astype(float) < 5])
        c1, c2, c3 = st.columns(3)
        c1.metric("总库存件数", f"{total_items} 件")
        c2.metric("库存总货值", f"¥{total_value:,.2f}")
        c3.metric("预警商品数", low_stock, delta="-需补货" if low_stock > 0 else None, delta_color="inverse")
        inv_show = df_inventory.copy()
        inv_show['库存状态'] = (inv_show['stock'].astype(float) / 50).clip(0, 1)
        st.dataframe(inv_show, column_config={
            "prod_name": "产品名称", "stock": st.column_config.NumberColumn("当前库存", format="%d 件"),
            "price": st.column_config.NumberColumn("单价", format="¥%.2f"),
            "库存状态": st.column_config.ProgressColumn("充盈度", min_value=0, max_value=1),
        }, use_container_width=True, hide_index=True)

    # 活动营销分析
    st.divider()
    st.subheader("🎟️ 活动营销分析")
    df_act = df_filtered[df_filtered['items'].str.contains('活动|🎁', na=False)].copy()
    if df_act.empty:
        st.info("无活动记录")
    else:
        df_act['活动项目'] = df_act['items'].str.extract(r'([活动|🎁][^,，]+)')
        acts = sorted(df_act['活动项目'].dropna().unique())
        sel_act = st.selectbox("筛选活动", ["全部活动"] + acts)
        df_target = df_act if sel_act == "全部活动" else df_act[df_act['活动项目'] == sel_act]
        summary = df_target.groupby('活动项目').agg(营收金额=('total_amount','sum'), 参与人次=('total_amount','count'), 平均客单=('total_amount','mean')).reset_index().sort_values('营收金额', ascending=False)
        st.dataframe(summary, use_container_width=True, hide_index=True)
        with st.expander(f"查看 {sel_act} 参与会员"):
            show_list = df_target[['date', '客户姓名', 'member_phone', 'total_amount', 'staff_name']].copy()
            show_list['date'] = show_list['date'].dt.strftime('%Y-%m-%d %H:%M')
            show_list.columns = ["办理时间", "姓名", "手机号", "支付金额", "经办人"]
            selection = st.dataframe(show_list, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="act_sel")
            if selection.selection.rows:
                idx = selection.selection.rows[0]
                sel_phone = str(show_list.iloc[idx]['手机号'])
                sel_name = show_list.iloc[idx]['姓名']
                st.markdown(f"#### 会员深度资料：{sel_name}")
                m_info = df_members[df_members['phone'].astype(str) == sel_phone]
                if not m_info.empty:
                    total_spent = df[df['member_phone'] == sel_phone]['total_amount'].sum()
                    c1, c2, c3 = st.columns(3)
                    c1.metric("累计消费", f"¥{total_spent:,.2f}")
                    c2.metric("当前余额", f"¥{float(m_info.iloc[0]['balance']):,.2f}")
                    c3.metric("当前欠款", f"¥{float(m_info.iloc[0]['debt']):,.2f}")
                user_items = df_salon_items[df_salon_items['member_phone'].astype(str) == sel_phone]
                if not user_items.empty:
                    st.write("**持有院装资产**")
                    st.dataframe(user_items[['item_name', 'total_qty', 'status']].rename(columns={'item_name':'名称','total_qty':'剩余','status':'状态'}), use_container_width=True, hide_index=True)

    # 交易流水明细
    st.divider()
    st.subheader("📜 交易流水明细")
    df_sales = df_filtered[~df_filtered['items'].str.contains('使用:|核销|消耗', na=False) & (df_filtered['total_amount'] > 0)].copy()
    search = st.text_input("🔍 搜索姓名或手机号")
    method = st.selectbox("支付方式", ["全部"] + sorted(df_sales['status'].unique().tolist()))
    if search:
        df_sales = df_sales[df_sales['客户姓名'].str.contains(search) | df_sales['member_phone'].str.contains(search)]
    if method != "全部":
        df_sales = df_sales[df_sales['status'] == method]
    st.dataframe(df_sales[['date', '客户姓名', 'items', 'total_amount', 'status', 'staff_name']].sort_values("date", ascending=False), use_container_width=True, hide_index=True)
