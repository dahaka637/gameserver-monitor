import os
import time
import requests
import psutil
from datetime import datetime
import traceback  # Para capturar detalhes de erros
import pytz       # Biblioteca para manipulação de fuso horário
import socket
import json
from pathlib import Path
import sys

#################
# Configurações #
#################

# Caminho do arquivo de configuração
CONFIG_PATH = Path(__file__).with_name("monitor_config.json")

# Configuração padrão (será gravada na 1ª execução, se o JSON não existir)
DEFAULT_CONFIG = {
    "ativo": True,
    "server_ip": "127.0.0.1",          # IP fictício (localhost)
    "server_port": 27015,              # Porta padrão (exemplo)

    "check_interval": 60,
    "failure_limit": 10,
    "startup_delay": 240,

    "start_command": "./gmodserver start",
    "restart_command": "./gmodserver restart",
    "server_process_names": ["srcds_run", "srcds_linux"],

    # ⚠️ Para uso real, configure seu webhook no JSON manualmente.
    # Este valor é apenas um placeholder seguro.
    "discord_webhook_url": "https://discordapp.com/api/webhooks/PLACEHOLDER/PLACEHOLDER",
    "icon_url": "https://i.imgur.com/9ot4o61.png"
}


# Estado atual (carregado do JSON)
CONFIG = DEFAULT_CONFIG.copy()
ACTIVE = CONFIG["ativo"]
_CONFIG_MTIME = None  # Para detectar mudança no arquivo

# Timezone fixo
BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')

# Estado do monitoramento
failure_count = 0


def ensure_config_exists():
    """Garante que o arquivo de configuração exista com os valores padrão."""
    if not CONFIG_PATH.exists():
        try:
            CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=4), encoding="utf-8")
            print(f"[config] '{CONFIG_PATH.name}' criado com valores padrão.")
        except Exception as e:
            print(f"[config] Erro ao criar config padrão: {e}")


def _load_config():
    """
    Recarrega a configuração do JSON quando o mtime mudar.
    Preenche chaves ausentes com DEFAULT_CONFIG.
    """
    global CONFIG, ACTIVE, _CONFIG_MTIME
    try:
        st = CONFIG_PATH.stat()
        if _CONFIG_MTIME is None or st.st_mtime != _CONFIG_MTIME:
            _CONFIG_MTIME = st.st_mtime
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

            # Merge com defaults para garantir todas as chaves
            merged = DEFAULT_CONFIG.copy()
            merged.update(data or {})

            CONFIG = merged
            prev_active = ACTIVE
            ACTIVE = bool(CONFIG.get("ativo", True))

            print(f"[config] Config recarregada: ativo={ACTIVE}")
            if prev_active != ACTIVE:
                print("[config] Monitoramento {}.".format("REATIVADO" if ACTIVE else "PAUSADO"))
    except FileNotFoundError:
        # Se foi removido, recria e recarrega
        print("[config] Arquivo ausente; recriando com valores padrão.")
        ensure_config_exists()
        _load_config()
    except json.JSONDecodeError as e:
        # JSON inválido durante edição: mantém a última config válida
        print(f"[config] JSON inválido ({e}); mantendo configuração anterior.")
    except Exception as e:
        print(f"[config] Erro lendo config: {e}; mantendo configuração anterior.")


def check_server_connection(ip, port, timeout=5):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


######################################
# Função para enviar logs ao Discord #
######################################

def send_discord_log(log_type="general", *args):
    # Respeitar o toggle global (sem logs quando desativado)
    if not ACTIVE:
        return

    webhook = CONFIG.get("discord_webhook_url")
    icon_url = CONFIG.get("icon_url")

    if not webhook:
        # Sem webhook configurado => não envia nada
        return

    current_time = datetime.now(BRAZIL_TZ).strftime("%H:%M:%S")

    # Modelos de mensagens com base no tipo
    if log_type == "init":
        title = "✅ Servidor Iniciado"
        description = f"O servidor foi iniciado com sucesso às {current_time}."
        color = 0x57F287
    elif log_type == "restart":
        title = "🔄 Servidor Reiniciado"
        description = f"O servidor foi reiniciado às {current_time}."
        color = 0xFF9800
    elif log_type == "error":
        title = "⚠️ Falha no Servidor"
        description = f"Erro: {args[0]} às {current_time}"
        color = 0xE74C3C
    elif log_type == "action":
        title = "🛠️ Medida Tomada"
        description = f"Ação tomada: {args[0]} às {current_time}"
        color = 0x3498DB
    elif log_type == "log":
        title = "🔵 Log Geral"
        description = f"{args[0]} às {current_time}"
        color = 0x7289DA
    else:
        title = "🔵 Log Geral"
        description = f"Mensagem não categorizada às {current_time}"
        color = 0x7289DA

    payload = {
        "username": "QuantumRP Status",
        "avatar_url": icon_url,
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color
            }
        ]
    }

    try:
        response = requests.post(webhook, json=payload, timeout=10)
        if response.status_code != 204:
            print(f"[discord] Erro ao enviar log. HTTP: {response.status_code} | Resp: {response.text[:300]}")
    except Exception as e:
        print(f"[discord] Erro ao conectar ao Discord: {e}")


##############################################
# Função para capturar e reportar exceções   #
##############################################

def exception_handler(exc_type, exc_value, exc_traceback):
    """Captura exceções não tratadas."""
    error_message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print("Erro não tratado capturado:", error_message)
    send_discord_log("error", error_message)


# Define o manipulador global de exceções
sys.excepthook = exception_handler


##############################################
# Funções de controle do servidor            #
##############################################

def kill_server_processes():
    names = set(CONFIG.get("server_process_names", []))
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] in names:
                print(f"Matando processo {proc.info['name']} com PID {proc.info['pid']}")
                proc.terminate()
                proc.wait()
                send_discord_log("action", f"Matando processo {proc.info['name']} com PID {proc.info['pid']}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    print("Todos os processos do servidor foram terminados.")


def is_server_running():
    names = set(CONFIG.get("server_process_names", []))
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] in names:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def start_server():
    print("Iniciando o servidor de Garry's Mod...")
    os.system(CONFIG.get("start_command", ""))
    print("Comando para iniciar o servidor enviado.")
    send_discord_log("init")


####################################
# Função para monitorar o servidor #
####################################

def monitor_server():
    global failure_count
    last_restart_date = None  # Controle para reinício diário
    _last_paused = None       # Para não spammar console

    while True:
        # Recarrega config a cada ciclo (hot reload)
        _load_config()

        # Se desativado, pausa o monitoramento inteiro
        if not ACTIVE:
            if _last_paused is not True:
                print("Monitoramento PAUSADO por configuração ('ativo': false).")
            _last_paused = True
            time.sleep(CONFIG.get("check_interval", 60))
            continue
        else:
            if _last_paused:
                print("Monitoramento REATIVADO ('ativo': true).")
            _last_paused = False

        # ---------------------------------
        # Checagem para reinício diário entre 06:00 e 06:59
        # ---------------------------------
        current_time = datetime.now(BRAZIL_TZ)
        if 6 <= current_time.hour < 7 and (last_restart_date != current_time.date()):
            print("Reinício diário programado entre 06:00 e 06:59.")
            send_discord_log("log", "Reinício diário programado entre 06:00 e 06:59.")
            os.system(CONFIG.get("restart_command", ""))
            send_discord_log("restart")
            print("Aguardando para estabilização após reinício diário...")
            time.sleep(CONFIG.get("startup_delay", 240))
            failure_count = 0
            last_restart_date = current_time.date()

        # ---------------------------------
        # Checagem normal do servidor via conexão TCP
        # ---------------------------------
        ip = CONFIG.get("server_ip")
        port = int(CONFIG.get("server_port", 27015))
        if check_server_connection(ip, port):
            print("Servidor ativo. Resetando contador.")
            failure_count = 0
        else:
            failure_count += 1
            print(f"Falha detectada. Contador: {failure_count}")
            if failure_count > 3:
                send_discord_log("error", f"Falha detectada no servidor. Contador: {failure_count}")

        # ---------------------------------
        # Reinício emergencial após falhas
        # ---------------------------------
        if failure_count > int(CONFIG.get("failure_limit", 10)):
            print("Número de falhas excedido. Reiniciando servidor.")
            send_discord_log("error", f"Número de falhas excedido. Reiniciando servidor.")
            if is_server_running():
                kill_server_processes()
            os.system(CONFIG.get("restart_command", ""))
            send_discord_log("restart")

            print("Aguardando alguns segundos para o servidor reiniciar...")
            time.sleep(CONFIG.get("startup_delay", 240))
            failure_count = 0

        # ---------------------------------
        # Aguardar próximo ciclo
        # ---------------------------------
        time.sleep(CONFIG.get("check_interval", 60))


#################
# Inicialização #
#################

if __name__ == "__main__":
    ensure_config_exists()
    _load_config()

    print("Aguardando inicialização completa da VPS...")
    time.sleep(CONFIG.get("startup_delay", 240))

    # Se estiver desativado, não inicia automaticamente; o loop cuidará disso
    if ACTIVE and not is_server_running():
        start_server()

    time.sleep(CONFIG.get("startup_delay", 240))
    print("Iniciando o monitoramento do servidor...")
    monitor_server()
