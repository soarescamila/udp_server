## Protocolo P2P File Sync (UDP)
Projeto de aplicação de sincronização de arquivos peer to peer (P2P) sobre o protocolo UDP através de protocolo personalizado de controle e transferência confiável de dados.

O protocolo opera na camada de aplicação utilizando UDP como transporte. A aplicação implementa mecanismos de garantia de entrega, ordenação e checagem de erros.

### Estrutura dos Pacotes
Todos os pacotes trafegados pela rede seguem um formato textual estrito de três partes: 

`PACKET = CHECKSUM + MESSAGE_TYPE + PAYLOAD`

**CHECKSUM:** Valor inteiro derivado do cálculo do 16-bit Internet Checksum (soma de complemento de um) sobre o corpo da mensagem (MESSAGE_TYPE + PAYLOAD). Se o checksum for inválido, o pacote é descartado.

**MESSAGE_TYPE:** Tipo da instrução (ANNOUNCE, REQUEST_FILE, FILE_START, FILE_DATA, FILE_END, ACK, DELETE, LIST, ERROR).

**PAYLOAD:** Dados associados ao comando (metadados do arquivo, número do bloco).

### Garantia de Entrega (Stop-and-Wait ARQ)
A transferência de arquivos fragmenta os dados em blocos de 512 bytes:

1. O transmissor envia o bloco `FILE_DATA` com seu índice (`FILE_DATA 0`).
2. O transmissor aguarda um pacote `ACK 0` durante um tempo limite (`ACK_TIMEOUT = 1.0s`).
3. Caso o ACK não chegue a tempo, o pacote é retransmitido até o limite máximo definido por `MAX_RETRIES = 5`.

### Arquitetura
**1. Servidor UDP (server.py):** Fica em escuta contínua na porta, respondendo a requisições de controle, registrando peers ativos e processando solicitações de transferência.

**2. Cliente UDP (client.py):** Gerencia o envio de mensagens de anúncio, sincronização inicial e requisição de arquivos ausentes.

**3. Monitor de Pasta (folder_monitor):** Monitora em segundo plano a pasta temp/ local a cada 2 segundos. Se um arquivo for colado ou excluído diretamente pelo sistema operacional, a alteração é propagada via `ANNOUNCE` ou `DELETE` para todos os peers. 

### Setup
Necessário o Python 3.13 (ou superior) instalado. Pode ser via instalador oficial no site https://www.python.org/downloads ou via terminal.

**Windows (PowerShell):**
```PowerShell
 winget install -e --id Python.Python.3.13
 ```

**MacOS (Homebrew):**
``` Bash
brew install python@3.13
```
**Linux (Ubuntu/Debian)**
```Bash
sudo apt install python3.13
```
### Config local
Clone o projeto para as máquinas que participarão da rede P2P. 
```bash
git clone https://github.com/soarescamila/udp_server.git
```
No arquivo `config.py` ajuste a comunicação entre as duas máquinas.
Identifique o endereço IPv4 de cada computador na rede local via `ipconfig` no Windows ou `ifconfig` no Mac/Linux.
Por exemplo:

Na Máquina 1  IP: 192.168.15.10:
```Python
IP = '0.0.0.0'
PORT = 5000
PEERS = [('192.168.15.20', 5000)]  # IP da Máquina 2
```
Na Máquina 2 IP: 192.168.15.20:
```Python
IP = '0.0.0.0'
PORT = 5000
PEERS = [('192.168.15.10', 5000)]  # IP da Máquina 1
```
Para executar a aplicação use:
```bash
python3 app.py
```
ou
```bash
py app.py
```

O servidor UDP inicia em segundo plano na porta configurada e exibe os arquivos locais. O cliente varre a pasta e avisa os peers da rede quais arquivos possui, aquele arquivo que estiver faltando localmente, é solicitado aos peers da rede e baixado localmente. O servidor em segundo plano mantém a escuta, sincronizando a pasta a cada alteração feita pelos outros peers.

---
Integrante: Camila Soares