Drop transaction exports here as CSV (simulating an S3 landing zone).

Prototype behavior:
- The app reads the *latest modified* CSV in this folder.
- Expected schema matches README.md (txn_ts, order_id, revenue, product, ...).
