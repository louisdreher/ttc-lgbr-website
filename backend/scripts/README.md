# Backend-Skripte

Die Skripte werden aus dem Verzeichnis `backend/` gestartet.

- `maintenance/`: einmalige oder wiederholbare Wartungs- und Backfill-Aufgaben
- `mytt/run_current_sync.py`: manuell gestartete aktuelle Synchronisierung
- `mytt/diagnostics/`: manuelle Abfragen gegen die echte myTT-API
- `mytt/history/`: historische Importe und zugehörige Prüfungen

Automatisierte Tests liegen ausschließlich unter `backend/tests/` und greifen
nicht auf die echte myTT-API zu.

Mit `--help` zeigt jedes parametrisierte Skript seine Argumente, zum Beispiel:

```powershell
conda run -n ttc-backend python -m scripts.mytt.run_current_sync --help
```

Die Modulschreibweise mit `python -m` ist wichtig: Dadurch bleibt `backend/`
die Python-Importwurzel und die kanonischen `app.*`-Imports funktionieren auch
für tiefer verschachtelte Skripte.

Der Event-Backfill kann wiederholt ausgeführt werden:

```powershell
conda run -n ttc-backend python -m scripts.maintenance.backfill_team_match_events --completed-only
```
