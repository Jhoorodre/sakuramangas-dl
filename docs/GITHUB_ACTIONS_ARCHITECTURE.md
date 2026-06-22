# Integração Contínua: Arquitetura em Nuvem (GitHub Actions)

A automação do **Sakura Mangás Downloader** atinge o seu ápice quando integrada a pipelines de CI/CD, permitindo a sincronização massiva de capítulos em segundo plano, sem a necessidade de manter o seu computador ligado.

Esta arquitetura tira vantagem das máquinas virtuais do GitHub (`ubuntu-latest`) para rodar o motor invisível semanalmente.

---

## 1. Topologia da Arquitetura em Nuvem

O pipeline na nuvem funciona da seguinte maneira:
1. **Gatilho (Cron Job):** O relógio do GitHub aciona a máquina virtual automaticamente no dia e hora programados.
2. **Ambiente Efêmero:** Um servidor Ubuntu limpo (sem monitor) é provisionado.
3. **Simulação de Hardware (Xvfb):** Como o Cloudflare exige uma interface gráfica para validar que somos humanos, instalamos um "Monitor Fantasma" via pacote nativo do Linux (`Xvfb`).
4. **Execução Headful:** O robô roda com a diretiva `--no-headless`, achando que tem um monitor real. O bypass ocorre instantaneamente.
5. **Artefatos:** Os arquivos baixados são zipados e enviados para o seu Cloud ou salvos como "Artifacts" no painel do GitHub.

---

## 2. Implementação do Workflow Avançado (`.yml`) com Rclone

Para que a máquina destruída não perca os arquivos, integramos o **Rclone** ao final do fluxo. Ele intercepta a pasta baixada e a joga instantaneamente no seu Google Drive (ou Dropbox/OneDrive).

Crie o arquivo `.github/workflows/sync.yml` com a seguinte topologia:

```yaml
name: 🔄 Sincronização Semanal Suprema (Drive)

on:
  schedule:
    # Roda toda segunda-feira à 01:00 da manhã
    - cron: '0 1 * * 1'
  workflow_dispatch: 

jobs:
  download-e-sync:
    runs-on: ubuntu-latest

    steps:
      - name: 📦 Clonar o Repositório
        uses: actions/checkout@v4

      - name: 🐍 Configurar Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: 🛠️ Instalar Dependências e Infraestrutura (Xvfb e Rclone)
        run: |
          sudo apt-get update
          sudo apt-get install -y xvfb rclone
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          playwright install chromium

      - name: 🤖 Rodar o Robô no Monitor Fantasma
        run: |
          echo "2" | xvfb-run python main.py --no-headless

      - name: ☁️ Enviar para o Google Drive
        env:
          RCLONE_CONFIG_GDRIVE_TYPE: drive
          RCLONE_CONFIG_GDRIVE_CLIENT_ID: ${{ secrets.GDRIVE_CLIENT_ID }}
          RCLONE_CONFIG_GDRIVE_CLIENT_SECRET: ${{ secrets.GDRIVE_CLIENT_SECRET }}
          RCLONE_CONFIG_GDRIVE_TOKEN: ${{ secrets.GDRIVE_TOKEN }}
        run: |
          # Sincroniza apenas o que mudou/baixou para a nuvem
          rclone sync download/ gdrive:/SakuraMangas/ --progress
```

> **Nota de Segurança:** As chaves de acesso ao seu Drive ficam salvas na aba `Secrets` do repositório, garantindo que ninguém terá acesso ao seu Cloud.

---

## 3. Gestão Inteligente com o `mapping.toml`

Ao trabalhar em nuvem, a inteligência reside na orquestração estática:

1. **Repositório Privado:** Mantenha o repositório privado se o seu `mapping.toml` for comitado junto ao código.
2. **Filas Massivas:** Adicione centenas de URLs no `mapping.toml` e esqueça.
3. **Smart Resume Perpétuo:** Como o Rclone *sincroniza* os arquivos com a nuvem, a cada semana o robô baixa apenas os capítulos novos, e o Rclone envia apenas os capítulos novos para o seu Drive. O ecosistema se retroalimenta.

## 4. Otimização de Carga e Ética
A execução na nuvem utilizando o interceptador nativo do código (Sniffer) não agride os servidores do Sakura Mangás. Como documentado na Arquitetura Central, a banda utilizada pela máquina virtual do GitHub para capturar as imagens será idêntica à de um humano lendo um capítulo em um computador físico no Brasil.
