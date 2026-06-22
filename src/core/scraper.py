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
    is_valid_image,
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
        self.state_file = os.path.join("data", "state_file.json")
        os.makedirs("data", exist_ok=True)

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
        user_data_dir = os.path.join("data", "browser_cache")
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
        if not manga_name or not chapter_name:
            m_name, c_name = self._extract_meta(url)
            manga_name = manga_name or m_name
            chapter_name = chapter_name or c_name

        output_dir = os.path.join(output_base_dir, manga_name, chapter_name)
        os.makedirs(output_dir, exist_ok=True)

        # Verificação de Retrabalho: Se a pasta já tem imagens formatadas (pag_), o capítulo foi concluído no passado!
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

            # Usaremos uma lista para garantir a ordem exata em que as imagens foram solicitadas
            ordered_urls = []
            downloaded_files = {}
            drm_headers = {}  # Armazena chaves DRM dinâmicas interceptadas
            # Variável de controle do Throttle: [min_sec, max_sec]
            throttle_range = [0.8, 1.7]

            # Traffic Controller: Enfileira as imagens para não causar DDoS no Cloudflare.
            def throttle_traffic(route):
                try:
                    # Removemos o time.sleep bloqueante! O rate limit agora é ditado puramente pela física do Scroll Suave
                    route.continue_()
                except Exception:
                    pass

            page.route("**/*", throttle_traffic)

            # Grampo de Rede: Rouba as imagens em tempo real
            def handle_response(response):
                if "/imagens/" in response.url and response.url.endswith(".jpg"):
                    # Escuta Ativa (Sniffer): Captura senhas DRM (x-harry, x-marquinhos, etc.)
                    for key, value in response.request.headers.items():
                        k = key.lower()
                        if k.startswith("x-") and k not in [
                            "x-requested-with",
                            "x-forwarded-for",
                        ]:
                            drm_headers[key] = value

                    if response.url in downloaded_files:
                        return

                    if response.url not in ordered_urls:
                        ordered_urls.append(response.url)

                    # Extrai o nome real temporário (ex: 001.jpg)
                    temp_filename = response.url.split("/")[-1]
                    temp_filepath = os.path.join(output_dir, temp_filename)

                    try:
                        body = response.body()

                        # Se por algum motivo o navegador retornar um buffer vazio, HTML ou HTTP de erro
                        if not is_valid_image(body):
                            logging.warning(
                                f"  -> [!] Imagem {temp_filename} interceptada como HTML/Vazia. Passando para o Pós-Processamento..."
                            )
                            return  # Aborta silenciosamente. O Pós-Processamento vai salvar a pátria.

                        # Validação final de DNA da imagem (Magic Bytes)
                        if is_valid_image(body):
                            with open(temp_filepath, "wb") as f:
                                f.write(body)
                            downloaded_files[response.url] = temp_filepath
                            logging.info(f"  -> [+] Imagem baixada: {temp_filename}")
                        else:
                            logging.error(
                                f"  -> [-] Imagem {temp_filename} irremediavelmente corrompida pela CDN."
                            )
                    except Exception as e:
                        logging.error(f"  -> [-] Falha ao salvar {temp_filename}: {e}")

            page.on("response", handle_response)

            logging.info("[PIPELINE] Acessando SakuraMangas...")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                logging.error(f"[PIPELINE] Erro ao carregar página inicial: {e}")

            # Resolve qualquer Captcha que possa aparecer
            handle_cloudflare(page, context, self.state_file)

            # Tempo de Respiro: O Cloudflare bloqueia as primeiras imagens porque o navegador tenta
            # baixar a 001, 002 e 003 ao mesmo tempo. Se a gente rolar a página imediatamente,
            # ele tenta baixar a 004 e 005 também, gerando um "Mini-DDoS" e bloqueando o IP.
            # Essa pausa de 10 segundos garante que a "onda inicial" passe em paz.
            logging.info(
                "[PIPELINE] Deixando a poeira baixar para as imagens iniciais carregarem em paz (10s)..."
            )
            page.wait_for_timeout(10000)

            # Ativa o modo cascata (Scroll)
            activate_scroll_mode(page)

            logging.info(
                "[PIPELINE] Acionando Scroll Brutal e Next Page para provocar Lazy Load..."
            )
            timeout = 60
            last_len = -1
            stable_count = 0

            while timeout > 0:
                current_len = len(downloaded_files)

                # Comportamento Base: Scroll Descendente Físico (Roda do Mouse real)
                page.mouse.wheel(0, random.randint(800, 1500))
                page.wait_for_timeout(random.randint(800, 1800))

                # HUMANO 1: O Leitor Distraído (10% de chance)
                if random.random() < 0.10:
                    logging.info(
                        "  -> [STEALTH] Simulando leitura atenta (pausa dramática na página)..."
                    )
                    page.wait_for_timeout(random.randint(4000, 8000))

                # HUMANO 2: O Scroll Desastrado (15% de chance)
                if random.random() < 0.15:
                    logging.info(
                        "  -> [STEALTH] Rolou muito rápido! Subindo a tela para reler..."
                    )
                    page.mouse.wheel(0, random.randint(-600, -200))
                    page.wait_for_timeout(random.randint(600, 1400))

                # HUMANO 3: A Mão Cansada (25% de chance)
                if random.random() < 0.25:
                    page.mouse.move(
                        random.randint(50, 1000),
                        random.randint(50, 800),
                        steps=random.randint(8, 25),
                    )
                    page.wait_for_timeout(random.randint(100, 400))

                # Verifica se o rodapé real da SakuraMangas (.footer-text-col) apareceu na tela
                is_bottom = page.evaluate("""() => {
                    const footer = document.querySelector('.footer-text-col');
                    if (footer) {
                        const rect = footer.getBoundingClientRect();
                        return rect.top <= window.innerHeight + 500; // Chegou perto do rodapé
                    }
                    // Fallback matemático caso o layout mude
                    return window.scrollY + window.innerHeight >= document.body.scrollHeight - 200;
                }""")

                if current_len > 0:
                    if current_len == last_len:
                        stable_count += 1
                        # Se chegamos no rodapé, só precisamos de 3 ciclos de confirmação para sair rápido.
                        # Se não chegamos no rodapé, esperamos 15 ciclos como segurança contra carregamento super lento.
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
                    # Se tiver um overlay bloqueando a página, tentamos clicar nele
                    try:
                        page.mouse.click(500, 500)
                    except Exception:
                        pass

                timeout -= 1
                if timeout % 10 == 0:
                    logging.info(f"[PIPELINE] Coletadas até agora: {current_len}")

            # Pós-processamento: Se alguma imagem falhou na interceptação (cache/vazia), usamos JS Fetch nativo do DOM para resgatá-la!
            for u in ordered_urls:
                if u not in downloaded_files:
                    logging.warning(
                        f"  -> [!] Imagem perdida/corrompida detectada. Resfriando conexão e resgatando via JS Blob: {u}"
                    )
                    try:
                        # Espera um tempinho pro DOM estabilizar
                        page.wait_for_timeout(1500)

                        import json

                        headers_json = json.dumps(drm_headers) if drm_headers else "{}"

                        b64 = page.evaluate(f"""async () => {{
                            // TENTATIVA 1: Roubo direto da Memória de Vídeo (Canvas)
                            const img = document.querySelector('img[src*="{u.split("/")[-1]}"]');
                            if (img && img.complete && img.naturalWidth > 0) {{
                                try {{
                                    const canvas = document.createElement("canvas");
                                    canvas.width = img.naturalWidth;
                                    canvas.height = img.naturalHeight;
                                    const ctx = canvas.getContext("2d");
                                    ctx.drawImage(img, 0, 0);
                                    const dataURL = canvas.toDataURL("image/jpeg", 1.0);
                                    if (dataURL.length > 100) return dataURL;
                                }} catch(e) {{ /* Ignora erro de CORS cruzado caso ocorra */ }}
                            }}
                            
                            // TENTATIVA 2: Fetch Nativo Injetando as Senhas DRM Interceptadas
                            try {{
                                const drmHeaders = {headers_json};
                                const res = await fetch("{u}", {{ headers: drmHeaders }});
                                const blob = await res.blob();
                                return new Promise(resolve => {{
                                    const reader = new FileReader();
                                    reader.onloadend = () => resolve(reader.result);
                                    reader.readAsDataURL(blob);
                                }});
                            }} catch(e) {{ return null; }}
                        }}""")

                        if b64 and "base64," in b64:
                            import base64

                            body = base64.b64decode(b64.split("base64,")[1])
                            if is_valid_image(body):
                                temp_filename = u.split("/")[-1]
                                temp_filepath = os.path.join(output_dir, temp_filename)
                                with open(temp_filepath, "wb") as f:
                                    f.write(body)
                                downloaded_files[u] = temp_filepath
                                logging.info(
                                    "  -> [+] Imagem resgatada com sucesso direto da Memória do Navegador!"
                                )
                            else:
                                logging.error(
                                    "  -> [-] Imagem inacessível no momento (Rate Limit Persistente)."
                                )
                    except Exception as e:
                        logging.error(f"  -> [-] Falha na recuperação JS: {e}")

            # Plano C: Reload (F5) caso ainda faltem imagens
            faltantes = [u for u in ordered_urls if u not in downloaded_files]
            if len(faltantes) > 0:
                logging.warning(
                    f"\n[PIPELINE] {len(faltantes)} imagens resistiram ao resgate. Acionando PLANO C: Reload (F5) Extremo!"
                )
                try:
                    # Aumenta agressivamente a distância entre as requisições no F5 para 1.5s - 3.0s
                    throttle_range[0] = 1.5
                    throttle_range[1] = 3.0

                    # Um Hard Reload que ignora o cache da página
                    page.reload(wait_until="networkidle", timeout=60000)

                    logging.info(
                        "[PIPELINE] F5 Concluído. Deixando a poeira baixar novamente (10s)..."
                    )
                    page.wait_for_timeout(10000)

                    # Reativa a Cascata
                    activate_scroll_mode(page)

                    # Desce a página fisicamente garantindo o Lazy Load sem depender de JS injetado
                    logging.info("[PIPELINE] Fazendo uma varredura final na página...")
                    for _ in range(random.randint(4, 7)):
                        page.mouse.wheel(0, random.randint(1200, 1800))
                        page.wait_for_timeout(random.randint(1200, 2000))

                    # Rola absurdamente pra baixo só pra ter certeza que bateu no rodapé
                    page.mouse.wheel(0, random.randint(8000, 12000))
                    page.wait_for_timeout(random.randint(4000, 6000))

                    # Como o interceptador de rede nunca foi desligado, ele pegou as imagens limpas que carregaram no F5.
                    faltantes_final = [
                        u for u in ordered_urls if u not in downloaded_files
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

            # Renomeação Ordenada (pag_001.jpg, pag_002.jpg)
            logging.info(
                "[PIPELINE] Formatando e numerando as imagens no disco (pag_001.jpg)..."
            )
            for index, url in enumerate(ordered_urls):
                if url in downloaded_files:
                    old_path = downloaded_files[url]
                    new_filename = f"pag_{index + 1:03d}.jpg"
                    new_path = os.path.join(output_dir, new_filename)
                    if os.path.exists(old_path):
                        os.rename(old_path, new_path)

            logging.info("======================================")
            logging.info("🎯 DOWNLOAD CONCLUÍDO!")
            logging.info(f"🎯 Total de imagens roubadas: {len(downloaded_files)}")
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
