import streamlit as st
import pandas as pd
import os
import plotly.express as px
import numpy as np
import glob

# --- ページ設定 (パスワードなしなので最初に配置) ---
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
def load_combined_data():
    all_rapsodo = []
    all_blast = []
    files = glob.glob("**/*.csv", recursive=True) + glob.glob("**/*.xlsx", recursive=True)
    
    for path in files:
        try:
            try:
                df = pd.read_csv(path, encoding='utf-8')
            except:
                df = pd.read_csv(path, encoding='cp932') if path.endswith('.csv') else pd.read_excel(path)
            
            df.columns = [c.strip() for c in df.columns]

            # --- BLASTデータの読み込み ---
            if 'バットスピード' in df.columns:
                df['Player'] = df['Name'].astype(str).str.strip()
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
                df['BatSpeed_kmh'] = pd.to_numeric(df['バットスピード'], errors='coerce') * 1.60934
                df['SwingTime'] = pd.to_numeric(df['スイング時間'], errors='coerce')
                df['AttackAngle'] = pd.to_numeric(df['アッパースイング度'], errors='coerce')
                df = df.dropna(subset=['Player', 'Date'])
                all_blast.append(df[['Player', 'Date', 'BatSpeed_kmh', 'SwingTime', 'AttackAngle']])
            
            # --- ラプソード（または打球計測）データの読み込み ---
            else:
                p_col = next((c for c in ['Hitter First Name', 'Hitter', 'Player', 'Batter'] if c in df.columns), None)
                if not p_col: continue
                
                df['Player'] = df[p_col].astype(str).str.strip()
                date_col = next((c for c in ['Hit Created At', 'Date', 'Pitch Created At', '日付'] if c in df.columns), None)
                if date_col:
                    df['Date'] = pd.to_datetime(df[date_col], errors='coerce').dt.date
                
                cols_map = {'ExitSpeed (KMH)': 'Speed', 'ExitSpeed': 'Speed', 'Angle': 'Angle', 'Distance (Meters)': 'Dist', 'Course': 'Course'}
                for orig, target in cols_map.items():
                    if orig in df.columns: df[target] = pd.to_numeric(df[orig], errors='coerce')
                
                df = df.dropna(subset=['Player', 'Speed', 'Date'])
                all_rapsodo.append(df)
        except:
            continue
            
    r_out = pd.concat(all_rapsodo, ignore_index=True) if all_rapsodo else pd.DataFrame()
    b_out = pd.concat(all_blast, ignore_index=True) if all_blast else pd.DataFrame()
    return r_out, b_out

# アプリのメイン処理
st.title("⚾️ 早稲田大学野球部 打撃分析システム")

r_df, b_df = load_combined_data()

if not r_df.empty:
    mode = st.sidebar.radio("メニュー", ["チーム全体分析", "個人詳細分析"], key="main_mode_switch")

    # =========================================================
    # チーム全体分析（ランキング表）
    # =========================================================
    if mode == "チーム全体分析":
        st.header("📊 チーム打撃分析ランキング")
        all_dates = sorted(r_df['Date'].unique(), reverse=True)
        selected_dates = st.multiselect("日付を選択", all_dates, default=[all_dates[0]] if all_dates else [], key="team_date_multiselect")
        
        if selected_dates:
            curr_df = r_df[r_df['Date'].isin(selected_dates)]
            summary = curr_df.groupby('Player').agg({'Speed': ['mean', 'max'], 'Dist': 'max'}).reset_index()
            summary.columns = ['Player', '平均打球速度', 'MAX打球速度', '最大飛距離']
            
            if not b_df.empty:
                b_curr = b_df[b_df['Date'].isin(selected_dates)].groupby('Player').agg({
                    'BatSpeed_kmh': 'mean',
                    'SwingTime': 'mean'
                }).reset_index()
                b_curr.columns = ['Player', '平均バット速度', '平均スイング時間']
                display_df = pd.merge(summary, b_curr, on='Player', how='left')
            else:
                display_df = summary

            display_df = display_df.sort_values('MAX打球速度', ascending=False).reset_index(drop=True)
            
            table_html = '<table class="feedback-table"><thead><tr>'
            for col in display_df.columns:
                table_html += f'<th>{col}</th>'
            table_html += '</tr></thead><tbody>'
            
            for _, row in display_df.iterrows():
                table_html += '<tr>'
                for col in display_df.columns:
                    val = row[col]
                    css_class = ''
                    if col == 'MAX打球速度':
                        if val >= 150: css_class = ' class="v-high"'
                        elif val >= 140: css_class = ' class="high"'
                    
                    if pd.isna(val):
                        d_val = "-"
                    elif col == '平均スイング時間':
                        d_val = f"{val:.3f}"
                    elif isinstance(val, (float, int)):
                        d_val = f"{val:.1f}"
                    else:
                        d_val = str(val)
                    table_html += f'<td{css_class}>{d_val}</td>'
                table_html += '</tr>'
            st.write(table_html + '</tbody></table>', unsafe_allow_html=True)

    # =========================================================
    # 個人詳細分析
    # =========================================================
    else:
        player = st.sidebar.selectbox("選手を選択", sorted(r_df['Player'].unique()), key="player_select_sidebar")
        st.header(f"👤 {player} 分析")
        
        p_df_full = r_df[r_df['Player'] == player].copy()
        b_df_full = b_df[b_df['Player'] == player].copy() if not b_df.empty else pd.DataFrame()
        
        player_dates = sorted(p_df_full['Date'].unique(), reverse=True)
        analysis_type = st.radio("分析範囲", ["総合（全期間）", "特定の日付を選択"], horizontal=True, key="p_range_radio")
        
        if analysis_type == "特定の日付を選択":
            sel_dates = st.multiselect("日付を選択", player_dates, default=[player_dates[0]] if player_dates else [], key="p_date_multi_select")
            p_df = p_df_full[p_df_full['Date'].isin(sel_dates)]
            b_df_sub = b_df_full[b_df_full['Date'].isin(sel_dates)] if not b_df_full.empty else pd.DataFrame()
        else:
            p_df = p_df_full
            b_df_sub = b_df_full

        if not p_df.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("選択期間MAX打球速度", f"{p_df['Speed'].max():.1f} km/h")
            c2.metric("選択期間平均打球速度", f"{p_df['Speed'].mean():.1f} km/h")
            c3.metric("バレル率", f"{( (p_df['Speed']>=140) & (p_df['Angle'].between(10,30)) ).mean()*100:.1f} %")

            if not b_df_sub.empty:
                st.markdown("---")
                st.markdown("#### ⚡️ BLASTスイング指標 (選択期間平均)")
                bc1, bc2, bc3 = st.columns(3)
                bs = b_df_sub['BatSpeed_kmh'].mean()
                bt = b_df_sub['SwingTime'].mean()
                ba = b_df_sub['AttackAngle'].mean()
                bc1.metric("平均バット速度", f"{bs:.1f} km/h" if pd.notnull(bs) else "-")
                bc2.metric("平均スイング時間", f"{bt:.3f} 秒" if pd.notnull(bt) else "-")
                bc3.metric("平均アタック角", f"{ba:.1f} °" if pd.notnull(ba) else "-")
            else:
                st.info("※この期間のBLASTデータはありません。")

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
            st.plotly_chart(fig_heat, use_container_width=True, key="p_heatmap_plotly")

            st.subheader("📋 スイング履歴（選択期間）")
            hist = p_df[['Date', 'Speed', 'Angle', 'Dist', 'Course']].sort_values(['Date', 'Speed'], ascending=[False, False])
            st.write(hist.to_html(classes='feedback-table', index=False, float_format='%.1f'), unsafe_allow_html=True)

else:
    st.info("CSV/Excelファイルを配置してください。")
