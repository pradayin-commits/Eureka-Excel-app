
import io
import hashlib
from decimal import Decimal, InvalidOperation, getcontext
import pandas as pd
import streamlit as st

st.set_page_config(page_title="EUREKA — Data Integrity Report Tool (Cloud)", page_icon="✅", layout="wide")

BOSCH_RED = "#E20017"

st.markdown(f"""
    <style>
    .eureka-title {{ font-size: 28px; font-weight: 800; color:{BOSCH_RED}; }}
    .eureka-sub {{ opacity:0.8; }}
    .stDownloadButton>button {{ border-radius: 8px; padding: 8px 14px; }}
    </style>
""", unsafe_allow_html=True)

col_logo, col_title = st.columns([1,5])
with col_logo:
    st.image("E.png", width=100, caption=None, use_column_width=False) if "E.png" in st.session_state.get("assets", []) else st.write("")
with col_title:
    st.markdown('<div class="eureka-title">EUREKA — Data Integrity Report Tool (Cloud)</div>', unsafe_allow_html=True)
    st.markdown('<div class="eureka-sub">Compare two CSV files, see differences, and export a report — all in your browser.</div>', unsafe_allow_html=True)

st.sidebar.header("Options")
compare_all_decimals = st.sidebar.checkbox("Strict decimal comparison (do not ignore trailing zeros)", value=False)
case_insensitive = st.sidebar.checkbox("Case-insensitive string compare", value=True)
drop_blank_rows = st.sidebar.checkbox("Drop trailing blank rows", value=True)
show_samples = st.sidebar.checkbox("Show sample rows of each diff", value=True)
key_columns = st.sidebar.text_input("Key columns (optional, comma-separated)",
                                    help="If provided, we will align rows by these columns; otherwise use full-row hash.")

left = st.file_uploader("Upload Source CSV (Left)", type=["csv"])
right = st.file_uploader("Upload Target CSV (Right)", type=["csv"])

def _drop_trailing_blank_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    mask_nonblank = ~(df.isna() | (df.astype(str).str.strip() == "")).all(axis=1)
    if not mask_nonblank.any():
        return df.iloc[0:0]
    last_idx = mask_nonblank[::-1].idxmax()
    return df.loc[:last_idx]

def _normalize_decimal(val: str, strict: bool) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if s == "":
        return ""
    try:
        if strict:
            # keep exact string
            return s
        # ignore trailing zeros: normalize via Decimal.quantize without exponent
        d = Decimal(s)
        # normalize to remove trailing zeros
        n = d.normalize()
        # Convert scientific notation to plain string
        return format(n, 'f').rstrip('0').rstrip('.') if '.' in format(n, 'f') else format(n, 'f')
    except InvalidOperation:
        return s

def _prep_df(df: pd.DataFrame) -> pd.DataFrame:
    # Cast to string for stable hashing/compare
    out = df.copy()
    for c in out.columns:
        if out[c].dtype == "float64" or out[c].dtype == "int64":
            out[c] = out[c].astype(str)
        else:
            out[c] = out[c].astype(str)
        if not compare_all_decimals:
            # try to normalize decimals
            out[c] = out[c].map(lambda x: _normalize_decimal(x, strict=False))
        if case_insensitive:
            out[c] = out[c].str.replace("\r\n","\n").str.strip().str.lower()
        else:
            out[c] = out[c].str.replace("\r\n","\n").str.strip()
    return out

def _hash_row(row: pd.Series) -> str:
    # stable hash of concatenated values
    m = hashlib.sha256()
    m.update(("||".join(map(str, row.values))).encode("utf-8"))
    return m.hexdigest()

def compare_frames(dfL: pd.DataFrame, dfR: pd.DataFrame, keys=None):
    report = {}
    # Shapes / columns
    report["left_rows"] = len(dfL)
    report["right_rows"] = len(dfR)
    report["left_cols"] = list(dfL.columns)
    report["right_cols"] = list(dfR.columns)
    report["missing_columns_in_right"] = [c for c in dfL.columns if c not in dfR.columns]
    report["new_columns_in_right"] = [c for c in dfR.columns if c not in dfL.columns]

    # Align on keys or full-row hash
    Lp = _prep_df(dfL)
    Rp = _prep_df(dfR)

    if keys:
        k = [c.strip() for c in keys if c.strip() in Lp.columns and c.strip() in Rp.columns]
        if k:
            Lp["_key"] = Lp[k].astype(str).agg("||".join, axis=1)
            Rp["_key"] = Rp[k].astype(str).agg("||".join, axis=1)
        else:
            keys = None

    if not keys:
        Lp["_key"] = Lp.apply(_hash_row, axis=1)
        Rp["_key"] = Rp.apply(_hash_row, axis=1)

    Lp["_source"] = "left"
    Rp["_source"] = "right"

    # Presence comparison
    L_keys = set(Lp["_key"])
    R_keys = set(Rp["_key"])
    only_left_keys = L_keys - R_keys
    only_right_keys = R_keys - L_keys
    common_keys = L_keys & R_keys

    only_left = Lp[Lp["_key"].isin(only_left_keys)].drop(columns=["_key","_source"])
    only_right = Rp[Rp["_key"].isin(only_right_keys)].drop(columns=["_key","_source"])

    report["only_left_count"] = len(only_left)
    report["only_right_count"] = len(only_right)

    # For common keys, compare value-level diffs (only when keys provided; otherwise identical rows by hash)
    cell_diffs = None
    if keys:
        l_common = Lp[Lp["_key"].isin(common_keys)].set_index("_key")
        r_common = Rp[Rp["_key"].isin(common_keys)].set_index("_key")
        shared_cols = [c for c in l_common.columns if c not in ("_source",)]
        diffs = []
        for key in common_keys:
            lv = l_common.loc[key]
            rv = r_common.loc[key]
            for c in shared_cols:
                if c == "_source": 
                    continue
                if lv[c] != rv[c]:
                    diffs.append({"_key": key, "column": c, "left": lv[c], "right": rv[c]})
        cell_diffs = pd.DataFrame(diffs) if diffs else pd.DataFrame(columns=["_key","column","left","right"])
        report["cell_diff_count"] = len(cell_diffs)
    else:
        report["cell_diff_count"] = 0

    return report, only_left, only_right, cell_diffs

if left and right:
    try:
        dfL = pd.read_csv(left, dtype=str, keep_default_na=False)
        dfR = pd.read_csv(right, dtype=str, keep_default_na=False)
        if drop_blank_rows:
            dfL = _drop_trailing_blank_rows(dfL)
            dfR = _drop_trailing_blank_rows(dfR)

        keys = [k.strip() for k in key_columns.split(",")] if key_columns.strip() else None
        report, only_left, only_right, cell_diffs = compare_frames(dfL, dfR, keys)

        st.success("Comparison complete.")

        # Summary cards
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Left rows", f"{report['left_rows']:,}")
        c2.metric("Right rows", f"{report['right_rows']:,}")
        c3.metric("Only-in-Left", f"{report['only_left_count']:,}")
        c4.metric("Only-in-Right", f"{report['only_right_count']:,}")

        st.subheader("Column differences")
        col1, col2 = st.columns(2)
        col1.write(pd.DataFrame({"Missing in Right": report["missing_columns_in_right"]}))
        col2.write(pd.DataFrame({"New in Right": report["new_columns_in_right"]}))

        if show_samples:
            st.subheader("Only in Left (sample)")
            st.dataframe(only_left.head(50))
            st.subheader("Only in Right (sample)")
            st.dataframe(only_right.head(50))

        if report["cell_diff_count"] and cell_diffs is not None:
            st.subheader("Cell-level differences (based on key columns)")
            st.dataframe(cell_diffs.head(200))

        # Build downloadable Excel report
        def build_excel():
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as xw:
                pd.DataFrame({
                    "left_rows":[report["left_rows"]],
                    "right_rows":[report["right_rows"]],
                    "only_left_count":[report["only_left_count"]],
                    "only_right_count":[report["only_right_count"]],
                    "cell_diff_count":[report["cell_diff_count"]]
                }).to_excel(xw, index=False, sheet_name="Summary")
                pd.DataFrame({"Missing in Right": report["missing_columns_in_right"]}).to_excel(xw, index=False, sheet_name="MissingColumnsInRight")
                pd.DataFrame({"New in Right": report["new_columns_in_right"]}).to_excel(xw, index=False, sheet_name="NewColumnsInRight")
                only_left.to_excel(xw, index=False, sheet_name="OnlyInLeft")
                only_right.to_excel(xw, index=False, sheet_name="OnlyInRight")
                if report["cell_diff_count"] and cell_diffs is not None:
                    cell_diffs.to_excel(xw, index=False, sheet_name="CellDiffs")
            out.seek(0)
            return out

        xls_bytes = build_excel()
        st.download_button("Download Excel Report", data=xls_bytes, file_name="EUREKA_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Upload both Source and Target CSV files to begin.")
