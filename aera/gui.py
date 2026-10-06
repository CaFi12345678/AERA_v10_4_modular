"""AERA calendar, themes and graphical user interfaces."""

from .foundation import *
from .intelligence import *
from .services import *
from .commands import *

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
