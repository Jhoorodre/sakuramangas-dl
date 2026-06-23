import os

from src.core.scraper import SakuraScraper


from src.core.manga_manager import MangaManager


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    banner = """
    Sakura Mangas Downloader
    Criado por Jhoorodre
    https://github.com/Jhoorodre/sakuramangas-dl/
    """
    print(banner)


def download_chapters(headless=True):
    clear_screen()
    print("=== Baixar Capítulos Específicos ===")

    toml_links = MangaManager.read_toml_links()
    if toml_links:
        print("Mangás cadastrados no mapping.toml:")
        for i, url in enumerate(toml_links, 1):
            name = url.strip("/").split("/")[-1].replace("-", " ").title()
            print(f"[{i}] {name}")

    print(
        "\nDigite o número do mangá acima, ou digite o NOME de um mangá para pesquisar online:"
    )
    print("Cole o link direto do mangá se preferir. (Pressione Enter para cancelar)")

    escolha = input("> ").strip()
    if not escolha:
        return

    scraper = SakuraScraper(headless=headless)
    links = []

    if escolha.isdigit() and 1 <= int(escolha) <= len(toml_links):
        links = [toml_links[int(escolha) - 1]]
    elif escolha.startswith("http"):
        links = [escolha]
    else:
        print(f"\n[*] Pesquisando '{escolha}' no SakuraMangas...")
        resultados = scraper.search_manga(escolha)
        if not resultados:
            print("[-] Nenhum mangá encontrado com esse nome.")
            input("Pressione Enter para continuar...")
            return

        print("\n=== Resultados da Pesquisa ===")
        for i, res in enumerate(resultados, 1):
            print(f"[{i}] {res['title']}")

        idx = input(
            "\nDigite o número correspondente (ou Enter para cancelar): "
        ).strip()
        if not idx.isdigit() or not (1 <= int(idx) <= len(resultados)):
            print("Operação cancelada.")
            return
        links = [resultados[int(idx) - 1]["url"]]

    for manga_url in links:
        print(f"\n[*] Identificando Obra: {manga_url}")
        try:
            manga_data = scraper.get_chapters(manga_url)
            if not manga_data or "chapters" not in manga_data:
                print("[-] Falha ao obter a lista de capítulos.")
                continue

            manga_title = manga_data.get("title", "Desconhecido")
            chapters_dict = manga_data.get("chapters", {})
            scanlator = MangaManager.get_majority_scanlator(chapters_dict)

            manga_folder = MangaManager.format_manga_folder(manga_title, scanlator)
            manga_base_dir = os.path.join(MangaManager.DOWNLOAD_DIR, manga_folder)
            data_dir = MangaManager.DATA_DIR
            os.makedirs(data_dir, exist_ok=True)

            json_path_data = MangaManager.save_manga_data(manga_data, chapters_dict)

            if manga_data.get("cover"):
                cover_path = os.path.join(manga_base_dir, "cover.jpg")
                if not os.path.exists(cover_path):
                    scraper.download_cover(manga_data["cover"], cover_path)

            print(f"\n[+] Obra: {manga_title} ({len(chapters_dict)} capítulos)")
            print("Quais capítulos você quer baixar? (Ex: 1, 2, 5-10, 19.2)")
            print("Deixe em branco para pular esta obra.")
            selection = input("> ").strip()

            if not selection:
                print("[*] Pulando...")
                continue

            specifics, ranges = MangaManager.parse_chapter_selection(selection)
            overwrite_all = False

            primary_caps = MangaManager.get_primary_chapters(chapters_dict)

            for cap_id, cap in reversed(list(chapters_dict.items())):
                if cap_id not in primary_caps:
                    cap["downloaded"] = False
                    continue

                raw_name = cap.get("name", "Cap 00")
                chap_num = MangaManager.get_chap_num_from_name(raw_name)

                if MangaManager.is_chapter_selected(chap_num, specifics, ranges):
                    url = cap.get("url")
                    if not url.startswith("http"):
                        url = "https://sakuramangas.org" + url

                    chapter_folder = MangaManager.format_chapter_folder(raw_name)
                    chapter_path = os.path.join(
                        MangaManager.DOWNLOAD_DIR, manga_folder, chapter_folder
                    )
                    is_physically_downloaded = MangaManager.is_physically_downloaded(
                        chapter_path
                    )

                    do_download = True
                    if is_physically_downloaded:
                        if overwrite_all:
                            ans = "s"
                        else:
                            print(f"\n[?] O {chapter_folder} já existe no HD.")
                            ans = (
                                input(
                                    "Deseja SOBRESCREVER? (S=Sim / N=Não / T=Sim para Todos): "
                                )
                                .strip()
                                .lower()
                            )
                            if ans == "t":
                                overwrite_all = True
                                ans = "s"

                        if ans != "s":
                            print("  -> [PULO] Mantendo o capítulo original.")
                            cap["downloaded"] = True
                            do_download = False
                        else:
                            import shutil

                            shutil.rmtree(chapter_path, ignore_errors=True)
                            print("  -> Apagando versão antiga...")
                    else:
                        if cap.get("downloaded"):
                            print(
                                f"\n[?] O {chapter_folder} consta no JSON como BAIXADO, mas sumiu da pasta."
                            )
                            ans = (
                                input(
                                    "Deseja baixar novamente para esta pasta? (S/N): "
                                )
                                .strip()
                                .lower()
                            )
                            if ans != "s":
                                print("  -> [PULO] Ignorando re-download.")
                                cap["downloaded"] = True
                                do_download = False

                    if do_download:
                        print(
                            f"  -> Baixando: {chapter_folder} na pasta {manga_folder}"
                        )
                        if scraper.download_chapter(
                            url, manga_name=manga_folder, chapter_name=chapter_folder
                        ):
                            cap["downloaded"] = True

            MangaManager.update_latest_downloaded(manga_data, json_path_data)

        except Exception as e:
            print(f"[-] Erro na operação com {manga_url}: {e}")

    input("\nProcesso concluído. Pressione Enter para voltar ao menu...")


def download_complete_manga(headless=True):
    clear_screen()
    print("=== Baixar Mangá Completo (Ponta-a-Ponta) ===")

    toml_links = MangaManager.read_toml_links()
    if toml_links:
        print("Mangás cadastrados no mapping.toml:")
        print("[0] TODOS OS MANGÁS (Sincronização em Massa)")
        for i, url in enumerate(toml_links, 1):
            name = url.strip("/").split("/")[-1].replace("-", " ").title()
            print(f"[{i}] {name}")

    print(
        "\nDigite o número do mangá (ex: 1), '0' para todos, ou cole links separados por vírgula:"
    )
    escolha = input("> ").strip()
    if not escolha:
        return

    links = []
    if escolha == "0" and toml_links:
        links = toml_links
    elif escolha.endswith(".toml"):
        links = MangaManager.read_toml_links(escolha)
    else:
        # Processa cada item separado por vírgula
        parts = [p.strip() for p in escolha.split(",") if p.strip()]
        for part in parts:
            if part.isdigit():
                idx = int(part)
                if 1 <= idx <= len(toml_links):
                    link = toml_links[idx - 1]
                    if link not in links:
                        links.append(link)
                else:
                    print(f"[-] O número {idx} não existe na lista. Ignorado.")
            else:
                if part not in links:
                    links.append(part)

    scraper = SakuraScraper(headless=headless)

    print("\n🚀 Iniciando Sincronização Ponta-a-Ponta...")
    for link in links:
        print("\n==========================================")
        print(f"[*] Processando Obra: {link}")
        try:
            manga_data = scraper.get_chapters(link)
            if not manga_data or "chapters" not in manga_data:
                print(f"[-] Falha ao obter dados para {link}.")
                continue

            json_path = MangaManager.save_manga_data(manga_data, manga_data["chapters"])
            unique_chaps = len(
                set(c.get("number", 0) for c in manga_data["chapters"].values())
            )
            print(
                f"[+] Lista salva em {json_path}! Encontrados {unique_chaps} capítulos únicos."
            )

            # Baixar imediatamente após gerar o metadado
            manga_title = manga_data.get("title", "Desconhecido")
            chapters_dict = manga_data.get("chapters", {})
            scanlator = MangaManager.get_majority_scanlator(chapters_dict)
            manga_folder = MangaManager.format_manga_folder(manga_title, scanlator)
            manga_base_dir = os.path.join(MangaManager.DOWNLOAD_DIR, manga_folder)

            if manga_data.get("cover"):
                cover_path = os.path.join(manga_base_dir, "cover.jpg")
                if not os.path.exists(cover_path):
                    os.makedirs(manga_base_dir, exist_ok=True)
                    scraper.download_cover(manga_data["cover"], cover_path)

            print(f"[*] Iniciando download dos capítulos de {manga_folder}...")

            primary_caps = MangaManager.get_primary_chapters(chapters_dict)

            for cap_id, cap in reversed(list(chapters_dict.items())):
                if cap_id not in primary_caps:
                    cap["downloaded"] = False
                    continue

                url = cap.get("url")
                if url:
                    if not url.startswith("http"):
                        url = "https://sakuramangas.org" + url

                    raw_name = cap.get("name", "Cap 00")
                    chapter_folder = MangaManager.format_chapter_folder(raw_name)
                    chapter_path = os.path.join(
                        MangaManager.DOWNLOAD_DIR, manga_folder, chapter_folder
                    )

                    if MangaManager.is_physically_downloaded(chapter_path):
                        print(
                            f"  -> [PULO] Capítulo já existente no HD: {chapter_folder}"
                        )
                        cap["downloaded"] = True
                    elif cap.get("downloaded"):
                        print(
                            f"  -> [MEMÓRIA] {chapter_folder} sumiu do HD, JSON diz que baixou. Pulando..."
                        )
                    else:
                        print(
                            f"  -> Baixando Inédito: {chapter_folder} na pasta {manga_folder}"
                        )
                        if scraper.download_chapter(
                            url, manga_name=manga_folder, chapter_name=chapter_folder
                        ):
                            cap["downloaded"] = True

            MangaManager.update_latest_downloaded(manga_data, json_path)
            print(f"[+] Obra {manga_folder} finalizada com sucesso!")

        except Exception as e:
            print(f"[-] Erro inesperado ao processar {link}: {e}")

    input("\nProcesso concluído. Pressione Enter para voltar ao menu...")


def sync_metadata_only(headless=True):
    clear_screen()
    print("=== Sincronizar Apenas Metadados (Atualizar JSONs) ===")

    toml_links = MangaManager.read_toml_links()
    if toml_links:
        print("Mangás cadastrados no mapping.toml:")
        print("[0] TODOS OS MANGÁS (Sincronização em Massa)")
        for i, url in enumerate(toml_links, 1):
            name = url.strip("/").split("/")[-1].replace("-", " ").title()
            print(f"[{i}] {name}")

    print(
        "\nDigite o número do mangá (ex: 1), '0' para todos, ou cole links separados por vírgula:"
    )
    escolha = input("> ").strip()
    if not escolha:
        return

    links = []
    if escolha == "0" and toml_links:
        links = toml_links
    elif escolha.endswith(".toml"):
        links = MangaManager.read_toml_links(escolha)
    else:
        parts = [p.strip() for p in escolha.split(",") if p.strip()]
        for part in parts:
            if part.isdigit():
                idx = int(part)
                if 1 <= idx <= len(toml_links):
                    link = toml_links[idx - 1]
                    if link not in links:
                        links.append(link)
                else:
                    print(f"[-] O número {idx} não existe na lista. Ignorado.")
            else:
                if part not in links:
                    links.append(part)

    scraper = SakuraScraper(headless=headless)

    for link in links:
        print(f"\n[*] Extraindo lista de capítulos para: {link}")
        try:
            manga_data = scraper.get_chapters(link)
            if manga_data and "chapters" in manga_data:
                json_path = MangaManager.save_manga_data(
                    manga_data, manga_data["chapters"]
                )

                # Sincroniza o status 'downloaded' verificando o Disco Rígido
                manga_title = manga_data.get("title", "Desconhecido")
                scanlator = MangaManager.get_majority_scanlator(manga_data["chapters"])
                manga_folder = MangaManager.format_manga_folder(manga_title, scanlator)

                has_updates = False
                for cap_id, cap in manga_data["chapters"].items():
                    if not cap.get("downloaded"):
                        raw_name = cap.get("name", "Cap 00")
                        chapter_folder = MangaManager.format_chapter_folder(raw_name)
                        chapter_path = os.path.join(
                            MangaManager.DOWNLOAD_DIR, manga_folder, chapter_folder
                        )
                        if MangaManager.is_physically_downloaded(chapter_path):
                            cap["downloaded"] = True
                            has_updates = True

                if has_updates:
                    MangaManager.update_latest_downloaded(manga_data, json_path)

                unique_chaps = len(
                    set(c.get("number", 0) for c in manga_data["chapters"].values())
                )
                print(
                    f"[+] Lista salva em {json_path}! Encontrados {unique_chaps} capítulos ({len(manga_data['chapters'])} links com traduções)."
                )
            else:
                print(f"[-] Falha ao obter dados para {link}.")
        except Exception as e:
            print(f"[-] Erro inesperado ao processar {link}: {e}")

    input("\nProcesso concluído. Pressione Enter para voltar ao menu...")


def add_urls_interactively():
    clear_screen()
    print("=== Adicionar URLs em Lote ao mapping.toml ===")
    print("Cole todas as URLs que deseja adicionar.")
    print("Pode colar milhares de linhas de uma vez.")
    print("Pressione Enter DUAS VEZES seguidas para finalizar.\n")

    urls = []
    while True:
        line = input()
        if not line.strip():
            # Aguarda uma segunda linha em branco para sair (para colar blocos)
            break

        # Pode ser que o usuário cole urls separadas por espaço ou virgula na mesma linha
        # Ou multiplas linhas de uma vez se o terminal suportar multiline paste
        for piece in line.split():
            # Limpa lixo do começo e fim antes de validar
            clean_piece = piece.strip('",[] \n')
            if clean_piece.startswith("http"):
                # Retira a barra final que possa ter sobrado
                clean_url = clean_piece.rstrip("/")
                urls.append(clean_url)

    if urls:
        count = MangaManager.add_urls_to_toml(urls)
        print(f"\n[+] {count} novas URLs foram adicionadas ao mapping.toml!")
    else:
        print("\n[-] Nenhuma URL válida foi fornecida.")

    input("\nPressione Enter para voltar ao menu...")


def main_menu(headless=True):
    while True:
        clear_screen()
        print_banner()
        print("Menu Principal:")
        print("1 - Baixar Capítulo(s) Específico(s)")
        print("2 - Baixar Mangá Completo (Ponta-a-Ponta)")
        print("3 - Sincronizar Apenas Metadados (Atualizar JSONs)")
        print("4 - Adicionar URLs em Lote (mapping.toml)")
        print("5 - Sair")

        choice = input("\nEscolha uma opção: ").strip()

        if choice == "1":
            download_chapters(headless=headless)
        elif choice == "2":
            download_complete_manga(headless=headless)
        elif choice == "3":
            sync_metadata_only(headless=headless)
        elif choice == "4":
            add_urls_interactively()
        elif choice == "5":
            print("Saindo do Sakura Mangas Downloader...")
            break
        else:
            print("Opção inválida. Por favor, escolha 1, 2, 3, 4 ou 5.")
            input("Pressione Enter para continuar...")
