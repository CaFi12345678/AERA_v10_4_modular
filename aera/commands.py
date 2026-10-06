"""AERA command processing and voice orchestration."""

from .foundation import *
from .intelligence import *
from .services import *

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
