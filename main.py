import streamlit as st
import pandas as pd
import os
import glob
import matplotlib.pyplot as plt

# --- 1. ページ設定 ---
st.set_page_config(page_title="Waseda Pitcher Analytics", layout="wide")

# 球種の表示順序を定義
CATEGORY_ORDER = ["Fastball", "Slider", "Cutter", "Curveball", "Splitter", "ChangeUp", "OneSeam", "TwoSeamFastball"]

# --- 2. パスワード設定 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = None
    if st.session_state["password_correct"] == True: return True
    
    def password_entered():
        if st.session_state.get("password_input") == "wbc1901":
            st.session_state["password_correct"] = True
        else:
            st.session_state["password_correct"] = False
            
    st.title("⚾️ 早稲田大学野球部 投手分析システム")
    st.text_input("パスワードを入力してください", type="password", on_change=password_entered, key="password_input")
    return False

if check_password():
    # テーブルデザインCSS（左上の項目名を非表示にし、枠線を整理）
    st.markdown("""
        <style>
        .p-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; border: 1px solid #dee2e6; }
        .p-table th { background-color: #f8f9fa; padding: 12px; border: 1px solid #dee2e6; font-weight: bold; text-align: center; }
        .p-table td { padding: 12px; border: 1px solid #dee2e6; text-align: center; }
        /* 左上の角のセル（球種名が入る場所）のヘッダーテキストを消す */
        .p-table thead tr th:first-child { color: transparent; }
        </style>
    """, unsafe_allow_html=True)

    @st.cache_data
    def load_data(folder):
        files = glob.glob(os.path.join(folder, "*.csv"))
        if not files: return None
        df_list = []
        for f in files:
            try:
                tmp = pd.read_csv(f, dtype=str)
                tmp.columns = tmp.columns.str.strip() # 列名の空白を削除
                df_list.append(tmp)
            except: continue
        if not df_list: return None
        full_df = pd.concat(df_list, axis=0, ignore_index=True)
        
        # 投手名のクリーニング
        full_df['Pitcher'] = full_df['Pitcher'].fillna('Unknown').astype(str).str.strip()
        
        # 数値への変換と列名の正規化
        # ファイルによって列名が違う場合（HorzBreak か HorizontalBreak など）に対応
        col_map = {
            'RelSpeed': 'RelSpeed',
            'InducedVertBreak': 'InducedVertBreak',
            'HorzBreak': 'HorzBreak',
            'PlateLocSide': 'PlateLocSide',
            'PlateLocHeight': 'PlateLocHeight'
        }
        
        for old_col, target_col in col_map.items():
            if old_col in full_df.columns:
                full_df[target_col] = pd.to_numeric(full_df[old_col], errors='coerce')
        
        if 'Date' in full_df.columns:
            full_df['Date'] = pd.to_datetime(full_df['Date'], errors='coerce').dt.date
            
        return full_df

    df_all = load_data("data")

    if df_all is not None:
        st.write("### 🔍 絞り込み条件")
        c1, c2, c3 = st.columns(3)
        with c1:
            all_pitchers = [str(p) for p in df_all['Pitcher'].unique() if p not in ['nan', 'Unknown', 'None']]
            sel_p = st.selectbox("投手を選択", ["すべて"] + sorted(all_pitchers), key="global_p")
        with c2:
            all_dates = [d for d in df_all['Date'].unique() if d is not None and str(d) != 'NaT']
            sel_d = st.selectbox("日付を選択", ["すべて"] + sorted(all_dates, reverse=True), key="global_d")
        with c3:
            sel_r = st.radio("ランナー状況", ["すべて", "通常", "クイック"], horizontal=True, key="global_r")

        # フィルタ適用
        df = df_all.copy()
        if sel_p != "すべて": df = df[df['Pitcher'] == sel_p]
        if sel_d != "すべて": df = df[df['Date'] == sel_d]

        t1, t2 = st.tabs(["📊 総合分析", "🎯 変化量分析"])

        with t1:
            if not df.empty:
                # 指標計算
                df['is_strike'] = df['PitchCall'].fillna('').str.contains('Strike|Foul|InPlay', case=False).astype(int)
                df['is_swing'] = df['PitchCall'].fillna('').str.contains('StrikeSwinging|Foul|InPlay', case=False).astype(int)
                df['is_whiff'] = df['PitchCall'].fillna('').str.contains('StrikeSwinging', case=False).astype(int)
                
                # 上部メトリクス
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("投球数", f"{len(df)} 球")
                m2.metric("平均球速", f"{df['RelSpeed'].mean():.1f} km/h")
                m3.metric("ストライク率", f"{(df['is_strike'].mean()*100):.1f} %")
                swings = df['is_swing'].sum()
                whiff_rate = (df['is_whiff'].sum() / swings * 100) if swings > 0 else 0
                m4.metric("空振り/スイング率", f"{whiff_rate:.1f} %")

                st.subheader("📊 球種別データ")
                # 集計処理
                sum_df = df.groupby('TaggedPitchType').agg({
                    'RelSpeed': ['count', 'mean'],
                    'is_strike': 'mean',
                    'is_whiff': 'sum',
                    'is_swing': 'sum'
                })
                sum_df.columns = ['投球数', '平均球速', 'ストライク率', '空振り', 'スイング']
                sum_df['ストライク率'] = sum_df['ストライク率'] * 100
                sum_df['空振り/スイング'] = (sum_df['空振り'] / sum_df['スイング'] * 100).fillna(0)
                
                # 球種順の適用
                present_order = [c for c in CATEGORY_ORDER if c in sum_df.index]
                others = [c for c in sum_df.index if c not in CATEGORY_ORDER]
                sum_df = sum_df.reindex(present_order + others)

                col_l, col_r = st.columns([2, 1])
                with col_l:
                    # 表の整形（不要な列を削り、球種名をインデックスにする）
                    final_table = sum_df[['投球数', '平均球速', 'ストライク率', '空振り/スイング']].round(1)
                    st.write(final_table.to_html(classes='p-table'), unsafe_allow_html=True)
                with col_r:
                    # 円グラフの描画
                    if not sum_df.empty:
                        fig_p, ax_p = plt.subplots(figsize=(5,5))
                        ax_p.pie(sum_df['投球数'], labels=sum_df.index, autopct='%1.1f%%', startangle=90, counterclock=False)
                        st.pyplot(fig_p)
            else:
                st.info("データがありません")

        with t2:
            if not df.empty:
                st.subheader("🎯 変化量・位置分析")
                # 列の存在チェックをしてエラーを回避
                has_break = 'HorzBreak' in df.columns and 'InducedVertBreak' in df.columns
                has_loc = 'PlateLocSide' in df.columns and 'PlateLocHeight' in df.columns
                
                cl1, cl2 = st.columns(2)
                with cl1:
                    if has_break:
                        st.write("**変化量 (cm)**")
                        fig_b, ax_b = plt.subplots()
                        for pt in (present_order + others):
                            if pt in df['TaggedPitchType'].unique():
                                sub = df[df['TaggedPitchType'] == pt]
                                ax_b.scatter(sub['HorzBreak'], sub['InducedVertBreak'], label=pt, alpha=0.6)
                        ax_b.axhline(0, color='gray', lw=1); ax_b.axvline(0, color='gray', lw=1)
                        ax_b.set_xlim(-60, 60); ax_b.set_ylim(-60, 60)
                        ax_b.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='small')
                        st.pyplot(fig_b)
                with cl2:
                    if has_loc:
                        st.write("**投球位置**")
                        fig_l, ax_l = plt.subplots()
                        for pt in (present_order + others):
                            if pt in df['TaggedPitchType'].unique():
                                sub = df[df['TaggedPitchType'] == pt]
                                ax_l.scatter(sub['PlateLocSide'], sub['PlateLocHeight'], label=pt, alpha=0.6)
                        # ストライクゾーン（簡易版）
                        rect = plt.Rectangle((-0.8, 1.5), 1.6, 2.0, fill=False, color="blue", lw=2)
                        ax_l.add_patch(rect)
                        ax_l.set_xlim(-2, 2); ax_l.set_ylim(0, 5)
                        st.pyplot(fig_l)
