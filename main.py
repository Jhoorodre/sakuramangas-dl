import sys
from dotenv import load_dotenv
from src.core.cli import main_menu

if __name__ == "__main__":
    load_dotenv()
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nPrograma interrompido pelo usuário.")
        sys.exit(0)
