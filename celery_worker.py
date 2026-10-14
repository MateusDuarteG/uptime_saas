from datetime import datetime
import os
import time
from celery import Celery
import httpx
from dotenv import load_dotenv  # <-- Importante para ler o .env
import requests

# Carrega as variáveis do arquivo .env que você criou
load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
WEBHOOK_URL = os.getenv(
    "WEBHOOK_URL", ""
)  # Vai ler a URL lá do seu arquivo .env recém-criado


def trigger_webhook_alert(
    monitor_name: str,
    url: str,
    is_up: bool,
    response_time_ms: float,
    error_message: str,
):
  """Dispara um POST HTTP para o Webhook configurado quando houver alteração ou falha."""
  if not WEBHOOK_URL:
    return  # Se não houver webhook configurado, não faz nada

  payload = {
      "evento": "UPTIME_CHECK",
      "monitor_name": monitor_name,
      "url": url,
      "status": "UP" if is_up else "DOWN",
      "response_time_ms": response_time_ms,
      "error_message": error_message,
      "checked_at": datetime.utcnow().isoformat(),
  }

  try:
    requests.post(WEBHOOK_URL, json=payload, timeout=5)
  except Exception as e:
    print(f"Erro ao disparar webhook: {e}")


# ... (o restante do código do celery_app e da task continua igualzinho você já mandou)