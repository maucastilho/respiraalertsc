"""
coleta_datasus.py
=================
Coleta dados de internaÃ§Ãµes hospitalares por doenÃ§as respiratÃ³rias (CID-10 J00â€“J99)
do Sistema de InformaÃ§Ãµes Hospitalares do SUS (SIH-SUS) para Santa Catarina.

Fluxo resiliente:
  ETAPA 1 â†’ Tenta API TabNet/DATASUS
  ETAPA 2 â†’ Tenta download de arquivos DBC pÃºblicos + conversÃ£o via pysus
  ETAPA 3 â†’ Utiliza dataset fallback jÃ¡ presente no repositÃ³rio
"""

import os
import json
import csv
import logging
import requests
import time
from datetime import datetime
from pathlib import Path

from status_dados import registrar_status

# ---------------------------------------------------------------------------
# ConfiguraÃ§Ã£o de logging
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).parent.parent / "data"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "coleta_datasus.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
ESTADO = "SC"
CID_RESPIRATORIO = "J"          # CID-10 J00â€“J99
ANOS = list(range(1990, datetime.now().year + 1))  # SIH-SUS disponÃ­vel desde 1990
DATA_DIR = Path(__file__).parent.parent / "data"
FALLBACK_CSV = DATA_DIR / "internacoes_sc.csv"

# URL base para consulta TabNet via POST (scraping estruturado)
TABNET_URL = "http://tabnet.datasus.gov.br/cgi/tabcgi.exe?sih/cnv/qisc.def"

# Mapeamento IBGE â†’ nome municÃ­pio (amostra; completado pelo JSON de municÃ­pios)
MUNICIPIOS_SC = {
    "420005": "Abdon Batista",
    "420010": "Abelardo Luz",
    "420020": "AgrolÃ¢ndia",
    "420025": "AgronÃ´mica",
    "420030": "Ãgua Doce",
    "420040": "Ãguas de ChapecÃ³",
    "420045": "Ãguas Frias",
    "420050": "Ãguas Mornas",
    "420060": "Alfredo Wagner",
    "420065": "Alto Bela Vista",
    "420070": "Anchieta",
    "420075": "Angelina",
    "420080": "Anita Garibaldi",
    "420085": "AnitÃ¡polis",
    "420090": "AntÃ´nio Carlos",
    "420095": "ApiÃºna",
    "420097": "ArabutÃ£",
    "420100": "Araquari",
    "420105": "AraranguÃ¡",
    "420110": "ArmazÃ©m",
    "420115": "Arroio Trinta",
    "420117": "Arvoredo",
    "420120": "Ascurra",
    "420125": "Atalanta",
    "420130": "Aurora",
    "420132": "BalneÃ¡rio Arroio do Silva",
    "420135": "BalneÃ¡rio CamboriÃº",
    "420140": "BalneÃ¡rio Gaivota",
    "420145": "Bandeirante",
    "420150": "Barra Bonita",
    "420155": "Barra Velha",
    "420160": "Bela Vista do Toldo",
    "420165": "Belmonte",
    "420170": "Benedito Novo",
    "420175": "BiguaÃ§u",
    "420180": "Blumenau",
    "420185": "Bocaina do Sul",
    "420190": "Bom Jardim da Serra",
    "420195": "Bom Jesus",
    "420200": "Bom Jesus do Oeste",
    "420205": "Bom Retiro",
    "420207": "Bombinhas",
    "420210": "BotuverÃ¡",
    "420215": "BraÃ§o do Norte",
    "420220": "BraÃ§o do Trombudo",
    "420225": "BrunÃ³polis",
    "420230": "Brusque",
    "420235": "CaÃ§ador",
    "420240": "Caibi",
    "420245": "Calmon",
    "420250": "CamboriÃº",
    "420255": "Campo Alegre",
    "420260": "Campo Belo do Sul",
    "420265": "Campo ErÃª",
    "420270": "Campos Novos",
    "420275": "Canelinha",
    "420280": "Canoinhas",
    "420285": "Capinzal",
    "420290": "Capivari de Baixo",
    "420295": "Catanduvas",
    "420300": "Caxambu do Sul",
    "420305": "Celso Ramos",
    "420308": "Cerro Negro",
    "420310": "ChapadÃ£o do Lageado",
    "420315": "ChapecÃ³",
    "420320": "Cocal do Sul",
    "420325": "ConcÃ³rdia",
    "420330": "Cordilheira Alta",
    "420335": "Coronel Freitas",
    "420340": "Coronel Martins",
    "420345": "CorupÃ¡",
    "420350": "Correia Pinto",
    "420355": "CriciÃºma",
    "420360": "Cunha PorÃ£",
    "420365": "CunhataÃ­",
    "420370": "Curitibanos",
    "420375": "Descanso",
    "420380": "DionÃ­sio Cerqueira",
    "420385": "Dona Emma",
    "420390": "Doutor Pedrinho",
    "420395": "Entre Rios",
    "420398": "Ermo",
    "420400": "Erval Velho",
    "420405": "Faxinal dos Guedes",
    "420407": "Flor do SertÃ£o",
    "420410": "FlorianÃ³polis",
    "420415": "Formosa do Sul",
    "420420": "Forquilhinha",
    "420425": "Fraiburgo",
    "420427": "Frei RogÃ©rio",
    "420430": "GalvÃ£o",
    "420435": "Garopaba",
    "420440": "Garuva",
    "420445": "Gaspar",
    "420450": "Governador Celso Ramos",
    "420455": "GrÃ£o ParÃ¡",
    "420460": "Gravatal",
    "420465": "Guabiruba",
    "420470": "Guaraciaba",
    "420475": "Guaramirim",
    "420480": "GuarujÃ¡ do Sul",
    "420482": "GuatambÃº",
    "420485": "Herval d'Oeste",
    "420490": "Ibiam",
    "420495": "IbicarÃ©",
    "420500": "Ibirama",
    "420505": "IÃ§ara",
    "420510": "Ilhota",
    "420515": "ImaruÃ­",
    "420520": "Imbituba",
    "420525": "Imbuia",
    "420530": "Indaial",
    "420535": "IomerÃª",
    "420540": "Ipira",
    "420545": "IporÃ£ do Oeste",
    "420550": "IpuaÃ§u",
    "420555": "Ipumirim",
    "420557": "Iraceminha",
    "420560": "Irani",
    "420562": "Irati",
    "420565": "IrineÃ³polis",
    "420570": "ItÃ¡",
    "420575": "ItaiÃ³polis",
    "420580": "ItajaÃ­",
    "420585": "Itapema",
    "420590": "Itapiranga",
    "420595": "ItapoÃ¡",
    "420600": "Ituporanga",
    "420605": "JaborÃ¡",
    "420610": "Jacinto Machado",
    "420615": "Jaguaruna",
    "420620": "JaraguÃ¡ do Sul",
    "420625": "JardinÃ³polis",
    "420630": "JoaÃ§aba",
    "420635": "Joinville",
    "420640": "JosÃ© Boiteux",
    "420645": "JupiÃ¡",
    "420650": "LacerdÃ³polis",
    "420655": "Lages",
    "420660": "Laguna",
    "420665": "Lajeado Grande",
    "420670": "Laurentino",
    "420675": "Lauro MÃ¼ller",
    "420680": "Lebon RÃ©gis",
    "420685": "Leoberto Leal",
    "420687": "LindÃ³ia do Sul",
    "420690": "Lontras",
    "420695": "Luiz Alves",
    "420697": "Luzerna",
    "420700": "Macieira",
    "420705": "Mafra",
    "420710": "Major Gercino",
    "420715": "Major Vieira",
    "420720": "MaracajÃ¡",
    "420725": "Maravilha",
    "420730": "Marema",
    "420735": "Massaranduba",
    "420740": "Matos Costa",
    "420745": "Meleiro",
    "420747": "Mirim Doce",
    "420750": "Modelo",
    "420755": "MondaÃ­",
    "420760": "Monte Carlo",
    "420765": "Monte Castelo",
    "420770": "Morro da FumaÃ§a",
    "420775": "Morro Grande",
    "420780": "Navegantes",
    "420785": "Nova Erechim",
    "420788": "Nova Itaberaba",
    "420790": "Nova Trento",
    "420795": "Nova Veneza",
    "420797": "Novo Horizonte",
    "420800": "Orleans",
    "420802": "OtacÃ­lio Costa",
    "420805": "Ouro",
    "420810": "Ouro Verde",
    "420815": "Paial",
    "420820": "Painel",
    "420825": "PalhoÃ§a",
    "420830": "Palma Sola",
    "420835": "Palmeira",
    "420840": "Palmitos",
    "420845": "Papanduva",
    "420855": "Passo de Torres",
    "420860": "Passos Maia",
    "420865": "Paulo Lopes",
    "420870": "Pedras Grandes",
    "420875": "Penha",
    "420880": "Peritiba",
    "420885": "PetrolÃ¢ndia",
    "420890": "Pinhalzinho",
    "420895": "Pinheiro Preto",
    "420900": "Piratuba",
    "420905": "Planalto Alegre",
    "420910": "Pomerode",
    "420915": "Ponte Alta",
    "420920": "Ponte Alta do Norte",
    "420925": "Ponte Serrada",
    "420930": "Porto Belo",
    "420935": "Porto UniÃ£o",
    "420940": "Pouso Redondo",
    "420945": "Praia Grande",
    "420950": "Presidente Castello Branco",
    "420955": "Presidente GetÃºlio",
    "420960": "Presidente Nereu",
    "420962": "Princesa",
    "420965": "Quilombo",
    "420970": "Rancho Queimado",
    "420975": "Rio das Antas",
    "420980": "Rio do Campo",
    "420985": "Rio do Oeste",
    "420990": "Rio do Sul",
    "420995": "Rio dos Cedros",
    "421000": "Rio Fortuna",
    "421005": "Rio Negrinho",
    "421007": "Rio Rufino",
    "421010": "Riqueza",
    "421015": "Rodeio",
    "421020": "RomelÃ¢ndia",
    "421025": "Salete",
    "421027": "Saltinho",
    "421030": "Salto Veloso",
    "421032": "SangÃ£o",
    "421035": "Santa CecÃ­lia",
    "421040": "Santa Helena",
    "421045": "Santa Rosa de Lima",
    "421050": "Santa Rosa do Sul",
    "421053": "Santa Terezinha",
    "421055": "Santa Terezinha do Progresso",
    "421060": "Santiago do Sul",
    "421065": "Santo Amaro da Imperatriz",
    "421070": "SÃ£o Bento do Sul",
    "421075": "SÃ£o Bernardino",
    "421080": "SÃ£o BonifÃ¡cio",
    "421085": "SÃ£o Carlos",
    "421090": "SÃ£o CristÃ³vÃ£o do Sul",
    "421095": "SÃ£o Domingos",
    "421100": "SÃ£o Francisco do Sul",
    "421105": "SÃ£o JoÃ£o Batista",
    "421107": "SÃ£o JoÃ£o do ItaperiÃº",
    "421110": "SÃ£o JoÃ£o do Oeste",
    "421115": "SÃ£o JoÃ£o do Sul",
    "421120": "SÃ£o Joaquim",
    "421125": "SÃ£o JosÃ©",
    "421130": "SÃ£o JosÃ© do Cedro",
    "421135": "SÃ£o JosÃ© do Cerrito",
    "421140": "SÃ£o LourenÃ§o do Oeste",
    "421145": "SÃ£o Ludgero",
    "421150": "SÃ£o Martinho",
    "421155": "SÃ£o Miguel da Boa Vista",
    "421157": "SÃ£o Miguel do Oeste",
    "421160": "SÃ£o Pedro de AlcÃ¢ntara",
    "421165": "Saudades",
    "421170": "Schroeder",
    "421175": "Seara",
    "421177": "Serra Alta",
    "421180": "SiderÃ³polis",
    "421185": "Sombrio",
    "421187": "Sul Brasil",
    "421190": "TaiÃ³",
    "421195": "TangarÃ¡",
    "421197": "Tigrinhos",
    "421200": "Tijucas",
    "421205": "TimbÃ© do Sul",
    "421210": "TimbÃ³",
    "421215": "TimbÃ³ Grande",
    "421220": "TrÃªs Barras",
    "421225": "Treviso",
    "421230": "Treze de Maio",
    "421235": "Treze TÃ­lias",
    "421240": "Trombudo Central",
    "421245": "TubarÃ£o",
    "421250": "TunÃ¡polis",
    "421255": "Turvo",
    "421260": "UniÃ£o do Oeste",
    "421265": "Urubici",
    "421267": "Urupema",
    "421270": "Urussanga",
    "421275": "VargeÃ£o",
    "421280": "Vargem",
    "421283": "Vargem Bonita",
    "421285": "Vidal Ramos",
    "421290": "Videira",
    "421295": "Vitor Meireles",
    "421300": "Witmarsum",
    "421305": "XanxerÃª",
    "421310": "Xavantina",
    "421315": "Xaxim",
    "421320": "ZortÃ©a",
}

MUNICIPIOS_SC.update({
    "4202057": "BalneÃ¡rio Barra do Sul",
    "4212809": "BalneÃ¡rio PiÃ§arras",
    "4220000": "BalneÃ¡rio RincÃ£o",
    "4203253": "CapÃ£o Alto",
    "4212239": "ParaÃ­so",
    "4212650": "Pescaria Brava",
})


# ---------------------------------------------------------------------------
# ETAPA 1 â€” Coleta via TabNet DATASUS
# ---------------------------------------------------------------------------
def coletar_via_tabnet(ano: int, mes: int) -> list[dict] | None:
    """
    Tenta realizar consulta ao TabNet DATASUS via POST.
    Retorna lista de dicts {municipio_ibge, municipio_nome, ano, mes, internacoes}
    ou None em caso de falha.
    """
    try:
        # ParÃ¢metros de consulta ao TabNet (SIH/SC, CID J, agrupado por municÃ­pio/mÃªs)
        params = {
            "Linha": "MunicÃ­pio",
            "Coluna": "MÃªs",
            "Incremento": "InternaÃ§Ãµes",
            "Pesqmes1": "CapÃ­tulo CID-10",
            "SMarca1": f"J",
            "Pesqmes2": "Ano proc.",
            "SMarca2": str(ano),
            "pesqmes3": "UF da internaÃ§Ã£o",
            "SMarca3": "42",  # cÃ³digo SC
            "formato": "prn",
            "mostre": "Mostra",
        }
        resp = requests.post(TABNET_URL, data=params, timeout=30)
        if resp.status_code != 200:
            log.warning(f"TabNet retornou HTTP {resp.status_code} para {ano}/{mes:02d}")
            return None

        # Parse do texto PRN retornado
        linhas = resp.text.splitlines()
        registros = []
        for linha in linhas:
            partes = linha.split(";")
            if len(partes) < 3:
                continue
            cod_mun = partes[0].strip()
            if cod_mun not in MUNICIPIOS_SC:
                continue
            try:
                internacoes = int(partes[mes].strip().replace(".", ""))
            except (ValueError, IndexError):
                continue
            registros.append({
                "municipio_ibge": cod_mun,
                "municipio_nome": MUNICIPIOS_SC[cod_mun],
                "ano": ano,
                "mes": mes,
                "internacoes": internacoes,
            })
        log.info(f"TabNet: {len(registros)} registros para {ano}/{mes:02d}")
        return registros if registros else None

    except Exception as exc:
        log.warning(f"TabNet falhou para {ano}/{mes:02d}: {exc}")
        return None


# ---------------------------------------------------------------------------
# ETAPA 2 â€” Download de arquivos DBC pÃºblicos
# ---------------------------------------------------------------------------
def coletar_via_ftp_datasus(ano: int) -> list[dict] | None:
    """
    Tenta baixar arquivo RD (SIH reduzido) do FTP pÃºblico do DATASUS.
    Requer pysus instalado (pip install pysus).
    """
    try:
        from pysus.online_data.SIH import download
        import pandas as pd

        log.info(f"Baixando SIH via pysus para SC {ano}...")
        # download retorna DataFrame com todas as AIH do estado/ano
        df = download(state="SC", year=ano, month=list(range(1, 13)), group="RD")
        if df is None or df.empty:
            return None

        # Filtrar CID J
        df = df[df["DIAG_PRINC"].str.startswith("J", na=False)]
        df["mes"] = pd.to_datetime(df["DT_INTER"], format="%Y%m%d").dt.month
        df["municipio_ibge"] = df["MUNIC_RES"].astype(str)
        df["ano"] = ano

        agg = (
            df.groupby(["municipio_ibge", "ano", "mes"])
            .size()
            .reset_index(name="internacoes")
        )

        registros = []
        for _, row in agg.iterrows():
            cod = row["municipio_ibge"]
            registros.append({
                "municipio_ibge": cod,
                "municipio_nome": MUNICIPIOS_SC.get(cod, "Desconhecido"),
                "ano": int(row["ano"]),
                "mes": int(row["mes"]),
                "internacoes": int(row["internacoes"]),
            })

        log.info(f"pysus: {len(registros)} registros para {ano}")
        return registros if registros else None

    except ImportError:
        log.warning("pysus nÃ£o instalado â€” ETAPA 2 indisponÃ­vel")
        return None
    except Exception as exc:
        log.warning(f"pysus falhou para {ano}: {exc}")
        return None


# ---------------------------------------------------------------------------
# ETAPA 3 â€” Fallback: dataset existente no repositÃ³rio
# ---------------------------------------------------------------------------
def carregar_fallback() -> list[dict]:
    """Carrega CSV de fallback jÃ¡ presente no repositÃ³rio."""
    if not FALLBACK_CSV.exists():
        log.error("Arquivo fallback internacoes_sc.csv nÃ£o encontrado!")
        return []

    registros = []
    with open(FALLBACK_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            registros.append({
                "municipio_ibge": row.get("municipio_ibge", ""),
                "municipio_nome": row.get("municipio_nome", ""),
                "ano": int(row.get("ano", 0)),
                "mes": int(row.get("mes", 0)),
                "internacoes": int(row.get("internacoes", 0)),
            })

    log.info(f"Ultimo dataset local carregado: {len(registros)} registros de {FALLBACK_CSV}")
    return registros


# ---------------------------------------------------------------------------
# Funcao principal
# ---------------------------------------------------------------------------
def contar_municipios(registros: list[dict]) -> int:
    return len({r.get("municipio_ibge") for r in registros if r.get("municipio_ibge")})


def coletar_internacoes() -> tuple[list[dict], str]:
    """
    Executa o fluxo de coleta resiliente.
    Se a coleta oficial vier incompleta, mantem o ultimo CSV valido local.
    """
    todos = []

    for ano in ANOS:
        resultado = coletar_via_ftp_datasus(ano)
        if resultado:
            todos.extend(resultado)
            continue

        for mes in range(1, 13):
            resultado = coletar_via_tabnet(ano, mes)
            if resultado:
                todos.extend(resultado)
                time.sleep(0.5)

    total_municipios = contar_municipios(todos)
    if total_municipios < 295:
        motivo = (
            f"Coleta oficial incompleta ({total_municipios} municipios). "
            "Mantendo ultimo dataset valido local."
        )
        log.warning(motivo)
        registrar_status("DATASUS/SIH-SUS", "ultimo_valido", motivo, len(todos))
        return carregar_fallback(), "ultimo_valido"

    registrar_status(
        "DATASUS/SIH-SUS",
        "oficial_atualizado",
        "Internacoes atualizadas a partir de fonte oficial DATASUS/SIH-SUS.",
        len(todos),
    )
    return todos, "oficial"

# ---------------------------------------------------------------------------
# Salvar resultados
# ---------------------------------------------------------------------------
def salvar_csv(registros: list[dict]) -> None:
    campos = ["municipio_ibge", "municipio_nome", "ano", "mes", "internacoes"]
    with open(FALLBACK_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(registros)
    log.info(f"CSV salvo: {FALLBACK_CSV} ({len(registros)} linhas)")


def registrar_log(sucesso: bool, fonte: str, n_registros: int) -> None:
    log_path = DATA_DIR / "logs.json"
    entrada = {
        "timestamp": datetime.now().isoformat(),
        "coleta": "datasus",
        "sucesso": sucesso,
        "fonte": fonte,
        "registros": n_registros,
    }
    historico = []
    if log_path.exists():
        with open(log_path, encoding="utf-8") as f:
            try:
                historico = json.load(f)
            except json.JSONDecodeError:
                historico = []
    historico.append(entrada)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(historico[-200:], f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    log.info("=== InÃ­cio da coleta DATASUS ===")
    registros, fonte = coletar_internacoes()
    if fonte == "oficial":
        salvar_csv(registros)
    else:
        log.warning("CSV de internacoes mantido sem sobrescrever: usando ultimo dataset valido.")
    registrar_log(bool(registros), fonte, len(registros))
    log.info(f"=== Coleta concluÃ­da: {len(registros)} registros ===")

