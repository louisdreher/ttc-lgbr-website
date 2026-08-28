# myTischtennis-Diagnosewerkzeuge

Diese Werkzeuge greifen auf die echte myTischtennis-API zu. Sie sind keine
automatisierten Tests. Alle Befehle werden aus `backend/` gestartet.

Die verfügbaren Parameter lassen sich anzeigen, ohne eine API-Abfrage zu
starten:

```powershell
conda run -n ttc-backend python -m scripts.mytt.diagnostics.probe_client --help
conda run -n ttc-backend python -m scripts.mytt.diagnostics.probe_registrations --help
conda run -n ttc-backend python -m scripts.mytt.diagnostics.sync_single_meeting --help
```

Antworten der reinen Diagnoseabfragen werden unter `backend/output/mytt_tests`
gespeichert. Dieses Verzeichnis wird nicht von Git versioniert.
