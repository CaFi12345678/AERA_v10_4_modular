"""AERA intelligence engines."""

from .foundation import *

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


