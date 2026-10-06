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

class SmartLearningEngine:
    """
    v10.2: Smart Learning v2 — Lernt Gewohnheiten UND Kontext-Sequenzen.

    Features:
    - Kontext-basierte Vorschläge: Erkennt "Du öffnest Outlook nach Teams"
    - Sequenz-Erkennung: Lernt typische Befehlsketten (App A → App B)
    - Vorhersage nach Aktionen: Nach "öffne Teams" → "Soll ich Outlook öffnen?"
    - Kontext-Gewichtung: Zeit + Sequenz kombiniert für bessere Vorschläge
    - Erfasst App-Öffnungen, Datei-Zugriffe, Befehle mit Zeitstempel
    - Analysiert Zeitmuster (Tageszeit, Wochentag)
    - Berechnet Durchschnittszeiten mit Toleranzfenster
    - Kontext-Prüfung: Vorschläge nur wenn nicht bereits offen
    - Intelligente Zeit-Kommentare ("Um 4 Uhr ist es früh")
    - Ja/Nein-Dialog für Vorschläge mit JSON-Speicherung
    - Feedback-Learning: Verbessert Vorschläge durch User-Antworten
    - JSON-Persistenz: ~/.aera_learning.json + ~/.aera_suggestions.json + ~/.aera_context.json
    """

    LEARN_FILE = HOME / ".aera_learning.json"
    SUGGESTION_HISTORY_FILE = HOME / ".aera_suggestions.json"
    CONTEXT_FILE = HOME / ".aera_context.json"  # NEU v10.2: Sequenz-Muster

    TIME_CONTEXTS = {
        "night":    (0, 5, "Nacht", "Es ist ziemlich spät — bist du sicher?"),
        "early":    (5, 8, "früher Morgen", "Guten Morgen! Ein früher Start."),
        "morning":  (8, 12, "Morgen", "Guten Morgen!"),
        "noon":     (12, 14, "Mittag", "Guten Mittag!"),
        "afternoon":(14, 18, "Nachmittag", "Guten Tag!"),
        "evening":  (18, 22, "Abend", "Guten Abend!"),
        "late":     (22, 24, "später Abend", "Es wird spät — möchtest du wirklich noch arbeiten?"),
    }

    def __init__(self, tts_manager=None, app_engine=None, system_commands=None):
        self.tts = tts_manager
        self.app_engine = app_engine
        self.system_commands = system_commands

        # Gewohnheits-Daten: {action_type: {action_name: [timestamps]}}
        self.habits = defaultdict(lambda: defaultdict(list))

        # NEU v10.2: Kontext-Sequenzen — {action_A: {action_B: count}}
        # Speichert wie oft Aktion B nach Aktion A folgt
        self.context_sequences = defaultdict(lambda: defaultdict(int))
        self.last_action = None  # Letzte ausgeführte Aktion
        self.last_action_time = None

        # Vorschlags-History für Feedback-Learning
        self.suggestion_feedback = []

        # Aktive Vorschläge (für Ja/Nein-Dialog)
        self.pending_suggestions = []
        self._suggestion_lock = threading.Lock()

        # Lern-Thread
        self._learning_active = True
        self._learning_thread = None

        self._load_data()
        self._start_learning_loop()

    def _load_data(self):
        """Lädt gelernte Gewohnheiten und Kontext-Sequenzen aus JSON."""
        try:
            if self.LEARN_FILE.exists():
                with open(self.LEARN_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Konvertiere geladene Daten zurück
                for action_type, actions in data.get("habits", {}).items():
                    for action_name, entries in actions.items():
                        for entry in entries:
                            entry["timestamp"] = datetime.fromisoformat(entry["timestamp"])
                            self.habits[action_type][action_name].append(entry)
                print(f"[SmartLearning] {sum(len(v) for actions in self.habits.values() for v in actions.values())} Gewohnheiten geladen.")
        except Exception as e:
            print(f"[SmartLearning] Lade-Fehler: {e}")

        # NEU v10.2: Kontext-Sequenzen laden
        try:
            if self.CONTEXT_FILE.exists():
                with open(self.CONTEXT_FILE, "r", encoding="utf-8") as f:
                    ctx_data = json.load(f)
                for from_action, to_actions in ctx_data.get("sequences", {}).items():
                    for to_action, count in to_actions.items():
                        self.context_sequences[from_action][to_action] = count
                print(f"[SmartLearning] {sum(len(v) for v in self.context_sequences.values())} Kontext-Sequenzen geladen.")
        except Exception as e:
            print(f"[SmartLearning] Kontext-Lade-Fehler: {e}")

        try:
            if self.SUGGESTION_HISTORY_FILE.exists():
                with open(self.SUGGESTION_HISTORY_FILE, "r", encoding="utf-8") as f:
                    self.suggestion_feedback = json.load(f)
        except Exception:
            pass

    def _save_data(self):
        """Speichert gelernte Gewohnheiten und Kontext-Sequenzen als JSON."""
        try:
            serializable = {"habits": {}}
            for action_type, actions in self.habits.items():
                serializable["habits"][action_type] = {}
                for action_name, entries in actions.items():
                    serializable["habits"][action_type][action_name] = [
                        {
                            "timestamp": e["timestamp"].isoformat(),
                            "day_of_week": e.get("day_of_week", 0),
                            "hour": e.get("hour", 0),
                            "minute": e.get("minute", 0),
                        }
                        for e in entries[-500:]  # Max 500 Einträge pro Aktion
                    ]
            with open(self.LEARN_FILE, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SmartLearning] Speicher-Fehler: {e}")

        # NEU v10.2: Kontext-Sequenzen speichern
        try:
            ctx_serializable = {"sequences": {}}
            for from_action, to_actions in self.context_sequences.items():
                ctx_serializable["sequences"][from_action] = dict(to_actions)
            with open(self.CONTEXT_FILE, "w", encoding="utf-8") as f:
                json.dump(ctx_serializable, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SmartLearning] Kontext-Speicher-Fehler: {e}")

    def _save_suggestion_feedback(self):
        """Speichert Feedback-History als JSON."""
        try:
            with open(self.SUGGESTION_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.suggestion_feedback[-200:], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def record_action(self, action_type, action_name, metadata=None):
        """
        Zeichnet eine User-Aktion auf.

        action_type: "app_open", "app_close", "file_open", "command", "web_open"
        action_name: z.B. "outlook", "rechnung.pdf", "screenshot"
        """
        if not CFG.get("smart_learning_enabled", True):
            return

        now = datetime.now()
        entry = {
            "timestamp": now,
            "day_of_week": now.weekday(),  # 0=Mo, 6=So
            "hour": now.hour,
            "minute": now.minute,
            "metadata": metadata or {},
        }
        self.habits[action_type][action_name].append(entry)

        # NEU v10.2: Kontext-Sequenz erfassen
        current_action = f"{action_type}:{action_name}"
        if self.last_action and self.last_action_time:
            time_diff = (now - self.last_action_time).total_seconds()
            # Nur Sequenzen innerhalb von 10 Minuten speichern
            if time_diff <= 600:
                self.context_sequences[self.last_action][current_action] += 1
        self.last_action = current_action
        self.last_action_time = now

        # Speichere alle 10 Aktionen
        if sum(len(v) for actions in self.habits.values() for v in actions.values()) % 10 == 0:
            self._save_data()

    def get_time_context(self, hour):
        """Gibt Zeit-Kontext und passenden Kommentar zurück."""
        for key, (start, end, name, comment) in self.TIME_CONTEXTS.items():
            if start <= hour < end:
                return name, comment
        return "Nacht", "Es ist spät."

    def analyze_pattern(self, action_type, action_name):
        """
        Analysiert das Zeitmuster einer Aktion.

        Returns: {
            "average_time": "18:15",      # Durchschnittszeit
            "std_deviation": 12,           # Standardabweichung in Minuten
            "most_common_day": 1,          # Häufigster Wochentag (0=Mo)
            "occurrences": 15,             # Anzahl Vorkommen
            "confidence": 0.85,            # Konfidenz 0-1
            "time_distribution": {...},   # Verteilung über den Tag
        }
        """
        entries = self.habits.get(action_type, {}).get(action_name, [])
        min_occurrences = CFG.get("smart_learning_min_occurrences", 3)

        if len(entries) < min_occurrences:
            return None

        # Nur Einträge der letzten 90 Tage, gewichtet letzte 30 stärker
        cutoff_90 = datetime.now() - timedelta(days=90)
        cutoff_30 = datetime.now() - timedelta(days=30)

        recent_entries = [e for e in entries if e["timestamp"] > cutoff_90]
        if len(recent_entries) < min_occurrences:
            return None

        # Berechne Durchschnittszeit (in Minuten seit Mitternacht)
        total_minutes = 0
        weights = []
        days = []

        for e in recent_entries:
            minutes = e["hour"] * 60 + e["minute"]
            # Gewichtung: letzte 30 Tage = 2x, 30-90 Tage = 1x
            weight = 2.0 if e["timestamp"] > cutoff_30 else 1.0
            total_minutes += minutes * weight
            weights.append(weight)
            days.append(e["day_of_week"])

        avg_minutes = total_minutes / sum(weights)
        avg_hour = int(avg_minutes // 60)
        avg_minute = int(avg_minutes % 60)

        # Standardabweichung
        variance = sum(
            ((e["hour"] * 60 + e["minute"]) - avg_minutes) ** 2
            for e in recent_entries
        ) / len(recent_entries)
        std_dev = math.sqrt(variance)

        # Häufigster Wochentag
        most_common_day = Counter(days).most_common(1)[0][0] if days else 0

        # Konfidenz basierend auf Anzahl und Konsistenz
        confidence = min(1.0, len(recent_entries) / 10) * (1 - min(std_dev / 120, 0.5))

        # Zeit-Verteilung (Stunden)
        hour_dist = Counter(e["hour"] for e in recent_entries)

        return {
            "average_time": f"{avg_hour:02d}:{avg_minute:02d}",
            "avg_hour": avg_hour,
            "avg_minute": avg_minute,
            "std_deviation": int(std_dev),
            "most_common_day": most_common_day,
            "occurrences": len(recent_entries),
            "confidence": round(confidence, 2),
            "time_distribution": dict(hour_dist),
        }

    def is_app_running(self, app_name):
        """Prüft ob eine App bereits läuft."""
        if not self.app_engine:
            return False
        try:
            if IS_WINDOWS:
                r = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                                   capture_output=True, text=True, timeout=5,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                app_lower = app_name.lower()
                for line in r.stdout.splitlines():
                    parts = line.split('","')
                    if parts:
                        proc = parts[0].strip('"').lower().replace(".exe", "")
                        if app_lower in proc or proc in app_lower:
                            return True
            else:
                r = subprocess.run(["ps", "-Ao", "comm"],
                                   capture_output=True, text=True, timeout=5)
                app_lower = app_name.lower()
                for line in r.stdout.splitlines()[1:]:
                    proc = Path(line.strip()).name.lower()
                    if app_lower in proc or proc in app_lower:
                        return True
        except Exception:
            pass
        return False

    def generate_suggestions(self, current_time=None):
        """
        Generiert intelligente Vorschläge basierend auf gelernten Gewohnheiten.
        """
        if not CFG.get("smart_learning_suggestions", True):
            return []

        now = current_time or datetime.now()
        current_hour = now.hour
        current_minutes = current_hour * 60 + now.minute
        tolerance = CFG.get("smart_learning_tolerance_min", 15)

        suggestions = []

        # Analysiere alle gelernten Gewohnheiten
        for action_type, actions in self.habits.items():
            for action_name, entries in actions.items():
                pattern = self.analyze_pattern(action_type, action_name)
                if not pattern:
                    continue

                avg_minutes = pattern["avg_hour"] * 60 + pattern["avg_minute"]
                diff_minutes = abs(current_minutes - avg_minutes)

                # Auch über Mitternacht hinweg prüfen
                diff_minutes = min(diff_minutes, 1440 - diff_minutes)

                # Nur vorschlagen wenn innerhalb Toleranzfenster
                if diff_minutes > tolerance:
                    continue

                # Konfidenz-Check
                if pattern["confidence"] < 0.3:
                    continue

                # Prüfe ob bereits offen (nur für Apps)
                if action_type == "app_open" and self.is_app_running(action_name):
                    continue

                # Generiere Vorschlag-Text
                time_ctx, time_comment = self.get_time_context(current_hour)

                # Kontext-Kommentar basierend auf Zeit
                context_parts = []
                if diff_minutes <= 5:
                    context_parts.append(f"Es ist genau deine übliche Zeit für {action_name}!")
                else:
                    context_parts.append(
                        f"Du {action_type.replace('_', ' ')} {action_name} "
                        f"normalerweise um {pattern['average_time']} Uhr."
                    )

                # Zeit-Kommentar (z.B. "Um 4 Uhr ist es früh")
                if current_hour < 6:
                    context_parts.append("Es ist ziemlich früh — möchtest du wirklich schon anfangen?")
                elif current_hour > 22:
                    context_parts.append("Es ist schon spät — eine letzte Sache noch?")

                # Wochentag-Check
                weekday_names = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
                                "Freitag", "Samstag", "Sonntag"]
                if pattern["most_common_day"] == now.weekday():
                    context_parts.append(f"Und heute ist {weekday_names[now.weekday()]} — dein typischer Tag dafür!")

                suggestion_text = f"Soll ich {action_name} öffnen?"
                if action_type == "file_open":
                    suggestion_text = f"Soll ich die Datei '{action_name}' öffnen?"
                elif action_type == "command":
                    suggestion_text = f"Soll ich '{action_name}' ausführen?"

                full_message = f"{time_comment}\n\n{suggestion_text}\n\n" + "\n".join(context_parts)

                # Erstelle Execute-Funktion - KORRIGIERT: Verwende default-Parameter um Closure-Bug zu vermeiden
                def make_execute(at=action_type, an=action_name, ae=self.app_engine, sc=self.system_commands):
                    if at == "app_open":
                        if ae:
                            return lambda: ae.open_app(an)
                        return lambda: f"App '{an}' nicht verfügbar."
                    elif at == "file_open":
                        if sc:
                            return lambda: sc.find_file(an)
                        return lambda: f"Datei '{an}' nicht verfügbar."
                    elif at == "command":
                        return lambda: f"Befehl '{an}' ausgeführt."
                    else:
                        return lambda: f"Aktion '{an}' ausgeführt."

                suggestions.append({
                    "type": action_type,
                    "action": action_name,
                    "suggestion_text": suggestion_text,
                    "full_message": full_message,
                    "average_time": pattern["average_time"],
                    "confidence": pattern["confidence"],
                    "context_comment": " ".join(context_parts),
                    "execute": make_execute(),
                    "diff_minutes": diff_minutes,
                })

        # Sortiere nach Konfidenz und Zeitnähe
        suggestions.sort(key=lambda x: (-x["confidence"], x["diff_minutes"]))
        return suggestions[:3]  # Max 3 Vorschläge

    def present_suggestion(self, suggestion, gui_callback=None, voice_callback=None):
        """
        Präsentiert einen Vorschlag mit Ja/Nein-Option.
        """
        with self._suggestion_lock:
            self.pending_suggestions.append(suggestion)

        msg = suggestion["full_message"]

        # TTS-Ansage
        if self.tts and CFG.get("smart_learning_voice_confirm", True):
            clean_msg = msg.replace("\\n", " ").strip()
            self.tts.speak(clean_msg + " Sage Ja oder Nein.")

        # GUI-Callback
        if gui_callback:
            gui_callback(suggestion)

        return msg

    def handle_user_response(self, response, suggestion=None):
        """
        Verarbeitet Ja/Nein-Antwort auf Vorschlag.

        response: "ja", "nein", "ok", "gern", "lieber nicht", etc.
        """
        response_lower = response.lower().strip()

        # Positive Antworten
        positive = ["ja", "ok", "gern", "gerne", "bitte", "mach", "mache",
                    "ja bitte", "klar", "sicher", "auf jeden fall", "jo",
                    "jop", "yep", "yes", "jawohl", "in ordnung", "einverstanden",
                    "ok mach", "ja mach", "öffne", "starte"]

        # Negative Antworten
        negative = ["nein", "ne", "nö", "nope", "no", "nicht", "lieber nicht",
                    "später", "nicht jetzt", "nein danke", "lass mal", "abgelehnt",
                    "nicht nötig", "brauch ich nicht", "vergiss es", "stop"]

        # Hole aktuellen Vorschlag falls nicht übergeben
        if suggestion is None:
            with self._suggestion_lock:
                if self.pending_suggestions:
                    suggestion = self.pending_suggestions.pop(0)
                else:
                    return "Kein aktiver Vorschlag vorhanden."

        is_positive = any(p in response_lower for p in positive)
        is_negative = any(n in response_lower for n in negative)

        # Feedback speichern
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "suggestion": suggestion,
            "response": response_lower,
            "accepted": is_positive,
        }
        self.suggestion_feedback.append(feedback_entry)
        self._save_suggestion_feedback()

        if is_positive:
            # Führe Aktion aus
            try:
                result = suggestion["execute"]()
                # Zeichne als erfolgreiche Aktion auf
                self.record_action(suggestion["type"], suggestion["action"])
                return f"✅ {result}"
            except Exception as e:
                return f"❌ Fehler: {e}"
        elif is_negative:
            return "👌 Verstanden. Ich werde dich später nicht mehr daran erinnern."
        else:
            # Unklare Antwort
            return "Ich habe dich nicht verstanden. Bitte sage 'Ja' oder 'Nein'."

    def _start_learning_loop(self):
        """Startet den Hintergrund-Thread für proaktive Vorschläge."""
        def loop():
            while self._learning_active:
                try:
                    if CFG.get("smart_learning_suggestions", True):
                        suggestions = self.generate_suggestions()
                        for sugg in suggestions:
                            # Prüfe ob dieser Vorschlag kürzlich abgelehnt wurde
                            if not self._was_recently_rejected(sugg):
                                self._queue_suggestion(sugg)
                    # Prüfe alle 5 Minuten
                    time.sleep(300)
                except Exception as e:
                    print(f"[SmartLearning] Loop-Fehler: {e}")
                    time.sleep(60)

        self._learning_thread = threading.Thread(target=loop, daemon=True)
        self._learning_thread.start()

    def _was_recently_rejected(self, suggestion, hours=2):
        """Prüft ob ein Vorschlag kürzlich abgelehnt wurde."""
        cutoff = datetime.now() - timedelta(hours=hours)
        for fb in reversed(self.suggestion_feedback):
            fb_time = datetime.fromisoformat(fb["timestamp"])
            if fb_time < cutoff:
                break
            if (fb["suggestion"].get("action") == suggestion["action"] and
                not fb.get("accepted", False)):
                return True
        return False

    def _queue_suggestion(self, suggestion):
        """Queue einen Vorschlag für die GUI."""
        # Wird von der GUI abgefragt
        with self._suggestion_lock:
            # Vermeide Duplikate
            for pending in self.pending_suggestions:
                if pending["action"] == suggestion["action"]:
                    return
            self.pending_suggestions.append(suggestion)

    def get_pending_suggestions(self):
        """Holt wartende Vorschläge (für GUI-Polling)."""
        with self._suggestion_lock:
            result = list(self.pending_suggestions)
            self.pending_suggestions.clear()
            return result

    def get_habit_stats(self):
        """Gibt Statistiken über gelernte Gewohnheiten und Kontext-Sequenzen aus."""
        lines = ["📊 SMART LEARNING v2 STATISTIKEN", "=" * 40]

        total_actions = sum(
            len(entries)
            for actions in self.habits.values()
            for entries in actions.values()
        )
        lines.append(f"Gesamt erfasste Aktionen: {total_actions}")
        lines.append(f"Erfasste App-Öffnungen: {sum(len(v) for v in self.habits.get('app_open', {}).values())}")
        lines.append(f"Erfasste Datei-Zugriffe: {sum(len(v) for v in self.habits.get('file_open', {}).values())}")
        lines.append(f"Erfasste Befehle: {sum(len(v) for v in self.habits.get('command', {}).values())}")

        # NEU v10.2: Kontext-Sequenzen
        total_sequences = sum(
            sum(counts.values())
            for counts in self.context_sequences.values()
        )
        unique_sequences = sum(len(counts) for counts in self.context_sequences.values())
        lines.append(f"Gelernte Kontext-Sequenzen: {unique_sequences} ({total_sequences} Übergänge)")
        lines.append("")

        # Top-Gewohnheiten
        lines.append("🔝 TOP-GEWOHNHEITEN (Zeit-basiert):")
        all_patterns = []
        for action_type, actions in self.habits.items():
            for action_name, entries in actions.items():
                pattern = self.analyze_pattern(action_type, action_name)
                if pattern:
                    all_patterns.append((action_type, action_name, pattern))

        all_patterns.sort(key=lambda x: x[2]["confidence"], reverse=True)

        for at, an, pat in all_patterns[:10]:
            emoji = "📱" if at == "app_open" else "📄" if at == "file_open" else "⚡"
            lines.append(
                f"  {emoji} {an}: Ø {pat['average_time']} Uhr "
                f"({pat['occurrences']}x, Konfidenz: {pat['confidence']:.0%})"
            )

        # NEU v10.2: Top-Kontext-Sequenzen
        if self.context_sequences:
            lines.append("")
            lines.append("🔗 TOP-KONTEXT-SEQUENZEN:")
            all_seqs = []
            for from_action, to_actions in self.context_sequences.items():
                for to_action, count in to_actions.items():
                    all_seqs.append((from_action, to_action, count))
            all_seqs.sort(key=lambda x: -x[2])
            for from_a, to_a, count in all_seqs[:8]:
                from_name = from_a.split(":", 1)[1] if ":" in from_a else from_a
                to_name = to_a.split(":", 1)[1] if ":" in to_a else to_a
                lines.append(f"  ➜ {from_name} → {to_name}: {count}x")

        # Vorschlags-Erfolgsrate
        if self.suggestion_feedback:
            accepted = sum(1 for fb in self.suggestion_feedback if fb.get("accepted"))
            total = len(self.suggestion_feedback)
            rate = accepted / total if total > 0 else 0
            lines.append("")
            lines.append(f"🎯 VORSCHLAGS-Erfolgsrate: {accepted}/{total} ({rate:.0%})")

        return " ".join(lines)

    def clear_habits(self):
        """Löscht alle gelernten Gewohnheiten."""
        self.habits.clear()
        self.suggestion_feedback.clear()
        self._save_data()
        self._save_suggestion_feedback()
        return "Alle gelernten Gewohnheiten wurden zurückgesetzt."

    def stop(self):
        """Stoppt den Learning-Thread."""
        self._learning_active = False
        self._save_data()
        self._save_suggestion_feedback()




# ═══════════════════════════════════════════════════════════════════════════════
#  LOKALE LLM ENGINE v10.2 — qwen3:8b Integration
# ═══════════════════════════════════════════════════════════════════════════════

class OllamaAIEngine:
    """
    v10.2: Lokale LLM Integration für AERA.

    Wenn ein Befehl nicht erkannt wird, wird er automatisch an Ollama weitergeleitet.
    Die Antwort wird durch AERA's TTS gesprochen und im Chat angezeigt.

    Features:
    • Automatische Erkennung unbekannter Befehle
    • qwen3:8b via Ollama API (localhost:11434)
    • Token-Limit: 500 max (konfigurierbar)
    • System-Prompt: AERA ist ein persönlicher Assistent
    • Konversationsspeicher für Kontext
    • Fehlerbehandlung mit Fallback
    • Integriert in AERA's TTS und GUI
    """

    DEFAULT_MODEL = "qwen3:8b"
    DEFAULT_HOST = "http://localhost:11434"
    DEFAULT_MAX_TOKENS = 500

    SYSTEM_PROMPT = """Du bist AERA, ein persönlicher digitaler Assistent. 
Du hilfst dem Nutzer bei alltäglichen Aufgaben, beantwortest Fragen und führst Anweisungen aus.
Antworte kurz, präzise und auf Deutsch. Verwende keine Markdown-Formatierung.

WICHTIG — DU KANNST AERA-BEFEHLE AUSFÜHREN!
Wenn der Nutzer eine Aufgabe beschreibt, die ein AERA-Befehl sein könnte,
antworte im Format: AERA_BEFEHL: <befehl>

Beispiele:
- Nutzer: "öffne Spotify" -> AERA_BEFEHL: öffne Spotify
- Nutzer: "wie viel Akku habe ich" -> AERA_BEFEHL: akku status
- Nutzer: "mach einen Screenshot" -> AERA_BEFEHL: screenshot
- Nutzer: "was ist 5 mal 7" -> AERA_BEFEHL: berechne 5 mal 7
- Nutzer: "suche die Rechnung Mueller" -> AERA_BEFEHL: suche Rechnung Mueller
- Nutzer: "starte Timer 10 Minuten" -> AERA_BEFEHL: timer 10 min
- Nutzer: "zeig CPU-Auslastung" -> AERA_BEFEHL: cpu
- Nutzer: "schliesse Chrome" -> AERA_BEFEHL: schliesse Chrome
- Nutzer: "öffne WhatsApp und Excel" -> AERA_BEFEHL: öffne WhatsApp und Excel
- Nutzer: "Wetter in Berlin" -> AERA_BEFEHL: wetter Berlin

Wenn der Nutzer eine allgemeine Frage stellt (z.B. "Was ist die Hauptstadt von Frankreich?"),
antworte normal ohne AERA_BEFEHL-Prefix.

Bleibe höflich und hilfsbereit."""

    def __init__(self, tts_manager=None, chat_callback=None, max_tokens=500, command_parser=None):
        self.tts = tts_manager
        self.chat_callback = chat_callback
        self.max_tokens = max_tokens
        self.model = CFG.get("ollama_model", self.DEFAULT_MODEL)
        self.host = CFG.get("ollama_host", self.DEFAULT_HOST)
        self.enabled = CFG.get("ollama_enabled", True)
        self.conversation_history = []  # Für Kontext
        self.max_history = 10  # Max 10 Nachrichten im Kontext
        self._lock = threading.Lock()
        self._last_response = None
        self.command_parser = command_parser  # NEU v10.4: Referenz zum CommandParser

        # Prüfe ob Ollama verfügbar ist
        self._check_availability()

    def _check_availability(self):
        """Prüft ob der lokale LLM-Server läuft."""
        if not OLLAMA_OK and not REQUESTS_OK:
            self.available = False
            return

        try:
            if OLLAMA_OK:
                # Versuche Liste der Modelle abzurufen
                models = ollama.list()
                self.available = True
                print(f"[Lokale LLMs] Verfügbar. Modelle: {[m['model'] for m in models.get('models', [])][:5]}")
            elif REQUESTS_OK:
                r = requests.get(f"{self.host}/api/tags", timeout=3)
                self.available = r.status_code == 200
                if self.available:
                    print(f"[Lokale LLMs] Verfügbar via REST API.")
        except Exception as e:
            self.available = False
            print(f"[Lokale LLMs] Nicht verfügbar: {e}")

    def is_available(self):
        """Gibt zurück ob lokale LLMs verfügbar sind."""
        return self.available and self.enabled

    def set_model(self, model_name: str):
        """Ändert das verwendete Modell."""
        self.model = model_name
        CFG.set("ollama_model", model_name)
        return f"Modell geändert zu: {model_name}"

    def ask(self, prompt: str, use_history: bool = True, execute_tools: bool = False) -> str:
        """
        Sendet eine Anfrage an lokale LLMs.

        Args:
            prompt: Die Benutzeranfrage
            use_history: Ob Konversationskontext verwendet werden soll
            execute_tools: Wenn True, versucht qwen AERA-Befehle auszuführen

        Returns:
            Die Antwort des Modells oder Fehlermeldung
        """
        if not self.available:
            return "❌ Lokale LLMs sind nicht verfügbar. Stelle sicher, dass der Server läuft (z.B. ollama serve) und ein Modell installiert ist."

        if not self.enabled:
            return "🔕 Lokale LLM-Integration ist deaktiviert."

        try:
            # Baue Nachrichten-Array
            messages = []

            # System-Prompt
            messages.append({
                "role": "system",
                "content": self.SYSTEM_PROMPT
            })

            # Konversationshistorie (wenn aktiviert)
            if use_history and self.conversation_history:
                messages.extend(self.conversation_history[-self.max_history:])

            # Aktuelle Benutzeranfrage
            messages.append({
                "role": "user",
                "content": prompt
            })

            # Sende Anfrage an Ollama
            if OLLAMA_OK:
                response = ollama.chat(
                    model=self.model,
                    messages=messages,
                    options={
                        "num_predict": self.max_tokens,
                        "temperature": 0.7,
                    }
                )
                answer = response["message"]["content"].strip()

            elif REQUESTS_OK:
                # Fallback via REST API
                r = requests.post(
                    f"{self.host}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "num_predict": self.max_tokens,
                            "temperature": 0.7,
                        }
                    },
                    timeout=60
                )
                r.raise_for_status()
                data = r.json()
                answer = data["message"]["content"].strip()
            else:
                return "❌ Weder Python-Library noch requests verfügbar."

            # NEU v10.4: Prüfe auf AERA_BEFEHL und führe aus!
            if execute_tools and self.command_parser:
                cmd_result = self._extract_and_execute(answer)
                if cmd_result:
                    return cmd_result

            # Speichere in Historie
            if use_history:
                with self._lock:
                    self.conversation_history.append({
                        "role": "user",
                        "content": prompt
                    })
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": answer
                    })
                    # Begrenze Historie
                    if len(self.conversation_history) > self.max_history * 2:
                        self.conversation_history = self.conversation_history[-self.max_history * 2:]

            self._last_response = answer
            return answer

        except Exception as e:
            error_msg = f"❌ LLM-Fehler: {str(e)}"
            print(f"[Lokale LLMs] {error_msg}")
            return error_msg


    def _extract_and_execute(self, answer: str) -> Optional[str]:
        """
        NEU v10.4: Extrahiert AERA_BEFEHL aus der Antwort und führt ihn aus.
        Sucht nach AERA_BEFEHL: <befehl> im Text und führt den Befehl aus.
        Gibt das Ergebnis zurück oder None wenn kein Befehl gefunden.
        """
        import re

        # Suche nach AERA_BEFEHL: pattern
        patterns = [
            r'AERA_BEFEHL:\s*(.+)',
            r'AERA BEFEHL:\s*(.+)',
            r'BEFEHL:\s*(.+)',
            r'AERA_CMD:\s*(.+)',
            r'CMD:\s*(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, answer, re.IGNORECASE)
            if match:
                cmd = match.group(1).strip()
                print(f"[OllamaAI] AERA-Befehl erkannt: '{cmd}'")

                # Führe den Befehl über den CommandParser aus
                if self.command_parser:
                    try:
                        result = self.command_parser.parse(cmd)
                        if result:
                            if isinstance(result, list):
                                return "\n".join(result)
                            return f"🧠 qwen hat ausgeführt: {cmd}" + "\n\n" + str(result)
                    except Exception as e:
                        print(f"[OllamaAI] Befehlsausführung fehlgeschlagen: {e}")
                        return f"🧠 qwen wollte ausführen: {cmd}" + "\n❌ Fehler: " + str(e)

        return None

    def ask_with_tools(self, prompt: str, use_history: bool = True) -> str:
        """
        NEU v10.4: Fragt qwen und lässt es AERA-Befehle direkt ausführen!
        Dies ist die bevorzugte Methode für Befehlsausführung.
        """
        return self.ask(prompt, use_history=use_history, execute_tools=True)
    def ask_streaming(self, prompt: str, chunk_callback=None) -> str:
        """
        Streaming-Antwort von lokalen LLMs (zeigt Antwort zeichenweise an).

        Args:
            prompt: Die Benutzeranfrage
            chunk_callback: Funktion die bei jedem Chunk aufgerufen wird

        Returns:
            Die vollständige Antwort
        """
        if not self.available:
            return "❌ Lokale LLMs nicht verfügbar."

        full_answer = ""

        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]

            if OLLAMA_OK:
                stream = ollama.chat(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    options={"num_predict": self.max_tokens, "temperature": 0.7}
                )
                for chunk in stream:
                    text = chunk["message"]["content"]
                    full_answer += text
                    if chunk_callback:
                        chunk_callback(text)

            elif REQUESTS_OK:
                r = requests.post(
                    f"{self.host}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": True,
                        "options": {"num_predict": self.max_tokens, "temperature": 0.7}
                    },
                    stream=True,
                    timeout=60
                )
                for line in r.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            text = data["message"]["content"]
                            full_answer += text
                            if chunk_callback:
                                chunk_callback(text)
                        except:
                            pass

            # NEU v10.4: Prüfe auf AERA_BEFEHL in Streaming-Antwort
            if self.command_parser:
                cmd_result = self._extract_and_execute(full_answer)
                if cmd_result:
                    return cmd_result

            return full_answer.strip()

        except Exception as e:
            return f"❌ Streaming-Fehler: {str(e)}"

    def clear_history(self):
        """Löscht die Konversationshistorie."""
        with self._lock:
            self.conversation_history.clear()
        return "🗑 Konversationshistorie gelöscht."

    def get_status(self) -> str:
        """Gibt den Status der lokalen LLM-Integration zurück."""
        status = []
        status.append("🧠 LOKALE LLM ENGINE STATUS")
        status.append("=" * 30)
        status.append(f"Modell: {self.model}")
        status.append(f"Host: {self.host}")
        status.append(f"Verfügbar: {'✅ Ja' if self.available else '❌ Nein'}")
        status.append(f"Aktiviert: {'✅ Ja' if self.enabled else '🔕 Nein'}")
        status.append(f"Token-Limit: {self.max_tokens}")
        status.append(f"Historie-Einträge: {len(self.conversation_history)}")
        status.append(f"Python-Library: {'✅' if OLLAMA_OK else '❌'}")
        status.append(f"REST-API: {'✅' if REQUESTS_OK else '❌'}")
        status.append(f"Tool-Ausführung: {'✅' if self.command_parser else '❌'}")
        return "\n".join(status)

    def toggle(self):
        """Schaltet lokale LLM-Integration ein/aus."""
        self.enabled = not self.enabled
        CFG.set("ollama_enabled", self.enabled)
        status = "aktiviert" if self.enabled else "deaktiviert"
        return f"🧠 Lokale LLM-Integration {status}."

    def set_max_tokens(self, limit: int):
        """Setzt das Token-Limit."""
        self.max_tokens = max(50, min(2000, limit))
        CFG.set("ollama_max_tokens", self.max_tokens)
        return f"Token-Limit auf {self.max_tokens} gesetzt."

    def set_command_parser(self, parser):
        """NEU v10.4: Setzt den CommandParser für Tool-Ausführung."""
        self.command_parser = parser
        return "✅ CommandParser verbunden. qwen kann jetzt AERA-Befehle ausführen!"


# ═══════════════════════════════════════════════════════════════════════════════
#  WAKE-WORD FUZZY DETECTOR
# ═══════════════════════════════════════════════════════════════════════════════


class WakeWordDetector:
    VARIANTS = [
        'aera', 'aero', 'aere', 'aria', 'aira',
        'ahera', 'aeira', 'eira', 'erra', 'aerah', 'ayra', 'aarra', 'aerra',
    ]
    THRESHOLD = 0.82

    def __init__(self, wake_word: str = "aera"):
        self.wake_word     = wake_word.lower()
        self._variants_set = set(self.VARIANTS)

    def _seq_sim(self, a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a, b).ratio()

    def _token_matches(self, token: str) -> bool:
        if len(token) < 3:
            return False
        if token == self.wake_word:
            return True
        if token in self._variants_set:
            return True
        if FUZZY_OK:
            for v in self.VARIANTS:
                if fuzz.ratio(token, v) >= int(self.THRESHOLD * 100):
                    return True
        else:
            for v in self.VARIANTS:
                if self._seq_sim(token, v) >= self.THRESHOLD:
                    return True
        return False

    def contains_wake_word(self, text: str) -> bool:
        text = FILLER.clean(text).lower().strip()
        if not text:
            return False
        if self.wake_word in text.split():
            return True
        tokens = re.split(r'[\s,\.!?]+', text)
        for tok in tokens:
            if self._token_matches(tok):
                return True
        return False

    def strip_wake_word(self, text: str) -> str:
        text  = FILLER.clean(text)
        words = text.split()
        result = []
        wake_found = False
        for w in words:
            wl = w.lower().strip(',.!?')
            if self._token_matches(wl):
                wake_found = True
            else:
                result.append(w)
        cleaned = ' '.join(result).strip(' ,.')
        cleaned = FILLER.clean(cleaned)
        if wake_found and not cleaned:
            return ""
        return cleaned


# ═══════════════════════════════════════════════════════════════════════════════
#  DEEP FILE SEARCH
# ═══════════════════════════════════════════════════════════════════════════════

class DeepFileSearch:
    SEARCH_DIRS = [str(Path.home() / d) for d in ["Desktop", "Documents", "Downloads"]]
    SKIP_DIRS   = {".git", "__pycache__", "node_modules", "AppData", "Library",
                   "Windows", "System32", "SysWOW64"}
    TEXT_EXTS = {
        '.txt', '.md', '.py', '.js', '.ts', '.html', '.htm', '.css',
        '.json', '.csv', '.xml', '.log', '.ini', '.cfg', '.yaml', '.yml',
        '.bat', '.sh', '.sql', '.rst', '.tex', '.rtf', '.c', '.cpp',
        '.h', '.java', '.rb', '.go', '.php', '.ps1', '.vbs', '.toml',
        '.properties', '.env', '.gitignore', '.dockerfile',
    }

    def fuzzy_score(self, query: str, text: str) -> int:
        """Verbesserte Fuzzy-Suche: Token-Set-Ratio für bessere Namensmatches."""
        q = query.lower().strip()
        t = text.lower().strip()
        if not q or not t:
            return 0
        if q == t:
            return 100
        # Exaktes Substring → höchste Priorität
        if q in t:
            return 95 + int(5 * len(q) / len(t))
        if t in q:
            return 85
        # Fuzzy via thefuzz (bessere Algorithmen)
        if FUZZY_OK:
            # token_set_ratio ignoriert Wort-Reihenfolge und Duplikate → perfekt für Dateinamen
            ts = fuzz.token_set_ratio(q, t)
            pr = fuzz.partial_ratio(q, t)
            wr = fuzz.WRatio(q, t)
            # Gewichtung: token_set_ratio stärker gewichtet für Namensmatches
            return int(max(ts * 0.5 + pr * 0.3 + wr * 0.2, ts, pr, wr))
        # Fallback: verbesserter SequenceMatcher
        sm = difflib.SequenceMatcher(None, q, t)
        ratio = sm.ratio()
        # Bonus für längste gemeinsame Substring
        match = sm.find_longest_match(0, len(q), 0, len(t))
        lcs_bonus = 0
        if match.size >= 3:
            lcs_bonus = min(15, match.size * 2)
        return int(ratio * 100) + lcs_bonus

    def search_files(self, query: str, max_results: int = 10) -> List[Dict]:
        """Verbesserte Dateisuche: smarte Namens-Matching, Ähnlichkeits-Ranking."""
        query_clean = query.strip()
        q_lower = query_clean.lower()
        extra_dirs = [str(Path.home() / d.lstrip("~/"))
                      for d in CFG.get("search_dirs", self.SEARCH_DIRS)]
        search_roots = list(set(self.SEARCH_DIRS + extra_dirs))

        all_files: List[Path] = []
        for root in search_roots:
            root_path = Path(root).expanduser()
            if not root_path.exists():
                continue
            for fp in self._walk(root_path):
                all_files.append(fp)

        file_scores: Dict[str, Dict] = {}
        for fp in all_files:
            name_lower = fp.name.lower()
            stem_lower = fp.stem.lower()
            parent_lower = fp.parent.name.lower()

            # 1. Exakter Treffer (Name)
            if q_lower == name_lower:
                score = 100
                source = "exakter_name"
            elif q_lower == stem_lower:
                score = 98
                source = "exakter_stem"
            # 2. Substring im Namen (stark bevorzugt)
            elif q_lower in name_lower:
                score = 90 + int(8 * len(q_lower) / len(name_lower))
                source = "name_substring"
            elif q_lower in stem_lower:
                score = 85 + int(8 * len(q_lower) / len(stem_lower))
                source = "stem_substring"
            # 3. Substring im Ordnernamen
            elif q_lower in parent_lower:
                score = 50 + int(20 * len(q_lower) / len(parent_lower))
                source = "ordner_substring"
            # 4. Fuzzy-Matching (nur wenn nötig)
            else:
                name_score = self.fuzzy_score(query_clean, fp.name)
                stem_score = self.fuzzy_score(query_clean, fp.stem)
                parent_score = self.fuzzy_score(query_clean, fp.parent.name)
                score = max(name_score, stem_score, int(parent_score * 0.5))
                source = "dateiname"

            file_scores[str(fp)] = {
                "path": str(fp), "name": fp.name,
                "score": score, "source": source, "snippet": "",
            }

        # Inhaltssuche als Ergänzung (niedriger priorisiert)
        content_hits = self._search_all_content(query_clean, all_files)
        for hit in content_hits:
            path = hit["path"]
            if path in file_scores:
                # Inhalt nur boosten, nicht überschreiben wenn Name schon gut matched
                if file_scores[path]["score"] < 70:
                    file_scores[path].update({
                        "score": max(file_scores[path]["score"], hit["score"]),
                        "source": hit["source"],
                        "snippet": hit["snippet"]})
                elif hit["snippet"] and not file_scores[path]["snippet"]:
                    file_scores[path]["snippet"] = hit["snippet"]
            else:
                file_scores[path] = hit

        # Sortieren: Score absteigend, dann nach Name-Länge (kürzere Namen bevorzugt = exaktere Treffer)
        sorted_results = sorted(
            file_scores.values(),
            key=lambda x: (-x["score"], len(x["name"]))
        )
        # Nur Ergebnisse mit Score >= 20 zurückgeben (keine Müll-Treffer)
        good = [r for r in sorted_results if r["score"] >= 20]
        return (good if good else sorted_results)[:max_results]

    def _walk(self, root: Path):
        try:
            for item in root.iterdir():
                if item.is_dir() and item.name not in self.SKIP_DIRS:
                    try:
                        yield from self._walk(item)
                    except PermissionError:
                        pass
                elif item.is_file():
                    yield item
        except PermissionError:
            pass

    def _search_all_content(self, query: str, files: List[Path]) -> List[Dict]:
        hits = []
        for fp in files:
            try:
                ext = fp.suffix.lower()
                snippet = ""
                source_type = "inhalt"
                if ext in self.TEXT_EXTS:
                    snippet     = self._search_text_file(fp, query)
                    source_type = f"{ext.lstrip('.')}-inhalt"
                elif ext in ('.xlsx', '.xls') and EXCEL_OK:
                    snippet     = self._search_excel(fp, query)
                    source_type = "excel-inhalt"
                elif ext == '.pdf' and PDF_OK:
                    snippet     = self._search_pdf(fp, query)
                    source_type = "pdf-inhalt"
                elif ext in ('.docx', '.doc'):
                    snippet     = self._search_docx(fp, query)
                    source_type = "docx-inhalt"
                if snippet:
                    raw_score = self.fuzzy_score(query, snippet)
                    score = max(75, raw_score)
                    hits.append({
                        "path": str(fp), "name": fp.name,
                        "score": score, "source": source_type,
                        "snippet": snippet[:120],
                    })
            except Exception:
                pass
        return hits

    def _search_text_file(self, path: Path, query: str) -> str:
        try:
            if path.stat().st_size > 5 * 1024 * 1024:
                return ""
            content = path.read_text(encoding="utf-8", errors="ignore")
            q_low   = query.lower()
            c_low   = content.lower()
            if q_low in c_low:
                idx = c_low.index(q_low)
                return content[max(0, idx - 40): idx + 100].replace("\n", " ")
            if FUZZY_OK and fuzz.partial_ratio(q_low, c_low) >= 72:
                score = fuzz.partial_ratio(q_low, c_low)
                return f"Ähnlicher Inhalt gefunden ({score}%)"
        except Exception:
            pass
        return ""

    def _search_docx(self, path: Path, query: str) -> str:
        try:
            with zipfile.ZipFile(str(path), "r") as z:
                if "word/document.xml" not in z.namelist():
                    return ""
                with z.open("word/document.xml") as f:
                    tree  = ET.parse(f)
                    root  = tree.getroot()
                    ns    = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                    texts = [elem.text for elem in root.iter(f"{ns}t") if elem.text]
                    content = " ".join(texts)
                    if query.lower() in content.lower():
                        idx = content.lower().index(query.lower())
                        return content[max(0, idx - 40): idx + 100].replace("\n", " ")
        except Exception:
            pass
        return ""

    def _search_excel(self, path: Path, query: str) -> str:
        try:
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    for cell in row:
                        if cell and query.lower() in str(cell).lower():
                            return f"Tabelle: {str(cell)[:80]}"
        except Exception:
            pass
        return ""

    def _search_pdf(self, path: Path, query: str) -> str:
        try:
            doc = fitz.open(str(path))
            for page in doc:
                text = page.get_text()
                if query.lower() in text.lower():
                    idx = text.lower().index(query.lower())
                    return text[max(0, idx - 30): idx + 80].replace("\n", " ")
        except Exception:
            pass
        return ""


DEEP_SEARCH = DeepFileSearch()


# ═══════════════════════════════════════════════════════════════════════════════
#  UNIVERSAL APP ENGINE v10 — HS
# ═══════════════════════════════════════════════════════════════════════════════

class UniversalAppEngine:
    """
    Findet, öffnet und schließt jede installierte App ohne hartes Mapping.
    Nutzt:
      Windows: Registry (App-Pfade), Start-Menü, PATH, winget, where.exe, Glob
      macOS:   /Applications, ~/Applications, Spotlight (mdfind), PATH
    Mit App-Cache für Geschwindigkeit.
    """

    def __init__(self):
        self._cache: Dict[str, str] = {}          # name_lower → exe_path
        self._cache_ts: float       = 0
        self._cache_ttl: float      = 300         # 5 min Cache-Gültigkeit
        self._lock = threading.Lock()
        self._load_cache()
        # Hintergrund-Scan beim Start
        threading.Thread(target=self._build_cache, daemon=True).start()

    # ── Cache ──────────────────────────────────────────────────────────────────

    def _load_cache(self):
        try:
            if APP_CACHE_FILE.exists():
                with open(APP_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._cache    = data.get("apps", {})
                    self._cache_ts = data.get("ts", 0)
        except Exception:
            pass

    def _save_cache(self):
        try:
            with open(APP_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"apps": self._cache, "ts": self._cache_ts}, f,
                          ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _build_cache(self):
        """Scannt alle installierten Apps im Hintergrund."""
        apps = {}
        if IS_WINDOWS:
            apps.update(self._scan_windows())
        else:
            apps.update(self._scan_macos())
        with self._lock:
            self._cache    = apps
            self._cache_ts = time.time()
        self._save_cache()

    def refresh(self) -> str:
        """Erzwingt einen neuen App-Scan."""
        self._build_cache()
        return f"App-Cache aktualisiert. {len(self._cache)} Apps gefunden."

    # ── Windows Scan ──────────────────────────────────────────────────────────

    def _scan_windows(self) -> Dict[str, str]:
        apps = {}

        # 1. Start-Menü Shortcuts (.lnk)
        start_dirs = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
        ]
        for sd in start_dirs:
            if sd.exists():
                for lnk in sd.rglob("*.lnk"):
                    name = lnk.stem.lower()
                    apps[name] = str(lnk)

        # 2. Registry: installierte Programme
        try:
            import winreg
            keys = [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths",
            ]
            for key_path in keys:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                    i = 0
                    while True:
                        try:
                            sub_name = winreg.EnumKey(key, i)
                            sub_key  = winreg.OpenKey(key, sub_name)
                            try:
                                val, _ = winreg.QueryValueEx(sub_key, "")
                                name   = sub_name.lower().replace(".exe", "")
                                apps[name] = val
                            except Exception:
                                pass
                            winreg.CloseKey(sub_key)
                            i += 1
                        except OSError:
                            break
                    winreg.CloseKey(key)
                except Exception:
                    pass
        except ImportError:
            pass

        # 3. Program Files Scan (exe-Dateien)
        prog_dirs = [
            Path("C:/Program Files"),
            Path("C:/Program Files (x86)"),
            Path.home() / "AppData/Local/Programs",
            Path.home() / "AppData/Local",
            Path.home() / "AppData/Roaming",
        ]
        for pd in prog_dirs:
            if pd.exists():
                try:
                    for exe in pd.rglob("*.exe"):
                        name = exe.stem.lower()
                        if name not in apps and len(name) > 2:
                            apps[name] = str(exe)
                except PermissionError:
                    pass

        # 4. PATH
        for cmd in os.environ.get("PATH", "").split(os.pathsep):
            try:
                p = Path(cmd)
                if p.exists():
                    for exe in p.glob("*.exe"):
                        name = exe.stem.lower()
                        if name not in apps:
                            apps[name] = str(exe)
            except Exception:
                pass

        return apps

    # ── macOS Scan ────────────────────────────────────────────────────────────

    def _scan_macos(self) -> Dict[str, str]:
        apps = {}

        # 1. /Applications + ~/Applications
        app_dirs = [Path("/Applications"), Path.home() / "Applications",
                    Path("/System/Applications")]
        for ad in app_dirs:
            if ad.exists():
                try:
                    for app in ad.rglob("*.app"):
                        name = app.stem.lower()
                        apps[name] = str(app)
                except Exception:
                    pass

        # 2. Spotlight mdfind
        try:
            r = subprocess.run(
                ["mdfind", "kMDItemKind == 'Application'"],
                capture_output=True, text=True, timeout=10)
            for line in r.stdout.splitlines():
                p = Path(line.strip())
                if p.suffix == ".app":
                    name = p.stem.lower()
                    if name not in apps:
                        apps[name] = str(p)
        except Exception:
            pass

        # 3. PATH
        for cmd in os.environ.get("PATH", "").split(os.pathsep):
            try:
                p = Path(cmd)
                if p.exists():
                    for exe in p.iterdir():
                        if exe.is_file() and os.access(exe, os.X_OK):
                            apps[exe.name.lower()] = str(exe)
            except Exception:
                pass

        return apps

    # ── Fuzzy-Suche ───────────────────────────────────────────────────────────

    def _find_best_match(self, query: str) -> Optional[Tuple[str, str, int]]:
        """
        Gibt (name, path, score) zurück oder None.
        Score 0-100.
        """
        q = query.lower().strip()

        with self._lock:
            cache = dict(self._cache)

        if not cache:
            return None

        # 1. Exakter Treffer
        if q in cache:
            return (q, cache[q], 100)

        # 2. Starts-with
        starts = [(k, v) for k, v in cache.items() if k.startswith(q)]
        if starts:
            best = sorted(starts, key=lambda x: len(x[0]))[0]
            return (best[0], best[1], 95)

        # 3. Contains
        contains = [(k, v) for k, v in cache.items() if q in k]
        if contains:
            best = sorted(contains, key=lambda x: len(x[0]))[0]
            return (best[0], best[1], 85)

        # 4. Fuzzy (v10: Threshold 80 + LCS-Validierung ≥3 Zeichen)
        if FUZZY_OK:
            keys   = list(cache.keys())
            result = fuzz_process.extractOne(q, keys, scorer=fuzz.partial_ratio)
            if result and result[1] >= 80:
                name  = result[0]
                score = result[1]
                # Zusätzliche Validierung: min. 3 Zeichen gemeinsamer Substring
                sm = difflib.SequenceMatcher(None, q, name)
                match = sm.find_longest_match(0, len(q), 0, len(name))
                if match.size >= 3:
                    return (name, cache[name], score)
        else:
            best_score = 0
            best_name  = None
            for k in cache:
                s = int(difflib.SequenceMatcher(None, q, k).ratio() * 100)
                if s > best_score:
                    best_score = s
                    best_name  = k
            if best_name and best_score >= 80:
                # Zusätzliche Validierung: min. 3 Zeichen gemeinsamer Substring
                sm = difflib.SequenceMatcher(None, q, best_name)
                match = sm.find_longest_match(0, len(q), 0, len(best_name))
                if match.size >= 3:
                    return (best_name, cache[best_name], best_score)

        return None

    # ── Öffnen ────────────────────────────────────────────────────────────────

    def open_app(self, query: str) -> str:
        """Öffnet eine App nach Name — findet sie, egal wie sie heißt."""
        match = self._find_best_match(query)
        if match:
            name, path, score = match
            try:
                if IS_WINDOWS:
                    os.startfile(path)
                else:
                    subprocess.Popen(["open", path])
                return f"'{name}' geöffnet ({score}% Treffer). Pfad: {path[:60]}"
            except Exception as e:
                # Fallback: direkt als Befehl
                try:
                    subprocess.Popen([path])
                    return f"'{name}' gestartet."
                except Exception as e2:
                    return f"Fehler beim Öffnen von '{name}': {e2}"

        # Letzter Fallback: OS-Standard
        try:
            if IS_WINDOWS:
                # winget search
                r = subprocess.run(["where", query], capture_output=True, text=True, timeout=5,
                                   creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0)
                if r.returncode == 0 and r.stdout.strip():
                    path = r.stdout.strip().split("\n")[0]
                    subprocess.Popen([path])
                    return f"'{query}' gestartet via PATH."
                os.startfile(query)
                return f"'{query}' geöffnet."
            else:
                r = subprocess.run(["open", "-a", query], capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    return f"'{query}' geöffnet."
                # which
                r2 = subprocess.run(["which", query], capture_output=True, text=True, timeout=3)
                if r2.returncode == 0:
                    subprocess.Popen([query])
                    return f"'{query}' gestartet."
                return f"App '{query}' nicht gefunden. Cache aktualisieren? Sage: apps aktualisieren"
        except Exception as e:
            return f"App '{query}' nicht gefunden: {e}"

    # ── Schließen ─────────────────────────────────────────────────────────────

    def close_app(self, query: str) -> str:
        """Schließt eine laufende App nach Namen — fuzzy."""
        q = query.lower().strip()
        closed = []

        if IS_WINDOWS:
            # Liste aller laufenden Prozesse
            try:
                r = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                                   capture_output=True, text=True, timeout=8,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                for line in r.stdout.splitlines():
                    parts = line.split('","')
                    if not parts:
                        continue
                    proc_name = parts[0].strip('"').lower()
                    proc_stem = proc_name.replace(".exe", "")

                    # Prüfe Treffer
                    match_score = 0
                    if q == proc_stem or q == proc_name:
                        match_score = 100
                    elif q in proc_stem or proc_stem.startswith(q):
                        match_score = 85
                    elif FUZZY_OK:
                        match_score = fuzz.partial_ratio(q, proc_stem)
                    else:
                        match_score = int(difflib.SequenceMatcher(None, q, proc_stem).ratio() * 100)

                    if match_score >= 60:
                        subprocess.run(["taskkill", "/f", "/im", parts[0].strip('"')],
                                       capture_output=True,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
                        closed.append(f"{parts[0].strip(chr(34))} ({match_score}%)")
            except Exception as e:
                return f"Fehler beim Schließen: {e}"

        else:  # macOS
            try:
                r = subprocess.run(["ps", "-Ao", "pid,comm"],
                                   capture_output=True, text=True, timeout=8)
                for line in r.stdout.splitlines()[1:]:
                    parts = line.strip().split(None, 1)
                    if len(parts) < 2:
                        continue
                    pid       = parts[0]
                    proc_name = Path(parts[1]).name.lower()

                    match_score = 0
                    if q == proc_name:
                        match_score = 100
                    elif q in proc_name or proc_name.startswith(q):
                        match_score = 85
                    elif FUZZY_OK:
                        match_score = fuzz.partial_ratio(q, proc_name)
                    else:
                        match_score = int(difflib.SequenceMatcher(None, q, proc_name).ratio() * 100)

                    if match_score >= 60:
                        subprocess.run(["kill", pid], capture_output=True)
                        closed.append(f"{proc_name} (PID {pid}, {match_score}%)")
            except Exception as e:
                return f"Fehler beim Schließen: {e}"

        if closed:
            return f"Geschlossen: {', '.join(closed[:5])}"
        return f"Kein laufender Prozess für '{query}' gefunden."

    # ── App-Liste ─────────────────────────────────────────────────────────────

    def list_running(self) -> str:
        """Zeigt alle laufenden Apps."""
        try:
            if IS_WINDOWS:
                r = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                                   capture_output=True, text=True, timeout=8,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                procs = []
                for line in r.stdout.splitlines()[:15]:
                    parts = line.split('","')
                    if len(parts) >= 5:
                        name = parts[0].strip('"')
                        mem  = parts[4].strip('"')
                        procs.append(f"  {name[:35]}: {mem}")
                return "Laufende Prozesse:\n" + "\n".join(procs)
            else:
                r = subprocess.run(["ps", "-Ao", "pid,pcpu,pmem,comm", "-r"],
                                   capture_output=True, text=True, timeout=8)
                lines = r.stdout.strip().split("\n")[1:16]
                return "Laufende Prozesse:\n" + "\n".join(f"  {l}" for l in lines)
        except Exception as e:
            return f"Prozessliste-Fehler: {e}"

    def list_installed(self, filter_q: str = "") -> str:
        """Listet installierte Apps aus dem Cache."""
        with self._lock:
            apps = dict(self._cache)
        if not apps:
            return "App-Cache leer. Sage: apps aktualisieren"
        names = sorted(apps.keys())
        if filter_q:
            names = [n for n in names if filter_q.lower() in n]
        total = len(names)
        preview = names[:20]
        lines = [f"  • {n}" for n in preview]
        suffix = f"\n  ... und {total - 20} weitere." if total > 20 else ""
        return f"Installierte Apps ({total} gesamt):\n" + "\n".join(lines) + suffix


APP_ENGINE = UniversalAppEngine()



# ═══════════════════════════════════════════════════════════════════════════════
#  NATURAL TTS RESPONSES v10.2 — Menschliche, variierende Antworten
# ═══════════════════════════════════════════════════════════════════════════════

class NaturalTTSResponses:
    """
    v10.2: Erzeugt natürliche, variierende TTS-Antworten statt technischer Pfade.
    """

    # App-Öffnen: Variierende, menschliche Formulierungen
    APP_OPEN = {
        "whatsapp": [
            "WhatsApp ist bereit für dich.",
            "WhatsApp ist jetzt geöffnet.",
            "Deine Nachrichten warten auf dich.",
            "WhatsApp läuft.",
        ],
        "chrome": [
            "Chrome ist startklar.",
            "Dein Browser ist geöffnet.",
            "Chrome läuft jetzt.",
            "Surfen kann beginnen.",
        ],
        "spotify": [
            "Spotify ist bereit. Viel Spaß beim Hören!",
            "Deine Musik wartet auf dich.",
            "Spotify läuft.",
            "Zeit für gute Musik.",
        ],
        "outlook": [
            "Outlook ist geöffnet. Viel Erfolg mit deinen Mails!",
            "Dein Postfach ist bereit.",
            "Outlook läuft.",
            "Zeit für E-Mails.",
        ],
        "teams": [
            "Teams ist startklar.",
            "Dein Team wartet auf dich.",
            "Teams läuft jetzt.",
            "Bereit für die Zusammenarbeit.",
        ],
        "excel": [
            "Excel ist geöffnet. Viel Erfolg mit deiner Tabelle!",
            "Deine Tabellenkalkulation ist bereit.",
            "Excel läuft.",
            "Zeit für Zahlen.",
        ],
        "word": [
            "Word ist bereit für dich.",
            "Dein Texteditor ist geöffnet.",
            "Word läuft jetzt.",
            "Zeit zum Schreiben.",
        ],
        "notepad": [
            "Notepad ist geöffnet.",
            "Dein Editor ist bereit.",
            "Notepad läuft.",
        ],
        "terminal": [
            "Terminal ist geöffnet.",
            "Die Kommandozeile wartet auf dich.",
            "Terminal läuft.",
        ],
        "default": [
            "{app} ist bereit für dich.",
            "{app} ist jetzt geöffnet.",
            "{app} läuft.",
            "{app} ist startklar.",
            "{app} wartet auf dich.",
        ],
    }

    # App-Schließen
    APP_CLOSE = {
        "default": [
            "{app} wurde geschlossen.",
            "{app} ist beendet.",
            "{app} wurde beendet.",
            "{app} läuft nicht mehr.",
        ],
    }

    # Datei-Suche Erfolg
    FILE_FOUND = [
        "Ich habe die Datei gefunden. Sie ist bereit für dich.",
        "Datei gefunden und markiert.",
        "Die Datei wartet auf dich im Explorer.",
        "Gefunden! Die Datei ist markiert.",
    ]

    # Datei-Suche Misserfolg
    FILE_NOT_FOUND = [
        "Ich habe die Datei leider nicht gefunden. Soll ich woanders suchen?",
        "Die Datei ist mir nicht bekannt. Vielleicht unter einem anderen Namen?",
        "Ich konnte die Datei nicht finden. Möchtest du eine erweiterte Suche?",
    ]

    # Timer
    TIMER_SET = [
        "Timer ist gestellt.",
        "Der Countdown läuft.",
        "Timer aktiv. Ich sage Bescheid.",
        "Alles klar, ich erinnere dich.",
    ]

    # System-Befehle
    SYSTEM = {
        "screenshot": [
            "Screenshot gemacht und gespeichert.",
            "Bildschirmfoto erledigt.",
            "Screenshot ist auf dem Desktop.",
        ],
        "shutdown": [
            "Der PC wird heruntergefahren.",
            "Bis gleich. Der PC fährt runter.",
            "Herunterfahren eingeleitet.",
        ],
        "restart": [
            "Der PC startet neu.",
            "Neustart wird durchgeführt.",
            "Gleich geht es weiter. Neustart läuft.",
        ],
        "battery": [
            "Hier ist der Akku-Status.",
            "Dein Akku-Stand.",
            "So viel Power hast du noch.",
        ],
    }

    # Allgemeine Bestätigungen
    CONFIRMATIONS = [
        "Erledigt.",
        "Gemacht.",
        "Alles klar.",
        "Verstanden.",
        "Ich kümmere mich drum.",
        "Passt.",
    ]

    @classmethod
    def get_app_open(cls, app_name: str) -> str:
        """Gibt eine natürliche Antwort für App-Öffnen zurück."""
        app_lower = app_name.lower()
        # Suche exakte Übereinstimmung
        for key, responses in cls.APP_OPEN.items():
            if key in app_lower or app_lower in key:
                return random.choice(responses)
        # Fallback mit Platzhalter
        return random.choice(cls.APP_OPEN["default"]).format(app=app_name)

    @classmethod
    def get_app_close(cls, app_name: str) -> str:
        """Gibt eine natürliche Antwort für App-Schließen zurück."""
        return random.choice(cls.APP_CLOSE["default"]).format(app=app_name)

    @classmethod
    def get_file_found(cls) -> str:
        return random.choice(cls.FILE_FOUND)

    @classmethod
    def get_file_not_found(cls) -> str:
        return random.choice(cls.FILE_NOT_FOUND)

    @classmethod
    def get_timer(cls) -> str:
        return random.choice(cls.TIMER_SET)

    @classmethod
    def get_system(cls, action: str) -> str:
        action_lower = action.lower()
        for key, responses in cls.SYSTEM.items():
            if key in action_lower:
                return random.choice(responses)
        return random.choice(cls.CONFIRMATIONS)

    @classmethod
    def get_confirmation(cls) -> str:
        return random.choice(cls.CONFIRMATIONS)

    @classmethod
    def naturalize(cls, text: str) -> str:
        """
        Wandelt technische TTS-Ausgaben in natürliche um.
        Erkennt Muster und ersetzt sie durch menschliche Formulierungen.
        """
        if not CFG.get("natural_tts", True):
            return text

        text_lower = text.lower()

        # App-Öffnen erkennen
        m = re.search(r"'([^']+)'\s+geöffnet", text_lower)
        if m and "pfad" not in text_lower:
            app_name = m.group(1)
            return cls.get_app_open(app_name)

        # App-Schließen erkennen
        m = re.search(r"geschlossen:\s*([^,]+)", text_lower)
        if m:
            app_name = m.group(1).strip()
            return cls.get_app_close(app_name)

        # Datei gefunden
        if "gefunden" in text_lower and "übereinstimmung" in text_lower:
            return cls.get_file_found()

        # Datei nicht gefunden
        if "nicht gefunden" in text_lower and "entschuldigung" in text_lower:
            return cls.get_file_not_found()

        # Timer
        if "timer" in text_lower and "min" in text_lower:
            return cls.get_timer()

        # Screenshot
        if "screenshot" in text_lower:
            return cls.get_system("screenshot")

        # Shutdown
        if "heruntergefahren" in text_lower:
            return cls.get_system("shutdown")

        # Restart
        if "neustart" in text_lower or "neu starten" in text_lower:
            return cls.get_system("restart")

        # Akku
        if "akku" in text_lower or "batterie" in text_lower:
            return cls.get_system("battery")

        return text


# ═══════════════════════════════════════════════════════════════════════════════
#  TTS MANAGER v10.2
# ═══════════════════════════════════════════════════════════════════════════════

class TTSManager:
    """
    v10.2: Natural TTS mit variierenden, menschlichen Antworten.
    Kristallklare, natürliche deutsche Stimme ohne Roboter-Effekt.
    Fallback: gTTS → pyttsx3 → System-Fallback
    """

    def __init__(self):
        self.queue = []
        self.lock  = threading.Lock()
        self.busy  = False
        self.muted = CFG.get("tts_muted", False)
        self._pyttsx3_engine = None
        self._init_pyttsx3()
        self._edge_voice = CFG.get("tts_voice", "de-DE-KatjaNeural")
        self._edge_rate = "+10%"
        self._edge_pitch = "+0Hz"

    def _init_pyttsx3(self):
        if PYTTSX3_OK:
            try:
                self._pyttsx3_engine = pyttsx3.init()
                self._pyttsx3_engine.setProperty("rate", 165)
                voices = self._pyttsx3_engine.getProperty("voices")
                for v in voices:
                    if "german" in v.name.lower() or "de_" in v.id.lower() or "deutsch" in v.name.lower():
                        self._pyttsx3_engine.setProperty("voice", v.id)
                        break
            except Exception:
                self._pyttsx3_engine = None

    def speak(self, text: str):
        if self.muted or not text or len(text.strip()) < 2:
            return
        # NEU v10.2: Natürliche Antworten verwenden
        if CFG.get("natural_tts", True):
            text = NaturalTTSResponses.naturalize(text)
        clean = self._clean(self._truncate(text, 200))
        if len(clean.strip()) < 3:
            return
        with self.lock:
            self.queue.append(clean)
        if not self.busy:
            threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        self.busy = True
        while True:
            with self.lock:
                if not self.queue:
                    self.busy = False
                    return
                text = self.queue.pop(0)
            self._speak_text(text)

    def _speak_text(self, text: str):
        # ═══════════════════════════════════════════════════════════════
        #  PRIORITÄT 1: Edge-TTS (Microsoft Neural Voice) — CLEANEST
        # ═══════════════════════════════════════════════════════════════
        if EDGE_TTS_OK:
            try:
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp.close()

                async def _edge_speak():
                    communicate = edge_tts.Communicate(
                        text=text,
                        voice=self._edge_voice,
                        rate=self._edge_rate,
                        pitch=self._edge_pitch,
                    )
                    await communicate.save(tmp.name)

                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(_edge_speak())
                    loop.close()
                except RuntimeError:
                    asyncio.run(_edge_speak())

                if PLAYSOUND_OK:
                    playsound.playsound(tmp.name)
                else:
                    if IS_WINDOWS:
                        os.startfile(tmp.name)
                        time.sleep(len(text) * 0.08 + 1)
                    else:
                        subprocess.run(["afplay", tmp.name], timeout=30)

                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
                return
            except Exception as e:
                print(f"[TTS-Edge] Fehler: {e}")

        # ═══════════════════════════════════════════════════════════════
        #  PRIORITÄT 2: gTTS (Fallback)
        # ═══════════════════════════════════════════════════════════════
        if GTTS_OK and PLAYSOUND_OK:
            try:
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp.close()
                tts = gTTS(text=text, lang="de", slow=False)
                tts.save(tmp.name)
                playsound.playsound(tmp.name)
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
                return
            except Exception as e:
                print(f"[TTS-gTTS] Fehler: {e}")

        # ═══════════════════════════════════════════════════════════════
        #  PRIORITÄT 3: pyttsx3 (offline)
        # ═══════════════════════════════════════════════════════════════
        if self._pyttsx3_engine:
            try:
                self._pyttsx3_engine.say(text)
                self._pyttsx3_engine.runAndWait()
                return
            except Exception as e:
                print(f"[TTS-pyttsx3] Fehler: {e}")

        # ═══════════════════════════════════════════════════════════════
        #  PRIORITÄT 4: System-Fallback
        # ═══════════════════════════════════════════════════════════════
        try:
            if IS_MACOS:
                speed = CFG.get("tts_speed", 170)
                subprocess.run(["say", "-v", "Anna", "-r", str(speed), text], timeout=15)
            else:
                safe_text = text.replace('"', "'").replace('\n', ' ')
                subprocess.run([
                    "powershell", "-c",
                    f'Add-Type -AssemblyName System.Speech; '
                    f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                    f'$s.Rate = 2; $s.Speak("{safe_text}")'
                ], timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0)
        except Exception as e:
            print(f"[TTS-System] {e}")

    def _truncate(self, text: str, n: int) -> str:
        if len(text) <= n:
            return text
        t = text[:n]
        for p in [". ", "! ", "? "]:
            i = t.rfind(p)
            if i > n * 0.5:
                return t[:i + 1]
        return (t[:t.rfind(" ")] + "...") if " " in t[:n] else t[:n]

    def _clean(self, text: str) -> str:
        text = re.sub(r"\*+", "", text)
        text = re.sub(r"[\[\]\(\)]", "", text)
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"[•►◄╔╚╠╣║═⏱️✅⚠️❌🎄🛒👏◈▸●]", "", text)
        text = re.sub(r"^AERA:\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\[(\d+)%\]", r"\1 Prozent", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def clear(self):
        with self.lock:
            self.queue.clear()

    def toggle_mute(self):
        self.muted = not self.muted
        CFG.set("tts_muted", self.muted)
        return self.muted

    @property
    def engine_name(self) -> str:
        if EDGE_TTS_OK:
            return f"Edge-TTS ({self._edge_voice})"
        elif GTTS_OK and PLAYSOUND_OK:
            return "gTTS + playsound"
        elif self._pyttsx3_engine:
            return "pyttsx3 (offline)"
        elif IS_MACOS:
            return "macOS say"
        else:
            return "PowerShell TTS"


# ═══════════════════════════════════════════════════════════════════════════════
#  TIMER MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class TimerManager:
    def __init__(self, tts: TTSManager, on_done=None):
        self.tts      = tts
        self.on_done  = on_done
        self.timers   = {}
        self.lock     = threading.Lock()
        self._id      = 0
        self.stopwatch_start = None

    def set_timer(self, minutes: int, name: str = None) -> str:
        self._id += 1
        name = name or f"Timer {self._id}"
        end  = datetime.now() + timedelta(minutes=minutes)
        with self.lock:
            self.timers[name] = {"end": end, "minutes": minutes, "done": False}
        threading.Thread(target=self._countdown, args=(name,), daemon=True).start()
        return f"Timer '{name}' — {minutes} Min."

    def _countdown(self, name):
        while True:
            with self.lock:
                if name not in self.timers or self.timers[name]["done"]:
                    return
                if (self.timers[name]["end"] - datetime.now()).total_seconds() <= 0:
                    self.timers[name]["done"] = True
                    break
            time.sleep(1)
        self._finish(name)

    def _finish(self, name):
        if self.on_done:
            self.on_done(f"⏱ TIMER '{name}' ABGELAUFEN!")
        for _ in range(3):
            self.tts.speak(f"Achtung! Timer {name} abgelaufen!")
            time.sleep(3)

    def get_active(self):
        res = []
        with self.lock:
            for name, d in self.timers.items():
                if not d["done"]:
                    rem = max(0, int((d["end"] - datetime.now()).total_seconds()))
                    m, s = divmod(rem, 60)
                    res.append({"name": name,
                                "remaining": f"{m:02d}:{s:02d}",
                                "pct": rem / (d["minutes"] * 60)})
        return res

    def start_stopwatch(self):
        self.stopwatch_start = datetime.now()

    def get_stopwatch(self) -> str:
        if not self.stopwatch_start:
            return "00:00:00"
        t    = int((datetime.now() - self.stopwatch_start).total_seconds())
        m, s = divmod(t, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def stop_timer(self, name: str):
        with self.lock:
            if name in self.timers:
                self.timers[name]["done"] = True


# ═══════════════════════════════════════════════════════════════════════════════
#  PLATTFORM-BEFEHLE — v8 komplett + v9 NEU
# ═══════════════════════════════════════════════════════════════════════════════

class SystemCommands:

    @staticmethod
    def _run(cmd: List[str], capture: bool = True, timeout: int = 8) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout,
                                  creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0)
        except Exception:
            return subprocess.CompletedProcess(cmd, -1, "", "")

    @staticmethod
    def _popen(cmd: List[str]):
        try:
            kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WINDOWS else {}
            subprocess.Popen(cmd, **kwargs)
        except Exception as e:
            print(f"[Popen] {e}")

    @staticmethod
    def _open_file_or_url(target: str):
        if IS_WINDOWS:
            os.startfile(target)
        else:
            subprocess.Popen(["open", target])
    @staticmethod
    def _reveal_in_file_manager(target: str):
        """Öffnet den Datei-Manager/Finder und markiert die Datei, ohne sie zu öffnen."""
        if not os.path.exists(target):
            return
        try:
            if IS_WINDOWS:
                # Windows: explorer /select,"pfad" öffnet Explorer und markiert Datei
                subprocess.Popen(["explorer", "/select,", target],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                # macOS: open -R "pfad" öffnet Finder und markiert Datei
                subprocess.Popen(["open", "-R", target])
        except Exception as e:
            print(f"[Reveal] Fehler: {e}")
            # Fallback: einfach den Ordner öffnen
            try:
                parent = str(Path(target).parent)
                if IS_WINDOWS:
                    os.startfile(parent)
                else:
                    subprocess.Popen(["open", parent])
            except Exception:
                pass


    # ════════════════════════════════════════════════════════════════════
    #  SYSTEM
    # ════════════════════════════════════════════════════════════════════

    @staticmethod
    def shutdown(minutes: int = 1) -> str:
        try:
            if IS_WINDOWS:
                SystemCommands._run(["shutdown", "/s", "/t", str(minutes * 60)])
            else:
                SystemCommands._popen(["sudo", "shutdown", "-h", f"+{minutes}"])
            return f"PC wird in {minutes} Minuten heruntergefahren."
        except Exception as e:
            return f"Shutdown-Fehler: {e}"

    @staticmethod
    def restart() -> str:
        try:
            if IS_WINDOWS:
                SystemCommands._run(["shutdown", "/r", "/t", "5"])
            else:
                SystemCommands._popen(["sudo", "shutdown", "-r", "now"])
            return "Neustart wird eingeleitet."
        except Exception as e:
            return f"Neustart-Fehler: {e}"

    @staticmethod
    def sleep_system() -> str:
        """PC in den Schlafmodus versetzen."""
        try:
            if IS_WINDOWS:
                subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"])
                return "PC wechselt in den Schlafmodus."
            else:
                subprocess.Popen(["pmset", "sleepnow"])
                return "Mac wechselt in den Schlafmodus."
        except Exception as e:
            return f"Sleep-Fehler: {e}"

    @staticmethod
    def hibernate() -> str:
        """PC in den Ruhezustand versetzen."""
        try:
            if IS_WINDOWS:
                SystemCommands._run(["shutdown", "/h"])
                return "PC wechselt in den Ruhezustand."
            else:
                return "Hibernate nur auf Windows verfügbar."
        except Exception as e:
            return f"Hibernate-Fehler: {e}"

    @staticmethod
    def screensaver() -> str:
        """Bildschirmschoner starten."""
        try:
            if IS_WINDOWS:
                SystemCommands._run(["rundll32.exe", "user32.dll,LockWorkStation"])
                return "Bildschirmschoner / Sperre gestartet."
            else:
                SystemCommands._run(["pmset", "displaysleepnow"])
                return "Bildschirm ausgeschaltet."
        except Exception as e:
            return f"Bildschirmschoner-Fehler: {e}"

    @staticmethod
    def battery_status() -> str:
        try:
            if IS_WINDOWS:
                r     = SystemCommands._run(["wmic", "path", "Win32_Battery", "get",
                                             "EstimatedChargeRemaining,BatteryStatus"])
                lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
                if len(lines) >= 2:
                    vals = lines[1].split()
                    if vals:
                        pct      = vals[0]
                        charging = vals[1] == "2" if len(vals) > 1 else False
                        status   = "lädt ⚡" if charging else "Batterie 🔋"
                        return f"Akku: {pct}% — {status}"
                return "Kein Akku (Desktop?)"
            else:
                r = SystemCommands._run(["pmset", "-g", "batt"])
                for line in r.stdout.split("\n"):
                    if "%" in line:
                        m = re.search(r"(\d+)%", line)
                        if m:
                            pct      = m.group(1)
                            charging = "charging" in line.lower()
                            status   = "lädt ⚡" if charging else "Batterie 🔋"
                            return f"Akku: {pct}% — {status}"
                return "Kein Akku gefunden."
        except Exception as e:
            return f"Akku-Fehler: {e}"

    @staticmethod
    def lock_screen() -> str:
        try:
            if IS_WINDOWS:
                SystemCommands._run(["rundll32.exe", "user32.dll,LockWorkStation"])
            else:
                SystemCommands._popen(["pmset", "displaysleepnow"])
            return "Bildschirm gesperrt."
        except Exception as e:
            return f"Sperr-Fehler: {e}"

    @staticmethod
    def screenshot() -> str:
        try:
            ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
            desktop = Path.home() / "Desktop"
            path    = str(desktop / f"AERA_Screenshot_{ts}.png")
            if IS_WINDOWS:
                if PYAUTOGUI_OK:
                    import pyautogui as pag
                    pag.screenshot(path)
                else:
                    return "pyautogui fehlt: pip install pyautogui"
            else:
                subprocess.Popen(["screencapture", "-x", path])
            return f"Screenshot gespeichert: AERA_Screenshot_{ts}.png"
        except Exception as e:
            return f"Screenshot-Fehler: {e}"

    @staticmethod
    def disk_space() -> str:
        try:
            if IS_WINDOWS:
                r     = SystemCommands._run(["wmic", "logicaldisk", "get",
                                             "size,freespace,caption"])
                lines = [l for l in r.stdout.splitlines()
                         if l.strip() and "Caption" not in l]
                results = []
                for line in lines[:3]:
                    parts = line.split()
                    if len(parts) >= 3:
                        cap    = parts[0]
                        free_b = int(parts[1]) if parts[1].isdigit() else 0
                        tot_b  = int(parts[2]) if parts[2].isdigit() else 0
                        if tot_b > 0:
                            results.append(f"{cap} {free_b/1e9:.1f}GB frei / {tot_b/1e9:.1f}GB")
                return "Festplatten: " + " | ".join(results) if results else "Disk-Info n.v."
            else:
                r = SystemCommands._run(["df", "-h", "/"])
                lines = r.stdout.strip().split("\n")
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 4:
                        return f"Festplatte: {parts[3]} frei von {parts[1]} ({parts[4]})"
            return "Disk-Info nicht verfügbar."
        except Exception as e:
            return f"Disk-Fehler: {e}"

    @staticmethod
    def ip_address() -> str:
        try:
            if IS_WINDOWS:
                r   = SystemCommands._run(["ipconfig"])
                ips = re.findall(r"IPv4.*?:\s*([\d\.]+)", r.stdout)
                local = [ip for ip in ips if not ip.startswith("127.")]
                return f"IP-Adresse: {local[0]}" if local else "Keine IP gefunden."
            else:
                for iface in ["en0", "en1"]:
                    r  = SystemCommands._run(["ipconfig", "getifaddr", iface])
                    ip = r.stdout.strip()
                    if ip:
                        return f"IP ({iface}): {ip}"
                return "Keine IP gefunden."
        except Exception as e:
            return f"IP-Fehler: {e}"

    @staticmethod
    def set_volume(level: int) -> str:
        level = max(0, min(100, level))
        try:
            if IS_WINDOWS:
                SystemCommands._run([
                    "powershell", "-c",
                    f"$obj = New-Object -com WScript.Shell; "
                    f"$obj.SendKeys([char]174*10); "
                    f"(New-Object -ComObject WScript.Shell).SendKeys([char]175 * {level // 2})"
                ])
                return f"Lautstärke ca. {level}% gesetzt."
            else:
                SystemCommands._run(["osascript", "-e", f"set volume output volume {level}"])
                return f"Lautstärke: {level}%"
        except Exception as e:
            return f"Lautstärke-Fehler: {e}"

    @staticmethod
    def get_volume() -> str:
        try:
            if IS_MACOS:
                r = SystemCommands._run(["osascript", "-e",
                    "output volume of (get volume settings)"])
                return f"Aktuelle Lautstärke: {r.stdout.strip()}%"
            return "Lautstärke: Windows — 'Lautstärke setzen X' nutzen"
        except Exception as e:
            return f"Lautstärke-Fehler: {e}"

    @staticmethod
    def open_task_manager() -> str:
        try:
            if IS_WINDOWS:
                SystemCommands._popen(["taskmgr"])
            else:
                SystemCommands._popen(["open", "-a", "Activity Monitor"])
            return "Task-Manager geöffnet."
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def empty_trash() -> str:
        try:
            if IS_WINDOWS:
                SystemCommands._run(["powershell", "-c",
                    "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"])
                return "Papierkorb geleert."
            else:
                SystemCommands._run(["osascript", "-e",
                    'tell application "Finder" to empty trash'])
                return "Papierkorb geleert."
        except Exception as e:
            return f"Papierkorb-Fehler: {e}"

    @staticmethod
    def system_info() -> str:
        try:
            if IS_WINDOWS:
                r     = SystemCommands._run(["systeminfo"])
                lines = r.stdout.splitlines()
                info  = []
                for line in lines[:15]:
                    if any(k in line for k in ["OS", "Prozessor", "RAM", "Systemtyp", "Hostname"]):
                        info.append(line.strip())
                return "\n".join(info[:6]) if info else "System-Info nicht verfügbar."
            else:
                parts = []
                r  = SystemCommands._run(["sw_vers"])
                parts.append(r.stdout.strip())
                r2 = SystemCommands._run(["sysctl", "-n", "hw.memsize"])
                if r2.stdout.strip():
                    gb = int(r2.stdout.strip()) // (1024 ** 3)
                    parts.append(f"RAM: {gb} GB")
                return "\n".join(parts)
        except Exception as e:
            return f"System-Info-Fehler: {e}"

    @staticmethod
    def energy_mode(enable: bool) -> str:
        try:
            if IS_WINDOWS:
                mode = "SCHEME_MIN" if enable else "SCHEME_BALANCED"
                SystemCommands._run(["powercfg", "/setactive", mode])
            else:
                val = "1" if enable else "0"
                SystemCommands._run(["sudo", "pmset", "-a", "lowpowermode", val])
            return f"Energiesparmodus {'aktiviert' if enable else 'deaktiviert'}."
        except Exception as e:
            return f"Energiemodus-Fehler: {e}"

    @staticmethod
    def show_processes() -> str:
        return APP_ENGINE.list_running()

    @staticmethod
    def network_info() -> str:
        info = []
        try:
            if IS_WINDOWS:
                r   = SystemCommands._run(["ipconfig", "/all"])
                ips = re.findall(r"IPv4.*?:\s*([\d\.]+)", r.stdout)
                gws = re.findall(r"Standardgateway.*?:\s*([\d\.]+)", r.stdout)
                if ips: info.append(f"IP: {ips[0]}")
                if gws: info.append(f"Gateway: {gws[0]}")
            else:
                r = SystemCommands._run(["networksetup", "-getairportnetwork", "en0"])
                info.append(r.stdout.strip())
        except Exception:
            pass
        return " | ".join(info) if info else "Netzwerkinfo nicht verfügbar."

    @staticmethod
    def bluetooth(enable: bool) -> str:
        action = "aktiviert" if enable else "deaktiviert"
        try:
            if IS_WINDOWS:
                return f"Bluetooth {action} (Windows — ggf. manuell aktivieren)."
            else:
                state = "1" if enable else "0"
                SystemCommands._run(["blueutil", "-p", state])
                return f"Bluetooth {action}."
        except Exception as e:
            return f"Bluetooth-Fehler: {e}"

    @staticmethod
    def clean_temp() -> str:
        cleaned = 0
        try:
            tmp = os.environ.get("TEMP", "C:/Windows/Temp") if IS_WINDOWS else "/tmp"
            for f in Path(tmp).iterdir():
                try:
                    if f.is_file():
                        f.unlink()
                        cleaned += 1
                except Exception:
                    pass
        except Exception:
            pass
        return f"Temp bereinigt. {cleaned} Dateien entfernt."

    @staticmethod
    def display_off() -> str:
        try:
            if IS_WINDOWS:
                import ctypes
                ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
                return "Monitor ausgeschaltet."
            else:
                SystemCommands._popen(["pmset", "displaysleepnow"])
                return "Monitor ausgeschaltet."
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def set_brightness(level: int) -> str:
        level = max(0, min(100, level))
        try:
            if IS_WINDOWS:
                SystemCommands._run(["powershell", "-c",
                    f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
                    f".WmiSetBrightness(1,{level})"])
            else:
                SystemCommands._run(["brightness", str(level / 100.0)])
            return f"Helligkeit auf {level}% gesetzt."
        except Exception as e:
            return f"Helligkeit-Fehler: {e}"

    @staticmethod
    def clear_dns_cache() -> str:
        try:
            if IS_WINDOWS:
                SystemCommands._run(["ipconfig", "/flushdns"])
                return "DNS-Cache geleert (Windows)."
            else:
                SystemCommands._run(["sudo", "dscacheutil", "-flushcache"])
                SystemCommands._run(["sudo", "killall", "-HUP", "mDNSResponder"])
                return "DNS-Cache geleert (macOS)."
        except Exception as e:
            return f"DNS-Fehler: {e}"

    @staticmethod
    def create_folder(name: str, loc: str = "~/Desktop") -> str:
        try:
            path = Path(loc).expanduser() / name
            path.mkdir(parents=True, exist_ok=True)
            SystemCommands._open_file_or_url(str(path))
            return f"Ordner '{name}' erstellt: {path}"
        except Exception as e:
            return f"Ordner-Fehler: {e}"

    @staticmethod
    def find_file(query: str) -> str:
        """
        v10: Verbesserte Dateisuche mit smartem Namens-Matching.
        """
        results = DEEP_SEARCH.search_files(query)
        if not results:
            # Höfliche Absage
            polite_rejections = [
                f"Entschuldigung, ich habe leider keine Datei zu '{query}' gefunden. Möchten Sie, dass ich in anderen Ordnern suche?",
                f"Ich habe '{query}' in den üblichen Verzeichnissen nicht gefunden. Soll ich eine erweiterte Suche starten?",
                f"Leider konnte ich keine passende Datei für '{query}' finden. Bitte prüfen Sie die Schreibweise oder geben Sie einen anderen Suchbegriff ein.",
            ]
            return random.choice(polite_rejections)

        # Höfliche Erfolgsmeldung
        best = results[0]
        score = best["score"]
        name = best["name"]
        path = best["path"]

        # Übereinstimmungsgrad in Worten
        if score >= 90:
            match_desc = "sehr hoher Übereinstimmung"
        elif score >= 75:
            match_desc = "hoher Übereinstimmung"
        elif score >= 60:
            match_desc = "guter Übereinstimmung"
        else:
            match_desc = "moderater Übereinstimmung"

        polite_responses = [
            f"Guten Tag. Ich habe die Datei '{name}' gefunden. Sie stimmt zu {score}% mit Ihrer Anfrage überein. Die Datei befindet sich unter: {path}",
            f"Sehr gerne. Ich habe folgende Datei gefunden: '{name}' mit einer {match_desc} von {score}%. Der Speicherort ist: {path}",
            f"Mit Vergnügen. Die Datei '{name}' wurde lokalisiert. Übereinstimmung: {score}%. Sie finden sie hier: {path}",
        ]

        result = random.choice(polite_responses)

        # Zusätzliche Treffer höflich anhängen
        if len(results) > 1:
            result += f"\n\nDarüber hinaus habe ich noch {len(results)-1} weitere Treffer gefunden:"
            for i, r in enumerate(results[1:4], 2):
                result += f"\n  {i}. '{r['name']}' ({r['score']}% Übereinstimmung)"

        return result

    @staticmethod
    def rename_file(old: str, new: str, folder: str = "~/Desktop") -> str:
        try:
            base = Path(folder).expanduser()
            if FUZZY_OK:
                names = [f.name for f in base.glob("*")]
                best  = fuzz_process.extractOne(old, names, scorer=fuzz.ratio)
                if best and best[1] >= 60:
                    old_path = base / best[0]
                    old_path.rename(base / new)
                    return f"'{best[0]}' → '{new}' umbenannt."
            old_path = base / old
            if old_path.exists():
                old_path.rename(base / new)
                return f"'{old}' → '{new}' umbenannt."
            return f"Datei '{old}' nicht gefunden."
        except Exception as e:
            return f"Umbenennen-Fehler: {e}"

    @staticmethod
    def delete_old_files(folder: str = "~/Downloads", days: int = 30) -> str:
        try:
            path   = Path(folder).expanduser()
            cutoff = time.time() - days * 86400
            deleted = 0
            for f in path.iterdir():
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
                    deleted += 1
            return f"{deleted} Dateien (älter als {days} Tage) gelöscht."
        except Exception as e:
            return f"Löschen-Fehler: {e}"

    @staticmethod
    def move_images() -> str:
        try:
            src = Path.home() / "Downloads"
            dst = Path.home() / "Pictures" / "AERA-Auto"
            dst.mkdir(parents=True, exist_ok=True)
            moved = 0
            for ext in ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.webp", "*.heic", "*.bmp"]:
                for f in src.glob(ext):
                    shutil.move(str(f), str(dst))
                    moved += 1
            return f"{moved} Bilder nach Pictures/AERA-Auto verschoben."
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def folder_size(folder: str) -> str:
        try:
            path  = Path(folder).expanduser()
            if not path.exists():
                return f"Ordner nicht gefunden: {folder}"
            total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            return f"'{path.name}': {total / 1e6:.1f} MB"
        except Exception as e:
            return f"Größen-Fehler: {e}"

    @staticmethod
    def zip_folder(folder: str) -> str:
        try:
            path = Path(folder).expanduser()
            if not path.exists():
                return f"Ordner '{folder}' nicht gefunden."
            zip_path = str(path.parent / path.name)
            shutil.make_archive(zip_path, "zip", str(path.parent), path.name)
            return f"'{path.name}.zip' erstellt."
        except Exception as e:
            return f"ZIP-Fehler: {e}"

    @staticmethod
    def open_last_document() -> str:
        try:
            docs = []
            for loc in ["Desktop", "Documents", "Downloads"]:
                p = Path.home() / loc
                for ext in ["*.docx", "*.pdf", "*.txt", "*.xlsx", "*.pptx", "*.md"]:
                    docs.extend(p.glob(ext))
            if docs:
                latest = max(docs, key=lambda f: f.stat().st_mtime)
                SystemCommands._open_file_or_url(str(latest))
                return f"Geöffnet: {latest.name}"
            return "Kein Dokument gefunden."
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def find_duplicates(folder: str = "~/Downloads") -> str:
        try:
            path   = Path(folder).expanduser()
            hashes: Dict[str, List[str]] = {}
            for f in path.iterdir():
                if f.is_file() and f.stat().st_size > 0:
                    try:
                        h = hashlib.md5(f.read_bytes()[:65536]).hexdigest()
                        hashes.setdefault(h, []).append(f.name)
                    except Exception:
                        pass
            dups = {h: ns for h, ns in hashes.items() if len(ns) > 1}
            if not dups:
                return f"Keine Duplikate in {folder}."
            lines = [f"  • {', '.join(ns)}" for ns in list(dups.values())[:5]]
            return "Duplikate:\n" + "\n".join(lines)
        except Exception as e:
            return f"Duplikat-Fehler: {e}"

    @staticmethod
    def show_hidden_files(show: bool = True) -> str:
        try:
            if IS_WINDOWS:
                val = "1" if show else "2"
                SystemCommands._run(["reg", "add",
                    r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                    "/v", "Hidden", "/t", "REG_DWORD", "/d", val, "/f"])
                SystemCommands._run(["taskkill", "/f", "/im", "explorer.exe"])
                SystemCommands._popen(["explorer.exe"])
            else:
                val = "true" if show else "false"
                SystemCommands._run(["defaults", "write", "com.apple.finder",
                                     "AppleShowAllFiles", val])
                SystemCommands._run(["killall", "Finder"])
            return f"Versteckte Dateien {'eingeblendet' if show else 'ausgeblendet'}."
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def create_text_file(filename: str, content: str) -> str:
        try:
            if not filename.endswith(".txt"):
                filename += ".txt"
            path = Path.home() / "Desktop" / filename
            path.write_text(content, encoding="utf-8")
            SystemCommands._open_file_or_url(str(path))
            return f"'{filename}' erstellt und geöffnet."
        except Exception as e:
            return f"Datei-Fehler: {e}"

    @staticmethod
    def count_files(folder: str = "~/Desktop") -> str:
        try:
            path  = Path(folder).expanduser()
            items = list(path.iterdir())
            files = sum(1 for f in items if f.is_file())
            dirs  = sum(1 for f in items if f.is_dir())
            return f"'{path.name}': {files} Dateien, {dirs} Ordner."
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def print_document(filename: str) -> str:
        for loc in ["Desktop", "Documents", "Downloads"]:
            path = Path.home() / loc / filename
            if path.exists():
                try:
                    if IS_WINDOWS:
                        os.startfile(str(path), "print")
                    else:
                        subprocess.Popen(["lpr", str(path)])
                    return f"'{filename}' wird gedruckt."
                except Exception as e:
                    return f"Drucker-Fehler: {e}"
        return f"'{filename}' nicht gefunden."

    @staticmethod
    def backup_desktop() -> str:
        try:
            src = Path.home() / "Desktop"
            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            dst = Path.home() / f"Desktop_Backup_{ts}"
            shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
            return f"Desktop-Backup erstellt: Desktop_Backup_{ts}"
        except Exception as e:
            return f"Backup-Fehler: {e}"

    @staticmethod
    def open_downloads() -> str:
        try:
            path = Path.home() / "Downloads"
            SystemCommands._open_file_or_url(str(path))
            return "Downloads-Ordner geöffnet."
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def dictate_text(text: str) -> str:
        try:
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = Path.home() / "Desktop" / f"AERA_Diktat_{ts}.txt"
            path.write_text(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}]\n{text}\n",
                            encoding="utf-8")
            SystemCommands._open_file_or_url(str(path))
            return f"Text diktiert und gespeichert: '{text[:50]}'"
        except Exception as e:
            return f"Diktat-Fehler: {e}"

    @staticmethod
    def open_recent_pdf() -> str:
        try:
            pdfs = []
            for loc in ["Desktop", "Documents", "Downloads"]:
                pdfs.extend((Path.home() / loc).glob("*.pdf"))
            if pdfs:
                latest = max(pdfs, key=lambda f: f.stat().st_mtime)
                SystemCommands._open_file_or_url(str(latest))
                return f"Neueste PDF: {latest.name}"
            return "Keine PDF gefunden."
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def create_shopping_list() -> str:
        path = Path.home() / "Desktop" / "AERA_Einkaufsliste.txt"
        mode = "a" if path.exists() else "w"
        with open(str(path), mode, encoding="utf-8") as f:
            if mode == "w":
                f.write(f"AERA Einkaufsliste — {datetime.now().strftime('%d.%m.%Y')}\n\n")
        SystemCommands._open_file_or_url(str(path))
        return "Einkaufsliste geöffnet."

    @staticmethod
    def google_search(query: str) -> str:
        url = f"https://www.google.de/search?q={urllib.parse.quote(query)}"
        SystemCommands._open_file_or_url(url)
        return f"Google-Suche: '{query}'"

    @staticmethod
    def get_weather(city: str = "Berlin") -> str:
        if REQUESTS_OK:
            try:
                url = f"https://wttr.in/{urllib.parse.quote(city)}?format=3"
                r   = requests.get(url, timeout=6)
                if r.status_code == 200:
                    return f"Wetter: {r.text.strip()}"
            except Exception:
                pass
        url = f"https://wttr.in/{urllib.parse.quote(city)}"
        SystemCommands._open_file_or_url(url)
        return f"Wetter für {city} im Browser geöffnet."

    @staticmethod
    def youtube_search(query: str) -> str:
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        SystemCommands._open_file_or_url(url)
        return f"YouTube: '{query}'"

    @staticmethod
    def bitcoin_price() -> str:
        if REQUESTS_OK:
            try:
                r    = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
                                    timeout=5)
                data = r.json()
                return f"Bitcoin: ${float(data['price']):,.2f} USD"
            except Exception:
                pass
        return "Bitcoin-Kurs: Keine Verbindung."

    @staticmethod
    def stock_price(symbol: str = "SAP") -> str:
        if REQUESTS_OK:
            try:
                url  = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                        f"?interval=1d")
                r    = requests.get(url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
                data = r.json()
                price    = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
                currency = data["chart"]["result"][0]["meta"]["currency"]
                return f"{symbol.upper()}: {price:.2f} {currency}"
            except Exception:
                pass
        return f"Kurs für {symbol} nicht verfügbar."

    @staticmethod
    def open_news() -> str:
        SystemCommands._open_file_or_url("https://www.tagesschau.de")
        return "Tagesschau geöffnet."

    @staticmethod
    def open_email() -> str:
        try:
            if IS_WINDOWS:
                SystemCommands._popen(["start", "outlook:"])
            else:
                SystemCommands._popen(["open", "-a", "Mail"])
            return "E-Mail-App geöffnet."
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def open_whatsapp() -> str:
        SystemCommands._open_file_or_url("https://web.whatsapp.com")
        return "WhatsApp Web geöffnet."

    @staticmethod
    def translate(text: str, lang: str = "en") -> str:
        url = (f"https://translate.google.com/?sl=auto&tl={lang}"
               f"&text={urllib.parse.quote(text)}&op=translate")
        SystemCommands._open_file_or_url(url)
        return f"Übersetzung geöffnet: '{text[:30]}' → {lang.upper()}"

    @staticmethod
    def amazon_search(query: str) -> str:
        url = f"https://www.amazon.de/s?k={urllib.parse.quote(query)}"
        SystemCommands._open_file_or_url(url)
        return f"Amazon: '{query}'"

    @staticmethod
    def maps_navigate(dest: str) -> str:
        url = f"https://www.google.com/maps/dir/?api=1&destination={urllib.parse.quote(dest)}"
        SystemCommands._open_file_or_url(url)
        return f"Navigation nach '{dest}' geöffnet."

    @staticmethod
    def search_news(topic: str) -> str:
        url = f"https://news.google.com/search?q={urllib.parse.quote(topic)}&hl=de"
        SystemCommands._open_file_or_url(url)
        return f"News über '{topic}'."

    @staticmethod
    def check_website(url: str) -> str:
        if REQUESTS_OK:
            try:
                if not url.startswith("http"):
                    url = "https://" + url
                r = requests.get(url, timeout=8, allow_redirects=True)
                if r.status_code < 400:
                    return f"✅ {url} ist online (HTTP {r.status_code})"
                return f"⚠️ {url} antwortet mit HTTP {r.status_code}"
            except Exception as e:
                return f"❌ {url} nicht erreichbar: {e}"
        return "requests fehlt: pip install requests"

    @staticmethod
    def internet_speed() -> str:
        if REQUESTS_OK:
            try:
                start = time.time()
                r     = requests.get("https://speed.cloudflare.com/__down?bytes=5000000",
                                     timeout=15, stream=True)
                data    = r.content
                elapsed = time.time() - start
                speed   = (len(data) * 8) / (elapsed * 1e6)
                return f"Internet-Download: ~{speed:.1f} Mbps"
            except Exception:
                pass
        return "Speedtest fehlgeschlagen."

    @staticmethod
    def open_chatgpt() -> str:
        SystemCommands._open_file_or_url("https://chat.openai.com")
        return "ChatGPT geöffnet."

    @staticmethod
    def search_recipe(dish: str) -> str:
        url = f"https://www.chefkoch.de/rs/s0/{urllib.parse.quote(dish)}/Rezepte.html"
        SystemCommands._open_file_or_url(url)
        return f"Rezepte für '{dish}'."

    @staticmethod
    def save_bookmark() -> str:
        bm_file = Path.home() / "Desktop" / "AERA_Bookmarks.txt"
        url = "URL manuell eintragen"
        try:
            if IS_MACOS:
                r = SystemCommands._run(["osascript", "-e",
                    'tell application "Safari" to return URL of current tab of front window'])
                if r.stdout.strip():
                    url = r.stdout.strip()
        except Exception:
            pass
        with open(str(bm_file), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')} | {url}\n")
        return f"Lesezeichen gespeichert: {url[:60]}"

    @staticmethod
    def define_word(word: str) -> str:
        url = f"https://www.duden.de/suchen/dudenonline/{urllib.parse.quote(word)}"
        SystemCommands._open_file_or_url(url)
        return f"Duden: '{word}'."

    @staticmethod
    def convert_currency(amount: float, from_c: str = "USD", to_c: str = "EUR") -> str:
        if REQUESTS_OK:
            try:
                r    = requests.get(f"https://api.exchangerate-api.com/v4/latest/{from_c.upper()}",
                                    timeout=6)
                data = r.json()
                rate = data["rates"].get(to_c.upper(), 1)
                return f"{amount:.2f} {from_c.upper()} = {amount * rate:.2f} {to_c.upper()}"
            except Exception:
                pass
        return "Währungsumrechnung fehlgeschlagen."

    @staticmethod
    def keyboard_shortcut(keys: str) -> str:
        if not PYAUTOGUI_OK:
            return "pyautogui fehlt: pip install pyautogui"
        try:
            import pyautogui as pag
            pag.hotkey(*keys.split("+"))
            return f"Tastenkombination {keys} gesendet."
        except Exception as e:
            return f"Hotkey-Fehler: {e}"

    @staticmethod
    def type_text(text: str) -> str:
        if not PYAUTOGUI_OK:
            return "pyautogui fehlt."
        try:
            import pyautogui as pag
            time.sleep(0.5)
            pag.typewrite(text, interval=0.05)
            return f"Text eingegeben: '{text[:40]}'"
        except Exception as e:
            return f"Tipp-Fehler: {e}"

    @staticmethod
    def open_terminal() -> str:
        try:
            if IS_WINDOWS:
                SystemCommands._popen(["cmd.exe"])
                return "Eingabeaufforderung geöffnet."
            else:
                SystemCommands._popen(["open", "-a", "Terminal"])
                return "Terminal geöffnet."
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def open_calculator() -> str:
        try:
            if IS_WINDOWS:
                SystemCommands._popen(["calc.exe"])
            else:
                SystemCommands._popen(["open", "-a", "Calculator"])
            return "Taschenrechner geöffnet."
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def open_notepad() -> str:
        try:
            if IS_WINDOWS:
                SystemCommands._popen(["notepad.exe"])
            else:
                SystemCommands._popen(["open", "-a", "TextEdit"])
            return "Notepad geöffnet."
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def open_system_settings() -> str:
        try:
            if IS_WINDOWS:
                SystemCommands._popen(["ms-settings:"])
            else:
                for app in ["System Settings", "System Preferences"]:
                    r = SystemCommands._run(["open", "-a", app])
                    if r.returncode == 0:
                        return f"{app} geöffnet."
            return "Einstellungen geöffnet."
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def open_browser(url: str = "") -> str:
        try:
            target = url if url else "https://www.google.de"
            SystemCommands._open_file_or_url(target)
            return f"Browser geöffnet: {target}"
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def speak_text(text: str) -> str:
        try:
            if IS_MACOS:
                subprocess.Popen(["say", "-v", "Anna", "-r", "170", text])
                return f"Lese vor: '{text[:50]}'"
            else:
                subprocess.run([
                    "powershell", "-c",
                    f'Add-Type -AssemblyName System.Speech; '
                    f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                    f'$s.Speak("{text}")'
                ])
                return f"Vorgelesen: '{text[:50]}'"
        except Exception as e:
            return f"Sprechen-Fehler: {e}"

    @staticmethod
    def install_package(package: str) -> str:
        try:
            if IS_WINDOWS:
                r = SystemCommands._run(["winget", "install", package,
                                         "--accept-source-agreements"])
                if r.returncode == 0:
                    return f"'{package}' via winget installiert."
                r2 = SystemCommands._run([sys.executable, "-m", "pip", "install", package])
                return f"pip: {r2.stdout[-200:]}"
            else:
                r = SystemCommands._run(["which", "brew"])
                if r.returncode == 0:
                    subprocess.Popen(["brew", "install", package])
                    return f"Installiere '{package}' via Homebrew..."
                return "Homebrew nicht installiert."
        except Exception as e:
            return f"Install-Fehler: {e}"

    @staticmethod
    def calculate(expr: str) -> str:
        try:
            expr_clean = expr.lower()
            for old, new in [
                ("mal", "*"), ("durch", "/"), ("plus", "+"), ("minus", "-"),
                ("geteilt durch", "/"), ("multipliziert mit", "*"),
                ("hoch", "**"), ("modulo", "%"), ("quadratwurzel von", "sqrt"),
                ("sinus", "sin"), ("cosinus", "cos"), ("tangens", "tan"),
                ("pi", str(math.pi)), ("e ", str(math.e) + " "),
            ]:
                expr_clean = expr_clean.replace(old, new)
            # math-Funktionen erlauben
            safe_globals = {
                "__builtins__": {},
                "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
                "tan": math.tan, "log": math.log, "log10": math.log10,
                "abs": abs, "round": round, "pow": pow,
                "pi": math.pi, "e": math.e, "ceil": math.ceil,
                "floor": math.floor, "factorial": math.factorial,
            }
            safe = re.sub(r"[^0-9+\-*/().\s%a-z_,]", "", expr_clean)
            if not safe.strip():
                return "Kein gültiger Ausdruck."
            result = eval(safe, safe_globals)
            if isinstance(result, float) and result == int(result):
                result = int(result)
            return f"{expr} = {result}"
        except ZeroDivisionError:
            return "Fehler: Division durch Null."
        except Exception as e:
            return f"Rechenfehler: {e}"

    @staticmethod
    def set_reminder(task: str, minutes: int = 30) -> str:
        try:
            if IS_MACOS:
                script = (f'tell application "Reminders" to make new reminder with properties '
                          f'{{name:"{task}", due date:(current date) + {minutes * 60}}}')
                SystemCommands._run(["osascript", "-e", script])
                return f"Erinnerung: '{task}' in {minutes} Min."
            else:
                return f"Erinnerung '{task}' in {minutes} Min. gesetzt."
        except Exception as e:
            return f"Erinnerung-Fehler: {e}"

    @staticmethod
    def days_until_christmas() -> str:
        today     = datetime.now()
        christmas = datetime(today.year, 12, 25)
        if today > christmas:
            christmas = datetime(today.year + 1, 12, 25)
        days = (christmas - today).days
        return f"Noch {days} Tage bis Weihnachten! 🎄"

    @staticmethod
    def world_clock(city: str) -> str:
        tz_map = {
            "new york": "America/New_York", "los angeles": "America/Los_Angeles",
            "london": "Europe/London", "paris": "Europe/Paris",
            "berlin": "Europe/Berlin", "tokio": "Asia/Tokyo", "tokyo": "Asia/Tokyo",
            "dubai": "Asia/Dubai", "sydney": "Australia/Sydney",
            "peking": "Asia/Shanghai", "beijing": "Asia/Shanghai",
            "moskau": "Europe/Moscow", "singapur": "Asia/Singapore",
        }
        tz = tz_map.get(city.lower().strip(), "UTC")
        try:
            if IS_WINDOWS:
                import pytz
                import datetime as dt
                tz_obj = pytz.timezone(tz)
                now    = dt.datetime.now(tz_obj)
                return f"Zeit in {city.title()}: {now.strftime('%H:%M Uhr (%Z)')}"
            else:
                env = {**os.environ, "TZ": tz}
                r   = subprocess.run(["date", "+%H:%M Uhr (%Z)"],
                                     capture_output=True, text=True, env=env, timeout=5)
                return f"Zeit in {city.title()}: {r.stdout.strip()}"
        except Exception as e:
            return f"Weltzeit-Fehler: {e}"

    @staticmethod
    def goodnight() -> str:
        try:
            SystemCommands.set_volume(20)
            if IS_MACOS:
                subprocess.run(["say", "-v", "Anna", "Gute Nacht! Bis morgen."], timeout=5)
                subprocess.Popen(["pmset", "sleepnow"])
            else:
                SystemCommands._run(["shutdown", "/h"])
            return "Gute Nacht! System wird heruntergefahren."
        except Exception as e:
            return f"Gute-Nacht-Fehler: {e}"

    # ════════════════════════════════════════════════════════════════════
    #  v8.0 TOOLS (unverändert)
    # ════════════════════════════════════════════════════════════════════

    @staticmethod
    def clipboard_read() -> str:
        if CLIPBOARD_OK:
            try:
                text = pyperclip.paste()
                if text and len(text.strip()) > 0:
                    preview = text.strip()[:200]
                    return f"Clipboard: '{preview}{'...' if len(text) > 200 else ''}'"
                return "Clipboard ist leer."
            except Exception as e:
                return f"Clipboard-Fehler: {e}"
        try:
            if IS_WINDOWS:
                r = SystemCommands._run(["powershell", "-c", "Get-Clipboard"])
                return f"Clipboard: '{r.stdout.strip()[:200]}'"
            else:
                r = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
                return f"Clipboard: '{r.stdout.strip()[:200]}'"
        except Exception as e:
            return f"Clipboard-Fehler: {e}"

    @staticmethod
    def clipboard_write(text: str) -> str:
        if CLIPBOARD_OK:
            try:
                pyperclip.copy(text)
                return f"In Clipboard kopiert: '{text[:60]}'"
            except Exception as e:
                return f"Clipboard-Fehler: {e}"
        try:
            if IS_WINDOWS:
                subprocess.run(["clip"], input=text, text=True, timeout=3)
            else:
                subprocess.run(["pbcopy"], input=text, text=True, timeout=3)
            return f"In Clipboard kopiert: '{text[:60]}'"
        except Exception as e:
            return f"Clipboard-Fehler: {e}"

    @staticmethod
    def generate_password(length: int = 16, secure: bool = True) -> str:
        try:
            if secure:
                alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
                pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
            else:
                alphabet = string.ascii_letters + string.digits
                pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
            SystemCommands.clipboard_write(pwd)
            return f"Passwort generiert ({length} Zeichen) und in Clipboard: {pwd}"
        except Exception as e:
            return f"Passwort-Fehler: {e}"

    @staticmethod
    def generate_qr(text: str) -> str:
        if not QR_OK:
            return "qrcode/Pillow fehlt: pip install qrcode[pil] Pillow"
        try:
            img  = qrcode.make(text)
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = Path.home() / "Desktop" / f"AERA_QR_{ts}.png"
            img.save(str(path))
            SystemCommands._open_file_or_url(str(path))
            return f"QR-Code erstellt: AERA_QR_{ts}.png für '{text[:40]}'"
        except Exception as e:
            return f"QR-Fehler: {e}"

    @staticmethod
    def kill_process(name: str) -> str:
        return APP_ENGINE.close_app(name)

    @staticmethod
    def get_uptime() -> str:
        try:
            if PSUTIL_OK:
                boot = datetime.fromtimestamp(psutil.boot_time())
                delta = datetime.now() - boot
                d = delta.days
                h, rem = divmod(delta.seconds, 3600)
                m = rem // 60
                return f"Uptime: {d} Tage {h} Stunden {m} Minuten (Boot: {boot.strftime('%d.%m.%Y %H:%M')})"
            if IS_WINDOWS:
                r2 = SystemCommands._run(["powershell", "-c",
                    "(get-date) - (gcim Win32_OperatingSystem).LastBootUpTime | "
                    "Select-Object -ExpandProperty TotalHours"])
                if r2.stdout.strip():
                    hours = float(r2.stdout.strip())
                    d, h  = int(hours // 24), int(hours % 24)
                    return f"Uptime: {d} Tage {h} Stunden"
                return "Uptime nicht ermittelbar."
            else:
                r = SystemCommands._run(["uptime"])
                return f"Uptime: {r.stdout.strip()}"
        except Exception as e:
            return f"Uptime-Fehler: {e}"

    @staticmethod
    def ping_host(host: str = "google.com") -> str:
        try:
            if IS_WINDOWS:
                r = SystemCommands._run(["ping", "-n", "3", host], timeout=10)
                match = re.search(r"Minimum\s*=\s*(\d+)ms.*?Maximum\s*=\s*(\d+)ms.*?Mittelwert\s*=\s*(\d+)ms", r.stdout)
                if match:
                    return f"Ping {host}: min={match.group(1)}ms avg={match.group(3)}ms max={match.group(2)}ms"
                match2 = re.search(r"Minimum = (\d+)ms.*Average = (\d+)ms.*Maximum = (\d+)ms", r.stdout)
                if match2:
                    return f"Ping {host}: min={match2.group(1)}ms avg={match2.group(2)}ms max={match2.group(3)}ms"
                return f"Ping-Ergebnis: {r.stdout[-100:].strip()}"
            else:
                r = SystemCommands._run(["ping", "-c", "3", host], timeout=10)
                match = re.search(r"min/avg/max.*?=\s*([\d\.]+)/([\d\.]+)/([\d\.]+)", r.stdout)
                if match:
                    return f"Ping {host}: min={match.group(1)}ms avg={match.group(2)}ms max={match.group(3)}ms"
                return f"Ping-Ergebnis: {r.stdout[-100:].strip()}"
        except Exception as e:
            return f"Ping-Fehler: {e}"

    @staticmethod
    def public_ip() -> str:
        if REQUESTS_OK:
            for url in ["https://api.ipify.org", "https://ipecho.net/plain",
                        "https://ifconfig.me/ip"]:
                try:
                    r = requests.get(url, timeout=5)
                    if r.status_code == 200 and r.text.strip():
                        ip = r.text.strip()
                        try:
                            geo = requests.get(f"https://ipapi.co/{ip}/json/", timeout=4).json()
                            city    = geo.get("city", "")
                            country = geo.get("country_name", "")
                            return f"Öffentliche IP: {ip}  ({city}, {country})"
                        except Exception:
                            return f"Öffentliche IP: {ip}"
                except Exception:
                    continue
        return "Öffentliche IP nicht ermittelbar."

    @staticmethod
    def webcam_snapshot() -> str:
        if not CV2_OK:
            return "OpenCV fehlt: pip install opencv-python"
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return "Keine Webcam gefunden."
            ret, frame = cap.read()
            cap.release()
            if ret:
                ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = Path.home() / "Desktop" / f"AERA_Webcam_{ts}.jpg"
                cv2.imwrite(str(path), frame)
                SystemCommands._open_file_or_url(str(path))
                return f"Webcam-Foto gespeichert: AERA_Webcam_{ts}.jpg"
            return "Webcam-Aufnahme fehlgeschlagen."
        except Exception as e:
            return f"Webcam-Fehler: {e}"

    @staticmethod
    def tell_joke() -> str:
        jokes = [
            "Was macht ein Informatiker beim Essen? Er lädt es runter.",
            "Warum können Programmierer nicht schlafen? Weil sie sich schämen, im Bett zu liegen, während der Rest der Welt debuggt.",
            "Ein WLAN-Router geht in die Bar. 'Passwort?' — 'Auf dem Boden, unter dem Tisch.' — 'Was?!' — 'Groß- und Kleinschreibung beachten.'",
            "Was ist weiß und stört beim Frühstück? Ein Anruf vom Chef.",
            "Warum trägt ein Elektriker keine Unterhose? Weil er keinen Kurzschluss mag.",
            "Wie viele Softwareentwickler braucht man, um eine Glühbirne zu wechseln? Keinen, das ist ein Hardware-Problem.",
            "was sagt  der große Stifft zum kleinen Stifft ? - Wachsmalstifft",
            "Warum hat der Computer Angst vor der Maus? Weil er Klicks bekommt.",
            "Was ist der Unterschied zwischen einem Programmierer und einem Pizzaboten? Der Pizzabote liefert.",
        ]
        return random.choice(jokes)

    @staticmethod
    def roll_dice(sides: int = 6) -> str:
        result = random.randint(1, sides)
        return f"Würfelwurf ({sides}-seitig): {result} 🎲"

    @staticmethod
    def flip_coin() -> str:
        result = random.choice(["Kopf 🪙", "Zahl 🪙"])
        return f"Münzwurf: {result}"

    @staticmethod
    def motivation_quote() -> str:
        quotes = [
            "Der beste Zeitpunkt, einen Baum zu pflanzen, war vor 20 Jahren. Der zweitbeste ist jetzt.",
            "Erfolg ist die Summe kleiner Anstrengungen, die Tag für Tag wiederholt werden.",
            "Wer aufgehört hat, besser werden zu wollen, hat aufgehört, gut zu sein.",
            "Der einzige Weg, großartige Arbeit zu leisten, ist, das zu tun, was man liebt.",
            "Jeder Experte war einmal ein Anfänger.",
            "Disziplin ist die Brücke zwischen Zielen und Errungenschaften.",
            "Glück ist kein Zufall. Es ist, wenn Vorbereitung auf Gelegenheit trifft.",
            "Tue heute, was andere nicht wollen — morgen kannst du, was andere nicht können.",
            "Das Geheimnis des Vorwärtskommens ist, anzufangen.",
            "Stärke wächst nicht aus körperlicher Kraft. Sie kommt aus einem unbeugsamen Willen.",
        ]
        q = random.choice(quotes)
        return f"💡 {q}"

    @staticmethod
    def wifi_info() -> str:
        try:
            if IS_WINDOWS:
                r = SystemCommands._run(["netsh", "wlan", "show", "interfaces"])
                ssid_match  = re.search(r"SSID\s*:\s*(.+)", r.stdout)
                sig_match   = re.search(r"Signal\s*:\s*(.+)", r.stdout)
                ssid  = ssid_match.group(1).strip() if ssid_match else "unbekannt"
                sig   = sig_match.group(1).strip() if sig_match else "?"
                return f"WLAN: {ssid} | Signal: {sig}"
            else:
                r = SystemCommands._run(
                    ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/"
                     "Resources/airport", "-I"])
                ssid_match = re.search(r"SSID:\s*(.+)", r.stdout)
                rssi_match = re.search(r"agrCtlRSSI:\s*(-?\d+)", r.stdout)
                ssid = ssid_match.group(1).strip() if ssid_match else "unbekannt"
                rssi = rssi_match.group(1) if rssi_match else "?"
                return f"WLAN: {ssid} | RSSI: {rssi} dBm"
        except Exception as e:
            return f"WLAN-Info-Fehler: {e}"

    @staticmethod
    def quick_note(text: str) -> str:
        try:
            NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(str(NOTES_FILE), "a", encoding="utf-8") as f:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                f.write(f"[{ts}] {text}\n")
            return f"Notiz gespeichert: '{text[:60]}'"
        except Exception as e:
            return f"Notiz-Fehler: {e}"

    @staticmethod
    def read_notes() -> str:
        try:
            if not NOTES_FILE.exists():
                return "Keine Notizen vorhanden."
            lines = NOTES_FILE.read_text(encoding="utf-8").strip().splitlines()
            last5 = lines[-5:] if len(lines) > 5 else lines
            return "Letzte Notizen:\n" + "\n".join(f"  {l}" for l in last5)
        except Exception as e:
            return f"Notiz-Lesefehler: {e}"

    @staticmethod
    def file_hash(filename: str, algo: str = "md5") -> str:
        for loc in ["Desktop", "Documents", "Downloads"]:
            path = Path.home() / loc / filename
            if path.exists():
                try:
                    h = hashlib.new(algo)
                    with open(str(path), "rb") as f:
                        for chunk in iter(lambda: f.read(8192), b""):
                            h.update(chunk)
                    return f"{algo.upper()} von '{filename}': {h.hexdigest()}"
                except Exception as e:
                    return f"Hash-Fehler: {e}"
        return f"Datei '{filename}' nicht gefunden."

    @staticmethod
    def system_beep() -> str:
        try:
            if IS_WINDOWS:
                import winsound
                winsound.Beep(880, 300)
                return "Beep! 🔔"
            else:
                subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], timeout=3)
                return "Beep! 🔔"
        except Exception:
            print("\a", end="", flush=True)
            return "Beep! (ASCII Bell)"

    @staticmethod
    def read_file_aloud(filename: str) -> str:
        for loc in ["Desktop", "Documents", "Downloads"]:
            path = Path.home() / loc / filename
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")[:500]
                    SystemCommands.speak_text(content)
                    return f"'{filename}' wird vorgelesen ({len(content)} Zeichen)."
                except Exception as e:
                    return f"Vorlesefehler: {e}"
        return f"Datei '{filename}' nicht gefunden."

    # ════════════════════════════════════════════════════════════════════
    #  v10 NEUE TOOLS
    # ════════════════════════════════════════════════════════════════════

    @staticmethod
    def cpu_usage() -> str:
        """CPU-Auslastung anzeigen."""
        if PSUTIL_OK:
            try:
                cpu    = psutil.cpu_percent(interval=1)
                cores  = psutil.cpu_count(logical=False)
                lcores = psutil.cpu_count(logical=True)
                freq   = psutil.cpu_freq()
                freq_s = f" @ {freq.current:.0f} MHz" if freq else ""
                return (f"CPU: {cpu:.1f}% | {cores} Kerne / {lcores} logisch{freq_s}")
            except Exception as e:
                return f"CPU-Fehler: {e}"
        return "psutil fehlt: pip install psutil"

    @staticmethod
    def ram_usage() -> str:
        """RAM-Auslastung anzeigen."""
        if PSUTIL_OK:
            try:
                ram = psutil.virtual_memory()
                swap = psutil.swap_memory()
                return (f"RAM: {ram.percent:.1f}% benutzt "
                        f"({ram.used/1e9:.1f} GB / {ram.total/1e9:.1f} GB) | "
                        f"Swap: {swap.percent:.1f}%")
            except Exception as e:
                return f"RAM-Fehler: {e}"
        return "psutil fehlt: pip install psutil"

    @staticmethod
    def top_processes() -> str:
        """Top-Prozesse nach CPU/RAM (psutil)."""
        if PSUTIL_OK:
            try:
                procs = []
                for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        procs.append(p.info)
                    except Exception:
                        pass
                top = sorted(procs, key=lambda x: x.get('cpu_percent', 0), reverse=True)[:8]
                lines = [f"  {p['name'][:30]:<30} CPU:{p['cpu_percent']:5.1f}%  RAM:{p['memory_percent']:.1f}%"
                         for p in top]
                return "Top-Prozesse (CPU):\n" + "\n".join(lines)
            except Exception as e:
                return f"Prozess-Fehler: {e}"
        return "psutil fehlt: pip install psutil"

    @staticmethod
    def network_traffic() -> str:
        """Netzwerk-Traffic-Monitor."""
        if PSUTIL_OK:
            try:
                n1 = psutil.net_io_counters()
                time.sleep(1)
                n2 = psutil.net_io_counters()
                sent_s     = (n2.bytes_sent - n1.bytes_sent) / 1024
                recv_s     = (n2.bytes_recv - n1.bytes_recv) / 1024
                total_sent = n2.bytes_sent / 1e9
                total_recv = n2.bytes_recv / 1e9
                return (f"Netzwerk: ↑ {sent_s:.1f} KB/s  ↓ {recv_s:.1f} KB/s | "
                        f"Gesamt: ↑ {total_sent:.2f} GB  ↓ {total_recv:.2f} GB")
            except Exception as e:
                return f"Traffic-Fehler: {e}"
        return "psutil fehlt: pip install psutil"

    @staticmethod
    def generate_uuid() -> str:
        """Generiert eine zufällige UUID."""
        uid = str(uuid.uuid4())
        SystemCommands.clipboard_write(uid)
        return f"UUID generiert (in Clipboard): {uid}"

    @staticmethod
    def text_to_upper(text: str) -> str:
        """Text in Großbuchstaben."""
        result = text.upper()
        SystemCommands.clipboard_write(result)
        return f"Großbuchstaben (in Clipboard): {result[:100]}"

    @staticmethod
    def text_to_lower(text: str) -> str:
        """Text in Kleinbuchstaben."""
        result = text.lower()
        SystemCommands.clipboard_write(result)
        return f"Kleinbuchstaben (in Clipboard): {result[:100]}"

    @staticmethod
    def count_text(text: str) -> str:
        """Zählt Zeichen, Wörter und Zeilen in einem Text."""
        chars = len(text)
        words = len(text.split())
        lines = len(text.splitlines())
        return f"Text-Statistik: {chars} Zeichen | {words} Wörter | {lines} Zeilen"

    @staticmethod
    def base64_encode(text: str) -> str:
        """Kodiert Text in Base64."""
        try:
            encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")
            SystemCommands.clipboard_write(encoded)
            return f"Base64 (in Clipboard): {encoded[:80]}{'...' if len(encoded)>80 else ''}"
        except Exception as e:
            return f"Base64-Fehler: {e}"

    @staticmethod
    def base64_decode(text: str) -> str:
        """Dekodiert Base64-Text."""
        try:
            decoded = base64.b64decode(text.encode("utf-8")).decode("utf-8")
            SystemCommands.clipboard_write(decoded)
            return f"Dekodiert (in Clipboard): {decoded[:100]}"
        except Exception as e:
            return f"Base64-Fehler: {e}"

    @staticmethod
    def json_format() -> str:
        """Formatiert JSON aus dem Clipboard."""
        try:
            if CLIPBOARD_OK:
                text = pyperclip.paste()
            else:
                if IS_WINDOWS:
                    r = SystemCommands._run(["powershell", "-c", "Get-Clipboard"])
                    text = r.stdout.strip()
                else:
                    r = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
                    text = r.stdout.strip()
            parsed  = json.loads(text)
            pretty  = json.dumps(parsed, indent=2, ensure_ascii=False)
            SystemCommands.clipboard_write(pretty)
            lines = len(pretty.splitlines())
            return f"JSON formatiert ({lines} Zeilen) und in Clipboard kopiert."
        except json.JSONDecodeError as e:
            return f"Kein gültiges JSON: {e}"
        except Exception as e:
            return f"JSON-Fehler: {e}"

    @staticmethod
    def hex_to_rgb(hex_color: str) -> str:
        """Konvertiert HEX-Farbe zu RGB."""
        try:
            hex_color = hex_color.lstrip("#")
            if len(hex_color) == 3:
                hex_color = "".join(c*2 for c in hex_color)
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            return f"#{hex_color.upper()} → RGB({r}, {g}, {b})"
        except Exception as e:
            return f"Farbfehler: {e}"

    @staticmethod
    def rgb_to_hex(r: int, g: int, b: int) -> str:
        """Konvertiert RGB zu HEX-Farbe."""
        try:
            hex_color = f"#{r:02X}{g:02X}{b:02X}"
            SystemCommands.clipboard_write(hex_color)
            return f"RGB({r}, {g}, {b}) → {hex_color} (in Clipboard)"
        except Exception as e:
            return f"Farbfehler: {e}"

    @staticmethod
    def get_username() -> str:
        """Gibt den aktuellen Benutzernamen aus."""
        try:
            import getpass
            user = getpass.getuser()
            host = socket.gethostname()
            return f"Benutzer: {user} | Hostname: {host}"
        except Exception as e:
            return f"Benutzer-Fehler: {e}"

    @staticmethod
    def get_hostname() -> str:
        """Gibt den Hostnamen aus."""
        try:
            host = socket.gethostname()
            ip   = socket.gethostbyname(host)
            return f"Hostname: {host} | IP: {ip}"
        except Exception as e:
            return f"Hostname-Fehler: {e}"

    @staticmethod
    def show_env_vars() -> str:
        """Zeigt wichtige Umgebungsvariablen."""
        important = ["PATH", "HOME", "USERNAME", "USER", "TEMP", "TMP",
                     "APPDATA", "PROGRAMFILES", "COMPUTERNAME", "OS"]
        lines = []
        for key in important:
            val = os.environ.get(key, "")
            if val:
                lines.append(f"  {key}: {val[:60]}")
        return "Umgebungsvariablen:\n" + "\n".join(lines[:10]) if lines else "Keine Variablen gefunden."

    @staticmethod
    def file_info(filename: str) -> str:
        """Zeigt detaillierte Datei-Informationen."""
        for loc in ["Desktop", "Documents", "Downloads", "."]:
            path = Path(loc).expanduser() / filename if loc == "." else Path.home() / loc / filename
            if path.exists():
                try:
                    stat     = path.stat()
                    size_kb  = stat.st_size / 1024
                    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M")
                    created  = datetime.fromtimestamp(stat.st_ctime).strftime("%d.%m.%Y %H:%M")
                    return (f"Datei: {path.name}\n"
                            f"  Größe:    {size_kb:.1f} KB ({stat.st_size} Bytes)\n"
                            f"  Typ:      {path.suffix or 'ohne Erweiterung'}\n"
                            f"  Geändert: {modified}\n"
                            f"  Erstellt: {created}\n"
                            f"  Pfad:     {path.parent}")
                except Exception as e:
                    return f"Datei-Info-Fehler: {e}"
        return f"Datei '{filename}' nicht gefunden."

    @staticmethod
    def find_empty_folders(folder: str = "~/Desktop") -> str:
        """Findet leere Ordner."""
        try:
            path  = Path(folder).expanduser()
            empty = []
            for d in path.rglob("*"):
                if d.is_dir() and not any(d.iterdir()):
                    empty.append(d.name)
            if not empty:
                return f"Keine leeren Ordner in '{folder}'."
            return f"Leere Ordner ({len(empty)}):\n" + "\n".join(f"  • {e}" for e in empty[:10])
        except Exception as e:
            return f"Suche-Fehler: {e}"

    @staticmethod
    def search_in_file(filename: str, keyword: str) -> str:
        """Durchsucht eine Datei nach einem Keyword."""
        for loc in ["Desktop", "Documents", "Downloads"]:
            path = Path.home() / loc / filename
            if path.exists():
                try:
                    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
                    hits  = [(i+1, l.strip()) for i, l in enumerate(lines)
                             if keyword.lower() in l.lower()]
                    if not hits:
                        return f"'{keyword}' nicht in '{filename}' gefunden."
                    result = [f"  Zeile {n}: {l[:80]}" for n, l in hits[:10]]
                    return f"'{keyword}' in '{filename}' ({len(hits)} Treffer):\n" + "\n".join(result)
                except Exception as e:
                    return f"Suche-Fehler: {e}"
        return f"Datei '{filename}' nicht gefunden."

    @staticmethod
    def bulk_rename(folder: str, pattern: str, replacement: str) -> str:
        """Bulk-Umbenennen: alle Dateien mit pattern → replacement."""
        try:
            path    = Path(folder).expanduser()
            renamed = 0
            for f in path.iterdir():
                if f.is_file() and pattern in f.name:
                    new_name = f.name.replace(pattern, replacement)
                    f.rename(f.parent / new_name)
                    renamed += 1
            return f"{renamed} Dateien umbenannt ('{pattern}' → '{replacement}')."
        except Exception as e:
            return f"Bulk-Rename-Fehler: {e}"

    @staticmethod
    def open_ports() -> str:
        """Zeigt offene Netzwerk-Ports."""
        try:
            if IS_WINDOWS:
                r = SystemCommands._run(["netstat", "-ano"], timeout=10)
                lines = [l for l in r.stdout.splitlines() if "LISTENING" in l][:10]
                return "Offene Ports (LISTENING):\n" + "\n".join(f"  {l.strip()}" for l in lines)
            else:
                r = SystemCommands._run(["netstat", "-tlnp"], timeout=10)
                lines = r.stdout.strip().splitlines()[2:12]
                return "Offene Ports:\n" + "\n".join(f"  {l.strip()}" for l in lines)
        except Exception as e:
            return f"Port-Fehler: {e}"

    @staticmethod
    def arp_table() -> str:
        """Zeigt die ARP-Tabelle (Netzwerkgeräte)."""
        try:
            r = SystemCommands._run(["arp", "-a"], timeout=8)
            lines = [l.strip() for l in r.stdout.splitlines() if l.strip()][:15]
            return "ARP-Tabelle:\n" + "\n".join(f"  {l}" for l in lines)
        except Exception as e:
            return f"ARP-Fehler: {e}"

    @staticmethod
    def restart_network() -> str:
        """Netzwerk-Adapter neu starten."""
        try:
            if IS_WINDOWS:
                adapters_r = SystemCommands._run(
                    ["powershell", "-c",
                     "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object -ExpandProperty Name"])
                for adapter in adapters_r.stdout.strip().splitlines():
                    adapter = adapter.strip()
                    if adapter:
                        SystemCommands._run(["powershell", "-c",
                            f"Disable-NetAdapter -Name '{adapter}' -Confirm:$false"])
                        time.sleep(1)
                        SystemCommands._run(["powershell", "-c",
                            f"Enable-NetAdapter -Name '{adapter}' -Confirm:$false"])
                return "Netzwerk-Adapter neu gestartet."
            else:
                SystemCommands._run(["sudo", "ifconfig", "en0", "down"])
                time.sleep(1)
                SystemCommands._run(["sudo", "ifconfig", "en0", "up"])
                return "Netzwerk-Interface neu gestartet."
        except Exception as e:
            return f"Netzwerk-Fehler: {e}"

    @staticmethod
    def unit_convert(value: float, from_unit: str, to_unit: str) -> str:
        """Einheitenumrechnung: Länge, Gewicht, Temperatur."""
        conversions = {
            # Länge (Basis: Meter)
            "m": 1.0, "km": 1000.0, "cm": 0.01, "mm": 0.001,
            "meile": 1609.34, "meilen": 1609.34, "mile": 1609.34, "miles": 1609.34,
            "fuß": 0.3048, "foot": 0.3048, "feet": 0.3048, "ft": 0.3048,
            "inch": 0.0254, "zoll": 0.0254, "yard": 0.9144, "yd": 0.9144,
            # Gewicht (Basis: Kilogramm)
            "kg": 1.0, "g": 0.001, "mg": 0.000001, "t": 1000.0,
            "lb": 0.453592, "pfund": 0.453592, "lbs": 0.453592,
            "oz": 0.0283495, "unze": 0.0283495,
            # Fläche (Basis: m²)
            "m2": 1.0, "km2": 1e6, "cm2": 0.0001, "ha": 10000.0,
            "acre": 4046.86, "ar": 100.0,
            # Volumen (Basis: Liter)
            "l": 1.0, "ml": 0.001, "cl": 0.01, "dl": 0.1,
            "gallon": 3.78541, "gallone": 3.78541,
            # Datenmenge (Basis: Byte)
            "byte": 1, "kb": 1024, "mb": 1048576, "gb": 1073741824,
            "tb": 1099511627776,
        }
        from_l = from_unit.lower()
        to_l   = to_unit.lower()

        # Temperatur separat
        if from_l in ("celsius", "°c", "c") and to_l in ("fahrenheit", "°f", "f"):
            result = value * 9/5 + 32
            return f"{value}°C = {result:.2f}°F"
        if from_l in ("fahrenheit", "°f", "f") and to_l in ("celsius", "°c", "c"):
            result = (value - 32) * 5/9
            return f"{value}°F = {result:.2f}°C"
        if from_l in ("celsius", "°c", "c") and to_l in ("kelvin", "k"):
            result = value + 273.15
            return f"{value}°C = {result:.2f} K"
        if from_l in ("kelvin", "k") and to_l in ("celsius", "°c", "c"):
            result = value - 273.15
            return f"{value} K = {result:.2f}°C"

        if from_l in conversions and to_l in conversions:
            # Gleiche Kategorie prüfen (beide Länge, beide Gewicht...)
            result = value * conversions[from_l] / conversions[to_l]
            return f"{value} {from_unit} = {result:.6g} {to_unit}"

        return (f"Einheit '{from_unit}' oder '{to_unit}' unbekannt. "
                f"Verfügbar: m, km, cm, mm, mile, fuß, kg, g, lb, oz, l, ml, gb, mb, °C, °F...")

    @staticmethod
    def pomodoro(minutes: int = 25) -> str:
        """Startet einen Pomodoro-Timer."""
        msg = f"Pomodoro gestartet: {minutes} Minuten fokussierte Arbeit."
        return msg  # Timer wird extern gesetzt

    @staticmethod
    def clipboard_as_qr() -> str:
        """Erstellt QR-Code aus Clipboard-Inhalt."""
        if not QR_OK:
            return "qrcode/Pillow fehlt: pip install qrcode[pil] Pillow"
        try:
            if CLIPBOARD_OK:
                text = pyperclip.paste()
            else:
                if IS_WINDOWS:
                    r = SystemCommands._run(["powershell", "-c", "Get-Clipboard"])
                    text = r.stdout.strip()
                else:
                    r = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
                    text = r.stdout.strip()
            if not text:
                return "Clipboard ist leer."
            return SystemCommands.generate_qr(text)
        except Exception as e:
            return f"QR-Fehler: {e}"

    @staticmethod
    def word_count_clipboard() -> str:
        """Zählt Wörter/Zeichen im Clipboard."""
        try:
            if CLIPBOARD_OK:
                text = pyperclip.paste()
            else:
                if IS_WINDOWS:
                    r = SystemCommands._run(["powershell", "-c", "Get-Clipboard"])
                    text = r.stdout.strip()
                else:
                    r = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
                    text = r.stdout.strip()
            return SystemCommands.count_text(text)
        except Exception as e:
            return f"Fehler: {e}"

    @staticmethod
    def show_disk_partitions() -> str:
        """Zeigt alle Laufwerke/Partitionen."""
        if PSUTIL_OK:
            try:
                parts  = psutil.disk_partitions()
                lines  = []
                for p in parts:
                    try:
                        usage = psutil.disk_usage(p.mountpoint)
                        lines.append(
                            f"  {p.device} ({p.fstype}) "
                            f"→ {usage.free/1e9:.1f} GB frei / {usage.total/1e9:.1f} GB")
                    except Exception:
                        lines.append(f"  {p.device} ({p.fstype}) → nicht lesbar")
                return "Laufwerke:\n" + "\n".join(lines)
            except Exception as e:
                return f"Partition-Fehler: {e}"
        return SystemCommands.disk_space()

    @staticmethod
    def open_sap() -> str:
        """Kompatibilität: SAP öffnen."""
        return APP_ENGINE.open_app("saplogon")

    @staticmethod
    def open_excel() -> str:
        return APP_ENGINE.open_app("excel")

    @staticmethod
    def open_word() -> str:
        return APP_ENGINE.open_app("winword")

    @staticmethod
    def open_outlook() -> str:
        return APP_ENGINE.open_app("outlook")

    @staticmethod
    def open_teams() -> str:
        return APP_ENGINE.open_app("teams")

    @staticmethod
    def open_notes() -> str:
        if IS_WINDOWS:
            return APP_ENGINE.open_app("notepad")
        return APP_ENGINE.open_app("notes")

    @staticmethod
    def open_todo() -> str:
        if IS_MACOS:
            return APP_ENGINE.open_app("reminders")
        SystemCommands._open_file_or_url("https://to-do.microsoft.com")
        return "Microsoft To-Do geöffnet."

    @staticmethod
    def open_paint() -> str:
        if IS_WINDOWS:
            return APP_ENGINE.open_app("mspaint")
        return "Paint nur auf Windows verfügbar."

    @staticmethod
    def open_app(name: str) -> str:
        """Universelles App-Öffnen via UniversalAppEngine."""
        return APP_ENGINE.open_app(name)


# ═══════════════════════════════════════════════════════════════════════════════
#  BEFEHLSPARSING v10.3
# ═══════════════════════════════════════════════════════════════════════════════

class CommandParser:

    def __init__(self):
        self.cmd  = SystemCommands()
        self.wake = WakeWordDetector(CFG.get("wake_word", "aera"))

    def _split_commands(self, text: str) -> List[str]:
        """
        v10: NEU — Robusteres Multi-Command Splitting
        Trennt Befehle anhand von Konjunktionen, aber NICHT innerhalb von App-Namen.
        """
        if not text:
            return []

        text = text.strip()
        if not text:
            return []

        # v10: Definiere alle bekannten Verben (erweiterte Liste)
        ALL_VERBS = {
            'öffne', 'öffnen', 'starte', 'starten', 'launch', 'open', 'zeig', 'führe',
            'schließe', 'beende', 'kille', 'stoppe', 'close', 'quit', 'suche', 'finde',
            'such', 'mach', 'mache', 'stell', 'stelle', 'drucke', 'lösche', 'berechne',
            'rechne', 'timer', 'erinnerung', 'screenshot', 'akku', 'batterie', 'wetter',
            'kurs', 'preis', 'bitcoin', 'aktie', 'ip', 'uhrzeit', 'datum', 'sap',
            'excel', 'word', 'outlook', 'teams', 'browser', 'terminal', 'herunterfahren',
            'neustart', 'festplatte', 'dns', 'bluetooth', 'lautstärke', 'helligkeit',
            'zip', 'ordner', 'datei', 'download', 'papierkorb', 'backup', 'youtube',
            'amazon', 'maps', 'navigation', 'nachrichten', 'news', 'übersetze',
            'installiere', 'install', 'passwort', 'qr', 'ping', 'witz', 'würfeln',
            'münze', 'notiz', 'uptime', 'wlan', 'clipboard', 'cpu', 'ram', 'apps',
            'uuid', 'base64', 'hex', 'rgb', 'hostname', 'benutzername', 'ports',
            'pomodoro', 'fokus', 'groß', 'klein', 'zähle', 'json', 'umrechnen',
            'konvertiere', 'leere', 'suche', 'prüfe', 'check', 'googl', 'google',
            'diktiere', 'lies', 'vorlesen', 'speichere', 'bookmark', 'link',
            'erstelle', 'neu', 'neuer', 'neuen', 'verschiebe', 'bilder', 'fotos',
            'lösche', 'alte', 'versteckte', 'hidden', 'zeige', 'anzeigen',
            'system', 'info', 'task', 'manager', 'aktivitätsanzeige', 'monitor',
            'display', 'bildschirm', 'sperre', 'lock', 'schlaf', 'ruhe',
            'hibernate', 'screensaver', 'bildschirmschoner', 'temp', 'bereinige',
            'leere', 'papierkorb', 'trash', 'desktop', 'sichere', 'backup',
            'letztes', 'zuletzt', 'drucke', 'print', 'einkaufsliste', 'shopping',
            'gute', 'nacht', 'feierabend', 'motivation', 'zitat', 'spruch',
            'weisheit', 'beep', 'piep', 'ton', 'vorlesen', 'diktat',
        }

        # v10: Konjunktionen/Trennzeichen (als ganze Wörter)
        CONJUNCTIONS = [' und ', ' sowie ', ' außerdem ', ' dann ', ' danach ', ' anschließend ', ' danach ']
        WEAK_CONJUNCTIONS = [';', ', ']  # Schwache Trennzeichen (nur wenn danach ein Verb folgt)

        # Schritt 1: Finde alle Positionen, an denen ein neuer Befehl beginnt
        command_positions = [0]  # Start immer bei 0
        text_lower = text.lower()

        # Suche nach starken Konjunktionen (immer trennen)
        for conj in CONJUNCTIONS:
            start = 0
            while True:
                idx = text_lower.find(conj, start)
                if idx == -1:
                    break
                # Prüfe: Steht danach ein Verb?
                after = text_lower[idx + len(conj):].strip()
                # Finde das nächste Wort nach der Konjunktion
                next_word_match = re.match(r'^(\w+)', after)
                if next_word_match:
                    next_word = next_word_match.group(1).lower()
                    if next_word in ALL_VERBS or any(next_word.startswith(v) for v in ALL_VERBS):
                        command_positions.append(idx)
                        command_positions.append(idx + len(conj))
                start = idx + 1

        # Schritt 2: Schwache Trennzeichen nur trennen, wenn danach ein Verb folgt
        for sep in WEAK_CONJUNCTIONS:
            start = 0
            while True:
                idx = text_lower.find(sep, start)
                if idx == -1:
                    break
                after = text_lower[idx + len(sep):].strip()
                next_word_match = re.match(r'^(\w+)', after)
                if next_word_match:
                    next_word = next_word_match.group(1).lower()
                    if next_word in ALL_VERBS or any(next_word.startswith(v) for v in ALL_VERBS):
                        command_positions.append(idx)
                        command_positions.append(idx + len(sep))
                start = idx + 1

        # Sortiere und entferne Duplikate
        command_positions = sorted(set(command_positions))

        # Schritt 3: Extrahiere Befehle aus den Positionen
        commands = []
        for i in range(len(command_positions)):
            start = command_positions[i]
            end = command_positions[i + 1] if i + 1 < len(command_positions) else len(text)
            segment = text[start:end].strip(' ,;')
            if segment and len(segment) >= 2:
                commands.append(segment)

        # Schritt 4: Bereinige — entferne leere und zu kurze Befehle
        commands = [cmd.strip() for cmd in commands if len(cmd.strip()) >= 2]

        # Schritt 5: Wenn kein Split erfolgt ist, versuche es mit Regex als Fallback
        if len(commands) <= 1 and len(text) > 10:
            # Fallback: Splitte an " und " wenn klar erkennbar
            # Aber nur wenn beide Teile sinnvoll aussehen
            for conj in [' und ', ' sowie ']:
                if conj in text_lower:
                    parts = text.split(conj)
                    if len(parts) == 2:
                        left, right = parts[0].strip(), parts[1].strip()
                        # Prüfe ob rechts ein Verb hat oder ein App-Name ist
                        right_lower = right.lower()
                        has_verb = any(v in right_lower for v in ALL_VERBS)
                        is_app_name = len(right.split()) <= 3  # Kurze Phrase = wahrscheinlich App-Name
                        if has_verb or is_app_name:
                            return [left, right]

        return commands if commands else [text]


    def parse(self, text: str) -> Optional[Union[str, List[str]]]:
        """
        v10: NEU — Verbesserte Multi-Command-Erkennung
        Unterstützt jetzt zuverlässig mehrere Befehle gleichzeitig!

        Beispiele:
          "AERA öffne WhatsApp und Excel"
          "AERA suche Erdkunde Arbeitsblatt und öffne WhatsApp"
          "AERA öffne Chrome, starte Spotify und zeig CPU"
          "AERA öffne Word; suche Rechnung; starte Timer 5 Minuten"
        """
        text = FILLER.clean(text)
        t    = text.lower().strip()
        t    = self.wake.strip_wake_word(t)

        if not t or len(t) < 2:
            return None

        # v10: Prüfe auf Mehrfachbefehle mit verbesserter Engine
        sub_commands = self._split_commands(t)

        if len(sub_commands) > 1:
            # Mehrere Befehle gefunden — alle einzeln parsen
            results = []
            for cmd in sub_commands:
                result = self._parse_single(cmd)
                if result:
                    results.append(result)

            if len(results) == 1:
                return results[0]
            elif len(results) > 1:
                return results  # Liste von Ergebnissen
            return None

        # Einzelbefehl — normal weiter
        return self._parse_single(t)

    def _parse_single(self, t: str) -> Optional[str]:
        """Original parse-Logik für einen einzelnen Befehl."""

        t = FILLER.clean(t)
        t = t.lower().strip()
        t    = self.wake.strip_wake_word(t)

        if not t or len(t) < 2:
            return None

        # ── UNIVERSAL APP ENGINE — ÖFFNEN ────────────────────────────────────
        # Muss VOR spezifischen App-Checks stehen!
        m = re.search(
            r"^(?:öffne?|starte?|launch|open|zeig|führe?\s+aus?)\s+"
            r"(?:die\s+(?:app|anwendung|program(?:m)?)\s+|das\s+(?:program(?:m)?)\s+)?"
            r"[\"']?(.+?)[\"']?\s*$", t)
        if m:
            app_name = m.group(1).strip()
            # Nicht mit System-Befehlen kollidieren
            skip = {"browser", "terminal", "downloads", "notepad", "texteditor",
                    "task-manager", "taskmanager", "datei", "ordner", "einstellungen"}
            if app_name not in skip and len(app_name) > 1:
                                # NEU v10: Lerne diese App-Öffnung für Smart Learning
                if hasattr(self, 'smart_learning') and self.smart_learning:
                    self.smart_learning.record_action("app_open", app_name)
                return APP_ENGINE.open_app(app_name)

        # ── UNIVERSAL APP ENGINE — SCHLIESSEN ────────────────────────────────
        m = re.search(
            r"(?:schließe?|beende?|kille?|stoppe?|close|quit)\s+"
            r"(?:die\s+(?:app|anwendung|program(?:m)?)\s+|den\s+prozess\s+)?"
            r"[\"']?(.+?)[\"']?\s*$", t)
        if m:
            app_name = m.group(1).strip()
            if len(app_name) > 1:
                return APP_ENGINE.close_app(app_name)

        # ── APP ENGINE VERWALTUNG ─────────────────────────────────────────────
        if any(x in t for x in ["apps aktualisieren", "app cache", "app-cache"]):
            return APP_ENGINE.refresh()
        if any(x in t for x in ["installierte apps", "apps auflisten", "alle apps"]):
            m = re.search(r"(?:apps\s+(?:suchen|filtern|mit)|filter)\s+(.+)", t)
            return APP_ENGINE.list_installed(m.group(1).strip() if m else "")
        if any(x in t for x in ["laufende apps", "laufende prozesse", "aktive prozesse"]):
            return APP_ENGINE.list_running()

        # ── v7/v8-BEFEHLE ────────────────────────────────────────────────────

        m = re.search(r"(?:fahr|shutdown|herunter|aus).*?(\d+)\s*(?:minuten|min)", t)
        if m:
            return self.cmd.shutdown(int(m.group(1)))

        if any(x in t for x in ["neu starten", "neustart", "restart", "reboot"]):
            return self.cmd.restart()
        if any(x in t for x in ["schlafmodus", "sleep", "suspend", "ruhezustand", "hibernate"]):
            if "ruhezustand" in t or "hibernate" in t:
                return self.cmd.hibernate()
            return self.cmd.sleep_system()
        if any(x in t for x in ["bildschirmschoner", "screensaver"]):
            return self.cmd.screensaver()
        if any(x in t for x in ["akku", "batterie", "battery", "wie viel laden", "ladestand"]):
            return self.cmd.battery_status()
        if any(x in t for x in ["monitor aus", "display aus", "bildschirm aus"]):
            return self.cmd.display_off()
        if any(x in t for x in ["sperren", "bildschirm sperren", "lock"]):
            return self.cmd.lock_screen()
        if any(x in t for x in ["screenshot", "bildschirmfoto"]):
            return self.cmd.screenshot()
        if any(x in t for x in ["festplatte", "speicherplatz", "freier speicher", "disk"]):
            if any(x in t for x in ["partition", "laufwerke"]):
                return self.cmd.show_disk_partitions()
            return self.cmd.disk_space()
        if any(x in t for x in ["ip-adresse", "ip adresse", "meine ip", "ip address"]):
            return self.cmd.ip_address()
        if any(x in t for x in ["task-manager", "taskmanager", "aktivitätsanzeige"]):
            return self.cmd.open_task_manager()
        if any(x in t for x in ["papierkorb", "trash", "müll leeren"]):
            return self.cmd.empty_trash()
        if any(x in t for x in ["systeminfo", "system info", "pc info"]):
            return self.cmd.system_info()
        if any(x in t for x in ["netzwerkinfo", "netzwerk info", "netzwerk status"]):
            return self.cmd.network_info()
        if any(x in t for x in ["energiesparmodus", "stromsparmodus"]):
            return self.cmd.energy_mode(True)

        m = re.search(r"helligkeit\s*(?:auf)?\s*(\d+)", t)
        if m:
            return self.cmd.set_brightness(int(m.group(1)))

        if any(x in t for x in ["bluetooth ein", "bluetooth an"]):
            return self.cmd.bluetooth(True)
        if "bluetooth aus" in t:
            return self.cmd.bluetooth(False)
        if any(x in t for x in ["temp leeren", "temp bereinigen", "temporäre dateien"]):
            return self.cmd.clean_temp()
        if any(x in t for x in ["dns", "dns cache", "dns leeren"]):
            return self.cmd.clear_dns_cache()
        if any(x in t for x in ["netzwerk neu starten", "wlan neu starten", "adapter neu"]):
            return self.cmd.restart_network()

        m = re.search(r"lautstärke\s*(?:auf)?\s*(\d+)", t)
        if m:
            return self.cmd.set_volume(int(m.group(1)))
        if "stumm" in t or "mute" in t:
            return self.cmd.set_volume(0)
        if any(x in t for x in ["internet speed", "internetgeschwindigkeit", "bandbreite"]):
            return self.cmd.internet_speed()

        m = re.search(r"(?:erstelle?|neuer?)\s+ordner\s+(?:namens?|mit\s+namen?\s+)?[\"']?([^\"']+)[\"']?", t)
        if m:
            return self.cmd.create_folder(m.group(1).strip())

        if any(x in t for x in ["download", "downloads öffnen"]):
            return self.cmd.open_downloads()
        if any(x in t for x in ["duplikate", "doppelte dateien"]):
            return self.cmd.find_duplicates()
        if any(x in t for x in ["versteckte dateien", "hidden files"]):
            return self.cmd.show_hidden_files()
        if any(x in t for x in ["backup desktop", "desktop sichern"]):
            return self.cmd.backup_desktop()
        if any(x in t for x in ["bilder verschieben", "fotos verschieben"]):
            return self.cmd.move_images()

        m = re.search(r"(?:zip|pack|komprimiere?)\s+(?:ordner\s+)?[\"']?([^\"']+)[\"']?", t)
        if m:
            return self.cmd.zip_folder(m.group(1).strip())

        if any(x in t for x in ["letztes dokument", "zuletzt bearbeitet"]):
            return self.cmd.open_last_document()
        if any(x in t for x in ["letzte pdf", "neueste pdf", "pdf öffnen"]):
            return self.cmd.open_recent_pdf()

        m = re.search(r"(?:drucke?|print)\s+(?:dokument\s+)?[\"']?([^\"']+\.\w+)[\"']?", t)
        if m:
            return self.cmd.print_document(m.group(1).strip())

        m = re.search(r"(?:diktiere?|schreibe?\s+auf|notiere?)\s*:?\s*(.+)", t)
        if m and "ordner" not in t and "notiz" not in t:
            return self.cmd.dictate_text(m.group(1).strip())

        m = re.search(r"wetter\s+(?:in|für)?\s*([a-zäöüß\s]+)", t)
        if m:
            return self.cmd.get_weather(m.group(1).strip())
        if "wetter" in t:
            return self.cmd.get_weather()

        m = re.search(r"youtube\s+(.+)", t)
        if not m:
            m = re.search(r"(?:suche?)\s+youtube\s+(.+)", t)
        if m:
            return self.cmd.youtube_search(m.group(1).strip())

        if any(x in t for x in ["bitcoin", "btc", "krypto"]):
            return self.cmd.bitcoin_price()

        m = re.search(r"(?:aktie|kurs|börsenkurs)\s+(?:von\s+)?([a-z]{1,5})", t)
        if m:
            return self.cmd.stock_price(m.group(1).upper())

        if any(x in t for x in ["nachrichten", "news öffnen", "tagesschau"]):
            return self.cmd.open_news()
        if any(x in t for x in ["e-mail", "email öffnen", "postfach"]):
            return self.cmd.open_email()
        if "whatsapp" in t:
            return self.cmd.open_whatsapp()

        m = re.search(r"(?:übersetze?)\s+(.+?)\s+(?:ins?|auf|to)\s+([a-zäöüß]+)", t)
        if m:
            lang_map = {"englisch": "en", "spanisch": "es", "französisch": "fr",
                        "italian": "it", "japanisch": "ja"}
            lang = lang_map.get(m.group(2).lower(), m.group(2)[:2])
            return self.cmd.translate(m.group(1).strip(), lang)

        m = re.search(r"amazon\s+(.+)", t)
        if m:
            return self.cmd.amazon_search(m.group(1).strip())

        m = re.search(r"(?:navigation|maps|route)\s+(?:nach\s+)?(.+)", t)
        if m:
            return self.cmd.maps_navigate(m.group(1).strip())

        if "chatgpt" in t:
            return self.cmd.open_chatgpt()

        m = re.search(r"(?:prüf|check)\s+(?:ob\s+)?(?:webseite\s+)?([a-z0-9\-\.]+\.[a-z]{2,})", t)
        if m:
            return self.cmd.check_website(m.group(1))

        m = re.search(r"(?:rezept|rezept\s+für)\s+(.+)", t)
        if m:
            return self.cmd.search_recipe(m.group(1).strip())

        m = re.search(r"(?:news|nachrichten)\s+(?:über|zu)\s+(.+)", t)
        if m:
            return self.cmd.search_news(m.group(1).strip())

        m = re.search(r"(?:umrechnen|konvertiere?)\s+([\d.]+)\s+([a-zäöüß°]+\d*)\s+(?:in|zu|nach)\s+([a-zäöüß°]+\d*)", t)
        if m:
            try:
                val = float(m.group(1))
                return self.cmd.unit_convert(val, m.group(2), m.group(3))
            except Exception:
                pass

        m = re.search(r"(?:umrechnen|konvertiere?)\s+([\d.]+)\s+([a-z]+)\s+(?:in|zu)\s+([a-z]+)", t)
        if m:
            try:
                return self.cmd.convert_currency(float(m.group(1)), m.group(2), m.group(3))
            except Exception:
                pass

        m = re.search(r"(?:was bedeutet|duden|definition)\s+([a-zäöüß]+)", t)
        if m:
            return self.cmd.define_word(m.group(1))

        m = re.search(r"(?:googl|suche\s+nach)\s+(.+)", t)
        if m and "youtube" not in t and "amazon" not in t:
            return self.cmd.google_search(m.group(1).strip())

        if any(x in t for x in ["browser", "internet öffnen"]):
            return self.cmd.open_browser()

        if any(x in t for x in ["terminal", "konsole", "cmd", "eingabeaufforderung"]):
            return self.cmd.open_terminal()
        if any(x in t for x in ["taschenrechner", "calculator", "rechner öffnen"]):
            return self.cmd.open_calculator()
        if any(x in t for x in ["notepad", "texteditor"]):
            return self.cmd.open_notepad()
        if any(x in t for x in ["einstellungen", "systemeinstellungen", "settings"]):
            return self.cmd.open_system_settings()
        if any(x in t for x in ["notizen öffnen", "notes öffnen"]):
            return self.cmd.open_notes()
        if any(x in t for x in ["to-do", "todo", "aufgaben", "erinnerungen"]):
            return self.cmd.open_todo()

        m = re.search(r"(?:installiere?|install)\s+([a-z0-9_\-]+)", t)
        if m:
            return self.cmd.install_package(m.group(1))

        m = re.search(r"(?:rechne?|berechne?|wie viel ist)\s+(.+)", t)
        if m:
            return self.cmd.calculate(m.group(1).strip())

        m = re.search(r"(?:erinnerung)\s+(?:für|an)?\s*[\"']?(.+?)[\"']?\s+in\s+(\d+)\s*min", t)
        if m:
            return self.cmd.set_reminder(m.group(1).strip(), int(m.group(2)))

        m = re.search(r"(?:uhrzeit|wie spät)\s+(?:in|bei)\s+([a-zäöüß\s]+)", t)
        if m:
            return self.cmd.world_clock(m.group(1).strip())

        if any(x in t for x in ["weihnachten", "wie viele tage"]):
            return self.cmd.days_until_christmas()
        if any(x in t for x in ["einkaufsliste", "shopping list"]):
            return self.cmd.create_shopping_list()
        if any(x in t for x in ["gute nacht", "feierabend", "goodnight"]):
            return self.cmd.goodnight()

        m = re.search(r"(?:lies?\s+vor|vorlesen|sprich)\s*:?\s*(.+)", t)
        if m:
            return self.cmd.speak_text(m.group(1).strip())

        if any(x in t for x in ["link speichern", "url speichern", "bookmark"]):
            return self.cmd.save_bookmark()

        # ── v8-TOOLS ─────────────────────────────────────────────────────────

        if any(x in t for x in ["clipboard lesen", "zwischenablage lesen",
                                  "was ist in der zwischenablage", "clipboard zeigen"]):
            return self.cmd.clipboard_read()

        m = re.search(r"(?:clipboard|zwischenablage)\s+(?:kopiere?|schreibe?|setze?)\s+(.+)", t)
        if m:
            return self.cmd.clipboard_write(m.group(1).strip())

        if any(x in t for x in ["clipboard als qr", "zwischenablage als qr"]):
            return self.cmd.clipboard_as_qr()

        if any(x in t for x in ["wörter zählen", "wörter im clipboard", "zeichen zählen"]):
            return self.cmd.word_count_clipboard()

        m = re.search(r"(?:passwort|password)\s+(?:generiere?n?|erstelle?n?|neues?)(?:\s+(\d+)\s*(?:zeichen|stellen?|chars?))?", t)
        if m:
            length = int(m.group(1)) if m.group(1) else 16
            return self.cmd.generate_password(length)
        if any(x in t for x in ["neues passwort", "sicheres passwort", "zufälliges passwort"]):
            return self.cmd.generate_password()

        m = re.search(r"(?:qr|qr-code|qrcode)\s+(?:für|von|erstelle?n?)?\s*(.+)", t)
        if m:
            return self.cmd.generate_qr(m.group(1).strip())

        if any(x in t for x in ["uptime", "laufzeit", "seit wann läuft", "wie lang läuft"]):
            return self.cmd.get_uptime()

        m = re.search(r"ping\s+([a-z0-9\.\-]+)", t)
        if m:
            return self.cmd.ping_host(m.group(1).strip())
        if "ping" in t:
            return self.cmd.ping_host()

        if any(x in t for x in ["öffentliche ip", "externe ip", "public ip", "was ist meine externe"]):
            return self.cmd.public_ip()

        if any(x in t for x in ["webcam", "kamera foto", "webcam foto", "selfie"]):
            return self.cmd.webcam_snapshot()

        if any(x in t for x in ["witz", "witze", "joke", "erzähl einen witz", "erzähl mir was lustiges"]):
            return self.cmd.tell_joke()

        m = re.search(r"(?:würfel|würfle?|roll)\s+(?:einen?\s+)?(\d+)\s*(?:-?seitig(?:en?)?)?", t)
        if m:
            return self.cmd.roll_dice(int(m.group(1)))
        if any(x in t for x in ["würfeln", "würfelwurf", "zufallszahl"]):
            return self.cmd.roll_dice()

        if any(x in t for x in ["münze", "münzwurf", "kopf oder zahl", "coin flip"]):
            return self.cmd.flip_coin()

        if any(x in t for x in ["motivation", "zitat", "motiviere mich", "spruch", "weisheit"]):
            return self.cmd.motivation_quote()

        if any(x in t for x in ["wlan", "wifi", "netzwerkname", "ssid"]):
            return self.cmd.wifi_info()

        m = re.search(r"(?:quick\s+)?notiz\s*:?\s*(.+)", t)
        if m and "lesen" not in t and "zeigen" not in t:
            return self.cmd.quick_note(m.group(1).strip())

        if any(x in t for x in ["notizen lesen", "notizen zeigen", "meine notizen"]):
            return self.cmd.read_notes()

        m = re.search(r"(?:hash|prüfsumme|checksum)\s+(?:von\s+)?[\"']?([^\"'\s]+\.\w+)[\"']?", t)
        if m:
            algo = "sha256" if "sha" in t else "md5"
            return self.cmd.file_hash(m.group(1).strip(), algo)

        if any(x in t for x in ["beep", "piep", "ton ausgeben", "systemton"]):
            return self.cmd.system_beep()

        if any(x in t for x in ["lautstärke anzeigen", "aktuelle lautstärke", "wie laut"]):
            return self.cmd.get_volume()

        m = re.search(r"(?:lies?\s+vor|vorlesen)\s+(?:datei\s+)?[\"']?([^\"'\s]+\.\w+)[\"']?", t)
        if m:
            return self.cmd.read_file_aloud(m.group(1).strip())

        # ── v9-NEUE TOOLS ─────────────────────────────────────────────────────

        if any(x in t for x in ["cpu", "prozessorauslastung", "cpu-auslastung"]):
            return self.cmd.cpu_usage()

        if any(x in t for x in ["ram", "arbeitsspeicher", "speicherauslastung", "ram-auslastung"]):
            return self.cmd.ram_usage()

        if any(x in t for x in ["top prozesse", "ressourcen", "prozesse nach cpu"]):
            return self.cmd.top_processes()

        if any(x in t for x in ["netzwerk traffic", "netzwerktraffic", "datentransfer"]):
            return self.cmd.network_traffic()

        if any(x in t for x in ["uuid", "unique id", "eindeutige id"]):
            return self.cmd.generate_uuid()

        m = re.search(r"(?:groß|uppercase|großbuchstaben)\s*:?\s*(.+)", t)
        if m:
            return self.cmd.text_to_upper(m.group(1).strip())

        m = re.search(r"(?:klein|lowercase|kleinbuchstaben)\s*:?\s*(.+)", t)
        if m:
            return self.cmd.text_to_lower(m.group(1).strip())

        m = re.search(r"(?:text\s+)?(?:zähle?|anzahl)\s*:?\s*(.+)", t)
        if m and any(x in t for x in ["wörter", "zeichen", "zeilen"]):
            return self.cmd.count_text(m.group(1).strip())

        m = re.search(r"base64\s+(?:encode|kodier[en]*|verschlüssel)\s*:?\s*(.+)", t)
        if m:
            return self.cmd.base64_encode(m.group(1).strip())

        m = re.search(r"base64\s+(?:decode|dekodier[en]*|entschlüssel)\s*:?\s*(.+)", t)
        if m:
            return self.cmd.base64_decode(m.group(1).strip())

        if any(x in t for x in ["json formatieren", "json format", "json pretty"]):
            return self.cmd.json_format()

        m = re.search(r"hex\s+(?:zu|nach|to)\s+rgb\s*:?\s*([0-9a-fA-F#]+)", t)
        if m:
            return self.cmd.hex_to_rgb(m.group(1))

        m = re.search(r"rgb\s+(?:zu|nach|to)\s+hex\s*:?\s*(\d+)\s*[,\s]+(\d+)\s*[,\s]+(\d+)", t)
        if m:
            return self.cmd.rgb_to_hex(int(m.group(1)), int(m.group(2)), int(m.group(3)))

        if any(x in t for x in ["benutzername", "wer bin ich", "benutzer"]):
            return self.cmd.get_username()

        if any(x in t for x in ["hostname", "computername", "rechnername"]):
            return self.cmd.get_hostname()

        if any(x in t for x in ["umgebungsvariablen", "environment", "env vars"]):
            return self.cmd.show_env_vars()

        m = re.search(r"datei\s+info\s+[\"']?([^\"'\s]+)[\"']?", t)
        if m:
            return self.cmd.file_info(m.group(1).strip())

        if any(x in t for x in ["leere ordner", "leere verzeichnisse"]):
            return self.cmd.find_empty_folders()

        m = re.search(r"suche?\s+(?:in\s+)?(?:datei\s+)?[\"']?([^\"'\s]+\.\w+)[\"']?\s+(?:nach\s+)?[\"']?([^\"']+)[\"']?", t)
        if m:
            return self.cmd.search_in_file(m.group(1).strip(), m.group(2).strip())

        if any(x in t for x in ["offene ports", "ports anzeigen", "netstat"]):
            return self.cmd.open_ports()

        if any(x in t for x in ["arp tabelle", "arp-tabelle", "netzwerkgeräte"]):
            return self.cmd.arp_table()

        m = re.search(r"(?:pomodoro|fokus-timer|fokustimer)\s*(?:(\d+)\s*(?:min|minuten?))?", t)
        if m:
            mins = int(m.group(1)) if m.group(1) else 25
            return self.cmd.pomodoro(mins)

        m = re.search(r"(?:laufwerke|partitionen|alle\s+laufwerke)", t)
        if m:
            return self.cmd.show_disk_partitions()

        # ── SMART LEARNING v10.2 ────────────────────────────────────────────
        if any(x in t for x in ["gewohnheiten", "meine gewohnheiten", "habits zeigen",
                                  "statistik", "meine statistik", "lern-statistik"]):
            if hasattr(self, 'smart_learning') and self.smart_learning:
                return self.smart_learning.get_habit_stats()
            return "Smart Learning nicht verfügbar."

        if any(x in t for x in ["lern-modus aus", "smart learning aus", "vorschläge aus",
                                  "keine vorschläge", "stop lernen"]):
            CFG.set("smart_learning_suggestions", False)
            return "🔕 Smart Learning Vorschläge deaktiviert."

        if any(x in t for x in ["lern-modus an", "smart learning an", "vorschläge an",
                                  "aktiviere vorschläge", "start lernen"]):
            CFG.set("smart_learning_suggestions", True)
            return "🔔 Smart Learning Vorschläge aktiviert."

        if any(x in t for x in ["vergiss alles", "lösche gewohnheiten", "reset habits",
                                  "lösche meine daten", "vergiss meine gewohnheiten"]):
            if hasattr(self, 'smart_learning') and self.smart_learning:
                return self.smart_learning.clear_habits()
            return "Smart Learning nicht verfügbar."

        # NEU v10.2: Natural TTS Toggle
        if any(x in t for x in ["natürliche tts", "natural tts", "menschliche antworten",
                                  "natürliche antworten", "tts natürlich"]):
            current = CFG.get("natural_tts", True)
            CFG.set("natural_tts", not current)
            status = "aktiviert" if not current else "deaktiviert"
            return f"🎙 Natürliche TTS-Antworten {status}."

        if any(x in t for x in ["technische tts", "rohe tts", "original tts"]):
            CFG.set("natural_tts", False)
            return "🎙 Technische TTS-Antworten aktiviert."

        # ═════════════════════════════════════════════════════════════════
        #  V10.3 FIX: Smart Learning Ja/Nein NUR bei aktivem Vorschlag!
        # ═════════════════════════════════════════════════════════════════
        # Prüfe ZUERST ob ein pending_suggestion existiert, bevor wir
        # auf "ja/nein" reagieren. Sonst wird "Ranking von Physikern"
        # fälschlicherweise als Vorschlags-Antwort interpretiert.
        if hasattr(self, 'smart_learning') and self.smart_learning:
            with self.smart_learning._suggestion_lock:
                has_pending = len(self.smart_learning.pending_suggestions) > 0
            if has_pending:
                positive = ["ja", "ok", "gern", "gerne", "bitte", "mach", "mache",
                            "ja bitte", "klar", "sicher", "auf jeden fall", "jo",
                            "jop", "yep", "yes", "jawohl", "in ordnung", "einverstanden",
                            "ok mach", "ja mach", "öffne", "starte"]
                negative = ["nein", "ne", "nö", "nope", "no", "nicht", "lieber nicht",
                            "später", "nicht jetzt", "nein danke", "lass mal", "abgelehnt",
                            "nicht nötig", "brauch ich nicht", "vergiss es", "stop",
                            "lösch den vorschlag", "ignorieren"]
                if any(p in t for p in positive):
                    return self.smart_learning.handle_user_response("ja")
                if any(n in t for n in negative):
                    return self.smart_learning.handle_user_response("nein")

        # ── KALENDER ─────────────────────────────────────────────────────────
        if any(x in t for x in ["kalender", "calendar", "öffne kalender", "termin", "termine"]):
            if any(x in t for x in ["neuer", "neuen", "erstelle", "setze", "stelle", "füge", "plane"]):
                return "KALENDER_ADD"
            if any(x in t for x in ["lies", "vorlesen", "lese", "was habe ich", "meine termine"]):
                return "KALENDER_READ"
            return "KALENDER_GUI"

        # ── Fallback: App öffnen am Ende (breiter Pattern) ──────────────────
        # Für alles was wie eine App klingt aber nicht spezifisch erkannt wurde
        m_app = re.search(r"^(?:öffne?|starte?)\s+(.+)$", t)
        if m_app:
            return APP_ENGINE.open_app(m_app.group(1).strip())

        # ── OLLAMA AI COMMANDS v10.2 ────────────────────────────────────────
        if any(x in t for x in ["lokale status", "ai status", "ki status", "llm status"]):
            if hasattr(self, 'ollama_engine') and self.ollama_engine:
                return self.ollama_engine.get_status()
            return "🧠 Lokale LLM-Engine nicht initialisiert."

        if any(x in t for x in ["lokale an", "ai an", "ki an", "llm an", "aktiviere lokale", "aktiviere ki"]):
            if hasattr(self, 'ollama_engine') and self.ollama_engine:
                return self.ollama_engine.toggle()
            return "Lokale LLM-Engine nicht verfügbar."

        if any(x in t for x in ["lokale aus", "ai aus", "ki aus", "llm aus", "deaktiviere lokale", "deaktiviere ki"]):
            if hasattr(self, 'ollama_engine') and self.ollama_engine:
                return self.ollama_engine.toggle()
            return "Lokale LLM-Engine nicht verfügbar."

        if any(x in t for x in ["vergiss historie", "lösche historie", "clear history", "reset ki"]):
            if hasattr(self, 'ollama_engine') and self.ollama_engine:
                return self.ollama_engine.clear_history()
            return "Lokale LLM-Engine nicht verfügbar."

        if any(x in t for x in ["token limit", "max tokens", "token einstellen"]):
            m = re.search(r'(\d+)', t)
            if m and hasattr(self, 'ollama_engine') and self.ollama_engine:
                return self.ollama_engine.set_max_tokens(int(m.group(1)))
            return "Token-Limit konnte nicht gesetzt werden."

        if any(x in t for x in ["wechsle modell", "ändere modell", "model wechseln"]):
            m = re.search(r'(?:modell|model|zu|auf)\s+([a-zA-Z0-9\.:_-]+)', t)
            if m and hasattr(self, 'ollama_engine') and self.ollama_engine:
                return self.ollama_engine.set_model(m.group(1))
            return "Modell konnte nicht gewechselt werden."

        # V10.3 FIX: Kein Befehlsfragment-Check mehr!
        # Der fragment-Check wurde entfernt, damit allgemeine Fragen
        # wie "Ranking von Physikern" direkt an lokale LLMs gehen.
        # Der Parser gibt None zurück → Lokaler LLM-Fallback wird getriggert.
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  ALWAYS-ON SPRACHERKENNUNG
# ═══════════════════════════════════════════════════════════════════════════════

class AlwaysOnVoice:

    SHORT_CMDS = {
        "hallo":       "Hallo! Ich bin AERA Version 10.1. Smart Learning v2 aktiv.",
        "hi":          "Hi! Alle Systeme online.",
        "moin":        "Moin! Schieß los.",
        "status":      "Alle Systeme nominal. Universal App Engine bereit.",
        "danke":       "Gerne! Jederzeit.",
        "tschüss":     "Bis dann! AERA geht in Standby.",
        "version":     "A.E.R.A Version 10.1.7. Multi-Command Edition.",
        "hilfe":       "Sage AERA plus Befehl. Zum Beispiel: öffne WhatsApp und Chrome, CPU, RAM.",
        "uhrzeit":     None,
        "wie spät":    None,
        "datum":       None,
        "welcher tag": None,
        "stopp":       "Angehalten.",
        "abbruch":     "Abgebrochen.",
    }

    def __init__(self, on_command, on_short=None, on_log=None, on_timer=None):
        self.on_command  = on_command
        self.on_short    = on_short
        self.on_log      = on_log
        self.on_timer    = on_timer
        self.running     = False
        self.audio_level = 0.0
        self._stop       = threading.Event()
        self.wake        = WakeWordDetector(CFG.get("wake_word", "aera"))
        self._recognizer = None
        self._microphone = None

    def _log(self, msg: str, lvl: str = "info"):
        if self.on_log:
            self.on_log(msg, lvl)

    def _clean_recognized(self, text: str) -> str:
        text = FILLER.clean(text)
        text = text.strip(".,!?;: ")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _init_sr(self) -> bool:
        if not VOICE_OK:
            self._log("SpeechRecognition fehlt: pip install SpeechRecognition pyaudio", "error")
            return False
        try:
            self._recognizer = sr.Recognizer()
            self._microphone = sr.Microphone()
            self._recognizer.dynamic_energy_threshold = True
            self._recognizer.energy_threshold         = 300
            with self._microphone as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=1)
            self._log("Mikrofon initialisiert ✓", "info")
            return True
        except Exception as e:
            self._log(f"Mikrofon-Fehler: {e}", "error")
            return False

    def start(self):
        if not VOICE_OK:
            self._log("SpeechRecognition nicht installiert.", "error")
            return
        if not self._init_sr():
            return
        self.running = True
        self._stop.clear()
        threading.Thread(target=self._listen_loop, daemon=True).start()
        self._log("Always-On Spracherkennung aktiv.", "info")

    def stop(self):
        self.running = False
        self._stop.set()

    def _listen_loop(self):
        api_errors = 0
        while self.running and not self._stop.is_set():
            try:
                with self._microphone as source:
                    self._log("Lausche...", "listen")
                    audio = self._recognizer.listen(source, timeout=0.5, phrase_time_limit=5)

                try:
                    raw = audio.get_raw_data()
                    n = len(raw) // 2
                    if n > 0:
                        shorts = struct.unpack(f"{n}h", raw[: n * 2])
                        sample = shorts[: min(500, len(shorts))]
                        self.audio_level = math.sqrt(
                            sum(s * s for s in sample) / len(sample))
                except Exception:
                    pass

                try:
                    raw_text = self._recognizer.recognize_google(
                        audio, language="de-DE").lower()
                    text = self._clean_recognized(raw_text)
                    if not text:
                        continue
                    self._log(f"Erkannt: '{text}'", "recognized")
                    api_errors = 0

                    if self.wake.contains_wake_word(text):
                        self._log(f"Wake-Word erkannt: '{text}'", "wake")
                        cleaned = self.wake.strip_wake_word(text)
                        if cleaned and len(cleaned.strip()) >= 3:
                            self._log(f"Inline-Befehl: '{cleaned}'", "command")
                            self._process(cleaned)
                        else:
                            self._log("Nur Wake-Word — warte auf Befehl...", "standby")
                            self._listen_for_command()

                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    api_errors += 1
                    self._log(f"API-Fehler ({api_errors}): {e}", "error")
                    if api_errors > 5:
                        time.sleep(3)
                        api_errors = 0

            except sr.WaitTimeoutError:
                pass
            except Exception as e:
                if not self._stop.is_set():
                    self._log(f"Loop-Fehler: {e}", "error")
                time.sleep(0.2)

    def _listen_for_command(self):
        self._log("Warte auf Befehl... (4 Sekunden)", "listen")
        try:
            with self._microphone as source:
                audio = self._recognizer.listen(source, timeout=4, phrase_time_limit=8)
            raw_text = self._recognizer.recognize_google(audio, language="de-DE")
            text     = self._clean_recognized(raw_text)
            self._log(f"Befehl erkannt: '{text}'", "command")
            if text and len(text.strip()) >= 2:
                self._process(text)
            else:
                self._log("Befehl zu kurz — ignoriert.", "standby")
        except sr.WaitTimeoutError:
            self._log("Timeout — kein Befehl. Zurück zu Standby.", "standby")
        except sr.UnknownValueError:
            self._log("Befehl nicht verstanden.", "error")
        except Exception as e:
            self._log(f"Befehl-Fehler: {e}", "error")

    def _process(self, command: str):
        command = FILLER.clean(command)
        if FILLER.is_noise(command):
            self._log(f"Nur Füllwörter — ignoriert: '{command}'", "standby")
            return
        t = command.lower().strip()

        for pat in [
            r"timer\s+(?:auf\s+)?(\d+)\s*(?:minuten?|min)",
            r"(\d+)\s*(?:minuten?|min)\s+timer",
            r"stell(?:e)?\s+timer\s+(?:auf\s+)?(\d+)",
        ]:
            m = re.search(pat, t)
            if m:
                mins = int(m.group(1))
                self._log(f"Timer: {mins} Min.", "timer")
                if self.on_timer:
                    self.on_timer(mins)
                return

        t_clean = self.wake.strip_wake_word(t)
        for kw, resp in self.SHORT_CMDS.items():
            if kw in t_clean or kw in t:
                if resp is None:
                    now = datetime.now()
                    if "uhrzeit" in kw or "spät" in kw:
                        resp = f"Es ist {now.strftime('%H:%M Uhr')}."
                    elif "datum" in kw or "tag" in kw:
                        tage   = ["Montag","Dienstag","Mittwoch","Donnerstag",
                                  "Freitag","Samstag","Sonntag"]
                        monate = ["Januar","Februar","März","April","Mai","Juni",
                                  "Juli","August","September","Oktober","November","Dezember"]
                        resp = (f"Heute ist {tage[now.weekday()]}, "
                                f"{now.day}. {monate[now.month-1]} {now.year}.")
                self._log(f"Kurzbefehl: '{kw}'", "info")
                if self.on_short:
                    self.on_short(resp, "shortcmd")
                return

        if self.on_command:
            self.on_command(command)

    def listen_once(self, timeout: float = 6.0) -> Optional[str]:
        if not VOICE_OK or not self._recognizer:
            return None
        try:
            with self._microphone as source:
                audio = self._recognizer.listen(source, timeout=timeout,
                                                phrase_time_limit=10)
            raw = self._recognizer.recognize_google(audio, language="de-DE")
            return self._clean_recognized(raw)
        except Exception as e:
            self._log(f"listen_once: {e}", "error")
            return None


# ═══════════════════════════════════════════════════════════════════════════════
#  WEB-RECHERCHE
# ═══════════════════════════════════════════════════════════════════════════════

class WebSearch:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    ]
    SMALLTALK = {
        "greeting": ["Hallo! Ich bin A.E.R.A Version 10 mit Universal App Engine. Was kann ich tun?",
                     "Hey! Bereit für alles. Sage z.B.: öffne Spotify, oder: schließe Chrome."],
        "mood":     ["Mir geht es super — Universal App Engine läuft auf Hochtouren!",
                     "Bestens! Alle Apps in Reichweite."],
        "identity": ["Ich bin A.E.R.A v10 — Multi-Command Edition. Ich öffne JEDE App.",
                     "AERA v10 — Multi-Command v2. Jetzt noch zuverlässiger!"],
        "ability":  ["Ich öffne und schließe jede App, die auf dem PC installiert ist — ohne Mapping.",
                     "Sage 'öffne Spotify' oder 'schließe Chrome' — ich finde alles selbst."],
        "thanks":   ["Gerne!", "Kein Problem. Immer wieder!"],
        "farewell": ["Bis dann!", "Auf Wiedersehen! Im Standby."],
    }

    def _smalltalk(self, text: str) -> Optional[str]:
        t    = text.lower()
        cats = {
            "greeting": ["hallo","hi","hey","moin","guten morgen","guten tag","servus","grüß gott"],
            "mood":     ["wie geht","wie gehts","alles gut"],
            "identity": ["wer bist du","wie heißt du","was bist du"],
            "ability":  ["was kannst du","hilfe","features","was machst du"],
            "thanks":   ["danke","vielen dank","super","toll"],
            "farewell": ["tschüss","ciao","bye","auf wiedersehen"],
        }
        for cat, patterns in cats.items():
            if any(p in t for p in patterns):
                return random.choice(self.SMALLTALK[cat])
        return None

    def _clean_html(self, raw: str) -> str:
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\[\d+\]", "", text)
        for old, new in {"&nbsp;":" ","&amp;":"&","&lt;":"<",
                         "&gt;":">","&quot;":'"',"&#039;":"'"}.items():
            text = text.replace(old, new)
        return re.sub(r"\s+", " ", text).strip()

    def _wiki_direct(self, term: str) -> Optional[str]:
        if not REQUESTS_OK:
            return None
        for variant in [term, term.title(), term.capitalize()]:
            try:
                url = (f"https://de.wikipedia.org/wiki/"
                       f"{urllib.parse.quote(variant.replace(' ', '_'))}")
                r   = requests.get(url, timeout=8,
                                   headers={"User-Agent": random.choice(self.USER_AGENTS)})
                if r.status_code == 200:
                    paras = re.findall(r"<p[^>]*>(.*?)</p>", r.text, re.DOTALL)
                    for p in paras[:4]:
                        clean = self._clean_html(p)
                        if len(clean) > 80 and "weiterleitung" not in clean.lower():
                            sents = re.split(r"(?<=[.!?])\s+", clean)
                            return " ".join(sents[:2])
            except Exception:
                pass
        return None

    def _ddg(self, query: str) -> Optional[str]:
        if not REQUESTS_OK:
            return None
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}&kl=de-de"
            r   = requests.get(url, timeout=10,
                               headers={"User-Agent": random.choice(self.USER_AGENTS)})
            if r.status_code == 200:
                snippets = re.findall(
                    r'class="result__snippet"[^>]*>(.*?)</a>', r.text, re.DOTALL)
                for s in snippets[:3]:
                    clean = self._clean_html(s)
                    if len(clean) > 80:
                        return clean
        except Exception:
            pass
        return None

    def answer(self, question: str) -> str:
        st = self._smalltalk(question)
        if st:
            return f"{st}"
        term = re.sub(
            r"^(was ist|wer ist|wer war|wie|erkläre|was sind|was bedeutet)\s+",
            "", question.lower()).strip()
        term = re.sub(r"^(ein|eine|der|die|das)\s+", "", term).strip()
        result = self._wiki_direct(term)
        if not result:
            result = self._ddg(question)
        if result:
            return f"{result}"
        return "Dazu konnte ich leider nichts finden. Versuche eine präzisere Frage."


WEB = WebSearch()


# ═══════════════════════════════════════════════════════════════════════════════
#  COMMAND HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

class CommandHistory:
    def __init__(self, max_size: int = 50):
        self.items: List[Dict] = []
        self.max   = max_size

    def add(self, text: str, result: str, cmd_type: str = "command"):
        self.items.insert(0, {
            "time":   datetime.now().strftime("%H:%M:%S"),
            "text":   text[:60],
            "result": result[:80],
            "type":   cmd_type,
        })
        if len(self.items) > self.max:
            self.items = self.items[:self.max]

    def get_recent(self, n: int = 10) -> List[Dict]:
        return self.items[:n]


HISTORY = CommandHistory()


# ═══════════════════════════════════════════════════════════════════════════════
#  ZUSTANDSMASCHINE
# ═══════════════════════════════════════════════════════════════════════════════

class DialogState:
    IDLE = "idle"

    def __init__(self):
        self.state   = self.IDLE
        self.context = {}

    def clear(self):
        self.state   = self.IDLE
        self.context = {}

    def is_idle(self) -> bool:
        return self.state == self.IDLE


DIALOG = DialogState()


# ═══════════════════════════════════════════════════════════════════════════════
#  FARBPALETTE
# ═══════════════════════════════════════════════════════════════════════════════

COLORS = {
    "bg":           "#0D1117",
    "bg_panel":     "#161B22",
    "bg_card":      "#1C2128",
    "bg_input":     "#0D1117",
    "accent":       "#1E6FD9",
    "accent_light": "#58A6FF",
    "accent_dark":  "#0D4A9E",
    "green":        "#3FB950",
    "amber":        "#F0A32F",
    "red":          "#F85149",
    "text_bright":  "#E6EDF3",
    "text_mid":     "#8B949E",
    "text_dim":     "#484F58",
    "border":       "#30363D",
    "glow":         "#1E4080",
    "purple":       "#A371F7",
}


# ═══════════════════════════════════════════════════════════════════════════════
#  SOKRATISCHE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def socratic_engine(text: str) -> Optional[str]:
    t = text.lower().strip()
    if len(t) < 5:
        return None
    ACTION_KEYS = {
        "öffne", "starte", "suche", "zeig", "mach", "stell", "drucke",
        "lösche", "berechne", "timer", "erinnerung", "screenshot", "akku",
        "batterie", "wetter", "kurs", "preis", "bitcoin", "aktie", "ip",
        "ip-adresse", "wie spät", "uhrzeit", "datum", "sap", "excel",
        "word", "outlook", "teams", "browser", "terminal", "rechne",
        "finde", "such", "öffnen", "starten", "herunterfahren", "neustart",
        "festplatte", "dns", "bluetooth", "lautstärke", "helligkeit",
        "zip", "ordner", "datei", "download", "papierkorb", "backup",
        "youtube", "amazon", "maps", "navigation", "nachrichten", "news",
        "übersetze", "installiere", "install", "passwort", "qr", "ping",
        "witz", "würfeln", "münze", "notiz", "uptime", "wlan", "clipboard",
        "cpu", "ram", "schließe", "beende", "kille", "apps", "uuid",
        "base64", "hex", "rgb", "hostname", "benutzername", "ports",
    }
    if any(kw in t for kw in ACTION_KEYS):
        return None
    QUESTION_TRIGGERS = {
        "warum", "wie funktioniert", "was bedeutet", "was ist",
        "erkläre", "wieso", "woran liegt", "weshalb", "inwiefern",
        "welchen unterschied", "was sind die",
    }
    if any(x in t for x in QUESTION_TRIGGERS):
        responses = [
            "Eine interessante Frage. Was denkst du selbst darüber?",
            "Bevor ich antworte: Was wäre dein erster Ansatz?",
            "Gute Frage. Welche Informationen fehlen dir noch?",
            "Lass uns das zusammen durchdenken. Was ist deine Hypothese?",
        ]
        return random.choice(responses)
    return None



# ═══════════════════════════════════════════════════════════════════════════════
#  AERA v10 — HIGH-END KALENDER WIDGET mit VOICE-TERMIN-MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class AERACalendar:
    """
    Premium Kalender-Widget für AERA v10
    • Monats-/Wochen-/Tagesansicht
    • Termine per GUI + Voice eintragen
    • Termine vorlesen lassen
    • Erinnerungen 30 Min vorher
    • JSON-Speicherung
    """

    MONTHS_DE = [
        "Januar", "Februar", "März", "April", "Mai", "Juni",
        "Juli", "August", "September", "Oktober", "November", "Dezember"
    ]
    DAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    DAYS_DE_FULL = [
        "Montag", "Dienstag", "Mittwoch", "Donnerstag",
        "Freitag", "Samstag", "Sonntag"
    ]

    def __init__(self, parent_root, tts_manager=None, on_close=None):
        self.parent = parent_root
        self.tts = tts_manager
        self.on_close = on_close
        self.today = datetime.now()
        self.current_year = self.today.year
        self.current_month = self.today.month
        self.selected_date: Optional[datetime] = None
        self.view_mode = "month"
        self.events: Dict[str, List[Dict]] = self._load_events()
        self._reminder_thread = None
        self._stop_reminders = threading.Event()
        self._build_window()
        self._start_reminder_thread()

    def _events_file(self) -> Path:
        return HOME / ".aera_calendar_events.json"

    def _load_events(self) -> Dict[str, List[Dict]]:
        try:
            if self._events_file().exists():
                with open(self._events_file(), "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_events(self):
        try:
            with open(self._events_file(), "w", encoding="utf-8") as f:
                json.dump(self.events, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Kalender] Speicherfehler: {e}")

    def _date_key(self, dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d")

    def get_events(self, dt: datetime) -> List[Dict]:
        return self.events.get(self._date_key(dt), [])

    def add_event(self, dt: datetime, title: str, category: str = "default",
                  time_str: str = "", reminder: bool = False) -> str:
        key = self._date_key(dt)
        if key not in self.events:
            self.events[key] = []
        event = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "time": time_str,
            "category": category,
            "reminder": reminder,
            "reminded": False,
            "created": datetime.now().isoformat(),
        }
        self.events[key].append(event)
        self.events[key].sort(key=lambda x: x.get("time", "00:00"))
        self._save_events()
        return f"Termin '{title}' am {dt.strftime('%d.%m.%Y')} um {time_str} gespeichert."

    def delete_event(self, dt: datetime, event_id: str) -> str:
        key = self._date_key(dt)
        if key in self.events:
            self.events[key] = [e for e in self.events[key] if e["id"] != event_id]
            if not self.events[key]:
                del self.events[key]
            self._save_events()
            return "Termin gelöscht."
        return "Termin nicht gefunden."

    def read_events_for_date(self, dt: datetime) -> str:
        events = self.get_events(dt)
        if not events:
            return f"Keine Termine am {dt.strftime('%d.%m.%Y')}."
        day_name = self.DAYS_DE_FULL[dt.weekday()]
        lines = [f"Termine für {day_name}, den {dt.strftime('%d.%m.%Y')}:"]
        for ev in events:
            time_str = ev.get("time", "")
            title = ev.get("title", "Unbenannt")
            if time_str:
                lines.append(f"  {time_str} Uhr — {title}")
            else:
                lines.append(f"  {title}")
        return "\n".join(lines)

    def _start_reminder_thread(self):
        self._reminder_thread = threading.Thread(target=self._reminder_loop, daemon=True)
        self._reminder_thread.start()

    def _reminder_loop(self):
        while not self._stop_reminders.is_set():
            try:
                now = datetime.now()
                for date_key, events in list(self.events.items()):
                    for ev in events:
                        if not ev.get("reminder", False) or ev.get("reminded", False):
                            continue
                        time_str = ev.get("time", "")
                        if not time_str:
                            continue
                        try:
                            ev_dt = datetime.strptime(f"{date_key} {time_str}", "%Y-%m-%d %H:%M")
                            diff = (ev_dt - now).total_seconds()
                            if 1740 <= diff <= 1800:
                                if self.tts:
                                    self.tts.speak(
                                        f"Erinnerung: In 30 Minuten — {ev.get('title', 'Termin')}. "
                                        f"Um {time_str} Uhr."
                                    )
                                ev["reminded"] = True
                                self._save_events()
                        except Exception:
                            pass
            except Exception:
                pass
            time.sleep(60)

    def stop_reminders(self):
        self._stop_reminders.set()

    def _build_window(self):
        self.win = tk.Toplevel(self.parent)
        self.win.title(f"AERA Kalender — {self.today.strftime('%B %Y')}")
        self.win.geometry("1100x780")
        self.win.configure(bg=COLORS["bg"])
        self.win.minsize(900, 600)
        self.win.transient(self.parent)

        main = tk.Frame(self.win, bg=COLORS["bg"])
        main.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        self._build_header(main)
        self._build_calendar_area(main)
        self._build_sidebar(main)
        self._build_footer(main)

        self._render_month()
        self.win.protocol("WM_DELETE_WINDOW", self._close)

    def _build_header(self, parent):
        hdr = tk.Frame(parent, bg=COLORS["bg_panel"], height=64)
        hdr.pack(fill=tk.X, pady=(0, 12))
        hdr.pack_propagate(False)

        nav = tk.Frame(hdr, bg=COLORS["bg_panel"])
        nav.pack(side=tk.LEFT, padx=16)

        self._make_nav_btn(nav, "◄", self._prev_period)
        self.month_lbl = tk.Label(
            nav, text="", font=("Consolas", 18, "bold"),
            bg=COLORS["bg_panel"], fg=COLORS["accent_light"]
        )
        self.month_lbl.pack(side=tk.LEFT, padx=16)
        self._make_nav_btn(nav, "►", self._next_period)
        self._make_nav_btn(nav, "HEUTE", self._goto_today, COLORS["green"])

        view = tk.Frame(hdr, bg=COLORS["bg_panel"])
        view.pack(side=tk.LEFT, padx=20)

        self.view_btns = {}
        for mode, label in [("month", "MONAT"), ("week", "WOCHE"), ("day", "TAG")]:
            btn = tk.Button(
                view, text=label, font=("Consolas", 9, "bold"),
                bg=COLORS["bg_card"], fg=COLORS["text_dim"],
                activebackground=COLORS["glow"],
                activeforeground=COLORS["text_bright"],
                relief=tk.FLAT, bd=0, padx=14, pady=6, cursor="hand2",
                command=lambda m=mode: self._set_view(m)
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.view_btns[mode] = btn

        search_frame = tk.Frame(hdr, bg=COLORS["bg_panel"])
        search_frame.pack(side=tk.RIGHT, padx=16)

        self.search_var = tk.StringVar()
        search_entry = tk.Entry(
            search_frame, textvariable=self.search_var,
            font=("Consolas", 10), bg=COLORS["bg"], fg=COLORS["text_bright"],
            insertbackground=COLORS["accent"], relief=tk.FLAT,
            highlightthickness=1, highlightcolor=COLORS["accent"],
            highlightbackground=COLORS["border"], width=24
        )
        search_entry.pack(side=tk.LEFT, padx=4)
        search_entry.bind("<Return>", lambda e: self._search_events())

        tk.Button(
            search_frame, text="🔍", font=("Consolas", 10),
            bg=COLORS["bg_card"], fg=COLORS["accent_light"],
            relief=tk.FLAT, bd=0, padx=8, pady=4, cursor="hand2",
            command=self._search_events
        ).pack(side=tk.LEFT)

        self.year_lbl = tk.Label(
            hdr, text=str(self.current_year),
            font=("Consolas", 14, "bold"),
            bg=COLORS["bg_panel"], fg=COLORS["amber"]
        )
        self.year_lbl.pack(side=tk.RIGHT, padx=8)

    def _make_nav_btn(self, parent, text, cmd, fg=None):
        return tk.Button(
            parent, text=text, font=("Consolas", 10, "bold"),
            bg=COLORS["bg_card"], fg=fg or COLORS["text_bright"],
            activebackground=COLORS["glow"],
            activeforeground=COLORS["text_bright"],
            relief=tk.FLAT, bd=0, padx=10, pady=6, cursor="hand2",
            command=cmd
        ).pack(side=tk.LEFT, padx=2)

    def _build_calendar_area(self, parent):
        self.cal_frame = tk.Frame(parent, bg=COLORS["bg_card"], bd=1,
                                   highlightbackground=COLORS["border"],
                                   highlightthickness=1)
        self.cal_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.days_header = tk.Frame(self.cal_frame, bg=COLORS["bg_card"], height=36)
        self.days_header.pack(fill=tk.X)
        self.days_header.pack_propagate(False)

        for day in self.DAYS_DE:
            lbl = tk.Label(
                self.days_header, text=day,
                font=("Consolas", 10, "bold"),
                bg=COLORS["bg_card"], fg=COLORS["text_dim"]
            )
            lbl.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        self.grid_container = tk.Frame(self.cal_frame, bg=COLORS["bg"])
        self.grid_container.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self.day_cells: Dict[Tuple[int, int], Dict] = {}

    def _build_sidebar(self, parent):
        self.sidebar = tk.Frame(parent, bg=COLORS["bg_panel"], width=320)
        self.sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        self.sidebar.pack_propagate(False)

        self.sidebar_date = tk.Label(
            self.sidebar, text="Termine",
            font=("Consolas", 12, "bold"),
            bg=COLORS["bg_panel"], fg=COLORS["accent_light"]
        )
        self.sidebar_date.pack(pady=(16, 8), padx=12, anchor="w")

        self.events_list = tk.scrolledtext.ScrolledText(
            self.sidebar, wrap=tk.WORD, font=("Consolas", 10),
            bg=COLORS["bg"], fg=COLORS["text_bright"],
            relief=tk.FLAT, padx=10, pady=8, height=14,
            selectbackground=COLORS["glow"]
        )
        self.events_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.events_list.config(state=tk.DISABLED)

        self.events_list.tag_config("time", foreground=COLORS["accent_light"],
                                     font=("Consolas", 9, "bold"))
        self.events_list.tag_config("title", foreground=COLORS["text_bright"],
                                     font=("Consolas", 10))
        self.events_list.tag_config("category", foreground=COLORS["purple"],
                                     font=("Consolas", 8))
        self.events_list.tag_config("empty", foreground=COLORS["text_dim"],
                                     font=("Consolas", 10, "italic"))

        tk.Frame(self.sidebar, bg=COLORS["border"], height=1).pack(
            fill=tk.X, padx=8, pady=8)

        tk.Label(self.sidebar, text="NEUER TERMIN",
                 font=("Consolas", 9, "bold"),
                 bg=COLORS["bg_panel"], fg=COLORS["green"]).pack(
                     padx=12, anchor="w")

        self.new_title = tk.Entry(
            self.sidebar, font=("Consolas", 10),
            bg=COLORS["bg"], fg=COLORS["text_bright"],
            insertbackground=COLORS["accent"], relief=tk.FLAT,
            highlightthickness=1, highlightcolor=COLORS["accent"],
            highlightbackground=COLORS["border"]
        )
        self.new_title.pack(fill=tk.X, padx=8, pady=4)
        self.new_title.insert(0, "Titel...")
        self.new_title.bind("<FocusIn>",
            lambda e: self.new_title.delete(0, tk.END) if self.new_title.get() == "Titel..." else None)

        time_frame = tk.Frame(self.sidebar, bg=COLORS["bg_panel"])
        time_frame.pack(fill=tk.X, padx=8, pady=2)

        self.new_time = tk.Entry(
            time_frame, font=("Consolas", 10), width=8,
            bg=COLORS["bg"], fg=COLORS["text_bright"],
            insertbackground=COLORS["accent"], relief=tk.FLAT,
            highlightthickness=1, highlightcolor=COLORS["accent"],
            highlightbackground=COLORS["border"]
        )
        self.new_time.pack(side=tk.LEFT)
        self.new_time.insert(0, "14:00")

        self.cat_var = tk.StringVar(value="default")
        cats = [(" Arbeit", "work", COLORS["accent_light"]),
                (" Privat", "private", COLORS["green"]),
                (" Wichtig", "important", COLORS["red"]),
                (" Meeting", "meeting", COLORS["purple"])]

        for label, val, color in cats:
            tk.Radiobutton(
                time_frame, text=label, variable=self.cat_var, value=val,
                font=("Consolas", 8), bg=COLORS["bg_panel"], fg=color,
                selectcolor=COLORS["bg"], activebackground=COLORS["bg_panel"]
            ).pack(side=tk.LEFT, padx=2)

        self.reminder_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.sidebar, text=" Erinnerung (30 Min vorher)",
            variable=self.reminder_var,
            font=("Consolas", 9), bg=COLORS["bg_panel"], fg=COLORS["amber"],
            selectcolor=COLORS["bg"], activebackground=COLORS["bg_panel"]
        ).pack(anchor="w", padx=8, pady=4)

        tk.Button(
            self.sidebar, text="+ TERMIN SPEICHERN",
            font=("Consolas", 10, "bold"),
            bg=COLORS["green"], fg=COLORS["bg"],
            activebackground="#2D8A3E", activeforeground=COLORS["bg"],
            relief=tk.FLAT, bd=0, padx=12, pady=8, cursor="hand2",
            command=self._add_new_event
        ).pack(fill=tk.X, padx=8, pady=8)

        tk.Button(
            self.sidebar, text="🔊 TERMIN VORLESEN",
            font=("Consolas", 10, "bold"),
            bg=COLORS["accent"], fg=COLORS["bg"],
            activebackground=COLORS["accent_light"], activeforeground=COLORS["bg"],
            relief=tk.FLAT, bd=0, padx=12, pady=8, cursor="hand2",
            command=self._read_selected_date
        ).pack(fill=tk.X, padx=8, pady=4)

    def _build_footer(self, parent):
        footer = tk.Frame(parent, bg=COLORS["bg_panel"], height=32)
        footer.pack(fill=tk.X, pady=(12, 0))
        footer.pack_propagate(False)

        self.footer_lbl = tk.Label(
            footer,
            text=f"{self.today.strftime('%d.%m.%Y')} │ {self.DAYS_DE_FULL[self.today.weekday()]}",
            font=("Consolas", 9),
            bg=COLORS["bg_panel"], fg=COLORS["text_dim"]
        )
        self.footer_lbl.pack(side=tk.LEFT, padx=16)

        tk.Label(footer,
                 text="AERA Kalender v1.0 │ JSON │ Voice-Termine │ 30-Min-Erinnerungen",
                 font=("Consolas", 8),
                 bg=COLORS["bg_panel"], fg=COLORS["text_dim"]).pack(side=tk.RIGHT, padx=16)

    def _render_month(self):
        self._clear_grid()
        self._highlight_view_btn("month")
        self.month_lbl.config(text=f"{self.MONTHS_DE[self.current_month - 1]}")
        self.year_lbl.config(text=str(self.current_year))

        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdayscalendar(self.current_year, self.current_month)

        for week_idx, week in enumerate(month_days):
            for day_idx, day in enumerate(week):
                self._create_day_cell(week_idx, day_idx, day)

    def _render_week(self):
        self._clear_grid()
        self._highlight_view_btn("week")
        dt = datetime(self.current_year, self.current_month, 1)
        while dt.weekday() != 0:
            dt -= timedelta(days=1)
        self.month_lbl.config(text=f"Woche {dt.isocalendar()[1]}")

        for day_idx in range(7):
            current = dt + timedelta(days=day_idx)
            self._create_day_cell(0, day_idx, current.day,
                                     full_date=current, week_mode=True)

    def _render_day(self):
        self._clear_grid()
        self._highlight_view_btn("day")
        dt = datetime(self.current_year, self.current_month,
                       self.selected_date.day if self.selected_date else 1)
        self.month_lbl.config(text=dt.strftime("%d.%m.%Y"))
        self._create_day_cell(0, 0, dt.day, full_date=dt, day_mode=True)

    def _create_day_cell(self, row: int, col: int, day: int,
                          full_date: Optional[datetime] = None,
                          week_mode: bool = False, day_mode: bool = False):
        if day == 0:
            cell = tk.Frame(self.grid_container, bg=COLORS["bg"])
            cell.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)
            return

        dt = full_date or datetime(self.current_year, self.current_month, day)
        is_today = (dt.date() == self.today.date())
        is_selected = (self.selected_date and dt.date() == self.selected_date.date())

        if is_selected:
            bg = COLORS["accent_dark"]
            border = COLORS["accent_light"]
        elif is_today:
            bg = "#1A2F1A"
            border = COLORS["green"]
        elif dt.weekday() >= 5:
            bg = "#141820"
            border = COLORS["border"]
        else:
            bg = COLORS["bg_card"]
            border = COLORS["border"]

        cell = tk.Frame(self.grid_container, bg=bg, bd=1,
                        highlightbackground=border, highlightthickness=1)
        cell.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)

        if day_mode:
            cell.grid_configure(columnspan=7, rowspan=6)

        self.grid_container.grid_columnconfigure(col, weight=1)
        self.grid_container.grid_rowconfigure(row, weight=1)

        day_font = ("Consolas", 14 if day_mode else 11,
                    "bold" if (is_today or is_selected) else "normal")
        day_fg = COLORS["green"] if is_today else (
            COLORS["accent_light"] if is_selected else COLORS["text_bright"]
        )

        day_lbl = tk.Label(cell, text=str(day), font=day_font,
                           bg=bg, fg=day_fg)
        day_lbl.pack(anchor="nw", padx=8, pady=6)

        events = self.get_events(dt)
        if events and not day_mode:
            dot_frame = tk.Frame(cell, bg=bg)
            dot_frame.pack(anchor="nw", padx=8, pady=(0, 4))
            for ev in events[:3]:
                cat_colors = {
                    "work": COLORS["accent_light"],
                    "private": COLORS["green"],
                    "important": COLORS["red"],
                    "meeting": COLORS["purple"],
                }
                dot_col = cat_colors.get(ev.get("category", "default"), COLORS["amber"])
                tk.Label(dot_frame, text="●", font=("Consolas", 8),
                         bg=bg, fg=dot_col).pack(side=tk.LEFT, padx=1)
            if len(events) > 3:
                tk.Label(dot_frame, text=f"+{len(events)-3}",
                         font=("Consolas", 7), bg=bg, fg=COLORS["text_dim"]
                         ).pack(side=tk.LEFT, padx=1)

        elif events and day_mode:
            for ev in events:
                self._render_event_in_cell(cell, ev, bg)

        cell.bind("<Button-1>", lambda e, d=dt: self._select_date(d))
        for child in cell.winfo_children():
            child.bind("<Button-1>", lambda e, d=dt: self._select_date(d))

        self.day_cells[(row, col)] = {
            "frame": cell, "date": dt, "day": day
        }

    def _render_event_in_cell(self, parent, event: Dict, bg: str):
        ev_frame = tk.Frame(parent, bg=bg)
        ev_frame.pack(fill=tk.X, padx=12, pady=2)

        time_str = event.get("time", "")
        if time_str:
            tk.Label(ev_frame, text=time_str, font=("Consolas", 10, "bold"),
                     bg=bg, fg=COLORS["accent_light"]).pack(anchor="w")

        tk.Label(ev_frame, text=event.get("title", "Unbenannt"),
                 font=("Consolas", 11), bg=bg, fg=COLORS["text_bright"]
                 ).pack(anchor="w")

    def _clear_grid(self):
        for widget in self.grid_container.winfo_children():
            widget.destroy()
        self.day_cells.clear()

    def _highlight_view_btn(self, mode: str):
        for m, btn in self.view_btns.items():
            if m == mode:
                btn.config(bg=COLORS["accent"], fg=COLORS["bg"])
            else:
                btn.config(bg=COLORS["bg_card"], fg=COLORS["text_dim"])

    def _select_date(self, dt: datetime):
        self.selected_date = dt
        self._update_sidebar(dt)
        if self.view_mode == "month":
            self._render_month()
        elif self.view_mode == "week":
            self._render_week()

    def _update_sidebar(self, dt: datetime):
        self.sidebar_date.config(
            text=f"{dt.strftime('%d.%m.%Y')} │ {self.DAYS_DE_FULL[dt.weekday()]}"
        )
        self.events_list.config(state=tk.NORMAL)
        self.events_list.delete("1.0", tk.END)

        events = self.get_events(dt)
        if not events:
            self.events_list.insert(tk.END, "Keine Termine an diesem Tag.\n", "empty")
        else:
            for ev in events:
                time_str = ev.get("time", "")
                if time_str:
                    self.events_list.insert(tk.END, f"{time_str}  ", "time")
                self.events_list.insert(tk.END, f"{ev.get('title', 'Unbenannt')}\n", "title")
                cat = ev.get("category", "default")
                self.events_list.insert(tk.END, f"  [{cat}]\n\n", "category")

        self.events_list.config(state=tk.DISABLED)

    def _add_new_event(self):
        if not self.selected_date:
            self.selected_date = self.today
        title = self.new_title.get().strip()
        if not title or title == "Titel...":
            return
        time_str = self.new_time.get().strip()
        category = self.cat_var.get()
        reminder = self.reminder_var.get()
        result = self.add_event(self.selected_date, title, category, time_str, reminder)
        self._update_sidebar(self.selected_date)
        if self.view_mode == "month":
            self._render_month()
        self.new_title.delete(0, tk.END)
        self.new_title.insert(0, "Titel...")
        if self.tts:
            self.tts.speak(result)

    def _read_selected_date(self):
        if not self.selected_date:
            self.selected_date = self.today
        text = self.read_events_for_date(self.selected_date)
        if self.tts:
            self.tts.speak(text)

    def _search_events(self):
        query = self.search_var.get().strip().lower()
        if not query:
            return
        results = []
        for date_key, events in self.events.items():
            for ev in events:
                if query in ev.get("title", "").lower():
                    results.append((date_key, ev))

        self.events_list.config(state=tk.NORMAL)
        self.events_list.delete("1.0", tk.END)
        if not results:
            self.events_list.insert(tk.END, f"Keine Termine für '{query}' gefunden.\n", "empty")
        else:
            self.events_list.insert(tk.END, f"{len(results)} Treffer für '{query}':\n\n", "time")
            for date_key, ev in results[:20]:
                self.events_list.insert(tk.END, f"{date_key}  ", "time")
                self.events_list.insert(tk.END, f"{ev.get('title')}\n", "title")
                self.events_list.insert(tk.END, f"  [{ev.get('category', 'default')}]\n\n", "category")
        self.events_list.config(state=tk.DISABLED)

    def _prev_period(self):
        if self.view_mode == "month":
            self.current_month -= 1
            if self.current_month < 1:
                self.current_month = 12
                self.current_year -= 1
            self._render_month()

    def _next_period(self):
        if self.view_mode == "month":
            self.current_month += 1
            if self.current_month > 12:
                self.current_month = 1
                self.current_year += 1
            self._render_month()

    def _goto_today(self):
        self.current_year = self.today.year
        self.current_month = self.today.month
        self.selected_date = self.today
        if self.view_mode == "month":
            self._render_month()
        self._update_sidebar(self.today)

    def _set_view(self, mode: str):
        self.view_mode = mode
        if mode == "month":
            self._render_month()
        elif mode == "week":
            self._render_week()
        elif mode == "day":
            self._render_day()

    def _close(self):
        self.stop_reminders()
        if self.on_close:
            self.on_close()
        self.win.destroy()


class VoiceCalendarManager:
    """Verwaltet Voice-Befehle für den Kalender."""

    def __init__(self, calendar_ref_getter, tts_manager):
        self.get_calendar = calendar_ref_getter
        self.tts = tts_manager

    def parse_date(self, text: str) -> Optional[datetime]:
        text = text.lower()
        today = datetime.now()

        if any(w in text for w in ["heute"]):
            return today
        if any(w in text for w in ["morgen"]):
            return today + timedelta(days=1)
        if any(w in text for w in ["übermorgen"]):
            return today + timedelta(days=2)

        m = re.search(r'(\d{1,2})\.(\d{1,2})\.(?:(\d{4}))?', text)
        if m:
            day, month = int(m.group(1)), int(m.group(2))
            year = int(m.group(3)) if m.group(3) else today.year
            try:
                return datetime(year, month, day)
            except ValueError:
                pass

        days_map = {
            "montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3,
            "freitag": 4, "samstag": 5, "sonntag": 6,
        }
        for day_name, day_num in days_map.items():
            if day_name in text:
                diff = (day_num - today.weekday()) % 7
                if diff == 0:
                    diff = 7
                return today + timedelta(days=diff)
        return None

    def parse_time(self, text: str) -> str:
        m = re.search(r'(\d{1,2}):(\d{2})', text)
        if m:
            return f"{int(m.group(1)):02d}:{m.group(2)}"
        m = re.search(r'(\d{1,2})\s*uhr', text)
        if m:
            return f"{int(m.group(1)):02d}:00"
        return ""

    def extract_title(self, text: str) -> str:
        stop_words = [
            "termin", "ein", "eine", "am", "um", "uhr", "morgen", "heute",
            "übermorgen", "montag", "dienstag", "mittwoch", "donnerstag",
            "freitag", "samstag", "sonntag", "mit", "erinnerung",
            "aera", "setze", "stelle", "neuer", "neuen", "füge", "hinzu",
            "erstelle", "mache", "plan", "plane", "vereinbare",
        ]
        words = text.lower().split()
        filtered = []
        for w in words:
            clean = re.sub(r'[^\w]', '', w)
            if clean not in stop_words and len(clean) > 1:
                filtered.append(w)
        return " ".join(filtered).strip() or "Termin"

    def add_event_voice(self, text: str) -> str:
        dt = self.parse_date(text)
        if not dt:
            dt = datetime.now()
        time_str = self.parse_time(text)
        title = self.extract_title(text)
        reminder = any(w in text.lower() for w in ["erinnerung", "erinnere", "remind", "benachrichtige"])

        cal = self.get_calendar()
        if cal:
            result = cal.add_event(dt, title, "default", time_str, reminder)
            if self.tts:
                self.tts.speak(result)
            return result
        return "Kalender nicht verfügbar."

    def read_events_voice(self, text: str) -> str:
        dt = self.parse_date(text)
        if not dt:
            dt = datetime.now()

        cal = self.get_calendar()
        if cal:
            result = cal.read_events_for_date(dt)
            if self.tts:
                self.tts.speak(result)
            return result
        return "Kalender nicht verfügbar."


# ═══════════════════════════════════════════════════════════════════════════════
#  HAUPTFENSTER GUI v10
# ═══════════════════════════════════════════════════════════════════════════════




# ═══════════════════════════════════════════════════════════════════════════════
#  COMPACT POPUP GUI v10 — Kompakte schwebende GUI
# ═══════════════════════════════════════════════════════════════════════════════



# ═══════════════════════════════════════════════════════════════════════════════
#  THEME MANAGER v10 — GUI Customization Engine
# ═══════════════════════════════════════════════════════════════════════════════

class ThemeManager:
    """
    v10: Verwaltet alle GUI-Themes für AERA.

    Features:
    • 5 Preset-Themes (Dark, Light, Cyberpunk, Ocean, Sunset)
    • Benutzerdefinierte Themes mit Live-Preview
    • JSON Export/Import
    • Farb-Picker für alle UI-Elemente
    • Font-Auswahl für alle Text-Größen
    • Fenster-Größe anpassbar
    """

    THEME_FILE = HOME / ".aera_themes.json"

    PRESETS = {
        "AERA Dark": {
            "bg": "#0D1117", "bg_panel": "#161B22", "bg_card": "#1C2128",
            "bg_input": "#0D1117", "accent": "#1E6FD9", "accent_light": "#58A6FF",
            "accent_dark": "#0D4A9E", "green": "#3FB950", "amber": "#F0A32F",
            "red": "#F85149", "text_bright": "#E6EDF3", "text_mid": "#8B949E",
            "text_dim": "#484F58", "border": "#30363D", "glow": "#1E4080",
            "purple": "#A371F7",
            "font_family": "Consolas", "font_size_base": 11,
            "font_size_header": 20, "font_size_title": 12,
            "font_size_small": 9, "font_size_tiny": 8,
            "ring_color_standby": "#484F58", "ring_color_listening": "#3FB950",
            "ring_color_working": "#1E6FD9", "ring_color_ready": "#A371F7",
            "compact_bg": "#0D1117", "compact_card": "#161B22",
            "compact_accent": "#1E6FD9", "compact_border": "#30363D",
        },
        "AERA Light": {
            "bg": "#F0F0F0", "bg_panel": "#FFFFFF", "bg_card": "#F8F8F8",
            "bg_input": "#FFFFFF", "accent": "#0066CC", "accent_light": "#3399FF",
            "accent_dark": "#004C99", "green": "#2D8A3E", "amber": "#CC8800",
            "red": "#CC3333", "text_bright": "#1A1A1A", "text_mid": "#555555",
            "text_dim": "#888888", "border": "#CCCCCC", "glow": "#99CCFF",
            "purple": "#7B4FB8",
            "font_family": "Segoe UI", "font_size_base": 11,
            "font_size_header": 20, "font_size_title": 12,
            "font_size_small": 9, "font_size_tiny": 8,
            "ring_color_standby": "#888888", "ring_color_listening": "#2D8A3E",
            "ring_color_working": "#0066CC", "ring_color_ready": "#7B4FB8",
            "compact_bg": "#F0F0F0", "compact_card": "#FFFFFF",
            "compact_accent": "#0066CC", "compact_border": "#CCCCCC",
        },
        "Cyberpunk": {
            "bg": "#0A0A1A", "bg_panel": "#12122A", "bg_card": "#1A1A3A",
            "bg_input": "#0A0A1A", "accent": "#FF00FF", "accent_light": "#FF66FF",
            "accent_dark": "#CC00CC", "green": "#00FF88", "amber": "#FFCC00",
            "red": "#FF3366", "text_bright": "#E0E0FF", "text_mid": "#9090CC",
            "text_dim": "#505080", "border": "#303060", "glow": "#FF00FF",
            "purple": "#AA00FF",
            "font_family": "Courier New", "font_size_base": 11,
            "font_size_header": 20, "font_size_title": 12,
            "font_size_small": 9, "font_size_tiny": 8,
            "ring_color_standby": "#505080", "ring_color_listening": "#00FF88",
            "ring_color_working": "#FF00FF", "ring_color_ready": "#AA00FF",
            "compact_bg": "#0A0A1A", "compact_card": "#12122A",
            "compact_accent": "#FF00FF", "compact_border": "#303060",
        },
        "Ocean": {
            "bg": "#0A1929", "bg_panel": "#0D2137", "bg_card": "#112D4E",
            "bg_input": "#0A1929", "accent": "#00B4D8", "accent_light": "#48CAE4",
            "accent_dark": "#0077B6", "green": "#2ECC71", "amber": "#F39C12",
            "red": "#E74C3C", "text_bright": "#E8F4F8", "text_mid": "#90C8D8",
            "text_dim": "#4A7A8A", "border": "#1A4A6A", "glow": "#00B4D8",
            "purple": "#9B59B6",
            "font_family": "Consolas", "font_size_base": 11,
            "font_size_header": 20, "font_size_title": 12,
            "font_size_small": 9, "font_size_tiny": 8,
            "ring_color_standby": "#4A7A8A", "ring_color_listening": "#2ECC71",
            "ring_color_working": "#00B4D8", "ring_color_ready": "#9B59B6",
            "compact_bg": "#0A1929", "compact_card": "#0D2137",
            "compact_accent": "#00B4D8", "compact_border": "#1A4A6A",
        },
        "Sunset": {
            "bg": "#1A0A0A", "bg_panel": "#2A1212", "bg_card": "#3A1A1A",
            "bg_input": "#1A0A0A", "accent": "#FF6B35", "accent_light": "#FF8C5A",
            "accent_dark": "#CC5522", "green": "#4CAF50", "amber": "#FFB347",
            "red": "#FF4444", "text_bright": "#FFF0E8", "text_mid": "#D4A080",
            "text_dim": "#8A6050", "border": "#4A3020", "glow": "#FF6B35",
            "purple": "#C75B9B",
            "font_family": "Consolas", "font_size_base": 11,
            "font_size_header": 20, "font_size_title": 12,
            "font_size_small": 9, "font_size_tiny": 8,
            "ring_color_standby": "#8A6050", "ring_color_listening": "#4CAF50",
            "ring_color_working": "#FF6B35", "ring_color_ready": "#C75B9B",
            "compact_bg": "#1A0A0A", "compact_card": "#2A1212",
            "compact_accent": "#FF6B35", "compact_border": "#4A3020",
        },
    }

    def __init__(self):
        self.custom_themes = {}
        self.current_theme = "AERA Dark"
        self._load_custom_themes()
        self._apply_theme(self.current_theme)

    def _load_custom_themes(self):
        """Lädt benutzerdefinierte Themes aus JSON."""
        try:
            if self.THEME_FILE.exists():
                with open(self.THEME_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.custom_themes = data.get("custom", {})
                    self.current_theme = data.get("current", "AERA Dark")
        except Exception as e:
            print(f"[ThemeManager] Lade-Fehler: {e}")

    def _save_custom_themes(self):
        """Speichert benutzerdefinierte Themes als JSON."""
        try:
            with open(self.THEME_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "current": self.current_theme,
                    "custom": self.custom_themes
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ThemeManager] Speicher-Fehler: {e}")

    def _apply_theme(self, name):
        """Wendet ein Theme an und aktualisiert COLORS global."""
        theme = self.get_theme(name)
        if theme:
            COLORS.update(theme)
            self.current_theme = name
            CFG.set("gui_theme_name", name)

    def get_theme(self, name):
        """Holt ein Theme nach Name."""
        if name in self.PRESETS:
            return dict(self.PRESETS[name])
        if name in self.custom_themes:
            return dict(self.custom_themes[name])
        return None

    def get_all_themes(self):
        """Gibt alle verfügbaren Theme-Namen zurück."""
        return list(self.PRESETS.keys()) + list(self.custom_themes.keys())

    def set_theme(self, name):
        """Setzt ein Theme aktiv."""
        if name in self.PRESETS or name in self.custom_themes:
            self._apply_theme(name)
            self._save_custom_themes()
            return f"Theme '{name}' aktiviert."
        return f"Theme '{name}' nicht gefunden."

    def create_custom_theme(self, name, colors):
        """Erstellt ein benutzerdefiniertes Theme."""
        self.custom_themes[name] = dict(colors)
        self._save_custom_themes()
        return f"Theme '{name}' erstellt."

    def delete_custom_theme(self, name):
        """Löscht ein benutzerdefiniertes Theme."""
        if name in self.custom_themes:
            del self.custom_themes[name]
            self._save_custom_themes()
            return f"Theme '{name}' gelöscht."
        return "Nur benutzerdefinierte Themes können gelöscht werden."

    def export_theme(self, name, path):
        """Exportiert ein Theme als JSON-Datei."""
        theme = self.get_theme(name)
        if theme:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"name": name, "colors": theme}, f, ensure_ascii=False, indent=2)
                return f"Theme '{name}' exportiert nach {path}"
            except Exception as e:
                return f"Export-Fehler: {e}"
        return f"Theme '{name}' nicht gefunden."

    def import_theme(self, path):
        """Importiert ein Theme aus JSON-Datei."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("name", "Imported Theme")
            colors = data.get("colors", {})
            self.custom_themes[name] = colors
            self._save_custom_themes()
            return f"Theme '{name}' importiert."
        except Exception as e:
            return f"Import-Fehler: {e}"

    def get_font(self, size_key="base"):
        """Gibt die aktuelle Font-Konfiguration zurück."""
        family = COLORS.get("font_family", "Consolas")
        size_map = {
            "header": COLORS.get("font_size_header", 20),
            "title": COLORS.get("font_size_title", 12),
            "base": COLORS.get("font_size_base", 11),
            "small": COLORS.get("font_size_small", 9),
            "tiny": COLORS.get("font_size_tiny", 8),
        }
        return (family, size_map.get(size_key, 11))


THEME = ThemeManager()



# ═══════════════════════════════════════════════════════════════════════════════
#  THEME EDITOR v10 — GUI Customization Dialog
# ═══════════════════════════════════════════════════════════════════════════════

class ThemeEditor:
    """
    v10: Visueller Theme-Editor für AERA.

    Features:
    • Farb-Picker für alle UI-Elemente (tkinter colorchooser)
    • Font-Auswahl aus allen System-Fonts
    • Live-Preview des Themes
    • Preset-Themes laden
    • Benutzerdefinierte Themes speichern
    • JSON Export/Import
    """

    COLOR_KEYS = [
        ("bg", "Hintergrund", "Haupt-Hintergrundfarbe"),
        ("bg_panel", "Panel", "Seitenleisten-Hintergrund"),
        ("bg_card", "Karte", "Karten/Container-Hintergrund"),
        ("accent", "Akzent", "Primäre Akzentfarbe"),
        ("accent_light", "Akzent Hell", "Heller Akzent-Ton"),
        ("accent_dark", "Akzent Dunkel", "Dunkler Akzent-Ton"),
        ("green", "Grün", "Erfolg/Positiv"),
        ("amber", "Gelb", "Warnung/Hinweis"),
        ("red", "Rot", "Fehler/Negativ"),
        ("text_bright", "Text Hell", "Heller Text"),
        ("text_mid", "Text Mittel", "Mittlerer Text"),
        ("text_dim", "Text Dunkel", "Gedimmter Text"),
        ("border", "Rahmen", "Rahmenfarbe"),
        ("glow", "Glow", "Glow-Effekt"),
        ("purple", "Lila", "Sekundäre Akzentfarbe"),
    ]

    FONT_KEYS = [
        ("font_family", "Schriftart", "Hauptschriftart"),
        ("font_size_header", "Header-Größe", "Überschriften"),
        ("font_size_title", "Titel-Größe", "Titel/Labels"),
        ("font_size_base", "Basis-Größe", "Normaler Text"),
        ("font_size_small", "Klein", "Kleiner Text"),
        ("font_size_tiny", "Mini", "Sehr kleiner Text"),
    ]

    def __init__(self, parent_root, on_apply=None, on_close=None):
        self.parent = parent_root
        self.on_apply = on_apply
        self.on_close = on_close
        self.current_colors = dict(COLORS)
        self.preview_widgets = []

        self._build_window()

    def _build_window(self):
        self.win = tk.Toplevel(self.parent)
        self.win.title("AERA Theme Editor v10")
        self.win.geometry("900x700")
        self.win.configure(bg=COLORS["bg"])
        self.win.minsize(800, 600)
        self.win.transient(self.parent)

        # Main layout
        main = tk.Frame(self.win, bg=COLORS["bg"])
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        # Header
        hdr = tk.Frame(main, bg=COLORS["bg_panel"], height=48)
        hdr.pack(fill=tk.X, pady=(0, 8))
        hdr.pack_propagate(False)

        tk.Label(hdr, text="◈ THEME EDITOR", font=("Consolas", 14, "bold"),
                 bg=COLORS["bg_panel"], fg=COLORS["accent_light"]).pack(side=tk.LEFT, padx=16, pady=8)

        # Theme selector
        theme_frame = tk.Frame(hdr, bg=COLORS["bg_panel"])
        theme_frame.pack(side=tk.RIGHT, padx=16)

        tk.Label(theme_frame, text="Preset:", font=("Consolas", 9),
                 bg=COLORS["bg_panel"], fg=COLORS["text_dim"]).pack(side=tk.LEFT)

        self.theme_var = tk.StringVar(value=THEME.current_theme)
        theme_combo = tk.OptionMenu(theme_frame, self.theme_var, *THEME.get_all_themes(),
                                     command=self._load_preset)
        theme_combo.config(bg=COLORS["bg_card"], fg=COLORS["text_bright"],
                           relief=tk.FLAT, highlightthickness=0)
        theme_combo["menu"].config(bg=COLORS["bg_card"], fg=COLORS["text_bright"])
        theme_combo.pack(side=tk.LEFT, padx=4)

        # Content area with tabs
        content = tk.Frame(main, bg=COLORS["bg"])
        content.pack(fill=tk.BOTH, expand=True)

        # Left: Color editor
        left = tk.Frame(content, bg=COLORS["bg_panel"], width=400)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        left.pack_propagate(False)

        tk.Label(left, text="FARBEN", font=("Consolas", 10, "bold"),
                 bg=COLORS["bg_panel"], fg=COLORS["accent_light"]).pack(anchor="w", padx=12, pady=8)

        # Scrollable color list
        color_canvas = tk.Canvas(left, bg=COLORS["bg_panel"], highlightthickness=0)
        scrollbar = tk.Scrollbar(left, orient="vertical", command=color_canvas.yview)
        self.color_frame = tk.Frame(color_canvas, bg=COLORS["bg_panel"])

        self.color_frame.bind("<Configure>", lambda e: color_canvas.configure(scrollregion=color_canvas.bbox("all")))
        color_canvas.create_window((0, 0), window=self.color_frame, anchor="nw", width=380)
        color_canvas.configure(yscrollcommand=scrollbar.set)

        color_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.color_vars = {}
        self.color_buttons = {}
        for key, label, desc in self.COLOR_KEYS:
            row = tk.Frame(self.color_frame, bg=COLORS["bg_panel"])
            row.pack(fill=tk.X, pady=2, padx=4)

            tk.Label(row, text=f"{label}:", font=("Consolas", 9),
                     bg=COLORS["bg_panel"], fg=COLORS["text_bright"],
                     width=12, anchor="w").pack(side=tk.LEFT)

            var = tk.StringVar(value=self.current_colors.get(key, "#000000"))
            self.color_vars[key] = var

            btn = tk.Button(row, text="   ", font=("Consolas", 8),
                           bg=var.get(), fg=var.get(),
                           relief=tk.FLAT, bd=1, width=3,
                           command=lambda k=key, v=var: self._pick_color(k, v))
            btn.pack(side=tk.LEFT, padx=4)
            self.color_buttons[key] = btn

            entry = tk.Entry(row, textvariable=var, font=("Consolas", 9),
                            bg=COLORS["bg"], fg=COLORS["text_bright"],
                            relief=tk.FLAT, width=10)
            entry.pack(side=tk.LEFT, padx=4)
            entry.bind("<Return>", lambda e, k=key, v=var: self._update_color(k, v.get()))

            tk.Label(row, text=desc, font=("Consolas", 8),
                     bg=COLORS["bg_panel"], fg=COLORS["text_dim"]).pack(side=tk.LEFT, padx=4)

        # Right: Font editor + Preview
        right = tk.Frame(content, bg=COLORS["bg_panel"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))

        # Font section
        font_section = tk.Frame(right, bg=COLORS["bg_panel"])
        font_section.pack(fill=tk.X, padx=12, pady=8)

        tk.Label(font_section, text="SCHRIFTART", font=("Consolas", 10, "bold"),
                 bg=COLORS["bg_panel"], fg=COLORS["accent_light"]).pack(anchor="w", pady=(0, 8))

        # Font family
        fam_row = tk.Frame(font_section, bg=COLORS["bg_panel"])
        fam_row.pack(fill=tk.X, pady=2)
        tk.Label(fam_row, text="Font:", font=("Consolas", 9),
                 bg=COLORS["bg_panel"], fg=COLORS["text_bright"],
                 width=12, anchor="w").pack(side=tk.LEFT)

        self.font_var = tk.StringVar(value=self.current_colors.get("font_family", "Consolas"))
        font_combo = tk.OptionMenu(fam_row, self.font_var, *sorted(tkfont.families() if tkfont else ["Consolas", "Arial", "Courier New"]),
                                    command=lambda _: self._update_preview())
        font_combo.config(bg=COLORS["bg_card"], fg=COLORS["text_bright"],
                          relief=tk.FLAT, highlightthickness=0)
        font_combo["menu"].config(bg=COLORS["bg_card"], fg=COLORS["text_bright"])
        font_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # Font sizes
        self.font_size_vars = {}
        for key, label, desc in self.FONT_KEYS[1:]:  # Skip font_family
            row = tk.Frame(font_section, bg=COLORS["bg_panel"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=f"{label}:", font=("Consolas", 9),
                     bg=COLORS["bg_panel"], fg=COLORS["text_bright"],
                     width=12, anchor="w").pack(side=tk.LEFT)

            var = tk.IntVar(value=self.current_colors.get(key, 11))
            self.font_size_vars[key] = var

            spin = tk.Spinbox(row, from_=6, to=48, textvariable=var,
                             font=("Consolas", 9), width=5,
                             bg=COLORS["bg"], fg=COLORS["text_bright"],
                             relief=tk.FLAT, command=self._update_preview)
            spin.pack(side=tk.LEFT, padx=4)

            tk.Label(row, text=desc, font=("Consolas", 8),
                     bg=COLORS["bg_panel"], fg=COLORS["text_dim"]).pack(side=tk.LEFT, padx=4)

        # Preview section
        preview_frame = tk.Frame(right, bg=COLORS["bg"], bd=1,
                                 highlightbackground=COLORS["border"], highlightthickness=1)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        tk.Label(preview_frame, text="LIVE PREVIEW", font=("Consolas", 9, "bold"),
                 bg=COLORS["bg"], fg=COLORS["accent_light"]).pack(anchor="w", padx=8, pady=4)

        self.preview_container = tk.Frame(preview_frame, bg=COLORS["bg"])
        self.preview_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self._build_preview()

        # Action buttons
        btn_frame = tk.Frame(main, bg=COLORS["bg"])
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        tk.Button(btn_frame, text="💾 SPEICHERN", font=("Consolas", 10, "bold"),
                  bg=COLORS["green"], fg=COLORS["bg"],
                  relief=tk.FLAT, bd=0, padx=16, pady=8, cursor="hand2",
                  command=self._save_theme).pack(side=tk.LEFT, padx=4)

        tk.Button(btn_frame, text="🔄 ANWENDEN", font=("Consolas", 10, "bold"),
                  bg=COLORS["accent"], fg=COLORS["bg"],
                  relief=tk.FLAT, bd=0, padx=16, pady=8, cursor="hand2",
                  command=self._apply_theme).pack(side=tk.LEFT, padx=4)

        tk.Button(btn_frame, text="📤 EXPORT", font=("Consolas", 10),
                  bg=COLORS["bg_card"], fg=COLORS["text_bright"],
                  relief=tk.FLAT, bd=0, padx=12, pady=8, cursor="hand2",
                  command=self._export_theme).pack(side=tk.LEFT, padx=4)

        tk.Button(btn_frame, text="📥 IMPORT", font=("Consolas", 10),
                  bg=COLORS["bg_card"], fg=COLORS["text_bright"],
                  relief=tk.FLAT, bd=0, padx=12, pady=8, cursor="hand2",
                  command=self._import_theme).pack(side=tk.LEFT, padx=4)

        tk.Button(btn_frame, text="🖼 GALERIE", font=("Consolas", 10),
                  bg=COLORS["bg_card"], fg=COLORS["text_bright"],
                  relief=tk.FLAT, bd=0, padx=12, pady=8, cursor="hand2",
                  command=self._show_theme_gallery).pack(side=tk.LEFT, padx=4)

        tk.Button(btn_frame, text="✕ SCHLIESSEN", font=("Consolas", 10),
                  bg=COLORS["red"], fg=COLORS["bg"],
                  relief=tk.FLAT, bd=0, padx=16, pady=8, cursor="hand2",
                  command=self._close).pack(side=tk.RIGHT, padx=4)

        self.win.protocol("WM_DELETE_WINDOW", self._close)

    def _build_preview(self):
        """Build the live preview widgets."""
        for w in self.preview_container.winfo_children():
            w.destroy()

        # Sample UI elements
        p = self.preview_container
        bg = self.current_colors.get("bg", "#0D1117")
        panel = self.current_colors.get("bg_panel", "#161B22")
        card = self.current_colors.get("bg_card", "#1C2128")
        accent = self.current_colors.get("accent", "#1E6FD9")
        text = self.current_colors.get("text_bright", "#E6EDF3")
        text_dim = self.current_colors.get("text_dim", "#484F58")
        green = self.current_colors.get("green", "#3FB950")
        red = self.current_colors.get("red", "#F85149")

        font_family = self.font_var.get()

        # Header preview
        hdr = tk.Frame(p, bg=panel, height=30)
        hdr.pack(fill=tk.X, pady=2)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="A.E.R.A", font=(font_family, 14, "bold"),
                 bg=panel, fg=accent).pack(side=tk.LEFT, padx=8, pady=4)

        # Chat area preview
        chat = tk.Frame(p, bg=bg, height=80)
        chat.pack(fill=tk.X, pady=2)
        chat.pack_propagate(False)
        tk.Label(chat, text="▸ Benutzerbefehl", font=(font_family, 10),
                 bg=bg, fg=self.current_colors.get("amber", "#F0A32F")).pack(anchor="w", padx=8, pady=2)
        tk.Label(chat, text="AERA Antwort hier...", font=(font_family, 10),
                 bg=bg, fg=text).pack(anchor="w", padx=8)

        # Button preview
        btn_row = tk.Frame(p, bg=bg)
        btn_row.pack(fill=tk.X, pady=4)
        tk.Button(btn_row, text="AKTION", font=(font_family, 9),
                  bg=accent, fg=bg, relief=tk.FLAT, bd=0, padx=8, pady=3).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="OK", font=(font_family, 9),
                  bg=green, fg=bg, relief=tk.FLAT, bd=0, padx=8, pady=3).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="X", font=(font_family, 9),
                  bg=red, fg=bg, relief=tk.FLAT, bd=0, padx=8, pady=3).pack(side=tk.LEFT, padx=4)

        # Status preview
        status = tk.Frame(p, bg=panel, height=20)
        status.pack(fill=tk.X, pady=2)
        status.pack_propagate(False)
        tk.Label(status, text="● NOMINAL │ v10", font=(font_family, 8),
                 bg=panel, fg=text_dim).pack(side=tk.LEFT, padx=8, pady=2)

    def _pick_color(self, key, var):
        """Open color picker dialog."""
        from tkinter import colorchooser
        color = colorchooser.askcolor(color=var.get(), title=f"Farbe wählen: {key}")
        if color[1]:
            var.set(color[1])
            self._update_color(key, color[1])

    def _update_color(self, key, value):
        """Update a color value."""
        self.current_colors[key] = value
        if key in self.color_buttons:
            self.color_buttons[key].config(bg=value)
        self._update_preview()

    def _update_preview(self):
        """Update the live preview."""
        # Update current colors from vars
        for key, var in self.color_vars.items():
            self.current_colors[key] = var.get()
        self.current_colors["font_family"] = self.font_var.get()
        for key, var in self.font_size_vars.items():
            self.current_colors[key] = var.get()
        self._build_preview()

    def _load_preset(self, name):
        """Load a preset theme."""
        theme = THEME.get_theme(name)
        if theme:
            self.current_colors = dict(theme)
            for key, var in self.color_vars.items():
                if key in theme:
                    var.set(theme[key])
                    if key in self.color_buttons:
                        self.color_buttons[key].config(bg=theme[key])
            if "font_family" in theme:
                self.font_var.set(theme["font_family"])
            for key, var in self.font_size_vars.items():
                if key in theme:
                    var.set(theme[key])
            self._update_preview()

    def _save_theme(self):
        """Save as custom theme."""
        from tkinter import simpledialog
        name = simpledialog.askstring("Theme speichern", "Name des Themes:",
                                       parent=self.win)
        if name:
            result = THEME.create_custom_theme(name, self.current_colors)
            self.theme_var.set(name)
            # Update dropdown
            menu = self.win.nametowidget(self.theme_var.trace_info()[0][0]) if self.win.nametowidget(self.theme_var.trace_info()[0][0]) else None
            self._show_message(result)

    def _apply_theme(self):
        """Apply theme immediately."""
        COLORS.update(self.current_colors)
        if self.on_apply:
            self.on_apply()
        self._show_message("Theme angewendet! GUI wird beim nächsten Start vollständig aktualisiert.")

    def _export_theme(self):
        """Export theme to JSON."""
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=f"aera_theme_{self.theme_var.get().replace(' ', '_')}.json"
        )
        if path:
            result = THEME.export_theme(self.theme_var.get(), path)
            self._show_message(result)

    def _import_theme(self):
        """Import theme from JSON."""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")]
        )
        if path:
            result = THEME.import_theme(path)
            self._show_message(result)
            # Refresh dropdown
            self._load_preset(THEME.current_theme)

    def _show_message(self, msg):
        """Show a temporary message."""
        popup = tk.Toplevel(self.win)
        popup.title("")
        popup.overrideredirect(True)
        popup.configure(bg=COLORS["bg_card"])
        lbl = tk.Label(popup, text=msg, font=("Consolas", 10),
                       bg=COLORS["bg_card"], fg=COLORS["text_bright"],
                       padx=20, pady=12)
        lbl.pack()
        popup.geometry(f"+{self.win.winfo_x() + 200}+{self.win.winfo_y() + 300}")
        self.win.after(3000, popup.destroy)

    def _show_theme_gallery(self):
        """Zeigt eine visuelle Galerie aller Themes."""
        gallery = tk.Toplevel(self.win)
        gallery.title("AERA Theme Galerie")
        gallery.geometry("700x400")
        gallery.configure(bg=COLORS["bg"])
        gallery.transient(self.win)

        tk.Label(gallery, text="◈ THEME GALERIE", font=("Consolas", 14, "bold"),
                 bg=COLORS["bg"], fg=COLORS["accent_light"]).pack(pady=12)

        frame = tk.Frame(gallery, bg=COLORS["bg"])
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        for name in THEME.get_all_themes():
            theme = THEME.get_theme(name)
            if not theme:
                continue

            card = tk.Frame(frame, bg=theme.get("bg_panel", "#161B22"), bd=1,
                           highlightbackground=theme.get("border", "#30363D"), highlightthickness=1)
            card.pack(fill=tk.X, pady=4, padx=4)

            top = tk.Frame(card, bg=theme.get("bg_panel", "#161B22"))
            top.pack(fill=tk.X, padx=8, pady=4)

            # Color dots
            for key, label in [("accent", "Ac"), ("green", "Gr"), ("red", "Rd"), ("amber", "Am")]:
                c = tk.Canvas(top, width=20, height=20, bg=theme.get("bg_panel", "#161B22"),
                             highlightthickness=0)
                c.pack(side=tk.LEFT, padx=2)
                c.create_oval(2, 2, 18, 18, fill=theme.get(key, "#000"), outline="")

            tk.Label(top, text=name, font=("Consolas", 11, "bold"),
                     bg=theme.get("bg_panel", "#161B22"),
                     fg=theme.get("accent_light", "#58A6FF")).pack(side=tk.LEFT, padx=8)

            tk.Button(top, text="LADEN", font=("Consolas", 8),
                     bg=theme.get("accent", "#1E6FD9"), fg=theme.get("bg", "#0D1117"),
                     relief=tk.FLAT, bd=0, padx=8, pady=2,
                     command=lambda n=name: [self._load_preset(n), gallery.destroy()]).pack(side=tk.RIGHT)

        tk.Button(gallery, text="SCHLIESSEN", font=("Consolas", 10),
                 bg=COLORS["red"], fg=COLORS["bg"], relief=tk.FLAT, bd=0,
                 padx=16, pady=6, command=gallery.destroy).pack(pady=12)

    def _close(self):
        if self.on_close:
            self.on_close()
        self.win.destroy()

class AERACompactGUI:
    """
    Kompakte, schwebende Popup-GUI für AERA.

    Features:
    • Borderloses Fenster (kein Rahmen, keine Titelleiste)
    • Immer im Vordergrund (always-on-top)
    • Verschiebbar per Drag & Drop
    • Zeigt aktuellen Zuhör-Status an (pulsierender Ring)
    • Zeigt letzten erkannten Befehl
    • Mikrofon-Button für manuelle Aufnahme
    • Toggle-Button zur Rückkehr zur Voll-GUI
    • Automatisches Ausblenden bei Inaktivität
    """

    def __init__(self, aera_gui_ref):
        self.aera = aera_gui_ref
        self.root = tk.Toplevel()
        self.root.title("AERA Compact")

        # Borderless, always-on-top window
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.95)

        # Size and position (bottom-right corner default)
        self.width = 320
        self.height = 140
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.x = screen_w - self.width - 20
        self.y = screen_h - self.height - 60
        self.root.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")

        # Colors matching AERA theme
        self.bg_color = "#0D1117"
        self.card_color = "#161B22"
        self.accent = "#1E6FD9"
        self.accent_light = "#58A6FF"
        self.green = "#3FB950"
        self.red = "#F85149"
        self.amber = "#F0A32F"
        self.text_bright = "#E6EDF3"
        self.text_dim = "#8B949E"

        self.root.configure(bg=self.bg_color)

        # Drag state
        self.drag_data = {"x": 0, "y": 0, "dragging": False}

        # Animation state
        self._pulse_angle = 0.0
        self._status = "standby"  # standby, listening, working
        self._last_command = ""
        self._auto_hide_timer = None
        self._visible = True

        self._build_ui()
        self._start_animations()
        self._setup_drag()

    def _build_ui(self):
        """Build the compact UI."""
        # Main container with rounded feel (using padding)
        main = tk.Frame(self.root, bg=self.bg_color, bd=1,
                        highlightbackground="#30363D", highlightthickness=1)
        main.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Top bar with drag handle and controls
        top = tk.Frame(main, bg=self.card_color, height=28)
        top.pack(fill=tk.X)
        top.pack_propagate(False)

        # Drag handle (grip lines)
        grip = tk.Frame(top, bg=self.card_color)
        grip.pack(side=tk.LEFT, padx=8, pady=4)
        for _ in range(3):
            tk.Label(grip, text="━", font=("Consolas", 5),
                     bg=self.card_color, fg=self.text_dim).pack()

        # Title
        tk.Label(top, text="A.E.R.A", font=("Consolas", 9, "bold"),
                 bg=self.card_color, fg=self.accent_light).pack(side=tk.LEFT, padx=4)

        # Window controls
        ctrl = tk.Frame(top, bg=self.card_color)
        ctrl.pack(side=tk.RIGHT, padx=4)

        # Minimize/Hide button
        tk.Button(ctrl, text="─", font=("Consolas", 8, "bold"),
                  bg=self.card_color, fg=self.text_dim,
                  relief=tk.FLAT, bd=0, padx=4, pady=0, cursor="hand2",
                  command=self._hide_window).pack(side=tk.LEFT, padx=1)

        # Expand to full GUI button
        tk.Button(ctrl, text="□", font=("Consolas", 8, "bold"),
                  bg=self.card_color, fg=self.accent_light,
                  relief=tk.FLAT, bd=0, padx=4, pady=0, cursor="hand2",
                  command=self._expand_to_full).pack(side=tk.LEFT, padx=1)

        # Close button
        tk.Button(ctrl, text="✕", font=("Consolas", 8, "bold"),
                  bg=self.card_color, fg=self.red,
                  relief=tk.FLAT, bd=0, padx=4, pady=0, cursor="hand2",
                  command=self._close).pack(side=tk.LEFT, padx=1)

        # Content area
        content = tk.Frame(main, bg=self.bg_color)
        content.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # Left: Status ring + mic button
        left = tk.Frame(content, bg=self.bg_color)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        # Status canvas (pulsing ring)
        self.status_canvas = tk.Canvas(left, width=50, height=50,
                                       bg=self.bg_color, highlightthickness=0)
        self.status_canvas.pack()

        # Draw ring
        cx, cy, r = 25, 25, 20
        self._ring_bg = self.status_canvas.create_oval(
            cx-r, cy-r, cx+r, cy+r, outline="#30363D", width=2)
        self._ring_arc = self.status_canvas.create_arc(
            cx-r, cy-r, cx+r, cy+r, start=90, extent=0,
            outline=self.accent, width=3, style="arc")
        self._center_dot = self.status_canvas.create_oval(
            cx-4, cy-4, cx+4, cy+4, fill=self.accent, outline="")

        # Mic button below ring
        self.mic_btn = tk.Button(left, text="🎤", font=("Segoe UI", 14),
                                 bg=self.card_color, fg=self.text_dim,
                                 relief=tk.FLAT, bd=0, padx=4, pady=2,
                                 cursor="hand2", command=self._mic_click)
        self.mic_btn.pack(pady=(4, 0))

        # Right: Status text + last command
        right = tk.Frame(content, bg=self.bg_color)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Status label
        self.status_lbl = tk.Label(right, text="STANDBY",
                                   font=("Consolas", 10, "bold"),
                                   bg=self.bg_color, fg=self.text_dim)
        self.status_lbl.pack(anchor="w")

        # Last command label
        self.cmd_lbl = tk.Label(right, text="Warte auf Befehl...",
                                font=("Consolas", 8),
                                bg=self.bg_color, fg=self.text_dim,
                                wraplength=200, justify=tk.LEFT)
        self.cmd_lbl.pack(anchor="w", pady=(2, 0))

        # Quick action buttons row
        actions = tk.Frame(right, bg=self.bg_color)
        actions.pack(fill=tk.X, pady=(6, 0))

        tk.Button(actions, text="📝", font=("Segoe UI", 10),
                  bg=self.card_color, fg=self.text_dim,
                  relief=tk.FLAT, bd=0, padx=4, pady=1, cursor="hand2",
                  command=lambda: self._send_quick("öffne notepad")).pack(side=tk.LEFT, padx=1)
        tk.Button(actions, text="🔍", font=("Segoe UI", 10),
                  bg=self.card_color, fg=self.text_dim,
                  relief=tk.FLAT, bd=0, padx=4, pady=1, cursor="hand2",
                  command=lambda: self._send_quick("öffne browser")).pack(side=tk.LEFT, padx=1)
        tk.Button(actions, text="📁", font=("Segoe UI", 10),
                  bg=self.card_color, fg=self.text_dim,
                  relief=tk.FLAT, bd=0, padx=4, pady=1, cursor="hand2",
                  command=lambda: self._send_quick("öffne downloads")).pack(side=tk.LEFT, padx=1)
        tk.Button(actions, text="⚙", font=("Segoe UI", 10),
                  bg=self.card_color, fg=self.text_dim,
                  relief=tk.FLAT, bd=0, padx=4, pady=1, cursor="hand2",
                  command=lambda: self._send_quick("öffne einstellungen")).pack(side=tk.LEFT, padx=1)

        # Bottom info bar
        info = tk.Frame(main, bg=self.card_color, height=18)
        info.pack(fill=tk.X, side=tk.BOTTOM)
        info.pack_propagate(False)

        self.info_lbl = tk.Label(info, text="v10.3 │ Smart Learning Guard",
                                 font=("Consolas", 7),
                                 bg=self.card_color, fg=self.text_dim)
        self.info_lbl.pack(side=tk.LEFT, padx=8)

        # TTS mute toggle
        self.tts_btn = tk.Label(info, text="🔊",
                                font=("Segoe UI", 8),
                                bg=self.card_color, fg=self.green,
                                cursor="hand2")
        self.tts_btn.pack(side=tk.RIGHT, padx=8)
        self.tts_btn.bind("<Button-1>", lambda e: self._toggle_tts())

    def _setup_drag(self):
        """Setup drag functionality for the borderless window."""
        def start_drag(event):
            self.drag_data["x"] = event.x_root - self.root.winfo_x()
            self.drag_data["y"] = event.y_root - self.root.winfo_y()
            self.drag_data["dragging"] = True

        def do_drag(event):
            if self.drag_data["dragging"]:
                x = event.x_root - self.drag_data["x"]
                y = event.y_root - self.drag_data["y"]
                self.root.geometry(f"+{x}+{y}")
                self.x, self.y = x, y

        def stop_drag(event):
            self.drag_data["dragging"] = False

        # Bind to top bar and grip
        for widget in [self.root, self.status_canvas]:
            widget.bind("<Button-1>", start_drag)
            widget.bind("<B1-Motion>", do_drag)
            widget.bind("<ButtonRelease-1>", stop_drag)

    def _start_animations(self):
        """Start the pulsing ring animation."""
        self._animate_ring()
        self._auto_hide_check()

    def _animate_ring(self):
        """Animate the status ring based on current state."""
        self._pulse_angle = (self._pulse_angle + 5) % 360
        c = self.status_canvas

        if self._status == "standby":
            extent = int(60 + 30 * math.sin(math.radians(self._pulse_angle)))
            color = self.text_dim
            dot_color = self.text_dim
            text = "STANDBY"
            text_color = self.text_dim
        elif self._status == "listening":
            extent = int(180 + 60 * math.sin(math.radians(self._pulse_angle * 3)))
            color = self.green
            dot_color = self.green
            text = "HÖRE ZU"
            text_color = self.green
        elif self._status == "working":
            extent = int(self._pulse_angle % 360)
            color = self.accent
            dot_color = self.accent
            text = "ARBEITE"
            text_color = self.accent_light
        else:
            extent = 360
            color = self.amber
            dot_color = self.amber
            text = "BEREIT"
            text_color = self.amber

        start = (90 - self._pulse_angle) % 360
        c.itemconfig(self._ring_arc, outline=color, extent=extent, start=start)
        c.itemconfig(self._center_dot, fill=dot_color)
        self.status_lbl.config(text=text, fg=text_color)

        # Schedule next frame
        self.root.after(50, self._animate_ring)

    def _auto_hide_check(self):
        """Check if window should auto-hide after inactivity."""
        # This could be expanded to auto-hide after X seconds of inactivity
        # For now, just keep it visible
        pass

    def set_status(self, status: str):
        """Set the current status (standby, listening, working)."""
        self._status = status

    def set_last_command(self, text: str):
        """Display the last recognized command."""
        self._last_command = text
        truncated = text[:45] + "..." if len(text) > 45 else text
        self.cmd_lbl.config(text=f"▸ {truncated}")

    def _mic_click(self):
        """Handle mic button click."""
        if self.aera and hasattr(self.aera, 'voice'):
            self.set_status("listening")
            self.mic_btn.config(fg=self.red)

            def record():
                text = self.aera.voice.listen_once(timeout=6)
                self.root.after(0, lambda: self._mic_done(text))

            threading.Thread(target=record, daemon=True).start()

    def _mic_done(self, text):
        """Called when manual recording is done."""
        self.mic_btn.config(fg=self.text_dim)
        if text:
            self.set_last_command(text)
            self.set_status("working")
            if self.aera:
                self.aera.send_message(text)
        else:
            self.set_status("standby")

    def _send_quick(self, cmd: str):
        """Send a quick command."""
        self.set_last_command(cmd)
        self.set_status("working")
        if self.aera:
            self.aera.send_message(cmd)

    def _toggle_tts(self):
        """Toggle TTS mute."""
        if self.aera and hasattr(self.aera, 'tts'):
            muted = self.aera.tts.toggle_mute()
            self.tts_btn.config(fg=self.red if muted else self.green,
                                text="🔇" if muted else "🔊")

    def _hide_window(self):
        """Minimize/hide the compact window."""
        self.root.withdraw()
        self._visible = False
        # Show a small tray indicator or system notification could go here

    def show_window(self):
        """Show the compact window."""
        self.root.deiconify()
        self.root.lift()
        self.root.attributes('-topmost', True)
        self._visible = True

    def _expand_to_full(self):
        """Switch back to full GUI mode."""
        if self.aera:
            self.aera.switch_to_full_gui()

    def _close(self):
        """Close the compact GUI."""
        self.root.destroy()
        if self.aera:
            self.aera.compact_gui = None

    def update_from_full(self):
        """Update compact GUI state from full GUI."""
        if self.aera:
            # Sync TTS state
            if hasattr(self.aera, 'tts') and self.aera.tts.muted:
                self.tts_btn.config(fg=self.red, text="🔇")
            else:
                self.tts_btn.config(fg=self.green, text="🔊")

    def is_visible(self):
        return self._visible


# ═══════════════════════════════════════════════════════════════════════════════
#  COLLAPSIBLE PANEL — Kollapsierbare Seitenleisten
# ═══════════════════════════════════════════════════════════════════════════════

class CollapsiblePanel:
    """
    Kollapsierbares Panel mit Toggle-Button im Header.
    Alle Widgets werden zum content_frame hinzugefügt.
    """

    def __init__(self, parent, title, width=310, default_open=True,
                 bg_color=None, title_color=None):
        self.parent = parent
        self.width = width
        self.is_open = default_open
        self.bg_color = bg_color or COLORS["bg_panel"]
        self.title_color = title_color or COLORS["accent_light"]

        # Haupt-Container — fill=tk.X damit er die volle Breite nutzt
        self.container = tk.Frame(parent, bg=self.bg_color)
        self.container.pack(fill=tk.X, padx=8, pady=(0, 4))

        # Header mit Toggle — füllt volle Breite, Höhe fix
        self.header = tk.Frame(self.container, bg=self.bg_color, height=28)
        self.header.pack(fill=tk.X)

        # Toggle-Icon
        self.toggle_icon = tk.Label(
            self.header, text="▼" if default_open else "▶",
            font=("Consolas", 8),
            bg=self.bg_color, fg=self.title_color,
            cursor="hand2", width=3
        )
        self.toggle_icon.pack(side=tk.LEFT, padx=(8, 4))

        # Titel
        self.title_lbl = tk.Label(
            self.header, text=title,
            font=("Consolas", 9, "bold"),
            bg=self.bg_color, fg=self.title_color
        )
        self.title_lbl.pack(side=tk.LEFT)

        # Badge (optional)
        self.badge_lbl = tk.Label(
            self.header, text="",
            font=("Consolas", 7),
            bg=self.bg_color, fg=COLORS["text_dim"]
        )
        self.badge_lbl.pack(side=tk.RIGHT, padx=8)

        # Separator
        self.sep = tk.Frame(self.container, bg=COLORS["border"], height=1)
        self.sep.pack(fill=tk.X, padx=8)

        # Content-Frame (kollapsierbar)
        self.content_frame = tk.Frame(self.container, bg=self.bg_color)
        if default_open:
            self.content_frame.pack(fill=tk.X, pady=(4, 8))

        # Bindings
        for widget in [self.toggle_icon, self.title_lbl, self.header]:
            widget.bind("<Button-1>", self._toggle)
        self.header.config(cursor="hand2")

    def _toggle(self, event=None):
        self.is_open = not self.is_open
        if self.is_open:
            self.toggle_icon.config(text="▼")
            self.content_frame.pack(fill=tk.X, pady=(4, 8))
        else:
            self.toggle_icon.config(text="▶")
            self.content_frame.pack_forget()

    def set_badge(self, text):
        self.badge_lbl.config(text=text)


class AERA_GUI:
    def __init__(self, start_compact=False):
        self.compact_gui = None
        self._gui_mode = "full"  # "full" or "compact"

        if HAS_CTK:
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
            self.root = ctk.CTk()
        else:
            self.root = tk.Tk()

        self.root.title(
            f"A.E.R.A v10.4 — qwen Tool-Ausführung + Smart Learning Guard")
        self.root.geometry("1700x1020")
        self.root.configure(bg=COLORS["bg"])
        self.root.minsize(1280, 720)

        self.tts    = TTSManager()
        self.timers = TimerManager(self.tts, on_done=self._timer_done)
        self.parser = CommandParser()
        # NEU v10: Smart Learning Engine
        self.smart_learning = SmartLearningEngine(
            tts_manager=self.tts,
            app_engine=APP_ENGINE,
            system_commands=SystemCommands()
        )
        # Verbinde Smart Learning mit Parser
        self.parser.smart_learning = self.smart_learning

        # NEU v10.4: Lokale LLM Engine mit Tool-Ausführung!
        self.ollama_engine = OllamaAIEngine(
            tts_manager=self.tts,
            max_tokens=500,
            command_parser=self.parser  # NEU v10.4: qwen kann AERA-Befehle ausführen!
        )
        # Verbinde lokale LLMs mit Parser
        self.parser.ollama_engine = self.ollama_engine

        self.voice  = AlwaysOnVoice(
            on_command=self._on_voice_cmd,
            on_short=self._on_short_cmd,
            on_log=self._voice_log,
            on_timer=self._on_timer,
        )

        self._pulse_angle  = 0.0
        self._ring_state   = "standby"
        self._stopwatch_on = False
        self.calendar_window = None
        self.voice_calendar = None

        self._build_ui()
        self._boot()
        self._start_voice()
        self._tick_timers()
        self._animate_ring()
        self._update_clock()

        # NEU v10: Starte im Kompakt-Modus wenn gewünscht
        if start_compact:
            self.root.after(500, self.switch_to_compact_gui)


    def _toggle_socratic(self):
        current = CFG.get("socratic_mode", True)
        CFG.set("socratic_mode", not current)
        self._update_soc_btn()
        status = "aktiviert" if CFG.get("socratic_mode") else "deaktiviert"
        self._insert(f"Sokratische Engine {status}.", "sys")

    def _update_soc_btn(self):
        if CFG.get("socratic_mode", True):
            self.soc_btn.config(text="SOKRATES", fg=COLORS["green"])
        else:
            self.soc_btn.config(text="SOKRATES", fg=COLORS["red"])

    def _build_ui(self):
        self._build_topbar()
        content = tk.Frame(self.root, bg=COLORS["bg"])
        content.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(content, bg=COLORS["bg_panel"], width=220)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 4), pady=8)
        left.pack_propagate(False)
        self._build_left(left)

        center = tk.Frame(content, bg=COLORS["bg"])
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=8)
        self._build_center(center)

        right = tk.Frame(content, bg=COLORS["bg_panel"], width=310)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 8), pady=8)
        right.pack_propagate(False)
        self._build_right(right)

        self._build_statusbar()

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=COLORS["bg_panel"], height=54)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        logo = tk.Frame(bar, bg=COLORS["bg_panel"])
        logo.pack(side=tk.LEFT, padx=20)
        tk.Label(logo, text="A.E.R.A", font=("Consolas", 20, "bold"),
                 bg=COLORS["bg_panel"], fg=COLORS["accent_light"]).pack(side=tk.LEFT)
        tk.Label(logo, text=" v10.2 [Lokale LLMs + Smart Learning v2 + Natural TTS]", font=("Consolas", 11),
                 bg=COLORS["bg_panel"], fg=COLORS["purple"]).pack(side=tk.LEFT, pady=6)

        right = tk.Frame(bar, bg=COLORS["bg_panel"])
        right.pack(side=tk.RIGHT, padx=16)

        self.clock_lbl = tk.Label(right, text="--:--:--",
                                  font=("Consolas", 14, "bold"),
                                  bg=COLORS["bg_panel"], fg=COLORS["amber"])
        self.clock_lbl.pack(side=tk.RIGHT, padx=12)

        self.voice_lbl = tk.Label(right, text="STANDBY",
                                  font=("Consolas", 10, "bold"),
                                  bg=COLORS["bg_panel"], fg=COLORS["text_dim"])
        self.voice_lbl.pack(side=tk.RIGHT, padx=10)

        # NEU v10: Theme Editor Button
        theme_btn = self._make_btn(right, "🎨 THEME", self._open_theme_editor, COLORS["purple"])
        theme_btn.pack(side=tk.RIGHT, padx=4)

        # NEU v10: GUI-Modus Toggle Button
        self.mode_btn = self._make_btn(right, "⛶ KOMPAKT", self.switch_to_compact_gui, COLORS["amber"])
        self.mode_btn.pack(side=tk.RIGHT, padx=4)

        mute_btn = self._make_btn(right, "TTS", self._toggle_mute, COLORS["text_mid"])
        mute_btn.pack(side=tk.RIGHT, padx=4)
        cmds_btn = self._make_btn(right, "Befehle", self._show_cmds, COLORS["accent"])
        cmds_btn.pack(side=tk.RIGHT, padx=4)
        apps_btn = self._make_btn(right, "Apps", self._show_app_search, COLORS["purple"])
        apps_btn.pack(side=tk.RIGHT, padx=4)
        self.soc_btn = self._make_btn(right, "SOKRATES", self._toggle_socratic, COLORS["green"])
        self.soc_btn.pack(side=tk.RIGHT, padx=4)

        tk.Frame(bar, bg=COLORS["accent_dark"], height=2).pack(side=tk.BOTTOM, fill=tk.X)


    def _build_left(self, parent):
        # STATUS Panel (immer offen)
        status_panel = CollapsiblePanel(
            parent, "STATUS", width=220, default_open=True,
            title_color=COLORS["accent_light"]
        )

        self.ring_canvas = tk.Canvas(status_panel.content_frame, width=180, height=180,
                                     bg=COLORS["bg_panel"], highlightthickness=0)
        self.ring_canvas.pack(padx=20)
        self._draw_ring_base()

        self.ring_lbl = tk.Label(status_panel.content_frame, text="STANDBY",
                                 font=("Consolas", 10, "bold"),
                                 bg=COLORS["bg_panel"], fg=COLORS["text_dim"])
        self.ring_lbl.pack(pady=4)

        # QUICK ACCESS Panel (immer offen)
        quick_panel = CollapsiblePanel(
            parent, "QUICK ACCESS", width=220, default_open=True,
            title_color=COLORS["purple"]
        )

        quick = [
            ("Screenshot",        "mach einen screenshot"),
            ("Batterie",          "akku status"),
            ("CPU-Auslastung",    "cpu"),
            ("RAM-Auslastung",    "ram"),
            ("Top-Prozesse",      "top prozesse"),
            ("Kalender",          "öffne kalender"),
            ("Passwort generieren", "passwort generieren"),
            ("UUID generieren",   "uuid"),
            ("Witz erzählen",     "erzähl einen witz"),
            ("Motivation",        "zitat"),
            ("Öff. IP",           "öffentliche ip"),
            ("WLAN Info",         "wlan"),
            ("Laufwerke",         "partitionen"),
            ("Ports anzeigen",    "offene ports"),
            ("Apps aktualisieren","apps aktualisieren"),
        ]
        for label, cmd in quick:
            btn = tk.Button(quick_panel.content_frame, text=f"▸ {label}",
                            font=("Consolas", 9),
                            bg=COLORS["bg_card"], fg=COLORS["accent_light"],
                            activebackground=COLORS["glow"],
                            activeforeground=COLORS["text_bright"],
                            relief=tk.FLAT, bd=0, padx=10, pady=3,
                            anchor="w", cursor="hand2",
                            command=lambda c=cmd: self.send_message(c))
            btn.pack(fill=tk.X, padx=8, pady=1)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=COLORS["glow"]))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=COLORS["bg_card"]))

    def _build_center(self, parent):
        hdr = tk.Frame(parent, bg=COLORS["bg_card"], height=32)
        hdr.pack(fill=tk.X, pady=(0, 2))
        hdr.pack_propagate(False)
        tk.Label(hdr, text="NEURAL INTERFACE",
                 font=("Consolas", 10, "bold"),
                 bg=COLORS["bg_card"], fg=COLORS["accent_light"]).pack(
            side=tk.LEFT, padx=16, pady=6)
        tk.Label(hdr, text="LOKALE LLMs │ MULTI-COMMAND v2 │ Natural TTS │ 150+ BEFEHLE │ v10.3",
                 font=("Consolas", 8),
                 bg=COLORS["bg_card"], fg=COLORS["text_dim"]).pack(
            side=tk.RIGHT, padx=16)

        chat_frame = tk.Frame(parent, bg=COLORS["bg_card"])
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self.chat = tk.scrolledtext.ScrolledText(
            chat_frame, wrap=tk.WORD, font=("Consolas", 11),
            bg=COLORS["bg"], fg=COLORS["text_bright"],
            insertbackground=COLORS["accent"],
            selectbackground=COLORS["glow"],
            relief=tk.FLAT, padx=18, pady=12, spacing3=4,
        )
        self.chat.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.chat.config(state=tk.DISABLED)

        tags = {
            "user":   (COLORS["amber"],        ("Consolas", 11, "bold")),
            "aera":   (COLORS["text_bright"],   ("Consolas", 11)),
            "sys":    (COLORS["text_dim"],      ("Consolas", 9)),
            "error":  (COLORS["red"],           ("Consolas", 11)),
            "voice":  (COLORS["green"],         ("Consolas", 11)),
            "syscmd": (COLORS["accent_light"],  ("Consolas", 11, "bold")),
            "timer":  (COLORS["red"],           ("Consolas", 11, "bold")),
            "short":  (COLORS["amber"],         ("Consolas", 11)),
            "search": (COLORS["accent_light"],  ("Consolas", 11)),
            "ask":    (COLORS["amber"],         ("Consolas", 11, "bold")),
            "app":    (COLORS["purple"],        ("Consolas", 11, "bold")),
        }
        for tag, (fg, font) in tags.items():
            self.chat.tag_config(tag, foreground=fg, font=font)

        inp_frame = tk.Frame(parent, bg=COLORS["bg_card"], height=54)
        inp_frame.pack(fill=tk.X)
        inp_frame.pack_propagate(False)
        tk.Frame(inp_frame, bg=COLORS["accent_dark"], height=1).pack(fill=tk.X, side=tk.TOP)

        self.mic_btn = tk.Button(inp_frame, text="MIC",
                                 font=("Consolas", 10, "bold"),
                                 bg=COLORS["bg_panel"], fg=COLORS["text_mid"],
                                 relief=tk.FLAT, bd=0, padx=14, pady=8, cursor="hand2")
        self.mic_btn.pack(side=tk.LEFT, padx=(12, 6), pady=8)
        self.mic_btn.bind("<ButtonPress-1>",   self._mic_press)
        self.mic_btn.bind("<ButtonRelease-1>", self._mic_release)

        self.input = tk.Entry(inp_frame, font=("Consolas", 12),
                              bg=COLORS["bg_input"], fg=COLORS["text_bright"],
                              insertbackground=COLORS["accent"],
                              relief=tk.FLAT, highlightthickness=1,
                              highlightcolor=COLORS["accent"],
                              highlightbackground=COLORS["border"])
        self.input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=8)
        self.input.bind("<Return>", lambda e: self._send())
        self.input.focus()

        send_btn = tk.Button(inp_frame, text="SENDEN ▶",
                             font=("Consolas", 10, "bold"),
                             bg=COLORS["accent"], fg=COLORS["bg"],
                             activebackground=COLORS["accent_light"],
                             activeforeground=COLORS["bg"],
                             relief=tk.FLAT, bd=0, padx=16, pady=8,
                             cursor="hand2", command=self._send)
        send_btn.pack(side=tk.RIGHT, padx=(4, 12), pady=8)

        clear_btn = self._make_btn(inp_frame, "CLR", self._clear_chat, COLORS["text_mid"])
        clear_btn.pack(side=tk.RIGHT, padx=0, pady=8)

    def _build_right(self, parent):
        # ── TIMER & STOPPUHR (immer offen) ─────────────────────────────
        timer_panel = CollapsiblePanel(
            parent, "TIMER & STOPPUHR", width=310, default_open=True,
            title_color=COLORS["red"]
        )

        self.timer_lbl = tk.Label(timer_panel.content_frame, text="KEIN TIMER",
                                  font=("Consolas", 12, "bold"),
                                  bg=COLORS["bg_panel"], fg=COLORS["text_dim"])
        self.timer_lbl.pack(pady=2)

        t_row = tk.Frame(timer_panel.content_frame, bg=COLORS["bg_panel"])
        t_row.pack(pady=2)
        for m in [5, 10, 15, 25, 30]:
            b = tk.Button(t_row, text=f"{m}m",
                          font=("Consolas", 9),
                          bg=COLORS["bg_card"], fg=COLORS["red"],
                          relief=tk.FLAT, bd=0, padx=7, pady=3, cursor="hand2",
                          command=lambda mm=m: self._quick_timer(mm))
            b.pack(side=tk.LEFT, padx=2)

        tk.Label(timer_panel.content_frame, text="STOPPUHR", font=("Consolas", 9, "bold"),
                 bg=COLORS["bg_panel"], fg=COLORS["text_dim"]).pack(pady=(8, 0))

        self.sw_lbl = tk.Label(timer_panel.content_frame, text="00:00:00",
                               font=("Consolas", 18, "bold"),
                               bg=COLORS["bg_panel"], fg=COLORS["text_dim"])
        self.sw_lbl.pack()

        sw_row = tk.Frame(timer_panel.content_frame, bg=COLORS["bg_panel"])
        sw_row.pack(pady=2)
        tk.Button(sw_row, text="▶ START", font=("Consolas", 9),
                  bg=COLORS["bg_card"], fg=COLORS["green"],
                  relief=tk.FLAT, bd=0, padx=8, pady=3, cursor="hand2",
                  command=self._sw_start).pack(side=tk.LEFT, padx=3)
        tk.Button(sw_row, text="■ STOP", font=("Consolas", 9),
                  bg=COLORS["bg_card"], fg=COLORS["red"],
                  relief=tk.FLAT, bd=0, padx=8, pady=3, cursor="hand2",
                  command=self._sw_stop).pack(side=tk.LEFT, padx=3)

        # ── APP-SUCHE (zugeklappt) ──────────────────────────────────────
        app_panel = CollapsiblePanel(
            parent, "APP SUCHE", width=310, default_open=False,
            title_color=COLORS["purple"]
        )

        app_sv = tk.StringVar()
        app_entry = tk.Entry(app_panel.content_frame, textvariable=app_sv, font=("Consolas", 9),
                             bg=COLORS["bg"], fg=COLORS["text_bright"],
                             insertbackground=COLORS["accent"],
                             relief=tk.FLAT, highlightthickness=1,
                             highlightcolor=COLORS["purple"],
                             highlightbackground=COLORS["border"])
        app_entry.pack(fill=tk.X, padx=8, pady=2)

        app_row = tk.Frame(app_panel.content_frame, bg=COLORS["bg_panel"])
        app_row.pack(pady=2)
        tk.Button(app_row, text="▶ Öffnen", font=("Consolas", 9),
                  bg=COLORS["bg_card"], fg=COLORS["green"],
                  relief=tk.FLAT, bd=0, padx=8, pady=3, cursor="hand2",
                  command=lambda: self.send_message(f"öffne {app_sv.get()}") if app_sv.get() else None
                  ).pack(side=tk.LEFT, padx=3)
        tk.Button(app_row, text="■ Schließen", font=("Consolas", 9),
                  bg=COLORS["bg_card"], fg=COLORS["red"],
                  relief=tk.FLAT, bd=0, padx=8, pady=3, cursor="hand2",
                  command=lambda: self.send_message(f"schließe {app_sv.get()}") if app_sv.get() else None
                  ).pack(side=tk.LEFT, padx=3)

        # ── OLLAMA AI (zugeklappt) ──────────────────────────────────────
        ollama_panel = CollapsiblePanel(
            parent, "LOKALE LLMs", width=310, default_open=False,
            title_color=COLORS["accent_light"]
        )

        self.ollama_status_lbl = tk.Label(
            ollama_panel.content_frame,
            text="🧠 Lokale LLMs bereit" if (self.ollama_engine and self.ollama_engine.is_available()) else "❌ Lokale LLMs nicht verfügbar",
            font=("Consolas", 8),
            wraplength=280,
            bg=COLORS["bg_panel"],
            fg=COLORS["green"] if (self.ollama_engine and self.ollama_engine.is_available()) else COLORS["red"],
            justify=tk.LEFT
        )
        self.ollama_status_lbl.pack(pady=2, padx=4, fill=tk.X)

        ollama_quick = tk.Frame(ollama_panel.content_frame, bg=COLORS["bg_panel"])
        ollama_quick.pack(fill=tk.X, padx=8, pady=2)

        tk.Button(ollama_quick, text="🧠 Status", font=("Consolas", 8),
                  bg=COLORS["bg_card"], fg=COLORS["accent_light"],
                  relief=tk.FLAT, bd=0, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.send_message("ollama status")
                  ).pack(side=tk.LEFT, padx=2)
        tk.Button(ollama_quick, text="🗑 Clear", font=("Consolas", 8),
                  bg=COLORS["bg_card"], fg=COLORS["amber"],
                  relief=tk.FLAT, bd=0, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.send_message("vergiss historie")
                  ).pack(side=tk.LEFT, padx=2)
        tk.Button(ollama_quick, text="🔕 Aus", font=("Consolas", 8),
                  bg=COLORS["bg_card"], fg=COLORS["text_dim"],
                  relief=tk.FLAT, bd=0, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.send_message("ollama aus")
                  ).pack(side=tk.LEFT, padx=2)
        tk.Button(ollama_quick, text="🔔 An", font=("Consolas", 8),
                  bg=COLORS["bg_card"], fg=COLORS["green"],
                  relief=tk.FLAT, bd=0, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.send_message("ollama an")
                  ).pack(side=tk.LEFT, padx=2)

        # ── SMART LEARNING (zugeklappt) ─────────────────────────────────
        smart_panel = CollapsiblePanel(
            parent, "SMART LEARNING", width=310, default_open=False,
            title_color=COLORS["purple"]
        )

        self.suggestion_lbl = tk.Label(
            smart_panel.content_frame,
            text="Keine aktiven Vorschläge",
            font=("Consolas", 9),
            wraplength=280,
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
            justify=tk.LEFT
        )
        self.suggestion_lbl.pack(pady=2, padx=4, fill=tk.X)

        self.suggestion_btn_frame = tk.Frame(smart_panel.content_frame, bg=COLORS["bg_panel"])
        self.suggestion_btn_frame.pack(pady=2)

        self.yes_btn = tk.Button(
            self.suggestion_btn_frame,
            text="✓ JA",
            font=("Consolas", 9, "bold"),
            bg=COLORS["green"], fg=COLORS["bg"],
            relief=tk.FLAT, bd=0, padx=12, pady=4, cursor="hand2",
            command=lambda: self._handle_suggestion_response("ja")
        )
        self.yes_btn.pack(side=tk.LEFT, padx=2)

        self.no_btn = tk.Button(
            self.suggestion_btn_frame,
            text="✗ NEIN",
            font=("Consolas", 9, "bold"),
            bg=COLORS["red"], fg=COLORS["bg"],
            relief=tk.FLAT, bd=0, padx=12, pady=4, cursor="hand2",
            command=lambda: self._handle_suggestion_response("nein")
        )
        self.no_btn.pack(side=tk.LEFT, padx=2)

        sl_quick = tk.Frame(smart_panel.content_frame, bg=COLORS["bg_panel"])
        sl_quick.pack(fill=tk.X, padx=8, pady=2)

        tk.Button(sl_quick, text="📊 Stats", font=("Consolas", 8),
                  bg=COLORS["bg_card"], fg=COLORS["purple"],
                  relief=tk.FLAT, bd=0, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.send_message("zeig meine gewohnheiten")
                  ).pack(side=tk.LEFT, padx=2)
        tk.Button(sl_quick, text="🗑 Reset", font=("Consolas", 8),
                  bg=COLORS["bg_card"], fg=COLORS["red"],
                  relief=tk.FLAT, bd=0, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.send_message("vergiss alles")
                  ).pack(side=tk.LEFT, padx=2)
        tk.Button(sl_quick, text="🔕 Aus", font=("Consolas", 8),
                  bg=COLORS["bg_card"], fg=COLORS["text_dim"],
                  relief=tk.FLAT, bd=0, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.send_message("vorschläge aus")
                  ).pack(side=tk.LEFT, padx=2)
        tk.Button(sl_quick, text="🔔 An", font=("Consolas", 8),
                  bg=COLORS["bg_card"], fg=COLORS["green"],
                  relief=tk.FLAT, bd=0, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.send_message("vorschläge an")
                  ).pack(side=tk.LEFT, padx=2)

        # ── BEFEHLSHISTORIE (zugeklappt) ────────────────────────────────
        hist_panel = CollapsiblePanel(
            parent, "BEFEHLSHISTORIE", width=310, default_open=False,
            title_color=COLORS["text_dim"]
        )

        self.history_box = tk.scrolledtext.ScrolledText(
            hist_panel.content_frame, wrap=tk.WORD, font=("Consolas", 8),
            bg=COLORS["bg"], fg=COLORS["text_mid"],
            relief=tk.FLAT, padx=6, pady=4, height=6,
        )
        self.history_box.pack(fill=tk.X, padx=8, pady=2)
        self.history_box.config(state=tk.DISABLED)

        # ── VOICE LOG (zugeklappt) ────────────────────────────────────
        log_panel = CollapsiblePanel(
            parent, "VOICE LOG", width=310, default_open=False,
            title_color=COLORS["text_dim"]
        )

        self.log_box = tk.scrolledtext.ScrolledText(
            log_panel.content_frame, wrap=tk.WORD, font=("Consolas", 8),
            bg=COLORS["bg"], fg=COLORS["text_mid"],
            relief=tk.FLAT, padx=6, pady=4, height=8,
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2, 4))
        self.log_box.config(state=tk.DISABLED)

        for tag, col in [
            ("listen",     COLORS["text_dim"]),
            ("recognized", COLORS["green"]),
            ("wake",       COLORS["amber"]),
            ("command",    COLORS["accent_light"]),
            ("error",      COLORS["red"]),
            ("timer",      COLORS["red"]),
            ("info",       COLORS["text_mid"]),
            ("standby",    COLORS["text_dim"]),
        ]:
            self.log_box.tag_config(tag, foreground=col)

        # ── AUDIO (zugeklappt) ────────────────────────────────────────
        audio_panel = CollapsiblePanel(
            parent, "AUDIO", width=310, default_open=False,
            title_color=COLORS["green"]
        )

        self.audio_cv = tk.Canvas(audio_panel.content_frame, bg=COLORS["bg"], height=14,
                                  highlightthickness=0)
        self.audio_cv.pack(fill=tk.X, padx=10, pady=(2, 8))
        self.audio_bar = self.audio_cv.create_rectangle(
            0, 2, 0, 12, fill=COLORS["green"], outline=""
        )
        self._upd_audio()

        # TTS Info (immer sichtbar, ganz unten)
        tts_col  = COLORS["green"] if (GTTS_OK and PLAYSOUND_OK) else COLORS["amber"]
        tts_text = "🔊 gTTS + playsound" if (GTTS_OK and PLAYSOUND_OK) else "🔊 pyttsx3 (offline)" if PYTTSX3_OK else "🔊 System-Fallback"
        tk.Label(parent, text=tts_text, font=("Consolas", 7),
                 bg=COLORS["bg_panel"], fg=tts_col).pack(pady=2)

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=COLORS["bg_panel"], height=26)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)
        tk.Frame(bar, bg=COLORS["accent_dark"], height=1).pack(fill=tk.X, side=tk.TOP)

        tts_engine = self.tts.engine_name if hasattr(self, 'tts') else "?"
        app_count  = len(APP_ENGINE._cache)
        ollama_status = "🧠 Lokale LLMs" if (self.ollama_engine and self.ollama_engine.is_available()) else "🧠 Ollama❌"
        self.status_lbl = tk.Label(
            bar,
            text=f"  NOMINAL  │  WAKE: AERA  │  TTS: {tts_engine}  │  APPS: {app_count} gecacht  │  {ollama_status}  │  v10.2",
            font=("Consolas", 8), bg=COLORS["bg_panel"], fg=COLORS["text_dim"])
        self.status_lbl.pack(side=tk.LEFT, padx=16)

        plat = f"{'Windows' if IS_WINDOWS else 'macOS'} │ Python {sys.version[:6]}"
        tk.Label(bar, text=plat, font=("Consolas", 8),
                 bg=COLORS["bg_panel"], fg=COLORS["text_dim"]).pack(side=tk.RIGHT, padx=16)

    def _draw_ring_base(self):
        c = self.ring_canvas
        cx, cy, r = 90, 90, 78
        for ri in [78, 55, 32]:
            c.create_oval(cx - ri, cy - ri, cx + ri, cy + ri,
                          outline=COLORS["border"], width=1)
        c.create_oval(cx - 5, cy - 5, cx + 5, cy + 5,
                      fill=COLORS["accent"], outline="")
        self._ring_arc  = c.create_arc(cx - r, cy - r, cx + r, cy + r,
                                        start=90, extent=0,
                                        outline=COLORS["accent"], width=4, style="arc")
        self._ring_glow = c.create_arc(cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4,
                                        start=90, extent=0,
                                        outline=COLORS["glow"], width=2, style="arc")

    def _animate_ring(self):
        self._pulse_angle = (self._pulse_angle + 4) % 360
        c = self.ring_canvas

        if self._ring_state == "standby":
            extent = int(60 + 30 * math.sin(math.radians(self._pulse_angle)))
            color  = COLORS["text_dim"];  color2 = COLORS["border"]
            text   = "STANDBY";           t_col  = COLORS["text_dim"]
        elif self._ring_state == "listening":
            extent = int(180 + 60 * math.sin(math.radians(self._pulse_angle * 2)))
            color  = COLORS["green"];     color2 = "#1A3A1A"
            text   = "HÖRE ZU";           t_col  = COLORS["green"]
        elif self._ring_state == "working":
            extent = int(self._pulse_angle % 360)
            color  = COLORS["accent"];    color2 = COLORS["glow"]
            text   = "ARBEITE";           t_col  = COLORS["accent_light"]
        else:
            extent = 360
            color  = COLORS["purple"];    color2 = "#2A1A4A"
            text   = "BEREIT";            t_col  = COLORS["purple"]

        start = (90 - self._pulse_angle) % 360
        c.itemconfig(self._ring_arc,  outline=color,  extent=extent, start=start)
        c.itemconfig(self._ring_glow, outline=color2, extent=extent, start=start)
        self.ring_lbl.config(text=text, fg=t_col)
        self.root.after(40, self._animate_ring)

    def _make_btn(self, parent, text, cmd, fg_color):
        return tk.Button(parent, text=text, font=("Consolas", 9),
                         bg=COLORS["bg_card"], fg=fg_color,
                         activebackground=COLORS["glow"],
                         activeforeground=COLORS["text_bright"],
                         relief=tk.FLAT, bd=0, padx=10, pady=6,
                         cursor="hand2", command=cmd)

    def _insert(self, text: str, tag: str = "sys"):
        self.chat.config(state=tk.NORMAL)
        self.chat.insert(tk.END, text + "\n", tag)
        self.chat.see(tk.END)
        self.chat.config(state=tk.DISABLED)

    def _set_status(self, text: str):
        self.status_lbl.config(text=f"● {text}")
        self.root.update_idletasks()

    def _voice_log(self, msg: str, lvl: str = "info"):
        self.root.after(0, lambda: self._do_log(msg, lvl))

    def _do_log(self, msg: str, lvl: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.config(state=tk.NORMAL)
        self.log_box.insert(tk.END, f"[{ts}] {msg}\n", lvl)
        self.log_box.see(tk.END)
        self.log_box.config(state=tk.DISABLED)
        lines = int(self.log_box.index("end-1c").split(".")[0])
        if lines > 300:
            self.log_box.delete("1.0", "31.0")

    def _update_history(self):
        self.history_box.config(state=tk.NORMAL)
        self.history_box.delete("1.0", tk.END)
        for item in HISTORY.get_recent(8):
            icon = "▸" if item["type"] == "command" else "⏱"
            self.history_box.insert(tk.END,
                f"{item['time']} {icon} {item['text'][:40]}\n", "info")
        self.history_box.config(state=tk.DISABLED)

    def _boot(self):
        tts_engine = self.tts.engine_name if hasattr(self, 'tts') else "?"
        app_count  = len(APP_ENGINE._cache)
        lines = [
            ("╔══════════════════════════════════════════════════════════════╗", "sys"),
            ("║  A.E.R.A v10.4 — qwen TOOL-AUSFÜHRUNG + SMART LEARNING GUARD    ║", "sys"),
            ("║  Unbekannte Befehle → automatisch an qwen3:8b via Ollama!    ║", "sys"),
            ("╚══════════════════════════════════════════════════════════════╝", "sys"),
            ("", "sys"),
            ("══ LOKALE LLMs ════════════════════════════════════════", "accent_light"),
            ("   Unbekannte Befehle → automatisch an lokale LLMs", "accent_light"),
            ("   Token-Limit: 500 max │ Konversationshistorie: 10", "accent_light"),
            ("   Befehle: 'lokale status' │ 'vergiss historie' │ 'token limit 300'", "accent_light"),
            ("   Host: localhost:11434 │ Modell: Lokales LLM", "accent_light"),
            ("", "sys"),
            ("══ SMART LEARNING v2 ════════════════════════════════════════", "app"),
            ("  Kontext-Sequenzen: Erkennt 'Outlook nach Teams'", "app"),
            ("  Vorhersage nach Aktionen: Nach Teams → Outlook vorschlagen", "app"),
            ("  Zeit + Kontext kombiniert für bessere Vorschläge", "app"),
            ("  Gewohnheiten: Zeitmuster, Toleranz ±15 Min", "app"),
            ("  JSON-Persistenz: ~/.aera_learning.json + ~/.aera_context.json", "app"),
            ("══ UNIVERSAL APP ENGINE v10.2 ═══════════════════════════════", "app"),
            ("  Öffnen: öffne Spotify / öffne Visual Studio Code", "app"),
            ("  Schließen: schließe Chrome / beende Spotify", "app"),
            ("  Fuzzy-Matching: 'spotfy' findet Spotify", "app"),
            ("  App-Liste: installierte apps  |  Refresh: apps aktualisieren", "app"),
            (f"  App-Cache: {app_count} Apps geladen (wird im Hintergrund aktualisiert)", "app"),
            ("", "sys"),
            ("══ NEUE TOOLS v10.2 ═══════════════════════════════════════", "short"),
            ("  NATURAL TTS: Variierende, menschliche Antworten", "short"),
            ("  'WhatsApp ist bereit für dich.' statt technischer Pfade", "short"),
            ("  CPU/RAM-Auslastung  │  Top-Prozesse  │  Netzwerk-Traffic", "short"),
            ("  UUID  │  Base64  │  JSON-Format  │  HEX/RGB-Konverter", "short"),
            ("  Einheiten umrechnen  │  Datei-Info  │  Leere Ordner", "short"),
            ("  Offene Ports  │  ARP-Tabelle  │  Netzwerk neu starten", "short"),
            ("  Schlafmodus/Hibernate  │  Bildschirmschoner", "short"),
            ("", "sys"),
            ("══ MULTI-COMMAND v10 ═══════════════════════════════════════", "green"),
            ("  Mehrere Befehle gleichzeitig!", "green"),
            ("  'öffne WhatsApp und Chrome'  │  'suche X und öffne Y'", "green"),
            ("  Trennzeichen: und , ; plus", "green"),
            ("", "sys"),
            (f"▸ TTS .......... {tts_engine}", "sys"),
            (f"▸ SR ........... {'✅ aktiv' if VOICE_OK else '❌ fehlt'}", "sys"),
            (f"▸ psutil ....... {'✅ CPU/RAM-Monitoring' if PSUTIL_OK else '❌ pip install psutil'}", "sys"),
            ("", "sys"),
            ("◈ Bereit. Sage 'AERA' + Befehl.", "short"),
            ("", "sys"),
        ]
        for text, tag in lines:
            self._insert(text, tag)
        self._update_soc_btn()
        # NEU v10: Starte Smart Learning Vorschlags-Polling
        self._poll_suggestions()

    def _start_voice(self):
        try:
            self.voice.start()
            self.voice_lbl.config(text="AKTIV", fg=COLORS["green"])
            self._ring_state = "done"
            self._insert("▸ SpeechRecognition aktiv. Sage 'AERA öffne WhatsApp und Excel' oder 'AERA schließe Chrome'.", "short")
        except Exception as e:
            self._insert(f"▸ Sprachfehler: {e}", "error")

    def _on_voice_cmd(self, text: str):
        self.root.after(0, lambda: self._process_voice(text))

    def _process_voice(self, text: str):
        self._ring_state = "working"
        self.voice_lbl.config(text=" VERARBEITE", fg=COLORS["accent_light"])
        self._insert(f" {text}", "voice")
        self.send_message(text)

    def _on_short_cmd(self, response: str, cmd_type: str):
        self.root.after(0, lambda: self._show(f"{response}", "short"))

    def _on_timer(self, minutes: int):
        self.root.after(0, lambda: self._do_timer(minutes))

    def _do_timer(self, minutes: int):
        msg = self.timers.set_timer(minutes)
        self._insert(f"  {msg}", "timer")
        self.tts.speak(f"Timer: {minutes} Minuten.")
        HISTORY.add(f"Timer {minutes} Min.", msg, "timer")
        self._update_history()

    def _mic_press(self, event):
        self.mic_btn.config(bg="#1A0810", fg=COLORS["red"])
        self._ring_state = "listening"
        self._set_status("MANUELLE AUFNAHME...")

    def _mic_release(self, event):
        self.mic_btn.config(bg=COLORS["bg_panel"], fg=COLORS["text_mid"])

        def record():
            text = self.voice.listen_once(timeout=6)
            if text:
                self._voice_log(f"Manuell: '{text}'", "recognized")
                self.root.after(0, lambda: self._process_voice(text))
            else:
                self.root.after(0, lambda: self._set_status("KEIN TEXT ERKANNT"))
                self.root.after(0, lambda: setattr(self, "_ring_state", "done"))

        threading.Thread(target=record, daemon=True).start()

    def _send(self, event=None):
        text = self.input.get().strip()
        if text:
            self.send_message(text)

    def send_message(self, text: str):
        self.input.delete(0, tk.END)
        self._insert(f"▸ {text}", "user")
        self.input.config(state=tk.DISABLED)
        self._ring_state = "working"
        self.voice_lbl.config(text="VERARBEITE", fg=COLORS["accent_light"])
        self._set_status(f"VERARBEITE: {text[:50]}")

        sys_result = self.parser.parse(text)

        # v10: Mehrfachbefehle verarbeiten
        if isinstance(sys_result, list):
            self._process_multi_results(sys_result, text)
            return

        if sys_result:
            # Kalender GUI-Befehl
            if sys_result == "KALENDER_GUI":
                self.root.after(100, lambda: self._open_calendar_gui())
                return
            # Kalender Termin hinzufügen per Voice
            if sys_result == "KALENDER_ADD":
                self.root.after(100, lambda: self._handle_calendar_add(text))
                return
            # Kalender Termine vorlesen per Voice
            if sys_result == "KALENDER_READ":
                self.root.after(100, lambda: self._handle_calendar_read(text))
                return
            HISTORY.add(text, sys_result, "command")
            self._update_history()
            # App-Ergebnisse lila markieren
            tag = "app" if any(x in sys_result.lower() for x in ["geöffnet", "geschlossen", "gestartet", "beendet"]) else "syscmd"
            self.root.after(100, lambda r=sys_result, tg=tag: self._show(f"{r}", tg))
            return

        for pat in [r"timer.*?(\d+)\s*(?:min|minuten?)",
                    r"(\d+)\s*(?:min|minuten?)\s+timer"]:
            m = re.search(pat, text.lower())
            if m:
                self._do_timer(int(m.group(1)))
                self.root.after(0, self._re_enable_input)
                return

        FILE_TRIGGERS = [
            "such", "finde", "suche", "datei", "rechnung", "bericht",
            "dokument", "zeig", "öffne datei", "wo ist", "file",
            "vertrag", "angebot", "protokoll", "lieferschein", "tabelle",
        ]
        if any(x in text.lower() for x in FILE_TRIGGERS):
            m = re.search(
                r"(?:such|finde?|suche?|datei|file|zeig|rechnung|bericht|"
                r"dokument|vertrag|angebot|protokoll|lieferschein|tabelle)\s+"
                r'''["']?([^"']{2,})["']?''',
                text.lower())
            if m:
                query = m.group(1).strip()
            else:
                stop = {
                    "such", "suche", "finde", "datei", "file", "zeig", "mir",
                    "die", "den", "das", "eine", "ein", "bitte", "mal", "öffne",
                    "bericht", "rechnung", "dokument", "wo", "ist", "der",
                }
                words = [w for w in text.lower().split()
                         if w not in stop and len(w) > 2]
                query = " ".join(words)

            if query and len(query) > 1:
                # NEU v10: Lerne Dateisuche für Smart Learning
                if hasattr(self.parser, 'smart_learning') and self.parser.smart_learning:
                    self.parser.smart_learning.record_action("file_open", query)
                def do_file_search(q=query, raw=text):
                    results = DEEP_SEARCH.search_files(q)
                    self.root.after(0, lambda: self._show_file_results(results, q, raw))
                threading.Thread(target=do_file_search, daemon=True).start()
                self._set_status(f"DURCHSUCHE DATEIEN: '{query}'...")
                return

        if CFG.get("socratic_mode", True):
            soc = socratic_engine(text)
            if soc:
                HISTORY.add(text, soc[:80], "search")
                self._update_history()
                self.root.after(100, lambda r=soc: self._show(f"{r}", "ask"))
                return

        # ═════════════════════════════════════════════════════════════════
        #  V10.3 FIX: OLLAMA HAT PRIORITÄT VOR WEB-SUCHE!
        # ═════════════════════════════════════════════════════════════════
        # Wenn lokale LLMs verfügbar sind, IMMER zuerst lokale LLMs fragen.
        # Nur wenn lokale LLMs NICHT laufen → Web-Suche als Fallback.
        if self.ollama_engine and self.ollama_engine.is_available():
            def do_ollama():
                try:
                    self.root.after(0, lambda: self._set_status(f" LOKALES LLM: '{text[:40]}'..."))
                    self.root.after(0, lambda: self._insert("", "sys"))
                    self.root.after(0, lambda: self._insert(" Lokales LLM analysiert...", "sys"))
                    result = self.ollama_engine.ask_with_tools(text)  # NEU v10.4: Tool-Ausführung aktiviert!
                    if result.startswith("AERA:") or result.startswith("Befehl:"):
                        cmd = result.split(":", 1)[1].strip()
                        self.root.after(0, lambda: self._insert(f" Lokales LLM empfiehlt: {cmd}", "app"))
                        self.root.after(100, lambda: self.send_message(cmd))
                        return
                    self.root.after(0, lambda r=result: self._show(r, "search"))
                    HISTORY.add(text, result[:80], "search")
                    self.root.after(0, self._update_history)
                except Exception as e:
                    self.root.after(0, lambda: self._show(f" LLM-Fehler: {e}", "error"))
                    # Fallback zu Web nur bei LLM-Fehler
                    try:
                        result = WEB.answer(text)
                        self.root.after(0, lambda r=result: self._show(r, "search"))
                    except Exception:
                        pass
            threading.Thread(target=do_ollama, daemon=True).start()
            return
        else:
            # Keine lokalen LLMs verfügbar → Web-Suche als Fallback
            def do_search():
                try:
                    result = WEB.answer(text)
                    self.root.after(0, lambda r=result: self._show(r, "search"))
                    HISTORY.add(text, result[:80], "search")
                    self.root.after(0, self._update_history)
                except Exception as e:
                    self.root.after(0, lambda: self._show(f"Fehler — {e}", "error"))
            threading.Thread(target=do_search, daemon=True).start()

    def _process_multi_results(self, results: List[str], original_text: str):
        """
        v10: Verarbeitet mehrere Befehlsergebnisse nacheinander.
        """
        total = len(results)
        self._insert(f"  [{total} Befehle erkannt]", "sys")

        for i, result in enumerate(results, 1):
            tag = "app" if any(x in result.lower() for x in ["geöffnet", "geschlossen", "gestartet", "beendet"]) else "syscmd"
            self._insert(f"  [{i}/{total}] {result}", tag)

            # TTS für jeden Befehl
            clean = self.tts._clean(result)
            if not self.tts.muted:
                self.tts.speak(clean)

            HISTORY.add(original_text, result, "command")

        self._update_history()
        self._ring_state = "done"
        self.voice_lbl.config(text="BEREIT", fg=COLORS["accent_light"])
        self._set_status(f"NOMINAL  │  APPS: {len(APP_ENGINE._cache)} gecacht  │  v10.4 qwen Tool-Ausführung + Smart Guard")
        self._re_enable_input()
    def _show_file_results(self, results: List[Dict], query: str, original_text: str):
        if not results:
            polite = f"Entschuldigung, ich habe keine Datei für '{query}' gefunden. Soll ich eine erweiterte Suche durchführen?"
            self._show(f"{polite}", "syscmd")
            return

        # Höfliche Erfolgsmeldung
        best = results[0]
        score = best["score"]
        name = best["name"]
        path = best["path"]

        if score >= 90:
            match_desc = "sehr hoher Übereinstimmung"
        elif score >= 75:
            match_desc = "hoher Übereinstimmung"
        elif score >= 60:
            match_desc = "guter Übereinstimmung"
        else:
            match_desc = "moderater Übereinstimmung"

        lines = [f"Guten Tag. Ich habe die Datei '{name}' gefunden."]
        lines.append(f"Sie stimmt zu {score}% mit Ihrer Anfrage überein ({match_desc}).")
        lines.append(f"Speicherort: {path}")

        if best.get("snippet"):
            lines.append(f"\nInhaltshinweis: {best['snippet'][:80]}")

        # Weitere Treffer höflich anzeigen
        if len(results) > 1:
            lines.append(f"\nDarüber hinaus habe ich noch {len(results)-1} weitere passende Dateien gefunden:")
            for i, r in enumerate(results[1:4], 2):
                lines.append(f"  {i}. '{r['name']}' — {r['score']}% Übereinstimmung")

        # Datei im Explorer/Finder markieren
        revealed = []
        for r in results[:2]:
            try:
                SystemCommands._reveal_in_file_manager(r["path"])
                revealed.append(f"'{Path(r['path']).name}' ({r['score']}%)")
            except Exception as e:
                revealed.append(f"Fehler: {e}")
        if revealed:
            lines.append("")
            lines.append("▸ Die Dateien wurden im Datei-Manager markiert:")
            for name in revealed:
                lines.append(f"  • {name}")

        result_text = "\n".join(lines)
        HISTORY.add(original_text, result_text[:80], "command")
        self._update_history()
        self._show(result_text, "syscmd")

    def _show(self, text: str, tag: str = "aera"):
        self._ring_state = "done"
        self.voice_lbl.config(text="BEREIT", fg=COLORS["accent_light"])
        self._set_status(f"NOMINAL  │  APPS: {len(APP_ENGINE._cache)} gecacht  │  v10.4 qwen Tool-Ausführung + Smart Guard")
        self._insert("", "sys")
        self._insert(text, tag)
        self._re_enable_input()
        clean = self.tts._clean(text)
        if not self.tts.muted:
            threading.Thread(target=self.tts.speak, args=(clean,), daemon=True).start()

    def _re_enable_input(self):
        self.input.config(state=tk.NORMAL)
        self.input.focus()

    def _timer_done(self, msg: str):
        self.root.after(0, lambda: self._insert(msg, "timer"))

    def _quick_timer(self, m: int):
        self._do_timer(m)

    def _sw_start(self):
        self.timers.start_stopwatch()
        self._stopwatch_on = True
        self.sw_lbl.config(fg=COLORS["green"])
        self._insert("Stoppuhr gestartet.", "short")

    def _sw_stop(self):
        self._stopwatch_on = False
        t = self.timers.get_stopwatch()
        self.sw_lbl.config(fg=COLORS["text_mid"])
        self._insert(f"Stoppuhr gestoppt — {t}", "short")

    def _tick_timers(self):
        active = self.timers.get_active()
        if active:
            texts = [f" {t['name']}: {t['remaining']}" for t in active]
            self.timer_lbl.config(text="\n".join(texts), fg=COLORS["red"])
        else:
            self.timer_lbl.config(text="KEIN TIMER", fg=COLORS["text_dim"])
        if self._stopwatch_on:
            self.sw_lbl.config(text=self.timers.get_stopwatch())
        self.root.after(500, self._tick_timers)

    def _update_clock(self):
        self.clock_lbl.config(text=datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000, self._update_clock)

    def _upd_audio(self):
        level = min(getattr(self.voice, "audio_level", 0) / 3000, 1.0)
        w = self.audio_cv.winfo_width()
        if w > 0:
            bw  = max(int(w * level), 2)
            col = (COLORS["red"] if level > 0.7
                   else COLORS["green"] if level > 0.3
                   else COLORS["text_dim"])
            self.audio_cv.itemconfig(self.audio_bar, fill=col)
            self.audio_cv.coords(self.audio_bar, 0, 2, bw, 12)
        self.root.after(80, self._upd_audio)

    def _toggle_mute(self):
        muted = self.tts.toggle_mute()
        self._insert(f"TTS {'stummgeschaltet' if muted else 'aktiviert'}.", "sys")

    def _clear_chat(self):
        self.chat.config(state=tk.NORMAL)
        self.chat.delete("1.0", tk.END)
        self.chat.config(state=tk.DISABLED)
        self._boot()

    def _show_app_search(self):
        """App-Suche / Browser Fenster."""
        win = tk.Toplevel(self.root)
        win.title("AERA v10 — App Browser")
        win.geometry("800x600")
        win.configure(bg=COLORS["bg"])

        hdr = tk.Frame(win, bg=COLORS["bg_panel"], height=40)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"UNIVERSAL APP BROWSER — {len(APP_ENGINE._cache)} Apps gecacht",
                 font=("Consolas", 12, "bold"),
                 bg=COLORS["bg_panel"], fg=COLORS["purple"]).pack(side=tk.LEFT, padx=20, pady=8)

        btn_row = tk.Frame(win, bg=COLORS["bg_card"])
        btn_row.pack(fill=tk.X, padx=10, pady=4)
        tk.Button(btn_row, text="App-Cache aktualisieren",
                  font=("Consolas", 9), bg=COLORS["bg_card"], fg=COLORS["amber"],
                  relief=tk.FLAT, bd=0, padx=12, pady=4, cursor="hand2",
                  command=lambda: [threading.Thread(target=APP_ENGINE._build_cache, daemon=True).start(),
                                   self._insert("App-Cache wird aktualisiert...", "app")]).pack(side=tk.LEFT, padx=4)

        sf = tk.Frame(win, bg=COLORS["bg_card"])
        sf.pack(fill=tk.X, padx=10, pady=4)
        tk.Label(sf, text="Suche:", font=("Consolas", 10),
                 bg=COLORS["bg_card"], fg=COLORS["text_mid"]).pack(side=tk.LEFT, padx=10)
        sv = tk.StringVar()
        se = tk.Entry(sf, textvariable=sv, font=("Consolas", 10),
                      bg=COLORS["bg"], fg=COLORS["text_bright"],
                      insertbackground=COLORS["purple"], relief=tk.FLAT,
                      highlightthickness=1, highlightcolor=COLORS["purple"],
                      highlightbackground=COLORS["border"])
        se.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=4)
        se.focus()

        btn_row2 = tk.Frame(win, bg=COLORS["bg_card"])
        btn_row2.pack(fill=tk.X, padx=10)

        def do_open():
            q = sv.get().strip()
            if q:
                result = APP_ENGINE.open_app(q)
                self._insert(f"{result}", "app")
                self._show(f"{result}", "app")

        def do_close():
            q = sv.get().strip()
            if q:
                result = APP_ENGINE.close_app(q)
                self._insert(f"{result}", "app")
                self._show(f"{result}", "app")

        tk.Button(btn_row2, text="▶ App öffnen", font=("Consolas", 9),
                  bg=COLORS["bg_card"], fg=COLORS["green"], relief=tk.FLAT, bd=0,
                  padx=10, pady=3, cursor="hand2", command=do_open).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row2, text="■ App schließen", font=("Consolas", 9),
                  bg=COLORS["bg_card"], fg=COLORS["red"], relief=tk.FLAT, bd=0,
                  padx=10, pady=3, cursor="hand2", command=do_close).pack(side=tk.LEFT, padx=4)

        lb = tk.scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Consolas", 9),
                                          bg=COLORS["bg"], fg=COLORS["text_bright"],
                                          relief=tk.FLAT, padx=12, pady=8)
        lb.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        lb.tag_config("name", foreground=COLORS["purple"], font=("Consolas", 9, "bold"))
        lb.tag_config("path", foreground=COLORS["text_dim"], font=("Consolas", 8))

        def populate(query=""):
            lb.config(state=tk.NORMAL)
            lb.delete("1.0", tk.END)
            with APP_ENGINE._lock:
                apps = dict(APP_ENGINE._cache)
            names = sorted(apps.keys())
            if query:
                names = [n for n in names if query.lower() in n.lower()]
            lb.insert(tk.END, f"{len(names)} Apps gefunden\n\n", "name")
            for name in names[:200]:
                lb.insert(tk.END, f"  {name}\n", "name")
                lb.insert(tk.END, f"    {apps[name][:80]}\n", "path")
            lb.config(state=tk.DISABLED)

        populate()
        sv.trace("w", lambda *a: populate(sv.get()))
        se.bind("<Return>", lambda e: do_open())

    def _show_cmds(self):
        win = tk.Toplevel(self.root)
        win.title("AERA v10 — Alle Befehle")
        win.geometry("1050x750")
        win.configure(bg=COLORS["bg"])

        hdr = tk.Frame(win, bg=COLORS["bg_panel"], height=40)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="◈ AERA v10 — 150+ BEFEHLE  [Multi-Command v2]",
                 font=("Consolas", 12, "bold"),
                 bg=COLORS["bg_panel"], fg=COLORS["purple"]).pack(side=tk.LEFT, padx=20, pady=8)

        sf = tk.Frame(win, bg=COLORS["bg_card"])
        sf.pack(fill=tk.X, padx=10, pady=4)
        tk.Label(sf, text="Suche:", font=("Consolas", 10),
                 bg=COLORS["bg_card"], fg=COLORS["text_mid"]).pack(side=tk.LEFT, padx=10)
        sv = tk.StringVar()
        se = tk.Entry(sf, textvariable=sv, font=("Consolas", 10),
                      bg=COLORS["bg"], fg=COLORS["text_bright"],
                      insertbackground=COLORS["accent"], relief=tk.FLAT,
                      highlightthickness=1, highlightcolor=COLORS["accent"],
                      highlightbackground=COLORS["border"])
        se.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=4)

        lb = tk.scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Consolas", 10),
                                          bg=COLORS["bg"], fg=COLORS["text_bright"],
                                          relief=tk.FLAT, padx=12, pady=8)
        lb.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        lb.tag_config("cat",  foreground=COLORS["purple"],       font=("Consolas", 10, "bold"))
        lb.tag_config("item", foreground=COLORS["text_mid"],     font=("Consolas", 9))
        lb.tag_config("ex",   foreground=COLORS["amber"],        font=("Consolas", 9))

        ALL_CMDS = [
            ("MULTI-COMMAND v10", [
                ("Mehrere Apps öffnen",   "öffne WhatsApp und Excel"),
                ("Suchen + Öffnen",       "suche Erdkunde Arbeitsblatt und öffne WhatsApp"),
                ("Mehrere schließen",     "schließe Chrome und Spotify"),
                ("Komplexer Befehl",      "öffne Word, starte Spotify und zeig CPU"),
                ("Trennzeichen",          "und  |  ,  |  ;  |  sowie  |  außerdem  |  dann"),
                ("Beispiel komplex",      "öffne Word, suche Bericht und öffne Outlook"),
            ]),
            ("UNIVERSAL APP ENGINE v10", [
                ("JEDE App öffnen",       "öffne Spotify  |  starte Exel"),
                ("JEDE App schließen",    "schließe Chrome  |  beende Spotify"),
                ("Fuzzy-Matching",        "öffne spotfy → findet Spotify automatisch"),
                ("App-Liste anzeigen",    "installierte apps"),
                ("App-Cache refresh",     "apps aktualisieren"),
                ("Laufende Apps",         "laufende prozesse"),
                ("App-Browser",           "Button ⚙ Apps oben rechts"),
            ]),
            ("LOKALE LLMs", [
                ("Status",                  "Aera, lokale status"),
                ("Aktivieren",              "Aera, lokale an"),
                ("Deaktivieren",            "Aera, lokale aus"),
                ("Historie löschen",      "Aera, vergiss historie"),
                ("Token-Limit setzen",    "Aera, token limit 300"),
                ("Modell wechseln",         "Aera, wechsle modell zu qwen3:8b"),
                ("KI-Frage stellen",      "Aera, was ist die Hauptstadt von Frankreich?"),
                ("KI-Hilfe",              "Aera, erkläre mir Quantencomputing"),
            ]),
            ("NEUE TOOLS v10", [
                ("CPU-Auslastung",        "Aera, cpu"),
                ("RAM-Auslastung",        "Aera, ram"),
                ("Top-Prozesse",          "Aera, top prozesse"),
                ("Netzwerk-Traffic",      "Aera, netzwerk traffic"),
                ("UUID generieren",       "Aera, uuid"),
                ("Großbuchstaben",        "Aera, groß: hallo welt"),
                ("Kleinbuchstaben",       "Aera, klein: HALLO WELT"),
                ("Base64 encode",         "Aera, base64 encode: mein text"),
                ("Base64 decode",         "Aera, base64 decode: bWVpbiB0ZXh0"),
                ("JSON formatieren",      "Aera, json formatieren (aus Clipboard)"),
                ("HEX zu RGB",            "Aera, hex zu rgb: #1E6FD9"),
                ("RGB zu HEX",            "Aera, rgb zu hex: 30 111 217"),
                ("Benutzername",          "Aera, benutzername"),
                ("Hostname",              "Aera, hostname"),
                ("Umgebungsvariablen",    "Aera, umgebungsvariablen"),
                ("Datei-Info",            "Aera, datei info rechnung.pdf"),
                ("Leere Ordner finden",   "Aera, leere ordner"),
                ("In Datei suchen",       "Aera, suche in notiz.txt nach Begriff"),
                ("Offene Ports",          "Aera, offene ports"),
                ("ARP-Tabelle",           "Aera, arp tabelle"),
                ("Netzwerk neu starten",  "Aera, netzwerk neu starten"),
                ("Einheiten umrechnen",   "Aera, umrechnen 5 km in meilen"),
                ("Pomodoro",              "Aera, pomodoro 25"),
                ("Laufwerke anzeigen",    "Aera, partitionen"),
                ("Schlafmodus",           "Aera, schlafmodus"),
                ("Hibernate",             "Aera, ruhezustand"),
                ("Bildschirmschoner",     "Aera, bildschirmschoner"),
            ]),
            ("SYSTEM", [
                ("Herunterfahren",       "Aera, fahr in 10 Minuten runter"),
                ("Neustart",             "Aera, starte neu"),
                ("Akku-Status",          "Aera, wie viel Akku?"),
                ("Screenshot",           "Aera, mach einen Screenshot"),
                ("Festplatten",          "Aera, festplatte"),
                ("IP-Adresse",           "Aera, meine ip"),
                ("Task-Manager",         "Aera, task-manager"),
                ("System-Info",          "Aera, systeminfo"),
            ]),
            ("DATEIEN", [
                ("Datei suchen",          "Aera, suche Rechnung Müller"),
                ("Ordner erstellen",      "Aera, erstelle Ordner Projekte"),
                ("Datei-Hash",            "Aera, hash von rechnung.pdf"),
                ("ZIP erstellen",         "Aera, zip ordner Dokumente"),
                ("Duplikate finden",      "Aera, duplikate"),
                ("Desktop-Backup",        "Aera, backup desktop"),
            ]),
            ("INTERNET", [
                ("Google-Suche",          "Aera, googl Python Tutorial"),
                ("Wetter",                "Aera, Wetter in München"),
                ("Bitcoin-Kurs",          "Aera, Bitcoin"),
                ("YouTube",               "Aera, YouTube Lofi Music"),
                ("Website prüfen",        "Aera, check google.com"),
                ("Internetspeed",         "Aera, internetgeschwindigkeit"),
                ("Öffentliche IP",        "Aera, öffentliche ip"),
            ]),
            ("SECURITY", [
                ("Passwort generieren",   "Aera, passwort generieren 20 zeichen"),
                ("UUID",                  "Aera, uuid"),
                ("Base64 encode",         "Aera, base64 encode: text"),
                ("QR-Code",               "Aera, qr-code für https://..."),
                ("Clipboard als QR",      "Aera, clipboard als qr"),
                ("Datei-Hash MD5",        "Aera, hash von datei.txt"),
                ("Datei-Hash SHA256",     "Aera, sha256 hash von datei.txt"),
            ]),
            ("TOOLS", [
                ("Berechnen",             "Aera, berechne sqrt(144)"),
                ("Einheiten umrechnen",   "Aera, umrechnen 100 km in meilen"),
                ("Währung umrechnen",     "Aera, umrechnen 100 usd in eur"),
                ("Witz",                  "Aera, erzähl einen witz"),
                ("Würfeln",               "Aera, würfeln"),
                ("Münze werfen",          "Aera, münze"),
                ("Motivation",            "Aera, motiviere mich"),
                ("Notiz",                 "Aera, notiz: Wichtiger Termin"),
            ]),
        ]

        def populate(query=""):
            lb.config(state=tk.NORMAL)
            lb.delete("1.0", tk.END)
            for cat, cmds in ALL_CMDS:
                visible = [(n, ex) for n, ex in cmds
                           if not query
                           or query in n.lower() or query in ex.lower()]
                if visible:
                    lb.insert(tk.END, f"\n{cat}\n", "cat")
                    for name, ex in visible:
                        lb.insert(tk.END, f"  ▸ {name:<35}", "item")
                        lb.insert(tk.END, f"  {ex}\n", "ex")
            lb.config(state=tk.DISABLED)

        populate()
        sv.trace("w", lambda *a: populate(sv.get().lower()))

        tk.Label(win,
                 text="v10.2 — Lokale LLMs | Smart Learning v2 | Natural TTS | Multi-Command | 150+ Befehle",
                 font=("Consolas", 9),
                 bg=COLORS["bg_panel"], fg=COLORS["text_dim"]).pack(fill=tk.X, padx=10, pady=4)

    def open_calendar(self):
        """Öffnet den AERA High-End Kalender als GUI-Fenster."""
        if self.calendar_window and hasattr(self.calendar_window, 'win') and self.calendar_window.win.winfo_exists():
            self.calendar_window.win.lift()
            self.calendar_window.win.focus_force()
            return
        self.calendar_window = AERACalendar(
            self.root,
            tts_manager=self.tts,
            on_close=lambda: setattr(self, 'calendar_window', None)
        )
        self.voice_calendar = VoiceCalendarManager(
            lambda: self.calendar_window,
            self.tts
        )

    def _open_calendar_gui(self):
        """Intern: Öffnet Kalender und zeigt Bestätigung."""
        self.open_calendar()
        self._ring_state = "done"
        self.voice_lbl.config(text="BEREIT", fg=COLORS["accent_light"])
        self._set_status(f"NOMINAL  │  APPS: {len(APP_ENGINE._cache)} gecacht  │  v10.4 qwen Tool-Ausführung + Smart Guard")
        self._insert("", "sys")
        self._insert("Kalender geöffnet.", "app")
        self._re_enable_input()
        self.tts.speak("Kalender geöffnet.")


    # ═══════════════════════════════════════════════════════════════════
    #  COMPACT GUI MODE — v10
    # ═══════════════════════════════════════════════════════════════════

    def _open_theme_editor(self):
        """Öffnet den Theme-Editor."""
        editor = ThemeEditor(self.root, on_apply=self._refresh_theme)

    def _refresh_theme(self):
        """Aktualisiert die GUI nach Theme-Änderung."""
        self._insert("▸ Theme aktualisiert. Einige Änderungen erfordern einen Neustart.", "sys")

    def switch_to_compact_gui(self):
        """Wechselt zur kompakten Popup-GUI."""
        if self.compact_gui and self.compact_gui.is_visible():
            return

        self._gui_mode = "compact"

        # Minimiere das Hauptfenster
        self.root.withdraw()

        # Erstelle kompakte GUI
        self.compact_gui = AERACompactGUI(self)
        self.compact_gui.update_from_full()

        # Verbinde Voice-Callbacks mit kompakter GUI
        self._connect_compact_callbacks()

        self._insert("▸ Kompakt-Modus aktiviert. Schwimmendes Fenster ist aktiv.", "sys")

    def switch_to_full_gui(self):
        """Wechselt zurück zur vollen GUI."""
        self._gui_mode = "full"

        # Schließe kompakte GUI
        if self.compact_gui:
            try:
                self.compact_gui.root.destroy()
            except Exception:
                pass
            self.compact_gui = None

        # Zeige Hauptfenster wieder
        self.root.deiconify()
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))

        # Stelle Voice-Callbacks wieder her
        self.voice.on_command = self._on_voice_cmd
        self.voice.on_short = self._on_short_cmd
        self.voice.on_log = self._voice_log
        self.voice.on_timer = self._on_timer

        self._insert("▸ Voll-GUI wiederhergestellt.", "sys")

    def _connect_compact_callbacks(self):
        """Verbindet Callbacks für den Kompakt-Modus."""
        if not self.compact_gui:
            return

        def compact_on_command(text):
            self.root.after(0, lambda: self._compact_process_command(text))

        def compact_on_short(response, cmd_type):
            self.root.after(0, lambda: self._compact_show_short(response))

        def compact_on_log(msg, lvl="info"):
            self.root.after(0, lambda: self._voice_log(msg, lvl))

        def compact_on_timer(minutes):
            self.root.after(0, lambda: self._do_timer(minutes))

        self.voice.on_command = compact_on_command
        self.voice.on_short = compact_on_short
        self.voice.on_log = compact_on_log
        self.voice.on_timer = compact_on_timer

    def _compact_process_command(self, text):
        """Verarbeitet Befehl im Kompakt-Modus."""
        if self.compact_gui:
            self.compact_gui.set_status("working")
            self.compact_gui.set_last_command(text)
        self._process_voice(text)

    def _compact_show_short(self, response):
        """Zeigt Kurzbefehl-Antwort im Kompakt-Modus."""
        if self.compact_gui:
            self.compact_gui.set_last_command(response)
            self.compact_gui.set_status("standby")
        self.tts.speak(response)

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()


    def _handle_calendar_add(self, text: str):
        """Fügt Termin per Voice hinzu."""
        if not self.calendar_window or not self.voice_calendar:
            self.open_calendar()
        if self.voice_calendar:
            result = self.voice_calendar.add_event_voice(text)
            self._ring_state = "done"
            self.voice_lbl.config(text="BEREIT", fg=COLORS["accent_light"])
            self._set_status(f"NOMINAL  │  APPS: {len(APP_ENGINE._cache)} gecacht  │  v10.4 qwen Tool-Ausführung + Smart Guard")
            self._insert("", "sys")
            self._insert(f"{result}", "app")
            self._re_enable_input()

    def _handle_calendar_read(self, text: str):
        """Liest Termine per Voice vor."""
        if not self.calendar_window or not self.voice_calendar:
            self.open_calendar()
        if self.voice_calendar:
            result = self.voice_calendar.read_events_voice(text)
            self._ring_state = "done"
            self.voice_lbl.config(text="BEREIT", fg=COLORS["accent_light"])
            self._set_status(f"NOMINAL  │  APPS: {len(APP_ENGINE._cache)} gecacht  │  v10.4 qwen Tool-Ausführung + Smart Guard")
            self._insert("", "sys")
            self._insert(f"{result}", "app")
            self._re_enable_input()

    def _poll_suggestions(self):
        """Prüft alle 5 Sekunden auf neue Smart Learning Vorschläge."""
        try:
            if hasattr(self, 'smart_learning') and self.smart_learning:
                suggestions = self.smart_learning.get_pending_suggestions()
                for sugg in suggestions:
                    self._show_suggestion(sugg)
        except Exception as e:
            print(f"[SuggestionPoll] {e}")
        self.root.after(5000, self._poll_suggestions)

    def _show_suggestion(self, suggestion):
        """Zeigt einen Vorschlag im GUI an."""
        # Ersetze \n durch echte Zeilenumbrüche für die Anzeige
        display_text = suggestion["full_message"].replace("\\n", "\n")
        self.suggestion_lbl.config(
            text=display_text,
            fg=COLORS["accent_light"]
        )
        # TTS-Ansage
        if self.tts and not self.tts.muted:
            clean = suggestion["suggestion_text"]
            self.tts.speak(clean + " Sage Ja oder Nein.")
        self._insert(f"💡 SMART VORSCHLAG: {suggestion['suggestion_text']}", "ask")

    def _handle_suggestion_response(self, response):
        """Verarbeitet Ja/Nein auf Smart Learning Vorschlag."""
        if hasattr(self, 'smart_learning') and self.smart_learning:
            result = self.smart_learning.handle_user_response(response)
            self._insert(result, "app")
            self.suggestion_lbl.config(
                text="Keine aktiven Vorschläge",
                fg=COLORS["text_dim"]
            )
            # TTS-Feedback
            if self.tts and not self.tts.muted:
                self.tts.speak(result)

    def _on_close(self):
        if hasattr(self, 'smart_learning') and self.smart_learning:
            self.smart_learning.stop()
        # NEU v10.2: Lokale LLM-Historie speichern (optional)
        if hasattr(self, 'ollama_engine') and self.ollama_engine:
            self.ollama_engine.clear_history()
        self.voice.stop()
        self.tts.clear()
        # Schließe auch kompakte GUI
        if self.compact_gui:
            try:
                self.compact_gui.root.destroy()
            except Exception:
                pass
        self.root.destroy()



# ═══════════════════════════════════════════════════════════════════════════════
#  LAUNCH
# ═══════════════════════════════════════════════════════════════════════════════

def print_banner():
    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║   A.E.R.A v10.4 — qwen TOOL-AUSFÜHRUNG + SMART LEARNING GUARD        ║
║                                                                      ║
║   KERN-FEATURE: Lokale LLM AI Integration v10.3                      ║
║   • Unbekannte Befehle → automatisch an lokale LLMs                  ║
║   • FIX: Lokale LLMs haben Priorität vor Web-Suche                   ║
║   • FIX: Smart Learning Ja/Nein nur bei aktivem Vorschlag            ║
║   • FIX: Kein Fragment-Check → allgemeine Fragen gehen an lokale LLMs║
║   • Token-Limit: 500 max (konfigurierbar)                            ║
║   • Konversationshistorie für Kontext                                ║
║                                                                      ║
║   SMART LEARNING v2:                                                 ║
║   Gewohnheiten + Kontext-Sequenzen → Vorschläge → Ausführen bei Ja   ║
║                                                                      ║
║   MULTI-COMMAND v2:                                                  ║
║   Mehrere Befehle gleichzeitig: "öffne X und Y"                      ║
║                                                                      ║
║   NEU v10.2 TOOLS:                                                   ║
║   Lokale LLMs  │  Natural TTS  │  CPU/RAM-Monitor  │  UUID           ║
║   Base64  │  JSON-Format  │  HEX/RGB  │  Einheiten  │  Ports         ║
║   ARP  │  Schlafmodus  │  Hibernate  │  Pomodoro  │  Netzwerk-Reset  ║
╠══════════════════════════════════════════════════════════════════════╣
║  PFLICHT:                                                            ║
║    pip install SpeechRecognition pyaudio                             ║
║    pip install gTTS playsound==1.2.2                                 ║
║    pip install pyttsx3 customtkinter                                 ║
║                                                                      ║
║  EMPFOHLEN:                                                          ║
║    pip install ollama     (Lokale LLM Integration)                   ║
║    pip install psutil     (CPU/RAM/Traffic-Monitor)                  ║
║    pip install thefuzz    (besseres Fuzzy-Matching)                  ║
║    pip install pyperclip  (Clipboard)                                ║
║    pip install qrcode[pil] Pillow opencv-python                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    print_banner()

    missing = []
    if not VOICE_OK:
        missing.append("SpeechRecognition + pyaudio  →  pip install SpeechRecognition pyaudio")
    if not HAS_CTK:
        missing.append("customtkinter  →  pip install customtkinter")
    if not FUZZY_OK:
        missing.append("thefuzz  →  pip install thefuzz python-Levenshtein  (empfohlen für App-Suche)")
    if not GTTS_OK:
        missing.append("gTTS  →  pip install gTTS")
    if not PLAYSOUND_OK:
        missing.append("playsound  →  pip install playsound==1.2.2")
    if not PSUTIL_OK:
        missing.append("psutil  →  pip install psutil  (CPU/RAM/Traffic)")
    if not OLLAMA_OK:
        missing.append("ollama  →  pip install ollama  (Ollama AI Integration)")

    if missing:
        print("FEHLENDE PAKETE:")
        for m in missing:
            print(f"  • {m}")
        print("\nDas Programm startet trotzdem (eingeschränkt).\n")

    # NEU v10: Kompakt-Modus via Kommandozeilenargument
    import argparse
    arg_parser = argparse.ArgumentParser(description="AERA v10")
    arg_parser.add_argument("--compact", action="store_true",
                            help="Starte im Kompakt-Modus (schwebendes Fenster)")
    args = arg_parser.parse_args()

    app = AERA_GUI(start_compact=args.compact)
    app.run()
