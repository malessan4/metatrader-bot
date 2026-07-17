import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import config

def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(period).mean()

def get_htf_bias(df_h4):
    if df_h4 is None or len(df_h4) < 21: return 0
    last_closed = df_h4.iloc[-2]
    ema20 = df_h4['Close'].ewm(span=20, adjust=False).mean().iloc[-2]
    if last_closed['Close'] > last_closed['Open'] and last_closed['Close'] > ema20: return 1
    elif last_closed['Close'] < last_closed['Open'] and last_closed['Close'] < ema20: return -1
    return 0

def analyze_smc(df_m15, df_h4=None):
    df = df_m15.copy()
    crt_bias = get_htf_bias(df_h4) if df_h4 is not None else 0
    
    df['ATR'] = calculate_atr(df, config.ATR_PERIOD)
    fvg_minimo = df['ATR'] * config.ATR_MULTIPLIER_FVG
    
    df['Gap_Bull_Size'] = df['Low'] - df['High'].shift(2)
    df['FVG_Bull'] = (df['Low'] > df['High'].shift(2)) & (df['Gap_Bull_Size'] > fvg_minimo)
    
    df['Gap_Bear_Size'] = df['Low'].shift(2) - df['High']
    df['FVG_Bear'] = (df['Low'].shift(2) > df['High']) & (df['Gap_Bear_Size'] > fvg_minimo)
    
    last_idx = -2
    row3 = df.iloc[last_idx]   
    row1 = df.iloc[last_idx - 2] 
    
    signal = None
    entry = 0.0
    sl = 0.0
    tp = 0.0
    buffer_pips = getattr(config, 'SL_BUFFER_PIPS', 1.0)
    
    # 1. Chequeo de FVG Normal
    if row3['FVG_Bull'] and crt_bias >= 0:
        signal = "BUY_LIMIT"
        entry = row1['High']
        sl = row1['Low'] - buffer_pips
        recent_high = df['High'].iloc[last_idx-10:last_idx+1].max()
        tp = recent_high if recent_high > entry + (entry - sl) else entry + (entry - sl) * 2.0
        
    elif row3['FVG_Bear'] and crt_bias <= 0:
        signal = "SELL_LIMIT"
        entry = row1['Low']
        sl = row1['High'] + buffer_pips
        recent_low = df['Low'].iloc[last_idx-10:last_idx+1].min()
        tp = recent_low if recent_low < entry - (sl - entry) else entry - (sl - entry) * 2.0

    # 2. Chequeo de IFVG (Inversion FVG)
    # Buscamos si la última vela cerrada acaba de ROMPER con fuerza un FVG opuesto del pasado.
    # Escaneamos los últimos 15 periodos buscando un FVG que haya sido violado.
    if not signal:
        cierre_actual = row3['Close']
        for i_back in range(3, 15):
            idx_analizar = last_idx - i_back
            vela_3 = df.iloc[idx_analizar]
            vela_1 = df.iloc[idx_analizar - 2]
            
            # Si había un FVG ALCISTA en el pasado (que ahora es soporte)
            if vela_3['FVG_Bull']:
                techo_fvg = vela_1['High']
                base_fvg = vela_1['Low']
                # Si la vela actual cerró con fuerza por debajo de la base del FVG alcista = IFVG BAJISTA
                if cierre_actual < base_fvg and crt_bias <= 0:
                    signal = "SELL_LIMIT" # IFVG
                    entry = base_fvg # Entramos en el re-testeo de la base rota (el antiguo soporte se vuelve resistencia)
                    sl = techo_fvg + buffer_pips # SL por encima del techo del bloque roto
                    recent_low = df['Low'].iloc[last_idx-10:last_idx+1].min()
                    tp = recent_low if recent_low < entry - (sl - entry) else entry - (sl - entry) * 2.0
                    break
                    
            # Si había un FVG BAJISTA en el pasado (que ahora es resistencia)
            elif vela_3['FVG_Bear']:
                base_fvg = vela_1['Low']
                techo_fvg = vela_1['High']
                # Si la vela actual cerró con fuerza por encima del techo del FVG bajista = IFVG ALCISTA
                if cierre_actual > techo_fvg and crt_bias >= 0:
                    signal = "BUY_LIMIT" # IFVG
                    entry = techo_fvg # Entramos en el re-testeo del techo roto (la antigua resistencia se vuelve soporte)
                    sl = base_fvg - buffer_pips # SL por debajo de la base del bloque roto
                    recent_high = df['High'].iloc[last_idx-10:last_idx+1].max()
                    tp = recent_high if recent_high > entry + (entry - sl) else entry + (entry - sl) * 2.0
                    break

    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp
    }
