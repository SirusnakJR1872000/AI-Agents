Drop Netcore engagement exports here as CSV (simulating an S3 landing zone).

Prototype behavior:
- The app reads the *latest modified* CSV in this folder.
- Expected schema matches README.md (event_ts, channel, campaign_id, ...).
