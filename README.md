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

You can upload your own CSVs in the app, or use the **built-in sample data**.

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
- Several “agent” modules (competitor/news context, IP reputation, credit utilization) are included as **stub panels** so the UX flow matches the target architecture.
