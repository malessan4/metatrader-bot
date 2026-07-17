import os
from dotenv import load_dotenv

load_dotenv() # Carga las variables del archivo .env

import MetaTrader5 as mt5

# Configuración General
SYMBOL = "XAUUSDm" # IMPORTANTE: Ajustar al nombre exacto de tu broker si es distinto (ej. "XAUUSD.a" o "Gold")
LOT_SIZE = 0.02
MAGIC_NUMBER = int(os.getenv("MAGIC_NUMBER", 123456)) # Identificador único para las operaciones del bot
DEVIATION = 20 # Desviación permitida (slippage) en puntos

# Temporalidades a monitorear
TIMEFRAMES = [mt5.TIMEFRAME_M15, mt5.TIMEFRAME_H1, mt5.TIMEFRAME_H4]

# Gestión de Riesgo (Risk Management)
RISK_REWARD_RATIO = 2.0 # Take Profit será 2 veces el tamaño del Stop Loss
MOVE_TO_BREAKEVEN_RATIO = 1.0 # Mover SL a precio de entrada cuando el precio alcance 1:1 R/R

# Configuración de Estrategia SMC
ATR_PERIOD = 14
ATR_MULTIPLIER_FVG = 0.5
SMA_BODY_PERIOD = 20
OB_BODY_MULTIPLIER = 2.0

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
MAGIC_NUMBER = int(os.getenv("MAGIC_NUMBER", 123456))
