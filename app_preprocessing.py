import streamlit as st
import pandas as pd
import numpy as np
import statsmodels.api as sm

st.set_page_config(page_title="EasyMedStats - 前処理編", layout="wide")
st.title("EasyMedStats - 前処理・クレンジング編")
st.write("医療データの泥臭い整形作業から、高度な傾向スコアマッチング（PSM）まで順番に重ねがけしていくアプリです。")

# --- コアシステム：ファイル名も記憶してバグを防止 ---
if 'raw_df' not in st.session_state: st.session_state.raw_df = None
if 'current_df' not in st.session_state: st.session_state.current_df = None
if 'action_msg' not in st.session_state: st.session_state.action_msg = None
if 'main_filename' not in st.session_state: st.session_state.main_filename = None
if 'sub_filename' not in st.session_state: st.session_state.sub_filename = None

# --- サイドバー ---
st.sidebar.header("1. メインデータの読み込み")
uploaded_file = st.sidebar.file_uploader("メインのExcel/CSVをドロップ", type=["csv", "xlsx"], key="main_upload")

st.sidebar.header("2. 結合用データの読み込み（任意）")
uploaded_file_B = st.sidebar.file_uploader("ドッキングしたい別ファイルをドロップ", type=["csv", "xlsx"], key="sub_upload")

# 💡 バグ修正：ファイル名が変わったらデータを強制リセットして読み込み直す
if uploaded_file is not None:
    if st.session_state.main_filename != uploaded_file.name:
        try:
            if uploaded_file.name.endswith('.csv'): df = pd.read_csv(uploaded_file, dtype=str)
            else: df = pd.read_excel(uploaded_file, dtype=str)
            df = df.apply(lambda col: pd.to_numeric(col, errors='ignore') if col.dtype == 'object' else col)
            st.session_state.raw_df = df.copy()
            st.session_state.current_df = df.copy()
            st.session_state.main_filename = uploaded_file.name # ファイル名を記憶
            st.session_state.action_msg = f"新しいデータ「{uploaded_file.name}」を読み込みました！"
        except Exception as e: st.sidebar.error(f"エラー: {e}")

df_B = None
if uploaded_file_B is not None:
    if st.session_state.sub_filename != uploaded_file_B.name:
        try:
            uploaded_file_B.seek(0)
            if uploaded_file_B.name.endswith('.csv'): df_B = pd.read_csv(uploaded_file_B, dtype=str)
            else: df_B = pd.read_excel(uploaded_file_B, dtype=str)
            df_B = df_B.apply(lambda col: pd.to_numeric(col, errors='ignore') if col.dtype == 'object' else col)
            st.session_state.sub_filename = uploaded_file_B.name
        except Exception as e: st.sidebar.error(f"結合データの読み込みエラー: {e}")
    else:
        # すでに読み込み済みの場合は再度パースする（Streamlitの再描画対策）
        uploaded_file_B.seek(0)
        if uploaded_file_B.name.endswith('.csv'): df_B = pd.read_csv(uploaded_file_B, dtype=str)
        else: df_B = pd.read_excel(uploaded_file_B, dtype=str)
        df_B = df_B.apply(lambda col: pd.to_numeric(col, errors='ignore') if col.dtype == 'object' else col)

if st.session_state.current_df is not None:
    df = st.session_state.current_df

    st.sidebar.markdown("---")
    st.sidebar.header("📊 現在のデータ状態")
    st.sidebar.info(f"**行数（患者数など）:** {len(df):,} 行\n\n**列数（変数の数）:** {len(df.columns)} 列")

    st.sidebar.markdown("---")
    st.sidebar.header("💾 エクスポート＆リセット")
    csv = df.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button("📥 現在のデータをCSVで保存", csv, "cleaned_data.csv", "text/csv")

    if st.sidebar.button("🔄 データを初期状態に戻す"):
        st.session_state.current_df = st.session_state.raw_df.copy()
        st.session_state.action_msg = "データをアップロード直後の初期状態にリセットしました。"
        st.rerun()

    if st.session_state.action_msg:
        st.success(st.session_state.action_msg)
        st.toast(st.session_state.action_msg, icon="✅")
        st.session_state.action_msg = None

    with st.expander("👀 現在のデータプレビュー（最初の100行）", expanded=True):
        st.dataframe(df.head(100))

    st.write("---")
    st.subheader("🛠️ データ編集メニュー")

    tab1, tab2, tab3, tab6, tab4, tab5, tab7 = st.tabs([
        "🧹 1. ゴミ取り", "✂️ 2. 抽出", "🚩 3. フラグ化",
        "➕ 4. 計算・変換", "🔄 5. 縦横変換", "🔗 6. 突合",
        "⚖️ 7. PSM (マッチング)"
    ])

    # ==========================================
    # タブ1：ゴミ取り
    # ==========================================
    with tab1:
        st.markdown("### 🗑️ 不要な列の削除（匿名化・整理）")
        cols_to_drop = st.multiselect("削除したい列をすべて選んでください", df.columns, key="drop_cols")
        if st.button("選択した列を削除して上書きする", type="primary"):
            if cols_to_drop:
                st.session_state.current_df = df.drop(columns=cols_to_drop)
                st.session_state.action_msg = f"列削除完了： {len(cols_to_drop)} 個の列を削除しました。"
                st.rerun()
            else: st.warning("削除する列が選ばれていません。")
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 👥 重複データの削除")
            dup_col = st.selectbox("基準となる列（IDなど）", df.columns, key="dup_col")
            keep_method = st.radio("どのデータを残すか", ["最初のデータ", "最後のデータ"], key="keep_m")
            if st.button("重複を削除して上書きする", type="primary"):
                keep_arg = 'first' if "最初" in keep_method else 'last'
                old_len = len(df)
                st.session_state.current_df = df.drop_duplicates(subset=[dup_col], keep=keep_arg)
                st.session_state.action_msg = f"重複削除完了： {old_len - len(st.session_state.current_df)} 件のデータを削除しました。"
                st.rerun()
        with col2:
            st.markdown("### 🕳️ 欠損値（空欄）の処理")
            na_col = st.selectbox("処理したい列", df.columns, key="na_col")
            na_method = st.radio("処理方法", ["空欄がある行を削除", "平均値で埋める", "中央値で埋める", "直前の値で埋める（LOCF）"], key="na_m")
            if st.button("欠損値を処理して上書きする", type="primary"):
                old_len = len(df)
                if "削除" in na_method:
                    st.session_state.current_df = df.dropna(subset=[na_col])
                    st.session_state.action_msg = f"欠損値削除完了： {old_len - len(st.session_state.current_df)} 行を削除しました。"
                else:
                    if "平均値" in na_method and pd.api.types.is_numeric_dtype(df[na_col]): st.session_state.current_df[na_col] = df[na_col].fillna(df[na_col].mean())
                    elif "中央値" in na_method and pd.api.types.is_numeric_dtype(df[na_col]): st.session_state.current_df[na_col] = df[na_col].fillna(df[na_col].median())
                    elif "直前" in na_method: st.session_state.current_df[na_col] = df[na_col].ffill()
                    st.session_state.action_msg = f"欠損値の穴埋め完了： 「{na_col}」を補完しました。"
                st.rerun()

    # ==========================================
    # タブ2：抽出
    # ==========================================
    with tab2:
        st.markdown("### 🔍 条件に合うデータだけを残す")
        fil_col = st.selectbox("検索する列", df.columns, key="fil_col")
        fil_type = st.radio("検索条件", ["キーワードを含む", "完全に一致する", "数値が〇〇以上"], key="fil_type")
        fil_val = st.text_input("検索するキーワードや数値を入力", key="fil_val")
        if st.button("抽出して上書きする", type="primary"):
            if fil_val:
                if "含む" in fil_type: st.session_state.current_df = df[df[fil_col].astype(str).str.contains(fil_val, na=False)]
                elif "完全" in fil_type: st.session_state.current_df = df[df[fil_col].astype(str) == fil_val]
                elif "以上" in fil_type: st.session_state.current_df = df[df[fil_col] >= float(fil_val)]
                st.session_state.action_msg = f"抽出完了： {len(st.session_state.current_df)} 行に絞り込みました。"
                st.rerun()

    # ==========================================
    # 🌟 強化版・タブ3：フラグ化（1と0の割り当て）
    # ==========================================
    with tab3:
        st.markdown("### 🚩 連続値のカテゴリ化 ＆ フラグ立て（1 / 0）")
        st.write("数値を特定の基準値で区切り、「1と0」のフラグや新しい文字ラベルを割り当てます。ロジスティック回帰やPSMに必須の処理です。")

        bin_col = st.selectbox("フラグ化・カテゴリ化する数値の列（例：年齢）", [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])], key="bin_col")
        threshold = st.number_input("基準となる数値を入力（この数値未満 / 以上で分割）", value=65.0, key="bin_th")

        col_high, col_low = st.columns(2)
        with col_high:
            label_high = st.text_input("基準値【以上】の場合のラベル（例： 1 または 高齢者）", value="1", key="lbl_h")
        with col_low:
            label_low = st.text_input("基準値【未満】の場合のラベル（例： 0 または 若年者）", value="0", key="lbl_l")

        new_col_name = st.text_input("新しく作るフラグ列の名前", value=f"{bin_col}_Flag", key="bin_new")

        if st.button("フラグを作成して新しい列を追加する", type="primary"):
            # 1や0が入力された場合は、文字列ではなく数値として扱うように自動調整
            val_high = float(label_high) if label_high.replace('.','',1).isdigit() else label_high
            val_low = float(label_low) if label_low.replace('.','',1).isdigit() else label_low

            st.session_state.current_df[new_col_name] = np.where(df[bin_col] >= threshold, val_high, val_low)
            st.session_state.action_msg = f"フラグ化完了： 新しい列「{new_col_name}」を追加しました。"
            st.rerun()

    # ==========================================
    # タブ6：変数の計算・変換
    # ==========================================
    with tab6:
        st.markdown("### ➕ 変数の計算・変換・クリーニング")
        calc_mode = st.radio("処理", ["A. 日付差分計算", "B. 四則演算", "C. 日付フォーマット変換", "D. データ型強制変換", "E. 文字列の置換・削除"])

        if calc_mode.startswith("A"):
            date_end = st.selectbox("終わりの日", df.columns, key="d_end")
            date_start = st.selectbox("始まりの日", df.columns, key="d_start")
            date_new_name = st.text_input("新しく作る列の名前", value="Duration_Days", key="d_new")
            if st.button("日付の差分（日数）を計算して追加する", type="primary"):
                try:
                    end_dt = pd.to_datetime(df[date_end], errors='coerce')
                    start_dt = pd.to_datetime(df[date_start], errors='coerce')
                    st.session_state.current_df[date_new_name] = (end_dt - start_dt).dt.days
                    st.session_state.action_msg = f"日付計算完了： 新しい列「{date_new_name}」を作成しました。"
                    st.rerun()
                except Exception as e: st.error(f"エラー: {e}")

        elif calc_mode.startswith("B"):
            num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            math_col_a = st.selectbox("変数A", num_cols, key="m_a")
            math_op = st.selectbox("計算方法", ["＋", "－", "×", "÷"], key="m_op")
            math_type = st.radio("変数Bの種類", ["他の列を指定", "固定の数値を入力"], key="m_type")
            if "列" in math_type:
                math_col_b = st.selectbox("変数B", num_cols, key="m_b_col")
                val_b = df[math_col_b]
            else:
                val_b = st.number_input("固定の数値", value=1.0, key="m_b_val")
            math_new_name = st.text_input("新しく作る列の名前", value="Calculated_Score", key="m_new")
            if st.button("数式を計算して新しい列を追加する", type="primary"):
                try:
                    if "＋" in math_op: st.session_state.current_df[math_new_name] = df[math_col_a] + val_b
                    elif "－" in math_op: st.session_state.current_df[math_new_name] = df[math_col_a] - val_b
                    elif "×" in math_op: st.session_state.current_df[math_new_name] = df[math_col_a] * val_b
                    elif "÷" in math_op: st.session_state.current_df[math_new_name] = df[math_col_a] / val_b
                    st.session_state.action_msg = f"四則演算完了： 新しい列「{math_new_name}」を作成しました。"
                    st.rerun()
                except Exception as e: st.error(f"エラー: {e}")

        elif calc_mode.startswith("C"):
            date_format_col = st.selectbox("変換したい列（数字の羅列）", df.columns, key="df_col")
            date_format_type = st.radio("現在の形式", ["8桁の数字（YYYYMMDD）", "6桁の年月（YYYYMM） ➡ 後ろに『01』を補う"])
            date_format_new = st.text_input("上書きするか、新しい列を作るか", value=date_format_col, key="df_new")
            if st.button("日付データに変換する", type="primary"):
                try:
                    if "8桁" in date_format_type:
                        st.session_state.current_df[date_format_new] = pd.to_datetime(df[date_format_col].astype(str), format='%Y%m%d', errors='coerce')
                    else:
                        st.session_state.current_df[date_format_new] = pd.to_datetime(df[date_format_col].astype(str) + '01', format='%Y%m%d', errors='coerce')
                    st.session_state.current_df[date_format_new] = st.session_state.current_df[date_format_new].dt.strftime('%Y-%m-%d')
                    st.session_state.action_msg = f"日付変換完了： 「{date_format_new}」をカレンダー日付に変換しました。"
                    st.rerun()
                except Exception as e: st.error(f"変換エラー: {e}")

        elif calc_mode.startswith("D"):
            type_col = st.selectbox("型を変換したい列", df.columns, key="t_col")
            type_to = st.radio("どの型に変換しますか？", ["文字列（IDやカテゴリとして扱う）", "数値（計算できるようにする）"])
            if st.button("データ型を強制変換して上書きする", type="primary"):
                try:
                    if "文字列" in type_to: st.session_state.current_df[type_col] = df[type_col].astype(str)
                    else: st.session_state.current_df[type_col] = pd.to_numeric(df[type_col], errors='coerce')
                    st.session_state.action_msg = f"型変換完了： 「{type_col}」を変換しました。"
                    st.rerun()
                except Exception as e: st.error(f"エラー: {e}")

        elif calc_mode.startswith("E"):
            rep_col = st.selectbox("処理したい列", df.columns, key="rep_col")
            rep_target = st.text_input("見つけて置き換えたい文字", key="rep_tgt")
            rep_new = st.text_input("新しい文字（消したい場合は空欄）", key="rep_new")
            if st.button("文字の置換・削除を実行して上書きする", type="primary"):
                if rep_target:
                    st.session_state.current_df[rep_col] = df[rep_col].astype(str).str.replace(rep_target, rep_new, regex=False)
                    st.session_state.current_df[rep_col] = st.session_state.current_df[rep_col].replace(['', 'nan', 'None'], np.nan)
                    st.session_state.action_msg = f"置換完了： 「{rep_col}」列の『{rep_target}』を変換しました。"
                    st.rerun()
                else: st.warning("置き換えたい文字を入力してください。")

    # ==========================================
    # タブ4：構造変換
    # ==========================================
    with tab4:
        st.markdown("### 🔄 データの縦横変換（ピボット処理）")
        col_id = st.selectbox("1. 固体の識別子となる列", df.columns, key="piv_id")
        col_time = st.selectbox("2. 時間や回数を表す列", [c for c in df.columns if c != col_id], key="piv_time")
        col_value = st.selectbox("3. 横に並べ替えたい数値の列", [c for c in df.columns if c not in [col_id, col_time]], key="piv_val")
        if st.button("横持ちへ変換して上書きする", type="primary"):
            try:
                df_pivoted = df.pivot(index=col_id, columns=col_time, values=col_value)
                df_pivoted.columns = [f"{col_value}_{col}" for col in df_pivoted.columns]
                df_pivoted = df_pivoted.reset_index()
                st.session_state.current_df = df_pivoted
                st.session_state.action_msg = f"構造変換完了： {len(df_pivoted)} 行の横長データに変換しました。"
                st.rerun()
            except Exception as e: st.error(f"構造変換に失敗しました。詳細: {e}")

    # ==========================================
    # タブ5：データの横結合
    # ==========================================
    with tab5:
        st.markdown("### 🔗 2つのファイルをIDで突合する（横結合）")
        if df_B is not None:
            col_left = st.selectbox("現在のデータ側のID", df.columns, key="join_L")
            col_right = st.selectbox("別ファイル側のID", df_B.columns, key="join_R")
            join_how = st.radio("結合方式", ["左結合", "内部結合"])
            if st.button("突合して上書き統合する", type="primary"):
                try:
                    how_arg = 'left' if "左結合" in join_how else 'inner'
                    old_cols, old_rows = len(df.columns), len(df)
                    df_merged = pd.merge(df, df_B, left_on=col_left, right_on=col_right, how=how_arg)
                    if col_left != col_right and col_right in df_merged.columns: df_merged = df_merged.drop(columns=[col_right])
                    st.session_state.current_df = df_merged
                    st.session_state.action_msg = f"結合完了： 行数 {old_rows} ➡ {len(df_merged)} になりました。"
                    st.rerun()
                except Exception as e: st.error(f"エラー: {e}")
        else: st.info("別ファイルをアップロードしてください。")

    # ==========================================
    # タブ7：傾向スコアマッチング (PSM)
    # ==========================================
    with tab7:
        st.markdown("### ⚖️ 傾向スコアマッチング（1:1 最近傍マッチング）")
        st.write("治療群と対照群の背景（年齢やBMIなど）が同じになるように、似た者同士を自動でペアにし、あぶれたデータを消去します。")
        st.info("⚠️ 注意: 介入変数（治療の有無）は『1 と 0』で入力されている必要があります。タブ3でフラグ化しておいてください。")

        treat_col = st.selectbox("🎯 介入変数（治療の有無: 1 or 0）", [c for c in df.columns if set(df[c].dropna().unique()).issubset({0, 1, 0.0, 1.0, '0', '1'})], key="psm_treat")
        covar_cols = st.multiselect("⚖️ 揃えたい背景因子（共変量: 年齢、BMIなど）", [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c != treat_col], key="psm_cov")

        if st.button("傾向スコアを計算し、マッチングを実行して上書きする", type="primary"):
            if treat_col and len(covar_cols) > 0:
                try:
                    psm_df = df.dropna(subset=[treat_col] + covar_cols).copy()
                    psm_df[treat_col] = pd.to_numeric(psm_df[treat_col])

                    X = sm.add_constant(psm_df[covar_cols])
                    y = psm_df[treat_col]
                    model = sm.Logit(y, X).fit(disp=0)
                    psm_df['Propensity_Score'] = model.predict(X)

                    treat_df = psm_df[psm_df[treat_col] == 1].copy()
                    control_df = psm_df[psm_df[treat_col] == 0].copy()

                    matched_indices = []
                    for idx, row in treat_df.iterrows():
                        if len(control_df) == 0: break
                        distances = np.abs(control_df['Propensity_Score'] - row['Propensity_Score'])
                        best_match_idx = distances.idxmin()
                        matched_indices.append(idx)
                        matched_indices.append(best_match_idx)
                        control_df = control_df.drop(best_match_idx)

                    matched_df = psm_df.loc[matched_indices].copy()

                    old_len = len(df)
                    new_len = len(matched_df)
                    st.session_state.current_df = matched_df
                    st.session_state.action_msg = f"PSM完了： {int(new_len/2)}組 のペアを作成しました！（全体行数: {old_len} ➡ {new_len}）"
                    st.rerun()
                except Exception as e:
                    st.error(f"エラーが発生しました。詳細: {e}")
            else:
                st.warning("介入変数と、少なくとも1つの背景因子を選択してください。")

else:
    st.info("👈 左のサイドバーからメインデータをアップロードして開始してください。")
