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

    # --- 中央揃えを強制するCSS ---
    st.markdown("""
        <style>
        .centered-table {
            margin-left: auto;
            margin-right: auto;
            text-align: center;
            width: 100%;
        }
        .centered-table th, .centered-table td {
            text-align: center !important;
            padding: 10px !important;
        }
        [data-testid="stMetricValue"] {
            text-align: center;
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
            
            # --- 日付の複数選択 ---
            all_dates = sorted(df['Date'].unique(), reverse=True)
            selected_dates = st.multiselect("分析対象日を選択（複数選ぶと合算されます）", all_dates, default=[all_dates[0]])
            
            if not selected_dates:
                st.warning("日付を選択してください")
            else:
                # 選択された全日付のデータを抽出
                curr_df = df[df['Date'].isin(selected_dates)]
                
                # 集計
                summary = curr_df.groupby('Player').agg({
                    'Speed': ['mean', 'max'],
                    'Angle': 'mean',
                    'Dist': 'max'
                })
                summary.columns = ['平均速度', 'MAX速度', '平均角度', '最大飛距離']
                
                # 最後に投げた日と比較（前週比用）
                prev_dates = [d for d in all_dates if d not in selected_dates and d < max(selected_dates)]
                if prev_dates:
                    last_prev_date = max(prev_dates)
                    p_avg = df[df['Date'] == last_prev_date].groupby('Player')['Speed'].mean()
                    summary['平均(前回比)'] = (summary['平均速度'] / p_avg * 100).map(lambda x: f"{x:.1f}%" if pd.notnull(x) else "-")

                # 表の表示用加工
                display_df = summary.sort_values('MAX速度', ascending=False).reset_index()
                
                # --- HTML/CSSで強制中央揃え ---
                # PandasのHTML変換を使い、クラスを付与
                html_table = display_df.to_html(classes='centered-table', index=False, justify='center', float_format='%.1f')
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
            
            # 個人分析の表もHTMLで中央揃え
            st.write(trend.sort_values('日付', ascending=False).to_html(classes='centered-table', index=False, justify='center', float_format='%.1f'), unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🎯 バレルゾーン分析")
                p_df['is_barrel'] = (p_df['Speed'] >= 140) & (p_df['Angle'].between(10, 30))
                barrel_rate = p_df['is_barrel'].mean() * 100
                st.metric("バレル率", f"{barrel_rate:.1f} %")
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
            st.write(history_df.to_html(classes='centered-table', index=False, justify='center', float_format='%.1f'), unsafe_allow_html=True)
    else:
        st.info("dataフォルダにCSVファイルを入れてください。")
