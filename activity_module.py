import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
# 引入新定义的云端管理函数
from db_manager import read_data, save_data

def show_activity_center():
    st.header("🎯 活动礼包")
    
    # 获取初始连接和数据
    t1, t2, t3 = st.tabs(["设置活动礼包", "批量办理活动", "活动列表管理"])

    # --- t1: 设置活动礼包 ---
    with t1:
        st.subheader("🎁 新增活动礼包")
        col_n, col_p = st.columns([2, 1])
        n = col_n.text_input("活动名称", placeholder="如：焕颜补水套装")
        p = col_p.number_input("礼包总价格", min_value=0.0)

        # 分类选择布局
        cat_col, search_col = st.columns([1, 2])
        full_products_df = read_data("products") # 从云端读取产品全表
        
        with cat_col:
            gift_cat = st.selectbox("内容类型", ["全部", "实物产品", "服务项目"], key="gift_cat_filter")

        with search_col:
            # 使用 Pandas 过滤代替 SQL WHERE
            if gift_cat == "全部":
                prods_df = full_products_df
            else:
                prods_df = full_products_df[full_products_df['type'] == gift_cat]

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
                counts[it] = cols[idx % 4].number_input(f"{it}({u})", 1, 100, 1, key=f"act_{it}")

        note = st.text_area("📝 活动备注", placeholder="在此填写活动规则等...")

        if st.button("🚀 立即发布活动", type="primary", use_container_width=True):
            if n and counts:
                df_acts = read_data("activities")
                new_act = pd.DataFrame([{
                    "id": int(time.time()), # 简易唯一ID
                    "name": n,
                    "packages": json.dumps(counts, ensure_ascii=False),
                    "price": p,
                    "is_open": 1,
                    "note": note
                }])
                df_acts = pd.concat([df_acts, new_act], ignore_index=True)
                save_data("activities", df_acts) # 同步云端
                
                st.toast(f"✅ 活动【{n}】已成功发布！", icon="🎁")
                time.sleep(1.5)
                st.rerun()

    # --- t2: 批量办理活动 ---
    with t2:
        st.info("注意：批量办理仅支持现金/转账扣款（现结），将自动生成财务流水")
        all_acts = read_data("activities")
        acts = all_acts[all_acts['is_open'] == 1]
        
        if not acts.empty:
            sel_act = st.selectbox("选择活动", acts['name'].tolist())
            ad = acts[acts['name'] == sel_act].iloc[0]
            pkg = json.loads(ad['packages'])
            
            ms = read_data("members")
            targs = st.multiselect(
                "选择办理会员", 
                options=ms['phone'].tolist(),
                format_func=lambda x: f"{ms[ms['phone'] == x]['name'].values[0]} ({str(x)[-4:]})"
            )
            
            staff_df = read_data("staffs")
            staff_list = staff_df['name'].tolist() if not staff_df.empty else ["店长"]
            staff = st.selectbox("经办人", staff_list)

            if st.button("🚀 批量确认办理", type="primary"):
                if not targs:
                    st.warning("请至少选择一个会员")
                else:
                    # 一次性读取涉及的所有表
                    df_p = read_data("products")
                    df_si = read_data("salon_items")
                    df_r = read_data("records")
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    for p_phone in targs:
                        for it_name, it_qty in pkg.items():
                            # 1. 扣库存
                            df_p.loc[df_p['prod_name'] == it_name, 'stock'] -= it_qty
                            df_p.loc[df_p['prod_name'] == it_name, 'last_updated'] = now
                            
                            # 2. 获取单位并增加资产
                            u_val = df_p[df_p['prod_name'] == it_name]['unit'].values[0] if it_name in df_p['prod_name'].values else "次"
                            new_si = pd.DataFrame([{
                                "member_phone": p_phone, "item_name": it_name, "total_qty": it_qty,
                                "used_qty": 0, "status": "使用中", "unit": u_val, "buy_date": now
                            }])
                            df_si = pd.concat([df_si, new_si], ignore_index=True)
                        
                        # 3. 记录流水
                        new_rec = pd.DataFrame([{
                            "member_phone": p_phone, "date": now, "items": f"活动:{sel_act}",
                            "total_amount": ad['price'], "status": "现结", "staff_name": staff
                        }])
                        df_r = pd.concat([df_r, new_rec], ignore_index=True)

                    # 统一写回云端
                    save_data("products", df_p)
                    save_data("salon_items", df_si)
                    save_data("records", df_r)

                    st.toast(f"✅ 办理完成！", icon="🎊")
                    time.sleep(1.5)
                    st.rerun()

    # --- t3: 活动管理与统计 ---
    with t3:
        df_acts = read_data("activities")
        if df_acts.empty:
            st.info("暂无活动记录。")
        else:
            for idx, row in df_acts.iterrows():
                status_icon = "🟢" if row['is_open'] == 1 else "⚪"
                with st.expander(f"{status_icon} {row['name']} | 价格: ¥{row['price']}"):
                    st.write(f"📝 备注: {row['note']}")
                    # 启用/停用逻辑
                    if st.button("切换状态", key=f"sw_{row['id']}"):
                        df_acts.at[idx, 'is_open'] = 0 if row['is_open'] == 1 else 1
                        save_data("activities", df_acts)
                        st.rerun()
                    if st.button("🗑️ 删除", key=f"del_{row['id']}"):
                        df_acts = df_acts.drop(idx)
                        save_data("activities", df_acts)
                        st.rerun()

            # 统计部分：使用 Pandas 聚合替代复杂的 SQL JOIN
            st.divider()
            st.subheader("📈 活动参与详情")
            df_records = read_data("records")
            # 过滤出活动相关的记录
            act_records = df_records[df_records['items'].str.contains("活动:", na=False)].copy()
            
            if not act_records.empty:
                # 提取活动名称并统计
                act_records['活动名称'] = act_records['items'].str.replace("活动:", "")
                stats_df = act_records.groupby('活动名称').agg(
                    参与人数=('member_phone', 'nunique'),
                    总收入=('total_amount', 'sum')
                ).reset_index()
                st.dataframe(stats_df, use_container_width=True, hide_index=True)
            else:
                st.caption("暂无活动参与数据。")
