import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import sys
import config
import mt5_client
import strategy

def simular_backtest():
    print(f"==================================================")
    print(f"☢️ INICIANDO BACKTEST CRT + FVG LIMIT ORDERS")
    print(f"==================================================")
    
    if not mt5_client.initialize():
        return
        
    symbol = config.SYMBOL
    timeframe_m15 = mt5.TIMEFRAME_M15
    timeframe_h4 = mt5.TIMEFRAME_H4
    n_velas = 10000
    balance_inicial = 1000.0
    lote = config.LOT_SIZE
    
    print(f"📥 Descargando {n_velas} velas M15 y H4 de {symbol}...")
    df_m15 = mt5_client.get_data(symbol, timeframe_m15, n_candles=n_velas)
    # Extraemos H4 para el trend
    df_h4 = mt5_client.get_data(symbol, timeframe_h4, n_candles=int(n_velas/16)) 
    
    if df_m15 is None or df_m15.empty or df_h4 is None or df_h4.empty:
        print("Error descargando datos.")
        mt5_client.shutdown()
        return
        
    print("⚙️ Calculando indicadores SMC...")
    
    # 2. Cálculo Vectorizado de Señales en M15
    df_m15['ATR'] = strategy.calculate_atr(df_m15, config.ATR_PERIOD)
    fvg_minimo = df_m15['ATR'] * config.ATR_MULTIPLIER_FVG
    
    df_m15['Gap_Bull_Size'] = df_m15['Low'] - df_m15['High'].shift(2)
    df_m15['FVG_Bull'] = (df_m15['Low'] > df_m15['High'].shift(2)) & (df_m15['Gap_Bull_Size'] > fvg_minimo)
    
    df_m15['Gap_Bear_Size'] = df_m15['Low'].shift(2) - df_m15['High']
    df_m15['FVG_Bear'] = (df_m15['Low'].shift(2) > df_m15['High']) & (df_m15['Gap_Bear_Size'] > fvg_minimo)
    
    symbol_info = mt5.symbol_info(symbol)
    contract_size = symbol_info.trade_contract_size if symbol_info else 100
    
    ganadas = 0
    perdidas = 0
    be_cierres = 0
    limit_no_activadas = 0
    balance = balance_inicial
    
    print("⏳ Simulando Limit Orders con HTF Bias...")
    
    # Pre-calcular EMA20 en H4
    df_h4['EMA20'] = df_h4['Close'].ewm(span=20, adjust=False).mean()
    
    for i in range(10, len(df_m15) - 100):
        if i % 250 == 0:
            pct = (i / len(df_m15)) * 100
            sys.stdout.write(f"\rProgreso: [{ '#' * int(pct/2) }{ '-' * (50-int(pct/2)) }] {pct:.1f}%")
            sys.stdout.flush()
            
        row = df_m15.iloc[i]
        signal = None
        
        # Buscar el H4 correspondiente a este timestamp
        current_time = row['Time']
        # Buscar la última vela H4 cerrada antes de este time
        h4_pasadas = df_h4[df_h4['Time'] < current_time]
        crt_bias = 0
        if len(h4_pasadas) >= 2:
            last_h4 = h4_pasadas.iloc[-1]
            if last_h4['Close'] > last_h4['Open'] and last_h4['Close'] > last_h4['EMA20']:
                crt_bias = 1
            elif last_h4['Close'] < last_h4['Open'] and last_h4['Close'] < last_h4['EMA20']:
                crt_bias = -1
                
        # Verificar FVG
        if row['FVG_Bull'] and crt_bias >= 0:
            signal = "BUY_LIMIT"
            entry = df_m15.iloc[i-2]['High']
            sl = df_m15.iloc[i-2]['Low'] - config.SL_BUFFER_PIPS
            recent_high = df_m15['High'].iloc[i-10:i+1].max()
            tp = recent_high if recent_high > entry + (entry - sl) else entry + (entry - sl) * 2.0
            
        elif row['FVG_Bear'] and crt_bias <= 0:
            signal = "SELL_LIMIT"
            entry = df_m15.iloc[i-2]['Low']
            sl = df_m15.iloc[i-2]['High'] + config.SL_BUFFER_PIPS
            recent_low = df_m15['Low'].iloc[i-10:i+1].min()
            tp = recent_low if recent_low < entry - (sl - entry) else entry - (sl - entry) * 2.0
            
        if signal:
            trade_activo = False
            be_activado = False
            limit_activa = True # La orden está puesta, esperando el retroceso
            
            if signal == "BUY_LIMIT":
                risk = entry - sl
                target_be = entry + (risk * config.MOVE_TO_BREAKEVEN_RATIO)
            else:
                risk = sl - entry
                target_be = entry - (risk * config.MOVE_TO_BREAKEVEN_RATIO)
                
            for j in range(i+1, min(i+150, len(df_m15))):
                f_row = df_m15.iloc[j]
                high = f_row['High']
                low = f_row['Low']
                
                # FASE 1: Esperar a que el precio toque la LIMIT (Entry)
                if limit_activa and not trade_activo:
                    if signal == "BUY_LIMIT":
                        if low <= entry: 
                            if low <= sl:
                                # Invalidado antes de entrar o entró y barrió el SL directo
                                limit_activa = False
                                break
                            trade_activo = True
                            limit_activa = False
                        elif high > tp:
                            # Se fue sin nosotros
                            limit_activa = False
                            limit_no_activadas += 1
                            break
                            
                    elif signal == "SELL_LIMIT":
                        if high >= entry:
                            if high >= sl:
                                limit_activa = False
                                break
                            trade_activo = True
                            limit_activa = False
                        elif low < tp:
                            limit_activa = False
                            limit_no_activadas += 1
                            break
                            
                # FASE 2: Trade Activo, manejar TP / SL / BE
                if trade_activo:
                    if signal == "BUY_LIMIT":
                        if not be_activado and high >= target_be:
                            sl = entry
                            be_activado = True
                        if low <= sl:
                            if be_activado: be_cierres += 1
                            else: perdidas += 1; balance -= (risk * lote * contract_size)
                            break
                        if high >= tp:
                            ganadas += 1
                            balance += ((tp - entry) * lote * contract_size)
                            break
                    else: # SELL_LIMIT
                        if not be_activado and low <= target_be:
                            sl = entry
                            be_activado = True
                        if high >= sl:
                            if be_activado: be_cierres += 1
                            else: perdidas += 1; balance -= (risk * lote * contract_size)
                            break
                        if low <= tp:
                            ganadas += 1
                            balance += ((entry - tp) * lote * contract_size)
                            break

    mt5_client.shutdown()
    
    print("\n\n" + "="*50)
    print(f"🏁 RESULTADO BACKTEST CRT + FVG LIMIT (10,000 velas)")
    print("="*50)
    print(f"🔵 Ganadas: {ganadas} | 🔴 Perdidas: {perdidas} | 🛡️ BE: {be_cierres} | 👻 Missed Limits: {limit_no_activadas}")
    
    total = ganadas + perdidas + be_cierres
    if total > 0:
        wr = (ganadas / (ganadas + perdidas)) * 100 if (ganadas + perdidas) > 0 else 0
        print(f"🎯 Win Rate Efectivo: {wr:.2f}%")
        print(f"💰 Balance Final: ${balance:.2f} USD")
        print(f"📈 Beneficio Neto: ${(balance - balance_inicial):.2f} USD")
    else:
        print("❌ El bot no encontró entradas válidas con la regla H4.")
    print("="*50)

if __name__ == "__main__":
    simular_backtest()
