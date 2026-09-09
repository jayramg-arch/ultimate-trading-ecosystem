import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import StandardScaler

def train_models():
    print("Loading trades data...")
    df = pd.read_csv("trades_ml_features.csv")
    print(f"Total records: {len(df)}")

    # Define target: 1 if winning trade, 0 if losing trade
    df['Target'] = (df['PnL_Pct'] > 0).astype(int)

    # Drop constant or mostly-null features
    # VOL_ACCUM is constant (all 1.0) — not informative
    # MANSFIELD_RS has ~86% missing — fill with 0 (neutral)
    df['MANSFIELD_RS'] = df['MANSFIELD_RS'].fillna(0)

    features = ['RSI', 'ATR_PCT', 'BBW', 'MANSFIELD_RS', 'ALPHA_SCORE', 
                'PULLBACK_DEPTH', 'VCP_TIGHT', 'MA_SQZ_VAL']
    
    # Drop remaining NaNs
    df = df.dropna(subset=features + ['Target'])
    print(f"Records after cleanup: {len(df)}")
    print(f"Win rate: {df['Target'].mean()*100:.1f}%")

    X = df[features]
    y = df['Target']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # Scale for Logistic Regression
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # ═══════════════════════════════════════════════════════
    # 1. Logistic Regression
    # ═══════════════════════════════════════════════════════
    print("\n" + "="*60)
    print("  LOGISTIC REGRESSION (Interpretable Weights)")
    print("="*60)
    lr = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr.fit(X_train_scaled, y_train)
    y_pred_lr = lr.predict(X_test_scaled)
    print(f"Accuracy: {accuracy_score(y_test, y_pred_lr):.4f}")
    print(classification_report(y_test, y_pred_lr, target_names=['Loss', 'Win']))
    
    # Unscale weights for direct use in Pine Script
    print("\n--- Pine Script Weights (Unscaled) ---")
    unscaled_weights = lr.coef_[0] / scaler.scale_
    intercept = lr.intercept_[0] - np.sum(lr.coef_[0] * scaler.mean_ / scaler.scale_)
    
    for i, feature in enumerate(features):
        print(f"  {feature:20s}: {unscaled_weights[i]:+.6f}")
    print(f"  {'Intercept':20s}: {intercept:+.6f}")
    
    print("\n--- Pine Script Formula ---")
    terms = [f"({unscaled_weights[i]:+.6f} * {f})" for i, f in enumerate(features)]
    print(f"ml_score = {intercept:.6f}")
    for t in terms:
        print(f"         + {t}")
    print("ml_win_prob = 1.0 / (1.0 + math.exp(-ml_score))")
    
    # ═══════════════════════════════════════════════════════
    # 2. Decision Tree (Max Depth 4)
    # ═══════════════════════════════════════════════════════
    print("\n" + "="*60)
    print("  DECISION TREE (Interpretable Branches, Depth=4)")
    print("="*60)
    dt = DecisionTreeClassifier(max_depth=4, class_weight='balanced', min_samples_leaf=50, random_state=42)
    dt.fit(X_train, y_train)
    y_pred_dt = dt.predict(X_test)
    print(f"Accuracy: {accuracy_score(y_test, y_pred_dt):.4f}")
    print(classification_report(y_test, y_pred_dt, target_names=['Loss', 'Win']))
    
    tree_rules = export_text(dt, feature_names=features, decimals=4)
    print("\nDecision Tree Rules:")
    print(tree_rules)

    # ═══════════════════════════════════════════════════════
    # 3. Feature Importance Rankings
    # ═══════════════════════════════════════════════════════
    print("\n" + "="*60)
    print("  FEATURE IMPORTANCE RANKINGS")
    print("="*60)
    
    # From Logistic Regression (absolute scaled weights)
    lr_importance = np.abs(lr.coef_[0])
    lr_sorted = sorted(zip(features, lr_importance), key=lambda x: x[1], reverse=True)
    print("\nLogistic Regression (by absolute weight):")
    for f, w in lr_sorted:
        print(f"  {f:20s}: {w:.4f}")
    
    # From Decision Tree (Gini importance)
    dt_importance = dt.feature_importances_
    dt_sorted = sorted(zip(features, dt_importance), key=lambda x: x[1], reverse=True)
    print("\nDecision Tree (Gini importance):")
    for f, w in dt_sorted:
        print(f"  {f:20s}: {w:.4f}")

    # ═══════════════════════════════════════════════════════
    # 4. Optimal Threshold Analysis
    # ═══════════════════════════════════════════════════════
    print("\n" + "="*60)
    print("  OPTIMAL THRESHOLD ANALYSIS")
    print("="*60)
    
    # Check win rate by feature quantiles
    for feat in features:
        q25 = df[feat].quantile(0.25)
        q75 = df[feat].quantile(0.75)
        low_wr = df[df[feat] <= q25]['Target'].mean() * 100
        high_wr = df[df[feat] >= q75]['Target'].mean() * 100
        print(f"  {feat:20s}: Bottom 25% WR={low_wr:.1f}%  |  Top 25% WR={high_wr:.1f}%  |  Spread={high_wr-low_wr:+.1f}pp")

if __name__ == "__main__":
    train_models()
