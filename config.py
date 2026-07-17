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
RISK_REWARD_RATIO = 2.0 # TP por defecto si no hay liquidez cercana
MOVE_TO_BREAKEVEN_RATIO = 1.0 # Mover SL a precio de entrada cuando el precio alcance 1:1 R/R
SL_BUFFER_PIPS = 0.5 # Distancia extra de respiro para el Stop Loss debajo de la mecha
BREAKEVEN_PLUS_PIPS = 0.1 # Puntos extra a sumar al BreakEven (ej. para cubrir comisiones)

# Configuración de Estrategia SMC
ATR_PERIOD = 14
ATR_MULTIPLIER_FVG = 0.2 # Extremadamente relajado para permitir muchas entradas
KILLZONE_START_HOUR = 0 # Operar todo el día
KILLZONE_END_HOUR = 24 # Sin límite de horario
SMA_BODY_PERIOD = 20
OB_BODY_MULTIPLIER = 2.0

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
MAGIC_NUMBER = int(os.getenv("MAGIC_NUMBER", 123456))
