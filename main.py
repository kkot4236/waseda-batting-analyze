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
            background-color: #444 !important;
            color: white !important;
            padding: 12px;
            border: 1px solid #333;
            text-align: center !important;
        }
        .feedback-table td {
            padding: 10px;
            border: 1px solid #ccc;
            text-align: center !important;
            font-size: 16px;
        }
        .v-high { background-color: #ff4b4b !important; color: white !important; font-weight: bold; }
        .high { background-color: #ffcccc !important; color: #b30000 !important; font-weight: bold; }
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
            selected_dates = st.multiselect("日付を選択", all_dates, default=[all_dates[0]], key="team_date")
            
            if selected_dates:
                curr_df = df[df['Date'].isin(selected_dates)]
                summary = curr_df.groupby('Player').agg({'Speed': ['mean', 'max'], 'Dist': 'max'})
                summary.columns = ['平均速度', 'MAX速度', '最大飛距離']
                
                # 前回比
                prev_dates = [d for d in all_dates if d not in selected_dates and d < max(selected_dates)]
                if prev_dates:
                    last_prev = max(prev_dates)
                    p_avg = df[df['Date'] == last_prev].groupby('Player')['Speed'].mean()
                    summary['平均比'] = (summary['平均速度'] / p_avg * 100).fillna(0).map(lambda x: f"{x:.0f}%" if x > 0 else "-")
                
                display_df = summary.sort_values('MAX速度', ascending=False).reset_index()
                
                table_html = '<table class="feedback-table"><thead><tr>'
                for col in display_df.columns: table_html += f'<th>{col}</th>'
                table_html += '</tr></thead><tbody>'
                for _, row in display_df.iterrows():
                    table_html += '<tr>'
                    for col in display_df.columns:
                        val = row[col]
                        css_class = ' class="v-high"' if col == 'MAX速度' and val >= 150 else (' class="high"' if col == 'MAX速度' and val >= 140 else '')
                        d_val = f"{val:.1f}" if isinstance(val, (float, int)) else str(val)
                        table_html += f'<td{css_class}>{d_val}</td>'
                    table_html += '</tr>'
                st.write(table_html + '</tbody></table>', unsafe_allow_html=True)

        else:
            player = st.sidebar.selectbox("選手を選択", sorted(df['Player'].unique()))
            st.header(f"👤 {player} 分析")
            
            full_p_df = df[df['Player'] == player].copy()
            player_dates = sorted(full_p_df['Date'].unique(), reverse=True)
            
            # --- 個人分析用・日付選択肢 ---
            analysis_type = st.radio("分析範囲", ["総合（全期間）", "特定の日付を選択"], horizontal=True)
            
            if analysis_type == "特定の日付を選択":
                selected_p_dates = st.multiselect("日付を選択してください", player_dates, default=[player_dates[0]])
                p_df = full_p_df[full_p_df['Date'].isin(selected_p_dates)]
            else:
                p_df = full_p_df.copy()

            if not p_df.empty:
                # 指標の表示
                p_df['is_barrel'] = (p_df['Speed'] >= 140) & (p_df['Angle'].between(10, 30))
                c1, c2, c3 = st.columns(3)
                c1.metric("選択期間MAX", f"{p_df['Speed'].max():.1f} km/h")
                c2.metric("選択期間平均", f"{p_df['Speed'].mean():.1f} km/h")
                c3.metric("バレル率", f"{p_df['is_barrel'].mean()*100:.1f} %")

                # グラフ（常に全期間の推移を表示して成長を見せる）
                st.subheader("📈 打球速度の推移（通算）")
                trend = full_p_df.groupby('Date')['Speed'].agg(['mean', 'max']).reset_index()
                fig = px.line(trend, x='Date', y=['mean', 'max'], markers=True)
                fig.update_layout(yaxis_range=[125, 160])
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("📋 スイング履歴（選択期間）")
                hist = p_df[['Date', 'Speed', 'Angle', 'Dist']].sort_values(['Date', 'Speed'], ascending=[False, False])
                st.write(hist.to_html(classes='feedback-table', index=False, float_format='%.1f'), unsafe_allow_html=True)
            else:
                st.warning("表示するデータがありません。")

    else:
        st.info("データを入れてください。")
