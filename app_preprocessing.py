import streamlit as st
import pandas as pd
import numpy as np
import statsmodels.api as sm
import unicodedata  # 👈 これを追加

st.set_page_config(page_title="EasyMedStats - 前処理編", layout="wide")
st.title("EasyMedStats - 前処理・クレンジング編")
st.write("医療データのクレンジングおよび前処理作業をローカル環境で完結させるアプリケーションです。")

# --- コアシステム：ファイル状態の監視 ---
if 'raw_df' not in st.session_state: st.session_state.raw_df = None
if 'current_df' not in st.session_state: st.session_state.current_df = None
if 'action_msg' not in st.session_state: st.session_state.action_msg = None

# --- サイドバー：読み込み設定 ---
st.sidebar.header("1. メインデータの読み込み")
uploaded_file = st.sidebar.file_uploader("メインのExcel/CSVをドロップ", type=["csv", "xlsx"], key="main_upload")
skip_rows = st.sidebar.number_input("読み飛ばす上の行数（タイトルなど）", min_value=0, value=0)
header_rows = st.sidebar.number_input("列名（ヘッダー）に使われている行数", min_value=1, value=1)

st.sidebar.header("2. 結合用データの読み込み（任意）")
uploaded_file_B = st.sidebar.file_uploader("ドッキングしたい別ファイルをドロップ", type=["csv", "xlsx"], key="sub_upload")
skip_rows_b = st.sidebar.number_input("結合データの読み飛ばす行数", min_value=0, value=0, key="skip_b")
header_rows_b = st.sidebar.number_input("結合データのヘッダー行数", min_value=1, value=1, key="head_b")

def load_data(file, skip, head):
    if file.name.endswith('.csv'): df = pd.read_csv(file, skiprows=skip, header=list(range(head)), dtype=str)
    else: df = pd.read_excel(file, skiprows=skip, header=list(range(head)), dtype=str)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(filter(None, [str(c) for c in col])).strip() for col in df.columns.values]
    df = df.apply(lambda col: pd.to_numeric(col, errors='ignore') if col.dtype == 'object' else col)
    return df

# リアルタイム読み込みシステム
if uploaded_file is None:
    st.session_state.raw_df = None
    st.session_state.current_df = None
    st.session_state.main_file_id = None
else:
    if (st.session_state.get('main_file_id') != uploaded_file.file_id or 
        st.session_state.get('last_skip') != skip_rows or 
        st.session_state.get('last_header') != header_rows):
        
        try:
            df = load_data(uploaded_file, skip_rows, header_rows)
            st.session_state.raw_df = df.copy()
            st.session_state.current_df = df.copy()
            st.session_state.main_file_id = uploaded_file.file_id
            st.session_state.last_skip = skip_rows
            st.session_state.last_header = header_rows
            st.session_state.action_msg = "データを読み込みました。（設定変更を反映）"
        except Exception as e:
            st.sidebar.error(f"読み込みエラー: {e}")

df_B = None
if uploaded_file_B is not None:
    if (st.session_state.get('sub_file_id') != uploaded_file_B.file_id or 
        st.session_state.get('last_skip_b') != skip_rows_b or 
        st.session_state.get('last_header_b') != header_rows_b):
        try:
            uploaded_file_B.seek(0)
            df_B = load_data(uploaded_file_B, skip_rows_b, header_rows_b)
            st.session_state.sub_file_id = uploaded_file_B.file_id
            st.session_state.last_skip_b = skip_rows_b
            st.session_state.last_header_b = header_rows_b
        except Exception as e: st.sidebar.error(f"エラー: {e}")
    else:
        uploaded_file_B.seek(0)
        df_B = load_data(uploaded_file_B, skip_rows_b, header_rows_b)

if st.session_state.current_df is not None:
    df = st.session_state.current_df

    st.sidebar.markdown("---")
    st.sidebar.header("データステータス")
    st.sidebar.info(f"**行数:** {len(df):,} 行\n\n**列数:** {len(df.columns)} 列")

    if df_B is not None:
        st.sidebar.markdown("**📂 結合用データのプレビュー**")
        st.sidebar.dataframe(df_B.head(3), use_container_width=True)

    st.sidebar.markdown("---")
    st.sidebar.header("データ出力・リセット")
    csv = df.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button("現在のデータをCSVで保存", csv, "cleaned_data.csv", "text/csv")
    if st.sidebar.button("データを初期状態に戻す"):
        st.session_state.current_df = st.session_state.raw_df.copy()
        st.session_state.action_msg = "データを初期状態にリセットしました。"
        st.rerun()

    if st.session_state.action_msg:
        st.success(st.session_state.action_msg)
        st.toast(st.session_state.action_msg)
        st.session_state.action_msg = None

    st.markdown("### データプレビュー")

    # 🔽🔽🔽 ここから追加 🔽🔽🔽
    with st.expander("各列の現在のデータ型（数値 / 文字列）を確認する", expanded=False):
        type_info = []
        for c in df.columns:
            if pd.api.types.is_numeric_dtype(df[c]):
                status = "数値型 (Numeric)"
            else:
                status = "文字列型 (String/Object) ※一部計算で使えない可能性があります"
            type_info.append({"列名": c, "現在の状態": status})
        st.dataframe(pd.DataFrame(type_info), use_container_width=True)
    # 🔼🔼🔼 ここまで追加 🔼🔼🔼

    prev_col1, prev_col2 = st.columns([1, 4])
    with prev_col1:
        prev_mode = st.radio("表示範囲", ["最初 (Head)", "最後 (Tail)", "ランダム (Sample)", "全て (All)"])
    with prev_col2:
        if "最初" in prev_mode: st.dataframe(df.head(100), use_container_width=True)
        elif "最後" in prev_mode: st.dataframe(df.tail(100), use_container_width=True)
        elif "ランダム" in prev_mode: st.dataframe(df.sample(min(100, len(df))), use_container_width=True)
        else: st.dataframe(df, use_container_width=True)

    st.write("---")
    
    # 💡 ここが最大の変更点：タブの代わりに「横並びのラジオボタン」を使って状態を記憶させる
    selected_tab = st.radio(
        "データ編集メニュー", 
        ["1. 列整理・ゴミ取り", "2. 抽出", "3. フラグ化", "4. 計算・変換", "5. 縦横変換", "6. 突合", "7. PSM"],
        horizontal=True,
        key="main_menu"
    )
    st.markdown("---")

    # ==========================================
    # 1. 列整理とゴミ取り
    # ==========================================
    if selected_tab == "1. 列整理・ゴミ取り":
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("### 列名の変更")
            rename_col = st.selectbox("名前を変えたい列", df.columns, key="ren_col")
            new_name = st.text_input("新しい列名を入力", key="ren_new")
            if st.button("列名を変更して上書きする", type="primary"):
                if new_name:
                    st.session_state.current_df = df.rename(columns={rename_col: new_name})
                    st.session_state.action_msg = f"列名変更完了： 「{rename_col}」を「{new_name}」に変更しました。"
                    st.rerun()
                else: st.warning("新しい列名を入力してください。")
                
        with col_r:
            st.markdown("### 不要な列の削除")
            cols_to_drop = st.multiselect("削除したい列を選択（複数可）", df.columns, key="drop_cols")
            if st.button("選択した列を削除して上書きする", type="primary"):
                if cols_to_drop:
                    st.session_state.current_df = df.drop(columns=cols_to_drop)
                    st.session_state.action_msg = f"列削除完了： {len(cols_to_drop)} 個の列を削除しました。"
                    st.rerun()
                    
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 重複データの削除")
            dup_cols = st.multiselect("重複判定の基準とする列（何も選ばないと『全列が完全に同じ行』を削除）", df.columns, key="dup_col")
            keep_method = st.radio("残すデータ", ["最初のデータ", "最後のデータ"], key="keep_m")
            if st.button("重複を削除して上書きする", type="primary"):
                keep_arg = 'first' if "最初" in keep_method else 'last'
                old_len = len(df)
                if len(dup_cols) == 0:
                    st.session_state.current_df = df.drop_duplicates(keep=keep_arg)
                else:
                    st.session_state.current_df = df.drop_duplicates(subset=dup_cols, keep=keep_arg)
                st.session_state.action_msg = f"重複削除完了： {old_len - len(st.session_state.current_df)} 件のデータを削除しました。"
                st.rerun()
        with col2:
            st.markdown("### 欠損値（空欄）の処理")
            na_col = st.selectbox("処理対象の列", df.columns, key="na_col")
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
    # 2. 抽出
    # ==========================================
    elif selected_tab == "2. 抽出":
        st.markdown("### 条件に合うデータのみ抽出")
        fil_col = st.selectbox("検索対象の列", df.columns, key="fil_col")
        fil_type = st.radio("検索条件", ["キーワードを含む", "完全に一致する", "数値が〇〇以上"], key="fil_type")
        fil_val = st.text_input("検索するキーワードまたは数値を入力", key="fil_val")
        if st.button("抽出して上書きする", type="primary"):
            if fil_val:
                if "含む" in fil_type: st.session_state.current_df = df[df[fil_col].astype(str).str.contains(fil_val, na=False)]
                elif "完全" in fil_type: st.session_state.current_df = df[df[fil_col].astype(str) == fil_val]
                elif "以上" in fil_type: st.session_state.current_df = df[df[fil_col] >= float(fil_val)]
                st.session_state.action_msg = f"抽出完了： {len(st.session_state.current_df)} 行に絞り込みました。"
                st.rerun()

    # ==========================================
    # 3. フラグ化
    # ==========================================
    elif selected_tab == "3. フラグ化":
        st.markdown("### 連続値のカテゴリ化・フラグ立て（1 / 0）")
        bin_col = st.selectbox("フラグ化・カテゴリ化する列", df.columns, key="bin_col")
        threshold = st.number_input("基準となる数値を入力", value=65.0, key="bin_th")
        col_high, col_low = st.columns(2)
        with col_high: label_high = st.text_input("基準値【以上】の場合のラベル", value="1", key="lbl_h")
        with col_low: label_low = st.text_input("基準値【未満】の場合のラベル", value="0", key="lbl_l")
        new_col_name = st.text_input("新しく作成するフラグ列の名前", value=f"{bin_col}_Flag", key="bin_new")
        if st.button("フラグを作成して新しい列を追加する", type="primary"):
            val_high = float(label_high) if label_high.replace('.','',1).isdigit() else label_high
            val_low = float(label_low) if label_low.replace('.','',1).isdigit() else label_low
            
            temp_series = pd.to_numeric(df[bin_col], errors='coerce')
            st.session_state.current_df[new_col_name] = np.where(temp_series >= threshold, val_high, val_low)
            st.session_state.action_msg = f"フラグ化完了： 新しい列「{new_col_name}」を追加しました。"
            st.rerun()

    # ==========================================
    # 4. 変数の計算・変換（一括置換）
    # ==========================================
    elif selected_tab == "4. 計算・変換":
        st.markdown("### 変数の計算・変換・クリーニング")
        calc_mode = st.radio("処理メニュー", ["A. 日付差分計算", "B. 四則演算", "C. 日付フォーマット変換", "D. データ型強制変換", "E. 文字列の置換・削除", "F. 全角・半角の統一（表記揺れ修正）"])
        
        if calc_mode.startswith("A"):
            date_end = st.selectbox("終了日", df.columns, key="d_end")
            date_start = st.selectbox("開始日", df.columns, key="d_start")
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
                    if "8桁" in date_format_type: st.session_state.current_df[date_format_new] = pd.to_datetime(df[date_format_col].astype(str), format='%Y%m%d', errors='coerce')
                    else: st.session_state.current_df[date_format_new] = pd.to_datetime(df[date_format_col].astype(str) + '01', format='%Y%m%d', errors='coerce')
                    st.session_state.current_df[date_format_new] = st.session_state.current_df[date_format_new].dt.strftime('%Y-%m-%d')
                    st.session_state.action_msg = f"日付変換完了： 「{date_format_new}」をカレンダー日付に変換しました。"
                    st.rerun()
                except Exception as e: st.error(f"変換エラー: {e}")
        
        # 💡 型変換の「複数選択（一括処理）」対応
        elif calc_mode.startswith("D"):
            type_cols = st.multiselect("型を変換したい列（複数選択可）", df.columns, key="t_cols")
            type_to = st.radio("変換先の型", ["文字列（IDやカテゴリとして扱う）", "数値（計算できるようにする）"])
            if st.button("データ型を強制変換して上書きする", type="primary"):
                if type_cols:
                    try:
                        for col in type_cols:
                            if "文字列" in type_to: 
                                st.session_state.current_df[col] = df[col].astype(str)
                            else: 
                                st.session_state.current_df[col] = pd.to_numeric(df[col], errors='coerce')
                        st.session_state.action_msg = f"型変換完了： {len(type_cols)} 列を変換しました。"
                        st.rerun()
                    except Exception as e: st.error(f"エラー: {e}")
                else:
                    st.warning("処理したい列を1つ以上選択してください。")
                
        elif calc_mode.startswith("E"):
            st.info("データ内にある特定の記号（ハイフンなど）を一括で置換・削除できます。削除する場合は「新しい文字」を空欄にしてください。")
            all_cols = st.checkbox("すべての列を対象にする（一括置換）", value=False)
            if all_cols:
                rep_cols = df.columns.tolist()
            else:
                rep_cols = st.multiselect("処理対象の列を選択（複数選択可）", df.columns, key="rep_cols")
                
            rep_target = st.text_input("置換対象の文字", value="-", key="rep_tgt")
            rep_new = st.text_input("新しい文字（消去する場合は空欄）", key="rep_new")
            
            if st.button("文字の置換・削除を実行して上書きする", type="primary"):
                if rep_target and rep_cols:
                    for col in rep_cols:
                        st.session_state.current_df[col] = df[col].astype(str).str.replace(rep_target, rep_new, regex=False)
                        st.session_state.current_df[col] = st.session_state.current_df[col].replace(['', 'nan', 'None'], np.nan)
                    st.session_state.action_msg = f"置換完了： {len(rep_cols)} 列の『{rep_target}』を変換しました。"
                    st.rerun()
                else:
                    st.warning("置き換えたい列と文字を入力してください。")

        elif calc_mode.startswith("F"):
            st.info("全角の英数字（１２３、ＡＢＣなど）を半角に統一し、突合エラーの原因となる表記揺れを瞬時に修正します。")
            all_zen_cols = st.checkbox("すべての列を対象にする", value=False, key="zen_all")
            if all_zen_cols:
                zen_cols = df.columns.tolist()
            else:
                zen_cols = st.multiselect("処理対象の列を選択（複数選択可）", df.columns, key="zen_cols")
                
            if st.button("全角・半角を統一して上書きする", type="primary"):
                if zen_cols:
                    try:
                        for col in zen_cols:
                            # NFKC正規化で、全角英数字を半角に綺麗に統一
                            st.session_state.current_df[col] = df[col].astype(str).apply(lambda x: unicodedata.normalize('NFKC', x) if x not in ['nan', 'None', ''] else np.nan)
                        st.session_state.action_msg = f"表記揺れ修正完了： {len(zen_cols)} 列の全角・半角を統一しました。"
                        st.rerun()
                    except Exception as e: st.error(f"エラー: {e}")
                else:
                    st.warning("処理したい列を選択してください。")

    # ==========================================
    # 5. 構造変換（Pivot ＆ Melt）
    # ==========================================
    elif selected_tab == "5. 縦横変換":
        st.markdown("### データの縦横変換")
        transform_mode = st.radio("変換の方向", [
            "A. 縦長 ➡ 横長 (Pivot)：IDごとに時間を横に並べる",
            "B. 横長 ➡ 縦長 (Melt)：複数列に分かれた属性を1列に折りたたむ（NDBデータ等で必須）"
        ])

        if transform_mode.startswith("A"):
            col_id = st.selectbox("1. 固体の識別子となる列（IDなど）", df.columns, key="piv_id")
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
                except Exception as e: st.error(f"構造変換に失敗しました。Excelの列名に不備がないかご確認ください。詳細: {e}")
        
        else:
            id_vars = st.multiselect("固定して残す列（都道府県、背景因子など）", df.columns, key="melt_id")
            val_vars = [c for c in df.columns if c not in id_vars]
            var_name = st.text_input("折りたたんだ列名（属性）につける新しい名前", value="属性", key="melt_var")
            val_name = st.text_input("その数値につける新しい名前", value="値", key="melt_val")
            
            if st.button("縦持ちへ変換して上書きする", type="primary"):
                if id_vars:
                    try:
                        df_melted = df.melt(id_vars=id_vars, value_vars=val_vars, var_name=var_name, value_name=val_name)
                        st.session_state.current_df = df_melted
                        st.session_state.action_msg = f"構造変換完了： {len(df_melted)} 行の縦長データに変換しました。"
                        st.rerun()
                    except Exception as e: st.error(f"構造変換に失敗しました。詳細: {e}")
                else:
                    st.warning("固定して残す列を少なくとも1つ選んでください。")

    # ==========================================
    # 6. 突合
    # ==========================================
    elif selected_tab == "6. 突合":
        st.markdown("### 2つのファイルをIDで突合する（横結合）")
        if df_B is not None:
            col_left = st.selectbox("現在のデータ側のID", df.columns, key="join_L")
            col_right = st.selectbox("別ファイル側のID", df_B.columns, key="join_R")
            join_how = st.radio("結合方式", ["左結合（メインデータを残す）", "内部結合（両方に存在するデータのみ）"])
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
        else: st.info("左側のサイドバーから結合用の別ファイルをアップロードしてください。")

    # ==========================================
    # 7. 傾向スコアマッチング（PSM）
    # ==========================================
    elif selected_tab == "7. PSM":
        st.markdown("### 傾向スコアマッチング（1:1 最近傍マッチング）")
        st.info("【重要】介入変数（治療の有無など）は必ず「1 と 0」の数値データで入力されている必要があります。事前にタブ3でフラグ化を完了させておいてください。")
        treat_col = st.selectbox("介入変数（治療の有無: 1 or 0）", [c for c in df.columns if set(df[c].dropna().unique()).issubset({0, 1, 0.0, 1.0, '0', '1'})], key="psm_treat")
        covar_cols = st.multiselect("揃えたい背景因子（共変量: 年齢、数値データなど）", [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c != treat_col], key="psm_cov")
        
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
                    st.session_state.action_msg = f"PSM完了： {int(new_len/2)}組 のペアを作成しました。（全体行数: {old_len} ➡ {new_len}）"
                    st.rerun()
                except Exception as e:
                    st.error(f"統計計算中にエラーが発生しました。データの欠損状態やデータ型をご確認ください。詳細: {e}")
            else:
                st.warning("介入変数と、少なくとも1つの背景因子を選択してください。")

else:
    st.info("左のサイドバーからメインデータ（CSVまたはExcel）をアップロードして開始してください。")
