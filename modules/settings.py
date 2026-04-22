import streamlit as st
import pandas as pd
from db_manager import save_data

def show(data_bundle):
    st.header("⚙️ 系统管理")

    # 员工维护
    st.subheader("👥 员工维护")
    staff_df = data_bundle["staffs"].copy()
    with st.container(border=True):
        h1, h2, h3 = st.columns([1,1,1])
        h1.markdown("<center><b>员工姓名</b></center>", unsafe_allow_html=True)
        h2.markdown("<center><b>状态</b></center>", unsafe_allow_html=True)
        h3.markdown("<center><b>操作</b></center>", unsafe_allow_html=True)
        if not staff_df.empty:
            for idx, row in staff_df.iterrows():
                c1, c2, c3 = st.columns([1,1,1], vertical_alignment="center")
                c1.markdown(f"<center>{row['name']}</center>", unsafe_allow_html=True)
                c2.markdown("<center>✅ 在职</center>", unsafe_allow_html=True)
                if c3.button("🗑️ 删除", key=f"del_staff_{idx}", use_container_width=True):
                    new_df = staff_df.drop(idx)
                    save_data("staffs", new_df)
                    st.rerun()
    with st.expander("➕ 添加新员工"):
        new_name = st.text_input("员工姓名")
        if st.button("确认添加"):
            if new_name:
                new_row = pd.DataFrame([{"name": new_name}])
                save_data("staffs", pd.concat([staff_df, new_row], ignore_index=True))
                st.rerun()

    st.divider()

    # 阈值设置
    st.subheader("🚩 阈值设置")
    config_df = data_bundle["sys_config"]
    curr_limit = 500.0
    if not config_df.empty and 'debt_limit' in config_df['item'].values:
        curr_limit = float(config_df[config_df['item']=='debt_limit']['value'].values[0])
    new_limit = st.number_input("红名阈值 (欠款超过此数标红)", value=curr_limit)
    if st.button("💾 保存设置"):
        new_config = pd.DataFrame([{"item": "debt_limit", "value": str(new_limit)}])
        save_data("sys_config", new_config)
        st.success("设置已保存")

    st.divider()

    # 数据备份
    st.subheader("💾 数据备份")
    if st.button("生成备份数据包"):
        members_df = data_bundle["members"]
        st.download_button("点击下载备份 (CSV)", members_df.to_csv(index=False).encode('utf-8-sig'), "backup.csv", "text/csv")