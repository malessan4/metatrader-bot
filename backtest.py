import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import sys
import config
import mt5_client
import strategy

def simular_backtest():
    print(f"==================================================")
    print(f"☢️ INICIANDO BACKTEST SMC (FVG)")
    print(f"==================================================")
    
    # 1. Conexión a MT5
    if not mt5_client.initialize():
        return
        
    symbol = config.SYMBOL
    timeframe = mt5.TIMEFRAME_M15 # Forzamos M15 para el backtest
    n_velas = 10000
    balance_inicial = 1000.0
    lote = config.LOT_SIZE
    
    print(f"📥 Descargando {n_velas} velas históricas de {symbol} en M15...")
    df = mt5_client.get_data(symbol, timeframe, n_candles=n_velas)
    if df is None or df.empty:
        print("Error descargando datos. Revisa la conexión y el nombre del símbolo.")
        mt5_client.shutdown()
        return
        
    print("⚙️ Calculando indicadores SMC en el histórico...")
    
    # 2. Cálculo Vectorizado de Señales (Súper rápido)
    df['ATR'] = strategy.calculate_atr(df, config.ATR_PERIOD)
    fvg_minimo = df['ATR'] * config.ATR_MULTIPLIER_FVG
    
    df['Gap_Bull_Size'] = df['Low'] - df['High'].shift(2)
    df['FVG_Bull'] = (df['Low'] > df['High'].shift(2)) & (df['Gap_Bull_Size'] > fvg_minimo)
    
    df['Gap_Bear_Size'] = df['Low'].shift(2) - df['High']
    df['FVG_Bear'] = (df['Low'].shift(2) > df['High']) & (df['Gap_Bear_Size'] > fvg_minimo)
    
    # Obtener el tamaño del contrato de MT5 para calcular dólares reales
    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        print(f"Símbolo {symbol} no encontrado en MT5.")
        mt5_client.shutdown()
        return
    contract_size = symbol_info.trade_contract_size
    
    # Estadísticas
    ganadas = 0
    perdidas = 0
    be_cierres = 0
    balance = balance_inicial
    
    print("⏳ Simulando operaciones y gestionando Trades (SL, TP, BE)...")
    
    # 3. Bucle de Simulación de Trades
    for i in range(2, len(df) - 100): # Dejamos 100 velas al final de "margen" para que cierren operaciones
        
        # Barra de progreso visual
        if i % 250 == 0:
            pct = (i / len(df)) * 100
            sys.stdout.write(f"\rProgreso: [{ '#' * int(pct/2) }{ '-' * (50-int(pct/2)) }] {pct:.1f}%")
            sys.stdout.flush()
            
        row = df.iloc[i]
        signal = None
        
        # Identificar si en esta vela específica se generó señal
        if row['FVG_Bull']:
            signal = "BUY"
            sl = df.iloc[i-2]['Low']
        elif row['FVG_Bear']:
            signal = "SELL"
            sl = df.iloc[i-2]['High']
            
        # Si hubo señal, iniciamos el trade virtual
        if signal:
            entry = row['Close'] # Entramos al cierre de la vela que conformó el FVG
            
            # Validar Stop Loss y calcular Take Profit / BreakEven target
            if signal == "BUY":
                risk = entry - sl
                if risk <= 0: continue
                tp = entry + (risk * config.RISK_REWARD_RATIO)
                target_be = entry + (risk * config.MOVE_TO_BREAKEVEN_RATIO)
            else:
                risk = sl - entry
                if risk <= 0: continue
                tp = entry - (risk * config.RISK_REWARD_RATIO)
                target_be = entry - (risk * config.MOVE_TO_BREAKEVEN_RATIO)
                
            be_activado = False
            
            # Buscar en el FUTURO (velas i+1 en adelante) qué pasa con este trade
            for j in range(i+1, min(i+150, len(df))): # Buscamos hasta 150 velas hacia adelante
                f_row = df.iloc[j]
                high = f_row['High']
                low = f_row['Low']
                
                if signal == "BUY":
                    # Chequeo si el precio tocó BreakEven Target
                    if not be_activado and high >= target_be:
                        sl = entry # Movemos Stop Loss a precio de entrada
                        be_activado = True
                        
                    # Chequeo si el precio nos sacó por SL (o BE si ya lo habíamos movido)
                    if low <= sl:
                        if be_activado:
                            be_cierres += 1
                        else:
                            perdidas += 1
                            balance -= (risk * lote * contract_size)
                        break # Termina el trade
                        
                    # Chequeo si el precio tocó el TP
                    if high >= tp:
                        ganadas += 1
                        balance += ((tp - entry) * lote * contract_size)
                        break # Termina el trade
                        
                else: # SELL
                    if not be_activado and low <= target_be:
                        sl = entry
                        be_activado = True
                        
                    if high >= sl:
                        if be_activado:
                            be_cierres += 1
                        else:
                            perdidas += 1
                            balance -= (risk * lote * contract_size)
                        break
                        
                    if low <= tp:
                        ganadas += 1
                        balance += ((entry - tp) * lote * contract_size)
                        break

    mt5_client.shutdown()
    
    # 4. Reporte Final
    print("\n\n" + "="*50)
    print(f"🏁 RESULTADO BACKTEST SMC (10,000 velas M15)")
    print("="*50)
    print(f"🔵 Ganadas: {ganadas} | 🔴 Perdidas: {perdidas} | 🛡️ BreakEven (Cero Pérdida): {be_cierres}")
    
    total = ganadas + perdidas + be_cierres
    if total > 0:
        wr = (ganadas / (ganadas + perdidas)) * 100 if (ganadas + perdidas) > 0 else 0
        print(f"🎯 Win Rate Efectivo (sin contar BE): {wr:.2f}%")
        print(f"💰 Balance Final: ${balance:.2f} USD (Balance Inicial: ${balance_inicial})")
        print(f"📈 Beneficio Neto: ${(balance - balance_inicial):.2f} USD")
    else:
        print("❌ El bot no encontró entradas. Revisa los filtros ATR o el Símbolo.")
    print("="*50)

if __name__ == "__main__":
    simular_backtest()
