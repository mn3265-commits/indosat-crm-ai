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

st.set_page_config(page_title="Indosat CRM AI", page_icon="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect fill='%23EB1C24' width='100' height='100' rx='20'/><text x='50' y='70' font-size='60' text-anchor='middle' fill='white'>I</text></svg>", layout="wide")

# ── Indosat Brand Styling ─────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Header bar */
    header[data-testid="stHeader"] {
        background-color: #EB1C24;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
        border-bottom: 3px solid #EB1C24;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 24px;
        font-weight: 600;
        color: #555;
    }
    .stTabs [aria-selected="true"] {
        color: #EB1C24 !important;
        border-bottom: 3px solid #EB1C24;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: #f8f9fa;
        border-left: 4px solid #EB1C24;
        padding: 12px 16px;
        border-radius: 4px;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.3rem;
        font-weight: 700;
        color: #1a1a1a;
    }

    /* Expander */
    .streamlit-expanderHeader {
        font-weight: 600;
        font-size: 0.95rem;
    }

    /* Buttons */
    .stButton > button {
        background-color: #EB1C24;
        color: white;
        border: none;
        border-radius: 4px;
        font-weight: 600;
    }
    .stButton > button:hover {
        background-color: #c4161d;
        color: white;
    }

    /* Title area */
    .brand-header {
        background: linear-gradient(135deg, #EB1C24 0%, #c4161d 100%);
        color: white;
        padding: 24px 32px;
        border-radius: 8px;
        margin-bottom: 24px;
    }
    .brand-header h1 {
        color: white;
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .brand-header p {
        color: rgba(255,255,255,0.85);
        margin: 4px 0 0 0;
        font-size: 0.95rem;
    }

    /* Section headers */
    .section-header {
        color: #EB1C24;
        font-weight: 700;
        font-size: 1.1rem;
        border-bottom: 2px solid #EB1C24;
        padding-bottom: 6px;
        margin-top: 20px;
        margin-bottom: 12px;
    }

    /* Risk badges */
    .risk-high { color: #dc3545; font-weight: 700; }
    .risk-med { color: #e67e22; font-weight: 700; }
    .risk-low { color: #27ae60; font-weight: 700; }

    /* Pass/fail badges */
    .pass-badge {
        background: #d4edda; color: #155724;
        padding: 2px 10px; border-radius: 12px;
        font-weight: 600; font-size: 0.85rem;
    }
    .fail-badge {
        background: #f8d7da; color: #721c24;
        padding: 2px 10px; border-radius: 12px;
        font-weight: 600; font-size: 0.85rem;
    }

    /* Clean dividers */
    hr { border: none; border-top: 1px solid #e0e0e0; margin: 20px 0; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #1a1a1a;
    }
    [data-testid="stSidebar"] * {
        color: #e0e0e0 !important;
    }
    [data-testid="stSidebar"] .stTextInput label {
        color: #aaa !important;
    }
</style>
""", unsafe_allow_html=True)

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
_TWILIO_WA_FROM  = _get_secret("TWILIO_WA_FROM", "whatsapp:+14155238886")

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

    st.markdown("---")
    st.markdown("**Gmail SMTP**")
    sender_email   = st.text_input("Your Gmail", value=_GMAIL_ADDRESS)
    gmail_app_pass = st.text_input("Gmail App Password", value=_GMAIL_APP_PASS, type="password", placeholder="Leave blank if using Secrets")

    st.markdown("---")
    st.markdown("**Twilio WhatsApp**")
    twilio_sid     = st.text_input("Twilio Account SID", value=_TWILIO_SID, type="password")
    twilio_token   = st.text_input("Twilio Auth Token", value=_TWILIO_TOKEN, type="password")
    twilio_wa_from = st.text_input("Twilio WhatsApp Number", value=_TWILIO_WA_FROM)

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

def send_whatsapp(to_number, message, sid, token, from_number):
    if not TWILIO_AVAILABLE:
        return False, "Twilio library not installed. Run: pip install twilio"
    try:
        client = TwilioClient(sid, token)
        wa_to  = f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number
        client.messages.create(body=message, from_=from_number, to=wa_to)
        return True, "WhatsApp message sent successfully."
    except Exception as e:
        return False, str(e)

# ── Synthetic customer database ───────────────────────────────────────────────
@st.cache_resource
def generate_customers():
    random.seed(42); np.random.seed(42)
    customers = [
        {"name":"Agung Nugroho",  "email":"mn3265@columbia.edu",       "whatsapp":"+16469890162", "plan_type":"Postpaid"},
        {"name":"Budi Santoso",   "email":"budi.santoso@gmail.com",    "whatsapp":"+6281234560001","plan_type":"Postpaid"},
        {"name":"Siti Rahayu",    "email":"siti.rahayu@yahoo.com",     "whatsapp":"+6281234560002","plan_type":"Prepaid"},
        {"name":"Ahmad Fauzi",    "email":"ahmad.fauzi@gmail.com",     "whatsapp":"+6281234560003","plan_type":"Postpaid"},
        {"name":"Dewi Lestari",   "email":"dewi.lestari@outlook.com",  "whatsapp":"+6281234560004","plan_type":"Postpaid"},
        {"name":"Rizky Pratama",  "email":"rizky.pratama@gmail.com",   "whatsapp":"+6281234560005","plan_type":"Prepaid"},
        {"name":"Nurul Hidayah",  "email":"nurul.hidayah@gmail.com",   "whatsapp":"+6281234560006","plan_type":"Postpaid"},
        {"name":"Andi Wijaya",    "email":"andi.wijaya@gmail.com",     "whatsapp":"+6281234560007","plan_type":"Prepaid"},
        {"name":"Fitri Handayani","email":"fitri.handayani@yahoo.com", "whatsapp":"+6281234560008","plan_type":"Postpaid"},
        {"name":"Deni Kurniawan", "email":"deni.kurniawan@gmail.com",  "whatsapp":"+6281234560009","plan_type":"Prepaid"},
        {"name":"Maya Putri",     "email":"maya.putri@outlook.com",    "whatsapp":"+6281234560010","plan_type":"Postpaid"},
        {"name":"Hendra Gunawan", "email":"hendra.gunawan@gmail.com",  "whatsapp":"+6281234560011","plan_type":"Postpaid"},
        {"name":"Rina Susanti",   "email":"rina.susanti@gmail.com",    "whatsapp":"+6281234560012","plan_type":"Prepaid"},
        {"name":"Fajar Setiawan", "email":"fajar.setiawan@gmail.com",  "whatsapp":"+6281234560013","plan_type":"Postpaid"},
        {"name":"Lina Marlina",   "email":"lina.marlina@yahoo.com",    "whatsapp":"+6281234560014","plan_type":"Prepaid"},
        {"name":"Bagas Prabowo",  "email":"bagas.prabowo@gmail.com",   "whatsapp":"+6281234560015","plan_type":"Postpaid"},
        {"name":"Indah Permata",  "email":"indah.permata@outlook.com", "whatsapp":"+6281234560016","plan_type":"Prepaid"},
        {"name":"Roni Saputra",   "email":"roni.saputra@gmail.com",    "whatsapp":"+6281234560017","plan_type":"Postpaid"},
        {"name":"Wulan Sari",     "email":"wulan.sari@gmail.com",      "whatsapp":"+6281234560018","plan_type":"Prepaid"},
        {"name":"Agus Hartono",   "email":"agus.hartono@gmail.com",    "whatsapp":"+6281234560019","plan_type":"Postpaid"},
        {"name":"Citra Dewi",     "email":"citra.dewi@yahoo.com",      "whatsapp":"+6281234560020","plan_type":"Postpaid"},
    ]
    plans_post = ["Postpaid Freedom 50","Postpaid Business Pro","Postpaid Platinum","Postpaid Family"]
    plans_pre  = ["Prepaid Freedom","Prepaid Social","Prepaid Gaming","Prepaid Basic"]
    cities     = ["Jakarta","Surabaya","Bandung","Medan","Semarang","Makassar","Yogyakarta"]
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
    X_tr,X_te,y_tr,y_te = train_test_split(X,ch,test_size=0.15,random_state=42,stratify=ch)
    X_tr,X_va,y_tr,y_va = train_test_split(X_tr,y_tr,test_size=0.176,random_state=42,stratify=y_tr)
    t0=_time.time()
    m=GradientBoostingClassifier(n_estimators=100,max_depth=4,random_state=42)
    m.fit(X_tr,y_tr)
    train_time=_time.time()-t0
    t1=_time.time()
    y_pred=m.predict(X_te); y_prob=m.predict_proba(X_te)[:,1]
    infer_time=_time.time()-t1
    features=['Tenure','ARPU','Loyalty','Interest','Data Drop','Top-up Days','Complaints','Network Quality']
    imp=m.feature_importances_
    return {
        "auc": roc_auc_score(y_te, y_prob),
        "accuracy": accuracy_score(y_te, y_pred),
        "precision": precision_score(y_te, y_pred),
        "recall": recall_score(y_te, y_pred),
        "f1": f1_score(y_te, y_pred),
        "cm": confusion_matrix(y_te, y_pred),
        "train_time": train_time,
        "infer_time_ms": infer_time*1000,
        "infer_per_sample_ms": infer_time*1000/len(X_te),
        "n_train": len(X_tr), "n_val": len(X_va), "n_test": len(X_te),
        "features": features,
        "importances": imp,
        "y_prob": y_prob, "y_te": y_te,
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
        actions.append("URGENT — Send retention offer within 24 hours via Email + WhatsApp")
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

def generate_whatsapp(row, prob, offer, benefit):
    first = row["name"].split()[0]
    if prob >= 0.70:
        return f"""Halo *{first}*!

Kami dari *Indosat Ooredoo Hutchison* ingin menyampaikan penawaran spesial yang kami siapkan khusus untukmu.

*HADIAH EKSKLUSIF UNTUKMU:*
- {offer.capitalize()}
- {benefit.capitalize()}

Penawaran ini hanya berlaku *48 jam* dan khusus untuk {first} saja.

Cara klaim:
1. Buka aplikasi myIM3
2. Masuk ke "Penawaran Spesial"
3. Tap *Klaim Sekarang*

Atau balas pesan ini dengan *YA* dan tim kami siap membantu!

_Indosat Care - 185_"""

    elif prob >= 0.40:
        return f"""Halo *{first}*!

Ada kabar baik dari *Indosat Ooredoo Hutchison* khusus untukmu!

*PENAWARAN UPGRADE EKSKLUSIF:*
- {offer.capitalize()}
- {benefit.capitalize()}

Penawaran ini tersedia *7 hari ke depan* dan hanya untuk {first}.

Aktifkan sekarang di aplikasi *myIM3* > menu Upgrade Paket.

Ada pertanyaan? Balas pesan ini ya!

_Indosat Care - 185_"""

    else:
        return f"""Halo *{first}*!

Terima kasih sudah setia bersama *Indosat* selama {row['tenure']} hari!

*HADIAH LOYALITAS BULAN INI:*
- Poin reward 2x lipat untuk semua transaksi
- Akses eksklusif penawaran member

Tukar poinmu sekarang di *myIM3* > menu Poin & Reward.

Terima kasih, {first}! Kami senang kamu bersama kami.

_Indosat Care - 185_"""

# ── MAIN UI ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="brand-header">
    <h1>Indosat CRM AI</h1>
    <p>Customer Intelligence Platform — AI-powered churn prediction and personalized retention</p>
</div>
""", unsafe_allow_html=True)

tab0, tab1, tab2, tab3, tab4 = st.tabs([
    "Dashboard", "Search & Predict", "All Customers",
    "Model Evaluation", "AI Architecture"])

# ── Tab 0: Dashboard ─────────────────────────────────────────────────────────
with tab0:
    st.markdown('<div class="section-header">Executive Summary</div>', unsafe_allow_html=True)

    Xi_all = df[["tenure","arpu","loyalty","interest","data_drop","topup_days","complaints","network"]].values
    probs_all = model.predict_proba(Xi_all)[:,1]
    n_total = len(df)
    n_high = int((probs_all >= 0.70).sum())
    n_med = int(((probs_all >= 0.40) & (probs_all < 0.70)).sum())
    n_low = int((probs_all < 0.40).sum())
    n_post = int((df["plan_type"]=="Postpaid").sum())
    n_pre = n_total - n_post

    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("Total Customers", n_total)
    d2.metric("High Risk", n_high, f"{n_high/n_total*100:.0f}%")
    d3.metric("Medium Risk", n_med, f"{n_med/n_total*100:.0f}%")
    d4.metric("Low Risk", n_low, f"{n_low/n_total*100:.0f}%")
    d5.metric("Postpaid / Prepaid", f"{n_post} / {n_pre}")

    st.markdown("---")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<div class="section-header">Risk Distribution</div>', unsafe_allow_html=True)
        risk_df = pd.DataFrame({
            "Risk Level": ["High (>=70%)", "Medium (40-70%)", "Low (<40%)"],
            "Count": [n_high, n_med, n_low]
        }).set_index("Risk Level")
        st.bar_chart(risk_df, color="#EB1C24")

    with col_right:
        st.markdown('<div class="section-header">Feature Importance</div>', unsafe_allow_html=True)
        feat_df = pd.DataFrame({
            "Feature": eval_metrics["features"],
            "Importance": eval_metrics["importances"]
        }).sort_values("Importance", ascending=False).set_index("Feature")
        st.bar_chart(feat_df, color="#FEDD00")

    st.markdown("---")
    st.markdown('<div class="section-header">Model Performance (Test Set)</div>', unsafe_allow_html=True)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("AUC-ROC", f"{eval_metrics['auc']:.4f}")
    k2.metric("Accuracy", f"{eval_metrics['accuracy']:.4f}")
    k3.metric("Precision", f"{eval_metrics['precision']:.4f}")
    k4.metric("Recall", f"{eval_metrics['recall']:.4f}")
    k5.metric("F1-Score", f"{eval_metrics['f1']:.4f}")

    st.markdown("---")
    st.markdown('<div class="section-header">Hybrid AI Architecture</div>', unsafe_allow_html=True)
    st.info(
        "**Predictive AI** — GradientBoostingClassifier scores churn risk per subscriber.  \n"
        "**Generative AI** — Anthropic Claude Sonnet 4.5 generates personalized Bahasa Indonesia retention messages.  \n"
        "**Delivery** — Email (Gmail SMTP) + WhatsApp (Twilio API) with rule-based template fallback."
    )

# ── Tab 1: Search & Predict ──────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="section-header">Search Customer</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2,1,1])
    with c1:
        search = st.text_input("Search by name, email, WhatsApp, or ID", placeholder="e.g. Agung, gmail, IOH-0003...")
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
        results = results.copy()
        results["prob"] = probs

        if filter_risk == "High Risk (>70%)":    results = results[results["prob"]>=0.70]
        elif filter_risk == "Medium (40-70%)":   results = results[(results["prob"]>=0.40)&(results["prob"]<0.70)]
        elif filter_risk == "Low Risk (<40%)":   results = results[results["prob"]<0.40]

        st.markdown(f"**{len(results)} customer(s) found**")

        for _, row in results.iterrows():
            prob = row["prob"]
            rlabel, rcls = risk_label(prob)

            with st.expander(f"{row['name']}  |  {row['email']}  |  {row['plan_type']}  |  {rlabel} ({prob*100:.1f}%)"):

                st.markdown('<div class="section-header">Customer Profile</div>', unsafe_allow_html=True)
                p1,p2,p3,p4,p5 = st.columns(5)
                p1.metric("ID", row["id"])
                p2.metric("Email", row["email"])
                p3.metric("WhatsApp", row["whatsapp"])
                p4.metric("City", row["city"])
                p5.metric("Plan Type", row["plan_type"])

                p6,p7,p8,p9,p10 = st.columns(5)
                p6.metric("Active Plan", row["plan"])
                p7.metric("Tenure", f"{row['tenure']}d", tseg(row["tenure"]))
                p8.metric("ARPU/mo", f"Rp {row['arpu']:,}", aseg(row["arpu"]))
                p9.metric("Last Top-up", row["last_active"])
                p10.metric("Complaints", f"{row['complaints']} open")

                p11,p12,p13,p14 = st.columns(4)
                p11.metric("Loyalty", LOYALTY[row['loyalty']])
                p12.metric("Interest", INTEREST[row['interest']])
                p13.metric("Data Drop", f"{row['data_drop']:.0f}%")
                p14.metric("Network Score", f"{row['network']}/5")
                st.markdown("---")

                st.markdown('<div class="section-header">AI Churn Prediction</div>', unsafe_allow_html=True)
                pa, pb = st.columns([1,2])
                with pa:
                    st.metric("Churn Probability", f"{prob*100:.1f}%", rlabel)
                with pb:
                    drivers = get_drivers(row)
                    st.markdown("**Top Risk Drivers:**")
                    for i,d in enumerate(drivers): st.markdown(f"{i+1}. {d}")
                st.markdown("---")

                st.markdown('<div class="section-header">Marketer Action Plan</div>', unsafe_allow_html=True)
                actions = marketer_actions(prob, row["plan_type"], row["interest"], row["loyalty"])
                for a in actions: st.markdown(f"- {a}")
                st.markdown("---")

                offer, benefit = get_offer(row["interest"], row["plan_type"])
                subject, email_body = generate_email_content(row, prob, offer, benefit)
                wa_msg = generate_whatsapp(row, prob, offer, benefit)

                st.markdown('<div class="section-header">Personalized Messages</div>', unsafe_allow_html=True)
                mt1, mt2 = st.tabs(["Email", "WhatsApp"])

                with mt1:
                    st.markdown(f"**To:** `{row['email']}`")
                    st.markdown(f"**Subject:** `{subject}`")
                    st.text_area("Email Body", email_body, height=320, key=f"email_{row['id']}")

                with mt2:
                    st.markdown(f"**To:** `{row['whatsapp']}`")
                    st.text_area("WhatsApp Message", wa_msg, height=220, key=f"wa_{row['id']}")

                st.markdown("---")
                st.markdown('<div class="section-header">Send to Customer</div>', unsafe_allow_html=True)
                now = datetime.now().strftime("%H:%M:%S")
                b1,b2,b3 = st.columns(3)

                if b1.button("Send Email", key=f"se_{row['id']}"):
                    if not gmail_app_pass:
                        st.error("Please enter your Gmail App Password in the sidebar.")
                    else:
                        ok, msg = send_email(row["email"], subject, email_body, sender_email, gmail_app_pass)
                        if ok: st.success(f"Email sent to {row['email']} at {now}")
                        else:  st.error(f"Failed: {msg}")

                if b2.button("Send WhatsApp", key=f"sw_{row['id']}"):
                    if not twilio_sid or not twilio_token or not twilio_wa_from:
                        st.error("Please enter Twilio credentials in the sidebar.")
                    else:
                        ok, msg = send_whatsapp(row["whatsapp"], wa_msg, twilio_sid, twilio_token, twilio_wa_from)
                        if ok: st.success(f"WhatsApp sent to {row['whatsapp']} at {now}")
                        else:  st.error(f"Failed: {msg}")

                if b3.button("Send Both", key=f"sb_{row['id']}"):
                    errors = []
                    if not gmail_app_pass:
                        errors.append("Gmail App Password missing")
                    else:
                        ok, msg = send_email(row["email"], subject, email_body, sender_email, gmail_app_pass)
                        if not ok: errors.append(f"Email: {msg}")
                    if not twilio_sid or not twilio_token or not twilio_wa_from:
                        errors.append("Twilio credentials missing")
                    else:
                        ok, msg = send_whatsapp(row["whatsapp"], wa_msg, twilio_sid, twilio_token, twilio_wa_from)
                        if not ok: errors.append(f"WhatsApp: {msg}")
                    if errors:
                        for e in errors: st.error(f"Failed: {e}")
                    else:
                        st.success(f"Email + WhatsApp sent to {row['name']} at {now}")

# ── Tab 2: All Customers ─────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="section-header">All Customers Overview</div>', unsafe_allow_html=True)
    Xi2 = df[["tenure","arpu","loyalty","interest","data_drop","topup_days","complaints","network"]].values
    all_probs = model.predict_proba(Xi2)[:,1]
    disp = df.copy()
    disp["Churn Risk"]  = (all_probs*100).round(1).astype(str)+"%"
    disp["Risk Level"]  = ["HIGH" if p>=0.70 else "MED" if p>=0.40 else "LOW" for p in all_probs]
    disp["Loyalty"]     = disp["loyalty"].apply(lambda x: LOYALTY[x])
    disp["Interest"]    = disp["interest"].apply(lambda x: INTEREST[x])
    disp["ARPU"]        = disp["arpu"].apply(lambda x: f"Rp {x:,}")
    show = disp[["id","name","email","whatsapp","plan_type","city","tenure","ARPU","Loyalty","Interest","Churn Risk","Risk Level"]].rename(
        columns={"id":"ID","name":"Name","email":"Email","whatsapp":"WhatsApp",
                 "plan_type":"Plan","city":"City","tenure":"Tenure(d)"})
    st.dataframe(show, use_container_width=True, hide_index=True)
    st.markdown("---")
    total=len(df); high=sum(all_probs>=0.70); med=sum((all_probs>=0.40)&(all_probs<0.70)); low=sum(all_probs<0.40); post=len(df[df["plan_type"]=="Postpaid"])
    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("Total Customers", total)
    m2.metric("High Risk", high, f"{high/total*100:.0f}%")
    m3.metric("Medium Risk", med, f"{med/total*100:.0f}%")
    m4.metric("Low Risk", low, f"{low/total*100:.0f}%")
    m5.metric("Postpaid", post, f"{post/total*100:.0f}% of total")

# ── Tab 3: Model Evaluation ──────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="section-header">Prototype Model Evaluation</div>', unsafe_allow_html=True)
    st.markdown("Evaluation on held-out test set using stratified split. Model: `GradientBoostingClassifier(n_estimators=100, max_depth=4)`.")

    st.markdown('<div class="section-header">Dataset Split</div>', unsafe_allow_html=True)
    sp1, sp2, sp3 = st.columns(3)
    sp1.metric("Train", f"{eval_metrics['n_train']} samples")
    sp2.metric("Validation", f"{eval_metrics['n_val']} samples")
    sp3.metric("Test", f"{eval_metrics['n_test']} samples")

    st.markdown("---")
    st.markdown('<div class="section-header">Performance Metrics</div>', unsafe_allow_html=True)
    e1, e2, e3, e4, e5 = st.columns(5)
    e1.metric("AUC-ROC", f"{eval_metrics['auc']:.4f}")
    e2.metric("Accuracy", f"{eval_metrics['accuracy']:.4f}")
    e3.metric("Precision", f"{eval_metrics['precision']:.4f}")
    e4.metric("Recall", f"{eval_metrics['recall']:.4f}")
    e5.metric("F1-Score", f"{eval_metrics['f1']:.4f}")

    st.markdown("---")
    st.markdown('<div class="section-header">Latency</div>', unsafe_allow_html=True)
    l1, l2, l3 = st.columns(3)
    l1.metric("Training Time", f"{eval_metrics['train_time']:.2f}s")
    l2.metric(f"Inference (batch {eval_metrics['n_test']})", f"{eval_metrics['infer_time_ms']:.1f} ms")
    l3.metric("Per-sample Latency", f"{eval_metrics['infer_per_sample_ms']:.3f} ms")

    st.markdown("---")
    cm = eval_metrics["cm"]
    st.markdown('<div class="section-header">Confusion Matrix</div>', unsafe_allow_html=True)
    cm_df = pd.DataFrame(
        [[cm[0,0], cm[0,1]], [cm[1,0], cm[1,1]]],
        index=["Actual: Retain", "Actual: Churn"],
        columns=["Predicted: Retain", "Predicted: Churn"]
    )
    st.dataframe(cm_df, use_container_width=False)

    st.markdown("---")
    st.markdown('<div class="section-header">Feature Importance Ranking</div>', unsafe_allow_html=True)
    feat_eval = pd.DataFrame({
        "Feature": eval_metrics["features"],
        "Importance": eval_metrics["importances"]
    }).sort_values("Importance", ascending=False).set_index("Feature")
    st.bar_chart(feat_eval, color="#EB1C24")

    st.markdown("---")
    st.markdown('<div class="section-header">Go / No-Go Evaluation</div>', unsafe_allow_html=True)

    def _status_html(passed):
        return '<span class="pass-badge">PASS</span>' if passed else '<span class="fail-badge">FAIL</span>'

    gng_data = [
        ("AUC-ROC", ">= 0.80", f"{eval_metrics['auc']:.4f}", eval_metrics['auc']>=0.80),
        ("Recall (churn)", ">= 0.75", f"{eval_metrics['recall']:.4f}", eval_metrics['recall']>=0.75),
        ("Precision (churn)", ">= 0.60", f"{eval_metrics['precision']:.4f}", eval_metrics['precision']>=0.60),
        ("F1-score", ">= 0.67", f"{eval_metrics['f1']:.4f}", eval_metrics['f1']>=0.67),
        ("Latency / sample", "< 5s", f"{eval_metrics['infer_per_sample_ms']:.3f} ms", True),
    ]
    gng_html = """<table style="width:100%; border-collapse:collapse; font-size:0.9rem;">
    <tr style="border-bottom:2px solid #EB1C24; text-align:left;">
        <th style="padding:8px;">Metric</th><th style="padding:8px;">Target</th>
        <th style="padding:8px;">Actual</th><th style="padding:8px;">Status</th></tr>"""
    for metric, target, actual, passed in gng_data:
        gng_html += f"""<tr style="border-bottom:1px solid #eee;">
        <td style="padding:8px;">{metric}</td><td style="padding:8px;">{target}</td>
        <td style="padding:8px; font-weight:700;">{actual}</td><td style="padding:8px;">{_status_html(passed)}</td></tr>"""
    gng_html += "</table>"
    st.markdown(gng_html, unsafe_allow_html=True)

    all_pass = all(p for _,_,_,p in gng_data)
    st.markdown("")
    if all_pass:
        st.success("**RECOMMENDATION: GO** — All pre-pilot thresholds passed by significant margins.")
    else:
        st.warning("**RECOMMENDATION: NEEDS REVIEW** — Some thresholds not met.")

    st.markdown("---")
    st.markdown('<div class="section-header">Risk Distribution (Test Set)</div>', unsafe_allow_html=True)
    y_prob = eval_metrics["y_prob"]
    n_te = len(y_prob)
    hi = int((y_prob >= 0.70).sum())
    mi = int(((y_prob >= 0.40) & (y_prob < 0.70)).sum())
    li = int((y_prob < 0.40).sum())
    r1, r2, r3 = st.columns(3)
    r1.metric("HIGH risk (>=70%)", f"{hi} ({100*hi/n_te:.1f}%)")
    r2.metric("MEDIUM risk (40-70%)", f"{mi} ({100*mi/n_te:.1f}%)")
    r3.metric("LOW risk (<40%)", f"{li} ({100*li/n_te:.1f}%)")

# ── Tab 4: AI Architecture ───────────────────────────────────────────────────
with tab4:
    st.markdown('<div class="section-header">AI Solution Architecture</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-header">Problem Statement</div>', unsafe_allow_html=True)
    st.markdown(
        "Indosat Ooredoo Hutchison (IOH) serves ~95 million subscribers in Indonesia. "
        "Churn pressure comes from SIM consolidation and competitive pricing. "
        "Retention today is **reactive** — teams respond only after a customer has churned. "
        "There is no system to identify at-risk subscribers in advance and deliver "
        "personalized retention offers before they leave."
    )

    st.markdown("---")
    st.markdown('<div class="section-header">Hybrid AI Architecture</div>', unsafe_allow_html=True)
    col_pred, col_gen = st.columns(2)
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

    st.markdown("---")
    st.markdown('<div class="section-header">Data Pipeline</div>', unsafe_allow_html=True)
    st.code("""Raw Data (CDR, CRM, Billing, CS Tickets, Network Logs)
   -> Daily ingestion + NLP preprocessing (IndoBERT for Bahasa Indonesia sentiment)
   -> Feature engineering (7d/14d/30d rolling windows) + 4-dimension segmentation
   -> Predictive model: daily batch scoring -> churn probability per subscriber
   -> Generative model: personalized retention message per flagged subscriber
   -> Delivery (Email via Gmail SMTP, WhatsApp via Twilio API)
   -> Feedback loop: outcomes (delivered / opened / retained / churned) feed monthly retraining""", language=None)

    st.markdown("---")
    st.markdown('<div class="section-header">Technology Stack</div>', unsafe_allow_html=True)

    stack_html = """<table style="width:100%; border-collapse:collapse; font-size:0.9rem;">
    <tr style="border-bottom:2px solid #EB1C24; text-align:left;">
        <th style="padding:8px; width:25%;">Component</th><th style="padding:8px;">Technology</th></tr>
    <tr style="border-bottom:1px solid #eee;"><td style="padding:8px; font-weight:600;">Predictive Model</td><td style="padding:8px;">scikit-learn GradientBoostingClassifier (prod: XGBoost / LightGBM)</td></tr>
    <tr style="border-bottom:1px solid #eee;"><td style="padding:8px; font-weight:600;">Generative Model</td><td style="padding:8px;">Anthropic Claude Sonnet 4.5 (anthropic Python SDK)</td></tr>
    <tr style="border-bottom:1px solid #eee;"><td style="padding:8px; font-weight:600;">UI / Dashboard</td><td style="padding:8px;">Streamlit (deployed on Streamlit Community Cloud)</td></tr>
    <tr style="border-bottom:1px solid #eee;"><td style="padding:8px; font-weight:600;">Email Delivery</td><td style="padding:8px;">Gmail SMTP (smtplib)</td></tr>
    <tr style="border-bottom:1px solid #eee;"><td style="padding:8px; font-weight:600;">WhatsApp Delivery</td><td style="padding:8px;">Twilio WhatsApp API</td></tr>
    <tr style="border-bottom:1px solid #eee;"><td style="padding:8px; font-weight:600;">Language</td><td style="padding:8px;">Python 3.11 (pandas, numpy, scikit-learn, anthropic, twilio)</td></tr>
    <tr style="border-bottom:1px solid #eee;"><td style="padding:8px; font-weight:600;">Deployment</td><td style="padding:8px;">GitHub -> Streamlit Cloud auto-deploy on push</td></tr>
    <tr style="border-bottom:1px solid #eee;"><td style="padding:8px; font-weight:600;">Secrets</td><td style="padding:8px;">Streamlit Cloud Secrets Manager (dev); AWS Secrets Manager (prod)</td></tr>
    </table>"""
    st.markdown(stack_html, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-header">Next Steps for Production</div>', unsafe_allow_html=True)
    st.markdown(
        "1. **Data quality sprint** — unify legacy Ooredoo + Hutchison subscriber IDs\n"
        "2. **Recalibration** — retrain on real post-merger data (expect AUC 0.80-0.85 range)\n"
        "3. **A/B pilot** — 10,000 subscribers, model-targeted vs. random retention outreach, "
        "two 30-day cycles\n"
        "4. **Go to production** only if pilot shows >= 10% churn reduction with statistical significance"
    )
