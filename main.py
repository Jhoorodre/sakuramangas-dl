import sys
import argparse
from dotenv import load_dotenv
from src.core.cli import main_menu

if __name__ == "__main__":
    load_dotenv()

    parser = argparse.ArgumentParser(description="Sakura Mangas Downloader")
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Inicia o robô com interface gráfica (útil para passar no Cloudflare via Xvfb)",
    )
    args = parser.parse_args()

    is_headless = not args.no_headless

    try:
        main_menu(headless=is_headless)
    except KeyboardInterrupt:
        print("\nPrograma interrompido pelo usuário.")
        sys.exit(0)
