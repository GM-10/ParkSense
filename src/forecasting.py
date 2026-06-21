"""Temporal forecast service comparing HistGradientBoostingRegressor, DecisionTreeRegressor, and LinearRegression."""
from __future__ import annotations
from datetime import datetime, timezone
import math
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

from functools import lru_cache

from src.analytics import DATASET, load_violations
from src.domain import DataLineage, ForecastPoint, ForecastResponse

MODEL_VERSION = "multi-model-ensemble-v2.0.0"
HORIZONS = (1, 6, 24, 168)

def _features(series: pd.Series) -> pd.DataFrame:
    frame = pd.DataFrame({"y": series})
    for lag in (1, 2, 6, 24, 48, 168):
        frame[f"lag_{lag}"] = frame["y"].shift(lag)
    frame["rolling_24"] = frame["y"].shift(1).rolling(24).mean()
    frame["rolling_168"] = frame["y"].shift(1).rolling(168).mean()
    frame["hour_sin"] = np.sin(2 * np.pi * frame.index.hour / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * frame.index.hour / 24)
    frame["dow_sin"] = np.sin(2 * np.pi * frame.index.dayofweek / 7)
    frame["dow_cos"] = np.cos(2 * np.pi * frame.index.dayofweek / 7)
    return frame.dropna()

@lru_cache(maxsize=128)
def forecast_locality(locality_name: str) -> ForecastResponse:
    df = load_violations()
    local = df[df["locality_name_lower"] == locality_name.lower()]
    origin = df["created_datetime"].max().to_pydatetime()
    base_lineage = DataLineage(dataset=DATASET.name, dataset_max_timestamp=origin,
        computed_at=datetime.now(timezone.utc), formula_version="hourly-count-aggregation-v1",
        model_version=MODEL_VERSION, measured=False,
        caveat="Forecast origin is the final timestamp in the historical dataset, not the current time.")
    
    if len(local) < 200 or local["created_datetime"].dt.date.nunique() < 28:
        return ForecastResponse(locality_name=locality_name, forecast_origin=origin,
            status="insufficient_data", points=[], evaluation={}, lineage=base_lineage)
            
    series = local.set_index("created_datetime").resample("h").size().astype(float)
    series = series.asfreq("h", fill_value=0)
    frame = _features(series)
    
    if len(frame) < 24 * 35:
        return ForecastResponse(locality_name=locality_name, forecast_origin=origin,
            status="insufficient_data", points=[], evaluation={}, lineage=base_lineage)
            
    split = int(len(frame) * .8)
    x, y = frame.drop(columns="y"), frame["y"]
    x_train, y_train = x.iloc[:split], y.iloc[:split]
    x_val, y_val = x.iloc[split:], y.iloc[split:]
    
    # 1. HistGradientBoosting (Primary Champion Model)
    m_hgb = HistGradientBoostingRegressor(loss="poisson", max_iter=30, max_leaf_nodes=12,
                                           learning_rate=.06, l2_regularization=1.0, random_state=42)
    m_hgb.fit(x_train, y_train)
    val_hgb = np.maximum(0, m_hgb.predict(x_val))
    mae_hgb = float(mean_absolute_error(y_val, val_hgb))
    
    # 2. DecisionTree
    m_dt = DecisionTreeRegressor(max_depth=8, random_state=42)
    m_dt.fit(x_train, y_train)
    val_dt = np.maximum(0, m_dt.predict(x_val))
    mae_dt = float(mean_absolute_error(y_val, val_dt))
    
    # 3. LinearRegression
    m_lr = LinearRegression()
    m_lr.fit(x_train, y_train)
    val_lr = np.maximum(0, m_lr.predict(x_val))
    mae_lr = float(mean_absolute_error(y_val, val_lr))
    
    # Select champion
    champion = m_hgb
    mae = mae_hgb
    val_preds = val_hgb
    best_model_name = "HistGradientBoosting"
    
    if mae_dt < mae:
        champion = m_dt
        mae = mae_dt
        val_preds = val_dt
        best_model_name = "DecisionTree"
    if mae_lr < mae:
        champion = m_lr
        mae = mae_lr
        val_preds = val_lr
        best_model_name = "LinearRegression"
        
    actual = y_val.to_numpy()
    rmse = float(math.sqrt(mean_squared_error(actual, val_preds)))
    tolerance_accuracy = float(np.mean(np.abs(val_preds - actual) <= np.maximum(1, actual * .25)))
    residual_std = float(np.std(val_preds - actual))
    
    import warnings
    # Recursive model prediction
    history_values = list(series.values)
    history_times = list(series.index)
    predictions = []
    
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        for _ in range(max(HORIZONS)):
            next_time = history_times[-1] + pd.Timedelta(hours=1)
            
            lag_1 = history_values[-1]
            lag_2 = history_values[-2]
            lag_6 = history_values[-6]
            lag_24 = history_values[-24]
            lag_48 = history_values[-48]
            lag_168 = history_values[-168]
            
            rolling_24 = sum(history_values[-24:]) / 24.0
            rolling_168 = sum(history_values[-168:]) / 168.0
            
            h = next_time.hour
            dow = next_time.dayofweek
            hour_sin = math.sin(2 * math.pi * h / 24.0)
            hour_cos = math.cos(2 * math.pi * h / 24.0)
            dow_sin = math.sin(2 * math.pi * dow / 7.0)
            dow_cos = math.cos(2 * math.pi * dow / 7.0)
            
            feat_arr = [[
                lag_1, lag_2, lag_6, lag_24, lag_48, lag_168,
                rolling_24, rolling_168,
                hour_sin, hour_cos, dow_sin, dow_cos
            ]]
            
            pred = max(0.0, float(champion.predict(feat_arr)[0]))
            predictions.append(pred)
            history_values.append(pred)
            history_times.append(next_time)
        
    points = []
    confidence = max(0.0, min(1.0, 1 - mae / max(1.0, float(y.mean()) + 1)))
    for horizon in HORIZONS:
        expected = float(sum(predictions[:horizon]))
        interval = 1.96 * residual_std * math.sqrt(horizon)
        points.append(ForecastPoint(horizon_hours=horizon, expected_violations=round(expected, 2),
            lower_bound=round(max(0, expected - interval), 2), upper_bound=round(expected + interval, 2),
            confidence=round(confidence, 3)))
            
    eval_dict = {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "tolerance_accuracy": round(tolerance_accuracy, 4),
        "model_champion": best_model_name,
        "metrics_comparison": {
            "HistGradientBoosting_MAE": round(mae_hgb, 4),
            "DecisionTree_MAE": round(mae_dt, 4),
            "LinearRegression_MAE": round(mae_lr, 4)
        }
    }
    
    return ForecastResponse(locality_name=locality_name, forecast_origin=origin, status="modelled", points=points,
        evaluation=eval_dict, lineage=base_lineage)
