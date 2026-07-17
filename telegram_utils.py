import requests
import config

def enviar_telegram(mensaje):
    """
    Envía un mensaje a Telegram usando las credenciales en config.py.
    Retorna True si fue exitoso, False en caso contrario.
    """
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("Telegram: Token o Chat ID no configurado.")
        return False
        
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID, 
        "text": mensaje, 
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            return True
        else:
            print(f"Telegram Error: {response.text}")
            return False
    except Exception as e:
        print(f"Error enviando Telegram: {e}")
        return False
