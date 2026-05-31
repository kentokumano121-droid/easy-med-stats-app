%%writefile app.py
import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
import pingouin as pg
import plotly.express as px
import plotly.graph_objects as go
from lifelines import KaplanMeierFitter, CoxPHFitter
from lifelines.statistics import logrank_test
import matplotlib.pyplot as plt
import statsmodels.api as sm
from statsmodels.stats.contingency_tables import mcnemar
from sklearn.metrics import roc_curve, auc
import io

st.set_page_config(page_title="EasyMedStats", layout="wide")
st.title("EasyMedStats (論文執筆＆自動ナビゲート版)")
st.write("医療統計のための直感的なデータ解析Webアプリ。解析結果からワンクリックで論文用グラフを出力できます。")

# --- 📖 専門用語クイック辞書 ---
st.sidebar.header("📖 専門用語クイック辞書")
with st.sidebar.expander("よく使う統計用語を開く"):
    st.markdown("""
    **p値 (p-value):** 一般的に0.05（5%）未満なら「偶然ではない（有意差あり）」と判断します。

    ---
    **95%信頼区間 (95% CI):** 「同じ調査を100回やったら、95回は真の値がこの範囲に収まるだろう」という予測範囲。

    ---
    **パラメトリック / ノンパラメトリック:** データが綺麗な山型（正規分布）をしていることを前提とするのがパラメトリック。歪んでいても使えるのがノンパラメトリックです。

    ---
    **オッズ比 / ハザード比:** 1より大きいと結果（病気・死亡など）が起こりやすく、1未満なら起こりにくいことを示します。

    ---
    **AUC (ROC曲線下面積):** 検査の正確さの指標。1.0が完璧、0.5が当てずっぽう。0.7以上で有用とされます。
    """)

# --- グラフダウンロード用の補助関数 ---
def download_plotly_figure(fig, filename="plot.png"):
    buffer = io.StringIO()
    fig.write_html(buffer, include_plotlyjs='cdn')
    st.download_button("📥 グラフをダウンロード (HTML/動的)", buffer.getvalue().encode(), f"{filename}.html", "text/html", key=f"btn_{filename}")

def download_matplotlib_figure(fig, filename="plot.png"):
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", dpi=300)
    st.download_button("📥 グラフを画像(PNG)でダウンロード", buffer, filename, "image/png", key=f"btn_{filename}")

st.sidebar.header("1. データのアップロード")
has_header = st.sidebar.checkbox("データファイルの1行目は「変数名（列の名前）」ですか？", value=True)
header_arg = 0 if has_header else None

uploaded_file = st.sidebar.file_uploader("ExcelまたはCSVファイルをドロップ", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df_preview = pd.read_csv(uploaded_file, nrows=100, header=header_arg)
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, header=header_arg)
        else:
            df_preview = pd.read_excel(uploaded_file, nrows=100, header=header_arg)
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file, header=header_arg)

        if not has_header:
            df.columns = [f"Column_{i+1}" for i in range(len(df.columns))]
            df_preview.columns = df.columns

        st.sidebar.success("読み込み成功！")

        # ==========================================
        # 🔍 データの確認と属性の設定
        # ==========================================
        st.header("🔍 データの確認と属性の設定")
        st.warning("⚠️ 高速処理とプライバシー保護のため、画面上のプレビュー表示は最初の100行のみに制限しています（実際の解析には全行使用されます）。")

        with st.expander("📊 アップロードデータのプレビューとデータ型の調整", expanded=True):
            st.dataframe(df_preview)

            st.write("### ⚙️ 各列のデータ型（変数の性質）の確認・変更")
            col_types = {}
            cols = st.columns(min(len(df.columns), 5))

            num_continuous = 0
            num_categorical = 0

            for idx, col_name in enumerate(df.columns):
                if any(k in col_name.lower() for k in ["id", "patient", "番号", "no.", "code", "コード"]):
                    default_type_idx = 2
                elif pd.api.types.is_numeric_dtype(df[col_name]) and df[col_name].nunique() > 10:
                    default_type_idx = 0
                else:
                    default_type_idx = 1

                with cols[idx % 5]:
                    chosen_type = st.selectbox(f"列: {col_name}", ["連続値（数値）", "カテゴリ（群分け）", "解析対象外（IDなど）"], index=default_type_idx, key=f"type_select_{col_name}")
                    col_types[col_name] = chosen_type
                    if chosen_type == "連続値（数値）": num_continuous += 1
                    elif chosen_type == "カテゴリ（群分け）": num_categorical += 1

        # ==========================================
        # 🗺️ このデータでできる解析の全体マップ
        # ==========================================
        st.write("---")
        st.header("🗺️ このデータでできる解析の全体マップ")
        st.info(f"あなたのデータは **【連続値: {num_continuous}個】** **【カテゴリ: {num_categorical}個】** で構成されています。以下の解析が推奨されます。")
        map_cols = st.columns(5)

        if num_continuous >= 1 and num_categorical >= 1:
            with map_cols[0]: st.success("🎯 **グループ間の差**\n\n👉 **タブ2(A) へ**\n\n(t検定、ANOVAなど)")
        if num_categorical >= 2:
            with map_cols[1]: st.info("🎯 **割合の差の比較**\n\n👉 **タブ2(B) へ**\n\n(カイ二乗、マクネマー検定)")
        if num_continuous >= 2:
            with map_cols[2]: st.warning("🎯 **データの関係性**\n\n👉 **タブ2(C) へ**\n\n(相関分析、散布図)")
        if num_continuous >= 1 and num_categorical >= 1:
            with map_cols[3]: st.success("⏳ **生存時間解析**\n\n👉 **タブ3 へ**\n\n(生存曲線、Log-rank)")
        if (num_continuous >= 1 and num_categorical >= 2) or num_continuous >= 2:
            with map_cols[4]: st.error("🎯 **多変量解析・調整**\n\n👉 **タブ4 へ**\n\n(ANCOVA、ロジスティック等)")

        st.write("---")

        # 各タブへの移行
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 1. 記述統計", "🧪 2. 推測統計", "⏳ 3. 生存時間解析", "📈 4. 多変量解析・調整", "🎯 5. 診断能評価 (ROC)"])

        # ==========================================
        # タブ1：記述統計
        # ==========================================
        with tab1:
            st.header("データの分布と特徴を確認しましょう")
            valid_cols = [c for c in df.columns if col_types[c] != "解析対象外（IDなど）"]
            if len(valid_cols) > 0:
                view_col = st.selectbox("👀 確認したい変数", valid_cols, key="view1")

                if col_types[view_col] == "連続値（数値）":
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.subheader("🛠️ グラフの編集")
                        title_input = st.text_input("グラフのタイトル", value=f"{view_col} の分布", key="t_title_1")
                        fig = px.histogram(df, x=view_col, marginal="box", title=title_input, color_discrete_sequence=['#4C78A8'])
                        st.plotly_chart(fig, use_container_width=True)
                        download_plotly_figure(fig, f"histogram_{view_col}")
                    with col2:
                        mean_val = df[view_col].mean(); median_val = df[view_col].median(); std_val = df[view_col].std()
                        st.subheader("📝 データの要約解説")
                        st.info(f"**平均値**: {mean_val:.1f}\n\n**中央値**: {median_val:.1f}\n\n**標準偏差（SD）**: {std_val:.1f}")

                        diff = mean_val - median_val
                        if abs(diff) <= (std_val * 0.15):
                            st.success(f"📊 **分布の判定根拠:**\n平均値と中央値の差が非常に小さいため、このデータは左右対称な山型（正規分布に近い綺麗な分布）をしていると推測されます。パラメトリック検定が適している可能性が高いです。")
                        elif diff > 0:
                            st.warning(f"📊 **分布の判定根拠:**\n平均値が中央値よりも右側に大きく離れています。これは、一部に極端に高い数値を持つ患者がいるため、分布の裾が右側に長く伸びていることを意味します。ノンパラメトリック検定の検討が必要です。")
                        else:
                            st.warning(f"📊 **分布の判定根拠:**\n平均値が中央値よりも左側に大きく離れています。分布の裾が左側に長く伸びていることを意味します。ノンパラメトリック検定の検討が必要です。")

                        st.info(f"""
                        📐 **標準偏差（SD: {std_val:.1f}）が示す臨床的意味:**
                        データが綺麗な山型（正規分布）だと仮定した場合、患者全体の**約68%**が、平均値を中心に **{mean_val-std_val:.1f} 〜 {mean_val+std_val:.1f}** の狭い範囲内に収まります。
                        """)
                else:
                     col1, col2 = st.columns([2, 1])
                     with col1:
                         title_input = st.text_input("グラフのタイトル", value=f"{view_col} の内訳", key="t_title_2")
                         fig = px.histogram(df, x=view_col, title=title_input, color=view_col)
                         st.plotly_chart(fig, use_container_width=True)
                         download_plotly_figure(fig, f"barchart_{view_col}")
                     with col2:
                         st.subheader("📝 内訳データ")
                         st.dataframe(df[view_col].value_counts())

        # ==========================================
        # タブ2：推測統計（✨全解釈・プロセス明示の完全版✨）
        # ==========================================
        with tab2:
            st.header("推測統計ナビゲーション（推定・仮説検定）")
            outcome_type = st.radio("Q1. 調べたいことは何ですか？", ["A. グループ間の「差」を比較する", "B. 割合の「差」を比較する", "C. 2つの連続データの「関係性」を調べる"])

            # --- A. グループ間の差の比較 ---
            if outcome_type == "A. グループ間の「差」を比較する":
                col_g, col_t = st.columns(2)
                with col_g: group_col = st.selectbox("🗂️ 群分け・時間変数", [c for c in df.columns if col_types[c] == "カテゴリ（群分け）"], key="g1")
                with col_t: target_col = st.selectbox("🎯 解析したい変数（連続値）", [c for c in df.columns if col_types[c] == "連続値（数値）"], key="t1")

                if group_col and target_col:
                    if group_col == target_col:
                        st.warning("⚠️ 群分け変数と解析したい変数には、それぞれ異なるものを選んでください。")
                    else:
                        paired = st.radio("Q2. データの対応は？", ["対応なし", "対応あり"])
                        unique_groups = df[group_col].dropna().unique(); num_groups = len(unique_groups)

                        # シャピロウィルク検定の実行（エラー回避のためデータ数が3以上の場合のみ）
                        clean_data = df[target_col].dropna()
                        if len(clean_data) >= 3:
                            _, p_value_shapiro = stats.shapiro(clean_data)
                            normality = p_value_shapiro > 0.05
                        else:
                            normality = False # データが少なすぎる場合は安全のためノンパラ

                        if num_groups == 2:
                            if paired == "対応なし":
                                if normality: res = pg.ttest(df[df[group_col] == unique_groups[0]][target_col], df[df[group_col] == unique_groups[1]][target_col], correction=True); method_name = "ウェルチのt検定"
                                else: res = pg.mwu(df[df[group_col] == unique_groups[0]][target_col], df[df[group_col] == unique_groups[1]][target_col]); method_name = "マン・ホイットニーのU検定"

                                st.write(f"### 📊 {method_name} の結果")
                                st.dataframe(res)
                                p_col = 'p_val' if 'p_val' in res.columns else 'p-val'
                                if res[p_col].values[0] < 0.05: st.success(f"💡 結論：{unique_groups[0]}と{unique_groups[1]}の間には、統計学的に有意な差があります。")
                                else: st.warning("💡 結論：2群間に統計学的な有意差は認められませんでした。")

                                if not normality:
                                    st.info("""
                                    📖 **表の専門用語の読み方:**
                                    * **U-val (U値):** 検定計算用の数値です。論文の本文に記載する用です。
                                    * **RBC (順位二系列相関):** 差の大きさ（効果量）。絶対値が1に近いほど「2群の差がハッキリしている」ことを意味します。
                                    * **CLES (共通言語効果量):** 「A群から1人、B群から1人をランダムに選んだとき、A群の人の数値が高くなる確率」です。臨床的にとても直感的な指標です。
                                    """)

                                # 💡 ✨プロセス解説の完全復活✨
                                with st.expander("💡 この解析の裏側（思考と計算のプロセス）"):
                                    st.write(f"""
                                    1. **データ構造:** 「2つのグループ」「データの対応なし」と認識しました。
                                    2. **正規性チェック:** シャピロ・ウィルク検定の結果、データは「**{'正規分布（綺麗な山型）' if normality else '非正規分布（歪みあり）'}**」と判定されました。
                                    3. **手法の決定:** 上記の条件から、最適な手法として **{method_name}** が自動選択され、実行されました。
                                    """)

                                st.write("### 🛠️ グラフの編集")
                                g_title = st.text_input("グラフのタイトル", value=f"{target_col} のグループ間比較", key="gt_a1")
                                x_label = st.text_input("X軸の名称", value=group_col, key="gx_a1")
                                y_label = st.text_input("Y軸の名称", value=target_col, key="gy_a1")

                                fig = px.box(df, x=group_col, y=target_col, color=group_col, title=g_title, labels={group_col: x_label, target_col: y_label})
                                st.plotly_chart(fig, use_container_width=True)
                                download_plotly_figure(fig, f"box_2groups_{target_col}")

                            elif paired == "対応あり":
                                g1_data = df[df[group_col] == unique_groups[0]][target_col].values; g2_data = df[df[group_col] == unique_groups[1]][target_col].values
                                if len(g1_data) != len(g2_data): st.error("データ数が一致しません（対応する前後のデータが揃っていません）。")
                                else:
                                    if normality: res = pg.ttest(g1_data, g2_data, paired=True); method_name = "対応のあるt検定"
                                    else: res = pg.wilcoxon(g1_data, g2_data); method_name = "ウィルコクソンの符号付順位検定"

                                    st.write(f"### 📊 {method_name} の結果")
                                    st.dataframe(res)
                                    p_col = 'p_val' if 'p_val' in res.columns else 'p-val'
                                    if res[p_col].values[0] < 0.05: st.success("💡 結論：対応のある2群間に、統計学的に有意な差（変化）が認められました。")
                                    else: st.warning("💡 結論：有意な差（変化）は認められませんでした。")

                                    with st.expander("💡 この解析の裏側（思考と計算のプロセス）"):
                                        st.write(f"1. **データ構造:** 「2つのグループ」「データの対応あり（前後比較）」と認識しました。\n2. **正規性チェック:** データは「**{'正規分布' if normality else '非正規分布'}**」と判定されました。\n3. **手法の決定:** これにより **{method_name}** が自動選択されました。同じ被験者における2つの時点の『差分』に注目して検定しています。")

                        elif num_groups >= 3:
                            if paired == "対応なし":
                                if normality: res = pg.anova(data=df, dv=target_col, between=group_col); posthoc = pg.pairwise_tukey(data=df, dv=target_col, between=group_col); method_name = "一元配置分散分析 (ANOVA)"
                                else: res = pg.kruskal(data=df, dv=target_col, between=group_col); posthoc = pg.pairwise_tests(data=df, dv=target_col, between=group_col, parametric=False); method_name = "クラスカル・ウォリス検定"

                                st.write(f"### 📊 {method_name} の結果（全体）")
                                st.dataframe(res)
                                p_col = 'p_unc' if 'p_unc' in res.columns else 'p-unc'
                                if res[p_col].values[0] < 0.05: st.success("💡 結論：少なくとも1つの群の間に、有意な差があります。")
                                else: st.warning("💡 結論：群の間に有意差は認められませんでした。")

                                st.write("#### 🔍 多重比較の結果 (どの群間に差があるか)")
                                st.info("""
                                📖 **多重比較表の読み方:**
                                * **A / B:** 比較している2つのグループです。
                                * **p-corr:** 多重比較用に厳しく補正されたP値です。（💡ここが0.05未満なら「この2群間に有意差あり」と判定します）
                                """)
                                st.dataframe(posthoc)

                                # 💡 ✨新機能：多重比較の詳細な結論を自動生成✨
                                p_corr_col = 'p-corr' if 'p-corr' in posthoc.columns else 'p-unc' # ノンパラ等でp-corrがない場合のフォールバック
                                sig_pairs = posthoc[posthoc[p_corr_col] < 0.05]
                                if not sig_pairs.empty:
                                    pairs_str = "、".join([f"「{row['A']} vs {row['B']}」" for idx, row in sig_pairs.iterrows()])
                                    st.success(f"💡 詳細比較の結論：**{pairs_str}** の間に統計学的に有意な差が確認されました！")
                                else:
                                    st.warning("💡 詳細比較の結論：特定の2群間に、明らかな有意差は確認できませんでした。")

                                with st.expander("💡 この解析の裏側（思考と計算のプロセス）"):
                                    st.write(f"1. **データ構造:** 「3群以上」「対応なし」と認識しました。\n2. **正規性チェック:** データは「**{'正規分布' if normality else '非正規分布'}**」と判定されました。\n3. **手法の決定:** まず全体の偏りを **{method_name}** で検定し、その後すべての組み合わせの総当たり戦（多重比較）を自動で行いました。")

                                st.write("### 🛠️ グラフの編集")
                                g_title = st.text_input("グラフのタイトル", value=f"{target_col} の多群比較", key="gt_a2")
                                x_label = st.text_input("X軸の名称", value=group_col, key="gx_a2")
                                y_label = st.text_input("Y軸の名称", value=target_col, key="gy_a2")

                                fig = px.box(df, x=group_col, y=target_col, color=group_col, title=g_title, labels={group_col: x_label, target_col: y_label})
                                st.plotly_chart(fig, use_container_width=True)
                                download_plotly_figure(fig, f"box_multigroups_{target_col}")

                            elif paired == "対応あり":
                                id_col = st.selectbox("患者IDの列を選択", [c for c in df.columns if col_types[c] == "解析対象外（IDなど）"], key="id_select")
                                if normality: res = pg.rm_anova(data=df, dv=target_col, within=group_col, subject=id_col); method_name = "反復測定分散分析"
                                else: res = pg.friedman(data=df, dv=target_col, within=group_col, subject=id_col); method_name = "フリードマン検定"
                                st.write(f"### 📊 {method_name} の結果")
                                st.dataframe(res)
                                p_col = 'p_unc' if 'p_unc' in res.columns else 'p-unc'
                                if res[p_col].values[0] < 0.05: st.success("💡 結論：時間経過（または群間）において、有意な数値の変化が認められます。")
                                else: st.warning("💡 結論：有意な変化は認められませんでした。")

            # --- B. 割合の「差」を比較する ---
            elif outcome_type == "B. 割合の「差」を比較する":
                 paired_b = st.radio("Q2. データの対応は？", ["対応なし", "対応あり"])
                 if paired_b == "対応なし":
                     col_g, col_t = st.columns(2)
                     with col_g: group_col = st.selectbox("群分け変数", [c for c in df.columns if col_types[c] == "カテゴリ（群分け）"], key="g2")
                     with col_t: target_col = st.selectbox("解析したい変数", [c for c in df.columns if col_types[c] == "カテゴリ（群分け）"], key="t2")

                     if group_col and target_col:
                         if group_col == target_col:
                             st.warning("⚠️ 異なる変数を選んでください。")
                         else:
                             cross_tab = pd.crosstab(df[group_col], df[target_col])
                             st.write("### 📊 クロス集計表（実際の人数）")
                             st.dataframe(cross_tab)

                             expected, observed, stats_res = pg.chi2_independence(data=df, x=group_col, y=target_col)
                             st.write("### 📊 カイ二乗検定の結果")

                             # 💡 ✨新機能：カイ二乗検定の難解用語解説✨
                             st.info("""
                             📖 **表の専門用語の読み方:**
                             * **pval:** P値です。ここが0.05未満なら割合に「有意な差がある」と言えます。
                             * **cramer (クラメールのV):** 関連性の強さを示す指標です（0〜1）。0.1で弱い関連、0.3で中等度の関連、0.5以上で強い関連があると解釈します。
                             * **power:** 検出力です。このデータ数で差を正しく見つけ出せる力（80%以上が理想）を示します。
                             """)
                             st.dataframe(stats_res)

                             p_val = stats_res['pval'].values[0]
                             if p_val < 0.05: st.success(f"💡 結論 (p={p_val:.4f}): 2つの変数の間には、統計学的に有意な関連（割合の差）が認められます！")
                             else: st.warning(f"💡 結論 (p={p_val:.4f}): 割合の差に統計学的な有意差は認められませんでした。")

                             with st.expander("💡 この解析の裏側（思考と計算のプロセス）"):
                                 st.write("群間で割合に『全く差がない』と仮定した場合の理論上の期待人数と、実際の観察人数のズレの大きさを計算し、それを確率（P値）に変換しています。")

                             st.write("### 🛠️ グラフの編集")
                             g_title = st.text_input("グラフのタイトル", value=f"{target_col} の割合比較", key="gt_b1")
                             x_label = st.text_input("X軸の名称", value=group_col, key="gx_b1")
                             y_label = st.text_input("Y軸の名称", value="割合 (Proportion)", key="gy_b1")

                             df_prop = cross_tab.div(cross_tab.sum(axis=1), axis=0).reset_index()
                             df_prop_melted = df_prop.melt(id_vars=group_col, value_name="Proportion", var_name=target_col)
                             fig = px.bar(df_prop_melted, x=group_col, y="Proportion", color=target_col, title=g_title, labels={"Proportion": y_label, group_col: x_label})
                             st.plotly_chart(fig, use_container_width=True)
                             download_plotly_figure(fig, f"proportion_{target_col}")

                 elif paired_b == "対応あり":
                     col_m1, col_m2 = st.columns(2)
                     with col_m1: m1_col = st.selectbox("検査1（時点1）", [c for c in df.columns if col_types[c] == "カテゴリ（群分け）"], key="m1")
                     with col_m2: m2_col = st.selectbox("検査2（時点2）", [c for c in df.columns if col_types[c] == "カテゴリ（群分け）"], key="m2")

                     if m1_col and m2_col:
                         if m1_col == m2_col:
                             st.warning("⚠️ 異なる時点・検査を選んでください。")
                         else:
                             cross_tab = pd.crosstab(df[m1_col], df[m2_col])
                             st.write("### 📊 対応ありのクロス集計表")
                             st.dataframe(cross_tab)
                             if cross_tab.shape == (2, 2):
                                 res = mcnemar(cross_tab, exact=True)
                                 st.write("### 📊 マクネマー検定の結果")
                                 st.info(f"**p値 (p-value):** {res.pvalue:.4f}")

                                 if res.pvalue < 0.05: st.success("💡 結論：2つの時点（または検査）の間で、陽性率に有意な変化・差が認められました。")
                                 else: st.warning("💡 結論：陽性率に有意な変化・差は認められませんでした。")

                                 with st.expander("💡 この解析の裏側（思考と計算のプロセス）"):
                                     st.write("同じ被験者に対する前後比較のため、表の対角線上にある『結果が食い違ったマス』の比率の偏りから確率を計算しました。")
                             else: st.error("マクネマー検定は2x2の表（例：陽性と陰性）である必要があります。")

            # --- C. 相関分析 ---
            elif outcome_type == "C. 2つの連続データの「関係性」を調べる":
                 col_x, col_y = st.columns(2)
                 with col_x: x_col = st.selectbox("変数X（横軸）", [c for c in df.columns if col_types[c] == "連続値（数値）"], key="corr_x")
                 with col_y: y_col = st.selectbox("変数Y（縦軸）", [c for c in df.columns if col_types[c] == "連続値（数値）"], key="corr_y")

                 if x_col and y_col:
                     if x_col == y_col:
                         st.warning("⚠️ X軸とY軸には異なる変数を選んでください。")
                     else:
                         df_clean = df[[x_col, y_col]].dropna()
                         _, p_x = stats.shapiro(df_clean[x_col]); _, p_y = stats.shapiro(df_clean[y_col])
                         corr_method = "pearson" if p_x > 0.05 and p_y > 0.05 else "spearman"

                         st.write("### 🛠️ グラフの編集")
                         g_title = st.text_input("グラフのタイトル", value=f"{x_col} と {y_col} の相関散布図", key="gt_c1")
                         x_label = st.text_input("X軸の名称", value=x_col, key="gx_c1")
                         y_label = st.text_input("Y軸の名称", value=y_col, key="gy_c1")

                         fig = px.scatter(df_clean, x=x_col, y=y_col, trendline="ols", trendline_color_override="red", opacity=0.7, title=g_title, labels={x_col: x_label, y_col: y_label})
                         st.plotly_chart(fig, use_container_width=True)
                         download_plotly_figure(fig, f"scatter_{x_col}_{y_col}")

                         res_corr = pg.corr(df_clean[x_col], df_clean[y_col], method=corr_method)
                         st.write(f"### 📊 {corr_method}相関分析の結果")

                         # 💡 ✨新機能：相関分析の難解用語解説✨
                         st.info("""
                         📖 **表の専門用語の読み方:**
                         * **n:** データ数
                         * **r:** 相関係数（-1から1の間。1に近いほど強い正の比例、-1に近いほど負の比例を示します）
                         * **CI95%:** 相関係数『r』の95%信頼区間
                         * **p-val:** P値（0.05未満なら「相関がある」と結論づけます）
                         """)
                         st.dataframe(res_corr)

                         # 💡 ✨復活：相関分析の結論解釈✨
                         r_val = res_corr['r'].values[0]
                         p_col = 'p_val' if 'p_val' in res_corr.columns else 'p-val'
                         p_val = res_corr[p_col].values[0]
                         if p_val < 0.05:
                             if r_val > 0.5: strength = "強い正の相関"
                             elif r_val > 0.2: strength = "弱い正の相関"
                             elif r_val < -0.5: strength = "強い負の相関"
                             elif r_val < -0.2: strength = "弱い負の相関"
                             else: strength = "ほとんど相関がない"
                             st.success(f"💡 結論 (p={p_val:.4f}): 2変数間には統計学的に有意な **「{strength}」** (r={r_val:.2f}) が認められます。")
                         else: st.warning(f"💡 結論 (p={p_val:.4f}): 2変数間に有意な相関は認められませんでした。")

                         with st.expander("💡 この解析の裏側（思考と計算のプロセス）"):
                             st.write(f"1. **正規性チェック:** 両方のデータが正規分布しているかを確認しました。\n2. **手法の決定:** 条件により **{corr_method}相関係数** の計算が選択されました。\n3. 直線的な関係性の強さを『r』として数値化し、それが偶然の産物ではないかをP値で検定しています。")

        # ==========================================
        # タブ3：生存時間解析
        # ==========================================
        with tab3:
            st.header("⏳ 生存時間解析（カプラン・マイヤー法）")
            col_t, col_e, col_g = st.columns(3)
            with col_t: km_time_col = st.selectbox("1. 期間・日数 (Time)", [c for c in df.columns if col_types[c] == "連続値（数値）"], key="km_time")
            with col_e: km_event_col = st.selectbox("2. イベント発生 (1=発生, 0=打ち切り)", [c for c in df.columns if col_types[c] != "解析対象外（IDなど）"], key="km_event")
            with col_g: km_group_col = st.selectbox("3. 群分け (Group)", [c for c in df.columns if col_types[c] == "カテゴリ（群分け）"], key="km_group")

            if km_time_col and km_event_col and km_group_col:
                if len(set([km_time_col, km_event_col, km_group_col])) < 3:
                    st.warning("⚠️ 期間、イベント、群分けにはすべて異なる変数を選んでください。")
                else:
                    st.write("### 🛠️ グラフの編集")
                    g_title = st.text_input("グラフのタイトル", value=f"Kaplan-Meier Survival Curve ({km_group_col})", key="gt_d1")
                    x_label = st.text_input("X軸の名称 (期間)", value="Time", key="gx_d1")
                    y_label = st.text_input("Y軸の名称 (生存率)", value="Survival Probability", key="gy_d1")

                    cols_to_extract = list(set([km_time_col, km_event_col, km_group_col]))
                    km_df = df[cols_to_extract].dropna()

                    fig, ax = plt.subplots(figsize=(8, 5))
                    kmf = KaplanMeierFitter(); groups = km_df[km_group_col].unique()
                    for g in groups:
                        idx = (km_df[km_group_col] == g)
                        kmf.fit(km_df[km_time_col][idx], km_df[km_event_col][idx], label=str(g))
                        kmf.plot_survival_function(ax=ax, show_censors=True)
                    plt.grid(True, alpha=0.3)
                    plt.title(g_title)
                    plt.xlabel(x_label)
                    plt.ylabel(y_label)
                    st.pyplot(fig)
                    download_matplotlib_figure(fig, "kaplan_meier.png")

                    if len(groups) == 2:
                        idx0 = (km_df[km_group_col] == groups[0])
                        idx1 = (km_df[km_group_col] == groups[1])
                        results = logrank_test(km_df[km_time_col][idx0], km_df[km_time_col][idx1], event_observed_A=km_df[km_event_col][idx0], event_observed_B=km_df[km_event_col][idx1])
                        p_val = results.p_value
                        if p_val < 0.05: st.success(f"💡 結論 (Log-rank p={p_val:.4f}): 2群の生存曲線には、統計学的に有意な差が認められました。")
                        else: st.warning(f"💡 結論 (Log-rank p={p_val:.4f}): 生存曲線に有意な差は認められませんでした。")

        # ==========================================
        # タブ4：多変量解析・調整
        # ==========================================
        with tab4:
            st.header("📈 多変量解析・共変量調整（複数の要因を同時に調べる）")
            analysis_type = st.radio("解析の種類を選択", ["A. ロジスティック回帰", "B. 重回帰分析", "C. Cox比例ハザード", "D. 共分散分析 (ANCOVA)"])
            st.write("---")

            def plot_forest(results_df, title="Forest Plot", x_label="Ratio"):
                variables = results_df.index; val_col = results_df.columns[0]
                fig = go.Figure()
                fig.add_shape(type="line", x0=1, y0=-0.5, x1=1, y1=len(variables)-0.5, line=dict(color="red", width=2, dash="dash"))
                fig.add_trace(go.Scatter(x=results_df[val_col], y=variables, error_x=dict(type='data', symmetric=False, array=results_df['95% CI (上限)'] - results_df[val_col], arrayminus=results_df[val_col] - results_df['95% CI (下限)'], color='blue', thickness=2, width=8), mode='markers', marker=dict(color='blue', size=10), name=val_col))
                fig.update_layout(title=title, xaxis_title=x_label, yaxis_title="Variables", height=max(400, len(variables)*50), margin=dict(l=150))
                return fig

            if analysis_type.startswith("D"):
                col_y, col_g = st.columns(2)
                with col_y: y_col = st.selectbox("🎯 目的変数 Y", [c for c in df.columns if col_types[c] == "連続値（数値）"], key="ancova_y")
                with col_g: group_col = st.selectbox("🗂️ 群分け変数", [c for c in df.columns if col_types[c] == "カテゴリ（群分け）"], key="ancova_g")
                covar_cols = st.multiselect("📏 補正したい共変量", [c for c in df.columns if col_types[c] == "連続値（数値）" and c != y_col], key="ancova_covar")

                if y_col and group_col and len(covar_cols) > 0:
                    if y_col == group_col or y_col in covar_cols or group_col in covar_cols:
                        st.warning("⚠️ 目的変数、群分け変数、共変量はそれぞれ異なるものを選んでください。")
                    else:
                        ancova_df = df[[y_col, group_col] + covar_cols].dropna()
                        res_ancova = pg.ancova(data=ancova_df, dv=y_col, between=group_col, covar=covar_cols)
                        st.write("### 📊 共分散分析 (ANCOVA) の結果")
                        st.dataframe(res_ancova)

                        p_col = 'p-unc' if 'p-unc' in res_ancova.columns else 'p_unc'
                        group_p = res_ancova.loc[res_ancova['Source'] == group_col, p_col].values[0]
                        if group_p < 0.05: st.success(f"💡 **結論 (p={group_p:.4f}):** 共変量の影響を補正しても、依然としてグループ間には有意な差が認められます！")
                        else: st.warning(f"💡 **結論 (p={group_p:.4f}):** 共変量の影響を補正すると、グループ間に有意差は認められませんでした。")

                        with st.expander("💡 この解析の裏側（思考と計算のプロセス）"):
                            st.write("共変量の影響を回帰ロジックで除去し、全員のスタートラインが完全に均一だったと仮定した状態を作ってから、改めてグループ間の差を検定しました。")

                        st.write("### 🛠️ グラフの編集")
                        g_title = st.text_input("グラフのタイトル", value="調整前のグループ間分布（箱ひげ図）", key="gt_e1")
                        fig = px.box(ancova_df, x=group_col, y=y_col, color=group_col, title=g_title)
                        st.plotly_chart(fig, use_container_width=True)
                        download_plotly_figure(fig, f"ancova_box_{y_col}")

            elif analysis_type.startswith("C"):
                col_t, col_e = st.columns(2)
                with col_t: time_col = st.selectbox("⏳ 期間・日数 (Time)", [c for c in df.columns if col_types[c] == "連続値（数値）"], key="cox_time")
                with col_e: event_col = st.selectbox("⚠️ イベント発生 (1=発生, 0=打ち切り)", [c for c in df.columns if col_types[c] != "解析対象外（IDなど）"], key="cox_event")
                x_cols = st.multiselect("🔍 説明変数 X (要因)", [c for c in df.columns if c not in [time_col, event_col] and col_types[c] != "解析対象外（IDなど）"], key="cox_x")

                if time_col and event_col and len(x_cols) > 0:
                    if time_col == event_col or time_col in x_cols or event_col in x_cols:
                        st.warning("⚠️ 期間、イベント、説明変数はそれぞれ異なるものを選んでください。")
                    else:
                        model_df = df[[time_col, event_col] + x_cols].dropna()
                        X = pd.get_dummies(model_df[x_cols], drop_first=True, dtype=float); cox_df = pd.concat([model_df[[time_col, event_col]], X], axis=1)
                        cph = CoxPHFitter(); cph.fit(cox_df, duration_col=time_col, event_col=event_col)
                        results_df = pd.DataFrame({"ハザード比": cph.hazard_ratios_, "p値": cph.summary['p'], "95% CI (下限)": np.exp(cph.summary['coef lower 95%']), "95% CI (上限)": np.exp(cph.summary['coef upper 95%'])})
                        st.write("### 📊 Cox比例ハザード分析の結果")
                        st.dataframe(results_df.style.format("{:.3f}"))

                        st.write("### 🛠️ グラフの編集")
                        g_title = st.text_input("グラフのタイトル", value="Forest Plot (Hazard Ratios)", key="gt_f1")
                        x_lbl = st.text_input("横軸の名称", value="Hazard Ratio", key="gx_f1")
                        fig = plot_forest(results_df, title=g_title, x_label=x_lbl)
                        st.plotly_chart(fig, use_container_width=True)
                        download_plotly_figure(fig, "forest_plot_cox")

            else:
                col_y, col_x = st.columns([1, 2])
                with col_y: y_col = st.selectbox("🎯 目的変数 Y", [c for c in df.columns if col_types[c] != "解析対象外（IDなど）"], key="multi_y")
                with col_x: x_cols = st.multiselect("🔍 説明変数 X", [c for c in df.columns if c != y_col and col_types[c] != "解析対象外（IDなど）"], key="multi_x")

                if y_col and len(x_cols) > 0:
                    if y_col in x_cols:
                        st.warning("⚠️ 目的変数と説明変数は異なるものを選んでください。")
                    else:
                        model_df = df[[y_col] + x_cols].dropna()
                        X = sm.add_constant(pd.get_dummies(model_df[x_cols], drop_first=True, dtype=float))

                        if analysis_type.startswith("A"):
                            y = pd.get_dummies(model_df[y_col], drop_first=True, dtype=float).iloc[:, 0]
                            model = sm.Logit(y, X).fit(disp=0)
                            results_df = pd.DataFrame({"オッズ比": np.exp(model.params), "p値": model.pvalues, "95% CI (下限)": np.exp(model.conf_int()[0]), "95% CI (上限)": np.exp(model.conf_int()[1])}).drop('const')
                            st.write("### 📊 ロジスティック回帰分析の結果")
                            st.dataframe(results_df.style.format("{:.3f}"))

                            st.write("### 🛠️ グラフの編集")
                            g_title = st.text_input("グラフのタイトル", value="Forest Plot (Odds Ratios)", key="gt_g1")
                            x_lbl = st.text_input("横軸の名称", value="Odds Ratio", key="gx_g1")
                            fig = plot_forest(results_df, title=g_title, x_label=x_lbl)
                            st.plotly_chart(fig, use_container_width=True)
                            download_plotly_figure(fig, "forest_plot_logistic")

                        elif analysis_type.startswith("B"):
                            y = model_df[y_col]; model = sm.OLS(y, X).fit()
                            results_df = pd.DataFrame({"偏回帰係数": model.params, "p値": model.pvalues, "95% CI (下限)": model.conf_int()[0], "95% CI (上限)": model.conf_int()[1]}).drop('const')
                            st.write("### 📊 重回帰分析の結果")
                            st.dataframe(results_df.style.format("{:.3f}"))
                            st.write(f"**決定係数 ($R^2$):** {model.rsquared:.3f}")

        # ==========================================
        # タブ5：診断能の評価（ROC曲線）
        # ==========================================
        with tab5:
            st.header("🎯 診断能の評価（ROC曲線分析）")
            col_y, col_x = st.columns(2)
            with col_y: y_col = st.selectbox("🎯 確定診断 (1=病気, 0=健康など)", [c for c in df.columns if col_types[c] == "カテゴリ（群分け）"], key="roc_y")
            with col_x: x_col = st.selectbox("🔍 検査値・スコア (連続値)", [c for c in df.columns if col_types[c] == "連続値（数値）"], key="roc_x")

            if y_col and x_col:
                if y_col == x_col:
                    st.warning("⚠️ 確定診断と検査値には異なる変数を選んでください。")
                else:
                    roc_df = df[[y_col, x_col]].dropna()
                    y_true = pd.get_dummies(roc_df[y_col], drop_first=True, dtype=float).iloc[:, 0]
                    y_score = roc_df[x_col]
                    fpr, tpr, thresholds = roc_curve(y_true, y_score); roc_auc = auc(fpr, tpr)
                    youden_idx = np.argmax(tpr - fpr); best_threshold = thresholds[youden_idx]

                    st.write("### 🛠️ グラフの編集")
                    g_title = st.text_input("グラフのタイトル", value="ROC Curve Analysis", key="gt_h1")
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=fpr, y=tpr, mode='lines', name=f'ROC (AUC = {roc_auc:.3f})', line=dict(color='blue', width=2)))
                    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode='lines', line=dict(color='gray', dash='dash')))
                    fig.add_trace(go.Scatter(x=[fpr[youden_idx]], y=[tpr[youden_idx]], mode='markers', name=f'カットオフ: {best_threshold:.2f}', marker=dict(color='red', size=12, symbol='star')))
                    fig.update_layout(title=g_title, xaxis_title="1 - Specificity", yaxis_title="Sensitivity")
                    st.plotly_chart(fig, use_container_width=True)
                    download_plotly_figure(fig, "roc_curve_final")

                    st.info(f"**AUC (曲線下面積):** {roc_auc:.3f}")
                    st.success(f"💡 **最適なカットオフ値:** {best_threshold:.2f} (感度: {tpr[youden_idx]:.1%}, 特異度: {1-fpr[youden_idx]:.1%})")

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
