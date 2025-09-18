# GameServer Monitor

## Visão Geral
O **GameServer Monitor** é um script em **Python** desenvolvido para monitorar servidores de jogos e manter suas atividades constantes, reforçando a segurança de que o servidor sempre esteja ativo e funcionando perfeitamente, conseguindo, de forma inteligente, se recuperar após crash ou travamentos.  
Ele verifica periodicamente se o servidor está ativo, reinicia em caso de falhas, e envia notificações para um canal do **Discord** via Webhook.  
O projeto foi criado com foco em **automação, resiliência e simplicidade**.

---

<img width="494" height="223" alt="image" src="https://github.com/user-attachments/assets/5e17b387-ceb5-470c-911c-7d90965507c9" />

## Funcionalidades Principais
- **Monitoramento de Servidor**
  - Verifica a disponibilidade do servidor via IP e porta TCP.
  - Reinicia o servidor caso atinja o limite de falhas consecutivas.

- **Reinício Diário Automático**
  - Reinicia o servidor em um horário programado para garantir estabilidade (por padrão, entre 06:00 e 06:59).

- **Gerenciamento de Processos**
  - Mata processos antigos usando `psutil` antes de reiniciar.
  - Suporte para múltiplos nomes de processos configuráveis.

- **Integração com Discord**
  - Logs enviados automaticamente para um canal configurado via Webhook.
  - Inclui detalhes como status, erros e reinicializações.

- **Configuração Dinâmica**
  - Todas as opções estão em `monitor_config.json`.
  - O script recarrega o JSON a cada ciclo, permitindo alterações sem reiniciar o monitor.

- **Resiliência**
  - Captura de exceções globais, evitando que o script seja interrompido.
  - Reinício automático do processo de monitoramento.

---

## Estrutura do Projeto

```
📂 gameserver-monitor
 ┣ monitoramento.py -> Script principal de monitoramento e integração com Discord.
 ┣ monitor_config.json -> Arquivo de configuração (IP, porta, processos, limites, webhook).
 ┗ exemplo.service -> Exemplo de unit do systemd para rodar o script como serviço.
```

---

## Configuração

### Arquivo `monitor_config.json`
Exemplo de configuração (placeholders):
```json
{
    "ativo": true,
    "server_ip": "127.0.0.1", <- Coloque o endereço público real do servidor
    "server_port": 27015, <- A porta do servidor
    "check_interval": 60, <- Intervalo entre as checagens 
    "failure_limit": 10, <- O máximo de falhas aceitável na checagem
    "startup_delay": 240, <- O delay antes de começar a checar novamente após inicialização ou reinicialização
    "start_command": "./startserver.sh", <- Comando a ser lançado no console para INICIAR o servidor
    "restart_command": "./restartserver.sh", <- Comando para reiniciar
    "server_process_names": ["processo1", "processo2"], <- Os processos do servidor (para serem mortos em caso de travamento)
    "discord_webhook_url": "https://discordapp.com/api/webhooks/PLACEHOLDER/PLACEHOLDER", <- o webhook do Discord para o envio dos logs
    "icon_url": "https://i.imgur.com/9ot4o61.png" <- Ícone para ser usado no webhook
}
```


---

## Executando o Script Manualmente
Pré-requisitos:
- Python 3.10+
- Bibliotecas necessárias:
  ```bash
  pip install psutil requests
  ```

Execução manual:
```bash
python monitoramento.py
```

---

## Usando como Serviço com systemd
Para manter o monitor ativo em background no Linux, recomenda-se rodá-lo como um **serviço systemd**.

### Passo 1: Criar o arquivo de serviço
Crie o arquivo `/etc/systemd/system/<nome-do-servico>.service` com o conteúdo:

```ini
[Unit]
Description=<o nome que você quiser para o serviço>
After=network.target

[Service]
ExecStart=/usr/bin/python3 /caminho/para/monitoramento.py
WorkingDirectory=/caminho/para/o/projeto
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Passo 2: Recarregar o systemd e habilitar o serviço
```bash
sudo systemctl daemon-reload
sudo systemctl enable <nome-do-servico>
sudo systemctl start <nome-do-servico>
```

### Passo 3: Verificar o status
```bash
sudo systemctl status <nome-do-servico>
```

Assim, o script será iniciado automaticamente junto com o sistema e reiniciado em caso de falhas.

---


