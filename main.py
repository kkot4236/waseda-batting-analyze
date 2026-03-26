import streamlit as st
import pandas as pd
import os
import plotly.express as px
import numpy as np
import glob

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
    if "page_config_set" not in st.session_state:
        st.set_page_config(layout="wide", page_title="Waseda Hitting Analyze")
        st.session_state["page_config_set"] = True

    st.markdown("""
        <style>
        .feedback-table { margin: auto; border-collapse: collapse; width: 100%; font-family: sans-serif; border: 1px solid #333; }
        .feedback-table th { background-color: #444 !important; color: white !important; padding: 12px; border: 1px solid #333; text-align: center !important; }
        .feedback-table td { padding: 10px; border: 1px solid #ccc; text-align: center !important; font-size: 16px; }
        .v-high { background-color: #ff4b4b !important; color: white !important; font-weight: bold; }
        .high { background-color: #ffcccc !important; color: #b30000 !important; font-weight: bold; }
        .blast-metric { background-color: #e8f4f8; padding: 10px; border-radius: 5px; border-left: 5px solid #2980b9; }
        </style>
    """, unsafe_allow_html=True)

    @st.cache_data
    def load_combined_data():
        all_rapsodo = []
        all_blast = []
        
        # ファイル探索
        files = glob.glob("**/*.csv", recursive=True) + glob.glob("**/*.xlsx", recursive=True)
        
        for path in files:
            try:
                # 文字コード対応
                try:
                    df = pd.read_csv(path, encoding='utf-8')
                except:
                    df = pd.read_csv(path, encoding='cp932') if path.endswith('.csv') else pd.read_excel(path)
                
                df.columns = [c.strip() for c in df.columns]

                # BLASTデータの判定
                if 'バットスピード' in df.columns or 'アッパースイング度' in df.columns:
                    # BLASTの処理
                    df['Player'] = df['Name'].astype(str)
                    df['Date'] = pd.to_datetime(df['Date']).dt.date
                    # MPHをKMHに変換
                    df['BatSpeed_kmh'] = pd.to_numeric(df['バットスピード'], errors='coerce') * 1.60934
                    df['SwingTime'] = pd.to_numeric(df['スイング時間'], errors='coerce')
                    df['AttackAngle'] = pd.to_numeric(df['アッパースイング度'], errors='coerce')
                    all_blast.append(df[['Player', 'Date', 'BatSpeed_kmh', 'SwingTime', 'AttackAngle']])
                
                else:
                    # ラプソード（打球データ）の処理
                    p_col = next((c for c in ['Hitter First Name', 'Hitter', 'Player', 'Batter'] if c in df.columns), None)
                    if not p_col: continue
                    
                    df['Player'] = df[p_col].astype(str)
                    date_col = next((c for c in ['Hit Created At', 'Date', 'Pitch Created At'] if c in df.columns), None)
                    if date_col:
                        df['Date'] = pd.to_datetime(df[date_col], errors='coerce').dt.date
                    
                    # 打球データの指標
                    cols_map = {'ExitSpeed (KMH)': 'Speed', 'ExitSpeed': 'Speed', 'Angle': 'Angle', 'Distance (Meters)': 'Dist', 'Course': 'Course'}
                    for orig, target in cols_map.items():
                        if orig in df.columns: df[target] = pd.to_numeric(df[orig], errors='coerce')
                    
                    df = df.dropna(subset=['Player', 'Speed', 'Date'])
                    df = df[df['Speed'] > 0]
                    all_rapsodo.append(df)
            except:
                continue
                
        rapsodo_df = pd.concat(all_rapsodo, ignore_index=True) if all_rapsodo else pd.DataFrame()
        blast_df = pd.concat(all_blast, ignore_index=True) if all_blast else pd.DataFrame()
        return rapsodo_df, blast_df

    r_df, b_df = load_combined_data()

    if not r_df.empty:
        mode = st.sidebar.radio("メニュー", ["チーム全体分析", "個人詳細分析"])

        if mode == "チーム全体分析":
            st.header("📊 チーム打球速度ランキング")
            all_dates = sorted(r_df['Date'].unique(), reverse=True)
            selected_dates = st.multiselect("日付を選択", all_dates, default=[all_dates[0]] if all_dates else [])
            
            if selected_dates:
                curr_df = r_df[r_df['Date'].isin(selected_dates)]
                summary = curr_df.groupby('Player').agg({'Speed': ['mean', 'max'], 'Dist': 'max'}).reset_index()
                summary.columns = ['Player', '平均速度', 'MAX速度', '最大飛距離']
                
                # BLASTデータもあれば平均値をマージ
                if not b_df.empty:
                    b_curr = b_df[b_df['Date'].isin(selected_dates)].groupby('Player')['BatSpeed_kmh'].mean().reset_index()
                    b_curr.columns = ['Player', '平均バット速度']
                    summary = pd.merge(summary, b_curr, on='Player', how='left')

                st.dataframe(summary.sort_values('MAX速度', ascending=False), use_container_width=True)

        else:
            player = st.sidebar.selectbox("選手を選択", sorted(r_df['Player'].unique()))
            st.header(f"👤 {player} 分析")
            
            p_df_full = r_df[r_df['Player'] == player].copy()
            b_df_full = b_df[b_df['Player'] == player].copy() if not b_df.empty else pd.DataFrame()
            
            player_dates = sorted(p_df_full['Date'].unique(), reverse=True)
            analysis_type = st.radio("分析範囲", ["総合（全期間）", "特定の日付を選択"], horizontal=True)
            
            if analysis_type == "特定の日付を選択":
                sel_dates = st.multiselect("日付を選択", player_dates, default=[player_dates[0]] if player_dates else [])
                p_df = p_df_full[p_df_full['Date'].isin(sel_dates)]
                b_df_sub = b_df_full[b_df_full['Date'].isin(sel_dates)] if not b_df_full.empty else pd.DataFrame()
            else:
                p_df = p_df_full
                b_df_sub = b_df_full

            # --- 指標表示 ---
            st.subheader("🚀 主要指標")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write("**【ラプソード】打球指標**")
                st.metric("MAX打球速度", f"{p_df['Speed'].max():.1f} km/h")
                st.metric("平均打球速度", f"{p_df['Speed'].mean():.1f} km/h")
            
            with col2:
                st.write("**【BLAST】スイング指標**")
                if not b_df_sub.empty:
                    st.metric("平均バット速度", f"{b_df_sub['BatSpeed_kmh'].mean():.1f} km/h")
                    st.metric("スイング時間", f"{b_df_sub['SwingTime'].mean():.2f} 秒")
                else:
                    st.info("BLASTデータなし")

            with col3:
                st.write("**【安定性】**")
                st.metric("バレル率", f"{( (p_df['Speed']>=140) & (p_df['Angle'].between(10,30)) ).mean()*100:.1f} %")
                if not b_df_sub.empty:
                    st.metric("アッパースイング度", f"{b_df_sub['AttackAngle'].mean():.1f} °")

            # --- グラフ表示 ---
            st.divider()
            c_left, c_right = st.columns(2)
            
            with c_left:
                st.subheader("🎯 コース別平均速度")
                # 前回のヒートマップ処理
                all_zones = pd.Series(index=range(1, 10), dtype=float)
                all_zones.update(p_df.groupby('Course')['Speed'].mean())
                z_data = all_zones.values.reshape(3, 3)
                fig_heat = px.imshow(z_data, x=['左', '中', '右'], y=['高', '中', '低'],
                                     color_continuous_scale='Reds', text_auto='.1f', aspect="equal")
                st.plotly_chart(fig_heat, use_container_width=True)

            with c_right:
                st.subheader("📈 速度相関")
                # 打球速度とバット速度の推移を並べる
                combined_trend = p_df.groupby('Date')['Speed'].max().reset_index()
                if not b_df_sub.empty:
                    b_trend = b_df_sub.groupby('Date')['BatSpeed_kmh'].mean().reset_index()
                    combined_trend = pd.merge(combined_trend, b_trend, on='Date', how='outer')
                
                fig_trend = px.line(combined_trend, x='Date', y=['Speed', 'BatSpeed_kmh'], markers=True,
                                    labels={'value': '速度 (km/h)', 'variable': '指標'})
                st.plotly_chart(fig_trend, use_container_width=True)

            st.subheader("📋 スイング履歴")
            st.dataframe(p_df[['Date', 'Speed', 'Angle', 'Dist', 'Course']].sort_values('Date', ascending=False), use_container_width=True)

    else:
        st.info("データファイルを配置してください。ラプソードとBLASTの両方を自動認識します。")
