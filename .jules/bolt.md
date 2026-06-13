## 2024-05-18 - Multiple generator expressions bottleneck in vector ops
**Learning:** Using multiple generator expressions inside a math-heavy loop (like vector dot products or sum of squares) creates significant overhead due to object allocation and function call overhead per element in Python. This limits performance significantly in linear scan vector databases.
**Action:** Unroll the multiple generator loops into a single linear loop to calculate all required scalars (e.g. dot product, sum of squares) in one pass for a substantial speedup (~35%).
