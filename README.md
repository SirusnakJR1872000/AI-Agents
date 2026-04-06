# Campaign Attribution + Intelligence Prototype

This is a lightweight **prototype** of the combined flow:

- **Campaign Attribution (Core)**: ingest engagement + transactions → identity stitching → attribution window → direct/indirect mapping → outputs
- **Campaign Intelligence (Insights)**: KPIs + trends + creative/frequency/segment views → human review/approval → executive + ops deliverables

## Run locally (Windows / PowerShell)

From this folder:

```bash
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Data inputs

You can ingest data via **connectors** (prototype-simulated) or manual upload:

- **Sample data (built-in)**
- **Manual upload (CSV)**
- **SFMC → SFTP connector (simulated as local folder)**: drops land in `connectors/sfmc_sftp/...`
- **Netcore → S3 connector (simulated as local folder)**: drops land in `connectors/netcore_s3/...`

Expected columns:

### Engagement events
- `event_ts` (datetime)
- `channel` (Email/SMS/WhatsApp/Push/RCS/WebPopup)
- `campaign_id`, `campaign_name`, `campaign_type`
- `user_id` (optional), `email` (optional), `phone` (optional)
- `engagement_type` (Click/Open/Delivered/Read/etc.)
- `target_product` (optional)
- `lob`, `category`, `brand` (optional)
- `creative_id` (optional), `cta` (optional), `language` (optional)

### Transactions / conversions
- `txn_ts` (datetime)
- `order_id`
- `revenue`
- `user_id` (optional), `email` (optional), `phone` (optional)
- `product`, `lob`, `category`, `brand`

### Identity map (optional)
- `user_id`
- `email`
- `phone`

If you don’t provide an identity map, the prototype will do simple stitching using available identifiers.

## Outputs
- Customer-level attribution dataset (downloadable CSV)
- Campaign-level + channel-level summaries
- Insights panels (trend flags, creative performance, frequency meter)
- “Approve” workflow + exportable Markdown reports

## Notes (prototype scope)
- Attribution model implemented: **last-touch click** within window (configurable); includes **direct vs indirect** tagging.
- External context inputs (competitor/news/market notes) are supported as **uploads** and are appended into the reports.

## Connector folders (simulated)

Drop CSVs here (latest modified file is picked automatically):

- `connectors/sfmc_sftp/engagement/*.csv`
- `connectors/sfmc_sftp/transactions/*.csv`
- `connectors/netcore_s3/engagement/*.csv`
- `connectors/netcore_s3/transactions/*.csv`
