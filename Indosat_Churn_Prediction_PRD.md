# AI Churn Prediction Solution
## Product Requirements Document (PRD)
### Indosat Ooredoo Hutchison | Individual Assignment
**Columbia University | Due: April 30, 2026**

---

## 1. Problem Definition and Context

### 1.1 Problem Statement

Indosat Ooredoo Hutchison (IOH) operates with approximately 95 million subscribers across Indonesia. Despite strong market presence, the company faces sustained pressure from SIM card consolidation — a pattern where users reduce the number of active SIMs they maintain — and aggressive competitive pricing from rival operators. Subscriber churn (customers who deactivate or stop using Indosat services) directly reduces Average Revenue Per User (ARPU) and increases acquisition costs, since acquiring a new customer costs significantly more than retaining an existing one.

### 1.2 Current State Limitations

The current retention process is **reactive**: customer service teams respond to churn only after it has occurred — after a SIM has been deactivated or a user has ported out. There is no systematic early-warning mechanism that identifies at-risk subscribers before they leave, meaning retention budgets are spent on broad campaigns rather than targeted interventions.

Specific limitations:
- No real-time or near-real-time scoring of individual subscriber churn risk
- Retention campaigns are broad and untargeted, leading to wasted budget
- Customer service teams lack data-driven prioritization for proactive outreach
- No feedback loop connecting retention outcomes back to model improvement

### 1.3 Definition of Success

The problem is considered solved when:
1. A model can identify, with measurable precision and recall, which subscribers are likely to churn within the next 30 days
2. Targeted retention offers are sent to predicted at-risk users before churn occurs
3. The churn rate among the targeted group decreases by at least 10% compared to the untargeted baseline
4. The system operates with low enough latency to allow daily batch scoring of all active subscribers

---

## 2. Data and AI Factory Design

### 2.1 Data Sources

| Data Source | Type | Description |
|---|---|---|
| CDR (Call Detail Records) | Internal, structured | Voice and data usage logs per subscriber |
| CRM System | Internal, structured | Demographics, plan type, contract length, complaint history |
| Billing System | Internal, structured | Monthly spend, top-up frequency, payment history, ARPU trend |
| Network Quality Logs | Internal, time-series | Signal strength, packet loss, latency per subscriber region |
| Customer Service Logs | Internal, unstructured text | Complaint tickets, call transcripts |
| External Market Data | External, structured | Competitor plan pricing, promotional events |

### 2.2 Data Types and Structure

- **Tabular/structured:** Majority of data. Stored in relational databases (PostgreSQL or Hive on Hadoop)
- **Time-series:** CDR and network logs aggregated into rolling 7-day, 14-day, and 30-day windows
- **Unstructured text:** Customer service tickets processed using NLP to extract sentiment and topic tags, then converted to structured features

### 2.3 Data Volume, Velocity, and Quality

- **Volume:** ~95 million subscribers; daily CDR logs generate hundreds of GB per day
- **Velocity:** Batch processing is sufficient for this use case (daily refresh); real-time streaming is not required at this stage
- **Quality issues:** Missing top-up records for prepaid users, duplicate CRM entries post-merger, inconsistent customer IDs across legacy Ooredoo and Hutchison systems

### 2.4 Data Preparation Steps

1. **De-duplication** — Merge legacy subscriber IDs from pre-merger Ooredoo and Hutchison systems
2. **Aggregation** — Compute rolling feature windows (7-day, 14-day, 30-day) from raw CDR logs
3. **Labeling** — Define churn label: a subscriber who has zero usage AND zero top-up for 30 consecutive days is labeled as churned
4. **Imputation** — Fill missing top-up values for prepaid users using median imputation per plan segment
5. **NLP preprocessing** — Tokenize and classify customer service tickets as positive, neutral, or negative sentiment; extract topics (billing, network, promotion)
6. **Train/validation/test split** — 70% train, 15% validation, 15% test; stratified by churn label to handle class imbalance

---

### 2.5 Customer Segmentation Framework

Before model training, each subscriber is assigned to four segmentation dimensions. These segments serve as structured input features to the churn model and make model outputs interpretable by the CRM team.

#### Dimension 1 — Tenure Segment

Tenure is calculated in days since SIM activation date, sourced from the CRM system.

| Segment | Tenure Range | Churn Risk | Behavioral Note |
|---|---|---|---|
| New | 0-30 days | Very High | Still in trial phase; easily swayed by competitor promotions |
| Early | 31-100 days | High | Forming usage habits; needs engagement to stay |
| Growing | 101-360 days | Medium | Has renewed at least once; more stable behavior |
| Loyal | >360 days | Low | Long-term user; best candidate for upsell and cross-sell |

#### Dimension 2 — ARPU Segment

ARPU is calculated as the average monthly spend over the last 3 months, sourced from the billing system.

| Segment | Monthly ARPU (IDR) | Retention Priority | Notes |
|---|---|---|---|
| Low | < 20,000 | Standard | Prepaid users; highly price-sensitive |
| Mid | 20,000-75,000 | Important | Core revenue base; most common segment |
| High | 75,000-200,000 | High | Power users and multi-SIM households |
| Premium | > 200,000 | Critical | Enterprise or heavy data users; highest lifetime value |

#### Dimension 3 — Loyalty Tier

Loyalty tier is a composite score computed from: tenure, reward redemption frequency, complaint history, and average monthly engagement rate.

| Tier | Description | Churn Risk |
|---|---|---|
| Bronze | New or disengaged; no loyalty rewards redeemed yet | High |
| Silver | Moderate engagement; occasional reward use | Medium |
| Gold | Frequent usage; active in loyalty program | Low |
| Platinum | Top-tier long-term subscriber; acts as a brand ambassador | Very Low |

#### Dimension 4 — Interest Segment

Interest segment is derived from CDR traffic analysis — which app categories account for the highest share of a subscriber's monthly data usage. Assigned automatically via a rule-based classifier on network traffic logs.

| Segment | Primary Usage Pattern | Key Sensitivity | Retention Lever |
|---|---|---|---|
| Data Streamer | YouTube, Netflix, TikTok | Speed and monthly quota | Streaming bonus data pass |
| Social Media User | WhatsApp, Instagram, X (Twitter) | Social pass pricing | Free social pack trial |
| Gamer | Online gaming, low-latency apps | Latency and ping stability | Gaming data bundle |
| Business User | VPN, email, cloud storage, video calls | Reliability and uptime SLA | SME or enterprise plan upgrade |

---

### 2.6 Segmentation Matrix — Churn Risk (Tenure x ARPU)

Estimated churn probability (%) for each subscriber group combination. Used to prioritize which groups receive retention interventions first.

| Tenure / ARPU | Low (<20k) | Mid (20-75k) | High (75-200k) | Premium (>200k) |
|---|---|---|---|---|
| New (0-30d) | 72% | 55% | 38% | 22% |
| Early (31-100d) | 50% | 38% | 25% | 15% |
| Growing (101-360d) | 30% | 22% | 14% | 8% |
| Loyal (>360d) | 15% | 10% | 6% | 3% |

The AI model produces a continuous churn score per subscriber. This matrix provides interpretable reference ranges for business stakeholders and CRM teams.

---

### 2.7 Retention Action Matrix (Interest x Loyalty Tier)

Maps each subscriber segment combination to a recommended retention action. Urgency score: 5 = act immediately, 1 = low urgency.

| Interest / Loyalty | Bronze | Silver | Gold | Platinum |
|---|---|---|---|---|
| Data Streamer | Quota bonus (5) | Streaming pass (4) | Upgrade push (2) | VIP lock-in (1) |
| Social Media User | Free social trial (5) | Social bundle (3) | Loyalty reward (2) | Ambassador invite (1) |
| Gamer | Gaming pack trial (4) | Gaming bundle (3) | eSports promo (2) | Elite gaming plan (1) |
| Business User | SME trial plan (3) | Business bundle (2) | SLA guarantee (1) | Enterprise VIP (1) |

---

### 2.8 How Segmentation Feeds Into the AI Model

Each dimension is encoded as a model input feature:
- tenure_segment — Ordinal encoded: New=0, Early=1, Growing=2, Loyal=3
- arpu_segment — Ordinal encoded: Low=0, Mid=1, High=2, Premium=3
- loyalty_tier — Ordinal encoded: Bronze=0, Silver=1, Gold=2, Platinum=3
- interest_segment — One-hot encoded: Streamer, Social, Gamer, Business

These engineered segment features are combined with raw behavioral features (data usage drop %, top-up frequency, complaint count, etc.) to train the XGBoost classifier. SHAP values are computed per subscriber so the CRM team can see which factor is the primary driver of each individual's churn risk.

Example model output:
"Subscriber #A8821 — Churn probability: 78%. Top drivers: (1) New tenure segment, (2) Low ARPU, (3) 2 unresolved complaints in last 14 days. Recommended action: Send free social pass trial."

---

### 2.9 AI Pipeline — Data Flow

  [Raw Data Sources]
         |
         v
  [Data Ingestion Layer]
    - CDR Logs (daily batch from network nodes)
    - CRM & Billing (daily SQL export)
    - Customer Service Tickets (daily NLP preprocessing)
         |
         v
  [Feature Engineering + Segmentation Assignment]
    - Rolling window aggregations (7d, 14d, 30d)
    - Segment encoding (tenure, ARPU, loyalty, interest)
    - Derived ratios: data usage drop %, spend decline %
    - Sentiment score from CS tickets via IndoBERT
         |
         v
  [Model Training Workflow]
    - Framework: XGBoost / LightGBM
    - Input: Engineered feature matrix (~40+ features per subscriber)
    - Target: Binary churn label (1 = churned within 30 days)
    - Imbalance handling: SMOTE or class_weight=balanced
         |
         v
  [Model Evaluation & Validation]
    - Metrics: Precision, Recall, F1, AUC-ROC
    - Threshold tuned to maximize Recall
         |
         v
  [Deployment: Daily Batch Scoring]
    - Run model on all active subscribers each morning
    - Output: churn_probability score (0.0-1.0) per subscriber
    - Flag subscribers above 0.70 threshold as "at-risk"
         |
         v
  [Retention Action Layer]
    - CRM receives at-risk list + segment labels + recommended action
    - Automated SMS/app push with personalized retention offer
    - Outcomes logged (offer accepted / retained / churned)
         |
         v
  [Feedback Loop]
    - Outcomes feed back into next training cycle (monthly retraining)
    - Model drift monitoring: alert if AUC drops >5% week-over-week

---

## 3. AI Techniques and Technology Stack

### 3.1 AI Approach

| Dimension | Choice | Justification |
|---|---|---|
| AI Type | Supervised Machine Learning | Labeled historical churn data is available; binary classification problem |
| Model Family | Gradient Boosted Trees (XGBoost / LightGBM) | Best performance on tabular data; handles missing values; interpretable via SHAP |
| Training Approach | Supervised with class imbalance handling | Churn is inherently imbalanced (typically 5-15% positive rate in telecom) |
| Interpretability | SHAP values | Required for business stakeholders to understand per-subscriber churn drivers |
| Sentiment Analysis | IndoBERT (HuggingFace) | Bahasa Indonesia NLP for customer service ticket classification |
| Baseline Model | Logistic Regression | Simple, fast, interpretable benchmark to compare against |

**Why not deep learning?**
The data is primarily tabular and structured. Deep learning does not significantly outperform gradient boosted trees on tabular data, and it is harder to interpret and deploy in batch pipelines.

**Why not generative AI?**
The task is binary classification with structured data. Generative AI adds no value here and introduces unnecessary complexity.

### 3.2 Technology Stack

| Layer | Tool | Purpose |
|---|---|---|
| Data Storage | PostgreSQL / Apache Hive | Structured subscriber data storage |
| Data Processing | Apache Spark / Pandas | Feature engineering and aggregation at scale |
| NLP Preprocessing | HuggingFace Transformers (IndoBERT) | Sentiment analysis on Bahasa Indonesia CS tickets |
| Model Development | scikit-learn, XGBoost, LightGBM | Model training and evaluation |
| Experiment Tracking | MLflow | Track model versions, hyperparameters, and metrics |
| Serving / Inference | Python batch script + FastAPI | Daily batch scoring + optional real-time API endpoint |
| Monitoring | Evidently AI | Data drift and model performance monitoring |
| Visualization / UI | Streamlit dashboard | Internal dashboard for CRM team to view at-risk subscriber list |
| CI/CD | GitHub Actions | Automate model retraining pipeline |

---

## 4. Prototype Development

### 4.1 Prototype Scope

The prototype demonstrates the core AI capability using a publicly available telecom churn dataset (IBM Telco Customer Churn on Kaggle) as a stand-in for Indosat's proprietary data. The system accepts subscriber input and returns a real-time churn prediction with explanations and a recommended retention action.

### 4.2 Prototype Components

1. **Data preprocessing notebook** — loads dataset, cleans missing values, engineers features, assigns segment labels
2. **Model training script** — trains XGBoost classifier with cross-validation; outputs trained model artifact
3. **Feature importance analysis** — identifies which factors drive churn risk for individual subscribers
4. **Streamlit web app (app.py)** — takes 8 subscriber inputs, returns churn probability score, risk level, top 3 risk drivers, segment labels, and recommended retention action

### 4.3 System Inputs and Outputs

**Inputs (8 fields per subscriber):**

| Input Field | Description | Example Value |
|---|---|---|
| Tenure (days) | Days since SIM activation | 45 |
| Monthly ARPU (IDR) | Average spend per month | 35,000 |
| Loyalty Tier | Bronze / Silver / Gold / Platinum | Bronze |
| Interest Segment | Streamer / Social / Gamer / Business | Social Media |
| Data Usage Drop (%) | % drop in data usage vs last month | 60% |
| Days Since Last Top-up | Recency of top-up activity | 25 days |
| Unresolved Complaints | Open complaints in last 30 days | 2 |
| Network Quality Score | 1 (poor) to 5 (excellent) | 3.0 |

**Outputs (generated per prediction):**

| Output | Description | Example |
|---|---|---|
| Churn Probability | AI model score from 0% to 100% | 78.3% |
| Risk Level | HIGH / MEDIUM / LOW | HIGH RISK |
| Tenure Segment Label | Auto-assigned from tenure input | Early (31-100d) |
| ARPU Segment Label | Auto-assigned from ARPU input | Low (<20k IDR) |
| Loyalty Label | From dropdown input | Bronze |
| Interest Label | From dropdown input | Social Media |
| Top 3 Risk Drivers | Plain-language explanations | "No top-up in 25 days", "Low ARPU", "2 complaints" |
| Recommended Action | Matched from Interest x Loyalty matrix | "Send free social pass trial" |
| Alert Banner | Urgency message for CRM team | "Trigger retention campaign immediately" |

### 4.4 The Value Moment

The value moment occurs when a CRM analyst enters a subscriber's usage profile and the system instantly returns a churn probability, the reason behind it in plain language, and the exact action to take — replacing manual guesswork with a data-driven decision in under 5 seconds.

### 4.5 How to Run the Prototype

Requirements:
  pip install streamlit scikit-learn numpy

Run the app:
  streamlit run app.py

Open browser at: http://localhost:8501

### 4.6 Prototype Deliverables

- app.py — Streamlit web application (working prototype)
- Jupyter Notebook — data preprocessing + model training + feature importance analysis
- This technical description (Section 4 of PRD)
- 2-4 minute demo video showing: input subscriber data > receive churn score > view drivers > trigger retention action

---

## 5. Success Metrics and Go / No-Go Evaluation

### 5.1 Model Performance Metrics

| Metric | Target Threshold | Rationale |
|---|---|---|
| AUC-ROC | >= 0.80 | Standard strong classifier benchmark for telecom churn |
| Recall (Sensitivity) | >= 0.75 | Priority: catch as many churners as possible; false negatives are costly |
| Precision | >= 0.60 | Avoid wasting too many retention offers on non-churners |
| F1 Score | >= 0.67 | Harmonic balance of precision and recall |
| Inference Latency | < 5 seconds per prediction | Must return result before CRM analyst moves on |

### 5.2 Data Quality Metrics

| Metric | Target |
|---|---|
| Feature completeness post-imputation | >= 95% |
| Churn label accuracy (manual validation sample) | >= 90% |
| Training data recency | Last 12 months minimum |
| Segment assignment coverage (all 4 dimensions) | 100% of active subscribers |

### 5.3 Business Outcome Metrics

| Metric | Target | Measurement Method |
|---|---|---|
| Churn rate reduction (targeted group) | >= 10% vs. control | A/B test: model-targeted vs. random outreach |
| Retention campaign cost efficiency | >= 20% cost reduction per retained subscriber | Cost per retained subscriber (model group vs. baseline) |
| ARPU impact on retained cohort | Maintained or increased | Monthly ARPU tracking per cohort |

### 5.4 Go / No-Go Criteria

**GO — proceed to production if:**
- AUC-ROC >= 0.80 on held-out test set
- Recall >= 0.75 (model catches at least 3 out of 4 churners)
- A/B pilot shows >= 10% churn reduction in targeted group
- Feature importance explanations are interpretable and trusted by CRM team

**NO-GO — pause and iterate if:**
- AUC-ROC < 0.75 (model too weak for production use)
- Recall < 0.60 (model misses too many actual churners)
- A/B pilot shows no statistically significant difference between groups
- Data quality issues cannot be resolved (e.g., > 20% missing CDR records)

### 5.5 Identified Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Class imbalance (low churn rate) | High | SMOTE, class weights, or adjusted decision threshold |
| Post-merger data inconsistencies | Medium | Dedicated data cleaning pipeline; use post-merger data only if needed |
| Model drift over time | Medium | Monthly retraining + Evidently AI monitoring with weekly alerts |
| Privacy / PII in CDR data | Medium | Anonymize subscriber IDs; comply with Indonesian UU PDP (Personal Data Protection Law) |
| Low feature importance interpretability for CRM team | Low | Plain-language summaries of drivers in the Streamlit UI |

### 5.6 Recommendation

**Proceed to pilot.** The churn prediction solution addresses a clearly quantifiable business problem, relies on data Indosat already collects as part of standard operations, and uses a well-established ML technique with a strong track record in the telecom industry. The four-dimension segmentation framework (tenure, ARPU, loyalty, interest) adds interpretability and directly connects model outputs to actionable CRM interventions.

The highest near-term risk is data quality from legacy system inconsistencies post-merger. A dedicated data engineering sprint to unify subscriber IDs and validate churn labels should be prioritized before production deployment.

---

---

## APPENDIX A: API Integration Documentation

### A.1 Email Integration — Gmail SMTP

**Provider:** Google Gmail SMTP
**Sender Account:** agung.technology.management@gmail.com
**Protocol:** SMTP over SSL (Port 465)
**Cost:** Free

#### Setup Steps

1. Go to your Google Account → Security → 2-Step Verification → Enable it
2. Go to Google Account → Security → App Passwords
3. Select "Mail" and "Other (Custom name)" → name it "Indosat CRM"
4. Copy the 16-digit App Password generated
5. Paste it into the sidebar field "Gmail App Password" in the app

#### How It Works in the App

- The app uses Python's built-in `smtplib` library — no extra dependency needed
- When "Send Email" is clicked, the app:
  1. Composes a personalized MIMEMultipart email with the customer's name, offer, and plan details
  2. Logs into Gmail SMTP via SSL using agung.technology.management@gmail.com + App Password
  3. Sends the email directly to the customer's email address
  4. Displays a success/failure confirmation with timestamp

#### Email Content Personalization

Each email is uniquely generated per customer and includes:
- Customer's full name and first name throughout the body
- Number of days they have been a subscriber (tenure)
- Their interest segment (Streamer, Social, Gamer, Business)
- Their loyalty tier (Bronze, Silver, Gold, Platinum)
- A Postpaid-exclusive paragraph for Postpaid customers
- Offer tailored to their interest segment
- Objective tailored to their churn risk level:
  - HIGH RISK (>70%): Retention letter — emotional tone, 48-hour urgency
  - MEDIUM RISK (40-70%): Upgrade pitch — exclusive privilege framing
  - LOW RISK (<40%): Loyalty appreciation — reward and cross-sell

---

### A.2 WhatsApp Integration — Twilio WhatsApp API

**Provider:** Twilio
**Channel:** WhatsApp Business API (via Twilio Sandbox)
**Cost:** Free trial (~$15 credit). Production: ~$0.005 per WhatsApp message (Indonesia)
**Documentation:** https://www.twilio.com/docs/whatsapp

#### Setup Steps

1. Sign up at twilio.com — free account
2. Go to Twilio Console → Messaging → Try it out → Send a WhatsApp message
3. Note your:
   - Account SID (from Console Dashboard)
   - Auth Token (from Console Dashboard)
   - Twilio WhatsApp Sandbox Number (default: whatsapp:+14155238886)
4. Each customer must send "join [sandbox-keyword]" to the sandbox number once to opt in (sandbox limitation)
5. For production: Apply for WhatsApp Business API approval through Twilio

#### How It Works in the App

- Uses the `twilio` Python library: `pip install twilio`
- When "Send WhatsApp" is clicked, the app:
  1. Initializes a Twilio Client with Account SID and Auth Token
  2. Formats the recipient number as `whatsapp:+62xxxxxxxxxx`
  3. Sends a personalized WhatsApp message using `client.messages.create()`
  4. Displays a success/failure confirmation with timestamp

#### WhatsApp Message Personalization

Each message is formatted with WhatsApp markdown (*bold*, emojis) and includes:
- Customer's first name in the greeting
- Interest-specific offer (streaming quota, social pass, gaming pack, business plan)
- Risk-level-appropriate objective:
  - HIGH RISK: Urgent retention offer with 48-hour deadline
  - MEDIUM RISK: Upgrade pitch with 7-day exclusivity
  - LOW RISK: Loyalty reward and points reminder
- Call to action: reply YA or open myIM3 app

---

### A.3 Tech Stack Update (Including APIs)

| Layer | Tool | Purpose |
|---|---|---|
| Email Sending | Gmail SMTP (smtplib) | Send personalized retention emails from agung.technology.management@gmail.com |
| WhatsApp Sending | Twilio WhatsApp API | Send personalized WhatsApp messages to subscriber numbers |
| Credential Management | Streamlit Sidebar (session-only) | Securely input API keys — never stored or logged |
| Message Personalization | Python string templating | Generate unique email and WhatsApp content per customer |
| Send Logging | Streamlit UI feedback | Timestamp-confirmed success/failure shown after each send action |

---

### A.4 Security and Privacy Notes

- Gmail App Password is used instead of the real account password — it can be revoked at any time from Google Account settings
- Twilio credentials are entered in the sidebar and stored only in the active Streamlit session memory — they are never written to disk or logged
- All customer data in the prototype is synthetic — no real PII is used in the demo
- In production, all credentials must be stored in environment variables or a secrets manager (e.g. AWS Secrets Manager, HashiCorp Vault)
- The system must comply with Indonesia's UU PDP (Personal Data Protection Law No. 27 of 2022) — customer consent for WhatsApp and email marketing must be obtained before sending

---

### A.5 Running the Full Prototype

Install all dependencies:

  pip install streamlit scikit-learn pandas numpy twilio

Run the app:

  streamlit run app.py

Open in browser:

  http://localhost:8501

Enter credentials in the left sidebar:
  - Gmail: agung.technology.management@gmail.com
  - Gmail App Password: [16-digit app password from Google]
  - Twilio Account SID: [from twilio.com console]
  - Twilio Auth Token: [from twilio.com console]
  - Twilio WhatsApp Number: whatsapp:+14155238886 (sandbox default)

---

*Prepared for: AI Solution Design and Prototype Evaluation*
*Columbia University | Due: April 30, 2026*
