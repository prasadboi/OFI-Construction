import pandas as pd
import numpy as np
from sklearn.decomposition import PCA
from typing import List

def load_order_book(csv_path: str) -> pd.DataFrame:
    """
    Load the raw ITCH snapshot CSV.
    - Parses timestamps.
    - Sort data by instrument and event-time.
    - Returns sorted non-empty Dataframe.
    """
    df = pd.read_csv(csv_path, parse_dates=["ts_event"])
    df.sort_values(["symbol", "ts_event"], inplace=True)
    return df


def compute_event_order_flows(df: pd.DataFrame, levels: int = 10) -> pd.DataFrame:
    """
    For each order-book event (row), computes OFI_b and OFI_a for levels 0..levels-1.
    Returns same DataFrame with added columns ofi_b_0…ofi_b_9 and ofi_a_0…ofi_a_9.
    """
    out = []
    for sym, g in df.groupby("symbol", as_index=False):
        g = g.reset_index(drop=True)
        # for each level
        for m in range(levels):
            # prices
            bid_price = g[f"bid_px_{m:02d}"]
            ask_price = g[f"ask_px_{m:02d}"]
            # sizes
            bid_size = g[f"bid_sz_{m:02d}"]
            ask_size = g[f"ask_sz_{m:02d}"]

            # price differences
            bid_price_diff = bid_price.diff().fillna(0)
            ask_price_diff = ask_price.diff().fillna(0)
            # size differences
            bid_size_diff = bid_size.diff().fillna(0)
            ask_size_diff = ask_size.diff().fillna(0)

            # bid OFI
            OF_b = np.where(
                bid_price_diff > 0,
                bid_size,
                np.where(bid_price_diff < 0, -bid_size, bid_size_diff),
            )
            # ask Order Flow
            OF_a = np.where(
                ask_price_diff > 0,
                -ask_size,
                np.where(ask_price_diff < 0, ask_size, ask_size_diff),
            )
            g[f"OF_b_{m}"] = OF_b
            g[f"OF_a_{m}"] = OF_a
        out.append(g)
    return pd.concat(out, ignore_index=True)

def aggregate_time_bins(df: pd.DataFrame, freq: str = '1min', levels: int = 10) -> pd.DataFrame:
    """
    Collapse event-level OFs into fixed time bins and then normalize
    each level-m OFI by the average book depth Q^{M,h}_{i,t}, per (3) in the paper.
    Returns a DataFrame with columns:
        best_ofi, ofi_1…ofi_{levels-1}, norm_ofi_0…norm_ofi_{levels-1}
    where:
        raw_ofi_m  = sum(OF_b_m - OF_a_m)
        norm_ofi_m = raw_ofi_m / Q
    """
    df = df.copy()
    df['ts_bin'] = df['ts_event'].dt.floor(freq)

    records = []
    for (symbol, ts_bin), g in df.groupby(['symbol','ts_bin'], as_index=False):
        N = len(g)
        if N == 0:
            continue

        raw_ofis = []
        total_depth = 0.0
        # levels 0 .. levels-1
        for m in range(levels):
            # 1) sum the raw OF at this level
            raw_m = (g[f'OF_b_{m}'] - g[f'OF_a_{m}']).sum()
            raw_ofis.append(raw_m)

            # 2) sum the snapshot depths (two‐digit zero‐padded columns)
            total_depth += (
                g[f'bid_sz_{m:02d}'].sum()
                + g[f'ask_sz_{m:02d}'].sum()
            )

        # 3) depth normalizer Q
        Q = total_depth / (2 * N * levels) if N>0 else np.nan

        # 4) normalize each raw ofi
        norm_ofis = [val / Q if Q and Q>0 else np.nan for val in raw_ofis]

        rec = {'symbol': symbol, 'ts_bin': ts_bin}
        for m, (raw_v, norm_v) in enumerate(zip(raw_ofis, norm_ofis)):
            rec[f'ofi_{m}']      = raw_v
            rec[f'norm_ofi_{m}'] = norm_v
        records.append(rec)

    out = pd.DataFrame.from_records(records)
    # rename level-0
    # out = out.rename(columns={'ofi_0':'best_ofi', 'norm_ofi_0':'norm_best_ofi'})
    return out


def compute_best_ofi(df: pd.DataFrame, levels=10) -> pd.DataFrame:
    """
    For each symbol and timestamp, compute best_ofi as:
      best_ofi = ofi_0
    Returns the same DataFrame with an added column 'best_ofi'.
    """
    if levels == 0:
        raise ValueError("levels must be > 0")
    df["best_ofi"] = df["ofi_0"]
    return df

def compute_multi_level_ofi(
    df: pd.DataFrame,
    levels: int = 10
) -> pd.DataFrame:
    """
    get the list of the normalized OFIs and put them in a new column 'multi_level_ofi' of the DataFrame.
    """
    df = df.copy()
    cols = [f'norm_ofi_{m}' for m in range(levels)]
    df[f'multi_level_ofi'] = df[cols].values.tolist()
    return df[['symbol', 'ts_bin', f'multi_level_ofi', 'best_ofi']]

def compute_integrated_ofi(
    df: pd.DataFrame,
    levels: int = 10
) -> pd.DataFrame:
    """
    - Stack multi_level_ofi into an (N × M) matrix X
    - Fit PCA(n_components=1) to X
    - Normalize the loading w so sum(|w|)=1
    - Compute integrated_{M}_level_ofi = X.dot(w)
    """
    df = df.copy()
    X = np.vstack(df[f'multi_level_ofi'].values)
    M = X.shape[1]

    pca = PCA(n_components=1)
    pca.fit(X)
    w_raw = pca.components_[0]          # shape (M,)
    w = w_raw / np.abs(w_raw).sum()

    col_name = f"integrated_{M}_level_ofi"
    df[col_name] = X.dot(w)
    
    return df

def compute_cross_asset_ofi(
    df: pd.DataFrame,
    betas: pd.DataFrame,
    ofi_col: str,
    cross_col: str = None
) -> pd.DataFrame:
    """
    Compute cross‐asset OFI contributions for each symbol and time‐bin.
    """
    if cross_col is None:
        cross_col = f"cross_asset_{ofi_col}"

    wide = df.pivot(index='ts_bin', columns='symbol', values=ofi_col).fillna(0)
    wide = wide.reindex(columns=betas.columns, fill_value=0)

    cross_wide = wide.dot(betas.T)

    cross_long = (
        cross_wide
        .stack()
        .reset_index(name=cross_col)
        .rename(columns={'level_1':'symbol'})
    )
    # cross_long has columns ['ts_bin','symbol', cross_col]
    out = df.merge(cross_long, on=['ts_bin','symbol'], how='left')
    return out

import pandas as pd

def process_betas(
    betas: pd.DataFrame,
    symbols: pd.Index,
    zero_diagonal: bool = True,
    fill_value: float = 0.0
) -> pd.DataFrame:
    """
    Align and clean a coefficient matrix for cross‐impact.
    """
    if not isinstance(betas, pd.DataFrame):
        raise ValueError("`betas` must be a pandas DataFrame")

    symbols = pd.Index(symbols)
    common = symbols.intersection(betas.index).intersection(betas.columns)

    dropped_from_df = set(symbols) - set(common)
    dropped_from_betas = (set(betas.index) | set(betas.columns)) - set(common)

    if dropped_from_df:
        print(f"Warning: These symbols are in your data but missing from betas: {dropped_from_df}")
    if dropped_from_betas:
        print(f"Warning: These symbols are in betas but not in your data: {dropped_from_betas}")
    if common.empty:
        raise ValueError("No overlapping symbols between `betas` and your data.")

    cleaned = betas.reindex(index=common, columns=common, fill_value=fill_value)

    if zero_diagonal:
        for sym in common:
            cleaned.at[sym, sym] = 0.0

    return cleaned

if __name__ == "__main__":
    import numpy as np
    import pandas as pd

    levels = 10
    freq   = "1min"

    # 1) Load raw LOB
    df = load_order_book("../Data/raw_lob.csv")
    print(f"After load_order_book: {df.shape[0]} rows")

    # 2) Compute event-level OFs
    df = compute_event_order_flows(df, levels=levels)
    print(f"After compute_event_order_flows: {df.shape[0]} rows")

    # 3) Aggregate into time bins
    df = aggregate_time_bins(df, freq=freq, levels=levels)
    print(f"After aggregate_time_bins: {df.shape[0]} rows")

    # 4) Best-level OFI
    df = compute_best_ofi(df, levels=levels)
    print(f"After compute_best_ofi: {df.shape[0]} rows")

    # 5) Pack multi-level OFI
    df = compute_multi_level_ofi(df, levels=levels)
    print(f"After compute_multi_level_ofi: {df.shape[0]} rows")

    # 6) Integrated OFI
    df = compute_integrated_ofi(df, levels=levels)
    print(f"After compute_integrated_ofi: {df.shape[0]} rows")

    # 7) Build toy beta matrices
    symbols = df["symbol"].unique().tolist()
    betas_best_example = pd.DataFrame(0.01, index=symbols, columns=symbols)
    np.fill_diagonal(betas_best_example.values, 0.0)
    betas_int_example = pd.DataFrame(0.02, index=symbols, columns=symbols)
    np.fill_diagonal(betas_int_example.values, 0.0)

    # 8) Clean & align betas
    betas_best = process_betas(betas_best_example, symbols)
    betas_int  = process_betas(betas_int_example,  symbols)
    print(f"Beta matrices prepared for {len(symbols)} symbols")

    # 9) Cross-asset best-level
    df = compute_cross_asset_ofi(
        df, betas_best,
        ofi_col='best_ofi',
        cross_col='cross_asset_best_ofi'
    )
    print(f"After cross-asset best: {df.shape[0]} rows")

    # 10) Cross-asset integrated
    int_col = f"integrated_{levels}_level_ofi"
    df = compute_cross_asset_ofi(
        df, betas_int,
        ofi_col=int_col,
        cross_col='cross_asset_integrated_ofi'
    )
    print(f"After cross-asset integrated: {df.shape[0]} rows")

    # 11) Final selection & save
    output_cols = [
      'symbol', 'ts_bin',
      'best_ofi',
      'multi_level_ofi',
      int_col,
      'cross_asset_best_ofi',
      'cross_asset_integrated_ofi'
    ]
    df[output_cols].to_csv("../Data/processed_lob.csv", index=False)
    print("Final head:")
    print(df[output_cols].head(10))
