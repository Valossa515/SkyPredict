import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from prophet import Prophet

def treinar_modelo(df):
    X = df[['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']]
    y = df['risk']
    model = RandomForestClassifier(n_estimators=100, random_state=42, min_samples_leaf=1, max_features='sqrt')
    model.fit(X, y)
    return model

def prever_variavel(df, coluna, data_futura):
    prophet_df = df[[coluna]].reset_index()
    prophet_df.columns = ['ds', 'y']
    modelo = Prophet()
    modelo.fit(prophet_df)
    futuro = pd.DataFrame({'ds': [data_futura]})
    previsao = modelo.predict(futuro)
    return previsao['yhat'].values[0]
