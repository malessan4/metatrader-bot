import pandas as pd
import numpy as np
import config

def calculate_atr(df, period=14):
    """Calcula el Average True Range (ATR)."""
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    
    return true_range.rolling(period).mean()

def analyze_smc(df):
    """
    Analiza el DataFrame y busca FVGs e IFVGs recientes.
    Retorna un diccionario con la señal (BUY, SELL) y niveles de SL y TP.
    """
    df = df.copy()
    
    # 1. Calculamos el ATR para filtrar FVG falsos
    df['ATR'] = calculate_atr(df, config.ATR_PERIOD)
    fvg_minimo = df['ATR'] * config.ATR_MULTIPLIER_FVG
    
    # 2. Lógica FVG Alcista (Bullish FVG)
    df['Gap_Bull_Size'] = df['Low'] - df['High'].shift(2)
    df['FVG_Bull'] = (df['Low'] > df['High'].shift(2)) & (df['Gap_Bull_Size'] > fvg_minimo)
    
    # 3. Lógica FVG Bajista (Bearish FVG)
    df['Gap_Bear_Size'] = df['Low'].shift(2) - df['High']
    df['FVG_Bear'] = (df['Low'].shift(2) > df['High']) & (df['Gap_Bear_Size'] > fvg_minimo)
    
    # Analizamos la última vela completada. 
    # Por lo general, en MT5 el último índice (df.iloc[-1]) es la vela actual formándose.
    # Por lo tanto, usamos df.iloc[-2] que es la última vela CERRADA.
    last_closed_idx = -2
    row = df.iloc[last_closed_idx]
    
    signal = None
    sl = 0.0
    entry = row['Close'] # Usamos el precio de cierre de la vela que confirma el FVG
    
    # Si la vela cerrada acaba de formar un FVG Alcista
    if row['FVG_Bull']:
        signal = "BUY"
        # El SL va por debajo de la vela que inició el movimiento (la vela 1 del patrón de 3)
        sl = df.iloc[last_closed_idx - 2]['Low'] 
        
    # Si la vela cerrada acaba de formar un FVG Bajista
    elif row['FVG_Bear']:
        signal = "SELL"
        # El SL va por encima de la vela que inició el movimiento
        sl = df.iloc[last_closed_idx - 2]['High']
        
    # Cálculo dinámico del Take Profit basado en Risk:Reward (1:2)
    tp = 0.0
    if signal == "BUY":
        risk = entry - sl
        if risk > 0:
            tp = entry + (risk * config.RISK_REWARD_RATIO)
        else:
            signal = None # Invalid setup
            
    elif signal == "SELL":
        risk = sl - entry
        if risk > 0:
            tp = entry - (risk * config.RISK_REWARD_RATIO)
        else:
            signal = None # Invalid setup
            
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp
    }
