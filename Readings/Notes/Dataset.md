# Dataset

## Timestamps and Sequencing
* **ts_recv**: The UTC timestamp (with nanosecond precision) when your data‐capture system received the message.
* **ts_event**: The UTC timestamp marking when the exchange actually generated the event—i.e. when the book update occurred.
* **ts_in_delta**: A micro‐ or millisecond‐resolution “delta” from some internal clock (often used to debug latency or ordering).
* **sequence**: A strictly increasing integer assigned by the exchange (or feed handler) to ensure you can reconstruct the exact order of messages, even if timestamps collide.

## Update Details
* action - A single letter code for what has happened
  * `A`: Add a new limit order
  * `C`: Change (modify) an existing order’s size
  * `E`: Execute (a trade consuming part or all of an order)
  * `D`: Delete or Cancel an existing order
  * Check dataset to verify these codes
* side - Which side of the book the update refers to
  * `B`: Bid (buy side)
  * `S` or `A`: Ask (sell side), depending on your feed’s conventions.
* depth - Indicates which level in the book the update is targeting
  * `0`: best (inside) bid or ask
  * `1`: second level bid or ask
  * `...`: and so on
* price - The price of the order being added, changed, or executed
* size - The size  (qty) associated with the action:
  * For an Add (`A`), this is the new order’s full size.
  * For a Change (`C`), the new total size at that level.
  * For an Execute (`E`), the executed quantity.
  * For a Delete (`D`), usually the size removed.
* flags - A bit‐mask field carrying extra information (e.g. hidden orders, iceberg indicators, short‐sale flags). The exact meaning depends on the exchange’s specification.

## Full Book Snapshot (Levels 0-9)
After each event you have captured a snapshot of the top 10 levels on bth sides. These columns let you reconstruct the shape of the book at that instant:
For each level `m = 00, 01, …, 09`:
* **bid_px_m, ask_px_m**: The price at the m-th bid and ask level.
* **bid_sz_m, ask_sz_m**: The aggregate size (sum of all resting orders) at that bid or ask level.
* **bid_ct_m, ask_ct_m**: The count of individual orders at that level.

E.g. at level “00” you have the best (inside) bid (bid_px_00, bid_sz_00, bid_ct_00) and best ask (ask_px_00, ask_sz_00, ask_ct_00); at “01” the next best, etc., out to “09.”

### NOTE: Why keep both sizes and counts?
* Size shows total available liquidity.
* Count gives you an idea of order fragmentation (many small orders vs. a few large blocks), which can signal differences in participant behavior.


## Message Metadata
* **rtype**: A numeric code for “record type,” indicating what kind of message this is (e.g. snapshot refresh, L2 update, trade report, etc.).
* **publisher_id**: Identifies which matching engine or data “partition” (e.g. NASDAQ, NYSE, etc.) published this event.
* **instrument_id**: A numeric identifier for the specific contract or ticker in the exchange’s internal nomenclature.
* **symbol**: The human‐readable ticker (e.g. “AAPL”).

## Putting it all together
Each row of the CSV file is therefore:
* A raw message (Add/Change/Exec/Cancel) stamped by both the exchange (ts_event) and your capture system (ts_recv),
* Full depth-10 snapshot of both sides of the book after that message,
* Metadata (sequence, instrument IDs, flags) you need to reliably reassemble market state and calculate derived features like OFI.