import datetime
from typing import Dict, Any, List
import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge

def run_time_series_forecast(df: pd.DataFrame, time_col: str, val_col: str, periods: int = 6) -> pd.DataFrame:
    """
    Parses historical dates, aggregates time values, trains a Ridge regression
    forecasting model with polynomial trend and monthly seasonal dummy features,
    calculates 95% confidence intervals, and returns a combined DataFrame
    containing both 'Gerçek' (Actual) and 'Tahmin' (Forecasted) values along
    with Lower_CI and Upper_CI bounds.
    """
    if df is None or len(df) < 2:
        return df

    # 1. Parse date column and sort chronologically
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
    df = df.dropna(subset=[time_col])
    df = df.sort_values(by=time_col).reset_index(drop=True)
    
    # 2. Group by date to aggregate duplicate date items (e.g. daily sales to daily totals)
    df_grouped = df.groupby(time_col)[val_col].sum().reset_index()
    
    if len(df_grouped) < 2:
        return df
        
    # 3. Detect time frequency: Monthly vs Daily
    diffs = df_grouped[time_col].diff().dropna()
    mean_days = diffs.dt.days.mean() if not diffs.empty else 30
    freq = 'M' if mean_days >= 27 else 'D'
    
    # 4. Prepare training features: Linear Trend + Quadratic Trend + 11 Monthly Seasonal Dummies
    X = []
    y = []
    
    for idx, row in df_grouped.iterrows():
        t = row[time_col]
        time_idx = idx
        month = t.month
        
        # Polynomial Trend (Linear + Quadratic)
        features = [time_idx, time_idx ** 2]
        # Monthly Seasonality
        for m in range(1, 12):
            features.append(1.0 if month == m else 0.0)
            
        X.append(features)
        y.append(float(row[val_col]))
        
    # 5. Fit Ridge Regression Model (with alpha regularization to prevent overfitting)
    model = Ridge(alpha=1.0)
    model.fit(X, y)
    
    # Calculate Residual Standard Error for 95% Confidence Intervals
    preds_train = model.predict(X)
    residuals = np.array(y) - preds_train
    std_error = np.std(residuals) if len(residuals) > 1 else 1.0
    if std_error == 0:
        std_error = 1.0
    
    # 6. Generate future dates
    last_date = df_grouped[time_col].max()
    future_dates = []
    current_date = last_date
    
    for _ in range(periods):
        if freq == 'M':
            # Safe next month offset
            current_date = current_date + pd.DateOffset(months=1)
        else:
            current_date = current_date + pd.DateOffset(days=1)
        future_dates.append(current_date)
        
    # 7. Compute future predictions & 95% Confidence Intervals
    future_X = []
    last_idx = len(df_grouped) - 1
    
    for i, f_date in enumerate(future_dates):
        time_idx = last_idx + 1 + i
        month = f_date.month
        
        features = [time_idx, time_idx ** 2]
        for m in range(1, 12):
            features.append(1.0 if month == m else 0.0)
        future_X.append(features)
        
    predictions = model.predict(future_X)
    
    # 8. Format results as continuous connecting timeline rows for Plotly with CI bounds
    history_rows = []
    for _, row in df_grouped.iterrows():
        history_rows.append({
            time_col: row[time_col].strftime('%Y-%m-%d'),
            val_col: float(row[val_col]),
            "Tip": "Gerçek",
            "Lower_CI": float(row[val_col]),
            "Upper_CI": float(row[val_col])
        })
        
    # Standard plotting trick: add the last actual point as the first prediction point
    # to seamlessly connect the two lines in the Plotly express line chart
    prediction_rows = [{
        time_col: last_date.strftime('%Y-%m-%d'),
        val_col: float(df_grouped[val_col].iloc[-1]),
        "Tip": "Tahmin",
        "Lower_CI": float(df_grouped[val_col].iloc[-1]),
        "Upper_CI": float(df_grouped[val_col].iloc[-1])
    }]
    
    for i, (f_date, pred) in enumerate(zip(future_dates, predictions)):
        # Calculate dynamic spreading spread for confidence bounds
        spread = 1.96 * std_error * np.sqrt(1.0 + ((i + 1) / len(df_grouped)))
        lower_bound = max(0.0, float(pred - spread))
        upper_bound = float(pred + spread)
        
        prediction_rows.append({
            time_col: f_date.strftime('%Y-%m-%d'),
            val_col: max(0.0, float(pred)), # prevent negative predictions
            "Tip": "Tahmin",
            "Lower_CI": lower_bound,
            "Upper_CI": upper_bound
        })
        
    merged_df = pd.DataFrame(history_rows + prediction_rows)
    return merged_df
