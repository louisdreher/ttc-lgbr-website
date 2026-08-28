# Historischer myTischtennis-Import

Alle Befehle werden aus dem Verzeichnis `backend/` ausgeführt. Sie greifen auf
die konfigurierte Datenbank und die echte myTischtennis-API zu.

Die Importe sollten in folgender Reihenfolge ausgeführt werden:

1. `scripts/mytt/history/import_schedule.py`  
   Erstellt Seasons, LeagueGroups, Teams und TeamMatches.

2. `scripts/mytt/history/import_registrations.py`  
   Importiert Spieler und Mannschaftsmeldungen.

3. `scripts/mytt/history/import_meetings.py`  
   Importiert Begegnungsdetails, Aufstellungen, Matches und Satzergebnisse.

4. `scripts/mytt/history/import_league_tables.py`  
   Importiert die historischen Tabellenstände für VR und RR.

Kurz:

`Schedule → Registrations → Meetings → League Tables`

## Beispiele

```powershell
conda run -n ttc-backend python -m scripts.mytt.history.import_schedule 2018 2019 vr
conda run -n ttc-backend python -m scripts.mytt.history.import_registrations 2009 2012
conda run -n ttc-backend python -m scripts.mytt.history.import_meetings
conda run -n ttc-backend python -m scripts.mytt.history.import_league_tables
```

`import_league_tables.py` überspringt vorhandene Tabellen. Mit
`--include-existing` werden sie erneut von myTT geladen und ersetzt.

Nach dem Registration-Import kann die Datenbank read-only geprüft werden:

```powershell
conda run -n ttc-backend python -m scripts.mytt.history.check_registrations
```
