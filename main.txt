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
        # パスワードを wbc1901 に変更
        if st.session_state["password_input"] == "wbc1901":
            st.session_state["password_correct"] = True
        else:
            st.session_state["password_correct"] = False
    st.title("⚾️ 早稲田大学野球部 打撃分析システム")
    st.text_input("パスワードを入力", type="password", on_change=password_entered, key="password_input")
    return False

if check_password():
    st.set_page_config(layout="wide", page_title="Waseda Hitting Analysis")

    @st.cache_data
    def load_data():
        all_data = []
        for root, dirs, files in os.walk("."):
            for file in files:
                if file.endswith(('.csv', '.xlsx')):
                    path = os.path.join(root, file)
                    try:
                        # CSV読み込み（Rapsodoの形式に対応）
                        df = pd.read_excel(path) if file.endswith('.xlsx') else pd.read_csv(path)
                        df.columns = df.columns.str.strip()
                        
                        # 項目名のマッピング
                        if 'Hitter First Name' in df.columns:
                            df['Player'] = df['Hitter First Name']
                        if 'Hit Created At' in df.columns:
                            df['Date'] = pd.to_datetime(df['Hit Created At']).dt.date
                        
                        # 数値変換（CSVの項目名 ExitSpeed (KMH) と Angle に対応）
                        cols = {'ExitSpeed (KMH)': 'Speed', 'Angle': 'Angle', 'Distance (Meters)': 'Dist'}
                        for original, target in cols.items():
                            if original in df.columns:
                                df[target] = pd.to_numeric(df[original], errors='coerce')
                        
                        # 打球速度が0のデータを除外
                        df = df[df['Speed'] > 0]
                        all_data.append(df)
                    except: continue
        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

    df = load_data()

    if not df.empty:
        menu = st.sidebar.radio("メニュー選択", ["チーム全体分析", "個人詳細分析"])

        if menu == "チーム全体分析":
            st.header("📊 チーム打球速度ランキング")
            all_dates = sorted(df['Date'].unique(), reverse=True)
            target_date = st.selectbox("分析対象日を選択", all_dates)
            
            curr_df = df[df['Date'] == target_date]
            prev_df = df[df['Date'] < target_date]
            
            summary = curr_df.groupby('Player').agg({
                'Speed': ['mean', 'max'],
                'Angle': 'mean',
                'Dist': 'max'
            })
            summary.columns = ['平均速度', 'MAX速度', '平均角度', '最大飛距離']
            
            # 前週比計算
            if not prev_df.empty:
                last_date = prev_df['Date'].max()
                p_avg = prev_df[prev_df['Date'] == last_date].groupby('Player')['Speed'].mean()
                summary['平均(前回比)'] = (summary['平均速度'] / p_avg * 100).map(lambda x: f"{x:.1f}%" if pd.notnull(x) else "-")

            st.dataframe(summary.sort_values('MAX速度', ascending=False).style.format(precision=1), use_container_width=True)

        else:
            st.header("👤 個人深掘り分析")
            player = st.sidebar.selectbox("選手を選択", sorted(df['Player'].unique()))
            p_df = df[df['Player'] == player].copy()

            # 1. 速度推移（表とグラフ）
            st.subheader("📈 打球速度の推移（日付別）")
            trend = p_df.groupby('Date')['Speed'].agg(['mean', 'max', 'count']).reset_index()
            trend.columns = ['日付', '平均速度', '最大速度', 'スイング数']
            
            fig_trend = px.line(trend, x='日付', y=['平均速度', '最大速度'], markers=True)
            st.plotly_chart(fig_trend, use_container_width=True)
            st.table(trend.sort_values('日付', ascending=False).set_index('日付'))

            # 2. バレルゾーン & 打球コース
            st.divider()
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🎯 バレルゾーン分析")
                # バレル定義 (速度140km/h以上 & 角度10-30度)
                p_df['is_barrel'] = (p_df['Speed'] >= 140) & (p_df['Angle'].between(10, 30))
                barrel_rate = p_df['is_barrel'].mean() * 100
                st.metric("バレル率 (Barrel %)", f"{barrel_rate:.1f} %")
                
                fig_scatter = px.scatter(p_df, x="Angle", y="Speed", color="is_barrel",
                                         color_discrete_map={True: "red", False: "gray"},
                                         range_x=[-10, 50], range_y=[70, 180], title="角度×速度 (赤:バレル)")
                fig_scatter.add_shape(type="rect", x0=10, y0=140, x1=30, y1=175, line=dict(color="Red"), opacity=0.1)
                st.plotly_chart(fig_scatter, use_container_width=True)

            with col2:
                st.subheader("⚾ 打球方向分布")
                if 'Direction' in p_df.columns:
                    # Direction: マイナスがレフト方向、プラスがライト方向
                    fig_dir = px.histogram(p_df, x="Direction", range_x=[-45, 45], nbins=20, title="方向分布 (-45:左 / 45:右)")
                    st.plotly_chart(fig_dir, use_container_width=True)
                else:
                    st.info("方向データがありません")

            st.subheader("📋 詳細データ（直近）")
            st.dataframe(p_df[['Date', 'Speed', 'Angle', 'Dist']].sort_values('Date', ascending=False).style.format(precision=1), hide_index=True)

    else:
        st.info("dataフォルダにCSVファイルを入れてください。")