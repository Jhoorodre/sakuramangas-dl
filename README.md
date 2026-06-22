# **Sakura Mangás Downloader**  

## **📌 Visão Geral**  
O **Sakura Mangás Downloader** é uma ferramenta Python projetada para a extração automatizada de mangás completos ou capítulos individuais da plataforma [sakuramangas.org](https://sakuramangas.org/). O sistema opera de forma autônoma simulando interações de usuário para resolver desafios de segurança de rede e garantir a obtenção integral dos arquivos.

**Autor:** Jhoorodre  
**Repositório:** [github.com/Jhoorodre/sakuramangas-dl](https://github.com/Jhoorodre/sakuramangas-dl)  

---

## **📂 Estrutura de Arquivos**  
A arquitetura do projeto foi reformulada para máxima modularidade, separando interface, regras de negócio e rede:

```
Sakura-Mangas-Downloader/  
│
├── main.py               # Ponto de entrada e menu principal da aplicação
├── .env                  # Arquivo para configurar pastas de saída (NÃO sobe pro Git)
├── mapping.toml.example  # Exemplo do arquivo de mapeamento de obras
├── mapping.toml          # Arquivo local com a fila gigante de URLs
│
├── src/  
│   └── core/  
│       ├── cli.py             # Módulo de interface interativa (Menus)
│       ├── manga_manager.py   # Gerenciamento de Pastas, JSONs e TOML (Regras de Negócio)
│       ├── network_utils.py   # Interceptador de rede, senhas DRM e fallbacks (JS Blob)
│       ├── scraper.py         # Motor principal que orquestra o Playwright e a navegação
│       └── utils.py           # Funções utilitárias de simulação orgânica
│
└── download/             # Diretório oficial de saída dos arquivos (Pode ser alterado no .env)
    └── [Nome do Mangá]/  
        └── [Capítulo]/  
            ├── pag_001.jpg
            └── ...  
```

---

## **📜 Funcionamento e Conceitos**  

### **1. Interface Unificada (`main.py`)**  
Todo o fluxo de uso agora acontece através de um único menu interativo central.
🔹 **Opções Disponíveis:**  
- **1. Baixar Capítulo(s)**: Permite baixar capítulos selecionados (ex: `1, 2, 5-10`). O sistema aceita a seleção através do atalho configurado no `mapping.toml`, via link direto do mangá ou busca pelo nome.
- **2. Baixar Mangá Completo**: Realiza a extração automatizada de todos os capítulos listados nas obras carregadas.
- **3. Adicionar URLs em Lote**: Permite colar milhares de URLs no terminal e injetá-las automaticamente no seu arquivo `mapping.toml`.
- **4. Sair**: Encerra a aplicação.

### **2. O Motor de Extração (`src/core/scraper.py` e `network_utils.py`)**  
A extração de imagens não ocorre mais por parsing estático tradicional, mas sim por intercepção direta do tráfego de rede via Playwright.
🔹 **Características:**
- **Grampo de Rede (Sniffer):** Ouve as respostas de rede do navegador, intercepta as imagens e rouba chaves DRM (como cabeçalhos `x-`) em tempo real.
- **Retomada Inteligente (Smart Resume):** Verifica a pasta de destino local. Se identificar páginas já baixadas e numeradas (`pag_XXX.jpg`), pula a etapa e apenas atualiza o histórico.
- **Mecanismos de Fallback:** Possui rotinas secundárias de resgate via blob e leitura nativa de memória de renderização caso blocos de imagem falhem. Conta também com uma rotina de Recarregamento Físico Extremo (F5).

### **3. Navegação Orgânica (`src/core/utils.py`)**  
Para contornar o Cloudflare e sistemas antibot (Rate Limiting), o robô ignora injeções de JS e usa física real.
🔹 **Características:**
- Expande listas de capítulos ocultas dinamicamente.
- O motor roda a exatos "60fps", aplicando rolagem física (scroll wheel) intercalada com pausas imprevisíveis e movimentos de mouse erráticos, simulando cansaço e distração humana.

---

## **⚙️ Instalação e Execução**  

1. Instale as dependências necessárias no seu ambiente virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Inicialize o motor de navegação do Playwright:
   ```bash
   playwright install chromium
   ```
3. (Opcional) Copie o arquivo de exemplo do ambiente e configure suas pastas:
   ```bash
   cp .env.example .env
   ```
4. Execute o programa:
   ```bash
   python main.py
   ```

---

## **🔒 Escalabilidade e Privacidade**
- O arquivo `mapping.toml` está no `.gitignore`. Isso significa que você pode colar 3.000 URLs da sua VPS sem correr o risco de expô-las no repositório.
- A pasta de cache do Playwright é montada dinamicamente dentro do `DATA_DIR` definido no seu `.env`.

---

## **🔍 SEO & Otimização**   
- "Baixar mangás Sakura completos"  
- "Sakura Mangás Downloader tutorial"  
- "Como baixar mangás de sakuramangas.org offline"  
- "Extrator automatizado de mangás em Python"  

🔗 **GitHub:** [github.com/Jhoorodre/sakuramangas-dl](https://github.com/Jhoorodre/sakuramangas-dl)  
