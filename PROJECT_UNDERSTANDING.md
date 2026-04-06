# Campaign Attribution + Intelligence (Agentic) — Project Understanding

## 1) Executive summary

This project builds an end-to-end **Campaign Attribution** and **Campaign Intelligence** system that:

- Ingests cross-channel **campaign engagement** data and **transaction / conversion** data from multiple platforms.
- Performs **identity resolution** (phone/email/customer ID stitching) to create a unified customer view.
- Computes **attribution** (e.g., 7/15/30-day lookback) and tags outcomes as **Direct vs Indirect**.
- Generates **campaign insights** (KPI dashboards, trends with reasons, creative performance, frequency/fatigue checks, segment/journey analytics).
- Uses **human-in-the-loop governance** for validation, review, edits, approval, and export of reports.

The system is designed to reduce manual effort (extracts/joins/spreadsheets), improve transparency of “campaign → revenue impact”, and enable ongoing optimization (channels, creatives, segments, frequency).

## 2) Primary outcomes (what “success” looks like)

- **Operational efficiency**
  - Reduce time to produce attribution + insights (hours/days → minutes)
  - Reduce manual extraction and manual joining across platforms
- **Accuracy + trust**
  - Consistent identity stitching rules and explainable attribution logic
  - Clear exception reporting (missing IDs, sequencing failures, outside window)
- **Business impact**
  - Campaign ROI visibility at campaign/channel/segment level
  - Faster iteration on creatives, cadence, and targeting
- **Scalability**
  - Multiple brands/LOBs/categories, multiple channels, many campaigns

## 3) Scope (v1)

### 3.1 In scope

#### A) Data connectors (ingestion)
- **SFMC workflow**: engagement metrics from SFMC Data Extensions via Automation Studio → **SFTP landing**
- **Netcore workflow**: engagement logs to brand-specific cloud storage → **S3 landing**
- **Manual ingestion**: CSV/Excel uploads for any source or ad-hoc datasets
- **External context inputs**: competitor datasets and market/news notes (uploaded qualitative intelligence)

#### B) Data layer (normalization + governance)
- Standardize channel definitions and engagement events
- Standardize timestamps/timezones, dimensions (LOB/Category/Brand)
- Dedupe and sequencing checks (engagement → transaction)
- Privacy boundary enforcement for PII where required

#### C) Identity resolution (stitching)
- Map/stitch: **Phone ↔ Email ↔ Customer ID**
- Create a **Unified Customer View** for joining engagement + transactions

#### D) Attribution engine (core)
- Attribution window (lookback) filter (e.g., 7 days)
- Engagement-to-transaction mapping
- **Direct vs Indirect** tagging:
  - Direct: transaction product matches campaign target product
  - Indirect: cross-category / cross-LOB / cross-brand mapping when sale differs
- Configurable knobs (window, filters, model selection)

#### E) Outputs
- Customer-level attribution dataset
- Campaign-level attribution summary
- Channel-level attribution analysis
- Advanced analytics:
  - Cross-dimension attribution (LOB/Category/Brand)
  - Time-to-conversion distributions
  - Window sensitivity comparisons (7/15/30)
  - ROI (cost input)

#### F) Insights generator (campaign intelligence)
- KPI report (sent/delivered/open/read/click/unsub/bounce where available)
- Trend identification (ups/downs + reasons)
- Channel comparison matrices
- Creative-wise performance (copy/language/image/CTA variants)
- Frequency meter (fatigue monitoring)
- Lifecycle journey performance (SFMC journey node-by-node)
- Segmentation performance (high-intent vs churn-risk, etc.)
- Operational health (credits, IP reputation, WA number health) — can start as manual inputs

#### G) Human-in-the-loop governance
- Input validation and completeness checks
- Logic validation: adjust window / model / filters
- Output review: approve, edit narratives, apply overrides
- Exception handling workflow and auditability

### 3.2 Out of scope (v1) / future
- Full real-time streaming attribution (v1 is typically batch/daily)
- Advanced multi-touch attribution with probabilistic weights/confidence scoring (can be v2)
- Automated competitor/news scraping (v1 uses user-provided uploads)
- Production-grade deliverability telemetry integrations (can be phased in)

## 4) End-to-end workflow (as designed)

### 4.1 Campaign Attribution (Core)
1. **Connectors ingest data**
   - SFMC → SFTP drops (scheduled)
   - Netcore → S3 drops (scheduled)
   - Manual file ingestion (ad-hoc)
2. **Validation + normalization**
   - Schema and type checks
   - Timestamp consistency
   - Deduplication rules
   - Event sequencing checks
3. **Identity resolution**
   - Build identity graph from available identifiers
   - Output unified identity key for joins
4. **Attribution engine**
   - Filter eligible engagements (e.g., Click)
   - Apply lookback window
   - Determine direct vs indirect
   - Produce customer/campaign/channel outputs + exception tables
5. **Governance**
   - Review exceptions and assumptions
   - Approve export-ready outputs

### 4.2 Campaign Intelligence (Insights Generator)
1. Combine:
   - Attribution outputs + engagement KPI history
   - External context uploads (competitor/news)
2. Generate:
   - KPI dashboards, trends, creative/frequency/segment/journey insights
3. Human validation:
   - Edit and approve recommendations and narratives
4. Deliverables:
   - Executive one-pager + full detailed ops report

## 5) Data model understanding (inputs)

### 5.1 Engagement data (cross-channel)
Typical fields:
- **Campaign metadata**: `campaign_id`, `campaign_name`, `campaign_type`, (optional) journey/node identifiers
- **Event**: `event_ts`, `channel`, `engagement_type` (Sent/Delivered/Open/Read/Click/etc.)
- **Identity**: `phone`, `email`, `customer_id`/`user_id`
- **Business dimensions**: `lob`, `category`, `brand`, `business_unit`
- **Creative tracking** (if available): `creative_id`, `cta`, `language`, `variant`, `message_template_id`
- **Targeting** (if available): `segment_id`, `segment_name`, audience cohort labels

### 5.2 Transactions / conversions
Typical fields:
- `order_id`/`invoice_id`
- `txn_ts`
- `revenue`
- `product`, `category`, `lob`, `brand`
- Identity keys: `phone`, `email`, `customer_id`/`user_id`
- Non-purchase conversions (optional): leads, test drives, bookings, form submits

### 5.3 Identity map (optional but recommended)
- `user_id/customer_id` with `email` and `phone`
- Used to stitch cross-channel identities and reduce unmatched rows

### 5.4 External context (qualitative intelligence)
- Competitor campaign datasets (uploaded)
- Market/news notes (uploaded)
- Used to annotate spikes/dips (“reasoning” context), not to compute attribution directly

## 6) Data validation points (governance checkpoints)

### 6.1 Ingestion/schema validation
- Required columns exist (per input type)
- Datetime parsing for `event_ts` and `txn_ts`
- Numeric parsing for `revenue`
- Allowed values checks (channel list, engagement types)

### 6.2 Quality checks
- **Timestamp consistency** (timezone, missing timestamps, outliers)
- **Identifier availability** (must have at least one stable identifier per record)
- **Deduplication** (event-level and order-level)
- **Event sequencing**: engagement must occur before transaction

### 6.3 Identity resolution checks
- Conflicting mappings (same email/phone → multiple customer IDs)
- Coverage: % engagement and % transactions successfully stitched

### 6.4 Attribution logic checks
- Window eligibility: `txn_ts - event_ts <= lookback_days`
- No double-counting orders for single-touch models
- Exceptions cataloged and visible to reviewers

### 6.5 Privacy/compliance checks
- PII tokenization where outputs are shared outside secure boundary
- Consent-based eligibility if consent flags exist
- Compliance alignment: GDPR/CCPA/DPDP (India)

## 7) Attribution logic (v1 understanding)

### 7.1 Core rules
- Choose the **eligible engagement** event(s) for a user:
  - Often: `engagement_type == Click` (configurable)
  - Must occur **before** the transaction timestamp
  - Must be within the configured **lookback window** (e.g., 7 days)
- Map transaction to campaign touchpoint using an attribution model:
  - v1 baseline: **Last-touch** within the window

### 7.2 Direct vs Indirect
- **Direct**: transaction product matches campaign’s target product
- **Indirect**: transaction differs but shares dimensions (same brand/category/LOB) or mapped by business rules

### 7.3 Example (7-day window)
- Day 1: user clicks WhatsApp link for “Summer Shirt”
- Day 4: user purchases “Summer Shirt”
- Checks:
  - sequencing: Day 1 < Day 4 ✅
  - within 7 days ✅
  - product match ✅ → Direct

## 8) Outputs & deliverables

### 8.1 Core attribution datasets
- **Customer-level attribution**
  - identity key, campaign, channel, engagement event, window, order, revenue, direct/indirect tag
- **Campaign-level summary**
  - engaged users, converted users/orders, conversion rate, total attributed revenue, avg revenue
- **Channel-level analysis**
  - revenue contribution and conversion efficiency by channel

### 8.2 Advanced analytics
- Cross-dimension views (LOB/Category/Brand)
- Time-to-conversion distribution
- Window sensitivity comparisons (7 vs 15 vs 30)
- ROI (requires campaign cost input)

### 8.3 Intelligence outputs
- KPI dashboard and channel comparisons
- Trend flags + “reasons” notes
- Creative performance tables (copy/lang/image/CTA)
- Frequency meter (fatigue monitoring)
- Lifecycle journey performance (SFMC journeys)
- Segmentation performance
- Operational health indicators (credits, IP/WA health)

### 8.4 Executive deliverables
- **Executive one-pager**: simplified “Campaign → Revenue Impact”
- **Full detailed report**: diagnostic export for marketing ops, including transparency on assumptions and exception tables

## 9) Non-functional requirements (NFRs)

- **Reliability**: idempotent ingestion; clear failures + retries; audit logs
- **Performance**: handle large CSV extracts; incremental loads preferred
- **Security**: protect PII; secret management for SFTP/S3; role-based access
- **Observability**: metrics for ingestion, stitching rate, attribution coverage, exception counts
- **Explainability**: every attributed order can show the chosen touchpoint and why

## 10) Implementation notes (current prototype in this repo)

This workspace contains a working **Streamlit prototype** that demonstrates the full flow including connectors (simulated as folders):

- `app.py`: UI flow (connectors → validation → attribution → insights → approval → exports)
- `proto/attribution.py`: attribution logic (v1 baseline)
- `proto/insights.py`: KPI + trend + creative + frequency + report builders
- `proto/connectors.py`: connector abstractions (SFMC SFTP and Netcore S3 simulated as local folders)
- `connectors/...`: landing zones for connector drops (latest CSV wins)

Prototype limitations are intentional: connectors are local-folder simulations and “agent” reasoning modules are mostly summarized/stubbed to match the architecture, while keeping the system runnable and reviewable.

## 11) Open questions to finalize before production build

1. **Attribution model choice**
   - last-touch only vs multiple models; single-touch vs multi-touch
2. **Authoritative identity source**
   - CDP identity graph vs CRM master vs deterministic rules
3. **Granularity**
   - campaign-level vs journey node-level attribution for SFMC
4. **Cost inputs**
   - how campaign costs are provided (manual, finance feed, platform spend feed)
5. **Compliance boundary**
   - what outputs can contain PII vs tokenized keys only
6. **Schedule**
   - batch cadence: hourly/daily/weekly; SLAs for report refresh

---

If you want, I can also produce a **BRD-style** version of this document (with explicit “As-Is vs To-Be”, user stories, acceptance criteria, and reporting wireframes) in a separate file.
