# Historischer myTischtennis-Import

Die Skripte sollten in folgender Reihenfolge ausgeführt werden:

1. `import_mytt_history_schedules.py`  
   Erstellt Seasons, LeagueGroups, Teams und TeamMatches.

2. `import_mytt_history_registrations.py`  
   Importiert Spieler und Mannschaftsmeldungen.

3. `import_mytt_history_meetings.py`  
   Importiert Begegnungsdetails, Aufstellungen, Matches und Satzergebnisse.

4. `import_mytt_history_league_tables.py`  
   Importiert die historischen Tabellenstände für VR und RR.

Kurz:

`Schedule → Registrations → Meetings → League Tables`