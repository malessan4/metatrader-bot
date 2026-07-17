import time
import MetaTrader5 as mt5
import config
import mt5_client
import strategy
import telegram_utils

TF_MAPPING = {
    mt5.TIMEFRAME_M15: "M15",
    mt5.TIMEFRAME_H1: "H1",
    mt5.TIMEFRAME_H4: "H4"
}

def manage_open_positions():
    """
    Revisa las posiciones abiertas de nuestro bot y ajusta el SL a Breakeven 
    si se alcanza la relación 1:1.
    """
    positions = mt5_client.get_open_positions()
    for pos in positions:
        ticket = pos.ticket
        symbol = pos.symbol
        order_type = pos.type
        price_open = pos.price_open
        sl = pos.sl
        current_price = pos.price_current
        
        contract_size = mt5_client.get_contract_size(symbol)
        be_offset = getattr(config, 'BREAKEVEN_PLUS_USD', 2.0) / (config.LOT_SIZE * contract_size)
        
        # Calcular si ha alcanzado el 1:1 (50% del TP total de 1:2)
        if order_type == mt5.ORDER_TYPE_BUY:
            risk = price_open - sl
            if risk <= 0: continue # Evitar divisiones o lógicas erróneas si no hay SL
            
            target_1_1 = price_open + risk
            be_price = price_open + be_offset
            
            # Si superamos el 1:1 y el SL aún no está en breakeven + USD
            if current_price >= target_1_1 and sl < be_price:
                print(f"[{symbol}] Moviendo SL a Breakeven (+USD) para orden BUY {ticket}")
                mt5_client.modify_position_sl(ticket, symbol, be_price)
                telegram_utils.enviar_telegram(f"🛡 *Breakeven Activado*\nSímbolo: {symbol}\nOrden: BUY {ticket}\nGanancia de {config.BREAKEVEN_PLUS_USD} USD asegurada.")
                
        elif order_type == mt5.ORDER_TYPE_SELL:
            risk = sl - price_open
            if risk <= 0: continue
            
            target_1_1 = price_open - risk
            be_price = price_open - be_offset
            
            # Si superamos el 1:1 (el precio bajó lo suficiente)
            if current_price <= target_1_1 and sl > be_price:
                print(f"[{symbol}] Moviendo SL a Breakeven (+USD) para orden SELL {ticket}")
                mt5_client.modify_position_sl(ticket, symbol, be_price)
                telegram_utils.enviar_telegram(f"🛡 *Breakeven Activado*\nSímbolo: {symbol}\nOrden: SELL {ticket}\nGanancia de {config.BREAKEVEN_PLUS_USD} USD asegurada.")

def main():
    if not mt5_client.initialize():
        return
        
    print("Iniciando Bot SMC (FVG/CRT)...")
    print(f"Monitoreando {config.SYMBOL} en temporalidades: {[TF_MAPPING.get(t, str(t)) for t in config.TIMEFRAMES]}")
    
    try:
        while True:
            # 1. Gestionar operaciones abiertas (Ej. asegurar BreakEven)
            manage_open_positions()
            
            # 2. Analizar el mercado en cada temporalidad configurada
            for timeframe in config.TIMEFRAMES:
                # Obtenemos los datos de la temporalidad principal (ej. M15) y del filtro HTF (H1)
                df_m15 = mt5_client.get_data(config.SYMBOL, timeframe, n_candles=100)
                df_htf = mt5_client.get_data(config.SYMBOL, mt5.TIMEFRAME_H1, n_candles=30)
                if df_m15 is None or df_m15.empty:
                    continue
                    
                result = strategy.analyze_smc(df_m15, df_htf)
                
                # Si encontramos una señal FVG
                if result['signal']:
                    # Verificamos posiciones abiertas y órdenes pendientes
                    positions = mt5_client.get_open_positions()
                    pending = mt5_client.get_pending_orders()
                    
                    symbol_positions = [p for p in positions if p.symbol == config.SYMBOL]
                    symbol_pending = [o for o in pending if o.symbol == config.SYMBOL]
                    
                    already_open = len(symbol_positions) > 0
                    
                    # Verificamos temporizador y límite de órdenes
                    current_time = time.time()
                    timeout_secs = getattr(config, 'PENDING_ORDER_TIMEOUT_MINUTES', 30) * 60
                    recent_pending = any((current_time - o.time_setup) < timeout_secs for o in symbol_pending)
                    max_pending_reached = len(symbol_pending) >= getattr(config, 'MAX_PENDING_ORDERS', 3)
                    
                    if not already_open and not recent_pending and not max_pending_reached:
                        print(f"\n[!] SEÑAL {result['signal']} DETECTADA en {config.SYMBOL} ({TF_MAPPING.get(timeframe, str(timeframe))})")
                        print(f"Esperando retroceso a (Limit Entry): {result['entry']:.3f} | SL: {result['sl']:.3f} | TP (CRT): {result['tp']:.3f}")
                        
                        msg = f"🚀 *NUEVA ORDEN {result['signal']}*\nSímbolo: {config.SYMBOL} ({TF_MAPPING.get(timeframe, str(timeframe))})\nEntrada Limit: {result['entry']:.3f}\nSL: {result['sl']:.3f}\nTP CRT: {result['tp']:.3f}"
                        telegram_utils.enviar_telegram(msg)
                        
                        # Ejecutar orden a mercado
                        order_res = mt5_client.send_market_order(config.SYMBOL, result['signal'], config.LOT_SIZE, result['entry'], result['sl'], result['tp'])
                        if order_res and order_res.retcode == mt5.TRADE_RETCODE_DONE:
                            print(f">> Orden ejecutada con éxito. Ticket: {order_res.order}")
                        else:
                            print(f">> Error al ejecutar orden: {order_res}")
                        
                        # Pausa para no saturar si acaba de mandar una señal
                        time.sleep(10)
                        
            # Pausa de ciclo para no consumir mucha CPU
            time.sleep(15) 
            
    except KeyboardInterrupt:
        print("\nDeteniendo bot manualmente...")
    finally:
        mt5_client.shutdown()

if __name__ == "__main__":
    main()
