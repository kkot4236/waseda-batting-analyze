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

    # --- デザインの定義 (以前のスタイルを完全維持) ---
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
    def load_combined_data():
        all_rapsodo = []
        all_blast = []
        files = glob.glob("**/*.csv", recursive=True) + glob.glob("**/*.xlsx", recursive=True)
        
        for path in files:
            try:
                # 文字コード試行
                try:
                    df = pd.read_csv(path, encoding='utf-8')
                except:
                    df = pd.read_csv(path, encoding='cp932') if path.endswith('.csv') else pd.read_excel(path)
                
                df.columns = [c.strip() for c in df.columns]

                # BLASTデータの判定 (列名の部分一致で判定を緩める)
                is_blast = any(c in df.columns for c in ['バットスピード', 'アッパースイング度', 'スイング時間'])
                
                if is_blast:
                    df['Player'] = df['Name'].astype(str)
                    df['Date'] = pd.to_datetime(df['Date']).dt.date
                    # MPHをKMHに変換 (MPH * 1.609)
                    if 'バットスピード' in df.columns:
                        df['BatSpeed_kmh'] = pd.to_numeric(df['バットスピード'], errors='coerce') * 1.60934
                    if 'スイング時間' in df.columns:
                        df['SwingTime'] = pd.to_numeric(df['スイング時間'], errors='coerce')
                    if 'アッパースイング度' in df.columns:
                        df['AttackAngle'] = pd.to_numeric(df['アッパースイング度'], errors='coerce')
                    all_blast.append(df)
                
                else:
                    # ラプソードデータの処理
                    p_col = next((c for c in ['Hitter First Name', 'Hitter', 'Player', 'Batter'] if c in df.columns), None)
                    if not p_col: continue
                    
                    df['Player'] = df[p_col].astype(str)
                    date_col = next((c for c in ['Hit Created At', 'Date', 'Pitch Created At'] if c in df.columns), None)
                    if date_col:
                        df['Date'] = pd.to_datetime(df[date_col], errors='coerce').dt.date
                    
                    cols_map = {'ExitSpeed (KMH)': 'Speed', 'ExitSpeed': 'Speed', 'Angle': 'Angle', 'Distance (Meters)': 'Dist', 'Course': 'Course'}
                    for orig, target in cols_map.items():
                        if orig in df.columns: df[target] = pd.to_numeric(df[orig], errors='coerce')
                    
                    df = df.dropna(subset=['Player', 'Speed', 'Date'])
                    all_rapsodo.append(df)
            except:
                continue
                
        return pd.concat(all_rapsodo, ignore_index=True) if all_rapsodo else pd.DataFrame(), \
               pd.concat(all_blast, ignore_index=True) if all_blast else pd.DataFrame()

    r_df, b_df = load_combined_data()

    if not r_df.empty:
        mode = st.sidebar.radio("メニュー", ["チーム全体分析", "個人詳細分析"], key="main_menu")

        if mode == "チーム全体分析":
            st.header("📊 チーム打球速度ランキング")
            all_dates = sorted(r_df['Date'].unique(), reverse=True)
            selected_dates = st.multiselect("日付を選択", all_dates, default=[all_dates[0]] if all_dates else [], key="team_date_multi")
            
            if selected_dates:
                curr_df = r_df[r_df['Date'].isin(selected_dates)]
                summary = curr_df.groupby('Player').agg({'Speed': ['mean', 'max'], 'Dist': 'max'}).reset_index()
                summary.columns = ['Player', '平均速度', 'MAX速度', '最大飛距離']
                display_df = summary.sort_values('MAX速度', ascending=False).reset_index(drop=True)
                
                # HTMLテーブル描画
                table_html = '<table class="feedback-table"><thead><tr>'
                for col in display_df.columns: table_html += f'<th>{col}</th>'
                table_html += '</tr></thead><tbody>'
                for _, row in display_df.iterrows():
                    table_html += '<tr>'
                    for col in display_df.columns:
                        val = row[col]
                        css_class = ''
                        if col == 'MAX速度':
                            if val >= 150: css_class = ' class="v-high"'
                            elif val >= 140: css_class = ' class="high"'
                        d_val = f"{val:.1f}" if isinstance(val, (float, int)) else str(val)
                        table_html += f'<td{css_class}>{d_val}</td>'
                    table_html += '</tr>'
                st.write(table_html + '</tbody></table>', unsafe_allow_html=True)

        else:
            player = st.sidebar.selectbox("選手を選択", sorted(r_df['Player'].unique()), key="player_select_box")
            st.header(f"👤 {player} 分析")
            
            p_df_full = r_df[r_df['Player'] == player].copy()
            b_df_full = b_df[b_df['Player'] == player].copy() if not b_df.empty else pd.DataFrame()
            
            player_dates = sorted(p_df_full['Date'].unique(), reverse=True)
            analysis_type = st.radio("分析範囲", ["総合（全期間）", "特定の日付を選択"], horizontal=True, key="p_analysis_range")
            
            if analysis_type == "特定の日付を選択":
                sel_dates = st.multiselect("日付を選択", player_dates, default=[player_dates[0]] if player_dates else [], key="p_date_multi")
                p_df = p_df_full[p_df_full['Date'].isin(sel_dates)]
                b_df_sub = b_df_full[b_df_full['Date'].isin(sel_dates)] if not b_df_full.empty else pd.DataFrame()
            else:
                p_df = p_df_full
                b_df_sub = b_df_full

            if not p_df.empty:
                # --- 指標表示 ---
                c1, c2, c3 = st.columns(3)
                c1.metric("選択期間MAX", f"{p_df['Speed'].max():.1f} km/h")
                c2.metric("選択期間平均", f"{p_df['Speed'].mean():.1f} km/h")
                c3.metric("バレル率", f"{( (p_df['Speed']>=140) & (p_df['Angle'].between(10,30)) ).mean()*100:.1f} %")

                # BLASTデータの表示
                if not b_df_sub.empty:
                    st.markdown("#### ⚡️ BLASTスイング指標 (平均)")
                    bc1, bc2, bc3 = st.columns(3)
                    if 'BatSpeed_kmh' in b_df_sub.columns:
                        bc1.metric("バット速度", f"{b_df_sub['BatSpeed_kmh'].mean():.1f} km/h")
                    if 'SwingTime' in b_df_sub.columns:
                        bc2.metric("スイング時間", f"{b_df_sub['SwingTime'].mean():.3f} 秒")
                    if 'AttackAngle' in b_df_sub.columns:
                        bc3.metric("アタック角", f"{b_df_sub['AttackAngle'].mean():.1f} °")

                # --- ヒートマップ ---
                st.subheader("🎯 コース別平均打球速度 (km/h)")
                all_zones = pd.Series(index=range(1, 10), dtype=float)
                all_zones.update(p_df.groupby('Course')['Speed'].mean())
                z_data = all_zones.values.reshape(3, 3)
                fig_heat = px.imshow(z_data, x=['左', '中', '右'], y=['高', '中', '低'],
                                     color_continuous_scale='Reds', text_auto='.1f', aspect="equal")
                for i in range(4):
                    fig_heat.add_shape(type="line", x0=i-0.5, y0=-0.5, x1=i-0.5, y1=2.5, line=dict(color="black", width=2))
                    fig_heat.add_shape(type="line", x0=-0.5, y0=i-0.5, x1=2.5, y1=i-0.5, line=dict(color="black", width=2))
                fig_heat.update_xaxes(side="top")
                st.plotly_chart(fig_heat, use_container_width=True, key="p_course_heat")

                # --- 履歴テーブル ---
                st.subheader("📋 スイング履歴（選択期間）")
                hist = p_df[['Date', 'Speed', 'Angle', 'Dist', 'Course']].sort_values(['Date', 'Speed'], ascending=[False, False])
                st.write(hist.to_html(classes='feedback-table', index=False, float_format='%.1f'), unsafe_allow_html=True)
            else:
                st.warning("表示できるデータがありません。")

    else:
        st.info("データを入れてください。")
