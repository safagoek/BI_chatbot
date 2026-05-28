import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

def run_kmeans_clustering(df: pd.DataFrame, n_clusters: int = 3) -> pd.DataFrame:
    """
    Standardizes all numerical columns in the DataFrame, runs scikit-learn KMeans,
    appends a 'Küme' (Cluster) column to the DataFrame, and returns the result.
    If there are more than 2 numeric columns, runs PCA to project them into 2 components
    for visualization purposes ('PCA1', 'PCA2' columns are added).
    """
    if df is None or len(df) < n_clusters:
        return df

    df_clean = df.copy()
    
    # 1. Select all numeric columns
    num_cols = df_clean.select_dtypes(include=['number']).columns.tolist()
    
    # Remove index or id columns from clustering features
    num_cols = [c for c in num_cols if not any(id_kw in c.lower() for id_kw in ["id", "key", "index", "kod", "no"])]
    
    if len(num_cols) < 1:
        # Fallback to all numeric columns if they were all excluded
        num_cols = df_clean.select_dtypes(include=['number']).columns.tolist()
        
    if len(num_cols) < 1:
        df_clean['Küme'] = 'Küme 0'
        return df_clean

    # Handle missing values by replacing with median
    X_raw = df_clean[num_cols].copy()
    for col in num_cols:
        X_raw[col] = pd.to_numeric(X_raw[col], errors='coerce')
        X_raw[col] = X_raw[col].fillna(X_raw[col].median() if not X_raw[col].isna().all() else 0.0)

    # 2. Standardize features
    scaler = StandardScaler()
    try:
        X_scaled = scaler.fit_transform(X_raw)
    except Exception:
        df_clean['Küme'] = 'Küme 0'
        return df_clean

    # 3. Fit KMeans
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto')
    try:
        clusters = kmeans.fit_predict(X_scaled)
        df_clean['Küme'] = [f"Segment {c + 1}" for c in clusters]
    except Exception:
        df_clean['Küme'] = 'Küme 0'
        return df_clean

    # 4. If we have more than 2 numeric features, run PCA for 2D graphing coordinates
    if len(num_cols) > 2:
        try:
            pca = PCA(n_components=2)
            X_pca = pca.fit_transform(X_scaled)
            df_clean['PCA1'] = X_pca[:, 0]
            df_clean['PCA2'] = X_pca[:, 1]
        except Exception:
            pass

    return df_clean
