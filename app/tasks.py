# app/tasks.py
import time
import requests
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from celery_worker import celery_app, trigger_webhook_alert
from app.database import SessionLocal
from app.models import Monitor, MonitorLog

@celery_app.task(name="tasks.check_all_active_monitors")
def check_all_active_monitors():
    """Busca monitores ativos diretamente no banco de dados e dispara as checagens."""
    db: Session = SessionLocal()
    try:
        monitores_ativos = db.query(Monitor).filter(Monitor.is_active == True).all()
        
        if not monitores_ativos:
            return "Nenhum monitor ativo encontrado para checagem."

        enviados = 0
        for monitor in monitores_ativos:
            # Ignora monitores sem URL válida
            if not monitor.url or not monitor.url.startswith("http"):
                continue

            check_single_monitor.delay(
                str(monitor.id), 
                str(monitor.tenant_id), 
                monitor.name, 
                monitor.url
            )
            enviados += 1
            
        return f"{enviados} monitores enviados para fila de checagem."
    except Exception as e:
        return f"Erro ao processar checagens: {str(e)}"
    finally:
        db.close()

@celery_app.task(name="tasks.check_single_monitor")
def check_single_monitor(monitor_id: str, tenant_id: str, monitor_name: str, url: str):
    """Executa a requisição HTTP, mede o tempo de resposta e salva o MonitorLog no banco."""
    start_time = time.time()
    error_message = ""
    try:
        response = requests.get(url, timeout=10)
        latency_ms = round((time.time() - start_time) * 1000, 2)
        status_code = response.status_code
        is_up = 200 <= status_code < 400
        if not is_up:
            error_message = f"Status code inesperado: {status_code}"
    except requests.RequestException as e:
        latency_ms = 0.0
        status_code = 0
        is_up = False
        error_message = str(e)

    # Converte as strings para objetos UUID nativos para o SQLite/SQLAlchemy processar sem conflito
    db: Session = SessionLocal()
    try:
        novo_log = MonitorLog(
            monitor_id=uuid.UUID(monitor_id),
            tenant_id=uuid.UUID(tenant_id),
            status_code=status_code,
            response_time_ms=latency_ms,
            is_up=is_up,
            error_message=error_message
        )
        db.add(novo_log)
        db.commit()
    except Exception as db_err:
        db.rollback()
        print(f"Erro ao salvar MonitorLog no banco: {db_err}")
    finally:
        db.close()

    # Dispara o webhook caso o site esteja fora do ar (DOWN)
    if not is_up:
        trigger_webhook_alert(
            monitor_name=monitor_name,
            url=url,
            is_up=is_up,
            response_time_ms=latency_ms,
            error_message=error_message
        )

    return {"monitor_id": monitor_id, "is_up": is_up, "latency_ms": latency_ms}