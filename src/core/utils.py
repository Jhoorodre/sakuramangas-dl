import logging
import json
import random


def format_state_file(state_file):
    """Lê o state_file e o salva de forma bonita e legível."""
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logging.error(f"[DEBUG] Erro ao formatar JSON: {e}")


def is_valid_image(body):
    """Lê os Magic Bytes do buffer para garantir que é uma imagem real e não um HTML/Erro do Cloudflare."""
    if not body or len(body) < 10:
        return False
    if body.startswith(b"\xff\xd8\xff"):
        return True  # JPEG
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return True  # PNG
    if body.startswith(b"RIFF") and b"WEBP" in body[:16]:
        return True  # WEBP
    if b"ftyp" in body[:16]:
        return True  # HEIC/Video
    if body.startswith(b"GIF8"):
        return True  # GIF
    return False


def handle_cloudflare(page, context, state_file):
    """Verifica e aguarda a resolução do Cloudflare com comportamento humano."""
    page.wait_for_timeout(random.randint(2500, 3500))

    def is_cloudflare():
        try:
            title = page.title().lower()
            if (
                "moment" in title
                or "cloudflare" in title
                or "attention" in title
                or "security" in title
            ):
                return True
            # Verifica se há elementos nativos do Cloudflare na tela
            if page.locator("text='Verificando se você é humano'").count() > 0:
                return True
            if (
                page.locator(
                    "#cf-challenge-running, #challenge-form, iframe[src*='cloudflare'], .cf-browser-verification"
                ).count()
                > 0
            ):
                return True
        except Exception:
            pass
        return False

    if is_cloudflare():
        logging.warning(
            "[PIPELINE] CLOUDFLARE DETECTADO! Tentando bypass orgânico (ou resolva no navegador)..."
        )
        for _ in range(120):  # Espera até 4 minutos
            if not is_cloudflare():
                logging.info("[PIPELINE] Desafio Cloudflare vencido com sucesso!")
                try:
                    context.storage_state(path=state_file)
                    format_state_file(state_file)
                except Exception:
                    pass
                break
            try:
                # Simula movimento de mouse humano cruzando a tela para burlar a biometria
                page.mouse.move(
                    random.randint(100, 800),
                    random.randint(100, 600),
                    steps=random.randint(5, 15),
                )
                page.wait_for_timeout(random.randint(200, 600))
                page.mouse.click(
                    random.randint(100, 800),
                    random.randint(100, 600),
                    delay=random.randint(50, 200),
                )
            except Exception:
                pass
            page.wait_for_timeout(random.randint(850, 2400))

        logging.info("[PIPELINE] Cloudflare ultrapassado ou timeout atingido.")


def activate_scroll_mode(page):
    """Garante que a visualização de leitura esteja em modo cascata (Scroll) com cliques orgânicos."""
    logging.info(
        "[PIPELINE] Aguardando a interface do Leitor (Se houver Captcha manual, digite agora)..."
    )
    try:
        # Congela o script por até 3 minutos (180s) aguardando o site real aparecer, garantindo tempo livre pro usuário agir.
        page.wait_for_selector(
            '.footer-text-col, .toggle-view-mode, .chapter-list, button[title="Modo de Leitura"]',
            timeout=180000,
        )
    except Exception:
        logging.warning(
            "[PIPELINE] O Leitor demorou muito para renderizar (ou o Captcha não foi resolvido a tempo)."
        )

    logging.info("[PIPELINE] Procurando botão de Cascata...")
    try:
        btn_scroll = page.locator("#toggle-view-mode .div-scroll").first
        if btn_scroll.count() > 0:
            for _ in range(
                10
            ):  # Tenta clicar repetidamente para furar bloqueio de anúncios
                classe = btn_scroll.get_attribute("class", timeout=2000) or ""
                if "active" not in classe:
                    try:
                        btn_scroll.click(
                            force=True, timeout=2000, delay=random.randint(100, 300)
                        )
                    except Exception:
                        pass
                    page.wait_for_timeout(random.randint(850, 2400))
                else:
                    logging.info("[PIPELINE] Modo Scroll ativado e verificado!")
                    break
    except Exception:
        pass


def expand_chapters_list(page):
    """Navega na página clicando em 'Ver Mais' durante a descida até os comentários de forma fluida e orgânica."""
    try:
        page.wait_for_selector(".chapter-list", timeout=60000)
        logging.info("[*] Expandindo lista de capítulos de forma orgânica...")

        # Pausa inicial aleatória de 2 a 6 segundos (admirando a página)
        page.wait_for_timeout(random.randint(2000, 6000))

        # 1. Jornada de descida mecânica e ultra-suave (Alta frequência - "60FPS Feel")
        logging.info("  -> [*] Descendo a tela mecanicamente de forma contínua...")

        hit_comments = False
        frame_counter = 0

        # Simulando um "Event Loop" de alta frequência usando apenas hardware simulado
        for _ in range(
            800
        ):  # Máximo de 800 "frames" de segurança para não rodar infinitamente
            frame_counter += 1

            # Gira a roda do mouse em pequenos incrementos (20 a 60 pixels)
            speed = random.randint(20, 60)
            page.mouse.wheel(0, speed)

            # Delay minúsculo (~16ms ideal para 60fps), o Playwright adiciona uns 5-10ms de overhead de rede
            page.wait_for_timeout(random.randint(10, 20))

            # A cada 15 frames (aprox 400ms), paramos para olhar a tela.
            # Não olhamos todo frame para não "engasgar" a rolagem com processamento de DOM.
            if frame_counter % 15 == 0:
                # Imprecisão humana: de vez em quando a pessoa volta a roda sem querer
                if random.random() < 0.2:
                    page.mouse.wheel(0, random.randint(-50, -10))

                # Olha se o botão de "Ver Mais" apareceu flutuando na tela
                btn = page.query_selector("#ver-mais")
                if btn and btn.is_visible():
                    # Move o mouse acompanhando a descida pra fazer o clique
                    page.mouse.move(
                        random.randint(200, 600),
                        random.randint(200, 500),
                        steps=random.randint(5, 10),
                    )
                    try:
                        # Clique rápido "no ar"
                        btn.click(
                            force=True, timeout=2000, delay=random.randint(30, 80)
                        )
                        logging.info(
                            "  -> [*] Clicou em 'Ver Mais' no embalo da descida!"
                        )

                        # Pausa orgânica aguardando as novas divs carregarem (como alguém respirando)
                        page.wait_for_timeout(random.randint(800, 1500))
                    except Exception:
                        pass

                # A cada 30 frames, avaliamos se chegamos no final verdadeiro (comentários)
                if frame_counter % 30 == 0:
                    form_comment = page.query_selector(
                        "#form-comentar, .form-comentario"
                    )
                    if form_comment and form_comment.is_visible():
                        # Confirma se ainda tem botão sobrando pra expandir
                        btn_left = page.query_selector("#ver-mais")
                        if not btn_left or not btn_left.is_visible():
                            logging.info(
                                "  -> [*] Atingiu a seção de comentários fisicamente."
                            )
                            hit_comments = True
                            break

        if hit_comments:
            # Freiada mecânica suave no fim
            for _ in range(5):
                page.mouse.wheel(0, random.randint(10, 20))
                page.wait_for_timeout(30)

        # 2. Comportamento pesado de leitura entre os comentários e o rodapé
        logging.info("  -> [*] Simulando leitura dos comentários (Pausas erráticas)...")
        for _ in range(random.randint(3, 6)):
            # Move o mouse acompanhando o texto imaginário
            page.mouse.move(
                random.randint(100, 800),
                random.randint(300, 700),
                steps=random.randint(10, 30),
            )

            # Pausa longa (Lendo o comentário)
            page.wait_for_timeout(random.randint(2500, 5000))

            # Scroll imperfeito curtinho pra cima ou pra baixo enquanto lê
            page.mouse.wheel(0, random.randint(-150, 300))

        # 3. Desliza até o rodapé para finalizar a presença na página
        try:
            page.evaluate(
                "window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});"
            )
            page.wait_for_timeout(random.randint(1500, 3000))
        except Exception:
            pass

        return True
    except Exception as e:
        logging.error(f"[-] Erro na navegação da obra: {e}")
        return False


# Payload de extração em JavaScript (formato Kotatsu)
JS_EXTRACT_MANGA = """() => {
    function stringHash(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            hash = (hash << 5) - hash + str.charCodeAt(i);
            hash |= 0;
        }
        return hash.toString();
    }

    let mangaDetails = {
        app_version: "0.2",
        nsfw: false,
        rating: -1,
        alt_titles: [],
        source: "SAKURA_MANGAS",
        public_url: window.location.href,
        cover_entry: "cover.jpg",
        app_id: "sakuramangas-dl",
        state: "ONGOING"
    };
    
    try {
        const h1 = document.querySelector('.h1-titulo');
        if (h1) {
            mangaDetails.title = h1.innerText.trim();
            mangaDetails.id = parseInt(stringHash(mangaDetails.title));
        }
        
        const pAutor = document.querySelector('.autor a');
        if (pAutor) {
            const authorText = pAutor.innerText.trim();
            mangaDetails.author = authorText;
            mangaDetails.authors = [authorText];
        }
        
        const pSinopse = document.querySelector('.sinopse');
        if (pSinopse) mangaDetails.description = pSinopse.innerText.trim();
        
        const spanStatus = document.querySelector('#status');
        if (spanStatus) {
            const statusText = spanStatus.innerText.trim().toLowerCase();
            if (statusText.includes("andamento")) mangaDetails.state = "ONGOING";
            else if (statusText.includes("concluído") || statusText.includes("completo")) mangaDetails.state = "COMPLETED";
        }
        
        const divGeneros = document.querySelectorAll('.generos a');
        mangaDetails.tags = [];
        if (divGeneros.length > 0) {
            Array.from(divGeneros).forEach(a => {
                const title = a.innerText.trim();
                mangaDetails.tags.push({
                    title: title,
                    key: title.toLowerCase()
                });
            });
        }
        
        const imgCapa = document.querySelector('.capa');
        if (imgCapa) mangaDetails.cover = imgCapa.src;
    } catch (e) {
        console.error(e);
    }

    const chList = document.querySelectorAll('.chapter-item');
    const chaptersObj = {};
    
    for (const ch of chList) {
        const aTag = ch.querySelector('a.title-text');
        if (!aTag) continue;
        
        let chUrl = aTag.getAttribute('href') || '';
        if (chUrl && !chUrl.startsWith('http')) {
            chUrl = "https://sakuramangas.org" + chUrl;
        }
        
        const capTitle = aTag.innerText.trim();
        const subtitleTag = ch.querySelector('.subtitle-text');
        const subtitle = subtitleTag ? subtitleTag.innerText.trim() : '';
        
        const fullName = subtitle ? `${capTitle} - ${subtitle}` : capTitle;
        
        // Extrai o número do capítulo corretamente ignorando apenas pontos isolados
        const capMatch = capTitle.match(/\d+(?:\.\d+)?/);
        const number = capMatch ? parseFloat(capMatch[0]) : 0;
        
        // Extrai o volume lendo a div pai "volume-section"
        let volume = 0;
        const volSection = ch.closest('.volume-section');
        if (volSection) {
            const volHeader = volSection.querySelector('.volume-header .fw-bold');
            if (volHeader) {
                const volMatch = volHeader.innerText.match(/\d+/);
                if (volMatch) volume = parseInt(volMatch[0]);
            }
        }
        
        let group = 'Morro dos Scans';
        const badgeTag = ch.querySelector('.badge-contributor');
        if (badgeTag) {
            group = badgeTag.getAttribute('data-full-name') || badgeTag.innerText.trim();
        }
        
        const chapterId = stringHash(chUrl);
        
        chaptersObj[chapterId] = {
            volume: volume,
            number: number,
            entries: "",
            file: "",
            uploadDate: Date.now(),
            scanlator: group,
            name: fullName,
            url: aTag.getAttribute('href')
        };
    }
    return { details: mangaDetails, chapters: chaptersObj };
}"""
