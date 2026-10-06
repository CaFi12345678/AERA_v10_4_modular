"""AERA v10.4 modular entry point.

Unterstützt beide Startarten:
    python aera/main.py
    python -m aera.main
"""

import argparse
import sys
from pathlib import Path

# Bei direktem Start kennt Python das Paket "aera" noch nicht.
# Der Paketordner wird deshalb vor dem Import in sys.path aufgenommen.
if __package__ in (None, ""):
    _PACKAGE_ROOT = Path(__file__).resolve().parent
    _PROJECT_ROOT = _PACKAGE_ROOT.parent
    if str(_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJECT_ROOT))
    from aera.foundation import *
    from aera.intelligence import *
    from aera.services import *
    from aera.commands import *
    from aera.gui import *
else:
    from .foundation import *
    from .intelligence import *
    from .services import *
    from .commands import *
    from .gui import *


def main():
    print_banner()
    missing = []
    if not VOICE_OK:
        missing.append("SpeechRecognition + pyaudio  →  pip install SpeechRecognition pyaudio")
    if not HAS_CTK:
        missing.append("customtkinter  →  pip install customtkinter")
    if not FUZZY_OK:
        missing.append("thefuzz → pip install thefuzz python-Levenshtein")
    if not GTTS_OK:
        missing.append("gTTS → pip install gTTS")
    if not PLAYSOUND_OK:
        missing.append("playsound → pip install playsound==1.2.2")
    if not PSUTIL_OK:
        missing.append("psutil → pip install psutil")
    if not OLLAMA_OK:
        missing.append("ollama → pip install ollama")
    if missing:
        print("FEHLENDE PAKETE:")
        for item in missing:
            print(f"  • {item}")
        print("\nDas Programm startet trotzdem (eingeschränkt).\n")

    parser = argparse.ArgumentParser(description="AERA v10")
    parser.add_argument("--compact", action="store_true", help="Starte im Kompakt-Modus")
    args = parser.parse_args()
    AERA_GUI(start_compact=args.compact).run()


if __name__ == "__main__":
    main()
