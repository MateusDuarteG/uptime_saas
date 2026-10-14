from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl
import uuid

from app.database import get_db, engine, Base
from app import models

# Cria as tabelas no banco automaticamente ao iniciar
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Uptime SaaS API", version="1.0.0")

# --- SCHEMAS Pydantic ---
class MonitorCreate(BaseModel):
    name: str
    url: str
    check_type: models.CheckType = models.CheckType.HTTP
    interval_seconds: int = 60

class MonitorResponse(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    check_type: models.CheckType
    interval_seconds: int
    is_active: bool

    class Config:
        from_attributes = True

# --- SIMULAÇÃO DE AUTH & MULTI-TENANCY ---
def get_current_tenant(tenant_id: str, db: Session = Depends(get_db)) -> models.Tenant:
    try:
        t_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Tenant ID inválido.")
    
    tenant = db.query(models.Tenant).filter(models.Tenant.id == t_uuid).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant (Empresa) não encontrado.")
    return tenant

# --- ENDPOINTS DE TENANTS ---

@app.post("/api/v1/tenants", status_code=status.HTTP_201_CREATED)
def create_tenant_test(name: str, db: Session = Depends(get_db)):
    """Cria um tenant de testes rapidamente para gerar o ID"""
    new_tenant = models.Tenant(
        name=name,
        plan_type=models.PlanType.FREE,
        max_monitors=5,
        min_interval_seconds=60
    )
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)
    return {"tenant_id": str(new_tenant.id), "name": new_tenant.name}


# --- ENDPOINTS DE MONITORES ---

@app.post("/api/v1/monitors", response_model=MonitorResponse, status_code=status.HTTP_201_CREATED)
def create_monitor(
    monitor_data: MonitorCreate,
    tenant_id: str,
    db: Session = Depends(get_db)
):
    tenant = get_current_tenant(tenant_id, db)

    current_monitors_count = db.query(models.Monitor).filter(
        models.Monitor.tenant_id == tenant.id
    ).count()

    if current_monitors_count >= tenant.max_monitors:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Limite do plano atingido! Seu plano atual ({tenant.plan_type}) "
                f"permite no máximo {tenant.max_monitors} monitores."
            )
        )

    if monitor_data.interval_seconds < tenant.min_interval_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"O intervalo mínimo de checagem para o seu plano ({tenant.plan_type}) "
                f"é de {tenant.min_interval_seconds} segundos."
            )
        )

    new_monitor = models.Monitor(
        tenant_id=tenant.id,
        name=monitor_data.name,
        url=str(monitor_data.url),
        check_type=monitor_data.check_type,
        interval_seconds=monitor_data.interval_seconds
    )

    db.add(new_monitor)
    db.commit()
    db.refresh(new_monitor)

    return new_monitor


@app.get("/api/v1/monitors", response_model=list[MonitorResponse])
def list_monitors(
    tenant_id: str,
    db: Session = Depends(get_db)
):
    tenant = get_current_tenant(tenant_id, db)
    monitors = db.query(models.Monitor).filter(models.Monitor.tenant_id == tenant.id).all()
    return monitors


@app.post("/api/v1/monitors/run-checks")
def trigger_all_monitors(db: Session = Depends(get_db)):
    """
    Varre todos os monitores ativos e despacha as tarefas para o Celery.
    """
    from celery_worker import check_monitor_task
    
    active_monitors = db.query(models.Monitor).filter(models.Monitor.is_active == True).all()
    
    dispatched_count = 0
    for monitor in active_monitors:
        check_monitor_task.delay(str(monitor.id))
        dispatched_count += 1
        
    return {
        "message": "Tarefas de checagem despachadas com sucesso!",
        "total_dispatched": dispatched_count
    }

# --- ENDPOINTS DE STATUS PAGE PÚBLICA ---

@app.post("/api/v1/status-pages", status_code=status.HTTP_201_CREATED)
def create_status_page(
    tenant_id: str,
    slug: str,
    title: str,
    db: Session = Depends(get_db)
):
    """
    Cria ou vincula uma Status Page pública para o tenant.
    """
    tenant = get_current_tenant(tenant_id, db)

    # Verifica se já existe status page para este tenant
    existing = db.query(models.StatusPage).filter(models.StatusPage.tenant_id == tenant.id).first()
    if existing:
        existing.slug = slug
        existing.title = title
        db.commit()
        db.refresh(existing)
        return {"message": "Status Page atualizada com sucesso!", "slug": existing.slug}

    new_page = models.StatusPage(
        tenant_id=tenant.id,
        slug=slug,
        title=title,
        is_public=True
    )
    db.add(new_page)
    db.commit()
    db.refresh(new_page)
    
    return {"message": "Status Page criada com sucesso!", "slug": new_page.slug}


@app.get("/api/v1/status/{slug}")
def get_public_status_page(slug: str, db: Session = Depends(get_db)):
    """
    ENDPOINT PÚBLICO: Retorna o status de todos os monitores do tenant 
    baseado no slug da Status Page (sem precisar de autenticação ou tenant_id).
    """
    # 1. Busca a página de status pelo slug
    status_page = db.query(models.StatusPage).filter(models.StatusPage.slug == slug, models.StatusPage.is_public == True).first()
    if not status_page:
        raise HTTPException(status_code=404, detail="Status Page não encontrada ou privada.")

    # 2. Busca o tenant dono da página
    tenant = db.query(models.Tenant).filter(models.Tenant.id == status_page.tenant_id).first()

    # 3. Busca todos os monitores do tenant
    monitors = db.query(models.Monitor).filter(models.Monitor.tenant_id == tenant.id, models.Monitor.is_active == True).all()

    # 4. Monta o resumo de saúde de cada monitor (pegando o último log registrado)
    monitors_status = []
    for monitor in monitors:
        latest_log = db.query(models.MonitorLog).filter(
            models.MonitorLog.monitor_id == monitor.id
        ).order_by(models.MonitorLog.checked_at.desc()).first()

        monitors_status.append({
            "name": monitor.name,
            "url": monitor.url,
            "is_up": latest_log.is_up if latest_log else None,
            "response_time_ms": latest_log.response_time_ms if latest_log else None,
            "last_checked": latest_log.checked_at if latest_log else "Nunca checado"
        })

    return {
        "company_name": tenant.name,
        "page_title": status_page.title,
        "monitors": monitors_status
    }

# --- ROTA ADMINISTRATIVA (MASTER) ---
@app.get("/api/v1/admin/overview")
def admin_overview(admin_key: str, db: Session = Depends(get_db)):
    """
    Painel Master: Retorna todas as empresas cadastradas e estatísticas gerais do SaaS.
    Protegido por uma chave secreta de admin simples para o MVP.
    """
    # Senha mestre simples do admin (em produção estaria em hash no banco/env)
    if admin_key != "admin123master":
        raise HTTPException(status_code=403, detail="Acesso negado. Chave de Admin inválida.")
    
    tenants = db.query(models.Tenant).all()
    total_monitors = db.query(models.Monitor).count()
    total_logs = db.query(models.MonitorLog).count()

    tenants_data = []
    for t in tenants:
        monitors_count = db.query(models.Monitor).filter(models.Monitor.tenant_id == t.id).count()
        tenants_data.append({
            "tenant_id": str(t.id),
            "name": t.name,
            "plan_type": t.plan_type,
            "max_monitors": t.max_monitors,
            "monitors_registered": monitors_count,
            "created_at": t.created_at
        })

    return {
        "total_tenants": len(tenants),
        "total_monitors": total_monitors,
        "total_logs_recorded": total_logs,
        "tenants": tenants_data
    }