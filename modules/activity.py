import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
from db_manager import read_data, save_data

def show(data_bundle):
    st.header("🎯 活动礼包")
    products_df = data_bundle["products"]
    members_df = data_bundle["members"]
    all_acts = data_bundle["activities"]
    records_df = data_bundle["records"]

    t1, t2, t3 = st.tabs(["设置活动礼包", "批量办理活动", "活动列表管理"])

    # ---------- 设置活动礼包 ----------
    with t1:
        st.subheader("🎁 新增活动礼包")
        col_n, col_p = st.columns([2,1])
        name = col_n.text_input("活动名称", placeholder="如：焕颜补水套装")
        price = col_p.number_input("礼包总价格", min_value=0.0)

        cat_col, search_col = st.columns([1,2])
        with cat_col:
            gift_cat = st.selectbox("内容类型", ["全部", "实物产品", "服务项目"])
        with search_col:
            if gift_cat == "全部":
                prods_df = products_df
            else:
                prods_df = products_df[products_df['type'] == gift_cat]
            prod_list = [f"[{row['type']}] {row['prod_name']}" for _, row in prods_df.iterrows()]
            unit_map = {f"[{row['type']}] {row['prod_name']}": row['unit'] for _, row in products_df.iterrows()}
            sel = st.multiselect("选择内含产品/服务", prod_list)

        extra = st.text_input("➕ 自定义福利 (如：赠送头部按摩)")
        counts = {}
        if sel or extra:
            st.write("--- 设定数量 ---")
            all_to_show = sel + ([extra] if extra else [])
            cols = st.columns(4)
            for idx, it in enumerate(all_to_show):
                u = unit_map.get(it, "次")
                counts[it] = cols[idx % 4].number_input(f"{it}({u})", 1, 100, 1, key=f"inp_{it}")

        note = st.text_area("📝 活动备注")

        if st.button("🚀 立即发布活动", type="primary", use_container_width=True):
            if name and counts:
                acts_latest = read_data("activities")
                new_act = pd.DataFrame([{
                    "id": int(time.time()), "name": name, "packages": json.dumps(counts, ensure_ascii=False),
                    "price": price, "is_open": 1, "note": note
                }])
                save_data("activities", pd.concat([acts_latest, new_act], ignore_index=True))
                st.success(f"活动【{name}】已发布")
                time.sleep(1)
                st.rerun()

    # ---------- 批量办理活动 ----------
    with t2:
        st.info("批量办理将自动扣除库存、增加会员资产并生成财务流水（现结模式）。")
        active_acts = all_acts[all_acts['is_open'] == 1]
        if active_acts.empty:
            st.warning("当前没有开启中的活动")
        else:
            sel_act_name = st.selectbox("选择活动", active_acts['name'].tolist())
            ad = active_acts[active_acts['name'] == sel_act_name].iloc[0]
            pkg = json.loads(ad['packages'])

            targs = st.multiselect(
                "选择办理会员",
                options=members_df['phone'].tolist(),
                format_func=lambda x: f"{members_df[members_df['phone']==x]['name'].values[0]} ({str(x)[-4:]})"
            )
            staff_list = data_bundle["staffs"]['name'].tolist() if not data_bundle["staffs"].empty else ["店长"]
            staff = st.selectbox("经办人", staff_list)

            if st.button("🚀 批量确认办理", type="primary", use_container_width=True):
                if not targs:
                    st.error("请至少选择一个会员")
                else:
                    with st.spinner("同步云端..."):
                        df_p = read_data("products")
                        df_si = read_data("salon_items")
                        df_r = read_data("records")
                        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        for phone in targs:
                            for it_full, it_qty in pkg.items():
                                pure_name = it_full.split("] ")[-1] if "] " in it_full else it_full
                                if pure_name in df_p['prod_name'].values:
                                    df_p.loc[df_p['prod_name'] == pure_name, 'stock'] -= it_qty
                                    df_p.loc[df_p['prod_name'] == pure_name, 'last_updated'] = now
                                    unit = df_p[df_p['prod_name'] == pure_name]['unit'].values[0]
                                else:
                                    unit = "次"
                                new_si = pd.DataFrame([{
                                    "member_phone": phone, "item_name": pure_name, "total_qty": it_qty,
                                    "used_qty": 0, "status": "使用中", "unit": unit, "buy_date": now
                                }])
                                df_si = pd.concat([df_si, new_si], ignore_index=True)
                            new_rec = pd.DataFrame([{
                                "member_phone": phone, "date": now, "items": f"活动:{sel_act_name}",
                                "total_amount": ad['price'], "status": "现结", "staff_name": staff
                            }])
                            df_r = pd.concat([df_r, new_rec], ignore_index=True)
                        save_data("products", df_p)
                        save_data("salon_items", df_si)
                        save_data("records", df_r)
                    st.balloons()
                    st.success(f"已为 {len(targs)} 位会员办理活动")
                    st.rerun()

    # ---------- 活动管理 ----------
    with t3:
        if all_acts.empty:
            st.info("暂无活动记录")
        else:
            df_display = all_acts.copy()
            for idx, row in df_display.iterrows():
                status_icon = "🟢" if int(row['is_open']) == 1 else "⚪"
                with st.expander(f"{status_icon} {row['name']} | 价格: ¥{row['price']}"):
                    st.write(f"📦 内容: {row['packages']}")
                    st.write(f"📝 备注: {row['note']}")
                    c1, c2, _ = st.columns([1,1,2])
                    if c1.button("切换状态", key=f"sw_{row['id']}"):
                        df_display.at[idx, 'is_open'] = 0 if int(row['is_open']) == 1 else 1
                        save_data("activities", df_display)
                        st.rerun()
                    if c2.button("🗑️ 删除", key=f"del_{row['id']}"):
                        df_display = df_display.drop(idx)
                        save_data("activities", df_display)
                        st.rerun()
            st.divider()
            st.subheader("📈 活动参与详情")
            act_records = records_df[records_df['items'].str.contains("活动:", na=False)].copy()
            if not act_records.empty:
                act_records['活动名称'] = act_records['items'].str.replace("活动:", "", regex=False)
                act_records['total_amount'] = pd.to_numeric(act_records['total_amount'], errors='coerce')
                stats = act_records.groupby('活动名称').agg(
                    参与人次=('member_phone', 'count'),
                    总收入额=('total_amount', 'sum')
                ).reset_index().sort_values('参与人次', ascending=False)
                st.table(stats)
            else:
                st.caption("暂无活动参与数据")
