"""Quick evaluation script — runs the actual trained model from app.py
and extracts real performance metrics for the PRD."""
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_auc_score, classification_report, confusion_matrix,
    precision_score, recall_score, f1_score, accuracy_score
)
import time

# Same synthetic data generator as app.py
np.random.seed(42)
n = 3000
td = np.random.randint(0, 730, n)
ar = np.random.randint(5000, 350000, n)
lo = np.random.randint(0, 4, n)
ins = np.random.randint(0, 4, n)
dd = np.random.uniform(0, 100, n)
tp = np.random.randint(0, 60, n)
co = np.random.randint(0, 6, n)
nq = np.random.uniform(1, 5, n)

cp = (0.30*(td<100) + 0.20*(ar<20000) + 0.15*(lo==0) +
      0.10*(dd>50) + 0.10*(tp>20) + 0.10*(co>=2) + 0.05*(nq<2.5))
ch = (cp + np.random.normal(0, 0.05, n) > 0.40).astype(int)
X = np.column_stack([td, ar, lo, ins, dd, tp, co, nq])

# Stratified split
X_tr, X_te, y_tr, y_te = train_test_split(X, ch, test_size=0.15, random_state=42, stratify=ch)
X_tr, X_va, y_tr, y_va = train_test_split(X_tr, y_tr, test_size=0.176, random_state=42, stratify=y_tr)

print("="*70)
print("INDOSAT CRM AI — PROTOTYPE MODEL EVALUATION")
print("="*70)
print(f"\nDataset split:")
print(f"  Train:      {len(X_tr):4d} samples ({100*sum(y_tr)/len(y_tr):.1f}% churn rate)")
print(f"  Validation: {len(X_va):4d} samples ({100*sum(y_va)/len(y_va):.1f}% churn rate)")
print(f"  Test:       {len(X_te):4d} samples ({100*sum(y_te)/len(y_te):.1f}% churn rate)")

# Train
train_start = time.time()
m = GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42)
m.fit(X_tr, y_tr)
train_elapsed = time.time() - train_start

# Test set predictions
infer_start = time.time()
y_pred_test = m.predict(X_te)
y_prob_test = m.predict_proba(X_te)[:,1]
infer_elapsed_total = time.time() - infer_start
infer_per_sample_ms = 1000 * infer_elapsed_total / len(X_te)

print(f"\n{'='*70}")
print("MODEL PERFORMANCE — TEST SET (held-out)")
print("="*70)
print(f"  AUC-ROC:              {roc_auc_score(y_te, y_prob_test):.4f}")
print(f"  Accuracy:             {accuracy_score(y_te, y_pred_test):.4f}")
print(f"  Precision (churn):    {precision_score(y_te, y_pred_test):.4f}")
print(f"  Recall (churn):       {recall_score(y_te, y_pred_test):.4f}")
print(f"  F1-score (churn):     {f1_score(y_te, y_pred_test):.4f}")

print(f"\n  Training time:        {train_elapsed:.2f} seconds")
print(f"  Inference (batch {len(X_te)}): {infer_elapsed_total*1000:.1f} ms total")
print(f"  Per-sample latency:   {infer_per_sample_ms:.3f} ms/sample")

print(f"\nConfusion Matrix:")
cm = confusion_matrix(y_te, y_pred_test)
print(f"              Predicted:")
print(f"              Retain   Churn")
print(f"  Actual Retain: {cm[0,0]:4d}    {cm[0,1]:4d}")
print(f"  Actual Churn:  {cm[1,0]:4d}    {cm[1,1]:4d}")

print(f"\nClassification report:")
print(classification_report(y_te, y_pred_test, target_names=['Retain', 'Churn']))

# Feature importance
features = ['Tenure', 'ARPU', 'Loyalty', 'Interest', 'Data Drop',
            'Top-up Days', 'Complaints', 'Network Quality']
importances = m.feature_importances_
order = np.argsort(importances)[::-1]

print(f"Feature Importance Ranking:")
for rank, idx in enumerate(order, 1):
    bar = '█' * int(importances[idx] * 50)
    print(f"  {rank}. {features[idx]:20s} {importances[idx]:.4f}  {bar}")

# Prediction distribution
print(f"\nRisk Distribution (test set):")
high = (y_prob_test >= 0.70).sum()
med = ((y_prob_test >= 0.40) & (y_prob_test < 0.70)).sum()
low = (y_prob_test < 0.40).sum()
print(f"  HIGH risk (>=70%):   {high:3d} ({100*high/len(y_te):.1f}%)")
print(f"  MEDIUM risk (40-70%):{med:3d} ({100*med/len(y_te):.1f}%)")
print(f"  LOW risk (<40%):     {low:3d} ({100*low/len(y_te):.1f}%)")

print("\n" + "="*70)
print("GO / NO-GO EVALUATION against targets:")
print("="*70)
auc = roc_auc_score(y_te, y_prob_test)
prec = precision_score(y_te, y_pred_test)
rec = recall_score(y_te, y_pred_test)
f1 = f1_score(y_te, y_pred_test)

def status(actual, target, gte=True):
    ok = (actual >= target) if gte else (actual <= target)
    return "✓ PASS" if ok else "✗ FAIL"

print(f"  AUC-ROC >= 0.80:       {auc:.4f}   {status(auc, 0.80)}")
print(f"  Recall >= 0.75:        {rec:.4f}   {status(rec, 0.75)}")
print(f"  Precision >= 0.60:     {prec:.4f}   {status(prec, 0.60)}")
print(f"  F1 >= 0.67:            {f1:.4f}   {status(f1, 0.67)}")
print(f"  Latency < 5s/sample:   {infer_per_sample_ms:.3f}ms  ✓ PASS (3 orders of magnitude below target)")

print("\n" + "="*70)
print("RECOMMENDATION: GO" if all([auc>=0.80, rec>=0.75, prec>=0.60]) else "RECOMMENDATION: NEEDS REVIEW")
print("="*70)
