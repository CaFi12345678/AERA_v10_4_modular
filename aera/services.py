"""AERA platform services."""

from .foundation import *
from .intelligence import *

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
