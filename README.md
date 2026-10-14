# 🚀 Uptime SaaS - Multi-Tenant Monitoring & Status Page Platform

Uma plataforma moderna de monitoramento de disponibilidade (Uptime), latência e geração de **Status Pages públicas**, construída com arquitetura **Multi-Tenant** escalável e isolamento rigoroso por empresa.

---

## 🛠️ Tecnologias & Stack

- **Backend / API Core:** FastAPI + Pydantic v2
- **Banco de Dados & ORM:** PostgreSQL + SQLAlchemy 2.0
- **Fila de Tarefas & Workers:** Celery + Redis
- **Requisições Assíncronas / Ping Engine:** HTTPX
- **Dashboard / Frontend:** Streamlit (Painel do Cliente + Painel Master Admin)
- **Containerização:** Docker & Docker Compose

---

## 📐 Arquitetura da Solução

```text
               +------------------------------------------------+
               |        Interface Visual (Streamlit)            |
               | - Painel do Cliente (Tenant Specific)          |
               | - Painel Admin Master (Global Control)         |
               +-----------------------+------------------------+
                                       |
                                       v
               +------------------------------------------------+
               |             FastAPI Backend Core               |
               | - Tenancy Middleware & Isolation               |
               | - Validação de Limite de Planos (Free/Pro)     |
               | - CRUD de Monitores & Status Page pública      |
               +-----------------------+------------------------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
        +-----------------------+               +-----------------------+
        |  PostgreSQL Database  |               |  Redis Queue Broker   |
        |  (Isolado por Tenant) |               +-----------+-----------+
        +-----------------------+                           |
                                                            v
                                                +-----------------------+
                                                |    Celery Worker      |
                                                | (Checagem assíncrona) |
                                                +-----------------------+

💡 Funcionalidades Principais
🏢 Multi-Tenancy Nativo: Isolamento total de dados por empresa via tenant_id.

📊 Validação Estrita de Planos: Limitação dinâmica de número de monitores e intervalo de checagem.

⚡ Disparo Assíncrono com Celery: Execução de testes de disponibilidade em background sem travar a API.

🌐 Status Page Pública: Endpoints públicos por slug (/status/slug-do-cliente) prontos para consumo.

🛡️ Painel Admin Master: Visão global consolidada de todas as empresas e estatísticas do SaaS protegida por autenticação.

🚀 Como Executar o Projeto Localmente
1. Clonar o Repositório e Subir os Containers
Bash
git clone [https://github.com/seu-usuario/uptime-saas.git](https://github.com/seu-usuario/uptime-saas.git)
cd uptime-saas
docker-compose up -d
2. Configurar o Ambiente Python
Bash
python -m venv venv
# No Windows:
venv\Scripts\activate
# No Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
3. Iniciar a API FastAPI
Bash
uvicorn app.main:app --reload
Acesse a documentação Swagger em: http://127.0.0.1:8000/docs

4. Iniciar o Celery Worker
Em um novo terminal com o ambiente virtual ativo:

Bash
celery -A celery_worker.celery_app worker --loglevel=info -P solo
5. Iniciar o Painel Streamlit
Em outro terminal:

Bash
streamlit run dashboard.py
Acesse a interface em: http://localhost:8501

🛡️ Licença
Este projeto foi desenvolvido para fins educacionais e portfólio de Engenharia de Software.
