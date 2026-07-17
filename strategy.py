import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import config

def calculate_atr(df, period=14):
    """Calcula el Average True Range (ATR)."""
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(period).mean()

def get_htf_bias(df_h4):
    """
    Analiza la temporalidad mayor (4H) para obtener el "permiso" de CRT.
    Retorna 1 (Alcista Fuerte), -1 (Bajista Fuerte), o 0 (Rango/Neutro).
    """
    if df_h4 is None or len(df_h4) < 21:
        return 0
        
    # Usamos la última vela H4 cerrada
    last_closed = df_h4.iloc[-2]
    
    # Calculamos una EMA rápida para confirmar la tendencia
    ema20 = df_h4['Close'].ewm(span=20, adjust=False).mean().iloc[-2]
    
    # Vela verde y por encima de la EMA = Subiendo firmemente
    if last_closed['Close'] > last_closed['Open'] and last_closed['Close'] > ema20:
        return 1
    # Vela roja y por debajo de la EMA = Cayendo con fuerza
    elif last_closed['Close'] < last_closed['Open'] and last_closed['Close'] < ema20:
        return -1
        
    return 0

def analyze_smc(df_m15, df_h4=None):
    """
    Analiza M15 buscando FVGs y define las órdenes LIMIT según CRT.
    """
    df = df_m15.copy()
    
    # 1. Permiso CRT (Temporalidad Mayor)
    # Si no se pasa H4 (ej. en el backtest viejo), asumimos neutralidad para no romper compatibilidad,
    # pero en producción obligamos a pasar df_h4.
    crt_bias = get_htf_bias(df_h4) if df_h4 is not None else 0
    
    # 2. Cálculo Vectorizado de FVG en M15
    df['ATR'] = calculate_atr(df, config.ATR_PERIOD)
    fvg_minimo = df['ATR'] * config.ATR_MULTIPLIER_FVG
    
    # Lógica FVG Alcista: Low(3) > High(1)
    df['Gap_Bull_Size'] = df['Low'] - df['High'].shift(2)
    df['FVG_Bull'] = (df['Low'] > df['High'].shift(2)) & (df['Gap_Bull_Size'] > fvg_minimo)
    
    # Lógica FVG Bajista: Low(1) > High(3)
    df['Gap_Bear_Size'] = df['Low'].shift(2) - df['High']
    df['FVG_Bear'] = (df['Low'].shift(2) > df['High']) & (df['Gap_Bear_Size'] > fvg_minimo)
    
    # 3. Analizar la última vela cerrada en M15 (Vela 3 del patrón)
    last_idx = -2
    row3 = df.iloc[last_idx]   # Vela 3 (La que confirma el FVG)
    row1 = df.iloc[last_idx - 2] # Vela 1 (La que originó el FVG)
    
    signal = None
    entry = 0.0
    sl = 0.0
    tp = 0.0
    
    buffer_pips = config.SL_BUFFER_PIPS if hasattr(config, 'SL_BUFFER_PIPS') else 1.0
    
    # Buscamos Compras SI Y SOLO SI CRT es Alcista (1) o Neutro (0 si ignoramos filtro por ahora)
    if row3['FVG_Bull'] and crt_bias >= 0:
        signal = "BUY_LIMIT"
        
        # Entrada: Borde superior del FVG (Máximo de la Vela 1)
        entry = row1['High']
        
        # SL: Por debajo de la mecha de la Vela 1
        sl = row1['Low'] - buffer_pips
        
        # TP: El máximo reciente (Máximo de la Vela 3) u objetivo de liquidez
        # Si el máximo de la vela 3 está muy cerca, buscamos el máximo de las últimas 10 velas.
        recent_high = df['High'].iloc[last_idx-10:last_idx+1].max()
        tp = recent_high if recent_high > entry + (entry - sl) else entry + (entry - sl) * 2.0
        
    # Buscamos Ventas SI Y SOLO SI CRT es Bajista (-1)
    elif row3['FVG_Bear'] and crt_bias <= 0:
        signal = "SELL_LIMIT"
        
        # Entrada: Borde inferior del FVG (Mínimo de la Vela 1)
        entry = row1['Low']
        
        # SL: Por encima de la mecha de la Vela 1
        sl = row1['High'] + buffer_pips
        
        # TP: Mínimo reciente o objetivo de liquidez
        recent_low = df['Low'].iloc[last_idx-10:last_idx+1].min()
        tp = recent_low if recent_low < entry - (sl - entry) else entry - (sl - entry) * 2.0

    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp
    }
