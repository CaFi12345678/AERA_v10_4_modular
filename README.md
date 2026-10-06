# AERA v10.4 — modulare Struktur

Der Originalstand liegt unverändert unter `original/aera_v10_4_monolith.py`.

## Start

```bash
python -m aera.main
python -m aera.main --compact
```

## Module

| Datei | Verantwortung |
|---|---|
| `foundation.py` | Imports, optionale Abhängigkeiten, Konfiguration und Füllwortfilter |
| `intelligence.py` | Smart Learning und lokale Ollama/Qwen-Integration |
| `services.py` | Wake-Word, Datei-/App-Suche, TTS, Timer und Systemwerkzeuge |
| `commands.py` | Command Parser, Voice-Orchestrierung, Websuche und Zustände |
| `gui.py` | Kalender, Themes und Full-/Compact-GUI |
| `main.py` | Kompatibler Programmstart |

Die ursprüngliche Datei bleibt als Referenz erhalten.
