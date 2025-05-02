import pandas as pd
import numpy as np
from sklearn.decomposition import PCA
from typing import List

def load_order_book(csv_path: str) -> pd.DataFrame:
    """
    Load the raw ITCH snapshot CSV.
    - Parses timestamps.
    - Sort data by instrument and event-time.
    """
    df = pd.read_csv(csv_path, parse_dates=['ts_event'])
    df.sort_values(['symbol', 'ts_event'], inplace=True)
    return df

def compute_event_ofis(df: pd.DataFrame, levels: int = 10) -> pd.DataFrame:
    """
    For each order-book event (row), compute OFI_b and OFI_a for levels 0..levels-1.
      OFm,b = +q   if price↑; 
            = Δq if price=; 
            = –q if price↓
      
      OFm,a = –q   if ask↑; 
            = Δq if ask=; 
            = +q if ask↓
    Returns same DataFrame with added columns ofi_b_0…ofi_b_9 and ofi_a_0…ofi_a_9.
    """
    out = []
    for sym, g in df.groupby('symbol', as_index=False):
        g = g.reset_index(drop=True)
        # for each level
        for m in range(levels):
            bid_price = g[f'bid_px_{m:02d}']; 
            ask_price = g[f'ask_px_{m:02d}']
            
            bid_size = g[f'bid_sz_{m:02d}']; 
            ask_size = g[f'ask_sz_{m:02d}']
            # price diffs
            bid_price_diff = bid_price.diff().fillna(0)
            bid_size_diff = bid_size.diff().fillna(0)
            ask_price_diff = ask_price.diff().fillna(0)
            ask_size_diff = ask_size.diff().fillna(0)
            # bid OFI
            ofi_b = np.where(bid_price_diff>0,  bid_size,
                     np.where(bid_price_diff<0, -bid_size,
                              bid_size_diff))
            # ask OFI
            ofi_a = np.where(ask_price_diff>0, -ask_size,
                     np.where(ask_price_diff<0,  ask_size,
                              ask_size_diff))
            g[f'ofi_b_{m}'] = ofi_b
            g[f'ofi_a_{m}'] = ofi_a
        out.append(g)
    return pd.concat(out, ignore_index=True)

def aggregate_time_bins(df: pd.DataFrame, freq: str = '1min', levels: int = 10) -> pd.DataFrame:
    """
    Collapse event-level OFIs into fixed time bins (e.g. '1min' = 1 minute):
      - Best_Level_OFI = sum(ofi_b_0 - ofi_a_0)
      - Multi_Level_OFI_m = sum(ofi_b_m - ofi_a_m) for m=0..levels-1
    Returns a DataFrame indexed by [symbol, ts_bin] with columns:
      best_ofi, ofi_0, …, ofi_{levels-1}
    """
    df['ts_bin'] = df['ts_event'].dt.floor(freq)
    agg = {}
    for m in range(levels):
        agg[f'ofi_{m}'] = (df[f'ofi_b_{m}'] - df[f'ofi_a_{m}']).groupby([df['symbol'], df['ts_bin']]).sum()
    # best-level
    out = pd.DataFrame(agg).reset_index()
    print(out.info())
    return out

def compute_best_ofi(df: pd.DataFrame, levels = 10) -> pd.DataFrame:
    """
    For each symbol and timestamp, compute best_ofi as:
      best_ofi = ofi_0 - ofi_0
    """
    if levels == 0:
        raise ValueError("levels must be > 0")
    df['best_ofi'] = df['ofi_0']
    return df

def compute_multi_level_ofi(df: pd.DataFrame, levels: int = 10) -> pd.DataFrame:
        """
        For each symbol and timestamp, compute multi_level_ofi as:
            multi_level_ofi = sum(ofi_0 - ofi_0) + sum(ofi_1 - ofi_1) + ... + sum(ofi_{levels-1} - ofi_{levels-1})
        """
        ofi_cols = [f'ofi_{m}' for m in range(levels)]
        df[f'{levels}_level_ofi'] = df[ofi_cols].sum(axis=1) # multi level OFI
        return df

def compute_integrated_ofi(df_ofi: pd.DataFrame, levels: int = 10) -> pd.DataFrame:
    """
    Given multi-level OFIs (columns ofi_0…ofi_{levels-1}), run a PCA
    on historical data to get the first principal component w (explains >89% :contentReference[oaicite:0]{index=0}:contentReference[oaicite:1]{index=1}).
    Then for each row:
      integrated_ofi = (w·[ofi_0…ofi_{L-1}]) / sum(|w|)
    Returns same DataFrame with an added column 'int_ofi'.
    """
    X = df_ofi[[f'ofi_{m}' for m in range(levels)]].values
    pca = PCA(n_components=1)
    pca.fit(X)
    w = pca.components_[0]
    w = w / np.abs(w).sum()
    df_ofi[f'integrated_{levels}_level_ofi'] = X.dot(w)
    return df_ofi

def compute_cross_asset_ofi(df_int: pd.DataFrame, levels = 10) -> pd.DataFrame:
    """
    For each timestamp and symbol, compute cross_asset_ofi as:
      total_int_ofi_at_t - own_int_ofi
    """
    total = df_int.groupby('ts_bin')[f'integrated_{levels}_level_ofi'].transform('sum')
    df_int[f'cross_asset_{levels}_level_ofi'] = total - df_int[f'integrated_{levels}_level_ofi']
    return df_int

if __name__ == "__main__":
    raw = load_order_book("/home/arjun-prasad/ARJUN/Work/Projects/OFI-Construction/Data/raw_lob.csv")
    final = (
        compute_cross_asset_ofi(
            compute_integrated_ofi(
                compute_multi_level_ofi(
                    compute_best_ofi(
                        aggregate_time_bins(
                            compute_event_ofis(raw, levels=10),
                            freq='1min', 
                            levels=10
                        )
                    ),
                    levels=10
                ),
                levels=10
            ),
            levels=10
        )
    )
    # final now has: ts_bin, symbol, best_ofi, ofi_0…ofi_9, multi_level_ofi, int_ofi, cross_asset_ofi
    final.to_csv("/home/arjun-prasad/ARJUN/Work/Projects/OFI-Construction/Data/processed_lob.csv", index=False)
    print(final.head(30))
