import streamlit as st
import pandas as pd
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

    # --- デザインの定義 (CSS) ---
    st.markdown("""
        <style>
        .feedback-table {
            margin: auto;
            border-collapse: collapse;
            width: 100%;
            font-family: sans-serif;
            border: 1px solid #333;
        }
        .feedback-table th {
            background-color: #555 !important;
            color: white !important;
            padding: 10px;
            border: 1px solid #333;
            text-align: center !important;
        }
        .feedback-table td {
            padding: 8px;
            border: 1px solid #ccc;
            text-align: center !important;
        }
        /* 色分けクラス */
        .v-high { background-color: #ff4b4b !important; color: white !important; font-weight: bold; } /* 150以上: 濃い赤 */
        .high { background-color: #ffcccc !important; color: #b30000 !important; } /* 140以上: 薄い赤 */
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
                            if orig in df.columns:
                                df[target] = pd.to_numeric(df[orig], errors='coerce')
                        
                        df = df.dropna(subset=['Player', 'Speed'])
                        df = df[df['Speed'] > 0]
                        all_data.append(df)
                    except: continue
        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

    df = load_data()

    if not df.empty:
        mode = st.sidebar.radio("メニュー", ["チーム全体分析", "個人詳細分析"])

        if mode == "チーム全体分析":
            st.header("📊 チーム打球速度ランキング")
            all_dates = sorted(df['Date'].unique(), reverse=True)
            selected_dates = st.multiselect("日付を選択", all_dates, default=[all_dates[0]])
            
            if selected_dates:
                curr_df = df[df['Date'].isin(selected_dates)]
                summary = curr_df.groupby('Player').agg({'Speed': ['mean', 'max'], 'Angle': 'mean', 'Dist': 'max'})
                summary.columns = ['平均速度', 'MAX速度', '平均角度', '最大飛距離']
                
                # 前回比の計算 (エラー回避処理付き)
                prev_dates = [d for d in all_dates if d not in selected_dates and d < max(selected_dates)]
                if prev_dates:
                    last_prev = max(prev_dates)
                    p_avg = df[df['Date'] == last_prev].groupby('Player')['Speed'].mean()
                    summary['前回平均比'] = (summary['平均速度'] / p_avg * 100).fillna(0).map(lambda x: f"{x:.0f}%" if x > 0 else "-")
                
                display_df = summary.sort_values('MAX速度', ascending=False).reset_index()

                # --- HTMLテーブル構築 ---
                table_html = '<table class="feedback-table"><thead><tr>'
                for col in display_df.columns:
                    table_html += f'<th>{col}</th>'
                table_html += '</tr></thead><tbody>'

                for _, row in display_df.iterrows():
                    table_html += '<tr>'
                    for col in display_df.columns:
                        val = row[col]
                        css_class = ""
                        # 色分けの条件
                        if col == 'MAX速度':
                            if val >= 150: css_class = ' class="v-high"'
                            elif val >= 140: css_class = ' class="high"'
                        
                        # 表示形式の整理
                        d_val = f"{val:.1f}" if isinstance(val, (float, int)) else str(val)
                        table_html += f'<td{css_class}>{d_val}</td>'
                    table_html += '</tr>'
                table_html += '</tbody></table>'
                st.write(table_html, unsafe_allow_html=True)

        else:
            # 個人分析
            player = st.sidebar.selectbox("選手を選択", sorted(df['Player'].unique()))
            p_df = df[df['Player'] == player].copy()
            st.header(f"👤 {player} 分析")

            # バレル率の計算
            p_df['is_barrel'] = (p_df['Speed'] >= 140) & (p_df['Angle'].between(10, 30))
            barrel_pct = p_df['is_barrel'].mean() * 100
            
            c1, c2, c3 = st.columns(3)
            c1.metric("MAX速度", f"{p_df['Speed'].max():.1f} km/h")
            c2.metric("平均速度", f"{p_df['Speed'].mean():.1f} km/h")
            c3.metric("バレル率", f"{barrel_pct:.1f} %")

            # 速度推移グラフ
            trend = p_df.groupby('Date')['Speed'].agg(['mean', 'max']).reset_index()
            fig = px.line(trend, x='Date', y=['mean', 'max'], markers=True)
            st.plotly_chart(fig, use_container_width=True)

            # 詳細履歴表
            hist = p_df[['Date', 'Speed', 'Angle', 'Dist']].sort_values('Date', ascending=False)
            st.write(hist.to_html(classes='feedback-table', index=False, float_format='%.1f'), unsafe_allow_html=True)

    else:
        st.info("dataフォルダにCSVファイルを入れてください。")
