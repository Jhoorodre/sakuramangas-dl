# **Sakura Mangás Downloader**  

## **📌 Visão Geral**  
O **Sakura Mangás Downloader** é uma ferramenta Python projetada para a extração automatizada de mangás completos ou capítulos individuais da plataforma [sakuramangas.org](https://sakuramangas.org/). O sistema opera de forma autônoma simulando interações de usuário para resolver desafios de segurança de rede e garantir a obtenção integral dos arquivos.

**Autor:** Etoshy  
**Repositório:** [github.com/Jhoorodre/sakuramangas-dl](https://github.com/Jhoorodre/sakuramangas-dl)  

---

## **📂 Estrutura de Arquivos**  
A arquitetura do projeto foi reformulada para maior modularidade e eficiência:

```
Sakura-Mangas-Downloader/  
│
├── main.py               # Ponto de entrada e menu principal da aplicação
├── mapping.toml          # Arquivo de configuração de atalhos e mapeamento de obras
│
├── src/  
│   └── core/  
│       ├── cli.py        # Módulo de interface interativa (CLI)
│       ├── scraper.py    # Motor principal de intercepção de rede e download (Playwright)
│       └── utils.py      # Funções utilitárias de navegação orgânica e renderização
│
└── donwload/             # Diretório oficial de saída dos arquivos
    └── [Nome do Mangá]/  
        └── [Capítulo]/  
            ├── pag_001.jpg
            ├── pag_002.jpg  
            └── ...  
```

---

## **📜 Funcionamento e Conceitos**  

### **1. Interface Unificada (`main.py`)**  
Todo o fluxo de uso agora acontece através de um único menu interativo central.
🔹 **Opções Disponíveis:**  
- **1. Baixar Capítulo(s)**: Permite baixar capítulos selecionados (ex: `1, 2, 5-10`). O sistema aceita a seleção através do atalho configurado no `mapping.toml`, via link direto do mangá ou busca pelo nome.
- **2. Baixar Mangá Completo**: Realiza a extração automatizada de todos os capítulos listados na página da obra selecionada.
- **3. Sair**: Encerra a aplicação.

### **2. O Motor de Extração (`src/core/scraper.py`)**  
A extração de imagens não ocorre mais por parsing estático tradicional, mas sim por intercepção direta do tráfego de rede via Playwright.
🔹 **Características:**
- **Intercepção Dinâmica:** Ouve as respostas de rede do navegador e extrai os arquivos de imagem em tempo real, independentemente da forma como o site os carrega.
- **Retomada de Download (Smart Resume):** Verifica a pasta de destino local. Se identificar páginas já baixadas e numeradas (`pag_XXX.jpg`), pula a etapa para evitar redundância de processamento.
- **Mecanismos de Fallback:** Possui rotinas secundárias de resgate via blob e leitura nativa de memória de renderização caso blocos específicos de imagem não carreguem de primeira.

### **3. Navegação Orgânica (`src/core/utils.py`)**  
Para garantir o carregamento completo do DOM (Lazy Load) e o bypass das verificações automatizadas de tráfego, o bot navega simulando a cadência humana.
🔹 **Características:**
- Expande listas de capítulos ocultas dinamicamente ("Ver Mais").
- Executa a rolagem controlada da página para desencadear as requisições de imagens sequencialmente, reduzindo a carga súbita (Rate Limiting).

---

## **⚙️ Instalação e Execução**  

1. Instale as dependências necessárias listadas no repositório.
2. Certifique-se de inicializar o motor de navegação do Playwright:
   ```bash
   playwright install chromium
   ```
3. Execute o programa:
   ```bash
   python main.py
   ```

---

## **🔍 SEO & Otimização**   
- "Baixar mangás Sakura completos"  
- "Sakura Mangás Downloader tutorial"  
- "Como baixar mangás de sakuramangas.org offline"  
- "Extrator automatizado de mangás em Python"  

🔗 **GitHub:** [github.com/Jhoorodre/sakuramangas-dl](https://github.com/Jhoorodre/sakuramangas-dl)  
