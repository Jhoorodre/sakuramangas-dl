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


def handle_cloudflare(page, context, state_file, is_headless=False):
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
        if is_headless:
            logging.warning(
                "[PIPELINE] Bloqueio Cloudflare detectado no modo Headless!"
            )
            return "NEEDS_HEADFUL"

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
    return "OK"


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

        # 1. Jornada de descida mecânica e ultra-suave (Alta frequência com Inércia)
        logging.info(
            "  -> [*] Descendo a tela mecanicamente de forma caótica e orgânica..."
        )

        hit_comments = False
        frame_counter = 0
        momentum = 0

        # Simulando um "Event Loop" de alta frequência usando apenas hardware simulado
        for _ in range(800):  # Máximo de 800 "frames" de segurança
            frame_counter += 1

            # --- MOTOR DE INÉRCIA HUMANA ---
            # Um humano não rola constantemente. Ele dá um "impulso" (flick) na rodinha e deixa desacelerar.
            if momentum <= 0 and random.random() < 0.15:
                # Novo impulso forte na rodinha!
                momentum = random.randint(30, 90)

            if momentum > 0:
                # Rola com a força do impulso atual + pequena variação
                speed = momentum + random.randint(-5, 10)
                page.mouse.wheel(0, speed)
                # O atrito natural do dedo desacelera o impulso rápido
                momentum -= random.randint(3, 12)
                page.wait_for_timeout(random.randint(12, 20))
            else:
                # Sem embalo: rola de levinho ou não faz nada (micro-pausas de leitura)
                if random.random() < 0.3:
                    page.mouse.wheel(0, random.randint(5, 25))
                page.wait_for_timeout(random.randint(20, 50))

            # --- PAUSAS ERRÁTICAS ---
            # A cada aprox 50-100 frames, o humano para para ler a tela ou mexer o mouse à toa
            if frame_counter % random.randint(60, 120) == 0:
                logging.debug("  -> [*] Micro-pausa para leitura/descanso...")
                page.wait_for_timeout(random.randint(400, 1500))
                # 50% de chance de vagar o mouse na tela enquanto lê
                if random.random() < 0.5:
                    page.mouse.move(
                        random.randint(100, 800),
                        random.randint(150, 600),
                        steps=random.randint(10, 25),
                    )

            # --- ERROS HUMANOS ---
            if frame_counter % random.randint(20, 40) == 0 and random.random() < 0.2:
                # Puxa pra cima sem querer (Over-scroll)
                page.mouse.wheel(0, random.randint(-60, -20))
                page.wait_for_timeout(random.randint(100, 300))

            # --- CHECAGEM DE BOTÕES (Apenas durante o fim do impulso para não travar o framerate) ---
            if momentum <= 0 and frame_counter % 5 == 0:
                # Olha se o botão de "Ver Mais" apareceu flutuando na tela
                btn = page.query_selector("#ver-mais")
                if btn and btn.is_visible():
                    # Move o mouse acompanhando a descida pra fazer o clique
                    page.mouse.move(
                        random.randint(200, 600),
                        random.randint(200, 500),
                        steps=random.randint(5, 12),
                    )
                    try:
                        # Clique humano hesitante (delay variado no mousedown)
                        btn.click(
                            force=True, timeout=2000, delay=random.randint(40, 150)
                        )
                        logging.info(
                            "  -> [*] Clicou em 'Ver Mais' no embalo da descida!"
                        )

                        # Pausa orgânica de alívio esperando a página renderizar
                        page.wait_for_timeout(random.randint(800, 2000))
                    except Exception:
                        pass

                # A cada parada de impulso avaliamos se chegamos no final verdadeiro (comentários)
                if frame_counter % 15 == 0:
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
            # Freiada mecânica suave no fim, como se estivesse ajustando a visão
            for _ in range(random.randint(3, 7)):
                page.mouse.wheel(0, random.randint(-15, 25))
                page.wait_for_timeout(random.randint(40, 100))

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
    let currentGroupTitle = "Cap. 00";
    
    for (const ch of chList) {
        if (ch.classList.contains('parent')) {
            const titleElem = ch.querySelector('.title-text');
            if (titleElem) {
                currentGroupTitle = titleElem.innerText.trim();
            }
        }
        
        let chUrl = ch.getAttribute('data-url');
        if (!chUrl) {
            const aTag = ch.querySelector('a');
            if (aTag) chUrl = aTag.getAttribute('href');
        }
        
        if (!chUrl) continue;
        
        if (!chUrl.startsWith('http')) {
            chUrl = "https://sakuramangas.org" + chUrl;
        }
        
        let capTitle = "Cap 00";
        const titleElem = ch.querySelector('.title-text');
        
        if (titleElem) {
            capTitle = titleElem.innerText.trim();
        } else if (ch.classList.contains('child')) {
            capTitle = currentGroupTitle;
        }
        
        const subtitleTag = ch.querySelector('.subtitle-text');
        const subtitle = subtitleTag ? subtitleTag.innerText.trim() : '';
        
        let group = 'Morro dos Scans';
        const badgeTag = ch.querySelector('.badge-contributor');
        if (badgeTag) {
            group = badgeTag.getAttribute('data-full-name') || badgeTag.innerText.trim();
        }
        
        let scanSuffix = "";
        if (ch.classList.contains('child') && group) {
            scanSuffix = ` [${group}]`;
        }
        
        let fullName = subtitle ? `${capTitle} - ${subtitle}` : capTitle;
        if (scanSuffix) {
            fullName += scanSuffix;
        }
        
        const capMatch = capTitle.match(/\d+(?:\.\d+)?/);
        const number = capMatch ? parseFloat(capMatch[0]) : 0;
        
        let volume = 0;
        const volSection = ch.closest('.volume-section');
        if (volSection) {
            const volHeader = volSection.querySelector('.volume-header .fw-bold');
            if (volHeader) {
                const volMatch = volHeader.innerText.match(/\d+/);
                if (volMatch) volume = parseInt(volMatch[0]);
            }
        }
        
        const dateTag = ch.querySelector('.bi-clock');
        let dateObj = Date.now();
        if (dateTag && dateTag.nextElementSibling) {
            const timeText = dateTag.nextElementSibling.innerText.toLowerCase();
            const match = timeText.match(/\d+/);
            const amount = match ? parseInt(match[0]) : 1;
            if (timeText.includes('segundo')) dateObj -= amount * 1000;
            else if (timeText.includes('min')) dateObj -= amount * 60000;
            else if (timeText.includes('hora')) dateObj -= amount * 3600000;
            else if (timeText.includes('dia')) dateObj -= amount * 86400000;
            else if (timeText.includes('sem')) dateObj -= amount * 604800000;
            else if (timeText.includes('mês') || timeText.includes('mes')) dateObj -= amount * 2592000000;
            else if (timeText.includes('ano')) dateObj -= amount * 31536000000;
        }
        
        const chapterId = stringHash(chUrl);
        
        chaptersObj[chapterId] = {
            volume: volume,
            number: number,
            entries: "",
            file: "",
            uploadDate: dateObj,
            scanlator: group,
            name: fullName,
            url: chUrl.replace("https://sakuramangas.org", "")
        };
    }
    return { details: mangaDetails, chapters: chaptersObj };
}"""
