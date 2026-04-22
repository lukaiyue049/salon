import streamlit as st
import pandas as pd
from datetime import datetime
from db_manager import read_data, save_data

def show(data_bundle):
    st.header("📦 项目与产品管理")
    products_df = data_bundle["products"]
    
    col_op1, col_op2 = st.columns(2)
    if col_op1.button("➕ 登记/进货/调价", use_container_width=True, type="primary"):
        add_product_dialog()
    if col_op2.button("✂️ 损耗/店用", use_container_width=True):
        deduct_product_dialog()
    
    st.divider()
    t_product, t_service = st.tabs(["🛍️ 实物产品库存", "💆 服务项目清单"])
    with t_product:
        render_product_list(products_df, "实物产品")
    with t_service:
        render_product_list(products_df, "服务项目")

def render_product_list(df, prod_type):
    sub_df = df[df['type'] == prod_type].copy()
    if sub_df.empty:
        st.info(f"暂无{prod_type}")
        return
    # 表头
    if prod_type == "实物产品":
        cols = st.columns([2.5, 1, 1, 1.2, 0.5])
        titles = ["名称", "单价", "库存", "最后更新", "操作"]
    else:
        cols = st.columns([3, 1, 1, 0.5])
        titles = ["名称", "单价", "单位", "操作"]
    for c, t in zip(cols, titles):
        c.markdown(f"<p style='color:#8D6E63; font-weight:bold'>{t}</p>", unsafe_allow_html=True)
    st.divider()
    
    for idx, row in sub_df.iterrows():
        if prod_type == "实物产品":
            c1, c2, c3, c4, c5 = st.columns([2.5, 1, 1, 1.2, 0.5], vertical_alignment="center")
            c1.write(f"**{row['prod_name']}**")
            c2.write(f"¥{float(row['price']):.2f}")
            c3.write(f"{row['stock']} {row['unit']}")
            c4.caption(str(row['last_updated'])[:16])
            if c5.button("🗑️", key=f"del_{prod_type}_{idx}"):
                confirm_delete_product(row['prod_name'], prod_type)
        else:
            c1, c2, c3, c4 = st.columns([3, 1, 1, 0.5], vertical_alignment="center")
            c1.write(f"**{row['prod_name']}**")
            c2.write(f"¥{float(row['price']):.2f}")
            c3.write(row['unit'])
            if c4.button("🗑️", key=f"del_{prod_type}_{idx}"):
                confirm_delete_product(row['prod_name'], prod_type)

@st.dialog("项目管理 / 录入与进货")
def add_product_dialog():
    prods_df = read_data("products")
    if 'batch_list' not in st.session_state:
        st.session_state.batch_list = []
    
    menu = st.tabs(["单次录入", "批量清单"])
    with menu[0]:
        p_type = st.radio("业务类别", ["实物产品", "服务项目"], horizontal=True)
        mode = st.radio("录入类型", ["新登记", "现有补货"], horizontal=True)
        with st.container(border=True):
            if mode == "新登记":
                prod_name = st.text_input(f"{p_type}名称*").strip()
                if p_type == "服务项目":
                    price = st.number_input("定价", min_value=0.0, step=10.0)
                    unit, stock, spec = "次", 9999.0, 1
                else:
                    unit = st.selectbox("单位", ["盒", "瓶", "支", "个", "套"])
                    price = st.number_input("单价", min_value=0.0)
                    stock = st.number_input(f"初始库存({unit})", min_value=0.0)
                    spec = st.number_input("规格系数", min_value=1, value=10 if unit=="盒" else 5 if unit=="套" else 1)
            else:
                filtered = prods_df[prods_df['type'] == p_type]
                if filtered.empty:
                    st.warning("暂无记录，请先新登记")
                    return
                prod_name = st.selectbox(f"选择已有{p_type}", filtered['prod_name'].tolist())
                price = st.number_input("更新单价 (0为不改)", 0.0)
                stock = st.number_input("增加数量", min_value=0.0)
                unit, spec = "原单位", 1
            
            c1, c2 = st.columns(2)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if c1.button("🚀 立即录入", use_container_width=True, type="primary"):
                if not prod_name:
                    return
                if mode == "新登记":
                    new_row = pd.DataFrame([{
                        "prod_name": prod_name, "category": str(spec), "price": price, "stock": stock,
                        "unit": unit, "type": p_type, "last_updated": now_str
                    }])
                    save_data("products", pd.concat([prods_df, new_row], ignore_index=True))
                else:
                    idx = prods_df[prods_df['prod_name'] == prod_name].index[0]
                    prods_df.at[idx, 'stock'] += stock
                    if price > 0:
                        prods_df.at[idx, 'price'] = price
                    prods_df.at[idx, 'last_updated'] = now_str
                    save_data("products", prods_df)
                st.rerun()
            if c2.button("➕ 加入清单", use_container_width=True):
                st.session_state.batch_list.append({
                    "名称": prod_name, "类型": p_type, "单价": price, "数量": stock,
                    "单位": unit, "模式": mode, "规格": spec
                })
                st.toast("已加入清单")
    with menu[1]:
        if st.session_state.batch_list:
            st.dataframe(pd.DataFrame(st.session_state.batch_list), use_container_width=True, hide_index=True)
            if st.button("🚀 全部入库", type="primary", use_container_width=True):
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for item in st.session_state.batch_list:
                    if item['模式'] == "新登记":
                        new_row = pd.DataFrame([{
                            "prod_name": item['名称'], "category": str(item['规格']), "price": item['单价'],
                            "stock": item['数量'], "unit": item['单位'], "type": item['类型'], "last_updated": now_str
                        }])
                        prods_df = pd.concat([prods_df, new_row], ignore_index=True)
                    else:
                        idx = prods_df[prods_df['prod_name'] == item['名称']].index
                        if not idx.empty:
                            prods_df.at[idx[0], 'stock'] += item['数量']
                            if item['单价'] > 0:
                                prods_df.at[idx[0], 'price'] = item['单价']
                save_data("products", prods_df)
                st.session_state.batch_list = []
                st.rerun()
        else:
            st.info("清单为空")

@st.dialog("损耗登记")
def deduct_product_dialog():
    prods_df = read_data("products")
    records_df = read_data("records")
    items = prods_df[(prods_df['type'] == '实物产品') & (prods_df['stock'] > 0)]
    if items.empty:
        st.warning("无可损耗的实物产品")
        return
    sel_p = st.selectbox("产品", items['prod_name'].tolist())
    info = items[items['prod_name'] == sel_p].iloc[0]
    col1, col2 = st.columns(2)
    mode = col1.radio("单位", [f"按{info['unit']}", "按片/支"])
    num = col2.number_input("数量", min_value=0.1, value=1.0)
    reason = st.selectbox("原因", ["店用消耗", "过期处理", "破损/丢弃"])
    if st.button("🔥 确认扣除", type="primary", use_container_width=True):
        spec = int(info['category']) if str(info['category']).isdigit() else 1
        real_deduct = num / spec if "片/支" in mode else num
        prods_df.loc[prods_df['prod_name'] == sel_p, 'stock'] -= real_deduct
        new_rec = pd.DataFrame([{
            "member_phone": "SYSTEM", "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "items": f"【{reason}】{sel_p} {num}{mode.replace('按','')}",
            "total_amount": 0, "status": "非销售损耗", "staff_name": "后台"
        }])
        save_data("products", prods_df)
        save_data("records", pd.concat([records_df, new_rec], ignore_index=True))
        st.rerun()

@st.dialog("确认删除")
def confirm_delete_product(name, p_type):
    if st.button(f"确认删除 {name} 吗？"):
        prods_df = read_data("products")
        prods_df = prods_df[prods_df['prod_name'] != name]
        save_data("products", prods_df)
        st.rerun()
