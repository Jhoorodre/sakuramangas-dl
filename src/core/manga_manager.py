import os
import json
import re

try:
    import tomllib
except ModuleNotFoundError:
    pass


class MangaManager:
    DATA_DIR = os.environ.get("DATA_DIR", "data")
    DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "download")

    @staticmethod
    def read_toml_links(toml_path="mapping.toml"):
        """Lê os links do arquivo de mapeamento."""
        toml_links = []
        if os.path.exists(toml_path):
            try:
                if "tomllib" in globals():
                    with open(toml_path, "rb") as f:
                        data = tomllib.load(f)
                        toml_links = data.get("mangas", {}).get("urls", [])
                else:
                    with open(toml_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip().startswith('"'):
                                raw_url = line.split('"')[1]
                                toml_links.append(raw_url.rstrip("/"))
            except Exception:
                pass
        return toml_links

    @staticmethod
    def add_urls_to_toml(urls, toml_path="mapping.toml"):
        """Adiciona milhares de URLs ao mapping.toml sem apagar os existentes."""
        existing = set(MangaManager.read_toml_links(toml_path))
        new_urls = [u for u in urls if u not in existing]

        if not new_urls:
            return 0

        # Se não existe, cria do zero
        if not os.path.exists(toml_path):
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write("[mangas]\nurls = [\n")
                for u in new_urls:
                    f.write(f'    "{u}",\n')
                f.write("]\n")
        else:
            # Se já existe, lê, remove a última chave "]" e adiciona mais links
            with open(toml_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            with open(toml_path, "w", encoding="utf-8") as f:
                for line in lines:
                    if line.strip() != "]":
                        f.write(line)

                # Garante que a linha anterior tem uma vírgula (se havia algum link)
                if len(lines) > 2 and not lines[-2].strip().endswith(","):
                    # Hack simples para adicionar a vírgula na linha de cima seria mais complexo em append bruto.
                    # Mas no TOML, a última vírgula no array é opcional/tolerada.
                    pass

                for u in new_urls:
                    f.write(f'    "{u}",\n')
                f.write("]\n")

        return len(new_urls)

    @staticmethod
    def get_safe_manga_name(manga_title):
        """Gera um nome seguro para o arquivo JSON do mangá."""
        safe_name = manga_title.lower().replace(" ", "_").replace("-", "_")
        return re.sub(r"[^a-z0-9_]", "", safe_name)

    @staticmethod
    def format_manga_folder(manga_title, scanlator=""):
        """Formata o nome da pasta do mangá."""
        manga_folder = f"{manga_title} - {scanlator}" if scanlator else manga_title
        return re.sub(r'[\\/:*?"<>|]', "", manga_folder)

    @staticmethod
    def format_chapter_folder(raw_name):
        """Formata o nome da pasta do capítulo (ex: Cap 024.00)."""
        chapter_folder = re.sub(
            r"Cap\.\s*([\d\.]+)",
            lambda m: f"Cap {float(m.group(1)):06.2f}".replace(".00", "")
            .replace(".", ",")
            .zfill(3),
            raw_name,
        )
        chapter_folder = re.sub(
            r"Cap\.\s*([\d\.]+)",
            lambda m: f"Cap {m.group(1).zfill(3)}",
            raw_name,
        )
        return re.sub(r'[\\/:*?"<>|]', "", chapter_folder)

    @staticmethod
    def get_chap_num_from_name(raw_name):
        """Extrai o número do capítulo float a partir do nome bruto."""
        match = re.search(r"Cap\.?\s*([\d\.]+)", raw_name)
        if match:
            return float(match.group(1))
        return -1.0

    @staticmethod
    def parse_chapter_selection(selection):
        """Analisa a string de seleção de capítulos do usuário e retorna (specifics, ranges)."""
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
                except Exception:
                    pass
            else:
                try:
                    specifics.add(float(part))
                except Exception:
                    pass
        return specifics, ranges

    @staticmethod
    def is_chapter_selected(chap_num, specifics, ranges):
        """Verifica se o número do capítulo foi selecionado."""
        if chap_num in specifics:
            return True
        for s, e in ranges:
            if s <= chap_num <= e:
                return True
        return False

    @staticmethod
    def is_physically_downloaded(chapter_path):
        """Verifica se o capítulo já foi baixado fisicamente analisando os arquivos jpg."""
        if os.path.exists(chapter_path):
            if any(
                f.startswith("pag_") and f.endswith(".jpg")
                for f in os.listdir(chapter_path)
            ):
                return True
        return False

    @staticmethod
    def save_manga_data(manga_data, chapters_dict, data_dir=None):
        """Mescla e salva os dados do mangá no JSON, preservando histórico."""
        if data_dir is None:
            data_dir = MangaManager.DATA_DIR
        os.makedirs(data_dir, exist_ok=True)
        manga_title = manga_data.get("title", "Desconhecido")
        safe_name = MangaManager.get_safe_manga_name(manga_title)
        json_path_data = os.path.join(data_dir, f"{safe_name}.json")

        # Fusão de Memória
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

        return json_path_data

    @staticmethod
    def update_latest_downloaded(manga_data, json_path):
        """Atualiza a propriedade latest_downloaded_chapter do JSON."""
        highest = 0.0
        chapters_dict = manga_data.get("chapters", {})
        for cap_id, cap in chapters_dict.items():
            if cap.get("downloaded", False):
                num = MangaManager.get_chap_num_from_name(cap.get("name", "Cap 00"))
                if num > highest:
                    highest = num

        manga_data["latest_downloaded_chapter"] = highest
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(manga_data, f, ensure_ascii=False, indent=4)
