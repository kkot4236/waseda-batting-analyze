import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
import plotly.express as px

# --- パスワード設定 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = None
    if st.session_state["password_correct"] == True: return True
    def password_entered():
        if st.session_state["password_input"] == "wbc1901":
            st.session_state["password_correct"] = True
        else:
            st.session_state["password_correct"] = False
    st.title("⚾️ 早稲田大学野球部 打撃分析システム")
    st.text_input("パスワードを入力", type="password", on_change=password_entered, key="password_input")
    return False

if check_password():
    st.set_page_config(layout="wide", page_title="Waseda Hitting Analyze")

    # --- PDFのデザインを再現するカスタムCSS ---
    st.markdown("""
        <style>
        .feedback-table {
            margin-left: auto;
            margin-right: auto;
            border-collapse: collapse;
            width: 100%;
            font-family: sans-serif;
            font-size: 16px;
        }
        /* ヘッダーのデザイン：グレー背景に白文字 */
        .feedback-table th {
            background-color: #555555 !important;
            color: white !important;
            text-align: center !important;
            padding: 12px !important;
            border: 1px solid #ddd;
        }
        /* セルのデザイン：中央揃え */
        .feedback-table td {
            text-align: center !important;
            padding: 10px !important;
            border: 1px solid #ddd;
        }
        /* 1行おきに色を変える（縞模様） */
        .feedback-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        /* マウスを乗せた時にハイライト */
        .feedback-table tr:hover {
            background-color: #f1f1f1;
        }
        </style>
    """, unsafe_allow_html=True)

    @st.cache_data
    def load_data():
        all_data = []
        for root, dirs, files in os.walk("."):
            for file in files:
                if file.endswith(('.csv', '.xlsx')):
                    path = os.path.join(root, file)
                    try:
                        df = pd.read_excel(path) if file.endswith('.xlsx') else pd.read_csv(path)
                        df.columns = df.columns.str.strip()
                        if 'Hitter First Name' in df.columns: df['Player'] = df['Hitter First Name']
                        if 'Hit Created At' in df.columns: df['Date'] = pd.to_datetime(df['Hit Created At']).dt.date
                        cols = {'ExitSpeed (KMH)': 'Speed', 'Angle': 'Angle', 'Distance (Meters)': 'Dist'}
                        for orig, target in cols.items():
                            if orig in df.columns: df[target] = pd.to_numeric(df[orig], errors='coerce')
                        df = df[df['Speed'] > 0].dropna(subset=['Speed'])
                        all_data.append(df)
                    except: continue
        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

    df = load_data()

    if not df.empty:
        mode = st.sidebar.radio("メニュー", ["チーム全体分析", "個人詳細分析"])

        if mode == "チーム全体分析":
            st.header("📊 チーム打球速度ランキング")
            all_dates = sorted(df['Date'].unique(), reverse=True)
            selected_dates = st.multiselect("分析対象日を選択", all_dates, default=[all_dates[0]])
            
            if not selected_dates:
                st.warning("日付を選択してください")
            else:
                curr_df = df[df['Date'].isin(selected_dates)]
                summary = curr_df.groupby('Player').agg({'Speed': ['mean', 'max'], 'Angle': 'mean', 'Dist': 'max'})
                summary.columns = ['平均速度', 'MAX速度', '平均角度', '最大飛距離']
                
                # 前回の最新日と比較
                prev_dates = [d for d in all_dates if d not in selected_dates and d < max(selected_dates)]
                if prev_dates:
                    last_prev_date = max(prev_dates)
                    p_avg = df[df['Date'] == last_prev_date].groupby('Player')['Speed'].mean()
                    p_max = df[df['Date'] == last_prev_date].groupby('Player')['Speed'].max()
                    summary['平均比'] = (summary['平均速度'] / p_avg * 100).map(lambda x: f"{x:.0f}%" if pd.notnull(x) else "-")
                    summary['MAX比'] = (summary['MAX速度'] / p_max * 100).map(lambda x: f"{x:.0f}%" if pd.notnull(x) else "-")

                display_df = summary.sort_values('MAX速度', ascending=False).reset_index()
                
                # HTML変換（中央揃えクラスを適用）
                html_table = display_df.to_html(classes='feedback-table', index=False, justify='center', float_format='%.1f')
                st.write(html_table, unsafe_allow_html=True)

        else:
            # 個人分析
            st.header("👤 個人深掘り分析")
            player = st.sidebar.selectbox("選手を選択", sorted(df['Player'].unique()))
            p_df = df[df['Player'] == player].copy()

            st.subheader("📈 打球速度の推移")
            trend = p_df.groupby('Date')['Speed'].agg(['mean', 'max', 'count']).reset_index()
            trend.columns = ['日付', '平均速度', '最大速度', 'スイング数']
            fig_trend = px.line(trend, x='日付', y=['平均速度', '最大速度'], markers=True)
            st.plotly_chart(fig_trend, use_container_width=True)
            
            # 個人分析の表も同じデザインに
            st.write(trend.sort_values('日付', ascending=False).to_html(classes='feedback-table', index=False, justify='center', float_format='%.1f'), unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🎯 バレルゾーン分析")
                p_df['is_barrel'] = (p_df['Speed'] >= 140) & (p_df['Angle'].between(10, 30))
                st.metric("バレル率", f"{p_df['is_barrel'].mean()*100:.1f} %")
                fig_scatter = px.scatter(p_df, x="Angle", y="Speed", color="is_barrel", color_discrete_map={True: "red", False: "gray"}, range_x=[-10, 50], range_y=[70, 180])
                fig_scatter.add_shape(type="rect", x0=10, y0=140, x1=30, y1=175, line=dict(color="Red"), opacity=0.1)
                st.plotly_chart(fig_scatter, use_container_width=True)

            with col2:
                st.subheader("🚀 打球方向分布")
                if 'Direction' in p_df.columns:
                    fig_dir = px.histogram(p_df, x="Direction", range_x=[-45, 45], nbins=20)
                    st.plotly_chart(fig_dir, use_container_width=True)
            
            st.subheader("📋 詳細スイング履歴")
            history_df = p_df[['Date', 'Speed', 'Angle', 'Dist']].sort_values('Date', ascending=False)
            st.write(history_df.to_html(classes='feedback-table', index=False, justify='center', float_format='%.1f'), unsafe_allow_html=True)
    else:
        st.info("dataフォルダにCSVファイルを入れてください。")
