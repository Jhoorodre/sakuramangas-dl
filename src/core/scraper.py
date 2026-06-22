import os
import json
import logging
import random
from playwright.sync_api import sync_playwright
from src.core.utils import (
    handle_cloudflare,
    activate_scroll_mode,
    expand_chapters_list,
    JS_EXTRACT_MANGA,
    format_state_file,
)

# Configurando o log para salvar no pipeline.log além de imprimir na tela
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler("pipeline.log"), logging.StreamHandler()],
)


class SakuraScraper:
    def __init__(self, headless=False):
        self.headless = headless
        data_dir = os.environ.get("DATA_DIR", "data")
        self.state_file = os.path.join(data_dir, "state_file.json")
        os.makedirs(data_dir, exist_ok=True)

        # Correção contra crashes: Se o arquivo state existir mas estiver vazio ou corrompido, delete-o.
        if os.path.exists(self.state_file):
            try:
                if os.path.getsize(self.state_file) == 0:
                    os.remove(self.state_file)
                else:
                    with open(self.state_file, "r") as f:
                        json.load(f)
            except Exception:
                os.remove(self.state_file)

    def _extract_meta(self, url):
        """Extrai o nome do mangá e o capítulo da URL para criar as pastas."""
        parts = url.strip("/").split("/")
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        return "desconhecido", "00"

    def _launch_browser(self, p):
        """Lança um contexto persistente que salva Cache no disco, emulando um Chrome humano."""
        data_dir = os.environ.get("DATA_DIR", "data")
        user_data_dir = os.path.join(data_dir, "browser_cache")
        os.makedirs(user_data_dir, exist_ok=True)

        args = ["--disable-blink-features=AutomationControlled"]

        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=self.headless,
            args=args,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # O launch_persistent já abre uma aba padrão. Vamos usá-la.
        page = context.pages[0] if context.pages else context.new_page()

        # Bloqueador de Popups: Mata qualquer aba de propaganda que tentar abrir
        context.on("page", lambda new_page: new_page.close())

        return context, page

    def download_chapter(
        self, url, manga_name=None, chapter_name=None, output_base_dir="download"
    ):
        from src.core.network_utils import ImageInterceptor

        if not manga_name or not chapter_name:
            m_name, c_name = self._extract_meta(url)
            manga_name = manga_name or m_name
            chapter_name = chapter_name or c_name

        output_dir = os.path.join(output_base_dir, manga_name, chapter_name)
        os.makedirs(output_dir, exist_ok=True)

        arquivos_prontos = [
            f
            for f in os.listdir(output_dir)
            if f.startswith("pag_") and f.endswith(".jpg")
        ]
        if len(arquivos_prontos) > 0:
            logging.info(
                f"[PIPELINE] PULO INTELIGENTE: Capítulo já está 100% baixado ({len(arquivos_prontos)} páginas). Ignorando: {chapter_name}"
            )
            return True

        logging.info(f"[PIPELINE] Preparando ambiente. Modo Headless: {self.headless}")
        logging.info(f"[PIPELINE] Pasta de destino: {output_dir}")

        with sync_playwright() as p:
            context, page = self._launch_browser(p)
            interceptor = ImageInterceptor(output_dir)

            page.route("**/*", interceptor.throttle_traffic)
            page.on("response", interceptor.handle_response)

            logging.info("[PIPELINE] Acessando SakuraMangas...")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                logging.error(f"[PIPELINE] Erro ao carregar página inicial: {e}")

            handle_cloudflare(page, context, self.state_file)

            logging.info(
                "[PIPELINE] Deixando a poeira baixar para as imagens iniciais carregarem em paz (10s)..."
            )
            page.wait_for_timeout(10000)

            activate_scroll_mode(page)

            logging.info(
                "[PIPELINE] Acionando Scroll Brutal e Next Page para provocar Lazy Load..."
            )
            timeout = 60
            last_len = -1
            stable_count = 0

            while timeout > 0:
                current_len = len(interceptor.downloaded_files)

                page.mouse.wheel(0, random.randint(800, 1500))
                page.wait_for_timeout(random.randint(800, 1800))

                if random.random() < 0.10:
                    logging.info(
                        "  -> [STEALTH] Simulando leitura atenta (pausa dramática na página)..."
                    )
                    page.wait_for_timeout(random.randint(4000, 8000))

                if random.random() < 0.15:
                    logging.info(
                        "  -> [STEALTH] Rolou muito rápido! Subindo a tela para reler..."
                    )
                    page.mouse.wheel(0, random.randint(-600, -200))
                    page.wait_for_timeout(random.randint(600, 1400))

                if random.random() < 0.25:
                    page.mouse.move(
                        random.randint(50, 1000),
                        random.randint(50, 800),
                        steps=random.randint(8, 25),
                    )
                    page.wait_for_timeout(random.randint(100, 400))

                is_bottom = page.evaluate("""() => {
                    const footer = document.querySelector('.footer-text-col');
                    if (footer) {
                        const rect = footer.getBoundingClientRect();
                        return rect.top <= window.innerHeight + 500;
                    }
                    return window.scrollY + window.innerHeight >= document.body.scrollHeight - 200;
                }""")

                if current_len > 0:
                    if current_len == last_len:
                        stable_count += 1
                        max_wait = 3 if is_bottom else 15

                        if stable_count >= max_wait:
                            logging.info(
                                f"[PIPELINE] Rodapé atingido / Sem novas imagens. Total de páginas: {current_len}"
                            )
                            break
                    else:
                        last_len = current_len
                        stable_count = 0
                else:
                    try:
                        page.mouse.click(500, 500)
                    except Exception:
                        pass

                timeout -= 1
                if timeout % 10 == 0:
                    logging.info(f"[PIPELINE] Coletadas até agora: {current_len}")

            # Resgate Passivo via JS Fetch Blob
            interceptor.rescue_missing_images_via_js(page)

            # Plano C: Reload (F5) Extremo caso ainda faltem imagens
            faltantes = [
                u
                for u in interceptor.ordered_urls
                if u not in interceptor.downloaded_files
            ]
            if len(faltantes) > 0:
                logging.warning(
                    f"\n[PIPELINE] {len(faltantes)} imagens resistiram ao resgate. Acionando PLANO C: Reload (F5) Extremo!"
                )
                try:
                    page.reload(wait_until="networkidle", timeout=60000)
                    logging.info(
                        "[PIPELINE] F5 Concluído. Deixando a poeira baixar (10s)..."
                    )
                    page.wait_for_timeout(10000)

                    activate_scroll_mode(page)

                    logging.info("[PIPELINE] Fazendo uma varredura final na página...")
                    for _ in range(random.randint(4, 7)):
                        page.mouse.wheel(0, random.randint(1200, 1800))
                        page.wait_for_timeout(random.randint(1200, 2000))

                    page.mouse.wheel(0, random.randint(8000, 12000))
                    page.wait_for_timeout(random.randint(4000, 6000))

                    faltantes_final = [
                        u
                        for u in interceptor.ordered_urls
                        if u not in interceptor.downloaded_files
                    ]
                    if len(faltantes_final) > 0:
                        logging.error(
                            f"[PIPELINE] Fim da linha. {len(faltantes_final)} imagens não puderam ser salvas."
                        )
                    else:
                        logging.info(
                            "[PIPELINE] F5 Extremo foi um sucesso! Todas as imagens recuperadas."
                        )
                except Exception as e:
                    logging.error(f"[PIPELINE] Erro catastrófico no F5: {e}")

            interceptor.finalize_and_rename_images()

            logging.info("======================================")
            logging.info("🎯 DOWNLOAD CONCLUÍDO!")
            logging.info(
                f"🎯 Total de imagens roubadas: {len(interceptor.downloaded_files)}"
            )
            logging.info("======================================")

            try:
                context.storage_state(path=self.state_file)
                format_state_file(self.state_file)
            except Exception:
                pass
            context.close()
            return True

    def search_manga(self, query):
        """Pesquisa um mangá pelo nome e retorna uma lista de resultados {title, url}."""
        logging.info(f"[*] Pesquisando por: {query}")
        with sync_playwright() as p:
            context, page = self._launch_browser(p)

            try:
                search_url = f"https://sakuramangas.org/?s={query.replace(' ', '+')}"
                try:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                except Exception:
                    pass

                handle_cloudflare(page, context, self.state_file)

                results = page.evaluate("""() => {
                    let items = [];
                    let links = document.querySelectorAll('a[href*="/obras/"]');
                    let seen = new Set();
                    links.forEach(a => {
                        let url = a.href;
                        let title = a.innerText.trim();
                        if(title && !seen.has(url) && title.length > 2) {
                            seen.add(url);
                            items.push({title: title, url: url});
                        }
                    });
                    return items;
                }""")
                return results
            finally:
                try:
                    context.storage_state(path=self.state_file)
                    format_state_file(self.state_file)
                except Exception:
                    pass
                context.close()

    def get_chapters(self, url):
        """Acessa a página principal do mangá e extrai a lista completa de capítulos"""
        logging.info(f"[*] Preparando extração de capítulos para: {url}")

        with sync_playwright() as p:
            context, page = self._launch_browser(p)

            try:
                logging.info("[*] Acessando a página...")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                except Exception as e:
                    logging.error(f"[-] Erro ao carregar página: {e}")

                # Lógica Anti-Cloudflare (Modularizado)
                handle_cloudflare(page, context, self.state_file)

                # Extração de Capítulos (Modularizado)
                expand_chapters_list(page)

                # Avalia o DOM para extrair as propriedades exatas usando o payload importado
                manga_info = page.evaluate(JS_EXTRACT_MANGA)

                # Mescla tudo em um objeto raiz do mesmo jeitinho que o Kotatsu espera
                final_output = manga_info["details"]
                final_output["url"] = url.replace("https://sakuramangas.org", "")
                final_output["chapters"] = manga_info["chapters"]

                return final_output

            except Exception as e:
                logging.error(f"[-] Erro extraindo manga: {e}")
                return None
            finally:
                try:
                    context.storage_state(path=self.state_file)
                    format_state_file(self.state_file)
                except Exception:
                    pass
                context.close()

    def download_cover(self, url, output_path):
        """Baixa a capa usando o Playwright para aproveitar os cookies do Cloudflare."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            context, page = self._launch_browser(p)
            try:
                response = page.goto(url, timeout=30000)
                if response and response.status == 200:
                    with open(output_path, "wb") as f:
                        f.write(response.body())
                    logging.info("[+] Capa (cover.jpg) baixada com sucesso!")
            except Exception as e:
                logging.error(f"[-] Falha ao baixar a capa: {e}")
            finally:
                context.close()
