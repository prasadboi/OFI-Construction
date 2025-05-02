# Order Flow Imbalance (OFI) Explained

## 1. What is Order-Flow Imbalance (OFI)?

Order-Flow Imbalance (OFI) measures the net supply–demand pressure in a limit-order book (LOB). It tracks the signed changes in bid and ask sizes across various price levels, capturing whether liquidity is being added or removed and at which side.

### Notation:
#### Symbols
* `i`: instrument index
* `t`: Time bin end point (e.g., 11:54 - 11:55 AM).
* `h` Length of aggregation interval (e.g., 1 min).
* `m`: Depth level (for best bid/ask,  for deeper levels).
* `q`: Denotes the size / total quantity / total volume
* `P`: Denotes the price
* $\text{P}^{i,n}_{m,b}$ = `bid_px_m`
* $\text{P}^{i,n}_{m,a}$ = `ask_px_m`
* $\text{q}^{i,n}_{m,b}$ = `bid_sz_m`
* $\text{q}^{i,n}_{m,a}$ = `ask_sz_m`

#### OFI subscripts
* $\text{OF}_{m,b}^{i,n}$ means means the bid‐side OFI at level m for instrument i on event n.
* $\text{OF}_{m,a}^{i,n}$ is the corresponding ask side OFI

### 1.1. The Limit-Order Book

At any time $t$, an instrument $i$ has:

* **Bid Quotes:** $(P_{m,b}^{i,t}, q_{m,b}^{i,t})$, where $m=0$ represents the best bid.
* **Ask Quotes:** $(P_{m,a}^{i,t}, q_{m,a}^{i,t})$, where $m=0$ represents the best ask.

These quotes update continually as orders arrive, trade, or cancel.

### 1.2. Event-Level Order Flows

For each event $n$ at level $m$, the OFI is computed as:

**Bid-side:**

$$
\text{OF}_{m,b}^{i,n} =
\begin{cases}
+q_{m,b}^{i,n}, & \text{if } P_{m,b}^{i,n}>P_{m,b}^{i,n-1},\\
q_{m,b}^{i,n}-q_{m,b}^{i,n-1}, & \text{if } P_{m,b}^{i,n}=P_{m,b}^{i,n-1},\\
-q_{m,b}^{i,n}, & \text{if } P_{m,b}^{i,n}<P_{m,b}^{i,n-1}.
\end{cases}
$$

**Ask-side:**

$$
\text{OF}_{m,a}^{i,n} =
\begin{cases}
-q_{m,a}^{i,n}, & \text{if } P_{m,a}^{i,n}>P_{m,a}^{i,n-1},\\
q_{m,a}^{i,n}-q_{m,a}^{i,n-1}, & \text{if } P_{m,a}^{i,n}=P_{m,a}^{i,n-1},\\
+q_{m,a}^{i,n}, & \text{if } P_{m,a}^{i,n}<P_{m,a}^{i,n-1}.
\end{cases}
$$

Positive values represent added liquidity at the bid or removed liquidity at the ask, and vice versa.

### 1.3. Best-Level and Multi-Level OFI

Over an interval $(t-h,t]$, OFI is summed across events:

* **Best-Level OFI:**

$\text{OFI}_{0,h}^{i,t} = \sum (\text{OF}_{0,b}^{i,n} - \text{OF}_{0,a}^{i,n})$

* **Multi-Level OFI:**

$\text{OFI}_{m,h}^{i,t} = \sum (\text{OF}_{m,b}^{i,n} - \text{OF}_{m,a}^{i,n})$

### 1.4. Integrated OFI

Due to high correlation among levels, Integrated OFI reduces dimensionality using PCA:

$\text{Integrated OFI}_{h}^{i,t} = \mathbf{w}_1^\top \mathbf{OFI}_h^{i,t}$

where $\mathbf{w}_1$ is the normalized first PCA loading vector.

### 1.5. Cross-Asset OFI

Cross-asset OFI isolates the effect of other assets:

$\text{Cross-Asset OFI}_{h}^{i,t} = \sum_{j\neq i}\text{Integrated OFI}_{h}^{j,t}$

---

## 2. Code Walk-Through

### 2.1. Load Order Book

```python
def load_order_book(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=['ts_event'])
    df.sort_values(['symbol', 'ts_event'], inplace=True)
    return df
```

### 2.2. Compute Event OFIs

```python
def compute_event_ofis(df, levels=10):
    out = []
    for sym, g in df.groupby('symbol'):
        g = g.reset_index(drop=True)
        for m in range(levels):
            bp, bs = g[f'bid_px_{m:02d}'], g[f'bid_sz_{m:02d}']
            ap, asz= g[f'ask_px_{m:02d}'], g[f'ask_sz_{m:02d}']
            d_bp, d_bs = bp.diff().fillna(0), bs.diff().fillna(0)
            d_ap, d_asz= ap.diff().fillna(0), asz.diff().fillna(0)

            ofi_b = np.where(d_bp>0,  bs,
                     np.where(d_bp<0, -bs,
                              d_bs))
            ofi_a = np.where(d_ap>0, -asz,
                     np.where(d_ap<0,  asz,
                              d_asz))

            g[f'ofi_b_{m}'], g[f'ofi_a_{m}'] = ofi_b, ofi_a
        out.append(g)
    return pd.concat(out, ignore_index=True)
```

### 2.3. Aggregate Time Bins

```python
def aggregate_time_bins(df, freq='1T', levels=10):
    df['ts_bin'] = df['ts_event'].dt.floor(freq)
    agg = {}
    for m in range(levels):
        agg[f'ofi_{m}'] = (
          df[f'ofi_b_{m}'] - df[f'ofi_a_{m}']
        ).groupby([df['symbol'], df['ts_bin']]).sum()
    out = pd.DataFrame(agg).reset_index()
    out.rename(columns={'ofi_0':'best_ofi'}, inplace=True)
    return out
```

### 2.4. Compute Integrated OFI

```python
def compute_integrated_ofi(df_ofi, levels=10):
    X = df_ofi[[f'ofi_{m}' for m in range(levels)]].values
    pca = PCA(n_components=1).fit(X)
    w = pca.components_[0]
    w /= np.abs(w).sum()
    df_ofi['int_ofi'] = X.dot(w)
    return df_ofi
```

### 2.5. Compute Cross-Asset OFI

```python
def compute_cross_asset_ofi(df_int):
    total = df_int.groupby('ts_bin')['int_ofi'].transform('sum')
    df_int['cross_asset_ofi'] = total - df_int['int_ofi']
    return df_int
```

---

## 3. Enhancements

* **Depth-Normalization** to reduce intraday liquidity effects.
* **Rolling PCA** to capture shifting market conditions.
* **Elastic Net or Group Lasso** for sparse selection of influential assets.
* **Higher-Frequency Buckets** for better granularity.
* **Non-Linear Models** for capturing complex interactions.