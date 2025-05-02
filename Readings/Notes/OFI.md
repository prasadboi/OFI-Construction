# Order Flow Imbalance (OFI) Explained

## 1. What is Order-Flow Imbalance (OFI)?

Order-Flow Imbalance (OFI) measures the net supply–demand pressure in a limit-order book (LOB). It tracks the signed changes in bid and ask sizes across various price levels, capturing whether liquidity is being added or removed and at which side.

### Notation:

#### Symbols

* `i`: instrument index
* `t`: Time bin end point (e.g., 11:54 - 11:55 AM).
* `h`: Length of aggregation interval (e.g., 1 min).
* `m`: Depth level (for best bid/ask and deeper levels).
* `q`: Size / quantity / volume
* `P`: Price
* \$P^{i,n}\_{m,b}\$: Bid price at level m  
* \$P^{i,n}\_{m,a}\$: Ask price at level m
* \$q^{i,n}\_{m,b}\$: Bid size at level m
* \$q^{i,n}\_{m,a}\$: Ask size at level m

#### OFI subscripts

* \$\text{OF}\_{m,b}^{i,n}\$: bid‐side OFI at level m, instrument i, event n
* \$\text{OF}\_{m,a}^{i,n}\$: ask-side OFI

### 1.1. The Limit-Order Book

At any time $t$, an instrument $i$ has:

- **Bid Quotes**: $(P_{m,b}^{i,t}, q_{m,b}^{i,t})$, where $m=0$ is the best bid.
- **Ask Quotes**: $(P_{m,a}^{i,t}, q_{m,a}^{i,t})$, where $m=0$ is the best ask.

These quotes update continually as orders arrive, trade, or cancel.

### 1.2. Event-Level Order Flows

For each event $n$ at level $m$, OFI is computed as follows.

**Bid-side:**

$$
\text{OF}_{m,b}^{i,n} =
\begin{cases}
  +q_{m,b}^{i,n}, & \text{if } P_{m,b}^{i,n} > P_{m,b}^{i,n-1} \\\\
  q_{m,b}^{i,n}-q_{m,b}^{i,n-1}, & \text{if } P_{m,b}^{i,n} = P_{m,b}^{i,n-1} \\\\
  -q_{m,b}^{i,n}, & \text{if } P_{m,b}^{i,n} < P_{m,b}^{i,n-1}
\end{cases}
$$

**Ask-side:**

$$
\text{OF}_{m,a}^{i,n} =
\begin{cases}
  -q_{m,a}^{i,n}, & \text{if } P_{m,a}^{i,n} > P_{m,a}^{i,n-1} \\\\
  q_{m,a}^{i,n}-q_{m,a}^{i,n-1}, & \text{if } P_{m,a}^{i,n} = P_{m,a}^{i,n-1} \\\\
  +q_{m,a}^{i,n}, & \text{if } P_{m,a}^{i,n} < P_{m,a}^{i,n-1}
\end{cases}
$$

**Order Flow Imbalance:**

$$
\text{OFI}_{i,t}^{m,h} := \sum_{n = N(t - h) + 1}^{N(t)} \left(\text{OF}_{m,b}^{i,n} - \text{OF}_{m,a}^{i,n}\right)
$$

Positive values indicate added liquidity at the bid or removed liquidity at the ask, and vice versa.

### 1.3. Best-Level and Multi-Level OFI

Summed across events within an interval $(t-h,t]$:

**Best-Level OFI:**

$$
\text{OFI}_{0,h}^{i,t} = \sum_{n} \left(\text{OF}_{0,b}^{i,n} - \text{OF}_{0,a}^{i,n}\right)
$$

**Multi-Level OFI:**

$$
\text{OFI}_{m,h}^{i,t} = \sum_{n} \left(\text{OF}_{m,b}^{i,n} - \text{OF}_{m,a}^{i,n}\right)
$$

### 1.4. Depth-Normalized OFI

To account for liquidity, OFI is normalized by the average book depth ($Q^{M,h}_{i,t}$):

$$
\text{norm\_OFI}_{m,h}^{i,t} = \frac{\text{OFI}_{m,h}^{i,t}}{Q^{M,h}_{i,t}}
$$

where $Q^{M,h}_{i,t}$ is the average total depth across all levels and events in the bin.

### 1.5. Integrated OFI

To reduce dimensionality due to high correlation among levels, PCA is used:

$$
\text{Integrated OFI}_{h}^{i,t} = \mathbf{w}_1^\top \mathbf{norm\_OFI}_h^{i,t}
$$

where $\mathbf{w}_1$ is the normalized first PCA loading vector.

### 1.6. Cross-Asset OFI

To isolate effects from other assets:

$$
\text{Cross-Asset OFI}_{h}^{i,t} = \sum_{j\neq i}\beta_{ij}\text{Integrated OFI}_{h}^{j,t}
$$

---

## References

* Rama Cont, Mihai Cucuringu & Chao Zhang (2023). [Cross-impact of order flow imbalance in equity markets, Quantitative Finance, 23:10, 1373-1393, DOI: 10.1080/14697688.2023.2236159](https://doi.org/10.1080/14697688.2023.2236159).

---
