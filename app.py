import inspect
import json
import os
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from catalogo import CATALOGO, musculo_de

st.set_page_config(page_title="Meu Treino", page_icon="🏋️", layout="centered")

# O Streamlit Cloud roda em UTC; sem o fuso, o horário das séries sairia 3h adiantado
FUSO = ZoneInfo("America/Sao_Paulo")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
PLANO_HEADER = ["dia", "ordem", "exercicio", "series", "meta_reps", "aluno"]
REGISTROS_HEADER = [
    "data", "dia_treino", "exercicio", "serie", "peso_kg", "reps",
    "hora", "registrado_em", "intervalo_seg",
]
ALUNO_PADRAO = "Fabrício Lopes"
NOVO_ALUNO = "＋ Novo aluno"
EXERCICIOS_HEADER = ["exercicio", "regiao", "musculo", "video"]
PREFIXO_ALUNO = "Treino "  # uma aba por aluno: "Treino Fabrício Lopes", "Treino Anah"
ABA_PLANO = "treinos_academia_plano"
ABA_EXERCICIOS = "treinos_academia_exercicios"
OUTRO = "✏️ Outro (digitar o nome)"
COR_SERIE = "#2a78d6"
# Streamlit novo troca use_container_width por width="stretch"; o antigo só conhece o primeiro
LARGURA_TOTAL = ({"width": "stretch"} if "width" in inspect.signature(st.button).parameters
                 else {"use_container_width": True})

PLANO_INICIAL = {
    "Segunda": [["Supino reto", 4, "8–12"], ["Supino inclinado", 3, "8–12"], ["Crossover", 3, "10–15"],
                ["Tríceps pulley", 3, "8–12"], ["Tríceps francês", 3, "10–12"], ["Tríceps testa", 2, "10–12"]],
    "Terça": [["Puxada frontal", 4, "8–12"], ["Remada baixa", 3, "8–12"], ["Remada unilateral", 3, "8–12"],
              ["Rosca direta", 4, "8–12"], ["Rosca inclinada", 3, "10–12"], ["Rosca martelo", 3, "10–12"]],
    "Quarta": [["Leg press", 4, "8–12"], ["Cadeira extensora", 3, "10–15"], ["Mesa flexora", 4, "10–15"],
               ["Cadeira flexora", 3, "10–15"], ["Cadeira abdutora", 3, "12–15"], ["Cadeira adutora", 3, "12–15"],
               ["Panturrilha", 4, "12–20"], ["Abdômen", 3, "12–20"]],
    "Quinta": [["Desenvolvimento", 3, "8–12"], ["Elevação lateral", 4, "10–15"], ["Crucifixo inverso", 3, "10–15"],
               ["Rosca Scott", 3, "8–12"], ["Rosca martelo", 3, "10–12"], ["Tríceps pulley", 3, "8–12"],
               ["Tríceps francês", 3, "10–12"]],
    "Sexta": [["Supino inclinado", 3, "8–12"], ["Crossover", 2, "10–15"], ["Puxada frontal", 3, "8–12"],
              ["Remada máquina", 3, "8–12"], ["Rosca direta", 3, "8–12"], ["Rosca alternada", 2, "10–12"],
              ["Tríceps testa", 3, "8–12"], ["Tríceps corda", 2, "10–15"]],
}

# Na tela do celular o Streamlit empilha as colunas; aqui elas ficam lado a lado
# (série | peso | reps | salvar), e os botões +/- somem para sobrar espaço.
CSS = """
<style>
div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.5rem !important; }
div[data-testid="stHorizontalBlock"] > div { min-width: 0 !important; }
button[data-testid="stNumberInputStepUp"], button[data-testid="stNumberInputStepDown"] { display: none; }
.block-container { padding-top: 2.5rem; padding-bottom: 4rem; }
.serie-num { font-weight: 700; padding-top: 0.55rem; white-space: nowrap; }
</style>
"""


# ---------- Planilha ----------

class AbaMemoria:
    """Imita uma aba do gspread, para testar o app sem mexer na planilha real."""

    def __init__(self, linhas=None):
        self.linhas = [list(l) for l in (linhas or [])]

    def get_all_values(self, **kwargs):
        return [list(l) for l in self.linhas]

    def row_values(self, n):
        return list(self.linhas[n - 1]) if len(self.linhas) >= n else []

    def append_row(self, valores, **kwargs):
        self.linhas.append(list(valores))

    def append_rows(self, linhas, **kwargs):
        self.linhas.extend(list(l) for l in linhas)

    def update(self, valores, range_name, **kwargs):
        # Escreve o bloco `valores` a partir da célula `range_name` (ex.: "A1", "D7")
        coluna = ord(range_name[0]) - ord("A")
        inicio = int(re.sub(r"\D", "", range_name)) - 1
        for i, valores_linha in enumerate(valores):
            while len(self.linhas) <= inicio + i:
                self.linhas.append([])
            atual = self.linhas[inicio + i]
            atual += [""] * (coluna + len(valores_linha) - len(atual))
            atual[coluna:coluna + len(valores_linha)] = list(valores_linha)
        # A API do Google não devolve linhas vazias no fim; aqui também não
        while self.linhas and not any(str(c).strip() for c in self.linhas[-1]):
            self.linhas.pop()

    def delete_rows(self, inicio, fim=None):
        del self.linhas[inicio - 1:(fim or inicio)]


class PlanilhaMemoria:
    def __init__(self, abas):
        self.abas = abas

    def worksheets(self):
        return list(self.abas)

    def worksheet(self, nome):
        import gspread

        for aba in self.abas:
            if aba.title == nome:
                return aba
        raise gspread.WorksheetNotFound(nome)

    def add_worksheet(self, nome, rows=1000, cols=26):
        aba = AbaMemoria()
        aba.title = nome
        self.abas.append(aba)
        return aba


def aba_memoria(nome, linhas=None):
    aba = AbaMemoria(linhas)
    aba.title = nome
    aba.update_title = lambda novo: setattr(aba, "title", novo)
    return aba


def modo_teste():
    return os.environ.get("TREINO_MODO_TESTE") == "1"


def segredo(nome):
    try:
        return st.secrets.get(nome)
    except Exception:
        return None


def preparar_aba(planilha, nome, cabecalho, renomear_de=()):
    """Abre a aba `nome`. Se não existir, renomeia uma aba vazia de `renomear_de` ou cria uma nova.

    Devolve (aba, nova): `nova` indica que a aba estava vazia e acabou de receber o cabeçalho."""
    import gspread

    try:
        aba = planilha.worksheet(nome)
    except gspread.WorksheetNotFound:
        vazias = [a for a in planilha.worksheets()
                  if a.title in renomear_de and not any(any(str(c).strip() for c in l) for l in a.get_all_values())]
        if vazias:
            aba = vazias[0]
            aba.update_title(nome)
        else:
            aba = planilha.add_worksheet(nome, rows=1000, cols=len(cabecalho))

    primeira = [str(v).strip() for v in aba.row_values(1)]
    if not any(primeira):
        aba.update([cabecalho], "A1")
        return aba, True
    if primeira[: len(cabecalho)] != cabecalho:
        # Nunca escreve por cima de uma aba que já tem outro conteúdo
        raise RuntimeError(f"a aba '{aba.title}' já tem outros dados na linha 1; "
                           f"esperava as colunas: {', '.join(cabecalho)}")
    return aba, False


def linhas_plano_inicial():
    return [[dia, ordem, nome, series, meta, ALUNO_PADRAO]
            for dia, exercicios in PLANO_INICIAL.items()
            for ordem, (nome, series, meta) in enumerate(exercicios, start=1)]


@st.cache_resource(show_spinner=False)
def conectar_planilha():
    """Devolve {"planilha", "plano", "exercicios", "alunos": {nome: aba do histórico}}."""
    if modo_teste():
        planilha = PlanilhaMemoria([
            aba_memoria("itens", [["nome", "valor_unitario", "quantidade_cadastrada"]]),
            aba_memoria(ABA_PLANO, [PLANO_HEADER] + linhas_plano_inicial()),
            aba_memoria(ABA_EXERCICIOS, [EXERCICIOS_HEADER]),
            aba_memoria(PREFIXO_ALUNO + ALUNO_PADRAO, dados_de_teste()),
        ])
        return {"planilha": planilha, "plano": planilha.worksheet(ABA_PLANO),
                "exercicios": planilha.worksheet(ABA_EXERCICIOS), "alunos": {}}

    import gspread
    from google.oauth2.service_account import Credentials

    # Mensagem clara quando os Secrets do Streamlit Cloud não foram colados inteiros (só os nomes, nunca os valores)
    try:
        encontrados = list(st.secrets.keys())
    except Exception:
        encontrados = []
    faltando = [k for k in ("planilha_id", "gcp_service_account") if k not in encontrados]
    if faltando:
        raise RuntimeError(
            f"faltam nos Secrets do app: {', '.join(faltando)}. "
            f"Encontrei: {', '.join(encontrados) if encontrados else 'nenhum secret'}. "
            "Cole o secrets.toml inteiro em Settings > Secrets e salve.")

    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    planilha = gspread.authorize(creds).open_by_key(st.secrets["planilha_id"])
    # A planilha é a do bazar: só mexemos nas abas de treino; itens e vendas não são tocadas
    aba_plano, plano_novo = preparar_aba(planilha, ABA_PLANO, PLANO_HEADER)
    if plano_novo:
        # Só na criação da aba; se depois você tirar todos os exercícios, o plano fica vazio mesmo
        aba_plano.append_rows(linhas_plano_inicial(), value_input_option="RAW")
    aba_exercicios, _ = preparar_aba(planilha, ABA_EXERCICIOS, EXERCICIOS_HEADER)
    return {"planilha": planilha, "plano": aba_plano, "exercicios": aba_exercicios, "alunos": {}}


def nome_da_aba(aluno):
    # O Google não aceita estes caracteres no nome da aba
    return PREFIXO_ALUNO + re.sub(r"[\[\]:*?/\\']", "", aluno).strip()[:80]


def aba_registros(aluno=None):
    """A aba de histórico do aluno. A do aluno padrão aproveita a "Página1" vazia do bazar."""
    abas = conectar_planilha()
    aluno = aluno or aluno_atual()
    if aluno not in abas["alunos"]:
        renomear = ("Página1", "Página 1") if aluno == ALUNO_PADRAO else ()
        abas["alunos"][aluno], _ = preparar_aba(abas["planilha"], nome_da_aba(aluno), REGISTROS_HEADER,
                                                renomear_de=renomear)
    return abas["alunos"][aluno]


def listar_alunos():
    titulos = [a.title for a in conectar_planilha()["planilha"].worksheets()]
    alunos = [t[len(PREFIXO_ALUNO):] for t in titulos if t.startswith(PREFIXO_ALUNO)]
    return [ALUNO_PADRAO] + sorted((a for a in alunos if a != ALUNO_PADRAO), key=str.lower)


def dados_de_teste():
    # Um treino de segunda da semana passada, para a prévia mostrar o "Anterior"
    hoje = datetime.now(FUSO).date()
    segunda = hoje - timedelta(days=hoje.weekday() + 7)
    inicio = datetime.combine(segunda, datetime.min.time()).replace(hour=18)
    linhas = [REGISTROS_HEADER]
    for i, (serie, peso, reps) in enumerate([(1, 40, 12), (2, 40, 10), (3, 42.5, 8), (4, 42.5, 7)]):
        momento = inicio + timedelta(minutes=2 * i)
        linhas.append([segunda.isoformat(), "Segunda", "Supino reto", serie, peso, reps,
                       momento.strftime("%H:%M:%S"), momento.strftime("%Y-%m-%d %H:%M:%S"), 120 if i else ""])
    return linhas


def ler_aba(aba, cabecalho):
    # Lido sem formatação para 22,5 não virar 225 na planilha em português
    valores = aba.get_all_values(value_render_option="UNFORMATTED_VALUE")
    linhas = [(list(l) + [""] * len(cabecalho))[: len(cabecalho)] for l in valores[1:]]
    df = pd.DataFrame(linhas, columns=cabecalho)
    df["_linha"] = range(2, len(df) + 2)
    return df


def normalizar_data(valor):
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        # Data digitada direto na planilha chega como número de série do Sheets
        return (date(1899, 12, 30) + timedelta(days=int(valor))).isoformat()
    texto = str(valor).strip()
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", texto):
        d, m, a = texto.split("/")
        return f"{a}-{m}-{d}"
    return texto[:10]


def para_numero(serie):
    return pd.to_numeric(serie.astype(str).str.replace(",", ".", regex=False), errors="coerce")


def nome_aluno(coluna):
    return coluna.astype(str).str.strip().replace("", ALUNO_PADRAO)


def aluno_atual():
    return st.session_state.get("aluno") or ALUNO_PADRAO


def do_aluno(df):
    return df[df["aluno"] == aluno_atual()]


def carregar_plano(aba_plano):
    df = ler_aba(aba_plano, PLANO_HEADER)
    df = df[df["exercicio"].astype(str).str.strip() != ""].copy()
    df["dia"] = df["dia"].astype(str).str.strip()
    df["exercicio"] = df["exercicio"].astype(str).str.strip()
    df["ordem"] = para_numero(df["ordem"]).fillna(999)
    df["series"] = para_numero(df["series"]).fillna(0).astype(int)
    df["meta_reps"] = df["meta_reps"].astype(str)
    df["aluno"] = nome_aluno(df["aluno"])
    df["_dia_ordem"] = df["dia"].map({d: i for i, d in enumerate(DIAS_SEMANA)}).fillna(99)
    return df[df["series"] > 0].sort_values(["_dia_ordem", "ordem"]).reset_index(drop=True)


def carregar_registros(aba):
    df = ler_aba(aba, REGISTROS_HEADER)
    df = df[df["exercicio"].astype(str).str.strip() != ""].copy()
    df["data"] = df["data"].map(normalizar_data)
    df["dia_treino"] = df["dia_treino"].astype(str).str.strip()
    df["exercicio"] = df["exercicio"].astype(str).str.strip()
    df["serie"] = para_numero(df["serie"]).fillna(0).astype(int)
    df["peso_kg"] = para_numero(df["peso_kg"])
    df["reps"] = para_numero(df["reps"])
    df["intervalo_seg"] = para_numero(df["intervalo_seg"])
    df["registrado_em"] = pd.to_datetime(df["registrado_em"].astype(str), errors="coerce")
    df["aluno"] = aluno_atual()
    return df.reset_index(drop=True)


def carregar_exercicios(aba_exercicios):
    df = ler_aba(aba_exercicios, EXERCICIOS_HEADER)
    for coluna in EXERCICIOS_HEADER:
        df[coluna] = df[coluna].astype(str).str.strip()
    return df[df["exercicio"] != ""].reset_index(drop=True)


def recarregar():
    abas = conectar_planilha()
    st.session_state["plano"] = carregar_plano(abas["plano"])
    st.session_state["registros"] = carregar_registros(aba_registros())
    st.session_state["exercicios"] = carregar_exercicios(abas["exercicios"])
    st.session_state["alunos"] = listar_alunos()
    # Os campos da tela de montar treino voltam a mostrar o que está na planilha
    for chave in [c for c in st.session_state.keys() if str(c).startswith("pl_")]:
        del st.session_state[chave]


def gravar_plano(por_dia):
    """Regrava a aba do plano inteira a partir de {dia: [{exercicio, series, meta_reps}, ...]}."""
    aba_plano = conectar_planilha()["plano"]
    antigas = len(aba_plano.get_all_values())
    ordem_dias = DIAS_SEMANA + [d for d in por_dia if d not in DIAS_SEMANA]
    aluno = aluno_atual()
    plano = st.session_state["plano"]
    outros = [[r["dia"], int(r["ordem"]), r["exercicio"], int(r["series"]), r["meta_reps"], r["aluno"]]
              for _, r in plano[plano["aluno"] != aluno].iterrows()]
    linhas = outros + [[dia, ordem, item["exercicio"], int(item["series"]), str(item["meta_reps"]), aluno]
                       for dia in ordem_dias if dia in por_dia
                       for ordem, item in enumerate(por_dia[dia], start=1)]
    # Escreve por cima e limpa as linhas que sobraram, sem apagar a aba antes:
    # se a gravação falhar no meio, o plano antigo não se perde
    sobras = [[""] * len(PLANO_HEADER)] * max(0, antigas - 1 - len(linhas))
    aba_plano.update([PLANO_HEADER] + linhas + sobras, "A1", value_input_option="RAW")
    st.session_state["plano"] = carregar_plano(aba_plano)


def salvar_exercicio(nome, regiao=None, musculo=None, video=None):
    """Guarda um exercício criado por você e/ou o link de vídeo dele."""
    aba = conectar_planilha()["exercicios"]
    df = carregar_exercicios(aba)
    mesmo = df[df["exercicio"].str.lower() == nome.strip().lower()]
    if mesmo.empty:
        aba.append_row([nome.strip(), regiao or "", musculo or "", video or ""], value_input_option="RAW")
    else:
        atual = mesmo.iloc[0]
        aba.update([[atual["exercicio"], regiao or atual["regiao"], musculo or atual["musculo"],
                     video if video is not None else atual["video"]]],
                   f"A{int(atual['_linha'])}", value_input_option="RAW")
    st.session_state["exercicios"] = carregar_exercicios(aba)


def salvar_serie(data_iso, dia, exercicio, serie, peso, reps):
    """Grava a série na planilha. Se ela já existe, corrige peso e reps e mantém o horário."""
    aba = aba_registros()
    # Lê de novo antes de gravar: a planilha pode ter sido editada ou ordenada em outro lugar
    df = do_aluno(carregar_registros(aba))
    mesma = df[(df["data"] == data_iso) & (df["dia_treino"] == dia)
               & (df["exercicio"] == exercicio) & (df["serie"] == serie)]

    if not mesma.empty:
        atual = mesma.iloc[0]
        linha = int(atual["_linha"])
        registrado = atual["registrado_em"]
        valores = [data_iso, dia, exercicio, serie, peso, reps,
                   str(atual["hora"]),
                   registrado.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(registrado) else "",
                   int(atual["intervalo_seg"]) if pd.notna(atual["intervalo_seg"]) else ""]
        aba.update([valores], f"A{linha}", value_input_option="RAW")
    else:
        agora = datetime.now(FUSO).replace(tzinfo=None, microsecond=0)
        sessao = df[(df["data"] == data_iso) & (df["dia_treino"] == dia) & df["registrado_em"].notna()]
        intervalo = ""
        if not sessao.empty:
            segundos = (agora - sessao["registrado_em"].max()).total_seconds()
            # Mais de 1h entre séries não é descanso (treino lançado depois, por exemplo)
            if 0 < segundos <= 3600:
                intervalo = int(segundos)
        valores = [data_iso, dia, exercicio, serie, peso, reps,
                   agora.strftime("%H:%M:%S"), agora.strftime("%Y-%m-%d %H:%M:%S"), intervalo]
        aba.append_row(valores, value_input_option="RAW")

    st.session_state["registros"] = carregar_registros(aba)


def excluir_serie(data_iso, dia, exercicio, serie):
    """Apaga a série da planilha e renumera as seguintes (a 3ª vira 2ª, e assim por diante)."""
    aba = aba_registros()
    df = do_aluno(carregar_registros(aba))
    do_ex = df[(df["data"] == data_iso) & (df["dia_treino"] == dia) & (df["exercicio"] == exercicio)]
    apagar = do_ex[do_ex["serie"] == serie]
    for _, linha in do_ex[do_ex["serie"] > serie].iterrows():
        aba.update([[int(linha["serie"]) - 1]], f"D{int(linha['_linha'])}", value_input_option="RAW")
    # De baixo para cima, para o número das linhas não mudar no meio
    for linha in sorted(apagar["_linha"], reverse=True):
        aba.delete_rows(int(linha))
    st.session_state["registros"] = carregar_registros(aba)


# ---------- Formatação ----------

def data_br(data_iso):
    a, m, d = data_iso.split("-")
    return f"{d}/{m}/{a}"


def fmt_intervalo(segundos):
    if segundos is None or pd.isna(segundos):
        return ""
    segundos = int(segundos)
    minutos, seg = divmod(segundos, 60)
    return f"{minutos}m {seg:02d}s" if minutos else f"{seg}s"


def fmt_num(valor):
    if valor is None or pd.isna(valor):
        return "—"
    return f"{valor:g}".replace(".", ",")


# ---------- Acesso ----------

def liberar_acesso():
    senha = segredo("senha_app")
    if not senha or st.session_state.get("liberado"):
        return
    # O link salvo no celular pode levar ?chave=..., para não pedir a senha toda vez
    if st.query_params.get("chave") == senha:
        st.session_state["liberado"] = True
        return
    st.subheader("🏋️ Meu Treino")
    digitada = st.text_input("Senha", type="password")
    if digitada:
        if digitada == senha:
            st.session_state["liberado"] = True
            st.rerun()
        st.error("Senha incorreta.")
    st.stop()


# ---------- Alunos ----------

# O que sobrevive à troca de aluno; o resto (campos da tela) é do aluno anterior e sai
ESTADO_FIXO = {"plano", "exercicios", "alunos", "aluno", "aluno_sel", "liberado", "salvo", "aviso"}


def trocar_aluno(nome):
    for chave in [c for c in st.session_state.keys() if c not in ESTADO_FIXO]:
        del st.session_state[chave]
    st.session_state["aluno"] = nome
    st.session_state["registros"] = carregar_registros(aba_registros(nome))


def ao_escolher_aluno():
    escolhido = st.session_state["aluno_sel"]
    if escolhido != NOVO_ALUNO and escolhido != aluno_atual():
        try:
            trocar_aluno(escolhido)
        except Exception as erro:
            st.session_state["aviso"] = f"Não consegui abrir os treinos de {escolhido}: {erro}"
            st.session_state["aluno_sel"] = aluno_atual()


def ao_criar_aluno():
    nome = re.sub(r"\s+", " ", st.session_state.get("novo_aluno_nome", "")).strip()
    nome = re.sub(r"[\[\]:*?/\\']", "", nome)
    if not nome:
        st.session_state["aviso"] = "Digite o nome do aluno."
        return
    existente = next((a for a in st.session_state["alunos"] if a.lower() == nome.lower()), None)
    try:
        trocar_aluno(existente or nome)  # cria a aba "Treino <nome>" se ainda não existir
    except Exception as erro:
        st.session_state["aviso"] = f"Não consegui criar a aba do aluno: {erro}"
        return
    if not existente:
        st.session_state["alunos"] = listar_alunos()
    st.session_state["aluno_sel"] = aluno_atual()
    st.session_state["salvo"] = f"Olá, {aluno_atual()}! Monte seu treino na aba Montar treino."


# ---------- Tela ----------

def ao_trocar_data():
    nome = DIAS_SEMANA[st.session_state["data_treino"].weekday()]
    if nome in st.session_state["dias_plano"]:
        st.session_state["dia"] = nome


def chave_serie(data_iso, dia, exercicio, serie):
    return f"{data_iso}|{dia}|{exercicio}|{serie}"


def ao_salvar(data_iso, dia, exercicio, serie):
    chave = chave_serie(data_iso, dia, exercicio, serie)
    peso = st.session_state.get(f"p|{chave}")
    reps = st.session_state.get(f"r|{chave}")
    if peso is None or reps is None:
        st.session_state["aviso"] = f"{exercicio} · série {serie}: informe peso e repetições."
        return
    # Maior carga já feita no exercício, sem contar esta própria série (caso seja uma correção)
    registros = do_aluno(st.session_state["registros"])
    outras = registros[(registros["exercicio"] == exercicio)
                       & ~((registros["data"] == data_iso) & (registros["dia_treino"] == dia)
                           & (registros["serie"] == serie))]
    recorde_antes = outras["peso_kg"].max() if not outras.empty else None
    try:
        salvar_serie(data_iso, dia, exercicio, serie, float(peso), int(reps))
        st.session_state["salvo"] = f"{exercicio} · série {serie} salva"
        if recorde_antes is not None and pd.notna(recorde_antes) and float(peso) > recorde_antes:
            st.session_state["recorde"] = f"Recorde em {exercicio}: {fmt_num(float(peso))} kg (antes {fmt_num(recorde_antes)} kg)"
    except Exception as erro:
        st.session_state["aviso"] = f"Não consegui salvar na planilha: {erro}"


def ao_adicionar_serie(chave_qtd):
    st.session_state[chave_qtd] += 1


def ao_pedir_exclusao(data_iso, dia, exercicio, serie, salva, qtd):
    if salva:
        # Série já gravada: pede confirmação antes de apagar da planilha
        st.session_state["confirmar_exclusao"] = chave_serie(data_iso, dia, exercicio, serie)
    else:
        tirar_da_tela(data_iso, dia, exercicio, serie, qtd)


def ao_confirmar_exclusao(data_iso, dia, exercicio, serie, qtd):
    st.session_state.pop("confirmar_exclusao", None)
    try:
        excluir_serie(data_iso, dia, exercicio, serie)
    except Exception as erro:
        st.session_state["aviso"] = f"Não consegui apagar da planilha: {erro}"
        return
    tirar_da_tela(data_iso, dia, exercicio, serie, qtd)
    st.session_state["salvo"] = f"{exercicio} · série {serie} apagada"


def ao_cancelar_exclusao():
    st.session_state.pop("confirmar_exclusao", None)


def tirar_da_tela(data_iso, dia, exercicio, serie, qtd):
    # Os campos das séries seguintes sobem uma posição, com o que já estava digitado
    for s in range(serie, qtd + 1):
        for prefixo in ("p", "r"):
            atual = f"{prefixo}|{chave_serie(data_iso, dia, exercicio, s)}"
            seguinte = f"{prefixo}|{chave_serie(data_iso, dia, exercicio, s + 1)}"
            if s < qtd and seguinte in st.session_state:
                st.session_state[atual] = st.session_state[seguinte]
            else:
                st.session_state.pop(atual, None)
    st.session_state[f"n|{data_iso}|{dia}|{exercicio}"] = qtd - 1


def ultimo_treino(registros, exercicio, data_iso):
    anteriores = registros[(registros["exercicio"] == exercicio) & (registros["data"] < data_iso)]
    if anteriores.empty:
        return None, anteriores
    ultima_data = anteriores["data"].max()
    return ultima_data, anteriores[anteriores["data"] == ultima_data]


def valor_de(linhas, coluna, tipo):
    if linhas.empty or pd.isna(linhas[coluna].iloc[0]):
        return None
    return tipo(linhas[coluna].iloc[0])


def topo_da_meta(meta_reps):
    """'8–12' -> 12; '10' -> 10; texto sem número -> None."""
    numeros = [int(n) for n in re.findall(r"\d+", str(meta_reps))]
    return max(numeros) if numeros else None


# Conta, ao vivo no celular, o tempo desde a última série gravada hoje.
# O Streamlit só redesenha a tela quando você toca em algo, por isso o relógio roda em JavaScript.
CRONOMETRO_HTML = """
<div id="c" style="font-family:'Source Sans Pro',sans-serif;font-size:15px;padding:6px 2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"></div>
<script>
const inicio = INICIO, rotulo = ROTULO;
const el = document.getElementById("c");
try { el.style.color = getComputedStyle(window.parent.document.body).color; } catch (e) {}
function tick() {
  const s = Math.floor((Date.now() - inicio) / 1000);
  if (s < 0 || s > 3600) { el.textContent = ""; return; }
  const m = Math.floor(s / 60), r = String(s % 60).padStart(2, "0");
  el.innerHTML = "⏱️ <b>" + m + ":" + r + "</b> de descanso · " + rotulo;
}
tick(); setInterval(tick, 1000);
</script>
"""


def cronometro_descanso(do_dia):
    gravadas = do_dia.dropna(subset=["registrado_em"])
    if gravadas.empty:
        return
    ultima = gravadas.loc[gravadas["registrado_em"].idxmax()]
    inicio_ms = int(ultima["registrado_em"].tz_localize(FUSO).timestamp() * 1000)
    rotulo = f"{ultima['exercicio']} {int(ultima['serie'])}ª"
    html = CRONOMETRO_HTML.replace("INICIO", str(inicio_ms)).replace("ROTULO", json.dumps(rotulo))
    # st.iframe substitui components.html nas versões novas do Streamlit
    if hasattr(st, "iframe"):
        st.iframe(html, height=36)
    else:
        import streamlit.components.v1 as components
        components.html(html, height=36)


# ---------- Catálogo e vídeos ----------

def catalogo_completo():
    """O catálogo fixo mais os exercícios que você criou (guardados na planilha)."""
    catalogo = {regiao: {m: list(ex) for m, ex in musculos.items()} for regiao, musculos in CATALOGO.items()}
    for _, linha in st.session_state["exercicios"].iterrows():
        if linha["regiao"] and linha["musculo"] and not musculo_de(linha["exercicio"], catalogo):
            catalogo.setdefault(linha["regiao"], {}).setdefault(linha["musculo"], []).append(linha["exercicio"])
    return catalogo


def id_youtube(texto):
    """Aceita link de vídeo normal, youtu.be ou Shorts e devolve (link para tocar, segundo inicial)."""
    achou = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})", str(texto))
    if not achou:
        return None
    inicio = re.search(r"[?&](?:t|start)=(\d+)", str(texto))
    return f"https://www.youtube.com/watch?v={achou.group(1)}", int(inicio.group(1)) if inicio else 0


def video_de(nome):
    df = st.session_state["exercicios"]
    linha = df[(df["exercicio"].str.lower() == nome.lower()) & (df["video"] != "")]
    return id_youtube(linha["video"].iloc[0]) if not linha.empty else None


def busca_youtube(nome):
    from urllib.parse import quote_plus
    return "https://www.youtube.com/results?search_query=" + quote_plus(f"como fazer {nome} execução correta shorts")


def ao_salvar_video(nome, chave):
    texto = st.session_state.get(chave, "").strip()
    if not texto:
        return
    if not id_youtube(texto):
        st.session_state["aviso"] = "Esse link não parece ser do YouTube. Copie o link pelo botão Compartilhar do vídeo."
        return
    try:
        salvar_exercicio(nome, *(musculo_de(nome, catalogo_completo()) or (None, None)), video=texto)
        st.session_state["salvo"] = f"Vídeo salvo em {nome}"
        st.session_state[chave] = ""
    except Exception as erro:
        st.session_state["aviso"] = f"Não consegui salvar o vídeo: {erro}"


def como_fazer(nome, chave):
    # O vídeo só carrega quando você liga a chave, para não pesar a tela no celular
    if not st.toggle("▶️ Como fazer", key=f"tg|{chave}"):
        return
    video = video_de(nome)
    if video:
        st.video(video[0], start_time=video[1])
    else:
        st.caption("Ainda não tem vídeo para este exercício. Procure um curto no YouTube e cole o link aqui embaixo.")
    st.link_button("🔎 Procurar no YouTube", busca_youtube(nome), **LARGURA_TOTAL)
    st.text_input("Trocar o vídeo (cole outro link)" if video else "Link do vídeo",
                  key=f"vl|{chave}", placeholder="https://youtube.com/shorts/...",
                  on_change=ao_salvar_video, args=(nome, f"vl|{chave}"))


def seletor_exercicio(prefixo, ja_tem):
    """Região -> músculo -> exercício. Os valores são lidos depois por ler_seletor()."""
    catalogo = catalogo_completo()
    regiao = st.radio("Região", list(catalogo), key=f"{prefixo}_reg", horizontal=True)
    musculo = st.radio("Músculo", list(catalogo[regiao]), key=f"{prefixo}_mus|{regiao}", horizontal=True)
    opcoes = catalogo[regiao][musculo] + [OUTRO]
    # Os nomes da lista não mudam: se mudassem, o Streamlit voltaria a seleção para o primeiro item
    escolha = st.selectbox("Exercício", opcoes, key=f"{prefixo}_ex|{regiao}|{musculo}")
    if escolha in ja_tem:
        st.caption("✓ Este exercício já está no treino.")
    if escolha == OUTRO:
        st.text_input("Nome do exercício", key=f"{prefixo}_novo")
    else:
        como_fazer(escolha, f"{prefixo}|{escolha}")
    col = st.columns(2)
    if f"{prefixo}_series" not in st.session_state:
        st.session_state[f"{prefixo}_series"] = 3
        st.session_state[f"{prefixo}_meta"] = "10–12"
    col[0].number_input("Séries", min_value=1, max_value=10, step=1, key=f"{prefixo}_series")
    col[1].text_input("Meta de reps", key=f"{prefixo}_meta")


def ler_seletor(prefixo):
    ss = st.session_state
    regiao = ss.get(f"{prefixo}_reg")
    musculo = ss.get(f"{prefixo}_mus|{regiao}")
    escolha = ss.get(f"{prefixo}_ex|{regiao}|{musculo}")
    novo = escolha == OUTRO
    nome = (ss.get(f"{prefixo}_novo") or "").strip() if novo else escolha
    return {"exercicio": nome, "regiao": regiao, "musculo": musculo, "novo": novo,
            "series": int(ss.get(f"{prefixo}_series") or 3), "meta_reps": (ss.get(f"{prefixo}_meta") or "").strip()}


# ---------- Plano ----------

def plano_por_dia():
    plano = do_aluno(st.session_state["plano"])
    por_dia = {dia: [] for dia in DIAS_SEMANA}
    for _, linha in plano.iterrows():
        por_dia.setdefault(linha["dia"], []).append(
            {"exercicio": linha["exercicio"], "series": int(linha["series"]), "meta_reps": linha["meta_reps"]})
    return por_dia


def mudar_plano(funcao, mensagem):
    por_dia = plano_por_dia()
    funcao(por_dia)
    try:
        gravar_plano(por_dia)
        st.session_state["salvo"] = mensagem
    except Exception as erro:
        st.session_state["aviso"] = f"Não consegui gravar o plano: {erro}"


def ao_adicionar_exercicio(prefixo, dia, so_hoje_chave=None):
    item = ler_seletor(prefixo)
    if not item["exercicio"]:
        st.session_state["aviso"] = "Digite o nome do exercício."
        return
    if item["novo"] and not musculo_de(item["exercicio"], catalogo_completo()):
        try:
            salvar_exercicio(item["exercicio"], item["regiao"], item["musculo"])
        except Exception as erro:
            st.session_state["aviso"] = f"Não consegui salvar o exercício novo: {erro}"
            return
    novo = {k: item[k] for k in ("exercicio", "series", "meta_reps")}

    if so_hoje_chave and not st.session_state.get(f"{prefixo}_manter", True):
        extras = st.session_state.setdefault(so_hoje_chave, [])
        if all(e["exercicio"] != novo["exercicio"] for e in extras):
            extras.append(novo)
        st.session_state["salvo"] = f"{novo['exercicio']} incluído só neste treino"
        return

    if any(e["exercicio"].lower() == novo["exercicio"].lower() for e in plano_por_dia().get(dia, [])):
        st.session_state["aviso"] = f"{novo['exercicio']} já está no treino de {dia}."
        return
    mudar_plano(lambda por_dia: por_dia[dia].append(novo), f"{novo['exercicio']} incluído no treino de {dia}")


def ao_mover_exercicio(dia, nome, passo):
    def mover(por_dia):
        lista = por_dia[dia]
        i = next(i for i, e in enumerate(lista) if e["exercicio"] == nome)
        j = i + passo
        if 0 <= j < len(lista):
            lista[i], lista[j] = lista[j], lista[i]
    mudar_plano(mover, f"{nome} {'subiu' if passo < 0 else 'desceu'}")


def ao_remover_exercicio(dia, nome):
    def remover(por_dia):
        por_dia[dia] = [e for e in por_dia[dia] if e["exercicio"] != nome]
    for prefixo in ("pl_s", "pl_m"):
        st.session_state.pop(f"{prefixo}|{dia}|{nome}", None)
    mudar_plano(remover, f"{nome} saiu do treino de {dia} (o histórico dele continua salvo)")


def ao_editar_exercicio(dia, nome):
    series = st.session_state.get(f"pl_s|{dia}|{nome}")
    meta = st.session_state.get(f"pl_m|{dia}|{nome}", "")

    def editar(por_dia):
        for e in por_dia[dia]:
            if e["exercicio"] == nome:
                e["series"], e["meta_reps"] = int(series or 1), meta.strip()
    mudar_plano(editar, f"{nome} atualizado")


def ao_copiar_plano():
    origem = st.session_state.get("copiar_de")
    todos = st.session_state["plano"]
    copia = todos[todos["aluno"] == origem]

    def copiar(por_dia):
        for _, r in copia.iterrows():
            por_dia.setdefault(r["dia"], []).append(
                {"exercicio": r["exercicio"], "series": int(r["series"]), "meta_reps": r["meta_reps"]})
    mudar_plano(copiar, f"Treino de {origem} copiado para {aluno_atual()}")


def tela_montar(plano):
    st.caption("Monte o treino de cada dia: escolha o músculo, o exercício, as séries e a meta. "
               "Tirar um exercício daqui não apaga o histórico dele.")
    if plano.empty:
        todos = st.session_state["plano"]
        outros = [a for a in dict.fromkeys(todos["aluno"]) if a != aluno_atual()]
        if outros:
            with st.container(border=True):
                st.markdown("**Começar copiando um treino pronto?**")
                st.caption("Depois você muda o que quiser. O treino da outra pessoa não é alterado.")
                st.selectbox("Copiar o treino de", outros, key="copiar_de")
                st.button("Copiar treino", on_click=ao_copiar_plano, **LARGURA_TOTAL)
    dia = st.radio("Dia", DIAS_SEMANA, key="montar_dia", horizontal=True, label_visibility="collapsed")
    do_dia = plano[plano["dia"] == dia].reset_index(drop=True)
    st.markdown(f"**{dia}** — {len(do_dia)} exercícios · {int(do_dia['series'].sum())} séries")
    if do_dia.empty:
        st.info(f"Nenhum exercício na {dia.lower()} ainda. Adicione abaixo.")

    for i, ex in do_dia.iterrows():
        nome = ex["exercicio"]
        grupo = musculo_de(nome, catalogo_completo())
        with st.container(border=True):
            st.markdown(f"**{i + 1}. {nome}**" + (f"  \n{grupo[1]}" if grupo else ""))
            chave_s, chave_m = f"pl_s|{dia}|{nome}", f"pl_m|{dia}|{nome}"
            if chave_s not in st.session_state:
                st.session_state[chave_s] = int(ex["series"])
                st.session_state[chave_m] = ex["meta_reps"]
            larguras = [1.3, 1.7, 0.8, 0.8, 0.8]
            cab = st.columns(larguras)
            cab[0].caption("Séries")
            cab[1].caption("Meta reps")
            col = st.columns(larguras)
            col[0].number_input("Séries", min_value=1, max_value=10, step=1, key=chave_s, label_visibility="collapsed",
                                on_change=ao_editar_exercicio, args=(dia, nome))
            col[1].text_input("Meta reps", key=chave_m, label_visibility="collapsed",
                              on_change=ao_editar_exercicio, args=(dia, nome))
            col[2].button("⬆️", key=f"pl_up|{dia}|{nome}", disabled=i == 0, help="Subir", **LARGURA_TOTAL,
                          on_click=ao_mover_exercicio, args=(dia, nome, -1))
            col[3].button("⬇️", key=f"pl_dn|{dia}|{nome}", disabled=i == len(do_dia) - 1, help="Descer",
                          **LARGURA_TOTAL, on_click=ao_mover_exercicio, args=(dia, nome, 1))
            col[4].button("🗑️", key=f"pl_rm|{dia}|{nome}", help="Tirar do treino", **LARGURA_TOTAL,
                          on_click=ao_remover_exercicio, args=(dia, nome))
            como_fazer(nome, f"pl_v|{dia}|{nome}")

    with st.container(border=True):
        st.markdown(f"**＋ Adicionar exercício na {dia.lower()}**")
        prefixo = f"pl_add|{dia}"
        seletor_exercicio(prefixo, set(do_dia["exercicio"]))
        st.button("Adicionar", key=f"{prefixo}_ok", type="primary", **LARGURA_TOTAL,
                  on_click=ao_adicionar_exercicio, args=(prefixo, dia))


COLUNAS_SERIE = [0.6, 2, 2, 1.1, 0.8]


def exercicios_do_treino(plano, do_dia, dia, chave_extras):
    """Os exercícios do plano do dia, mais os incluídos só neste treino."""
    itens = [{"exercicio": r["exercicio"], "series": int(r["series"]), "meta_reps": r["meta_reps"], "extra": False}
             for _, r in plano[plano["dia"] == dia].iterrows()]
    nomes = {i["exercicio"] for i in itens}
    # Um exercício "só hoje" continua aparecendo depois de recarregar, porque já tem série gravada
    gravados = [{"exercicio": n, "series": int(g["serie"].max()), "meta_reps": ""}
                for n, g in do_dia.groupby("exercicio", sort=False)]
    for item in st.session_state.get(chave_extras, []) + gravados:
        if item["exercicio"] not in nomes:
            itens.append({**item, "extra": True})
            nomes.add(item["exercicio"])
    return itens


def tela_treino(plano, registros):
    dias = list(dict.fromkeys(plano["dia"]))
    st.session_state["dias_plano"] = dias
    if not dias:
        st.info("Seu plano está vazio. Monte o treino na aba **Montar treino**.")
        return
    hoje = datetime.now(FUSO).date()
    if "data_treino" not in st.session_state:
        st.session_state["data_treino"] = hoje
    if st.session_state.get("dia") not in dias:
        nome_hoje = DIAS_SEMANA[hoje.weekday()]
        st.session_state["dia"] = nome_hoje if nome_hoje in dias else dias[0]

    st.date_input("Data do treino", key="data_treino", format="DD/MM/YYYY", on_change=ao_trocar_data)
    st.radio("Treino", dias, key="dia", horizontal=True, label_visibility="collapsed")

    data_iso = st.session_state["data_treino"].isoformat()
    dia = st.session_state["dia"]
    do_dia = registros[(registros["data"] == data_iso) & (registros["dia_treino"] == dia)]
    chave_extras = f"extras|{data_iso}|{dia}"
    exercicios = exercicios_do_treino(plano, do_dia, dia, chave_extras)
    progresso = st.empty()
    if data_iso == hoje.isoformat():
        cronometro_descanso(do_dia)
    total = 0

    for ex in exercicios:
        nome = ex["exercicio"]
        ultima_data, anteriores = ultimo_treino(registros, nome, data_iso)
        salvas_hoje = do_dia[do_dia["exercicio"] == nome]

        # Quantas séries mostrar: as que você fez da última vez (ou as do plano), e nunca
        # menos do que as já gravadas hoje
        chave_qtd = f"n|{data_iso}|{dia}|{nome}"
        if chave_qtd not in st.session_state:
            st.session_state[chave_qtd] = int(anteriores["serie"].max()) if not anteriores.empty else int(ex["series"])
        maior_hoje = int(salvas_hoje["serie"].max()) if not salvas_hoje.empty else 0
        st.session_state[chave_qtd] = max(st.session_state[chave_qtd], maior_hoje)
        qtd = st.session_state[chave_qtd]
        total += qtd

        with st.container(border=True):
            if ex["extra"]:
                detalhe = "incluído só neste treino" + (f" · meta {ex['meta_reps']} reps" if ex["meta_reps"] else "")
            else:
                detalhe = f"plano: {ex['series']} séries · meta {ex['meta_reps']} reps"
            st.markdown(f"**{nome}**  \n{detalhe}")
            como_fazer(nome, f"tr|{dia}|{nome}")
            if ultima_data:
                n_antes = anteriores["serie"].nunique()
                st.caption(f"Último treino: {data_br(ultima_data)} · {n_antes} série{'s' if n_antes > 1 else ''}")
                limite = topo_da_meta(ex["meta_reps"])
                if limite and anteriores["reps"].notna().all() and (anteriores["reps"] >= limite).all():
                    st.caption(f"💡 Da última vez você fez {limite}+ reps em todas as séries: tente subir a carga.")
            if qtd:
                cab = st.columns(COLUNAS_SERIE)
                cab[1].caption("Peso (kg)")
                cab[2].caption("Reps")

            for serie in range(1, qtd + 1):
                atual = salvas_hoje[salvas_hoje["serie"] == serie]
                antes = anteriores[anteriores["serie"] == serie]
                chave = chave_serie(data_iso, dia, nome, serie)
                chave_p, chave_r = f"p|{chave}", f"r|{chave}"
                # Começa com o que já foi salvo hoje; senão, com o treino anterior;
                # numa série nova, repete o que está na série de cima
                if chave_p not in st.session_state:
                    base = atual if not atual.empty else antes
                    acima = chave_serie(data_iso, dia, nome, serie - 1)
                    if not base.empty:
                        st.session_state[chave_p] = valor_de(base, "peso_kg", float)
                        st.session_state[chave_r] = valor_de(base, "reps", int)
                    else:
                        st.session_state[chave_p] = st.session_state.get(f"p|{acima}")
                        st.session_state[chave_r] = st.session_state.get(f"r|{acima}")

                salva = not atual.empty
                # Série gravada e sem mudança fica travada; mexeu no peso ou nas reps, libera para corrigir
                sem_mudanca = (salva and st.session_state[chave_p] == valor_de(atual, "peso_kg", float)
                               and st.session_state[chave_r] == valor_de(atual, "reps", int))

                col = st.columns(COLUNAS_SERIE)
                col[0].markdown(f"<div class='serie-num'>{serie}ª</div>", unsafe_allow_html=True)
                col[1].number_input("Peso (kg)", min_value=0.0, step=0.5, value=None, format="%.1f",
                                    key=chave_p, label_visibility="collapsed")
                col[2].number_input("Repetições", min_value=0, step=1, value=None,
                                    key=chave_r, label_visibility="collapsed")
                col[3].button("✅" if sem_mudanca else "💾", key=f"b|{chave}", **LARGURA_TOTAL,
                              type="secondary" if sem_mudanca else "primary", disabled=sem_mudanca,
                              help="Série gravada" if sem_mudanca else ("Gravar correção" if salva else "Gravar série"),
                              on_click=ao_salvar, args=(data_iso, dia, nome, serie))
                col[4].button("🗑️", key=f"x|{chave}", **LARGURA_TOTAL, help="Excluir esta série",
                              on_click=ao_pedir_exclusao, args=(data_iso, dia, nome, serie, salva, qtd))

                if st.session_state.get("confirmar_exclusao") == chave:
                    st.warning(f"Apagar a {serie}ª série de {nome} da planilha?")
                    conf = st.columns(2)
                    conf[0].button("Sim, apagar", key=f"xs|{chave}", type="primary", **LARGURA_TOTAL,
                                   on_click=ao_confirmar_exclusao, args=(data_iso, dia, nome, serie, qtd))
                    conf[1].button("Cancelar", key=f"xn|{chave}", **LARGURA_TOTAL, on_click=ao_cancelar_exclusao)

                partes = []
                if not antes.empty:
                    partes.append(f"antes {fmt_num(antes['peso_kg'].iloc[0])} kg × {fmt_num(antes['reps'].iloc[0])}")
                if salva:
                    partes.append(f"✓ {atual['hora'].iloc[0]}")
                    if fmt_intervalo(atual["intervalo_seg"].iloc[0]):
                        partes.append(f"intervalo {fmt_intervalo(atual['intervalo_seg'].iloc[0])}")
                if partes:
                    st.caption(" · ".join(partes))

            st.button("＋ Série", key=f"add|{data_iso}|{dia}|{nome}", on_click=ao_adicionar_serie, args=(chave_qtd,))

    with st.expander("＋ Incluir exercício neste treino"):
        prefixo = f"tr_add|{data_iso}|{dia}"
        seletor_exercicio(prefixo, {e["exercicio"] for e in exercicios})
        st.checkbox(f"Deixar fixo no treino de {dia.lower()}", value=True, key=f"{prefixo}_manter",
                    help="Desmarque para incluir só hoje, sem mudar o plano")
        st.button("Incluir", key=f"{prefixo}_ok", type="primary", **LARGURA_TOTAL,
                  on_click=ao_adicionar_exercicio, args=(prefixo, dia, chave_extras))

    feitas = len(do_dia.drop_duplicates(["exercicio", "serie"]))
    progresso.progress(min(feitas / total, 1.0) if total else 0.0,
                       text=f"**{dia} · {data_br(data_iso)}** — {feitas}/{total} séries")


def tela_historico(registros):
    if registros.empty:
        st.info("Nenhum treino salvo ainda.")
        return
    df = registros.dropna(subset=["peso_kg", "reps"]).copy()
    df["volume"] = df["peso_kg"] * df["reps"]

    st.markdown("**Treinos realizados**")
    resumo = (df.groupby(["data", "dia_treino"])
              .agg(series=("serie", "size"), exercicios=("exercicio", "nunique"), volume=("volume", "sum"),
                   inicio=("registrado_em", "min"), fim=("registrado_em", "max"))
              .reset_index().sort_values("data", ascending=False))
    resumo["duracao"] = ((resumo["fim"] - resumo["inicio"]).dt.total_seconds() / 60).round()
    tabela = pd.DataFrame({
        "Data": resumo["data"].map(data_br),
        "Treino": resumo["dia_treino"],
        "Séries": resumo["series"],
        "Exercícios": resumo["exercicios"],
        "Volume (kg)": resumo["volume"].round(0),
        "Duração (min)": resumo["duracao"],
    })
    st.dataframe(tabela, hide_index=True, **LARGURA_TOTAL)

    st.markdown("**Evolução por exercício**")
    exercicios = sorted(df["exercicio"].unique(), key=str.lower)
    escolhido = st.selectbox("Exercício", exercicios, label_visibility="collapsed")
    do_ex = df[df["exercicio"] == escolhido]
    evolucao = (do_ex.sort_values(["peso_kg", "reps"], ascending=False)
                .groupby("data").first().reset_index()[["data", "peso_kg", "reps"]])
    evolucao = evolucao.merge(do_ex.groupby("data")["volume"].sum().reset_index(), on="data").sort_values("data")

    if len(evolucao) > 1:
        grafico = pd.DataFrame({"Data": pd.to_datetime(evolucao["data"]), "Maior carga (kg)": evolucao["peso_kg"]})
        st.line_chart(grafico, x="Data", y="Maior carga (kg)", color=COR_SERIE, height=220)
    st.dataframe(pd.DataFrame({
        "Data": evolucao["data"].map(data_br),
        "Maior carga (kg)": evolucao["peso_kg"],
        "Reps nessa carga": evolucao["reps"].astype(int),
        "Volume (kg)": evolucao["volume"].round(0),
    }).iloc[::-1], hide_index=True, **LARGURA_TOTAL)

    csv = registros[REGISTROS_HEADER].assign(registrado_em=registros["registrado_em"].dt.strftime("%Y-%m-%d %H:%M:%S"))
    st.download_button("Baixar histórico completo (CSV)", csv.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       file_name=f"historico-treinos-{date.today().isoformat()}.csv", mime="text/csv")


def importar_backup_antigo(conteudo, registros):
    """Converte o backup JSON do app antigo (HTML) em linhas da planilha."""
    backup = json.loads(conteudo)
    plano = backup.get("plano") or PLANO_INICIAL
    existentes = set(zip(registros["data"], registros["dia_treino"], registros["exercicio"], registros["serie"]))
    novas, sem_data = [], 0
    for sessao in (backup.get("sessoes") or {}).values():
        data_iso, dia = sessao.get("date", ""), sessao.get("day", "")
        if data_iso == "2000-01-01":
            sem_data += 1
            continue
        linhas_sessao = []
        for chave, reg in (sessao.get("records") or {}).items():
            e, s = (int(x) for x in chave.split("|"))
            if dia not in plano or e >= len(plano[dia]):
                continue
            peso = pd.to_numeric(str(reg.get("weight", "")).replace(",", "."), errors="coerce")
            reps = pd.to_numeric(str(reg.get("reps", "")), errors="coerce")
            if pd.isna(peso) or pd.isna(reps):
                continue
            exercicio = plano[dia][e][0]
            ts = reg.get("ts")
            momento = datetime.fromtimestamp(ts / 1000, FUSO).replace(tzinfo=None) if ts else None
            linhas_sessao.append([momento, data_iso, dia, exercicio, s + 1, float(peso), int(reps), reg.get("time", "")])
        linhas_sessao.sort(key=lambda l: (l[0] is None, l[0] or datetime.min))
        anterior = None
        for momento, *resto in linhas_sessao:
            intervalo = ""
            if momento and anterior and 0 < (momento - anterior).total_seconds() <= 3600:
                intervalo = int((momento - anterior).total_seconds())
            anterior = momento or anterior
            # Séries já na planilha entram no cálculo do intervalo, mas não são gravadas de novo
            if tuple(resto[:4]) not in existentes:
                novas.append(resto + [momento.strftime("%Y-%m-%d %H:%M:%S") if momento else "", intervalo])
    return novas, sem_data


def tela_importar(registros):
    st.caption("No app antigo (HTML), toque em *Exportar backup* e envie o arquivo .json aqui.")
    arquivo = st.file_uploader("Backup .json", type=["json"], label_visibility="collapsed")
    if arquivo is not None:
        try:
            novas, sem_data = importar_backup_antigo(arquivo.getvalue().decode("utf-8"), registros)
        except Exception as erro:
            st.error(f"Não consegui ler o backup: {erro}")
            return
        if sem_data:
            st.caption(f"{sem_data} treino(s) sem data definida no app antigo foram ignorados.")
        if not novas:
            st.info("Nada novo para importar: essas séries já estão na planilha.")
        elif st.button(f"Importar {len(novas)} séries para a planilha", type="primary"):
            aba = aba_registros()
            aba.append_rows(novas, value_input_option="RAW")
            st.session_state["registros"] = carregar_registros(aba)
            st.success(f"{len(novas)} séries importadas.")


# ---------- App ----------

st.markdown(CSS, unsafe_allow_html=True)
liberar_acesso()

if "registros" not in st.session_state:
    try:
        with st.spinner("Carregando seus treinos..."):
            # O ícone no celular abre direto no aluno certo: o link leva ?aluno=Nome
            pedido = (st.query_params.get("aluno") or "").strip()
            st.session_state["aluno"] = ALUNO_PADRAO
            recarregar()
            if pedido in st.session_state["alunos"] and pedido != ALUNO_PADRAO:
                trocar_aluno(pedido)
    except Exception as erro:
        st.error(f"Não consegui abrir a planilha de treinos: {erro}")
        st.stop()
st.query_params["aluno"] = aluno_atual()

topo = st.columns([3, 1])
topo[0].subheader("🏋️ Meu Treino")
if topo[1].button("🔄", help="Recarregar da planilha", **LARGURA_TOTAL):
    recarregar()

alunos = st.session_state["alunos"]
if st.session_state.get("aluno_sel") not in alunos + [NOVO_ALUNO]:
    st.session_state["aluno_sel"] = aluno_atual()
st.selectbox("👤 Aluno", alunos + [NOVO_ALUNO], key="aluno_sel", on_change=ao_escolher_aluno)
if st.session_state["aluno_sel"] == NOVO_ALUNO:
    with st.container(border=True):
        st.text_input("Nome do novo aluno", key="novo_aluno_nome", placeholder="Ex.: Maria Silva")
        st.caption("Cada aluno tem o próprio treino e histórico, numa aba só dele na planilha.")
        st.button("Criar aluno", type="primary", on_click=ao_criar_aluno, **LARGURA_TOTAL)
    if "aviso" in st.session_state:
        st.warning(st.session_state.pop("aviso"))
    st.stop()

if "aviso" in st.session_state:
    st.warning(st.session_state.pop("aviso"))
if "salvo" in st.session_state:
    st.toast(st.session_state.pop("salvo"), icon="✅")
if "recorde" in st.session_state:
    st.toast(st.session_state.pop("recorde"), icon="🏆")

plano, registros = do_aluno(st.session_state["plano"]), st.session_state["registros"]
aba_treino, aba_montar, aba_hist = st.tabs(["Treino", "Montar treino", "Histórico"])
with aba_treino:
    tela_treino(plano, registros)
with aba_montar:
    tela_montar(plano)
with aba_hist:
    tela_historico(registros)
    with st.expander("Importar backup do app antigo"):
        tela_importar(registros)
