import os
import json
import logging
import random
import shutil
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright
from src.core.utils import (
    handle_cloudflare,
    activate_scroll_mode,
    expand_chapters_list,
    JS_EXTRACT_MANGA,
    format_state_file,
)
from src.core.anti_ban import (
    get_governor,
    get_breaker,
    assess_page,
    BlockType,
    BlockedError,
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

    _VIEWPORTS = [
        {"width": 1366, "height": 768},
        {"width": 1920, "height": 1080},
        {"width": 1440, "height": 900},
        {"width": 1536, "height": 864},
        {"width": 1280, "height": 720},
        {"width": 1600, "height": 900},
    ]

    def _launch_browser(self, p, headless=None):
        """Lança um contexto persistente que salva Cache no disco, emulando um Chrome humano."""
        if headless is None:
            headless = self.headless

        data_dir = os.environ.get("DATA_DIR", "data")
        user_data_dir = os.path.join(data_dir, "browser_cache")
        os.makedirs(user_data_dir, exist_ok=True)

        chrome_ver = str(random.randint(120, 131))
        viewport = random.choice(self._VIEWPORTS)
        ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_ver}.0.0.0 Safari/537.36"

        args = [
            "--disable-blink-features=AutomationControlled",
            f"--window-size={viewport['width']},{viewport['height']}",
        ]

        proxy_server = os.environ.get("PROXY_SERVER", "")
        proxy = None
        if proxy_server:
            proxy = {"server": proxy_server}
            if os.environ.get("PROXY_USERNAME"):
                proxy["username"] = os.environ["PROXY_USERNAME"]
            if os.environ.get("PROXY_PASSWORD"):
                proxy["password"] = os.environ["PROXY_PASSWORD"]

        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            args=args,
            user_agent=ua,
            viewport=viewport,
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            proxy=proxy,
        )

        if os.path.exists(self.state_file):
            try:
                with open(self.state_file) as f:
                    state = json.load(f)
                if state.get("cookies"):
                    context.add_cookies(state["cookies"])
            except Exception:
                pass

        page = context.pages[0] if context.pages else context.new_page()

        try:
            from playwright_stealth import stealth_sync

            stealth_sync(page)
        except ImportError:
            pass

        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Bloqueador de Popups: Mata qualquer aba de propaganda que tentar abrir
        context.on("page", lambda new_page: new_page.close())

        return context, page

    def _connect_lightpanda(self, p, url, interceptor=None):
        """Tenta navegar via Lightpanda Cloud CDP. Levanta exceção se não disponível ou bloqueado."""
        token = os.environ.get("LIGHTPANDA_TOKEN", "")
        if not token:
            raise RuntimeError("LIGHTPANDA_TOKEN não definido")

        region = os.environ.get("LIGHTPANDA_REGION", "euwest")
        proxy = os.environ.get("LIGHTPANDA_PROXY", "datacenter")
        country = os.environ.get("LIGHTPANDA_COUNTRY", "br")
        cdp_ws = f"wss://{region}.cloud.lightpanda.io/ws?token={token}&browser=chrome&proxy={proxy}&country={country}"

        browser = p.chromium.connect_over_cdp(cdp_ws, timeout=30000)
        context = None
        try:
            storage = None
            if os.path.exists(self.state_file):
                try:
                    with open(self.state_file) as f:
                        storage = json.load(f)
                except Exception:
                    pass

            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
                storage_state=storage,
            )
            # ponytail: fecha o browser CDP quando o caller fechar o context
            context.on("close", lambda: browser.close())

            page = context.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            if interceptor:
                page.add_init_script("""(function() {
                    window.__lp = { urls: [], headers: {} };
                    window.fetch = new Proxy(window.fetch, {
                        apply: function(target, thisArg, args) {
                            var url = args[0], opts = args[1];
                            if (typeof url === 'string' && url.indexOf('/imagens/') !== -1 && url.endsWith('.jpg')) {
                                if (window.__lp.urls.indexOf(url) === -1) window.__lp.urls.push(url);
                                if (opts && opts.headers) {
                                    var h = opts.headers;
                                    if (typeof Headers !== 'undefined' && h instanceof Headers) {
                                        var tmp = {}; h.forEach(function(v,k){ tmp[k]=v; }); h = tmp;
                                    }
                                    Object.keys(h).forEach(function(k) {
                                        var kl = k.toLowerCase();
                                        if (kl.startsWith('x-') && kl !== 'x-requested-with' && kl !== 'x-forwarded-for')
                                            window.__lp.headers[k] = h[k];
                                    });
                                }
                            }
                            return Reflect.apply(target, thisArg, args);
                        }
                    });
                })();""")
            if interceptor:
                page.on("response", interceptor.handle_response)

            get_governor().wait_turn("navegar (lightpanda)")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                raise RuntimeError(f"Falha ao navegar com Lightpanda: {e}") from e
            if "/manutencao/" in page.url or "block.php" in page.url:
                raise RuntimeError(f"Site bloqueou acesso (redirect para {page.url})")
            try:
                body_text = (
                    page.evaluate("() => document.body ? document.body.innerText : ''")
                    or ""
                )
                if "conflito entre" in body_text.lower():
                    raise RuntimeError(
                        "Lightpanda bloqueado: Conflito entre códigos detectado"
                    )
            except RuntimeError:
                raise
            except Exception:
                pass
            cf_status = handle_cloudflare(
                page, context, self.state_file, is_headless=True
            )
        except Exception:
            try:
                context.close() if context else browser.close()
            except Exception:
                pass
            raise

        if cf_status == "NEEDS_HEADFUL":
            context.close()
            raise RuntimeError("Lightpanda bloqueado pelo Cloudflare")

        return context, page

    def _navigate_with_cf_bypass(self, p, url, interceptor=None):
        """Acessa a URL via Lightpanda (primário) ou browser local (fallback)."""
        token = os.environ.get("LIGHTPANDA_TOKEN", "")
        if token:
            lp_retries = int(os.environ.get("LIGHTPANDA_RETRIES", "3"))
            for attempt in range(1, lp_retries + 1):
                try:
                    logging.info(
                        f"[PIPELINE] Tentando Lightpanda Cloud (tentativa {attempt}/{lp_retries})..."
                    )
                    return self._connect_lightpanda(p, url, interceptor)
                except Exception as e:
                    logging.warning(
                        f"[PIPELINE] Lightpanda tentativa {attempt} falhou: {e}."
                    )
                    if attempt < lp_retries:
                        logging.info(
                            "[PIPELINE] Trocando IP via nova sessão Lightpanda..."
                        )
            logging.warning(
                "[PIPELINE] Todas as tentativas Lightpanda falharam. Usando fallback local."
            )

        current_headless = self.headless
        context, page = self._launch_browser(p, headless=current_headless)

        if interceptor:
            page.on("response", interceptor.handle_response)

        get_governor().wait_turn("navegar")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            logging.error(f"[PIPELINE] Erro ao carregar página: {e}")

        # Detecção precoce de bloqueio de firewall (1020/1015): reabrir o
        # navegador não ajuda quando o IP está banido — abre o circuito e aborta.
        block = assess_page(page)
        if block in (BlockType.BLOCKED, BlockType.RATE_LIMITED, BlockType.MAINTENANCE):
            get_breaker().trip(f"WAF {block} ao navegar")
            try:
                context.close()
            except Exception:
                pass
            raise BlockedError(f"Cloudflare {block}")

        cf_status = handle_cloudflare(
            page, context, self.state_file, is_headless=current_headless
        )

        if cf_status == "NEEDS_HEADFUL":
            logging.info("======================================")
            logging.info("🛡️  SISTEMA DE DEFESA ATIVADO!")
            logging.info("☁️  O Cloudflare nos barrou por estarmos 'invisíveis'.")
            logging.info(
                "👁️  Reabrindo o navegador com interface gráfica para passar pelo bloqueio..."
            )
            logging.info("======================================")
            try:
                context.close()
            except Exception:
                pass

            # Reabre headful real
            current_headless = False
            context, page = self._launch_browser(p, headless=current_headless)
            if interceptor:
                page.on("response", interceptor.handle_response)

            get_governor().wait_turn("reabrir headful")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception:
                pass

            block = assess_page(page)
            if block in (
                BlockType.BLOCKED,
                BlockType.RATE_LIMITED,
                BlockType.MAINTENANCE,
            ):
                get_breaker().trip(f"WAF {block} no headful")
                try:
                    context.close()
                except Exception:
                    pass
                raise BlockedError(f"Cloudflare {block}")

            handle_cloudflare(
                page, context, self.state_file, is_headless=current_headless
            )
            logging.info(
                "[PIPELINE] Salvando os cookies novos. A próxima tentativa poderá voltar a ser invisível!"
            )
            # Cooldown pós-bypass: evita acionar dois bypasses headful em sequência rápida,
            # que é o padrão que dispara ban de IP no Cloudflare.
            cooldown = random.randint(20000, 35000)
            logging.info(
                f"[PIPELINE] Cooldown anti-ban: aguardando {cooldown // 1000}s antes de continuar..."
            )
            page.wait_for_timeout(cooldown)

        return context, page

    def download_chapter(
        self,
        url,
        manga_name=None,
        chapter_name=None,
        output_base_dir="download",
        expected_pages=None,
        on_total_detected=None,
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
        local_count = len(arquivos_prontos)
        skip_existing = False

        if local_count > 0:
            if not expected_pages or local_count == expected_pages:
                logging.info(
                    f"[PIPELINE] PULO INTELIGENTE: {local_count} páginas verificadas. Ignorando: {chapter_name}"
                )
                return local_count
            elif local_count > expected_pages:
                logging.info(
                    f"[PIPELINE] REBUILD: {local_count} págs locais > {expected_pages} esperadas. Limpando pasta..."
                )
                shutil.rmtree(output_dir)
                os.makedirs(output_dir, exist_ok=True)
            else:
                logging.info(
                    f"[PIPELINE] RECUPERAÇÃO: {local_count}/{expected_pages} págs. Preservando existentes e baixando as faltantes..."
                )
                skip_existing = True

        # Disjuntor: se um bloqueio 1020 já abriu o circuito, nem abre o navegador.
        breaker = get_breaker()
        if breaker.is_open():
            logging.error(
                f"[ANTI-BAN] Circuito aberto — pulando capítulo. "
                f"Faltam {breaker.remaining() / 60:.0f} min de cooldown."
            )
            return 0

        logging.info(
            f"[PIPELINE] Preparando ambiente. Modo Headless Base: {self.headless}"
        )
        logging.info(f"[PIPELINE] Pasta de destino: {output_dir}")

        with sync_playwright() as p:
            interceptor = ImageInterceptor(output_dir, skip_existing=skip_existing)
            logging.info("[PIPELINE] Acessando SakuraMangas...")

            try:
                context, page = self._navigate_with_cf_bypass(
                    p, url, interceptor=interceptor
                )
            except BlockedError as e:
                logging.error(
                    f"[ANTI-BAN] Bloqueio do Cloudflare ao acessar o capítulo: {e}. "
                    "Interrompendo (circuito aberto)."
                )
                return 0

            logging.info("[PIPELINE] Aguardando primeiras imagens carregarem...")
            try:
                for _ in range(100):
                    page.wait_for_timeout(100)
                    if interceptor.ordered_urls:
                        break
                page.wait_for_timeout(1000)
            except Exception as _e:
                _msg = str(_e).lower()
                if any(
                    k in _msg for k in ("closed", "target", "disconnect", "session")
                ):
                    logging.warning(
                        f"[PIPELINE] Sessão encerrada durante espera inicial: {_e}"
                    )
                    return 0
                raise

            activate_scroll_mode(page)

            if not expected_pages:
                for _attempt in range(10):
                    try:
                        counter_text = page.locator(
                            "#scroll-page-counter"
                        ).text_content(timeout=3000)
                        dom_total = int(counter_text.split("/")[-1].strip())
                        if dom_total > 0:
                            expected_pages = dom_total
                            logging.info(
                                f"[PIPELINE] Total detectado via DOM: {expected_pages} páginas"
                            )
                            if on_total_detected:
                                on_total_detected(expected_pages)
                            break
                    except Exception:
                        pass
                    if _attempt < 9:
                        page.wait_for_timeout(1000)

                if expected_pages is None:
                    logging.error(
                        "[PIPELINE] Não foi possível ler #scroll-page-counter. Abortando capítulo."
                    )
                    try:
                        context.close()
                    except Exception:
                        pass
                    return 0

            logging.info(
                "[PIPELINE] Acionando Scroll Brutal e Next Page para provocar Lazy Load..."
            )
            timeout = 60
            last_len = -1
            stable_count = 0
            forced_continuations = 0

            _session_closed = False
            try:
                while timeout > 0:
                    if "/manutencao/" in page.url or "block.php" in page.url:
                        logging.warning(
                            "[PIPELINE] Site bloqueou durante scroll. Abortando."
                        )
                        break
                    if timeout % 5 == 0:
                        try:
                            blocked = page.evaluate(
                                "() => document.body ? document.body.innerText.includes('atividade incomum') : false"
                            )
                            if blocked:
                                logging.warning(
                                    "[PIPELINE] Site detectou atividade incomum. Abortando scroll."
                                )
                                break
                        except Exception:
                            pass
                    current_len = len(interceptor.downloaded_files)

                    if expected_pages and current_len >= expected_pages:
                        logging.info(
                            f"[PIPELINE] Todas as {expected_pages} imagens capturadas! Encerrando scroll."
                        )
                        break

                    # Distribuição humana de scroll: maioria lendo (curto), às vezes pulando (longo)
                    r = random.random()
                    if r < 0.60:
                        scroll_dist = random.randint(350, 850)  # ritmo de leitura
                    elif r < 0.90:
                        scroll_dist = random.randint(850, 1600)  # folhear rápido
                    else:
                        scroll_dist = random.randint(1600, 2600)  # pulo grande
                    page.mouse.wheel(0, scroll_dist)

                    # Pausa bimodal: olhada rápida vs lendo a página com calma
                    if random.random() < 0.30:
                        page.wait_for_timeout(random.randint(400, 900))
                    else:
                        page.wait_for_timeout(random.randint(1000, 2500))

                    if random.random() < 0.10:
                        logging.info(
                            "  -> [STEALTH] Simulando leitura atenta (pausa dramática na página)..."
                        )
                        page.wait_for_timeout(random.randint(4000, 8000))

                    # ponytail: back-scroll desativado durante recovery — windowed renderers removem DOM nodes ao subir
                    if random.random() < 0.15 and forced_continuations == 0:
                        logging.info(
                            "  -> [STEALTH] Rolou muito rápido! Subindo a tela para reler..."
                        )
                        page.mouse.wheel(0, random.randint(-600, -200))
                        page.wait_for_timeout(random.randint(600, 1400))

                    # Mouse move restrito à coluna de leitura central (não voa para cantos)
                    if random.random() < 0.12:
                        page.mouse.move(
                            random.randint(300, 750),
                            random.randint(200, 600),
                            steps=random.randint(5, 15),
                        )
                        page.wait_for_timeout(random.randint(100, 300))

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
                                if (
                                    expected_pages
                                    and len(interceptor.ordered_urls) < expected_pages
                                    and forced_continuations < 8
                                ):
                                    forced_continuations += 1
                                    logging.info(
                                        f"[PIPELINE] {len(interceptor.ordered_urls)}/{expected_pages} URLs. Forçando scroll agressivo ({forced_continuations}/8)..."
                                    )
                                    page.mouse.wheel(0, random.randint(3000, 6000))
                                    page.evaluate(
                                        "window.scrollTo(0, document.body.scrollHeight)"
                                    )
                                    page.wait_for_timeout(random.randint(2000, 4000))
                                    stable_count = 0
                                    continue
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
                    if (
                        timeout == 0
                        and expected_pages
                        and len(interceptor.ordered_urls) < expected_pages
                        and forced_continuations < 8
                    ):
                        forced_continuations += 1
                        timeout = 15
                        logging.info(
                            f"[PIPELINE] Timeout com {len(interceptor.ordered_urls)}/{expected_pages} URLs. Estendendo scroll ({forced_continuations}/8)..."
                        )
                        page.mouse.wheel(0, random.randint(3000, 6000))
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(random.randint(2000, 4000))
                        stable_count = 0
                    if timeout % 10 == 0 and timeout > 0:
                        logging.info(f"[PIPELINE] Coletadas até agora: {current_len}")
            except Exception as _scroll_err:
                _msg = str(_scroll_err).lower()
                if any(
                    k in _msg for k in ("closed", "target", "disconnect", "session")
                ):
                    logging.warning(
                        f"[PIPELINE] Sessão remota encerrada durante scroll: {_scroll_err}"
                    )
                    _session_closed = True
                else:
                    raise

            # Resgate Passivo via JS Fetch Blob
            interceptor.sync_from_lp_patcher(page)
            interceptor.rescue_missing_images_via_js(page)

            # Plano C: reloads — o site entrega lazy-load em lotes, cada F5 desbloqueia o próximo.
            # Cada reload é uma navegação nova, então é um vetor de ban: fica limitado
            # (AB_MAX_RELOADS, padrão 2), governado pelo token bucket e interrompido ao
            # primeiro sinal de bloqueio. O smart-resume recupera o resto na próxima execução.
            try:
                _max_reloads = int(os.environ.get("AB_MAX_RELOADS", "2"))
            except (ValueError, TypeError):
                _max_reloads = 2
            reload_range = range(1, _max_reloads + 1) if not _session_closed else []
            for reload_num in reload_range:
                if get_breaker().is_open():
                    logging.error(
                        "[ANTI-BAN] Circuito aberto durante os reloads. Interrompendo."
                    )
                    break
                faltantes = interceptor.get_missing_urls()
                needs_reload = bool(faltantes) or (
                    expected_pages and len(interceptor.ordered_urls) < expected_pages
                )
                if not needs_reload:
                    break
                motivo = (
                    f"{len(faltantes)} faltantes"
                    if faltantes
                    else f"lazy-load incompleto ({len(interceptor.ordered_urls)}/{expected_pages})"
                )
                logging.warning(
                    f"\n[PIPELINE] {motivo}. Acionando PLANO C: Reload {reload_num}/5..."
                )
                try:
                    get_governor().wait_turn("reload")
                    page.reload(wait_until="domcontentloaded", timeout=60000)
                    block = assess_page(page)
                    if block in (
                        BlockType.BLOCKED,
                        BlockType.RATE_LIMITED,
                        BlockType.MAINTENANCE,
                    ):
                        get_breaker().trip(f"WAF {block} durante reload")
                        logging.error(
                            "[ANTI-BAN] Bloqueio detectado no reload. Interrompendo."
                        )
                        break
                    wait_secs = (
                        random.randint(45, 60)
                        if reload_num == 1
                        else random.randint(30, 45)
                    )
                    logging.info(
                        f"[PIPELINE] F5 #{reload_num} concluído. Aguardando {wait_secs}s..."
                    )
                    page.wait_for_timeout(wait_secs * 1000)

                    activate_scroll_mode(page)

                    logging.info(
                        "[PIPELINE] Fazendo varredura completa da página após F5..."
                    )
                    for _ in range(120):
                        page.mouse.wheel(0, random.randint(1800, 2800))
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(random.randint(800, 1500))
                        if (
                            expected_pages
                            and len(interceptor.ordered_urls) >= expected_pages
                        ):
                            break
                        is_at_bottom = page.evaluate(
                            "() => window.scrollY + window.innerHeight >= document.body.scrollHeight - 500"
                        )
                        if is_at_bottom:
                            page.wait_for_timeout(2000)

                    interceptor.sync_from_lp_patcher(page)
                    interceptor.rescue_missing_images_via_js(page)
                    logging.info(
                        f"[PIPELINE] Reload #{reload_num}: {len(interceptor.ordered_urls)}/{expected_pages or '?'} URLs encontradas."
                    )
                except Exception as e:
                    logging.error(f"[PIPELINE] Erro no reload #{reload_num}: {e}")

            faltantes_final = interceptor.get_missing_urls()
            if faltantes_final:
                logging.error(
                    f"[PIPELINE] Fim da linha. {len(faltantes_final)} imagens não puderam ser salvas."
                )

            if _session_closed and not expected_pages:
                logging.warning(
                    "[PIPELINE] Sessão encerrada sem total de páginas conhecido. Descartando download incompleto."
                )
                return 0

            interceptor.finalize_and_rename_images()

            # Relatório Final Minimalista
            total_mapped = len(interceptor.ordered_urls)
            total_downloaded = len(interceptor.downloaded_files)
            final_missing = interceptor.get_missing_urls()

            logging.info("")
            logging.info("┌──────────────────────────────────────")

            try:
                context.storage_state(path=self.state_file)
                format_state_file(self.state_file)
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass

            if len(final_missing) > 0:
                logging.info("│ 🔴 RESULTADO: FALHA PARCIAL")
                logging.info(f"│ 📄 Total Mapeado: {total_mapped}")
                logging.info(f"│ ✅ Recuperadas:   {total_downloaded}")
                logging.info(f"│ ❌ Perdidas:      {len(final_missing)}")
                logging.info("└──────────────────────────────────────")
                logging.error(
                    "[!] O capítulo não será marcado como concluído devido a falhas."
                )
                return 0
            else:
                total_on_disk = interceptor.count_all_on_disk()
                if expected_pages and total_on_disk < expected_pages:
                    logging.error(
                        f"│ 🔴 RESULTADO: INCOMPLETO — {total_on_disk}/{expected_pages} páginas no disco. Reagendando."
                    )
                    logging.info("└──────────────────────────────────────")
                    return 0
                logging.info("│ 🟢 RESULTADO: SUCESSO ABSOLUTO")
                logging.info(f"│ 📄 Total Mapeado: {total_mapped}")
                logging.info(f"│ ✅ Total no Disco: {total_on_disk} (100%)")
                logging.info("└──────────────────────────────────────")

                if os.environ.get("SAVE_AS_CBZ", "false").lower() == "true":
                    try:
                        logging.info(
                            "[PIPELINE] Compactando imagens para formato CBZ..."
                        )
                        shutil.make_archive(output_dir, "zip", output_dir)
                        os.rename(f"{output_dir}.zip", f"{output_dir}.cbz")
                        shutil.rmtree(output_dir, ignore_errors=True)
                        logging.info(
                            f"[PIPELINE] Arquivo gerado com sucesso: {chapter_name}.cbz"
                        )
                    except Exception as e:
                        logging.error(f"[PIPELINE] Erro ao criar CBZ: {e}")

                return total_on_disk

    def search_manga(self, query):
        """Pesquisa um mangá pelo nome e retorna uma lista de resultados {title, url}."""
        logging.info(f"[*] Pesquisando por: {query}")
        if get_breaker().is_open():
            logging.error("[ANTI-BAN] Circuito aberto — pesquisa cancelada.")
            return []
        with sync_playwright() as p:
            search_url = f"https://sakuramangas.org/?s={quote_plus(query)}"
            try:
                context, page = self._navigate_with_cf_bypass(p, search_url)
            except BlockedError as e:
                logging.error(f"[ANTI-BAN] Bloqueio na pesquisa: {e}")
                return []

            try:
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

        if get_breaker().is_open():
            logging.error(
                "[ANTI-BAN] Circuito aberto — extração de capítulos cancelada."
            )
            return None

        with sync_playwright() as p:
            try:
                context, page = self._navigate_with_cf_bypass(p, url)
            except BlockedError as e:
                logging.error(f"[ANTI-BAN] Bloqueio ao extrair capítulos: {e}")
                return None

            try:
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
        # Último vetor de navegação: também passa pelo disjuntor + token bucket
        # para não gastar requisição fora do ritmo governado.
        if get_breaker().is_open():
            logging.warning("[ANTI-BAN] Circuito aberto — pulando download da capa.")
            return
        with sync_playwright() as p:
            context, page = self._launch_browser(p)
            try:
                get_governor().wait_turn("baixar capa")
                response = page.goto(url, timeout=30000)
                if response and response.status == 200:
                    with open(output_path, "wb") as f:
                        f.write(response.body())
                    logging.info("[+] Capa (cover.jpg) baixada com sucesso!")
            except Exception as e:
                logging.error(f"[-] Falha ao baixar a capa: {e}")
            finally:
                context.close()
