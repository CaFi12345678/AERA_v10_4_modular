"""
AERA v10.4 — qwen Tool-Ausführung + Smart Learning Guard (Adaptive Intelligence)

Änderungen gegenüber v10:
  - SMART LEARNING ENGINE v1:
      • Gewohnheits-Erkennung: App-Nutzung, Datei-Zugriffe, Befehle mit JSON-Speicherung
      • Adaptive Vorschläge basierend auf Zeitmustern (Tageszeit, Wochentag)
      • Kontext-Sensitivität: Keine Vorschläge wenn bereits offen
      • Intelligente Zeit-Analyse: Durchschnittszeiten, Toleranzfenster ±15 Min
      • Kontext-Awareness: "Um 4 Uhr ist es früh" — lernt Kontext
      • Ja/Nein-Dialog für Vorschläge (Voice + GUI) mit Feedback-Speicherung
      • Proaktive Benachrichtigungen alle 5 Minuten im Hintergrund
      • Lern-Modell: Speichert letzte 90 Tage, gewichtet letzte 30 Tage stärker
      • Selbstlernend: Verbessert Vorschläge durch Feedback (Ja/Nein)
      • JSON-Persistenz: ~/.aera_learning.json + ~/.aera_suggestions.json
  - Multi-Command Engine v2 beibehalten
      • Robusteres Splitting: "und" nur als ganzes Wort, nicht in App-Namen
      • Korrekte Verbbindung: "öffne WhatsApp und Excel" funktioniert jetzt
      • Schutz vor Falsch-Splits bei App-Namen mit "und" (z.B. "Kommando")
      • Neue Trennzeichen: "und", ",", ";", "sowie", "außerdem", "dann"
      • Intelligente Kontexterkennung: Verben bleiben an ihren Objekten gebunden

  - Verbesserte Fehlerbehandlung bei Mehrfachbefehlen
"""

import asyncio
import re
import random
import threading
import urllib.parse
import ssl
import os
import json
import hashlib
import time
import subprocess
import shutil
import glob
import math
import sys
import platform
import struct
import zipfile
import xml.etree.ElementTree as ET
import difflib
import string
import secrets
import tempfile
import uuid
import base64
import socket
import calendar
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Union
from pathlib import Path

# ── Platform Detection ─────────────────────────────────────────────────────────
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS   = platform.system() == "Darwin"

# ── Optional Imports (graceful fallback) ───────────────────────────────────────
try:
    import customtkinter as ctk
    from customtkinter import CTkFont
    HAS_CTK = True
except ImportError:
    HAS_CTK = False
    import tkinter as ctk
    print("[WARN] CustomTkinter nicht gefunden: pip install customtkinter")
    print("for extra wWindows")
try:
    import tkinter as tk
    from tkinter import scrolledtext, messagebox
    import tkinter.font as tkfont
except ImportError:
    print("[FATAL] tkinter fehlt!")
    print("Dumpass, Tkinter for GUI !")
    sys.exit(1)

try:
    import speech_recognition as sr
    VOICE_OK = True
except ImportError:
    VOICE_OK = False
    print("[WARN] SpeechRecognition fehlt: pip install SpeechRecognition pyaudio")
    print("Speechregonice for Regonision of Audio  to text")
try:
    from thefuzz import fuzz, process as fuzz_process
    FUZZY_OK = True
except ImportError:
    FUZZY_OK = False
    print("[WARN] thefuzz fehlt: pip install thefuzz python-Levenshtein")
    print("The fuzz for matching Ansers")
try:
    import pyautogui
    PYAUTOGUI_OK = True
except ImportError:
    PYAUTOGUI_OK = False

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    import openpyxl
    EXCEL_OK = True
except ImportError:
    EXCEL_OK = False

try:
    import fitz  # PyMuPDF
    PDF_OK = True
except ImportError:
    PDF_OK = False

try:
    from gtts import gTTS
    GTTS_OK = True
except ImportError:
    GTTS_OK = False

try:
    import playsound
    PLAYSOUND_OK = True
except ImportError:
    PLAYSOUND_OK = False

try:
    import pyttsx3
    PYTTSX3_OK = True
except ImportError:
    PYTTSX3_OK = False

try:
    import pyperclip
    CLIPBOARD_OK = True
except ImportError:
    CLIPBOARD_OK = False

try:
    import qrcode
    from PIL import Image
    QR_OK = True
except ImportError:
    QR_OK = False

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False
    print("[WARN] psutil fehlt: pip install psutil  (CPU/RAM-Monitoring)")

# ═══════════════════════════════════════════════════════════════════════════════
#  NEU v10: EDGE-TTS — Clean Neural Voice
# ═══════════════════════════════════════════════════════════════════════════════
try:
    import edge_tts
    EDGE_TTS_OK = True
except ImportError:
    EDGE_TTS_OK = False
    print("[INFO] Edge-TTS nicht installiert. Für beste Stimme: pip install edge-tts")

# ═══════════════════════════════════════════════════════════════════════════════
#  NEU v10.2: LOKALE LLM ENGINE — qwen3:8b Integration
# ═══════════════════════════════════════════════════════════════════════════════
try:
    import ollama
    OLLAMA_OK = True
except ImportError:
    OLLAMA_OK = False
    print("[INFO] Lokale LLM-Integration nicht verfügbar. Für AI-Integration: pip install ollama")

# ── Pfade ──────────────────────────────────────────────────────────────────────
HOME             = Path.home()
CACHE_FILE       = HOME / ".aera_cache.json"
CONFIG_FILE      = HOME / ".aera_config.json"
LOG_FILE         = HOME / ".aera_log.txt"
NOTES_FILE       = HOME / "Desktop" / "AERA_Notizen.txt"
APP_CACHE_FILE   = HOME / ".aera_app_cache.json"

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode    = ssl.CERT_NONE


# ═══════════════════════════════════════════════════════════════════════════════
#  KONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

class Config:
    DEFAULT = {
        "wake_word":       "aera",
        "wake_threshold":  0.82,
        "tts_speed":       170,
        "tts_muted":       False,
        "search_dirs":     ["~/Desktop", "~/Documents", "~/Downloads"],
        "company_name":    "",
        "theme":           "dark",
        "accent":          "#1E6FD9",
        "autostart":       False,
        "socratic_mode":   True,
        "tts_engine":      "edge",  # NEU v10: Edge-TTS als Standard
        "tts_voice":       "de-DE-KatjaNeural",  # NEU v10: Premium Neural Voice
        "polite_mode":     True,  # NEU v10: Höfliche Antworten
        # NEU v10.2: Smart Learning v2 Settings
        "smart_learning_enabled": True,
        "smart_learning_suggestions": True,
        "smart_learning_voice_confirm": True,
        "smart_learning_tolerance_min": 30,  # ±30 Minuten Toleranz
        "smart_learning_min_occurrences": 2,  # Min. 2x für Vorschlag
        "smart_learning_context_weight": 0.5,  # Gewichtung Kontext vs Zeit
        "natural_tts": True,  # Natürliche TTS-Ausgaben
        # NEU v10.2: Lokale LLM Settings
        "ollama_enabled": True,
        "ollama_model": "qwen3:8b",
        "ollama_host": "http://localhost:11434",
        "ollama_max_tokens": 500,
    }

    def __init__(self):
        self.data = dict(self.DEFAULT)
        self._load()

    def _load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self.data.update(loaded)
                if self.data.get("wake_threshold", 1.0) < 0.80:
                    self.data["wake_threshold"] = 0.82
            except Exception:
                pass

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Config] Speicherfehler: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()


CFG = Config()


# ═══════════════════════════════════════════════════════════════════════════════
#  FÜLLWORT-FILTER
# ═══════════════════════════════════════════════════════════════════════════════

class FillerWordFilter:
    HARD_FILLERS = {
        "äh", "ähm", "ähem", "ähäm", "ähh", "ähhm",
        "hmm", "hm", "hmmm", "hmhmm",
        "uh", "uhm", "um", "uhh",
        "er", "eh", "ne", "nä",
        "öh", "öhm", "like", "well",
    }
    SOFT_FILLERS_START = {
        "also", "ja", "naja", "okay", "ok", "so",
        "halt", "mal", "kurz", "einfach", "bitte", "hey", "hej",
    }
    _PHONETIC_RE = re.compile(
        r"^(ä+h*m*|ö+h*m*|u+h*m*|h+m+|e+h+|a+h+)$",
        re.IGNORECASE | re.UNICODE,
    )

    def clean(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"[,!]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        tokens  = text.split()
        cleaned = []
        for i, tok in enumerate(tokens):
            tok_lower = tok.lower().strip(".,!?;:")
            if tok_lower in self.HARD_FILLERS:
                continue
            if self._PHONETIC_RE.match(tok_lower):
                continue
            if tok_lower in self.SOFT_FILLERS_START and not cleaned:
                continue
            cleaned.append(tok)
        return " ".join(cleaned).strip()

    def is_noise(self, text: str) -> bool:
        cleaned = self.clean(text)
        return len(cleaned.strip()) < 2


FILLER = FillerWordFilter()


# ═══════════════════════════════════════════════════════════════════════════════
#  SMART LEARNING ENGINE v10 — ADAPTIVE INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════════

