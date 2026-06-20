import pandas as pd
from prophet import Prophet
import datetime

df = pd.DataFrame({
    'ds': [datetime.datetime(2026, 1, 1), datetime.datetime(2026, 1, 3), datetime.datetime(2026, 1, 5)],
    'y': [1.0, 1.0, 1.0]
})
m = Prophet()
m.fit(df)
print("Prophet fit success!")
