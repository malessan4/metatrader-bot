import MetaTrader5 as mt5
import pandas as pd
import config

def initialize():
    """Conecta a la terminal de MetaTrader 5"""
    if not mt5.initialize():
        print("initialize() fallo, error code =", mt5.last_error())
        return False
    print("Conectado a MetaTrader 5, versión:", mt5.version())
    return True

def shutdown():
    mt5.shutdown()

def get_data(symbol, timeframe, n_candles=100):
    """Obtiene datos históricos y los formatea en un DataFrame de pandas"""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n_candles)
    if rates is None:
        print(f"Error al obtener datos para {symbol} en la temporalidad {timeframe}")
        return None
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.rename(columns={'time': 'Time', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'tick_volume': 'Volume'}, inplace=True)
    return df

def send_market_order(symbol, order_type, lot, price, sl, tp):
    """Envía una orden de mercado con SL y TP"""
    point = mt5.symbol_info(symbol).point
    
    if order_type == "BUY":
        mt5_order_type = mt5.ORDER_TYPE_BUY
    elif order_type == "SELL":
        mt5_order_type = mt5.ORDER_TYPE_SELL
    elif order_type == "BUY_LIMIT":
        mt5_order_type = mt5.ORDER_TYPE_BUY_LIMIT
    elif order_type == "SELL_LIMIT":
        mt5_order_type = mt5.ORDER_TYPE_SELL_LIMIT
    else:
        return None
        
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot),
        "type": mt5_order_type,
        "price": float(price),
        "sl": float(sl),
        "tp": float(tp),
        "deviation": config.DEVIATION,
        "magic": config.MAGIC_NUMBER,
        "comment": "SMC Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC, # Algunos brokers requieren FOK, ajustar de ser necesario
    }
    
    result = mt5.order_send(request)
    return result

def modify_position_sl(ticket, symbol, new_sl):
    """Modifica el Stop Loss de una posición existente (para el Breakeven)"""
    position = mt5.positions_get(ticket=ticket)
    if not position:
        return None
    
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": symbol,
        "sl": float(new_sl),
        "position": ticket
    }
    
    result = mt5.order_send(request)
    return result
    
def get_open_positions():
    """Obtiene las posiciones abiertas por el bot"""
    positions = mt5.positions_get(magic=config.MAGIC_NUMBER)
    if positions is None:
        return []
    return positions
