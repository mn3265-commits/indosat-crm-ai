# Indosat CRM AI — Technical Description (1-Page)

**Agung Nugroho · Columbia University · AI Solution Design and Prototype Evaluation · April 2026**

---

## Problem

Indosat Ooredoo Hutchison (IOH) serves ~95 million subscribers in Indonesia and faces sustained churn pressure from SIM consolidation and competitive pricing. Retention today is **reactive**: teams respond only after a customer has churned. There is no system to identify at-risk subscribers in advance and deliver personalized retention offers before they leave.

## AI Approach — Hybrid Architecture

Two AI models, each suited to a different sub-task:

**Predictive AI (churn scoring):** GradientBoostingClassifier (scikit-learn, 100 trees, max depth 4). Supervised binary classification on 8 features per subscriber (tenure, ARPU, loyalty tier, interest, data usage drop, top-up recency, complaint count, network quality). Chosen over deep learning because the data is tabular and gradient boosted trees are industry-standard for this problem.

**Generative AI (message personalization):** Anthropic Claude Sonnet 4.5 via API. For each flagged subscriber, the model receives customer profile + predicted churn probability + top risk drivers + recommended offer, and generates a unique Bahasa Indonesia Email + WhatsApp message. Rule-based template fallback if the API is unavailable — ensures production reliability.

## Data Pipeline

```
Raw Data (CDR, CRM, Billing, CS Tickets, Network Logs)
   → Daily ingestion + NLP preprocessing (IndoBERT for Bahasa Indonesia sentiment)
   → Feature engineering (7d/14d/30d rolling windows) + 4-dimension segmentation
   → Predictive model: daily batch scoring → churn probability per subscriber
   → Generative model: personalized retention message per flagged subscriber
   → Delivery (Email via Gmail SMTP, WhatsApp via Twilio API)
   → Feedback loop: outcomes (delivered / opened / retained / churned) feed monthly retraining
```

## Prototype Evaluation (Test Set, n=450, held out)

| Metric | Target | Actual | Status |
|---|---|---|---|
| AUC-ROC | ≥ 0.80 | **0.9798** | PASS |
| Recall (churn) | ≥ 0.75 | **0.7980** | PASS |
| Precision (churn) | ≥ 0.60 | **0.8977** | PASS |
| F1-score | ≥ 0.67 | **0.8449** | PASS |
| Inference latency / sample | < 5s | 0.006 ms | PASS |
| Training time (2,101 samples) | < 60s | 0.52s | PASS |

**Top 3 predictive features:** Tenure (50%), Loyalty tier (13%), Top-up recency (10%). Confusion matrix: 342 true negatives, 79 true positives, 9 false positives, 20 false negatives out of 450.

## Technology Stack

- **Predictive model:** scikit-learn GradientBoostingClassifier (production target: XGBoost / LightGBM)
- **Generative model:** Anthropic `anthropic` Python SDK, Claude Sonnet 4.5
- **UI:** Streamlit (deployed on Streamlit Community Cloud)
- **Delivery:** Gmail SMTP (`smtplib`) + Twilio WhatsApp API
- **Code:** Python 3.11, `pandas`, `numpy`, `scikit-learn`, `anthropic`, `twilio`, `streamlit`
- **Deployment:** GitHub → Streamlit Cloud auto-deploy on push
- **Secrets:** Streamlit Cloud Secrets Manager (dev); AWS Secrets Manager (production)

## Recommendation — Go

All pre-pilot thresholds passed by significant margins. Three gating conditions before full rollout: (1) data quality sprint to unify legacy Ooredoo + Hutchison subscriber IDs, (2) recalibration on real post-merger data (expect AUC to settle 0.80-0.85 range), (3) A/B pilot on 10,000 subscribers comparing model-targeted vs. random retention outreach across two 30-day cycles. Proceed to production only if pilot shows ≥ 10% churn reduction with statistical significance.

## Live Demo & Code

- **App (live):** https://indosat-crm-ai.streamlit.app
- **GitHub:** https://github.com/mn3265-commits/indosat-crm-ai
- **Full PRD:** `Indosat_Churn_Prediction_PRD.md` (in repo)
- **Evaluation script:** `evaluate_model.py` (reproduces all metrics above)
