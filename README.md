# OFI-Construction Data Pipeline

This module processes limit order book (LOB) data to compute various Order Flow Imbalance (OFI) features for market microstructure research and modeling, following the methodology of [Benzaquen et al., 2023](#references).

## Overview

The pipeline:

1. **Loads raw LOB data** from CSV.
2. **Computes event-level OFI** for each price level.
3. **Aggregates OFI into time bins** (e.g., 1-minute), with both normalized and raw OFI.
4. **Computes best-level, multi-level, and integrated OFI** features.
5. **Computes cross-asset OFI** (if multiple symbols are present).

## Usage

```sh
python Code/data.py
```

This will read `Data/raw_lob.csv`, process the data, and write the results to `Data/processed_lob.csv`.

---

## Column Descriptions

### Raw LOB Columns

| Column         | Description                                                        |
|----------------|--------------------------------------------------------------------|
| ts_recv        | Timestamp when the message was received                            |
| ts_event       | Timestamp when the event occurred                                  |
| rtype          | Record type (e.g., 10 for order book snapshot)                     |
| publisher_id   | Data publisher identifier                                          |
| instrument_id  | Instrument identifier                                              |
| action         | Event action (e.g., A=Add, C=Cancel)                               |
| side           | Order side (B=Bid, A=Ask)                                          |
| depth          | Book depth for this event (0=top of book, 1=second level, etc.)    |
| price          | Price for this event                                               |
| size           | Size (quantity) for this event                                     |
| flags          | Event flags                                                        |
| ts_in_delta    | Internal timestamp delta                                           |
| sequence       | Sequence number                                                    |
| bid_px_00...09 | Bid price at levels 0–9                                            |
| ask_px_00...09 | Ask price at levels 0–9                                            |
| bid_sz_00...09 | Bid size at levels 0–9                                             |
| ask_sz_00...09 | Ask size at levels 0–9                                             |
| bid_ct_00...09 | Number of orders at bid levels 0–9                                 |
| ask_ct_00...09 | Number of orders at ask levels 0–9                                 |
| symbol         | Ticker symbol (e.g., AAPL)                                         |

### Feature Columns (after processing)

| Column                       | Description                                                                 |
|------------------------------|-----------------------------------------------------------------------------|
| ts_bin                       | Timestamp bin (start of each time interval, e.g., 1-minute)                 |
| symbol                       | Ticker symbol                                                               |
| best_ofi                     | Normalized OFI at the top of the book (level 0)                             |
| ofi_1 ... ofi_{N-1}          | Normalized OFI at each book level (1–N-1)                                    |
| raw_ofi_0 ... raw_ofi_{N-1}  | Raw (non-normalized) OFI at each book level (0–N-1)                         |
| norm_ofi_0 ... norm_ofi_{N-1}| Normalized OFI at each book level (0–N-1)                                   |
| multi_level_ofi              | List of normalized OFIs for all levels (see below)                          |
| integrated_{N}_level_ofi     | Integrated OFI (first principal component via PCA, all N levels)             |
| cross_asset_best_ofi         | Cross-asset OFI at best level (see below)                                   |
| cross_asset_integrated_ofi   | Cross-asset integrated OFI (see below)                                      |

---

## Timestamp Binning

- **Binning:** All events are grouped into fixed time intervals (default: 1 minute) using `ts_event`.
- **Column:** `ts_bin` is the floored timestamp (e.g., `2024-10-21 11:54:00` for all events in that minute).
- **Purpose:** This allows aggregation of high-frequency events into manageable time slices for analysis.

---

## OFI Feature Definitions

- **OFI at level m:** Measures net order flow at price level m, using changes in price and size.
- **best_ofi:** Normalized OFI at the top of the book (level 0).
- **multi_level_ofi:** List of normalized OFIs for all levels, stored as a column for compatibility with the referenced research paper.
- **integrated_{N}_level_ofi:** First principal component of multi-level OFI (captures most variance).
- **cross_asset_best_ofi:** For each time bin, the sum of best-level OFI across all symbols (weighted by betas) minus the symbol’s own value.
- **cross_asset_integrated_ofi:** For each time bin, the sum of integrated OFI across all symbols (weighted by betas) minus the symbol’s own value.

---

## Final Dataset Structure

| ts_bin              | symbol | best_ofi | multi_level_ofi | integrated_{N}_level_ofi | cross_asset_best_ofi | cross_asset_integrated_ofi |
|---------------------|--------|----------|-----------------|-------------------------|----------------------|---------------------------|
| ...                 | ...    | ...      | ...             | ...                     | ...                  | ...                       |

---

## Function Descriptions

- **load_order_book:** Loads and sorts the raw LOB data.
- **compute_event_order_flows:** Computes event-level bid/ask OFI for each level.
- **aggregate_time_bins:** Aggregates event-level OFIs into time bins, computes both raw and normalized OFI for each level.
- **compute_best_ofi:** Adds a `best_ofi` column (normalized OFI at level 0).
- **compute_multi_level_ofi:** Packs normalized OFIs for all levels into a list column (`multi_level_ofi`), matching the structure in the referenced research.
- **compute_integrated_ofi:** Applies PCA to the multi-level OFI vectors and computes the integrated OFI as the projection onto the first principal component.
- **process_betas:** Cleans and aligns the cross-impact beta matrices.
- **compute_cross_asset_ofi:** Computes cross-asset OFI features using the provided beta matrices.

---

## Notes

- **Relative Paths:** Data paths are relative to the script location for portability.
- **Cross-Asset OFI:** Will be zero if only one symbol is present in the data.
- **Order Count Columns:** `bid_ct_*` and `ask_ct_*` are not used in OFI calculations, but may be useful for advanced analysis.

---

## References

- Rama Cont, Mihai Cucuringu & Chao Zhang (2023). [Cross-impact of order flow imbalance in equity markets, Quantitative Finance, 23:10, 1373-1393, DOI: 10.1080/14697688.2023.2236159](https://doi.org/10.1080/14697688.2023.2236159).

---