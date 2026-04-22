import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
from db_manager import read_data, save_data

def show_activity_center(data_bundle=None):
    st.header("🎯 活动礼包")
    
    # --- 1. 数据预加载逻辑 ---
    if data_bundle:
        full_products_df = data_bundle.get("products")
        full_members_df = data_bundle.get("members")
        all_acts = data_bundle.get("activities") if data_bundle.get("activities") is not None else read_data("activities")
    else:
        full_products_df = read_data("products")
        full_members_df = read_data("members")
        all_acts = read_data("activities")

    t1, t2, t3 = st.tabs(["设置活动礼包", "批量办理活动", "活动列表管理"])

    # --- t1: 设置活动礼包 ---
    with t1:
        st.subheader("🎁 新增活动礼包")
        col_n, col_p = st.columns([2, 1])
        n = col_n.text_input("活动名称", placeholder="如：焕颜补水套装", key="new_act_name")
        p = col_p.number_input("礼包总价格", min_value=0.0, key="new_act_price")

        cat_col, search_col = st.columns([1, 2])
        with cat_col:
            gift_cat = st.selectbox("内容类型", ["全部", "实物产品", "服务项目"], key="gift_cat_filter")

        with search_col:
            if gift_cat == "全部":
                prods_df = full_products_df
            else:
                prods_df = full_products_df[full_products_df['type'] == gift_cat]

            # 这里的 unit_map 改为从全表提取，保证准确性
            prod_list = [f"[{row['type']}] {row['prod_name']}" for _, row in prods_df.iterrows()]
            unit_map = {f"[{row['type']}] {row['prod_name']}": row['unit'] for _, row in full_products_df.iterrows()}
            sel = st.multiselect("选择内含产品/服务", prod_list)

        extra = st.text_input("➕ 自定义福利 (如：赠送头部按摩)", placeholder="不填则不加")

        counts = {}
        if sel or extra:
            st.write("--- 设定数量 ---")
            all_to_show = sel + ([extra] if extra else [])
            cols = st.columns(4)
            for idx, it in enumerate(all_to_show):
                u = unit_map.get(it, "次")
                counts[it] = cols[idx % 4].number_input(f"{it}({u})", 1, 100, 1, key=f"inp_{it}")

        note = st.text_area("📝 活动备注", placeholder="在此填写活动规则等...")

        if st.button("🚀 立即发布活动", type="primary", use_container_width=True):
            if n and counts:
                # 注意：发布活动时需要拉取最新的活动表防止覆盖
                df_acts_latest = read_data("activities")
                new_act = pd.DataFrame([{
                    "id": int(time.time()),
                    "name": n,
                    "packages": json.dumps(counts, ensure_ascii=False),
                    "price": p,
                    "is_open": 1,
                    "note": note
                }])
                df_acts_latest = pd.concat([df_acts_latest, new_act], ignore_index=True)
                save_data("activities", df_acts_latest)
                st.success(f"活动【{n}】已发布")
                time.sleep(1)
                st.rerun()

    # --- t2: 批量办理活动 ---
    with t2:
        st.info("批量办理将自动扣除库存、增加会员资产并生成财务流水（现结模式）。")
        active_acts = all_acts[all_acts['is_open'] == 1]
        
        if active_acts.empty:
            st.warning("当前没有开启中的活动")
        else:
            sel_act_name = st.selectbox("选择活动", active_acts['name'].tolist())
            ad = active_acts[active_acts['name'] == sel_act_name].iloc[0]
            pkg = json.loads(ad['packages'])
            
            # 格式化会员选择器，显示姓名和手机后四位
            targs = st.multiselect(
                "选择办理会员", 
                options=full_members_df['phone'].tolist(),
                format_func=lambda x: f"{full_members_df[full_members_df['phone'] == x]['name'].values[0]} ({str(x)[-4:]})"
            )
            
            staff_list = read_data("staffs")['name'].tolist() if not read_data("staffs").empty else ["店长"]
            staff = st.selectbox("经办人", staff_list, key="act_staff")

            if st.button("🚀 批量确认办理", type="primary", use_container_width=True):
                if not targs:
                    st.error("❌ 请至少选择一个会员")
                else:
                    with st.spinner("正在同步云端数据，请勿关闭页面..."):
                        # 1. 统一读取涉及的所有表（办理瞬间拉取最新库存）
                        df_p = read_data("products")
                        df_si = read_data("salon_items")
                        df_r = read_data("records")
                        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        # 2. 在内存中完成所有计算
                        for p_phone in targs:
                            for it_full_name, it_qty in pkg.items():
                                # 提取纯产品名（去除 [实物产品] 这种前缀）
                                pure_name = it_full_name.split("] ")[-1] if "] " in it_full_name else it_full_name
                                
                                # 扣库存逻辑
                                if pure_name in df_p['prod_name'].values:
                                    df_p.loc[df_p['prod_name'] == pure_name, 'stock'] -= it_qty
                                    df_p.loc[df_p['prod_name'] == pure_name, 'last_updated'] = now
                                    u_val = df_p[df_p['prod_name'] == pure_name]['unit'].values[0]
                                else:
                                    u_val = "次"
                                
                                # 增加会员资产
                                new_si = pd.DataFrame([{
                                    "member_phone": p_phone, "item_name": pure_name, "total_qty": it_qty,
                                    "used_qty": 0, "status": "使用中", "unit": u_val, "buy_date": now
                                }])
                                df_si = pd.concat([df_si, new_si], ignore_index=True)
                            
                            # 记录流水
                            new_rec = pd.DataFrame([{
                                "member_phone": p_phone, "date": now, "items": f"活动:{sel_act_name}",
                                "total_amount": ad['price'], "status": "现结", "staff_name": staff
                            }])
                            df_r = pd.concat([df_r, new_rec], ignore_index=True)

                        # 3. 一次性写回云端（减少 API 请求次数）
                        save_data("products", df_p)
                        save_data("salon_items", df_si)
                        save_data("records", df_r)

                    st.balloons()
                    st.success(f"✅ 已成功为 {len(targs)} 位会员办理活动！")
                    time.sleep(1.5)
                    st.rerun()

    # --- t3: 活动管理与统计 ---
    with t3:
        if all_acts.empty:
            st.info("暂无活动记录。")
        else:
            # 这里的 df_acts 用于展示和操作
            df_acts_display = all_acts.copy()
            for idx, row in df_acts_display.iterrows():
                status_icon = "🟢" if int(row['is_open']) == 1 else "⚪"
                with st.expander(f"{status_icon} {row['name']} | 价格: ¥{row['price']}"):
                    st.write(f"📦 内容: {row['packages']}")
                    st.write(f"📝 备注: {row['note']}")
                    
                    c1, c2, _ = st.columns([1, 1, 2])
                    if c1.button("切换状态", key=f"sw_{row['id']}"):
                        df_acts_display.at[idx, 'is_open'] = 0 if int(row['is_open']) == 1 else 1
                        save_data("activities", df_acts_display)
                        st.rerun()
                    if c2.button("🗑️ 删除", key=f"del_{row['id']}"):
                        df_acts_display = df_acts_display.drop(idx)
                        save_data("activities", df_acts_display)
                        st.rerun()

            st.divider()
            st.subheader("📈 活动参与详情")
            df_records = data_bundle.get("records") if data_bundle else read_data("records")
            act_records = df_records[df_records['items'].str.contains("活动:", na=False)].copy()
            
            if not act_records.empty:
                act_records['活动名称'] = act_records['items'].str.replace("活动:", "", regex=False)
                # 确保金额是数值
                act_records['total_amount'] = pd.to_numeric(act_records['total_amount'], errors='coerce')
                
                stats_df = act_records.groupby('活动名称').agg(
                    参与人次=('member_phone', 'count'),
                    总收入额=('total_amount', 'sum')
                ).reset_index().sort_values('参与人次', ascending=False)
                
                st.table(stats_df)
            else:
                st.caption("暂无活动参与数据。")
