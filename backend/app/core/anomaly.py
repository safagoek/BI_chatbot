import pandas as pd
import numpy as np

def detect_anomalies(df: pd.DataFrame, val_col: str, method: str = "isolation_forest") -> pd.DataFrame:
    """
    Fits an anomaly detection model (Isolation Forest or IQR) on the chosen column
    and appends a "Durum" column with 'Normal' or 'Anomali'.
    """
    df_clean = df.copy()
    if val_col not in df_clean.columns:
        df_clean['Durum'] = 'Normal'
        return df_clean
    
    # Save original values and create a numeric representation for calculation
    orig_series = df_clean[val_col]
    numeric_series = pd.to_numeric(orig_series, errors='coerce')
    non_nan_indices = numeric_series.notna()
    
    # Initialize all rows to 'Normal'
    df_clean['Durum'] = 'Normal'
    
    # If we have less than 3 non-nan data points, we can't reliably detect outliers, so return baseline
    if non_nan_indices.sum() < 3:
        return df_clean
        
    X = numeric_series[non_nan_indices].values.reshape(-1, 1)
    
    if method == "isolation_forest":
        try:
            from sklearn.ensemble import IsolationForest
            # standard 5% contamination rate for outliers
            clf = IsolationForest(contamination=0.05, random_state=42)
            preds = clf.fit_predict(X)
            # IsolationForest returns -1 for anomalies and 1 for inliers
            anomalies = (preds == -1)
            df_clean.loc[non_nan_indices, 'Durum'] = np.where(anomalies, 'Anomali', 'Normal')
        except Exception:
            # Fallback to IQR in case sklearn import or execution fails
            method = "iqr"
            
    if method == "iqr":
        q1 = np.percentile(X, 25)
        q3 = np.percentile(X, 75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        anomalies = (X < lower_bound) | (X > upper_bound)
        # Reshape to 1D
        anomalies = anomalies.flatten()
        df_clean.loc[non_nan_indices, 'Durum'] = np.where(anomalies, 'Anomali', 'Normal')
        
    return df_clean
