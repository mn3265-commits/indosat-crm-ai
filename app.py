import streamlit as st
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from datetime import datetime, timedelta
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

st.set_page_config(page_title="Indosat CRM AI", layout="wide")

# ── Sidebar Credentials ───────────────────────────────────────────────────────
import os

def _get_secret(key, default=""):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)

_GMAIL_ADDRESS   = _get_secret("GMAIL_ADDRESS", "agung.technology.management@gmail.com")
_GMAIL_APP_PASS  = _get_secret("GMAIL_APP_PASSWORD", "")
_TWILIO_SID      = _get_secret("TWILIO_SID", "")
_TWILIO_TOKEN    = _get_secret("TWILIO_TOKEN", "")
_TWILIO_FROM     = _get_secret("TWILIO_PHONE_FROM", _get_secret("TWILIO_SMS_FROM", _get_secret("TWILIO_WA_FROM", "")))
_ANTHROPIC_KEY   = _get_secret("ANTHROPIC_API_KEY", "")

with st.sidebar:
    st.markdown("### API Configuration")
    st.markdown("---")

    if _GMAIL_APP_PASS:
        st.success("Gmail credentials loaded")
    else:
        st.warning("Gmail App Password not configured")

    if _TWILIO_SID and _TWILIO_TOKEN:
        st.success("Twilio credentials loaded")
    else:
        st.warning("Twilio credentials not configured")

    if _ANTHROPIC_KEY and ANTHROPIC_AVAILABLE:
        st.success("Claude AI connected")
    elif not ANTHROPIC_AVAILABLE:
        st.warning("anthropic library not installed")
    else:
        st.warning("Claude API key not configured")

    st.markdown("---")
    st.markdown("**Claude AI (Generative)**")
    anthropic_key = st.text_input("Anthropic API Key", value=_ANTHROPIC_KEY, type="password", placeholder="sk-ant-...")

    st.markdown("---")
    st.markdown("**Gmail SMTP**")
    sender_email   = st.text_input("Your Gmail", value=_GMAIL_ADDRESS)
    gmail_app_pass = st.text_input("Gmail App Password", value=_GMAIL_APP_PASS, type="password", placeholder="Leave blank if using Secrets")

    st.markdown("---")
    st.markdown("**Twilio Voice Call**")
    twilio_sid     = st.text_input("Twilio Account SID", value=_TWILIO_SID, type="password")
    twilio_token   = st.text_input("Twilio Auth Token", value=_TWILIO_TOKEN, type="password")
    twilio_from    = st.text_input("Twilio Phone Number", value=_TWILIO_FROM, placeholder="+1xxxxxxxxxx")

    st.markdown("---")
    st.caption("Credentials load automatically from Streamlit Cloud Secrets. Sidebar fields are for manual override only.")

# ── Send functions ────────────────────────────────────────────────────────────
def send_email(to_email, subject, body, sender, app_password):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = sender
        msg["To"]      = to_email
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, app_password)
            server.sendmail(sender, to_email, msg.as_string())
        return True, "Email sent successfully."
    except Exception as e:
        return False, str(e)

def send_call(to_number, message, sid, token, from_number):
    if not TWILIO_AVAILABLE:
        return False, "Twilio library not installed. Run: pip install twilio"
    try:
        client = TwilioClient(sid, token)
        to_clean = to_number.replace("whatsapp:", "").strip()
        if not to_clean.startswith("+"):
            to_clean = f"+{to_clean}"
        from_clean = from_number.replace("whatsapp:", "").strip()
        # Use TwiML to speak the message in Indonesian
        twiml = (
            f'<Response>'
            f'<Say language="id-ID" voice="Polly.Siti">{message}</Say>'
            f'<Pause length="1"/>'
            f'<Say language="id-ID" voice="Polly.Siti">Terima kasih telah mendengarkan. Selamat tinggal.</Say>'
            f'</Response>'
        )
        client.calls.create(
            to=to_clean,
            from_=from_clean,
            twiml=twiml
        )
        return True, "Call initiated successfully."
    except Exception as e:
        return False, str(e)

# ── Claude AI message generation ──────────────────────────────────────────────
def generate_with_claude(row, prob, drivers, offer, benefit, api_key):
    """Call Claude API to generate personalized retention messages.
    Returns (email_subject, email_body, call_script) or None on failure."""
    if not ANTHROPIC_AVAILABLE or not api_key:
        return None

    first = row["name"].split()[0]
    if prob >= 0.70:
        urgency = "HIGH RISK - urgent retention needed within 24 hours"
    elif prob >= 0.40:
        urgency = "MEDIUM RISK - upsell/engagement opportunity within 3 days"
    else:
        urgency = "LOW RISK - loyalty reward and cross-sell opportunity"

    prompt = f"""You are a CRM retention copywriter for Indosat Ooredoo Hutchison, Indonesia's major telecom operator.

Write TWO personalized retention messages in Bahasa Indonesia for this subscriber (one email, one voice call script):

CUSTOMER PROFILE:
- Name: {row['name']}
- Plan: {row['plan']} ({row['plan_type']})
- City: {row['city']}
- Tenure: {row['tenure']} days
- ARPU: Rp {row['arpu']:,}/month
- Loyalty tier: {LOYALTY[row['loyalty']]}
- Interest segment: {INTEREST[row['interest']]}
- Churn probability: {prob*100:.1f}%
- Risk level: {urgency}
- Top risk drivers: {'; '.join(drivers)}
- Recommended offer: {offer}
- Offer benefit: {benefit}

OUTPUT FORMAT (follow exactly):
===EMAIL_SUBJECT===
[one line subject]
===EMAIL_BODY===
[full email body, professional but warm, address the customer by first name, mention the offer, include call to action via myIM3 app, sign off as the appropriate Indosat team]
===CALL===
[voice call script in natural spoken Bahasa Indonesia, 30-60 seconds when read aloud, warm and professional tone, include the offer, explain how to claim via myIM3 app, close with Indosat Care 185]

RULES:
- Write entirely in Bahasa Indonesia
- Be warm and personal, not corporate-speak
- Reference specific customer data (tenure, city, plan) to show personalization
- The offer should feel exclusive and time-limited
- Do not use emojis
- Do not use em-dashes"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-5-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text

        parts = {}
        for section in ["EMAIL_SUBJECT", "EMAIL_BODY", "CALL"]:
            marker = f"==={section}==="
            if marker in text:
                start = text.index(marker) + len(marker)
                next_markers = [f"==={s}===" for s in ["EMAIL_SUBJECT","EMAIL_BODY","CALL"] if s != section]
                end = len(text)
                for nm in next_markers:
                    if nm in text[start:]:
                        candidate = start + text[start:].index(nm)
                        if candidate < end:
                            end = candidate
                parts[section] = text[start:end].strip()

        if all(k in parts for k in ["EMAIL_SUBJECT","EMAIL_BODY","CALL"]):
            return parts["EMAIL_SUBJECT"], parts["EMAIL_BODY"], parts["CALL"]
        return None
    except Exception:
        return None

# ── Synthetic customer database ───────────────────────────────────────────────
@st.cache_resource
def generate_customers():
    random.seed(42); np.random.seed(42)

    # First names and last names for generating 100 realistic Indonesian customers
    first_names = [
        "Agung","Budi","Siti","Ahmad","Dewi","Rizky","Nurul","Andi","Fitri","Deni",
        "Maya","Hendra","Rina","Fajar","Lina","Bagas","Indah","Roni","Wulan","Agus",
        "Citra","Tono","Putri","Wahyu","Ratna","Dimas","Yuni","Eko","Sari","Joko",
        "Nita","Arif","Mega","Bambang","Ayu","Reza","Ani","Surya","Tika","Irwan",
        "Novi","Hendri","Dina","Prasetyo","Lia","Galih","Wati","Yusuf","Intan","Kukuh",
        "Sinta","Teguh","Mira","Haryo","Lestari","Faisal","Dian","Bagus","Nuri","Sigit",
        "Evi","Guntur","Ratih","Pandu","Yanti","Ilham","Rini","Danang","Laras","Bima",
        "Tiara","Adi","Kania","Rudi","Anisa","Haris","Melati","Jaya","Kartika","Umar",
        "Dewanti","Lutfi","Puspa","Rangga","Siska","Taufik","Anggi","Wisnu","Cantika","Ferdi",
        "Nadia","Satria","Bunga","Yoga","Amira","Gilang","Zahra","Kemal","Elsa","Rama",
    ]
    last_names = [
        "Nugroho","Santoso","Rahayu","Fauzi","Lestari","Pratama","Hidayah","Wijaya",
        "Handayani","Kurniawan","Putri","Gunawan","Susanti","Setiawan","Marlina",
        "Prabowo","Permata","Saputra","Sari","Hartono","Dewi","Suryadi","Wibowo",
        "Kusuma","Hakim","Utama","Pranata","Budiman","Firmansyah","Mulyadi",
    ]
    domains = ["gmail.com","yahoo.com","outlook.com","hotmail.com"]

    # Agung (real user) is always first
    customers = [{"name":"Agung Nugroho","email":"mn3265@columbia.edu","whatsapp":"+16469890162","plan_type":"Postpaid"}]

    # Generate 99 more
    used_names = {"Agung Nugroho"}
    for idx in range(99):
        while True:
            fn = random.choice(first_names)
            ln = random.choice(last_names)
            full = f"{fn} {ln}"
            if full not in used_names:
                used_names.add(full)
                break
        email_name = f"{fn.lower()}.{ln.lower()}"
        domain = random.choice(domains)
        plan = random.choice(["Postpaid","Prepaid"])
        customers.append({
            "name": full,
            "email": f"{email_name}@{domain}",
            "whatsapp": f"+62812{random.randint(10000000,99999999)}",
            "plan_type": plan,
        })

    plans_post = ["Postpaid Freedom 50","Postpaid Business Pro","Postpaid Platinum","Postpaid Family"]
    plans_pre  = ["Prepaid Freedom","Prepaid Social","Prepaid Gaming","Prepaid Basic"]
    cities     = ["Jakarta","Surabaya","Bandung","Medan","Semarang","Makassar","Yogyakarta",
                  "Denpasar","Palembang","Balikpapan","Manado","Pontianak","Malang"]
    rows = []
    for i, c in enumerate(customers):
        tenure    = random.randint(5, 720)
        arpu      = random.randint(50000, 350000) if c["plan_type"]=="Postpaid" else random.randint(8000, 80000)
        loyalty   = random.randint(0, 3)
        interest  = random.randint(0, 3)
        data_drop = random.uniform(0, 90)
        topup     = random.randint(0, 55)
        compl     = random.randint(0, 4)
        netq      = round(random.uniform(1.5, 5.0), 1)
        phone     = f"0812-{random.randint(1000,9999)}-{random.randint(1000,9999)}"
        rows.append({
            "id": f"IOH-{str(i+1).zfill(4)}",
            "name": c["name"], "email": c["email"],
            "whatsapp": c["whatsapp"], "phone": phone,
            "plan_type": c["plan_type"],
            "plan": random.choice(plans_post if c["plan_type"]=="Postpaid" else plans_pre),
            "city": random.choice(cities),
            "tenure": tenure, "arpu": arpu, "loyalty": loyalty,
            "interest": interest, "data_drop": data_drop,
            "topup_days": topup, "complaints": compl, "network": netq,
            "last_active": (datetime.today()-timedelta(days=topup)).strftime("%d %b %Y"),
        })
    return pd.DataFrame(rows)

@st.cache_resource
def train_model():
    np.random.seed(42); n=3000
    td=np.random.randint(0,730,n); ar=np.random.randint(5000,350000,n)
    lo=np.random.randint(0,4,n);   ins=np.random.randint(0,4,n)
    dd=np.random.uniform(0,100,n); tp=np.random.randint(0,60,n)
    co=np.random.randint(0,6,n);   nq=np.random.uniform(1,5,n)
    cp=(0.30*(td<100)+0.20*(ar<20000)+0.15*(lo==0)+0.10*(dd>50)+0.10*(tp>20)+0.10*(co>=2)+0.05*(nq<2.5))
    ch=(cp+np.random.normal(0,0.05,n)>0.40).astype(int)
    X=np.column_stack([td,ar,lo,ins,dd,tp,co,nq])
    m=GradientBoostingClassifier(n_estimators=100,max_depth=4,random_state=42)
    m.fit(X,ch); return m

@st.cache_resource
def evaluate_model_metrics():
    from sklearn.model_selection import train_test_split
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import (roc_auc_score, precision_score, recall_score,
                                 f1_score, accuracy_score, confusion_matrix)
    import time as _time

    np.random.seed(42); n=3000
    td=np.random.randint(0,730,n); ar=np.random.randint(5000,350000,n)
    lo=np.random.randint(0,4,n);   ins=np.random.randint(0,4,n)
    dd=np.random.uniform(0,100,n); tp=np.random.randint(0,60,n)
    co=np.random.randint(0,6,n);   nq=np.random.uniform(1,5,n)
    cp=(0.30*(td<100)+0.20*(ar<20000)+0.15*(lo==0)+0.10*(dd>50)+0.10*(tp>20)+0.10*(co>=2)+0.05*(nq<2.5))
    ch=(cp+np.random.normal(0,0.05,n)>0.40).astype(int)
    X=np.column_stack([td,ar,lo,ins,dd,tp,co,nq])
    features=['Tenure','ARPU','Loyalty','Interest','Data Drop','Top-up Days','Complaints','Network Quality']

    X_tr,X_te,y_tr,y_te = train_test_split(X,ch,test_size=0.15,random_state=42,stratify=ch)
    X_tr,X_va,y_tr,y_va = train_test_split(X_tr,y_tr,test_size=0.176,random_state=42,stratify=y_tr)

    # --- Model 1: GradientBoosting (primary) ---
    t0=_time.time()
    gb=GradientBoostingClassifier(n_estimators=100,max_depth=4,random_state=42)
    gb.fit(X_tr,y_tr)
    gb_train_time=_time.time()-t0
    t1=_time.time()
    gb_pred=gb.predict(X_te); gb_prob=gb.predict_proba(X_te)[:,1]
    gb_infer=_time.time()-t1

    def _metrics(y_true, y_pred, y_prob):
        return {
            "auc": roc_auc_score(y_true, y_prob),
            "accuracy": accuracy_score(y_true, y_pred),
            "precision": precision_score(y_true, y_pred, zero_division=0),
            "recall": recall_score(y_true, y_pred, zero_division=0),
            "f1": f1_score(y_true, y_pred, zero_division=0),
        }

    gb_m = _metrics(y_te, gb_pred, gb_prob)

    # --- Model 2: Logistic Regression (baseline) ---
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)
    lr = LogisticRegression(random_state=42, max_iter=1000)
    lr.fit(X_tr_s, y_tr)
    lr_pred = lr.predict(X_te_s); lr_prob = lr.predict_proba(X_te_s)[:,1]
    lr_m = _metrics(y_te, lr_pred, lr_prob)

    # --- Model 3: Rule-based baseline (no ML) ---
    # Simple heuristic: flag as churn if tenure<100 OR data_drop>50 OR complaints>=2
    rb_pred = ((X_te[:,0]<100) | (X_te[:,4]>50) | (X_te[:,6]>=2)).astype(int)
    rb_prob = np.clip(0.3*(X_te[:,0]<100) + 0.3*(X_te[:,4]>50) + 0.25*(X_te[:,6]>=2) + 0.15*(X_te[:,1]<20000), 0, 1)
    rb_m = _metrics(y_te, rb_pred, rb_prob)

    # --- Edge case simulations ---
    # Simulate 4 scenarios on test set by perturbing features
    edge_cases = {}

    # 1. Mass competitor promo: sudden data drop across all users
    X_promo = X_te.copy()
    X_promo[:,4] = np.clip(X_promo[:,4] + np.random.uniform(30, 60, len(X_te)), 0, 100)
    ec_pred = gb.predict(X_promo); ec_prob = gb.predict_proba(X_promo)[:,1]
    edge_cases["Competitor mass promo"] = {
        **_metrics(y_te, ec_pred, ec_prob),
        "desc": "Simulated sudden data usage drop across all subscribers (competitor runs aggressive promo). "
                "Model over-predicts churn because it cannot distinguish voluntary switching from temporary usage dips."
    }

    # 2. Aggressive price hike: ARPU drops as users downgrade
    X_price = X_te.copy()
    X_price[:,1] = X_price[:,1] * 0.4  # ARPU drops 60%
    ec_pred2 = gb.predict(X_price); ec_prob2 = gb.predict_proba(X_price)[:,1]
    edge_cases["Aggressive pricing change"] = {
        **_metrics(y_te, ec_pred2, ec_prob2),
        "desc": "Simulated 60% ARPU reduction (price hike causes mass downgrade). "
                "Model flags nearly everyone as high risk because low ARPU is a strong churn signal, "
                "but the actual cause is a pricing decision, not organic churn intent."
    }

    # 3. Regulatory change: new SIM registration forces re-verification
    X_reg = X_te.copy()
    X_reg[:,0] = np.where(X_reg[:,0] > 365, X_reg[:,0], np.random.randint(0, 30, len(X_te)))
    X_reg[:,5] = np.clip(X_reg[:,5] + 20, 0, 60)
    ec_pred3 = gb.predict(X_reg); ec_prob3 = gb.predict_proba(X_reg)[:,1]
    edge_cases["Regulatory SIM re-registration"] = {
        **_metrics(y_te, ec_pred3, ec_prob3),
        "desc": "Simulated SIM re-registration mandate resetting tenure for non-loyal subscribers and increasing top-up gaps. "
                "Model misinterprets regulatory compliance behavior as churn signals."
    }

    # 4. Dual-SIM behavior: users maintain 2 active SIMs with low engagement on one
    X_dual = X_te.copy()
    dual_mask = np.random.choice([True, False], len(X_te), p=[0.4, 0.6])
    X_dual[dual_mask, 1] = X_dual[dual_mask, 1] * 0.3  # low ARPU on secondary SIM
    X_dual[dual_mask, 4] = np.random.uniform(40, 80, dual_mask.sum())  # erratic data usage
    X_dual[dual_mask, 5] = np.random.randint(15, 45, dual_mask.sum())  # irregular top-up
    ec_pred4 = gb.predict(X_dual); ec_prob4 = gb.predict_proba(X_dual)[:,1]
    edge_cases["Dual-SIM user behavior"] = {
        **_metrics(y_te, ec_pred4, ec_prob4),
        "desc": "Simulated 40% of subscribers being dual-SIM users with low engagement on their Indosat SIM. "
                "Model cannot distinguish a secondary SIM (stable, low usage) from a subscriber about to churn."
    }

    return {
        "auc": gb_m["auc"], "accuracy": gb_m["accuracy"],
        "precision": gb_m["precision"], "recall": gb_m["recall"], "f1": gb_m["f1"],
        "cm": confusion_matrix(y_te, gb_pred),
        "train_time": gb_train_time,
        "infer_time_ms": gb_infer*1000,
        "infer_per_sample_ms": gb_infer*1000/len(X_te),
        "n_train": len(X_tr), "n_val": len(X_va), "n_test": len(X_te),
        "features": features,
        "importances": gb.feature_importances_,
        "y_prob": gb_prob, "y_te": y_te,
        # Baseline comparison
        "baselines": {
            "GradientBoosting": gb_m,
            "Logistic Regression": lr_m,
            "Rule-based Heuristic": rb_m,
        },
        # Edge cases
        "edge_cases": edge_cases,
    }

df    = generate_customers()
model = train_model()
eval_metrics = evaluate_model_metrics()

LOYALTY  = ["Bronze","Silver","Gold","Platinum"]
INTEREST = ["Data Streamer","Social Media","Gamer","Business User"]

def tseg(d):
    if d<=30:    return "New (0-30d)"
    elif d<=100: return "Early (31-100d)"
    elif d<=360: return "Growing (101-360d)"
    else:        return "Loyal (>360d)"

def aseg(a):
    if a<20000:    return "Low (<20k)"
    elif a<75000:  return "Mid (20-75k)"
    elif a<200000: return "High (75-200k)"
    else:          return "Premium (>200k)"

def risk_label(prob):
    if prob>=0.70: return "HIGH RISK","risk-high"
    elif prob>=0.40: return "MEDIUM","risk-med"
    else: return "LOW RISK","risk-low"

def get_drivers(row):
    f=[]
    if row.tenure<=30:    f.append("Brand new subscriber — still in trial phase")
    elif row.tenure<=100: f.append("Early subscriber — usage habits not yet formed")
    if row.arpu<20000:    f.append("Very low ARPU — highly price-sensitive")
    elif row.arpu<40000:  f.append("Below-average ARPU")
    if row.loyalty==0:    f.append("Bronze tier — no loyalty rewards engagement yet")
    if row.data_drop>50:  f.append(f"Data usage dropped {row.data_drop:.0f}% vs last month")
    if row.topup_days>20: f.append(f"No top-up activity in {row.topup_days} days")
    if row.complaints>=2: f.append(f"{row.complaints} unresolved complaints on record")
    if row.network<2.5:   f.append("Poor network quality in subscriber area")
    return f[:3] if f else ["No significant risk drivers detected"]

def get_offer(interest, plan_type):
    offers = {
        0: ("10GB kuota streaming gratis selama 7 hari",    "nikmati YouTube, Netflix, dan Disney+ tanpa buffering"),
        1: ("akses gratis semua sosial media selama 30 hari","WhatsApp, Instagram, TikTok, dan X tanpa batas"),
        2: ("Gaming Pack 5GB + prioritas ping rendah",       "main Mobile Legends, PUBG, dan Free Fire tanpa lag"),
        3: ("upgrade gratis ke paket Business selama 1 bulan","koneksi stabil untuk meeting dan WFH"),
    }
    return offers[interest]

def marketer_actions(prob, plan_type, interest, loyalty):
    actions = []
    if prob >= 0.70:
        actions.append("URGENT — Send retention offer within 24 hours via Email + Voice Call")
        actions.append("Schedule personal call from retention team if no response in 48h")
        actions.append("Offer loyalty discount (10-20% off next bill) as last resort")
        if plan_type == "Postpaid":
            actions.append("Postpaid priority: Escalate to senior retention team (higher LTV)")
    elif prob >= 0.40:
        actions.append("UPSELL — Target with plan upgrade or add-on offer within 3 days")
        actions.append("Send loyalty points reward to re-engage the customer")
        actions.append("Monitor usage weekly — escalate to HIGH RISK if data drop continues")
        if plan_type == "Postpaid":
            actions.append("Postpaid upsell: push to Platinum or Family Plan tier")
    else:
        actions.append("LOYALTY — Reward with bonus points or exclusive member benefit")
        actions.append("CROSS-SELL — Offer family plan, device bundle, or add-on service")
        actions.append("Re-engage quarterly with VIP newsletter or early access to new plans")
        if plan_type == "Postpaid":
            actions.append("Postpaid cross-sell: Introduce Family Plan to increase ARPU")
    return actions

def generate_email_content(row, prob, offer, benefit):
    first = row["name"].split()[0]
    today = datetime.today().strftime("%d %B %Y")
    loyalty_name = LOYALTY[row["loyalty"]]
    interest_name = INTEREST[row["interest"]]
    postpaid_line = f"\n\nSebagai pelanggan Postpaid kami, {first} mendapatkan prioritas layanan eksklusif yang tidak tersedia untuk pelanggan umum." if row["plan_type"]=="Postpaid" else ""

    if prob >= 0.70:
        subject = f"[Indosat] Hadiah Spesial Untukmu, {first} — Jangan Sampai Terlewat!"
        body = f"""Kepada Yth.
{row['name']},

Salam hangat dari Indosat Ooredoo Hutchison.{postpaid_line}

Kami memperhatikan bahwa belakangan ini aktivitas penggunaan layanan kamu mengalami perubahan. Kami sangat menghargai kesetiaan kamu selama {row['tenure']} hari bersama Indosat, dan kami tidak ingin kamu melewatkan penawaran spesial ini.

Sebagai pelanggan {interest_name} yang kami hormati, kami menyiapkan:

PENAWARAN EKSKLUSIF KHUSUS {first.upper()}:
   > {offer.upper()}
   > Manfaat: {benefit.capitalize()}.

Penawaran ini hanya berlaku 48 jam dan dibuat khusus untuk kamu.

Cara klaim mudah:
   1. Buka aplikasi myIM3
   2. Masuk ke menu "Penawaran Spesial"
   3. Tap "Klaim Sekarang" — GRATIS, tanpa syarat tambahan

Atau balas email ini dengan kata YA dan tim kami akan memproses klaim kamu langsung.

Kami tidak ingin kehilangan kamu, {first}. Kamu adalah bagian penting dari keluarga Indosat.

Salam hangat,
Tim Retensi Pelanggan
Indosat Ooredoo Hutchison
{today}
---
Hubungi kami: 185
Email: care@indosatooredoo.com
myIM3: indosatooredoo.com/myim3"""

    elif prob >= 0.40:
        subject = f"[Indosat] {first}, Ada Penawaran Upgrade Eksklusif Khusus Untukmu!"
        body = f"""Kepada Yth.
{row['name']},

Halo {first}! Salam dari Indosat Ooredoo Hutchison.{postpaid_line}

Sebagai pelanggan {loyalty_name} yang sudah bersama kami selama {row['tenure']} hari, kamu berhak mendapatkan akses ke penawaran upgrade eksklusif yang tidak tersedia untuk umum.

Kami telah menganalisis kebiasaan penggunaan kamu sebagai {interest_name} dan menyiapkan penawaran terbaik:

PENAWARAN UPGRADE EKSKLUSIF UNTUK {first.upper()}:
   > Dapatkan {offer}
   > Manfaat: {benefit.capitalize()}.

Cara aktivasi:
   1. Buka aplikasi myIM3
   2. Pilih menu "Upgrade Paket"
   3. Pilih paket rekomendasi dan nikmati manfaatnya langsung

Penawaran ini hanya tersedia 7 hari ke depan, khusus untuk {first}.

Salam,
Tim Customer Experience
Indosat Ooredoo Hutchison
{today}
---
Hubungi kami: 185
Email: care@indosatooredoo.com"""

    else:
        subject = f"[Indosat] Terima Kasih, {first}! Hadiah Loyalitas Menantimu"
        body = f"""Kepada Yth.
{row['name']},

Halo {first}! Terima kasih telah menjadi pelanggan setia Indosat selama {row['tenure']} hari.{postpaid_line}

Kesetiaan kamu sangat berarti bagi kami. Sebagai pelanggan {loyalty_name}, kamu adalah bagian dari kelompok pelanggan terbaik Indosat.

HADIAH LOYALITAS BULAN INI UNTUK {first.upper()}:
   > Poin reward ekstra 2x lipat untuk semua transaksi
   > Akses prioritas ke penawaran eksklusif member {loyalty_name}

Tukarkan poin kamu untuk mendapatkan kuota data tambahan, diskon tagihan, atau voucher belanja partner Indosat.

Cara tukar poin:
   1. Buka aplikasi myIM3
   2. Pilih menu "Poin & Reward"
   3. Pilih hadiah favoritmu

Terima kasih, {first}. Kami berkomitmen memberikan yang terbaik untukmu.

Salam,
Tim Loyalty & Rewards
Indosat Ooredoo Hutchison
{today}
---
Hubungi kami: 185
Email: care@indosatooredoo.com"""

    return subject, body

def generate_call_script(row, prob, offer, benefit):
    first = row["name"].split()[0]
    if prob >= 0.70:
        return (f"Halo {first}. Saya dari Indosat Ooredoo Hutchison. "
                f"Kami ingin menyampaikan penawaran spesial khusus untuk Anda. "
                f"Sebagai pelanggan setia selama {row['tenure']} hari, Anda berhak mendapatkan {offer}. "
                f"Penawaran ini berlaku 48 jam. "
                f"Untuk klaim, silakan buka aplikasi my IM3, masuk ke menu Penawaran Spesial, "
                f"dan tap Klaim Sekarang. "
                f"Jika ada pertanyaan, hubungi kami di 185.")
    elif prob >= 0.40:
        return (f"Halo {first}. Saya dari Indosat Ooredoo Hutchison. "
                f"Ada penawaran upgrade eksklusif untuk Anda: {offer}. "
                f"Manfaatnya adalah {benefit}. "
                f"Penawaran berlaku 7 hari ke depan. "
                f"Aktifkan di aplikasi my IM3, menu Upgrade Paket. "
                f"Hubungi kami di 185 untuk informasi lebih lanjut.")
    else:
        return (f"Halo {first}. Saya dari Indosat Ooredoo Hutchison. "
                f"Terima kasih telah menjadi pelanggan setia selama {row['tenure']} hari. "
                f"Sebagai hadiah loyalitas, Anda mendapatkan poin reward 2 kali lipat untuk semua transaksi. "
                f"Tukarkan poin Anda di aplikasi my IM3, menu Poin dan Reward. "
                f"Terima kasih, {first}. Kami senang Anda bersama kami.")

# ── Indosat Dark Theme ────────────────────────────────────────────────────────
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {font-family: 'Inter', sans-serif !important;}
.block-container {padding-top:1.5rem; max-width:1100px;}

/* Metric cards */
[data-testid="stMetric"] {
    background: #1A1D24;
    padding: 16px;
    border-radius: 10px;
    border: 1px solid #2A2D35;
}
[data-testid="stMetricLabel"] {
    font-size: 0.7rem; color: #888;
    text-transform: uppercase; letter-spacing: 0.5px;
    font-weight: 600;
}
[data-testid="stMetricValue"] {font-size: 1.3rem; font-weight: 700; color: #F0F0F0;}

/* Expander */
div[data-testid="stExpander"] {
    border: 1px solid #2A2D35;
    border-radius: 10px;
    margin-bottom: 8px;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {gap: 0; border-bottom: 2px solid #2A2D35;}
.stTabs [data-baseweb="tab"] {font-weight: 600; font-size: 0.85rem;}

/* Buttons */
.stButton > button {border-radius: 8px; font-weight: 600; font-size: 0.8rem;}

/* Risk boxes */
.risk-box {padding: 20px; border-radius: 10px; margin: 8px 0;}
.risk-box-high {background: rgba(198,40,40,0.15); border-left: 4px solid #EF5350;}
.risk-box-med {background: rgba(230,81,0,0.12); border-left: 4px solid #FFA726;}
.risk-box-low {background: rgba(46,125,50,0.12); border-left: 4px solid #66BB6A;}

/* Hide branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>""", unsafe_allow_html=True)

def risk_badge_html(prob):
    base = "display:inline-block; padding:4px 14px; border-radius:20px; font-weight:700; font-size:0.75rem; letter-spacing:0.5px;"
    if prob >= 0.70:
        return f'<span style="{base} background:#EF5350; color:white;">HIGH RISK</span>'
    elif prob >= 0.40:
        return f'<span style="{base} background:#FFA726; color:#1a1a1a;">MEDIUM RISK</span>'
    else:
        return f'<span style="{base} background:#66BB6A; color:#1a1a1a;">LOW RISK</span>'

def risk_box_class(prob):
    if prob >= 0.70: return "risk-box risk-box-high"
    elif prob >= 0.40: return "risk-box risk-box-med"
    else: return "risk-box risk-box-low"

def apply_overrides(ids, probs):
    """Apply any marketer overrides from session state to probability array."""
    result = probs.copy()
    for i, cid in enumerate(ids):
        ov = st.session_state.get(f"override_{cid}", "Use AI prediction")
        if ov != "Use AI prediction":
            if "HIGH" in ov: result[i] = 0.85
            elif "MEDIUM" in ov: result[i] = 0.55
            else: result[i] = 0.20
    return result

# ── MAIN UI ──────────────────────────────────────────────────────────────────
st.markdown("""<div style="margin-bottom:28px;">
    <div style="font-size:2rem; font-weight:700; color:#EB1C24; letter-spacing:-0.5px;">Indosat CRM AI</div>
    <div style="font-size:0.85rem; color:#666; margin-top:4px; letter-spacing:0.5px;">CUSTOMER INTELLIGENCE &nbsp;&bull;&nbsp; CHURN PREDICTION &nbsp;&bull;&nbsp; PERSONALIZED RETENTION</div>
</div>""", unsafe_allow_html=True)

tab0, tab1, tab2, tab5, tab3, tab4 = st.tabs([
    "Dashboard", "Search & Predict", "All Customers",
    "What-If Simulator", "Model Evaluation", "AI Architecture"])

# ── Tab 0: Dashboard ─────────────────────────────────────────────────────────
with tab0:
    Xi_all = df[["tenure","arpu","loyalty","interest","data_drop","topup_days","complaints","network"]].values
    probs_all = apply_overrides(df["id"].values, model.predict_proba(Xi_all)[:,1])
    n_total = len(df)
    n_high = int((probs_all >= 0.70).sum())
    n_med = int(((probs_all >= 0.40) & (probs_all < 0.70)).sum())
    n_low = int((probs_all < 0.40).sum())
    n_post = int((df["plan_type"]=="Postpaid").sum())
    n_pre = n_total - n_post

    st.markdown("")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Total Customers", n_total)
    d2.metric("High Risk", n_high, f"{n_high/n_total*100:.0f}% of base")
    d3.metric("Medium Risk", n_med, f"{n_med/n_total*100:.0f}% of base")
    d4.metric("Low Risk", n_low, f"{n_low/n_total*100:.0f}% of base")

    st.markdown("")
    st.markdown("")
    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        st.markdown("**Risk Distribution**")
        risk_df = pd.DataFrame({
            "Risk Level": ["High (>=70%)", "Medium (40-70%)", "Low (<40%)"],
            "Subscribers": [n_high, n_med, n_low]
        }).set_index("Risk Level")
        st.bar_chart(risk_df, color="#EB1C24")

    with col_right:
        st.markdown("**Feature Importance**")
        feat_df = pd.DataFrame({
            "Feature": eval_metrics["features"],
            "Weight": eval_metrics["importances"]
        }).sort_values("Weight", ascending=False).set_index("Feature")
        st.bar_chart(feat_df, color="#FFA726")

    st.markdown("")
    st.markdown("")
    st.markdown("**Model Performance** (held-out test set, n=450)")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("AUC-ROC", f"{eval_metrics['auc']:.4f}")
    k2.metric("Precision", f"{eval_metrics['precision']:.4f}")
    k3.metric("Recall", f"{eval_metrics['recall']:.4f}")
    k4.metric("F1-Score", f"{eval_metrics['f1']:.4f}")

    st.markdown("")
    st.markdown("")
    st.markdown("**Hybrid AI Approach**")
    st.markdown(
        "**Predictive AI** scores churn risk per subscriber using GradientBoostingClassifier. "
        "**Generative AI** (Claude Sonnet 4.5) creates personalized Bahasa Indonesia retention messages. "
        "**Delivery** via Email (Gmail SMTP) and Voice Call (Twilio API) with rule-based template fallback."
    )

# ── Tab 1: Search & Predict ──────────────────────────────────────────────────
with tab1:
    st.markdown("")
    c1, c2, c3 = st.columns([2,1,1])
    with c1:
        search = st.text_input("Search by name, email, phone, or ID", placeholder="e.g. Agung, gmail, IOH-0003...")
    with c2:
        filter_risk = st.selectbox("Risk Level", ["All","High Risk (>70%)","Medium (40-70%)","Low Risk (<40%)"])
    with c3:
        filter_plan = st.selectbox("Plan Type", ["All","Postpaid","Prepaid"])

    results = df.copy()
    if search:
        mask = (df["name"].str.contains(search,case=False) |
                df["email"].str.contains(search,case=False) |
                df["whatsapp"].str.contains(search,case=False) |
                df["id"].str.contains(search,case=False))
        results = df[mask]
    if filter_plan != "All":
        results = results[results["plan_type"]==filter_plan]

    if results.empty:
        st.warning("No customer found. Try a different search.")
    else:
        Xi = results[["tenure","arpu","loyalty","interest","data_drop","topup_days","complaints","network"]].values
        probs = model.predict_proba(Xi)[:,1]
        probs = apply_overrides(results["id"].values, probs)
        results = results.copy()
        results["prob"] = probs

        if filter_risk == "High Risk (>70%)":    results = results[results["prob"]>=0.70]
        elif filter_risk == "Medium (40-70%)":   results = results[(results["prob"]>=0.40)&(results["prob"]<0.70)]
        elif filter_risk == "Low Risk (<40%)":   results = results[results["prob"]<0.40]

        st.markdown(f"**{len(results)} customer(s) found**")

        for _, row in results.iterrows():
            prob = row["prob"]

            # Check override BEFORE rendering expander header
            override_key = f"override_{row['id']}"
            current_override = st.session_state.get(override_key, "Use AI prediction")
            display_prob = prob
            is_overridden = current_override != "Use AI prediction"
            if is_overridden:
                if "HIGH" in current_override: display_prob = 0.85
                elif "MEDIUM" in current_override: display_prob = 0.55
                else: display_prob = 0.20

            # Determine workflow stage from session state
            fb_key = f"feedback_{row['id']}"
            review_key = f"reviewed_{row['id']}"
            sent_key = f"sent_{row['id']}"
            is_reviewed = st.session_state.get(review_key, False) or is_overridden
            is_sent = st.session_state.get(sent_key, False)
            has_feedback = fb_key in st.session_state

            # Build status for expander header
            rlabel, rcls = risk_label(display_prob)
            risk_dot = "🔴" if display_prob>=0.70 else "🟠" if display_prob>=0.40 else "🟢"
            if has_feedback:
                stage_tag = "  [DONE]"
            elif is_sent:
                stage_tag = "  [SENT]"
            elif is_reviewed:
                stage_tag = "  [REVIEWED]"
            else:
                stage_tag = ""

            with st.expander(f"{risk_dot}  {row['name']}  |  {row['plan_type']}  |  {rlabel} ({display_prob*100:.1f}%){stage_tag}"):

                # ── Step tracker ──────────────────────────────────────
                def step_style(active, done):
                    if done: return "background:#66BB6A; color:#1a1a1a; border:none;"
                    elif active: return "background:#EB1C24; color:white; border:none;"
                    else: return "background:transparent; color:#555; border:1px solid #333;"

                s1_done = True
                s2_done = is_reviewed
                s3_done = is_sent
                s4_done = has_feedback

                st.markdown(f"""<div style="display:flex; gap:4px; margin:4px 0 20px 0;">
                    <div style="flex:1; text-align:center; padding:8px; border-radius:4px; font-size:0.7rem; font-weight:600; {step_style(True, s1_done)}">1. AI SCORED</div>
                    <div style="flex:1; text-align:center; padding:8px; border-radius:4px; font-size:0.7rem; font-weight:600; {step_style(s1_done and not s2_done, s2_done)}">2. REVIEWED</div>
                    <div style="flex:1; text-align:center; padding:8px; border-radius:4px; font-size:0.7rem; font-weight:600; {step_style(s2_done and not s3_done, s3_done)}">3. CONTACTED</div>
                    <div style="flex:1; text-align:center; padding:8px; border-radius:4px; font-size:0.7rem; font-weight:600; {step_style(s3_done and not s4_done, s4_done)}">4. OUTCOME</div>
                </div>""", unsafe_allow_html=True)

                # ── Profile + Prediction ──────────────────────────────
                drivers = get_drivers(row)
                offer, benefit = get_offer(row["interest"], row["plan_type"])
                effective_prob = display_prob

                if is_overridden:
                    saved_reason = st.session_state.get(f"ov_reason_saved_{row['id']}", "")
                    override_driver = f"Marketer override: {saved_reason}" if saved_reason else "Marketer override (no reason given)"
                    drivers = [override_driver] + drivers

                p1, p2, p3 = st.columns(3)
                p1.metric("ID", row["id"])
                p2.metric("Plan", row["plan"])
                p3.metric("City", row["city"])

                p4, p5, p6 = st.columns(3)
                p4.metric("Tenure", f"{row['tenure']}d", tseg(row["tenure"]))
                p5.metric("ARPU", f"Rp {row['arpu']:,}", aseg(row["arpu"]))
                p6.metric("Loyalty", LOYALTY[row['loyalty']])

                p7, p8, p9 = st.columns(3)
                p7.metric("Data Drop", f"{row['data_drop']:.0f}%")
                p8.metric("Complaints", f"{row['complaints']} open")
                p9.metric("Network", f"{row['network']}/5")

                st.markdown("")
                pred_col, driver_col = st.columns([1, 2], gap="large")
                with pred_col:
                    st.metric("Churn Probability", f"{effective_prob*100:.1f}%", rlabel)
                    if is_overridden:
                        saved_reason = st.session_state.get(f"ov_reason_saved_{row['id']}", "")
                        st.caption(f"Override: {saved_reason}. AI was {prob*100:.1f}%.")
                with driver_col:
                    st.markdown("**Risk Drivers**")
                    for i, d in enumerate(drivers):
                        st.markdown(f"{i+1}. {d}")

                # ── Step 2: Marketer Decision ─────────────────────────
                st.markdown("")
                d1, d2, d3, d4 = st.columns(4)
                d1.button("Approve AI", key=f"approve_{row['id']}", on_click=lambda rid=row['id']: (
                    st.session_state.update({f"reviewed_{rid}": True})))
                d2.button("Escalate", key=f"escalate_{row['id']}", on_click=lambda rid=row['id']: (
                    st.session_state.update({
                        f"override_{rid}": "Override to HIGH RISK",
                        f"ov_reason_saved_{rid}": "Escalated by marketer",
                        f"reviewed_{rid}": True}),
                    st.session_state.pop(f"ai_msg_{rid}", None)))
                d3.button("Mark Safe", key=f"safe_{row['id']}", on_click=lambda rid=row['id']: (
                    st.session_state.update({
                        f"override_{rid}": "Override to LOW RISK",
                        f"ov_reason_saved_{rid}": "Marked safe by marketer",
                        f"reviewed_{rid}": True}),
                    st.session_state.pop(f"ai_msg_{rid}", None)))
                d4.button("Reset", key=f"reset_{row['id']}", on_click=lambda rid=row['id']: [
                    st.session_state.pop(k, None) for k in [
                        f"override_{rid}", f"reviewed_{rid}", f"sent_{rid}",
                        f"feedback_{rid}", f"ov_reason_saved_{rid}", f"ai_msg_{rid}"]])

                # ── Recommended actions (collapsed) ───────────────────
                with st.expander("Recommended actions"):
                    actions = marketer_actions(effective_prob, row["plan_type"], row["interest"], row["loyalty"])
                    for a in actions:
                        st.markdown(f"- {a}")

                # ── Step 3: Messages & Send ───────────────────────────
                st.markdown("")
                subject, email_body = generate_email_content(row, effective_prob, offer, benefit)
                call_msg = generate_call_script(row, effective_prob, offer, benefit)
                msg_source = "Template"
                ai_key = f"ai_msg_{row['id']}"
                if ai_key in st.session_state:
                    subject = st.session_state[ai_key]["subject"]
                    email_body = st.session_state[ai_key]["email"]
                    call_msg = st.session_state[ai_key].get("call", st.session_state[ai_key].get("sms", call_msg))
                    msg_source = "Claude AI"

                st.markdown(f"**Retention Messages** (`{msg_source}`)")
                if anthropic_key and ANTHROPIC_AVAILABLE:
                    if st.button("Generate with Claude AI", key=f"ai_{row['id']}"):
                        with st.spinner("Generating..."):
                            result = generate_with_claude(row, effective_prob, drivers, offer, benefit, anthropic_key)
                        if result:
                            st.session_state[ai_key] = {"subject": result[0], "email": result[1], "call": result[2]}
                            st.rerun()
                        else:
                            st.error("Generation failed.")

                email_col, call_col = st.columns(2, gap="medium")
                with email_col:
                    st.markdown(f"**Email** to `{row['email']}`")
                    st.caption(f"Subject: {subject}")
                    st.text_area("Email body", email_body, height=240, key=f"email_{row['id']}", label_visibility="collapsed")
                with call_col:
                    st.markdown(f"**Voice Call** to `{row['whatsapp']}`")
                    st.text_area("Call script", call_msg, height=240, key=f"call_{row['id']}", label_visibility="collapsed")

                se1, se2, se3, _ = st.columns([1, 1, 1, 1])
                if se1.button("Send Email", key=f"se_{row['id']}"):
                    if not gmail_app_pass:
                        st.error("Gmail App Password missing.")
                    else:
                        ok, msg = send_email(row["email"], subject, email_body, sender_email, gmail_app_pass)
                        if ok:
                            st.session_state[sent_key] = True
                            st.success(f"Email sent to {row['email']}")
                        else: st.error(f"Failed: {msg}")
                if se2.button("Call Customer", key=f"sw_{row['id']}"):
                    if not twilio_sid or not twilio_token or not twilio_from:
                        st.error("Twilio credentials missing.")
                    else:
                        ok, msg = send_call(row["whatsapp"], call_msg, twilio_sid, twilio_token, twilio_from)
                        if ok:
                            st.session_state[sent_key] = True
                            st.success(f"Calling {row['whatsapp']}...")
                        else: st.error(f"Failed: {msg}")
                if se3.button("Email + Call", key=f"sb_{row['id']}"):
                    errors = []
                    if gmail_app_pass:
                        ok, msg = send_email(row["email"], subject, email_body, sender_email, gmail_app_pass)
                        if not ok: errors.append(f"Email: {msg}")
                    else: errors.append("Gmail missing")
                    if twilio_sid and twilio_token and twilio_from:
                        ok, msg = send_call(row["whatsapp"], call_msg, twilio_sid, twilio_token, twilio_from)
                        if not ok: errors.append(f"Call: {msg}")
                    else: errors.append("Twilio missing")
                    if errors:
                        for e in errors: st.error(e)
                    else:
                        st.session_state[sent_key] = True
                        st.success(f"Email + call to {row['name']}")

                # ── Step 4: Outcome ───────────────────────────────────
                st.markdown("")
                st.markdown("**Record Outcome** (feeds into retraining)")
                fb1, fb2 = st.columns(2)
                with fb1:
                    fb_outcome = st.selectbox("Outcome",
                        ["Pending", "Retained (offer accepted)", "Retained (other reason)",
                         "Churned despite outreach", "Could not reach"],
                        key=f"fb_out_{row['id']}")
                with fb2:
                    fb_channel = st.selectbox("Channel",
                        ["Not contacted yet", "Email", "Voice call", "Phone call (manual)", "Branch visit"],
                        key=f"fb_ch_{row['id']}")
                fb_notes = st.text_input("Notes", placeholder="e.g., Customer asked for family plan instead",
                    key=f"fb_notes_{row['id']}")

                if st.button("Save outcome", key=f"fb_save_{row['id']}"):
                    st.session_state[fb_key] = {
                        "outcome": fb_outcome, "channel": fb_channel, "notes": fb_notes,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "model_prediction": f"{prob*100:.1f}%",
                        "override": st.session_state.get(override_key, "None"),
                    }
                    st.rerun()

                if has_feedback:
                    fb = st.session_state[fb_key]
                    st.success(f"Outcome: {fb['outcome']} via {fb['channel']} ({fb['timestamp']})")

# ── Tab 2: All Customers ─────────────────────────────────────────────────────
with tab2:
    st.markdown("")
    Xi2 = df[["tenure","arpu","loyalty","interest","data_drop","topup_days","complaints","network"]].values
    all_probs = apply_overrides(df["id"].values, model.predict_proba(Xi2)[:,1])
    disp = df.copy()
    disp["Churn Risk"]  = (all_probs*100).round(1).astype(str)+"%"
    disp["Risk Level"]  = ["🔴 HIGH" if p>=0.70 else "🟠 MED" if p>=0.40 else "🟢 LOW" for p in all_probs]
    disp["Loyalty"]     = disp["loyalty"].apply(lambda x: LOYALTY[x])
    disp["Interest"]    = disp["interest"].apply(lambda x: INTEREST[x])
    disp["ARPU"]        = disp["arpu"].apply(lambda x: f"Rp {x:,}")
    show = disp[["id","name","email","plan_type","city","tenure","ARPU","Loyalty","Churn Risk","Risk Level"]].rename(
        columns={"id":"ID","name":"Name","email":"Email",
                 "plan_type":"Plan","city":"City","tenure":"Tenure(d)"})
    st.dataframe(show, use_container_width=True, hide_index=True)

    st.markdown("")
    total=len(df); high=int(sum(all_probs>=0.70)); med=int(sum((all_probs>=0.40)&(all_probs<0.70))); low=int(sum(all_probs<0.40))
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Total", total)
    m2.metric("High Risk", high, f"{high/total*100:.0f}%")
    m3.metric("Medium Risk", med, f"{med/total*100:.0f}%")
    m4.metric("Low Risk", low, f"{low/total*100:.0f}%")

    # ── CSV Download ──────────────────────────────────────────────────────
    st.markdown("")
    st.markdown("**Export Risk Report**")
    export_df = df.copy()
    export_df["churn_probability"] = (all_probs * 100).round(1)
    export_df["risk_level"] = ["HIGH" if p>=0.70 else "MEDIUM" if p>=0.40 else "LOW" for p in all_probs]
    export_df["loyalty_tier"] = export_df["loyalty"].apply(lambda x: LOYALTY[x])
    export_df["interest_segment"] = export_df["interest"].apply(lambda x: INTEREST[x])
    csv_cols = ["id","name","email","whatsapp","plan_type","city","tenure","arpu",
                "loyalty_tier","interest_segment","data_drop","topup_days","complaints",
                "network","churn_probability","risk_level"]
    csv_data = export_df[csv_cols].to_csv(index=False)
    st.download_button(
        "Download full risk report (CSV)",
        csv_data,
        file_name=f"indosat_churn_risk_report_{datetime.today().strftime('%Y%m%d')}.csv",
        mime="text/csv")

    # ── Batch Email ───────────────────────────────────────────────────────
    st.markdown("")
    st.markdown("**Batch Actions**")
    high_risk_df = df[all_probs >= 0.70].copy()
    high_risk_df["prob"] = all_probs[all_probs >= 0.70]

    if len(high_risk_df) == 0:
        st.info("No high-risk customers to contact.")
    else:
        st.markdown(f"{len(high_risk_df)} high-risk customer(s) eligible for batch outreach.")
        if st.button(f"Send retention email to all {len(high_risk_df)} high-risk customers"):
            if not gmail_app_pass:
                st.error("Gmail App Password missing. Configure in sidebar.")
            else:
                sent = 0
                failed = 0
                progress = st.progress(0)
                for i, (_, r) in enumerate(high_risk_df.iterrows()):
                    offer, benefit = get_offer(r["interest"], r["plan_type"])
                    subj, body = generate_email_content(r, r["prob"], offer, benefit)
                    ok, _ = send_email(r["email"], subj, body, sender_email, gmail_app_pass)
                    if ok: sent += 1
                    else: failed += 1
                    progress.progress((i + 1) / len(high_risk_df))
                progress.empty()
                if failed == 0:
                    st.success(f"All {sent} emails sent successfully.")
                else:
                    st.warning(f"{sent} sent, {failed} failed.")

# ── Tab 5: What-If Simulator ─────────────────────────────────────────────────
with tab5:
    st.markdown("")
    st.markdown(
        "Adjust subscriber features and see how the churn prediction changes in real time. "
        "This demonstrates model interpretability: which factors drive churn risk up or down."
    )

    st.markdown("")
    sim1, sim2 = st.columns(2, gap="large")

    with sim1:
        st.markdown("**Subscriber Profile**")
        wi_tenure = st.slider("Tenure (days)", 0, 730, 180, key="wi_tenure")
        wi_arpu = st.slider("ARPU (Rp/month)", 5000, 350000, 75000, step=5000, key="wi_arpu")
        wi_loyalty = st.selectbox("Loyalty Tier", LOYALTY, index=1, key="wi_loyalty")
        wi_interest = st.selectbox("Interest Segment", INTEREST, index=0, key="wi_interest")

    with sim2:
        st.markdown("**Usage & Service**")
        wi_datadrop = st.slider("Data Usage Drop (%)", 0, 100, 25, key="wi_dd")
        wi_topup = st.slider("Days Since Last Top-up", 0, 60, 10, key="wi_topup")
        wi_complaints = st.slider("Open Complaints", 0, 6, 0, key="wi_compl")
        wi_network = st.slider("Network Quality Score", 1.0, 5.0, 3.5, step=0.1, key="wi_nq")

    wi_X = np.array([[wi_tenure, wi_arpu, LOYALTY.index(wi_loyalty), INTEREST.index(wi_interest),
                       wi_datadrop, wi_topup, wi_complaints, wi_network]])
    wi_prob = model.predict_proba(wi_X)[0, 1]
    wi_label, _ = risk_label(wi_prob)

    st.markdown("")
    box_cls = risk_box_class(wi_prob)
    badge = risk_badge_html(wi_prob)

    # Feature contributions (compare to baseline average)
    baseline_X = np.array([[365, 75000, 1, 0, 25, 10, 0, 3.5]])
    baseline_prob = model.predict_proba(baseline_X)[0, 1]
    diff = wi_prob - baseline_prob

    st.markdown(f"""<div class="{box_cls}">
        <div style="display:flex; align-items:center; gap:32px; flex-wrap:wrap;">
            <div>
                <div style="color:#888; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">Predicted Churn Risk</div>
                <div style="font-size:2.5rem; font-weight:700; margin-bottom:8px;">{wi_prob*100:.1f}%</div>
                {badge}
            </div>
            <div>
                <div style="color:#888; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">vs. Average Subscriber</div>
                <div style="font-size:1.5rem; font-weight:700;">{diff*100:+.1f}pp</div>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("")
    st.markdown("**Try these scenarios:**")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown(
            "**New price-sensitive user**  \n"
            "Tenure: 30, ARPU: 15000, Complaints: 2  \n"
            "Expected: HIGH RISK")
    with sc2:
        st.markdown(
            "**Loyal high-value user**  \n"
            "Tenure: 600, ARPU: 250000, Gold tier  \n"
            "Expected: LOW RISK")
    with sc3:
        st.markdown(
            "**Mid-tier with data drop**  \n"
            "Tenure: 200, Data drop: 70%, Complaints: 1  \n"
            "Expected: MEDIUM to HIGH")

# ── Tab 3: Model Evaluation ──────────────────────────────────────────────────
with tab3:
    st.markdown("")
    st.markdown("Evaluation on held-out test set (stratified split). Model: GradientBoostingClassifier, 100 trees, max depth 4.")

    st.markdown("")
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("AUC-ROC", f"{eval_metrics['auc']:.4f}")
    e2.metric("Precision", f"{eval_metrics['precision']:.4f}")
    e3.metric("Recall", f"{eval_metrics['recall']:.4f}")
    e4.metric("F1-Score", f"{eval_metrics['f1']:.4f}")

    st.markdown("")
    ev_left, ev_right = st.columns(2, gap="large")

    with ev_left:
        st.markdown("**Confusion Matrix**")
        cm = eval_metrics["cm"]
        cm_df = pd.DataFrame(
            [[cm[0,0], cm[0,1]], [cm[1,0], cm[1,1]]],
            index=["Actual: Retain", "Actual: Churn"],
            columns=["Pred: Retain", "Pred: Churn"]
        )
        st.dataframe(cm_df, use_container_width=True)

        st.markdown("")
        st.markdown("**Latency**")
        l1, l2 = st.columns(2)
        l1.metric("Training Time", f"{eval_metrics['train_time']:.2f}s")
        l2.metric("Per-sample", f"{eval_metrics['infer_per_sample_ms']:.3f} ms")

    with ev_right:
        st.markdown("**Feature Importance**")
        feat_eval = pd.DataFrame({
            "Feature": eval_metrics["features"],
            "Importance": eval_metrics["importances"]
        }).sort_values("Importance", ascending=False).set_index("Feature")
        st.bar_chart(feat_eval, color="#555555")

    # ── Go / No-Go ────────────────────────────────────────────────────────────
    st.markdown("")
    st.markdown("")
    st.markdown("**Go / No-Go Evaluation**")

    gng = pd.DataFrame([
        {"Metric": "AUC-ROC", "Target": ">= 0.80", "Actual": f"{eval_metrics['auc']:.4f}",
         "Status": "PASS" if eval_metrics['auc']>=0.80 else "FAIL"},
        {"Metric": "Recall", "Target": ">= 0.75", "Actual": f"{eval_metrics['recall']:.4f}",
         "Status": "PASS" if eval_metrics['recall']>=0.75 else "FAIL"},
        {"Metric": "Precision", "Target": ">= 0.60", "Actual": f"{eval_metrics['precision']:.4f}",
         "Status": "PASS" if eval_metrics['precision']>=0.60 else "FAIL"},
        {"Metric": "F1-score", "Target": ">= 0.67", "Actual": f"{eval_metrics['f1']:.4f}",
         "Status": "PASS" if eval_metrics['f1']>=0.67 else "FAIL"},
        {"Metric": "Latency", "Target": "< 5s", "Actual": f"{eval_metrics['infer_per_sample_ms']:.3f} ms",
         "Status": "PASS"},
    ])
    st.dataframe(gng, use_container_width=True, hide_index=True)

    all_pass = (eval_metrics['auc']>=0.80 and eval_metrics['recall']>=0.75
                and eval_metrics['precision']>=0.60 and eval_metrics['f1']>=0.67)
    if all_pass:
        st.success("RECOMMENDATION: GO. All pre-pilot thresholds passed.")
    else:
        st.warning("RECOMMENDATION: NEEDS REVIEW. Some thresholds not met.")

    # ── Baseline Comparison ───────────────────────────────────────────────────
    st.markdown("")
    st.markdown("")
    st.markdown("**Baseline Comparison**")
    st.markdown(
        "Three models evaluated on the same test set. Rule-based heuristic uses simple threshold rules "
        "(tenure < 100, data drop > 50%, complaints >= 2). Logistic Regression is a standard linear baseline."
    )
    baselines = eval_metrics["baselines"]
    bl_rows = []
    for name, m in baselines.items():
        bl_rows.append({
            "Model": name,
            "AUC-ROC": f"{m['auc']:.4f}",
            "Precision": f"{m['precision']:.4f}",
            "Recall": f"{m['recall']:.4f}",
            "F1": f"{m['f1']:.4f}",
        })
    st.dataframe(pd.DataFrame(bl_rows), use_container_width=True, hide_index=True)

    gb_auc = baselines["GradientBoosting"]["auc"]
    lr_auc = baselines["Logistic Regression"]["auc"]
    rb_auc = baselines["Rule-based Heuristic"]["auc"]
    st.markdown(
        f"GradientBoosting outperforms Logistic Regression by **{(gb_auc - lr_auc):.4f} AUC** "
        f"and the rule-based heuristic by **{(gb_auc - rb_auc):.4f} AUC**. "
        f"The ML approach captures non-linear feature interactions that simple rules miss."
    )

    # ── Business Impact ───────────────────────────────────────────────────────
    st.markdown("")
    st.markdown("")
    st.markdown("**Business Impact Estimation**")
    st.markdown(
        "Projections based on Indonesian telecom industry benchmarks: "
        "monthly churn rate 3-5% (GSMA Intelligence, 2023), "
        "CAC Rp 150,000-300,000, "
        "ARPU Rp 40,000/month (Indosat FY2024 annual report), "
        "average customer lifetime 24 months."
    )

    subscriber_base = 95_000_000
    monthly_churn_rate = 0.035
    monthly_churners = int(subscriber_base * monthly_churn_rate)
    avg_arpu = 40_000
    avg_cac = 225_000
    avg_lifetime_months = 24
    model_recall = eval_metrics["recall"]
    retention_success_rate = 0.25
    identifiable = int(monthly_churners * model_recall)
    retained = int(identifiable * retention_success_rate)
    revenue_saved_monthly = retained * avg_arpu * avg_lifetime_months

    bi1, bi2, bi3 = st.columns(3)
    bi1.metric("Churners Flagged/Month", f"{identifiable:,}")
    bi2.metric("Subscribers Retained", f"{retained:,}/mo")
    bi3.metric("Revenue Saved", f"Rp {revenue_saved_monthly/1e9:.1f}B/mo")

    with st.expander("Full business impact breakdown"):
        biz = pd.DataFrame([
            {"Metric": "IOH subscriber base", "Value": f"{subscriber_base:,}", "Source": "Indosat FY2024"},
            {"Metric": "Monthly churn rate", "Value": "3.5%", "Source": "GSMA Intelligence 2023"},
            {"Metric": "Monthly churners (est.)", "Value": f"{monthly_churners:,}", "Source": "Calculated"},
            {"Metric": "Average ARPU", "Value": f"Rp {avg_arpu:,}/mo", "Source": "Indosat FY2024"},
            {"Metric": "Customer acquisition cost", "Value": f"Rp {avg_cac:,}", "Source": "Industry benchmark"},
            {"Metric": "Model recall", "Value": f"{model_recall:.1%}", "Source": "Prototype eval"},
            {"Metric": "Churners flagged/month", "Value": f"{identifiable:,}", "Source": "Calculated"},
            {"Metric": "Retention rate (with offer)", "Value": "25%", "Source": "Industry benchmark"},
            {"Metric": "Subscribers retained/month", "Value": f"{retained:,}", "Source": "Calculated"},
            {"Metric": "Lifetime revenue saved/month", "Value": f"Rp {revenue_saved_monthly:,}", "Source": "Calculated"},
            {"Metric": "Annual revenue impact", "Value": f"Rp {revenue_saved_monthly*12:,}", "Source": "Calculated"},
        ])
        st.dataframe(biz, use_container_width=True, hide_index=True)

    # ── Edge Cases ────────────────────────────────────────────────────────────
    st.markdown("")
    st.markdown("")
    st.markdown("**Edge Cases and Known Failure Modes**")
    st.markdown(
        "Four stress scenarios drawn from real Indonesian telecom operations. Each perturbs the test data "
        "to simulate a market event the model was not trained for."
    )

    for scenario, data in eval_metrics["edge_cases"].items():
        with st.expander(f"{scenario}  /  AUC: {data['auc']:.4f}"):
            st.markdown(data['desc'])
            st.markdown("")
            ec1, ec2, ec3, ec4 = st.columns(4)
            ec1.metric("AUC-ROC", f"{data['auc']:.4f}",
                       f"{data['auc'] - eval_metrics['auc']:+.4f}")
            ec2.metric("Precision", f"{data['precision']:.4f}",
                       f"{data['precision'] - eval_metrics['precision']:+.4f}")
            ec3.metric("Recall", f"{data['recall']:.4f}",
                       f"{data['recall'] - eval_metrics['recall']:+.4f}")
            ec4.metric("F1", f"{data['f1']:.4f}",
                       f"{data['f1'] - eval_metrics['f1']:+.4f}")

# ── Tab 4: AI Architecture ───────────────────────────────────────────────────
with tab4:
    st.markdown("")
    st.markdown(
        "Indosat Ooredoo Hutchison (IOH) serves ~95 million subscribers in Indonesia. "
        "Churn pressure comes from SIM consolidation and competitive pricing. "
        "Retention today is **reactive**: teams respond only after a customer has churned. "
        "This system identifies at-risk subscribers in advance and delivers "
        "personalized retention offers before they leave."
    )

    st.markdown("")
    st.markdown("")
    st.markdown("**Hybrid AI Architecture**")
    col_pred, col_gen = st.columns(2, gap="large")
    with col_pred:
        st.markdown("**Predictive AI (Churn Scoring)**")
        st.markdown(
            "- **Model:** GradientBoostingClassifier (scikit-learn)\n"
            "- **Config:** 100 trees, max depth 4\n"
            "- **Task:** Supervised binary classification\n"
            "- **Features:** 8 per subscriber (tenure, ARPU, loyalty tier, interest, "
            "data usage drop, top-up recency, complaint count, network quality)\n"
            "- **Why:** Gradient boosted trees are industry-standard for tabular churn prediction"
        )
    with col_gen:
        st.markdown("**Generative AI (Message Personalization)**")
        st.markdown(
            "- **Model:** Anthropic Claude Sonnet 4.5 via API\n"
            "- **Task:** Generate personalized Bahasa Indonesia retention messages\n"
            "- **Input:** Customer profile + churn probability + risk drivers + recommended offer\n"
            "- **Output:** Unique Email + WhatsApp message per subscriber\n"
            "- **Fallback:** Rule-based templates if API is unavailable"
        )

    st.markdown("")
    st.markdown("")
    st.markdown("**AI Factory Architecture**")
    st.graphviz_chart("""
    digraph AIFactory {
        rankdir=TB;
        graph [fontname="Helvetica", bgcolor="transparent", pad="0.5"];
        node [fontname="Helvetica", fontsize=11, style="filled,rounded", shape=box];
        edge [fontname="Helvetica", fontsize=9, color="#666666"];

        subgraph cluster_data {
            label="Data Layer"; style="dashed"; color="#999999"; fontcolor="#666666";
            CDR [label="CDR\\n(Call Detail Records)", fillcolor="#FFEBEE"];
            CRM [label="CRM System", fillcolor="#FFEBEE"];
            Billing [label="Billing System", fillcolor="#FFEBEE"];
            CS [label="CS Tickets\\n(Unstructured)", fillcolor="#FFEBEE"];
            Network [label="Network Logs", fillcolor="#FFEBEE"];
        }

        subgraph cluster_pipeline {
            label="Processing Pipeline"; style="dashed"; color="#999999"; fontcolor="#666666";
            Ingest [label="Daily Ingestion\\n+ Validation", fillcolor="#FFF3E0"];
            NLP [label="NLP Preprocessing\\n(IndoBERT)", fillcolor="#FFF3E0"];
            Features [label="Feature Engineering\\n(Rolling Windows)", fillcolor="#FFF3E0"];
            Segment [label="4-Dimension\\nSegmentation", fillcolor="#FFF3E0"];
        }

        subgraph cluster_ai {
            label="AI Models"; style="dashed"; color="#999999"; fontcolor="#666666";
            Predictive [label="Predictive AI\\nGradientBoosting\\n(Churn Scoring)", fillcolor="#E3F2FD"];
            Generative [label="Generative AI\\nClaude Sonnet 4.5\\n(Message Personalization)", fillcolor="#E3F2FD"];
        }

        subgraph cluster_delivery {
            label="Delivery & Action"; style="dashed"; color="#999999"; fontcolor="#666666";
            Dashboard [label="Streamlit Dashboard\\n(Marketer UI)", fillcolor="#E8F5E9"];
            Email [label="Email\\n(Gmail SMTP)", fillcolor="#E8F5E9"];
            WhatsApp [label="WhatsApp\\n(Twilio API)", fillcolor="#E8F5E9"];
        }

        subgraph cluster_feedback {
            label="Feedback & Governance"; style="dashed"; color="#999999"; fontcolor="#666666";
            Monitor [label="Model Monitoring\\n(Drift Detection)", fillcolor="#F3E5F5"];
            Retrain [label="Monthly Retraining\\n(Champion-Challenger)", fillcolor="#F3E5F5"];
            Outcomes [label="Outcome Tracking\\n(Delivered/Opened/\\nRetained/Churned)", fillcolor="#F3E5F5"];
        }

        CDR -> Ingest; CRM -> Ingest; Billing -> Ingest; CS -> NLP; Network -> Ingest;
        NLP -> Features; Ingest -> Features;
        Features -> Segment;
        Segment -> Predictive;
        Predictive -> Generative [label="Risk scores +\\nTop drivers"];
        Predictive -> Dashboard [label="Churn probability"];
        Generative -> Email [label="Personalized\\nmessage"];
        Generative -> WhatsApp;
        Generative -> Dashboard;
        Email -> Outcomes; WhatsApp -> Outcomes; Dashboard -> Outcomes;
        Outcomes -> Monitor;
        Monitor -> Retrain [label="Drift alert"];
        Retrain -> Predictive [label="Updated model", style="dashed"];
        Retrain -> Generative [label="Updated prompts", style="dashed"];
    }
    """)

    st.markdown("")
    st.markdown("")
    st.markdown("**Technology Stack**")

    stack = pd.DataFrame([
        {"Component": "Predictive Model", "Technology": "scikit-learn GradientBoostingClassifier (prod: XGBoost / LightGBM)"},
        {"Component": "Generative Model", "Technology": "Anthropic Claude Sonnet 4.5 (anthropic Python SDK)"},
        {"Component": "UI / Dashboard", "Technology": "Streamlit (deployed on Streamlit Community Cloud)"},
        {"Component": "Email Delivery", "Technology": "Gmail SMTP (smtplib)"},
        {"Component": "WhatsApp Delivery", "Technology": "Twilio WhatsApp API"},
        {"Component": "Language", "Technology": "Python 3.11 (pandas, numpy, scikit-learn, anthropic, twilio)"},
        {"Component": "Deployment", "Technology": "GitHub -> Streamlit Cloud auto-deploy on push"},
        {"Component": "Secrets", "Technology": "Streamlit Cloud Secrets Manager (dev); AWS Secrets Manager (prod)"},
    ])
    st.dataframe(stack, use_container_width=True, hide_index=True)

    st.markdown("")
    st.markdown("")
    st.markdown("**Next Steps for Production**")
    st.markdown(
        "1. **Data quality sprint** — unify legacy Ooredoo + Hutchison subscriber IDs\n"
        "2. **Recalibration** — retrain on real post-merger data (expect AUC 0.80-0.85 range)\n"
        "3. **A/B pilot** — 10,000 subscribers, model-targeted vs. random retention outreach, "
        "two 30-day cycles\n"
        "4. **Go to production** only if pilot shows >= 10% churn reduction with statistical significance"
    )
