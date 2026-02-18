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

                # --- 【追加】コース別平均速度ヒートマップ ---
                st.subheader("🎯 コース別平均打球速度 (km/h)")
                
                # 1-9のコースを3x3の行列に変換
                # 1(左上), 2(中上), 3(右上) -> index [0,0], [0,1], [0,2]
                course_stats = p_df.groupby('Course')['Speed'].mean().reindex(range(1, 10)).values.reshape(3, 3)
                
                # コースごとの打数（サンプル数）も取得（ツールチップ用）
                course_counts = p_df.groupby('Course')['Speed'].count().reindex(range(1, 10)).values.reshape(3, 3)

                fig_heat = px.imshow(
                    course_stats,
                    labels=dict(x="外郭", y="高さ", color="平均速度"),
                    x=['左', '真ん中', '右'],
                    y=['高め', '真ん中', '低め'],
                    color_continuous_scale='Reds',
                    text_auto='.1f', # 数値を表示
                    aspect="equal"
                )
                
                fig_heat.update_traces(
                    hovertemplate="コース: %{x}%{y}<br>平均速度: %{z:.1f} km/h<br>打数: %{customdata} 回",
                    customdata=course_counts
                )
                
                fig_heat.update_layout(
                    coloraxis_colorbar=dict(title="速度"),
                    width=400,
                    height=400,
                )
                
                st.plotly_chart(fig_heat, use_container_width=True)
                # ------------------------------------------

                # グラフ（常に全期間の推移を表示して成長を見せる）
                st.subheader("📈 打球速度の推移（通算）")
                trend = full_p_df.groupby('Date')['Speed'].agg(['mean', 'max']).reset_index()
                fig = px.line(trend, x='Date', y=['mean', 'max'], markers=True)
                fig.update_layout(yaxis_range=[120, 170]) # 範囲を少し調整
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("📋 スイング履歴（選択期間）")
                # コース(Course)も履歴に表示するように追加
                hist = p_df[['Date', 'Speed', 'Angle', 'Dist', 'Course']].sort_values(['Date', 'Speed'], ascending=[False, False])
                st.write(hist.to_html(classes='feedback-table', index=False, float_format='%.1f'), unsafe_allow_html=True)
