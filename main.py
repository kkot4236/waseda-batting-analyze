import streamlit as st
import pandas as pd
import os
import plotly.express as px
import numpy as np
import glob

# --- ページ設定 ---
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
    # 直下およびサブディレクトリの全CSV/Excelを検索
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
st.title("早稲田大学野球部 打撃分析システム")

r_df, b_df = load_combined_data()

# いずれかのデータが存在する場合
if not r_df.empty or not b_df.empty:
    mode = st.sidebar.radio("メニュー", ["チーム全体分析", "個人詳細分析"], key="main_mode_switch")

    # =========================================================
    # チーム全体分析（ランキング表）
    # =========================================================
    if mode == "チーム全体分析":
        st.header("📊 チーム打撃分析ランキング")
        
        # 全データから日付を抽出（和集合）
        dates_r = set(r_df['Date'].unique()) if not r_df.empty else set()
        dates_b = set(b_df['Date'].unique()) if not b_df.empty else set()
        combined_dates = sorted(list(dates_r | dates_b), reverse=True)
        
        selected_dates = st.multiselect("日付を選択", combined_dates, default=[combined_dates[0]] if combined_dates else [], key="team_date_multiselect")
        
        if selected_dates:
            # 1. 打球データの集計
            if not r_df.empty:
                curr_r = r_df[r_df['Date'].isin(selected_dates)]
                summary_r = curr_r.groupby('Player').agg({'Speed': ['mean', 'max'], 'Dist': 'max'}).reset_index()
                summary_r.columns = ['Player', '平均打球速度', 'MAX打球速度', '最大飛距離']
            else:
                summary_r = pd.DataFrame(columns=['Player', '平均打球速度', 'MAX打球速度', '最大飛距離'])

            # 2. BLASTデータの集計
            if not b_df.empty:
                curr_b = b_df[b_df['Date'].isin(selected_dates)]
                summary_b = curr_b.groupby('Player').agg({
                    'BatSpeed_kmh': 'mean',
                    'SwingTime': 'mean'
                }).reset_index()
                summary_b.columns = ['Player', '平均バット速度', '平均スイング時間']
            else:
                summary_b = pd.DataFrame(columns=['Player', '平均バット速度', '平均スイング時間'])

            # 3. 外部結合 (how='outer') により、どちらか一方でもあれば表示
            display_df = pd.merge(summary_r, summary_b, on='Player', how='outer')

            # 打球速度があればそれでソート、なければバット速度でソート
            sort_col = 'MAX打球速度' if 'MAX打球速度' in display_df.columns and not display_df['MAX打球速度'].isnull().all() else '平均バット速度'
            display_df = display_df.sort_values(sort_col, ascending=False).reset_index(drop=True)
            
            # HTMLテーブル描画
            table_html = '<table class="feedback-table"><thead><tr>'
            for col in display_df.columns:
                table_html += f'<th>{col}</th>'
            table_html += '</tr></thead><tbody>'
            
            for _, row in display_df.iterrows():
                table_html += '<tr>'
                for col in display_df.columns:
                    val = row[col]
                    css_class = ''
                    if col == 'MAX打球速度' and pd.notnull(val):
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
        # 選手リストも両方のデータから統合
        players_r = set(r_df['Player'].unique()) if not r_df.empty else set()
        players_b = set(b_df['Player'].unique()) if not b_df.empty else set()
        all_players = sorted(list(players_r | players_b))
        
        player = st.sidebar.selectbox("選手を選択", all_players, key="player_select_sidebar")
        st.header(f"👤 {player} 分析")
        
        p_df_full = r_df[r_df['Player'] == player].copy() if not r_df.empty else pd.DataFrame()
        b_df_full = b_df[b_df['Player'] == player].copy() if not b_df.empty else pd.DataFrame()
        
        # 選手が持っている全日付を抽出
        p_dates_r = set(p_df_full['Date'].unique()) if not p_df_full.empty else set()
        p_dates_b = set(b_df_full['Date'].unique()) if not b_df_full.empty else set()
        player_dates = sorted(list(p_dates_r | p_dates_b), reverse=True)
        
        analysis_type = st.radio("分析範囲", ["総合（全期間）", "特定の日付を選択"], horizontal=True, key="p_range_radio")
        
        if analysis_type == "特定の日付を選択":
            sel_dates = st.multiselect("日付を選択", player_dates, default=[player_dates[0]] if player_dates else [], key="p_date_multi_select")
            p_df = p_df_full[p_df_full['Date'].isin(sel_dates)] if not p_df_full.empty else pd.DataFrame()
            b_df_sub = b_df_full[b_df_full['Date'].isin(sel_dates)] if not b_df_full.empty else pd.DataFrame()
        else:
            p_df = p_df_full
            b_df_sub = b_df_full

        # --- 打球指標の表示 ---
        if not p_df.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("選択期間MAX打球速度", f"{p_df['Speed'].max():.1f} km/h")
            c2.metric("選択期間平均打球速度", f"{p_df['Speed'].mean():.1f} km/h")
            c3.metric("バレル率", f"{( (p_df['Speed']>=140) & (p_df['Angle'].between(10,30)) ).mean()*100:.1f} %")
        else:
            st.info("※この期間の打球データはありません。")

        # --- BLAST指標の表示 ---
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

        # --- ヒートマップ (打球データがある場合のみ) ---
        if not p_df.empty and 'Course' in p_df.columns:
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
            cols_to_show = [c for c in ['Date', 'Speed', 'Angle', 'Dist', 'Course'] if c in p_df.columns]
            hist = p_df[cols_to_show].sort_values(['Date', 'Speed'], ascending=[False, False])
            st.write(hist.to_html(classes='feedback-table', index=False, float_format='%.1f'), unsafe_allow_html=True)

else:
    st.info("CSV/Excelファイルを配置してください。")
