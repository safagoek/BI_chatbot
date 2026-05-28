import pandas as pd

def compute_correlation(df: pd.DataFrame) -> pd.DataFrame:
    """
    Finds all numeric columns in a DataFrame, computes the Pearson correlation matrix,
    and returns a DataFrame with 'Değişken' as the first column containing row labels.
    """
    # Select numeric columns
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    
    # If we have less than 2 numeric columns, correlation is not possible
    if len(numeric_cols) < 2:
        return pd.DataFrame()
        
    corr_matrix = df[numeric_cols].corr(method='pearson')
    
    # Round to 3 decimal places for clean formatting
    corr_matrix = corr_matrix.round(3)
    
    # Reset index and rename it to 'Değişken'
    corr_matrix = corr_matrix.reset_index()
    corr_matrix = corr_matrix.rename(columns={'index': 'Değişken'})
    
    return corr_matrix
