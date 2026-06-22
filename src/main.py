import argparse
from dotenv import load_dotenv
from core.scraper import SakuraScraper


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Sakura Mangas Downloader 2.0 (The Ghost Scraper)"
    )
    parser.add_argument("url", help="A URL completa do capítulo do Sakura Mangas")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Rodar em modo invisível (Pode falhar no Cloudflare)",
    )

    args = parser.parse_args()

    # Inicia o motor
    # Nota: Headless é falso por padrão para facilitar a passagem pelo Cloudflare
    scraper = SakuraScraper(headless=args.headless)

    print("======================================")
    print("🌸 SAKURA MANGAS DL v2.0 🌸")
    print("======================================")

    # Executa o download
    scraper.download_chapter(args.url)


if __name__ == "__main__":
    main()
