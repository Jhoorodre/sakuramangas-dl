import sys
import logging
import argparse
from dotenv import load_dotenv
from src.core.cli import main_menu


class _Tee:
    def __init__(self, primary, secondary):
        self.files = (primary, secondary)

    def write(self, text):
        for f in self.files:
            try:
                f.write(text)
            except (ValueError, OSError):
                pass

    def flush(self):
        for f in self.files:
            try:
                f.flush()
            except (ValueError, OSError):
                pass

    def __getattr__(self, name):
        return getattr(self.files[0], name)


if __name__ == "__main__":
    load_dotenv()

    parser = argparse.ArgumentParser(description="Sakura Mangas Downloader")
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Inicia o robô com interface gráfica (útil para passar no Cloudflare via Xvfb)",
    )
    args = parser.parse_args()

    _log_file = open("pipeline.log", "w", encoding="utf-8")
    sys.stdout = _Tee(sys.__stdout__, _log_file)
    sys.stderr = _Tee(sys.__stderr__, _log_file)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)

    is_headless = not args.no_headless

    try:
        main_menu(headless=is_headless)
    except KeyboardInterrupt:
        print("\nPrograma interrompido pelo usuário.")
        sys.exit(0)
    finally:
        _log_file.close()
