# =============================================================================
# HelioSense AI — Solar Potential Model Training Pipeline
# =============================================================================
# Target      : irradiance (Solar Irradiance, kWh/m²/day)
# Algorithm   : Random Forest Regressor
# Dataset     : Preprocessed NASA POWER daily meteorological dataset
# =============================================================================

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DATA_PATH     = os.path.join(BASE_DIR, "dataset", "solar_dataset.csv")
MODELS_DIR    = os.path.join(BASE_DIR, "models")
PLOT_DIR      = os.path.join(BASE_DIR, "plots")

# Ensure directories exist
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

MODEL_PATH     = os.path.join(MODELS_DIR, "solar_model.pkl")
CLIMATOLOGY_PATH = os.path.join(MODELS_DIR, "climatology.pkl")

# ── Styling for plots ─────────────────────────────────────────────────────────
ORANGE = "#FF6B00"
DARK   = "#1A1A2E"
LIGHT  = "#F5F5F5"
sns.set_style("darkgrid")
plt.rcParams.update({
    "figure.facecolor": DARK,
    "axes.facecolor"  : "#16213E",
    "axes.edgecolor"  : ORANGE,
    "axes.labelcolor" : LIGHT,
    "xtick.color"     : LIGHT,
    "ytick.color"     : LIGHT,
    "text.color"      : LIGHT,
    "grid.color"      : "#2A2A4A",
    "grid.linewidth"  : 0.5,
})

def main():
    print("\n" + "="*60)
    print("  HelioSense AI — Model Training Pipeline")
    print("="*60)

    # 1. Load Dataset
    print("\n[1/8] Loading dataset ...")
    if not os.path.exists(DATA_PATH):
        print(f"Error: Dataset not found at {DATA_PATH}!")
        return
        
    df = pd.read_csv(DATA_PATH)
    print(f"  Dataset Loaded successfully. Shape: {df.shape[0]:,} rows × {df.shape[1]} columns")
    print(f"  Columns: {df.columns.tolist()}")

    # 2. Compute Climatology
    # Aggregate monthly weather climatology (T, RH, WS) per grid coordinate (lat, lon, month)
    # This climatology will be used at prediction time to forecast monthly yields
    print("\n[2/8] Generating monthly weather climatology averages ...")
    climatology = df.groupby(['latitude', 'longitude', 'month'])[['temperature', 'humidity', 'wind_speed']].mean().reset_index()
    print(f"  Climatology shape: {climatology.shape[0]} rows (coordinate-month pairs)")
    joblib.dump(climatology, CLIMATOLOGY_PATH)
    print(f"  Saved climatology table to: {CLIMATOLOGY_PATH}")

    # 3. Feature Engineering
    print("\n[3/8] Performing cyclical month and day feature engineering ...")
    # Cyclical encoding for month
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    
    # Cyclical encoding for day
    df["day_sin"] = np.sin(2 * np.pi * df["day"] / 31)
    df["day_cos"] = np.cos(2 * np.pi * df["day"] / 31)

    # Final feature set
    FEATURES = [
        "latitude", "longitude", "year", "month", "day", 
        "temperature", "humidity", "wind_speed",
        "month_sin", "month_cos", "day_sin", "day_cos"
    ]
    TARGET = "irradiance"

    X = df[FEATURES]
    y = df[TARGET]
    print(f"  Engineered Features: {FEATURES}")
    print(f"  Target variable: '{TARGET}'")

    # 4. Train/Test Split
    print("\n[4/8] Splitting data (80% train / 20% test) ...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )
    print(f"  Training set size: {X_train.shape[0]:,} records")
    print(f"  Testing set size : {X_test.shape[0]:,} records")

    # 5. Train Random Forest Model
    print("\n[5/8] Training Random Forest Regressor ...")
    rf = RandomForestRegressor(
        n_estimators=150,
        max_depth=None,
        min_samples_split=4,
        min_samples_leaf=2,
        max_features="sqrt",
        n_jobs=-1,
        random_state=42
    )
    rf.fit(X_train, y_train)
    print("  Model training complete.")

    # 6. Evaluate
    print("\n[6/8] Evaluating model predictions ...")
    y_pred = rf.predict(X_test)
    
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))

    print("\n  ╔══════════════════════════════════╗")
    print(f"  ║  R² Score  :  {r2:.6f}           ║")
    print(f"  ║  MAE       :  {mae:.6f} kWh/m²/d ║")
    print(f"  ║  RMSE      :  {rmse:.6f} kWh/m²/d ║")
    print("  ╚══════════════════════════════════╝")

    # Save model binary
    joblib.dump(rf, MODEL_PATH)
    print(f"  Saved trained model binary to: {MODEL_PATH}")

    # 7. Feature Importances
    print("\n[7/8] Feature Importance Ranking:")
    fi_df = pd.DataFrame({
        "Feature"   : FEATURES,
        "Importance": rf.feature_importances_
    }).sort_values("Importance", ascending=False)
    print(fi_df.to_string(index=False))

    # 8. Save Diagnostics Visualizations
    print("\n[8/8] Generating and saving diagnostic plots ...")
    
    # 8a. Correlation Heatmap
    fig, ax = plt.subplots(figsize=(9, 7))
    fig.patch.set_facecolor(DARK)
    ax.set_facecolor("#16213E")
    corr = df[FEATURES + [TARGET]].corr()
    mask = np.triu(np.ones_like(corr, dtype=bool))
    sns.heatmap(
        corr, mask=mask, ax=ax,
        cmap=sns.diverging_palette(220, 20, as_cmap=True),
        annot=True, fmt=".2f", linewidths=0.5,
        annot_kws={"size": 8, "color": LIGHT},
        cbar_kws={"shrink": 0.8}
    )
    ax.set_title("Feature Correlation Heatmap", color=ORANGE, fontsize=14, pad=14)
    plt.tight_layout()
    heatmap_path = os.path.join(PLOT_DIR, "correlation_heatmap.png")
    plt.savefig(heatmap_path, dpi=150, bbox_inches="tight", facecolor=DARK)
    plt.close()
    print(f"  ✔ Correlation Heatmap -> {heatmap_path}")
    
    # 8b. Feature Importance Chart
    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor(DARK)
    ax.set_facecolor("#16213E")
    colors = [ORANGE if i == 0 else "#C0C0C0" for i in range(len(fi_df))]
    bars = ax.barh(fi_df["Feature"][::-1], fi_df["Importance"][::-1], color=colors[::-1])
    ax.set_xlabel("Importance Score", color=LIGHT)
    ax.set_title("Feature Importance Ranking", color=ORANGE, fontsize=14)
    for bar, val in zip(bars, fi_df["Importance"][::-1]):
        ax.text(bar.get_width() + 0.002, bar.get_y() + bar.get_height()/2,
                f"{val:.4f}", va="center", color=LIGHT, fontsize=8)
    plt.tight_layout()
    fi_path = os.path.join(PLOT_DIR, "feature_importance.png")
    plt.savefig(fi_path, dpi=150, bbox_inches="tight", facecolor=DARK)
    plt.close()
    print(f"  ✔ Feature Importance Chart -> {fi_path}")

    # 8c. Actual vs Predicted Scatter
    sample_idx = np.random.choice(len(y_test), size=min(500, len(y_test)), replace=False)
    y_test_s   = np.array(y_test)[sample_idx]
    y_pred_s   = y_pred[sample_idx]
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.patch.set_facecolor(DARK)
    for ax in axes:
        ax.set_facecolor("#16213E")
        
    axes[0].scatter(y_test_s, y_pred_s, alpha=0.4, color=ORANGE, s=18, edgecolors="none")
    lims = [min(y_test_s.min(), y_pred_s.min()) - 0.2,
            max(y_test_s.max(), y_pred_s.max()) + 0.2]
    axes[0].plot(lims, lims, "w--", linewidth=1.2, label="Perfect fit")
    axes[0].set_xlabel("Actual Irradiance (kWh/m²/day)", color=LIGHT)
    axes[0].set_ylabel("Predicted Irradiance (kWh/m²/day)", color=LIGHT)
    axes[0].set_title("Actual vs Predicted Values", color=ORANGE, fontsize=13)
    axes[0].legend(fontsize=9)
    axes[0].text(0.05, 0.92, f"R² = {r2:.4f}", transform=axes[0].transAxes, color=ORANGE, fontsize=11)
    
    residuals = y_test_s - y_pred_s
    axes[1].scatter(y_pred_s, residuals, alpha=0.4, color="#00D4FF", s=18, edgecolors="none")
    axes[1].axhline(0, color="white", linestyle="--", linewidth=1.2)
    axes[1].set_xlabel("Predicted Irradiance (kWh/m²/day)", color=LIGHT)
    axes[1].set_ylabel("Residual (Actual − Predicted)", color=LIGHT)
    axes[1].set_title("Residual Diagnostics", color=ORANGE, fontsize=13)
    
    plt.suptitle("HelioSense AI — Model Performance Evaluations", color=ORANGE, fontsize=15, y=1.02)
    plt.tight_layout()
    avp_path = os.path.join(PLOT_DIR, "actual_vs_predicted.png")
    plt.savefig(avp_path, dpi=150, bbox_inches="tight", facecolor=DARK)
    plt.close()
    print(f"  ✔ Model Diagnostic Charts -> {avp_path}")
    
    print("\nTraining Pipeline completed successfully!")

if __name__ == "__main__":
    main()
