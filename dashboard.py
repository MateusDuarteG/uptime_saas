from datetime import datetime
import pandas as pd
import plotly.express as px
import requests
import sqlalchemy
from sqlalchemy.orm import sessionmaker
import streamlit as st

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Uptime SaaS - Painel de Controle", page_icon="🚀", layout="wide"
)

API_URL = "http://api:8000/api/v1"
BASE_URL = "http://api:8000"

# Conexão direta com o banco SQLite local para ler os gráficos de latência em tempo real
DATABASE_URL = "sqlite:///./uptime.db"
engine = sqlalchemy.create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# --- ESTADOS DA SESSÃO ---
if "token" not in st.session_state:
    st.session_state["token"] = None
if "user_email" not in st.session_state:
    st.session_state["user_email"] = None

def get_auth_headers():
    token = st.session_state.get("token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}

def api_get_monitors(t_id):
    try:
        headers = get_auth_headers()
        response = requests.get(f"{API_URL}/monitors", params={"tenant_id": t_id}, headers=headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            st.error("🔒 Sessão expirada ou não autorizada. Faça login novamente.")
        elif response.status_code == 404:
            st.error("❌ Locatário não encontrado no banco de dados.")
    except requests.exceptions.ConnectionError:
        st.error("🚨 Não foi possível conectar à API FastAPI.")
    return []

# --- FUNÇÕES AUXILIARES ---
def get_latency_logs(monitor_id):
    db = SessionLocal()
    try:
        query = f"""
            SELECT checked_at, response_time_ms, is_up, status_code 
            FROM monitor_logs 
            WHERE monitor_id = '{monitor_id}' 
            ORDER BY checked_at DESC 
            LIMIT 50
        """
        df = pd.read_sql(query, con=db.connection())
        if not df.empty:
            df = df.sort_values("checked_at")
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        db.close()



# --- SIDEBAR: NAVEGAÇÃO & SESSÃO ---
st.sidebar.title("🔐 Menu SaaS")

if st.session_state["token"]:
    st.sidebar.success(f"👤 Logado como: {st.session_state['user_email']}")
    if st.sidebar.button("Sair (Logout)"):
        st.session_state["token"] = None
        st.session_state["user_email"] = None
        st.rerun()

menu_options = [
    "Entrar / Criar Conta",
    "Visão Geral do Cliente",
    "Cadastrar Nova Empresa (Tenant)",
    "Cadastrar Novo Monitor",
    "Página de status pública",
    "Painel Admin (Mestre)",
]

menu = st.sidebar.radio("Selecione o Painel:", menu_options)


# ==========================================
# PÁGINA: LOGIN / ENTRAR
# ==========================================
if menu == "Entrar / Criar Conta":
    st.title("🔑 Autenticação do SaaS")

    tab1, tab2 = st.tabs(["Fazer Login", "Criar Primeira Conta"])

    with tab1:
        st.subheader("Login de Usuário")
        with st.form("form_login"):
            email_input = st.text_input("E-mail")
            password_input = st.text_input("Senha", type="password")
            submit_login = st.form_submit_button("Entrar")

            if submit_login:
                if email_input and password_input:
                    try:
                        # O endpoint /token do FastAPI espera x-www-form-urlencoded (username e password)
                        response = requests.post(
                            f"{BASE_URL}/token",
                            data={"username": email_input, "password": password_input},
                        )
                        if response.status_code == 200:
                            data = response.json()
                            st.session_state["token"] = data["access_token"]
                            st.session_state["user_email"] = email_input
                            
                            # Opcional: Se a sua rota /token ou /users/me retornar o tenant_id, salve-o aqui:
                            # st.session_state["tenant_id"] = data.get("tenant_id", "c6abfa80-a6d1-447f-87a3-2ac1633f2a86")
                            
                            st.success("🎉 Login realizado com sucesso!")
                            st.rerun()
                        else:
                            st.error("❌ E-mail ou senha incorretos.")
                    except Exception as e:
                        st.error(f"Erro de conexão com a API: {e}")
                else:
                    st.warning("⚠️ Preencha e-mail e senha.")

    with tab2:
        st.subheader("Cadastrar Novo Usuário e Vincular a Empresa")
        with st.form("form_register"):
            reg_email = st.text_input("E-mail do Usuário")
            reg_password = st.text_input("Defina uma Senha", type="password")
            reg_tenant_id = st.text_input(
                "ID da Empresa (UUID Tenant):",
                value="c6abfa80-a6d1-447f-87a3-2ac1633f2a86",
            )
            submit_reg = st.form_submit_button("Criar Usuário")

            if submit_reg:
                if reg_email and reg_password and reg_tenant_id:
                    try:
                        response = requests.post(
                            f"{API_URL}/create-first-user",
                            params={
                                "email": reg_email,
                                "password": reg_password,
                                "tenant_id": reg_tenant_id,
                            },
                        )
                        if response.status_code == 200:
                            st.success("✅ Usuário criado com sucesso! Agora você já pode fazer o Login.")
                        else:
                            st.error(f"Erro ao criar usuário: {response.text}")
                    except Exception as e:
                        st.error(f"Erro de conexão: {e}")


# ==========================================
# PÁGINA 1: VISÃO GERAL & GRÁFICOS DE LATÊNCIA
# ==========================================
elif menu == "Visão Geral do Cliente":
    st.title("📊 Painel de Controle da Empresa & Latência")

    if not st.session_state["token"]:
        st.warning("🔒 Você precisa fazer login na aba 'Entrar / Criar Conta' para acessar este painel.")
    else:
        st.markdown(
            "Gerencie e acompanhe o histórico de tempo de resposta dos seus serviços em tempo real."
        )

        tenant_id_input = st.text_input(
            "Insira seu ID de locatário (UUID da Empresa):",
            value="c6abfa80-a6d1-447f-87a3-2ac1633f2a86",
        )

        if tenant_id_input:
            col1, col2 = st.columns([4, 1])
            with col2:
                if st.button("Executar Checagens"):
                    try:
                        res = requests.post(f"{API_URL}/monitors/run-checks")
                        if res.status_code == 200:
                            st.success("Checagens disparadas!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

            monitors = api_get_monitors(tenant_id_input)

            if monitors:
                st.markdown("### 🖥️ Seus Monitores Ativos")

                monitor_names = {
                    m["name"] if m["name"] else f"Monitor {m['id']}": m["id"]
                    for m in monitors
                }
                selected_name = st.selectbox(
                    "Selecione um monitor para ver os gráficos de latência:",
                    list(monitor_names.keys()),
                )
                selected_id = monitor_names[selected_name]

                df_logs = get_latency_logs(selected_id)

                if not df_logs.empty:
                    latest_status = df_logs.iloc[-1]["is_up"]
                    latest_latency = df_logs.iloc[-1]["response_time_ms"]

                    m_col1, m_col2 = st.columns(2)
                    with m_col1:
                        st.metric(
                            label="Status Atual",
                            value="UP 🟢" if latest_status else "DOWN 🔴",
                        )
                    with m_col2:
                        st.metric(label="Última Latência", value=f"{latest_latency} ms")

                    fig = px.line(
                        df_logs,
                        x="checked_at",
                        y="response_time_ms",
                        markers=True,
                        title=f"Tempo de Resposta (ms) - {selected_name}",
                        labels={
                            "checked_at": "Horário",
                            "response_time_ms": "Latência (ms)",
                        },
                    )
                    fig.update_traces(line_color="#00CC96", line_width=2)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(
                        "Ainda não há logs de verificação para este monitor. Clique em 'Executar Checagens'."
                    )

                st.markdown("---")
                st.markdown("📋 **Tabela Bruta de Monitores**")
                df_monitors = pd.DataFrame(monitors)
                st.dataframe(df_monitors, use_container_width=True)


# ==========================================
# PÁGINA 2: CADASTRAR NOVA EMPRESA (TENANT)
# ==========================================
elif menu == "Cadastrar Nova Empresa (Tenant)":
    st.title("🏢 Criar Nova Empresa (Tenant)")
    st.markdown("Cadastre uma nova empresa para gerar o seu ID de locatário.")

    with st.form("form_create_tenant"):
        tenant_name = st.text_input("Nome da Empresa")
        submitted_tenant = st.form_submit_button("Criar Empresa")

        if submitted_tenant:
            if tenant_name:
                try:
                    response = requests.post(
                        f"{API_URL}/tenants", params={"name": tenant_name}
                    )
                    if response.status_code == 201:
                        data = response.json()
                        st.success("🎉 Empresa criada com sucesso! Copie o seu Tenant ID abaixo:")
                        st.code(data["tenant_id"])
                        st.balloons()
                    else:
                        st.error(f"Erro ao criar empresa: {response.text}")
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")


# ==========================================
# PÁGINA 3: CADASTRAR NOVO MONITOR
# ==========================================
elif menu == "Cadastrar Novo Monitor":
    st.title("➕ Adicionar Novo Endpoint")

    if not st.session_state["token"]:
        st.warning("🔒 Faça login na aba 'Entrar / Criar Conta' para cadastrar monitores.")
    else:
        tenant_id_input = st.text_input(
            "ID do locatário (Empresa):", value="c6abfa80-a6d1-447f-87a3-2ac1633f2a86"
        )

        with st.form("form_create_monitor"):
            name = st.text_input("Nome do Serviço")
            url = st.text_input("URL Completa (ex: https://site.com.br)")
            check_type = st.selectbox("Tipo de Checagem", ["HTTP", "PING", "PORT"])
            interval_seconds = st.slider(
                "Intervalo (segundos)", min_value=30, max_value=300, value=60
            )

            submitted = st.form_submit_button("Cadastrar Monitor")

            if submitted:
                payload = {
                    "name": name,
                    "url": url,
                    "check_type": check_type,
                    "interval_seconds": interval_seconds,
                }
                try:
                    response = requests.post(
                        f"{API_URL}/monitors",
                        params={"tenant_id": tenant_id_input},
                        json=payload,
                    )
                    if response.status_code == 201:
                        st.success("🎉 Monitor cadastrado com sucesso!")
                        st.balloons()
                    elif response.status_code == 403:
                        st.error("❌ Limite do plano atingido! Faça upgrade.")
                    else:
                        st.error(f"Erro: {response.text}")
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")


# ==========================================
# PÁGINA 4: STATUS PAGE PÚBLICA
# ==========================================
elif menu == "Página de status pública":
    st.title("🌐 Configurar Página de Status")

    tenant_id_input = st.text_input(
        "ID do locatário (Empresa):", value="c6abfa80-a6d1-447f-87a3-2ac1633f2a86"
    )
    slug_input = st.text_input(
        "Slug da Página (ex: minha-empresa-status)", value="gardenall-status"
    )
    title_input = st.text_input("Título Oficial", value="Status Oficial dos Serviços")

    if st.button("Salvar página de status"):
        res = requests.post(
            f"{API_URL}/status-pages",
            params={
                "tenant_id": tenant_id_input,
                "slug": slug_input,
                "title": title_input,
            },
        )
        if res.status_code == 201:
            st.success("✅ Status Page salva com sucesso!")
            st.markdown(
                f"🔗 [Acessar Página Pública](http://127.0.0.1:8000/api/v1/status/{slug_input})"
            )


# ==========================================
# PÁGINA 5: PAINEL ADMIN (MASTER) - PROTEGIDO
# ==========================================
elif menu == "Painel Admin (Mestre)":
    st.title("🛡️ Painel Administrativo Global (Master)")
    st.markdown("Área restrita aos donos da plataforma gerenciando todas as empresas cadastradas.")

    admin_password = st.text_input("Digite a Senha Mestre do Admin", type="password")

    if st.button("Acessar Painel Master"):
        if admin_password == "admin123master":
            st.session_state["is_admin"] = True
        else:
            st.error("Senha incorreta!")

    if st.session_state.get("is_admin", False):
        st.success("🔓 Acesso Autorizado - Bem-vindo, Administrador!")

        try:
            response = requests.get(
                f"{API_URL}/admin/overview", params={"admin_key": "admin123master"}
            )
            if response.status_code == 200:
                data = response.json()

                c1, c2, c3 = st.columns(3)
                c1.metric("Total de Empresas (Tenants)", data["total_tenants"])
                c2.metric("Total de Monitores Globais", data["total_monitors"])
                c3.metric("Logs Registrados no Banco", data["total_logs_recorded"])

                st.markdown("---")
                st.subheader("📋 Lista Completa de Empresas Cadastradas no SaaS")

                df_tenants = pd.DataFrame(data["tenants"])
                st.dataframe(df_tenants, use_container_width=True)

            else:
                st.error("Erro ao buscar dados administrativos.")
        except Exception as e:
            st.error(f"Erro de conexão: {e}")
    else:
        st.info("🔒 Insira a senha mestre acima para visualizar o painel global da plataforma.")