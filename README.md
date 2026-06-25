# **Sakura Mangás Downloader**  

## **📌 Visão Geral**  
O **Sakura Mangás Downloader** é uma ferramenta Python projetada para a extração automatizada de mangás completos ou capítulos individuais da plataforma [sakuramangas.org](https://sakuramangas.org/). O sistema opera de forma autônoma simulando interações de usuário para resolver desafios de segurança de rede e garantir a obtenção integral dos arquivos.

**Autor:** Jhoorodre  
**Repositório:** [github.com/Jhoorodre/sakuramangas-dl](https://github.com/Jhoorodre/sakuramangas-dl)  

---

## **📂 Estrutura de Arquivos**  
A arquitetura do projeto baseia-se em alta modularidade, segmentando a interface, as regras de negócio e a camada de rede:

```
Sakura-Mangas-Downloader/  
│
├── main.py               # Ponto de entrada e menu principal da aplicação
├── .env                  # Arquivo para configurar pastas de saída (NÃO versionado)
├── mapping.toml.example  # Exemplo do arquivo de mapeamento de obras
├── mapping.toml          # Repositório local de URLs de extração
│
├── src/  
│   └── core/  
│       ├── cli.py             # Módulo de interface interativa
│       ├── manga_manager.py   # Gerenciamento estrutural (I/O de arquivos e manipulação de TOML/JSON)
│       ├── network_utils.py   # Interceptação de tráfego e tratamento de DRM
│       ├── scraper.py         # Orquestração do Playwright e automação de navegação
│       └── utils.py           # Algoritmos de simulação de comportamento orgânico
│
└── download/             # Diretório de saída configurável via .env
    └── [Nome do Mangá]/  
        └── [Capítulo]/  
            ├── pag_001.jpg
            └── ...  
```

---

## **📜 Arquitetura e Conceitos**  

### **1. Interface Unificada (`main.py`)**  
O fluxo operacional é conduzido por meio de um menu interativo central.
🔹 **Recursos:**  
- **1. Baixar Capítulo(s) Específico(s)**: Permite o download de capítulos isolados ou intervalos (ex: `1, 2, 5-10`), utilizando atalhos do `mapping.toml` ou URLs diretas.
- **2. Baixar Mangá Completo (Ponta-a-Ponta)**: Automatiza a extração e o download sequencial das obras em lote. Realiza o scraping dos metadados e imediatamente faz o download dos arquivos em uma linha de produção contínua.
- **3. Sincronizar Apenas Metadados (Atualizar JSONs)**: Rastreador silencioso que inspeciona o site em busca de capítulos inéditos e traduções alternativas. Ele atualiza o banco de dados sem acionar o motor de download pesado (Ideal para rotinas periódicas de Cron).
- **4. Adicionar URLs em Lote**: Interface para injeção de lotes massivos de URLs no repositório local.
- **5. Sair**: Encerra a aplicação.

### **2. O Motor de Extração (`src/core/scraper.py` e `network_utils.py`)**  
A extração contorna métodos baseados em parsing estático (sujeitos a quebras frequentes) e adota a intercepção direta em nível de rede utilizando o Playwright.
🔹 **Características:**
- **Intercepção de Tráfego:** Analisa os pacotes HTTP do navegador em tempo real, capturando fluxos de mídia e tokens de segurança (DRM).
- **Retomada Inteligente (Smart Resume):** Efetua a verificação incremental do diretório de destino. Arquivos detectados como já baixados (`pag_XXX.jpg` ou pacotes `.cbz`) são ignorados nas requisições subsequentes.
- **Empacotamento Automático CBZ:** Quando a variável `SAVE_AS_CBZ=true` for ativada no `.env`, as galerias de imagens convertem-se automaticamente em arquivos unificados `.cbz` nativos (Zip) e expurgam a pasta crua, poupando inodes do HD e viabilizando o uso em leitores externos.
- **Fallback Tolerante a Falhas:** Incorpora rotinas de mitigação para extração via blob do DOM ou buffers de renderização, além de reloads agressivos em caso de bloqueio.

### **3. Navegação Orgânica (`src/core/utils.py`)**  
Aplica técnicas avançadas de engenharia social reversa em bots para evadir sistemas como Cloudflare e Rate Limiting.
🔹 **Características:**
- Resolução dinâmica de elementos ocultos na árvore do DOM.
- Aplicação de rolagem paralela com pausas estocásticas e movimentos de cursor não-lineares, reproduzindo estatisticamente o comportamento fisiológico humano.

---

## **⚙️ Instalação e Execução**  

1. Inicialize o ambiente virtual e instale as dependências:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Instale os binários essenciais do Playwright:
   ```bash
   playwright install chromium
   ```
3. (Opcional) Parametrize os diretórios configurando o ambiente:
   ```bash
   cp .env.example .env
   ```
4. Inicie o sistema:
   ```bash
   python main.py                  # modo headless (padrão)
   python main.py --no-headless    # abre o navegador visivelmente
   ```

---

## **🛡️ Mitigação Antibot e Execução Headless**

O alvo emprega proteções (ex: Cloudflare Turnstile) que ativamente bloqueiam conexões provenientes de automações tradicionais. O sistema contorna isso utilizando um **Fallback Dinâmico**:
- O ciclo padrão inicia requisições em modo `Headless` para conservação computacional.
- Na ocorrência de uma validação severa, o motor invoca o navegador com renderização gráfica ativa (`Headful`), supera a validação de segurança via interações orgânicas e consolida as assinaturas (cookies e tokens de validação) no armazenamento local.

**Ambientes Sem Interface Gráfica (VPS / Servidores Headless):**
Para implantações em Linux não-GUI, o Playwright exige um Display Server ativo. Use o `X Virtual Framebuffer` (Xvfb):

```bash
sudo apt install xvfb
xvfb-run python main.py --no-headless
```
*(Simula um monitor na camada X11: o navegador roda com renderização completa para validar o bloqueio antibot, mas permanece oculto para o SO.)*

---

## **🔒 Escalabilidade e Privacidade**
- O arquivo de indexação `mapping.toml` está configurado nativamente no `.gitignore`. Essa restrição previne o vazamento de coleções privadas e viabiliza a escalabilidade de extração na nuvem (VPS).
- As pastas de cache, contextos e estado do navegador são alocados no path configurado pelo `DATA_DIR` em seu `.env`, assegurando isolamento total.

---

🔗 **GitHub:** [github.com/Jhoorodre/sakuramangas-dl](https://github.com/Jhoorodre/sakuramangas-dl)
