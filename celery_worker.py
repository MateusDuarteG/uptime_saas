from celery import Celery
from datetime import datetime
from celery.schedules import crontab
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

# Instância do Celery com Redis como Broker e Result Backend
celery_app = Celery(
    "saas_monitoring",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
)

# Agendamento Periódico (Celery Beat)
celery_app.conf.beat_schedule = {
    "run-checks-every-minute": {
        "task": "tasks.check_all_active_monitors",
        "schedule": 60.0,  # Executa a cada 60 segundos (1 minuto)
    },
}

# No seu celery_worker.py, mude a instância do Celery para:
celery_app = Celery(
    "saas_monitoring",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["app.tasks"] # <-- Adiciona esta linha para o worker achar as tarefas dentro de app/
)