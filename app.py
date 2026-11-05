import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime, date
import io
from PIL import Image

# Configuração da página
st.set_page_config(
    page_title="Gestor Prático SaaS - Gestão",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS
st.markdown("""
    <style>
        .main-title { font-size: 1.4rem !important; font-weight: bold; color: #1E3A8A; margin-bottom: 0px; }
        .sub-title { color: #666; font-size: 0.8rem; margin-top: -3px; margin-bottom: 10px; }
        .stButton button { border-radius: 8px; font-weight: bold; }
        div.stExpander { border-radius: 10px !important; border: 1px solid #e2e8f0 !important; margin-bottom: 6px; background-color: #fff; }
    </style>
""", unsafe_allow_html=True)

# INICIALIZAÇÃO DO SUPABASE
@st.cache_resource
def init_supabase() -> Client:
    if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
        st.error("⚠️ As credenciais do Supabase não foram encontradas nos Secrets!")
        st.stop()
    url = st.secrets["SUPABASE_URL"].strip().rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[:-8]
    key = st.secrets["SUPABASE_KEY"].strip()
    return create_client(url, key)

supabase = init_supabase()

# ESTADOS DE SESSÃO
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_data" not in st.session_state:
    st.session_state.user_data = None
if "filtro_ativo" not in st.session_state:
    st.session_state.filtro_ativo = "Todos"

# AUTENTICAÇÃO
def autenticar_usuario(usuario_input, senha_input):
    try:
        res = supabase.table("assinantes").select("*").eq("usuario", usuario_input.strip()).execute()
        if res.data and len(res.data) > 0:
            user = res.data[0]
            if user["senha"] == senha_input:
                return user, None
            else:
                return None, "Senha incorreta."
        return None, "Utilizador não encontrado."
    except Exception as e:
        return None, f"Erro ao autenticar: {e}"

# --- ECRÃ DE LOGIN ---
if not st.session_state.logged_in:
    st.markdown('<p class="main-title">📱 Gestor Prático SaaS</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Acesso Restrito</p>', unsafe_allow_html=True)
    
    with st.form("login_form"):
        usuario = st.text_input("👤 Utilizador")
        senha = st.text_input("🔑 Palavra-passe", type="password")
        btn_login = st.form_submit_button("Entrar no Sistema", use_container_width=True)
        
        if btn_login:
            user_data, erro = autenticar_usuario(usuario, senha)
            if user_data:
                if not user_data.get("ativo", True):
                    st.error("⚠️ Assinatura suspensa. Contacte o suporte.")
                else:
                    st.session_state.logged_in = True
                    st.session_state.user_data = user_data
                    st.success("✅ Login efetuado com sucesso!")
                    st.rerun()
            else:
                st.error(f"❌ {erro}")
    st.stop()

# --- CONFIGURAÇÃO INICIAL (PRIMEIRO ACESSO) ---
user = st.session_state.user_data
if st.session_state.logged_in and user.get("deve_trocar_credenciais", False):
    st.markdown('<p class="main-title">🔐 Configuração Inicial</p>', unsafe_allow_html=True)
    with st.form("form_troca_inicial"):
        novo_usuario = st.text_input("Novo Nome de Utilizador", value=user["usuario"])
        nova_senha = st.text_input("Nova Palavra-passe", type="password")
        confirma_senha = st.text_input("Confirmar Palavra-passe", type="password")
        nicho_selecionado = st.selectbox("Segmento de Atuação", ["Prestador de Serviços", "Personal Trainer / Fitness", "Saúde / Clínica", "Geral / Outros"])
        
        btn_atualizar = st.form_submit_button("Guardar e Acessar", use_container_width=True)
        if btn_atualizar:
            if novo_usuario and nova_senha and nova_senha == confirma_senha:
                if len(nova_senha) >= 4:
                    try:
                        supabase.table("assinantes").update({
                            "usuario": novo_usuario.strip(),
                            "senha": nova_senha,
                            "nicho": nicho_selecionado,
                            "deve_trocar_credenciais": False
                        }).eq("id", user["id"]).execute()
                        
                        user["usuario"] = novo_usuario.strip()
                        user["nicho"] = nicho_selecionado
                        user["deve_trocar_credenciais"] = False
                        st.session_state.user_data = user
                        st.success("✅ Configurações salvas!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Erro: {ex}")
                else:
                    st.error("⚠️ A palavra-passe deve ter pelo menos 4 caracteres.")
            else:
                st.error("⚠️ Preencha os campos corretamente.")
    st.stop()

# VERIFICA SE É O MASTER ADMIN
is_master_admin = (user.get("usuario") == "admin")

# RÓTULOS POR NICHO
nicho = user.get("nicho", "Prestador de Serviços")
if nicho == "Personal Trainer / Fitness":
    lbl_cliente, lbl_id, lbl_demanda = "Aluno / Cliente", "Plano / Frequência", "Ficha de Treino / Meta"
elif nicho == "Saúde / Clínica":
    lbl_cliente, lbl_id, lbl_demanda = "Paciente", "Cartão SUS / CPF", "Caso / Demanda Clínica"
else:
    lbl_cliente, lbl_id, lbl_demanda = "Cliente / Solicitante", "Cód. Pedido / Referência", "Descrição do Serviço"

# FUNÇÕES DE DADOS
def comprimir_imagem(uploaded_file):
    try:
        image = Image.open(uploaded_file)
        if image.mode in ("RGBA", "P"): image = image.convert("RGB")
        image.thumbnail((800, 800))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=60, optimize=True)
        return buffer.getvalue()
    except Exception:
        return None

def carregar_demandas(assinante_id):
    try:
        res = supabase.table("pacientes_demandas").select("*").eq("assinante_id", assinante_id).order("id", desc=True).execute()
        return res.data if res.data else []
    except Exception:
        return []

def salvar_demanda(assinante_id, nome, telefone, cartao_sus, demanda, reportado, prioridade, data_previsao):
    try:
        status_inicial = "Delegado" if reportado and reportado.strip() != "" else "Em Aberto"
        dados = {
            "assinante_id": assinante_id, "nome": nome, "telefone": telefone,
            "cartao_sus": cartao_sus, "demanda": demanda, "reportado": reportado,
            "status": status_inicial, "prioridade": prioridade, "data_previsao": str(data_previsao) if data_previsao else None
        }
        return supabase.table("pacientes_demandas").insert(dados).execute()
    except Exception as e:
        raise Exception(f"Erro ao guardar: {e}")

def atualizar_status(demanda_id, novo_status):
    try:
        atualizacao = {"status": novo_status}
        if novo_status == "Encerrado":
            atualizacao["data_resolucao"] = datetime.now().isoformat()
        supabase.table("pacientes_demandas").update(atualizacao).eq("id", demanda_id).execute()
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")

# --- MENU LATERAL DE NAVEGAÇÃO ---
st.sidebar.markdown(f"### ⚙️ {user.get('nome_empresa', 'Gestor Prático')}")
st.sidebar.markdown(f"**Segmento:** {nicho}")
st.sidebar.markdown("---")

# Se for admin, a primeira opção é o Painel Master focado puramente em gestão
opcoes_menu = ["📋 Operacional", "📊 Meus Indicadores (BI)", "❓ Central de Ajuda"]
if is_master_admin:
    opcoes_menu.insert(0, "👑 Gestão do Sistema (Master)")

aba_selecionada = st.sidebar.radio("Navegação", opcoes_menu)

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Sair do Sistema", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.user_data = None
    st.rerun()

dados_demandas = carregar_demandas(user["id"])
df = pd.DataFrame(dados_demandas) if dados_demandas else pd.DataFrame()

# ==========================================
# GESTÃO DO SISTEMA (MASTER) - EXCLUSIVO PARA O DONO
# ==========================================
if is_master_admin and aba_selecionada == "👑 Gestão do Sistema (Master)":
    st.markdown('<p class="main-title">👑 Painel de Controlo e Gestão do Micro-SaaS</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Métricas de negócio, receita recorrente, controlo de assinantes e saúde da plataforma</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    try:
        res_assinantes = supabase.table("assinantes").select("*").execute()
        df_assinantes = pd.DataFrame(res_assinantes.data) if res_assinantes.data else pd.DataFrame()
        
        res_todas_demandas = supabase.table("pacientes_demandas").select("*").execute()
        df_todas_demandas = pd.DataFrame(res_todas_demandas.data) if res_todas_demandas.data else pd.DataFrame()
        
        if not df_assinantes.empty:
            total_assinantes = len(df_assinantes)
            ativos = len(df_assinantes[df_assinantes["ativo"] == True]) if "ativo" in df_assinantes.columns else total_assinantes
            inadimplentes = total_assinantes - ativos
            mrr_estimado = ativos * 14.90
            
            # Cards de Métricas do Negócio (SaaS KPIs)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total de Assinantes", total_assinantes)
            c2.metric("Clientes Ativos", ativos, delta="🟢 Regular")
            c3.metric("Bloqueados (Inadimplentes)", inadimplentes, delta="🔴 Risco" if inadimplentes > 0 else "0")
            c4.metric("MRR Estimado", f"R$ {mrr_estimado:.2f}", delta="📈 Plano Base")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.markdown("##### 🏢 Adoção por Nicho / Segmento")
                if "nicho" in df_assinantes.columns:
                    nicho_counts = df_assinantes["nicho"].value_counts().reset_index()
                    nicho_counts.columns = ["Segmento", "Assinantes"]
                    st.bar_chart(nicho_counts.set_index("Segmento"))
                
            with col_m2:
                st.markdown("##### 🌐 Volume Geral de Uso da Tecnologia")
                st.metric("Total de Registros na Base Global", len(df_todas_demandas))
                if not df_todas_demandas.empty and "status" in df_todas_demandas.columns:
                    status_global = df_todas_demandas["status"].value_counts().reset_index()
                    status_global.columns = ["Status", "Quantidade"]
                    st.bar_chart(status_global.set_index("Status"))
            
            st.markdown("---")
            st.markdown("##### 👥 Carteira de Clientes Cadastrados")
            st.dataframe(df_assinantes[["id", "nome_empresa", "usuario", "nicho", "ativo"]], use_container_width=True)
            
        else:
            st.info("Nenhum assinante registado na base.")
            
    except Exception as e:
        st.error(f"Erro ao carregar dados do painel Master: {e}")

# ==========================================
# ABA: OPERACIONAL
# ==========================================
elif aba_selecionada == "📋 Operacional":
    col_head1, col_head2 = st.columns([3, 1])
    with col_head1:
        st.markdown(f'<p class="main-title">📱 Gestor Operacional</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="sub-title">Atendimentos de {user.get("nome_empresa", "Empresa")}</p>', unsafe_allow_html=True)
    
    if not df.empty:
        total = len(df)
        aberto = len(df[df["status"] == "Em Aberto"]) if "status" in df.columns else 0
        delegado = len(df[df["status"] == "Delegado"]) if "status" in df.columns else 0
        encerrado = len(df[df["status"] == "Encerrado"]) if "status" in df.columns else 0
        
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            if st.button(f"📊 Total\n\n{total}", key="btn_tot"): st.session_state.filtro_ativo = "Todos"; st.rerun()
        with k2:
            if st.button(f"🟡 Aberto\n\n{aberto}", key="btn_ab"): st.session_state.filtro_ativo = "Em Aberto"; st.rerun()
        with k3:
            if st.button(f"🟣 Deleg.\n\n{delegado}", key="btn_del"): st.session_state.filtro_ativo = "Delegado"; st.rerun()
        with k4:
            if st.button(f"🟢 Encerr.\n\n{encerrado}", key="btn_enc"): st.session_state.filtro_ativo = "Encerrado"; st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    with st.expander("➕ **Registar Nova Demanda**", expanded=False):
        with st.form("form_demanda_mobile", clear_on_submit=True):
            nome = st.text_input(f"👤 {lbl_cliente} *")
            telefone = st.text_input("📱 Telemóvel / WhatsApp")
            cartao_sus = st.text_input(f"🆔 {lbl_id}")
            
            col_p1, col_p2 = st.columns(2)
            with col_p1: prioridade = st.selectbox("⚡ Prioridade", ["Normal", "Média", "Alta", "Urgente"])
            with col_p2: data_previsao = st.date_input("📅 Previsão Resolução", value=date.today())
            
            demanda = st.text_area(f"📝 {lbl_demanda} *")
            reportado = st.text_input("🏛️ Origem / Delegado a (Vazio = 'Em Aberto')")
            anexo = st.file_uploader("📎 Anexar Foto / Documento", type=["png", "jpg", "jpeg"])
            
            submitted = st.form_submit_button("💾 Guardar Demanda", use_container_width=True)
            if submitted:
                if nome and demanda:
                    try:
                        if anexo: comprimir_imagem(anexo)
                        salvar_demanda(user["id"], nome, telefone, cartao_sus, demanda, reportado, prioridade, data_previsao)
                        st.success("✅ Registado com sucesso!")
                        st.rerun()
                    except Exception as ex: st.error(f"❌ {ex}")
                else: st.error("⚠️ Preencha os campos obrigatórios.")

    if not df.empty:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            opcoes_filtro = ["Todos", "Em Aberto", "Delegado", "Encerrado"]
            idx_selecionado = opcoes_filtro.index(st.session_state.filtro_ativo) if st.session_state.filtro_ativo in opcoes_filtro else 0
            filtro_status = st.selectbox("Status", opcoes_filtro, index=idx_selecionado, label_visibility="collapsed")
            if filtro_status != st.session_state.filtro_ativo: st.session_state.filtro_ativo = filtro_status
        with col_f2:
            busca = st.text_input("Pesquisar", placeholder="🔍 Pesquisar...", label_visibility="collapsed")
            
        df_filtrado = df.copy()
        if st.session_state.filtro_ativo != "Todos" and "status" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["status"] == st.session_state.filtro_ativo]
        if busca and "nome" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["nome"].str.contains(busca, case=False, na=False) | df_filtrado["cartao_sus"].str.contains(busca, case=False, na=False)]

        st.markdown(f"### 📋 Demandas ({len(df_filtrado)}) — *Filtro: {st.session_state.filtro_ativo}*")

        for index, row in df_filtrado.iterrows():
            status_atual, prioridade_atual, previsao = row.get('status', 'Em Aberto'), row.get('prioridade', 'Normal'), row.get('data_previsao', 'N/A')
            prio_emoji = "🟢" if prioridade_atual == "Normal" else ("🟡" if prioridade_atual == "Média" else ("🟠" if prioridade_atual == "Alta" else "🔴"))
            status_emoji = "🟡" if status_atual == "Em Aberto" else ("🟣" if status_atual == "Delegado" else "🟢")
            
            with st.expander(f"{status_emoji} {prio_emoji} **{row.get('nome', 'Sem Nome')}**"):
                st.markdown(f"**⚡ Prioridade:** {prioridade_atual}")
                st.markdown(f"**📅 Previsão:** {previsao}")
                st.markdown(f"**📱 Telemóvel:** {row.get('telefone', 'Não inf.')}")
                st.markdown(f"**🆔 {lbl_id}:** {row.get('cartao_sus', 'Não inf.')}")
                st.markdown(f"**📝 Demanda:** {row.get('demanda', 'N/A')}")
                st.markdown(f"**🏛️ Origem:** {row.get('reportado', 'N/A')}")
                
                tel = row.get('telefone')
                if tel:
                    tel_limpo = "".join(filter(str.isdigit, str(tel)))
                    st.markdown(f'<a href="https://wa.me/55{tel_limpo}" target="_blank" class="wsp-button">💬 Conversar no WhatsApp</a>', unsafe_allow_html=True)
                
                st.markdown("---")
                novo_estado = st.selectbox("Mudar Estado", ["Em Aberto", "Delegado", "Encerrado"], index=["Em Aberto", "Delegado", "Encerrado"].index(status_atual), key=f"st_{row.get('id', index)}")
                if novo_estado != status_atual:
                    atualizar_status(row['id'], novo_estado)
                    st.success("Atualizado!")
                    st.rerun()
    else:
        st.info("ℹ️ Sem demandas registadas.")

# ==========================================
# ABA: MEUS INDICADORES (BI)
# ==========================================
elif aba_selecionada == "📊 Meus Indicadores (BI)":
    st.markdown('<p class="main-title">📊 Meus Indicadores de Produtividade</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Desempenho operacional do seu negócio</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    if df.empty:
        st.warning("⚠️ Sem dados suficientes. Registe demandas na aba Operacional.")
    else:
        tot, enc = len(df), len(df[df["status"] == "Encerrado"])
        taxa = round((enc / tot) * 100, 1) if tot > 0 else 0.0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Volume Total", tot)
        m2.metric("Concluídas", enc)
        m3.metric("Taxa de Resolução", f"{taxa}%")
        
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 📌 Status")
            st.bar_chart(df["status"].value_counts())
        with c2:
            st.markdown("##### ⚡ Prioridades")
            st.bar_chart(df["prioridade"].value_counts())

# ==========================================
# ABA: CENTRAL DE AJUDA
# ==========================================
elif aba_selecionada == "❓ Central de Ajuda":
    st.markdown('<p class="main-title">❓ Central de Dúvidas & Procedimentos</p>', unsafe_allow_html=True)
    st.markdown("---")
    busca_faq = st.text_input("🔍 Pesquisar dúvida", placeholder="Ex: login, pagamento, WhatsApp...")
    
    faqs = [
        {"cat": "👑 Gestão SaaS", "pergunta": "Como funciona o painel de controlo de assinantes?", "resposta": "O painel 'Gestão do Sistema (Master)' exibe os KPIs globais de clientes, MRR estimado e volume total na plataforma."},
        {"cat": "💼 Assinatura", "pergunta": "Como bloquear um cliente inadimplente?", "resposta": "Basta definir o campo 'ativo' como FALSE para o cliente correspondente na tabela assinantes do Supabase."}
    ]
    
    for item in [f for f in faqs if busca_faq.lower() in f["pergunta"].lower() or busca_faq.lower() in f["cat"].lower()]:
        with st.expander(f"[{item['cat']}] **{item['pergunta']}**"):
            st.write(item["resposta"])
