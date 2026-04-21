# 📡 Indosat CRM AI — Customer Intelligence Platform

AI-powered churn prediction, customer segmentation, and personalized retention messaging for Indosat Ooredoo Hutchison.

Built as part of: **AI Solution Design and Prototype Evaluation**
Columbia University | Due: April 30, 2026

---

## 🧠 What This App Does

This system uses machine learning to:
- **Predict** which subscribers are at risk of churning in the next 30 days
- **Segment** customers by tenure, ARPU, loyalty tier, and interest
- **Generate** fully personalized Email and WhatsApp messages per customer
- **Recommend** specific actions for the marketing/CRM team
- **Send** messages directly via Gmail SMTP and Twilio WhatsApp API

---

## 🗂️ Project Structure

```
indosat-crm-ai/
├── app.py                              # Main Streamlit application
├── requirements.txt                    # Python dependencies
├── .replit                             # Replit run configuration
├── README.md                           # This file
├── Indosat_Churn_Prediction_PRD.md     # Product Requirements Document (Markdown)
├── Indosat_Churn_Prediction_PRD_v3.docx # Product Requirements Document (Word)
└── assets/
    ├── churn_matrix.png                # Churn Risk Matrix diagram
    ├── action_matrix.png               # Retention Action Matrix diagram
    └── pipeline_diagram.png            # AI Pipeline flowchart
```

---

## ⚙️ Setup & Installation

### Option A — Run Locally

**1. Install dependencies**
```bash
pip install streamlit scikit-learn pandas numpy twilio
```

**2. Run the app**
```bash
streamlit run app.py
```

**3. Open in browser**
```
http://localhost:8501
```

**4. Enter credentials in the sidebar**
- Gmail App Password (see setup below)
- Twilio credentials (see setup below)

---

### Option B — Run on Replit

**1.** Create a new Replit project → choose **Python** template

**2.** Upload these files:
- `app.py`
- `requirements.txt`
- `.replit`

**3.** Add Secrets (click 🔒 in left panel):

| Key | Value |
|---|---|
| `GMAIL_ADDRESS` | agung.technology.management@gmail.com |
| `GMAIL_APP_PASSWORD` | *(16-digit Gmail App Password)* |
| `TWILIO_SID` | *(Twilio Account SID)* |
| `TWILIO_TOKEN` | *(Twilio Auth Token)* |
| `TWILIO_WA_FROM` | whatsapp:+14155238886 |

**4.** Click **Run ▶️** — Replit will install dependencies and launch the app automatically

---

## 🔑 API Credentials Setup

### 📧 Gmail App Password (for Email)

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. Security → **2-Step Verification** → Enable it
3. Security → **App Passwords** → Create new → name it "Indosat CRM"
4. Copy the 16-digit password
5. Add it to Replit Secrets as `GMAIL_APP_PASSWORD`

> ⚠️ Never share or commit your App Password. It can be revoked anytime from Google Account settings.

---

### 💬 Twilio WhatsApp (for WhatsApp)

1. Sign up free at [twilio.com](https://twilio.com)
2. Go to Console → copy your **Account SID** and **Auth Token**
3. Go to Messaging → Try it out → Send a WhatsApp message
4. Note the sandbox number: `whatsapp:+14155238886`
5. Each customer must opt-in by sending `join <sandbox-keyword>` to the sandbox number (sandbox limitation only)
6. Add SID, Token, and number to Replit Secrets

> 💡 For production deployment, apply for Twilio WhatsApp Business API approval.

---

## 🤖 AI Model

| Property | Detail |
|---|---|
| Model Type | Gradient Boosted Trees (GradientBoostingClassifier) |
| Framework | scikit-learn |
| Training Data | Synthetic dataset (2,000 subscribers) with realistic churn logic |
| Target Variable | Binary churn label (1 = churned within 30 days) |
| Input Features | Tenure, ARPU, loyalty score, interest segment, data usage drop, days since top-up, complaint count, network quality |
| Output | Churn probability (0.0–1.0) per subscriber |
| Imbalance Handling | Weighted class probabilities |

---

## 👤 Customer Segmentation

Each subscriber is classified across 4 dimensions:

### Tenure Segment
| Segment | Range | Churn Risk |
|---|---|---|
| New | 0–30 days | Very High |
| Early | 31–100 days | High |
| Growing | 101–360 days | Medium |
| Loyal | >360 days | Low |

### ARPU Segment
| Segment | Monthly ARPU (IDR) | Priority |
|---|---|---|
| Low | < 20,000 | Standard |
| Mid | 20,000–75,000 | Important |
| High | 75,000–200,000 | High |
| Premium | > 200,000 | Critical |

### Loyalty Tier
Bronze → Silver → Gold → Platinum (based on engagement, tenure, rewards)

### Interest Segment
📺 Data Streamer · 📱 Social Media · 🎮 Gamer · 💼 Business User

---

## 📣 Messaging Logic

Messages are fully personalized per customer based on:
- **Name** — used directly in greeting and body
- **Churn risk level** — determines objective (retention / upsell / loyalty)
- **Interest segment** — determines specific offer (quota, social pass, gaming pack, business plan)
- **Loyalty tier** — affects tone and exclusivity framing
- **Plan type** — Postpaid customers receive a special priority paragraph
- **Tenure** — number of days mentioned directly in the message body

### Channels
| Risk Level | Channel | Objective |
|---|---|---|
| HIGH (>70%) | Email + WhatsApp | Prevent churn — 48h urgency offer |
| MEDIUM (40–70%) | WhatsApp | Increase ARPU — exclusive upgrade |
| LOW (<40%) | Email | Strengthen loyalty — reward points |

---

## 🎯 Marketer Action Guide

For each customer, the app generates 3–4 specific next steps for the CRM/marketing team:

- **HIGH RISK:** Send offer in 24h → Personal call if no reply in 48h → Discount as last resort
- **MEDIUM RISK:** Upsell within 3 days → Send loyalty points → Monitor weekly
- **LOW RISK:** Reward with bonus points → Cross-sell family plan → VIP newsletter

Postpaid customers receive an additional escalation note due to their higher lifetime value.

---

## 📊 Success Metrics

| Metric | Target |
|---|---|
| AUC-ROC | ≥ 0.80 |
| Recall | ≥ 0.75 |
| Precision | ≥ 0.60 |
| Churn rate reduction (targeted group) | ≥ 10% vs control |
| Inference latency | < 5 seconds |

---

## 🔒 Security & Privacy

- All credentials are loaded from environment variables (Replit Secrets) — never hardcoded
- Sidebar fields are for manual override only during development
- All customer data in the prototype is **synthetic** — no real PII is used
- In production, comply with **Indonesia's UU PDP** (Personal Data Protection Law No. 27 of 2022)
- Customer opt-in for WhatsApp and email marketing must be obtained before sending

---

## 📦 Dependencies

```
streamlit
scikit-learn
pandas
numpy
twilio
```

---

## 👨‍💻 Author

Columbia University — AI Solution Design and Prototype Evaluation
Sender Email: agung.technology.management@gmail.com

---

*Indosat Ooredoo Hutchison AI Prototype — April 2026*
