import os
import sys
import glob
import json
import re

try:
    import tomllib
except ModuleNotFoundError:
    pass  # Compatibilidade com Python < 3.11

from src.core.scraper import SakuraScraper


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    banner = """
    Sakura Mangas Downloader
    Criado por Etoshy
    https://github.com/etoshy/Sakura-Mangas-Downloader/
    """
    print(banner)


def download_chapters():
    clear_screen()
    print("=== Baixar Capítulos Específicos ===")

    # Pré-carregar o mapping.toml para mostrar o menu
    toml_path = "mapping.toml"
    toml_links = []
    if os.path.exists(toml_path):
        try:
            if "tomllib" in sys.modules:
                with open(toml_path, "rb") as f:
                    data = tomllib.load(f)
                    toml_links = data.get("mangas", {}).get("urls", [])
            else:
                with open(toml_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith('"http'):
                            toml_links.append(line.split('"')[1])
        except Exception:
            pass

    if toml_links:
        print(f"Mangás cadastrados no {toml_path}:")
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

    scraper = SakuraScraper(headless=False)
    links = []

    if escolha.isdigit() and 1 <= int(escolha) <= len(toml_links):
        links = [toml_links[int(escolha) - 1]]
    elif escolha.startswith("http"):
        links = [escolha]
    else:
        # Pesquisa inteligente!
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

            scanlator = ""
            if chapters_dict:
                first_cap = list(chapters_dict.values())[0]
                scanlator = first_cap.get("scanlator", "")

            manga_folder = f"{manga_title} - {scanlator}" if scanlator else manga_title
            manga_folder = re.sub(r'[\\/:*?"<>|]', "", manga_folder)

            # Criar a pasta base da obra
            manga_base_dir = os.path.join("download", manga_folder)
            os.makedirs(manga_base_dir, exist_ok=True)

            # Salvar TAMBÉM na pasta /data/nome_da_obra.json conforme solicitado!
            data_dir = "data"
            os.makedirs(data_dir, exist_ok=True)
            safe_name = manga_title.lower().replace(" ", "_").replace("-", "_")
            safe_name = re.sub(r"[^a-z0-9_]", "", safe_name)
            json_path_data = os.path.join(data_dir, f"{safe_name}.json")

            # Fusão de Memória: Lê o JSON antigo para preservar o status "downloaded" dos capítulos movidos e checa novidades
            if os.path.exists(json_path_data):
                with open(json_path_data, "r", encoding="utf-8") as f:
                    old_data = json.load(f)

                if "chapters" in old_data:
                    for cid, cdata in chapters_dict.items():
                        if cid in old_data["chapters"]:
                            cdata["downloaded"] = old_data["chapters"][cid].get(
                                "downloaded", False
                            )

                    manga_data["latest_downloaded_chapter"] = old_data.get(
                        "latest_downloaded_chapter", 0.0
                    )

                    novos = len(chapters_dict) - len(old_data["chapters"])
                    if novos > 0:
                        print(
                            f"\n[HOT] O site possui {novos} capítulo(s) a mais do que o seu JSON antigo! A fila foi atualizada."
                        )

            with open(json_path_data, "w", encoding="utf-8") as f:
                json.dump(manga_data, f, ensure_ascii=False, indent=4)

            # Baixar a capa automaticamente se existir!
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

            # Parse da seleção do usuário (suporta ranges 5-10 e decimais 19.2)
            specifics = set()
            ranges = []
            for part in selection.split(","):
                part = part.strip()
                if not part:
                    continue
                if "-" in part and part.count("-") == 1:
                    try:
                        s, e = part.split("-")
                        ranges.append((float(s), float(e)))
                    except:
                        pass
                else:
                    try:
                        specifics.add(float(part))
                    except:
                        pass

            # Processar de trás pra frente (ordem cronológica de lançamento)
            overwrite_all = False
            for cap_id, cap in reversed(list(chapters_dict.items())):
                raw_name = cap.get("name", "Cap 00")

                # Extrai o número do capítulo do nome (Ex: "Cap. 24 - Titulo" -> 24.0)
                chap_num = -1.0
                match = re.search(r"Cap\.?\s*([\d\.]+)", raw_name)
                if match:
                    chap_num = float(match.group(1))

                # Verifica se o capítulo está na seleção do usuário
                selected = False
                if chap_num in specifics:
                    selected = True
                for s, e in ranges:
                    if s <= chap_num <= e:
                        selected = True
                        break

                if selected:
                    url = cap.get("url")
                    if not url.startswith("http"):
                        url = "https://sakuramangas.org" + url

                    chapter_folder = re.sub(
                        r"Cap\.\s*([\d\.]+)",
                        lambda m: f"Cap {float(m.group(1)):06.2f}".replace(".00", "")
                        .replace(".", ",")
                        .zfill(3),
                        raw_name,
                    )
                    # Fallback mais simples para o regex de nome de pasta
                    chapter_folder = re.sub(
                        r"Cap\.\s*([\d\.]+)",
                        lambda m: f"Cap {m.group(1).zfill(3)}",
                        raw_name,
                    )
                    chapter_folder = re.sub(r'[\\/:*?"<>|]', "", chapter_folder)
                    chapter_path = os.path.join(
                        "download", manga_folder, chapter_folder
                    )

                    # Verificação Bilateral Interativa (Opção 1)
                    is_physically_downloaded = False
                    if os.path.exists(chapter_path):
                        if any(
                            f.startswith("pag_") and f.endswith(".jpg")
                            for f in os.listdir(chapter_path)
                        ):
                            is_physically_downloaded = True

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
                                f"\n[?] O {chapter_folder} consta no JSON como BAIXADO, mas sumiu da pasta (foi movido?)."
                            )
                            ans = (
                                input(
                                    "Deseja baixar novamente para esta pasta? (S/N): "
                                )
                                .strip()
                                .lower()
                            )
                            if ans != "s":
                                print(
                                    "  -> [PULO] Ignorando re-download. Mantendo flag True no JSON."
                                )
                                cap["downloaded"] = True
                                do_download = False

                    if do_download:
                        print(
                            f"  -> Baixando: {chapter_folder} na pasta {manga_folder}"
                        )
                        success = scraper.download_chapter(
                            url, manga_name=manga_folder, chapter_name=chapter_folder
                        )
                        if success:
                            cap["downloaded"] = True

            # Calcula e salva o maior capítulo baixado no cabeçalho do JSON
            highest_downloaded = 0.0
            for cap_id, cap in chapters_dict.items():
                if cap.get("downloaded", False):
                    raw_name = cap.get("name", "Cap 00")
                    match = re.search(r"Cap\.?\s*([\d\.]+)", raw_name)
                    if match:
                        num = float(match.group(1))
                        if num > highest_downloaded:
                            highest_downloaded = num

            manga_data["latest_downloaded_chapter"] = highest_downloaded

            # Salva a Verificação Bilateral de volta no JSON
            with open(json_path_data, "w", encoding="utf-8") as f:
                json.dump(manga_data, f, ensure_ascii=False, indent=4)

        except Exception as e:
            print(f"[-] Erro na operação com {manga_url}: {e}")

    input("\nProcesso concluído. Pressione Enter para voltar ao menu...")


def download_complete_manga():
    clear_screen()
    print("=== Baixar Mangá Completo ===")
    print("Digite os links dos mangás separados por vírgula (,)")
    print("Ou digite o nome de um arquivo TOML (ex: mapping.toml)")
    print("Exemplo: https://sakuramangas.org/obras/shin-kirari")
    print("\nDigite os links ou arquivo:")

    links_input = input("> ").strip()
    if not links_input:
        print("Nenhum link fornecido. Voltando ao menu...")
        input("Pressione Enter para continuar...")
        return

    # Suporte para carregar fila de um arquivo TOML
    if links_input.endswith(".toml"):
        print(f"\n[*] Lendo arquivo de mapeamento: {links_input}")
        links = []
        try:
            if "tomllib" in sys.modules:
                with open(links_input, "rb") as f:
                    data = tomllib.load(f)
                    links = data.get("mangas", {}).get("urls", [])
            else:
                with open(links_input, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith('"http'):
                            links.append(line.split('"')[1])
        except Exception as e:
            print(f"[-] Erro ao ler TOML: {e}")
            input("Pressione Enter para continuar...")
            return
    else:
        links = [link.strip() for link in links_input.split(",") if link.strip()]

    json_files = set()

    scraper = SakuraScraper(headless=False)

    for link in links:
        print(f"\n[*] Extraindo lista de capítulos para: {link}")
        try:
            manga_data = scraper.get_chapters(link)
            if manga_data and "chapters" in manga_data:
                manga_title = manga_data.get("title", link.strip("/").split("/")[-1])
                safe_name = manga_title.lower().replace(" ", "_").replace("-", "_")
                safe_name = re.sub(r"[^a-z0-9_]", "", safe_name)

                data_dir = "data"
                os.makedirs(data_dir, exist_ok=True)
                json_path = os.path.join(data_dir, f"{safe_name}.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(manga_data, f, ensure_ascii=False, indent=4)

                print(
                    f"[+] Lista salva em {json_path}! Encontrados {len(manga_data['chapters'])} capítulos."
                )
                json_files.add(json_path)
            else:
                print(f"[-] Falha ao obter dados para {link}.")
        except Exception as e:
            print(f"[-] Erro inesperado ao processar {link}: {e}")

    json_files.update(glob.glob("data/*.json", recursive=False))
    # Ignora o state_file
    json_files = {f for f in json_files if "state_file.json" not in f}

    if json_files:
        print("\nArquivos de metadados gerados com sucesso:")
        for json_file in sorted(json_files):
            print(f"- {json_file}")

        print("\nDeseja baixar todos os capítulos agora? (S/N)")
        choice = input("> ").strip().lower()

        if choice == "s":
            for json_path in sorted(json_files):
                print(f"\n[*] Processando fila gerada: {json_path}")
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        dados = json.load(f)

                        manga_title = dados.get("title", "Desconhecido")
                        chapters_dict = dados.get("chapters", {})

                        scanlator = ""
                        if chapters_dict:
                            first_cap = list(chapters_dict.values())[0]
                            scanlator = first_cap.get("scanlator", "")

                        manga_folder = (
                            f"{manga_title} - {scanlator}" if scanlator else manga_title
                        )
                        manga_folder = re.sub(r'[\\/:*?"<>|]', "", manga_folder)

                        for cap_id, cap in reversed(list(chapters_dict.items())):
                            url = cap.get("url")
                            if url:
                                if not url.startswith("http"):
                                    url = "https://sakuramangas.org" + url

                                raw_name = cap.get("name", "Cap 00")
                                chapter_folder = re.sub(
                                    r"Cap\.\s*([\d\.]+)",
                                    lambda m: f"Cap {float(m.group(1)):06.2f}".replace(
                                        ".00", ""
                                    )
                                    .replace(".", ",")
                                    .zfill(3),
                                    raw_name,
                                )
                                chapter_folder = re.sub(
                                    r"Cap\.\s*([\d\.]+)",
                                    lambda m: f"Cap {m.group(1).zfill(3)}",
                                    raw_name,
                                )
                                chapter_folder = re.sub(
                                    r'[\\/:*?"<>|]', "", chapter_folder
                                )

                                chapter_path = os.path.join(
                                    "download", manga_folder, chapter_folder
                                )

                                # Verificação Bilateral Passiva (Opção 2 - Batch)
                                is_physically_downloaded = False
                                if os.path.exists(chapter_path):
                                    if any(
                                        f.startswith("pag_") and f.endswith(".jpg")
                                        for f in os.listdir(chapter_path)
                                    ):
                                        is_physically_downloaded = True

                                if is_physically_downloaded:
                                    print(
                                        f"  -> [PULO] Capítulo já existente no HD: {chapter_folder}"
                                    )
                                    cap["downloaded"] = True
                                else:
                                    if cap.get("downloaded"):
                                        # Usuário moveu para outro lugar para economizar espaço
                                        print(
                                            f"  -> [MEMÓRIA] {chapter_folder} sumiu do HD, mas JSON diz que já foi baixado. Presumindo movimentação. Pulando..."
                                        )
                                    else:
                                        print(
                                            f"  -> Baixando Inédito: {chapter_folder} na pasta {manga_folder}"
                                        )
                                        success = scraper.download_chapter(
                                            url,
                                            manga_name=manga_folder,
                                            chapter_name=chapter_folder,
                                        )
                                        if success:
                                            cap["downloaded"] = True

                        # Calcula e atualiza o maior capítulo baixado no Batch
                        highest_downloaded = 0.0
                        for cap_id, cap in chapters_dict.items():
                            if cap.get("downloaded", False):
                                raw_name = cap.get("name", "Cap 00")
                                match = re.search(r"Cap\.?\s*([\d\.]+)", raw_name)
                                if match:
                                    num = float(match.group(1))
                                    if num > highest_downloaded:
                                        highest_downloaded = num

                        dados["latest_downloaded_chapter"] = highest_downloaded

                        # Salva o estado atualizado no JSON ao final da fila
                        with open(json_path, "w", encoding="utf-8") as f:
                            json.dump(dados, f, ensure_ascii=False, indent=4)

                except Exception as e:
                    print(f"[-] Erro na fila: {e}")

    input("\nProcesso concluído. Pressione Enter para voltar ao menu...")


def main_menu():
    while True:
        clear_screen()
        print_banner()
        print("Menu Principal:")
        print("1 - Baixar Capítulo(s) Específico(s)")
        print("2 - Baixar Mangá Completo")
        print("3 - Sair")

        choice = input("\nEscolha uma opção: ").strip()

        if choice == "1":
            download_chapters()
        elif choice == "2":
            download_complete_manga()
        elif choice == "3":
            print("Saindo do Sakura Mangas Downloader...")
            break
        else:
            print("Opção inválida. Por favor, escolha 1, 2 ou 3.")
            input("Pressione Enter para continuar...")
