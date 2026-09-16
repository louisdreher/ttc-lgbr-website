# Spielbericht-Usecases

CreateMatchReportDraft lädt gespeicherte Spieldaten und erstellt einen Klartextentwurf.
Der Generator ist austauschbar. Wiederholte und parallele Aufrufe erzeugen keinen zweiten Bericht.
EditArticleDraft überträgt die Autorenschaft an einen aktiven ADMIN/EDITOR und erhält die Herkunft.
Die Verdrahtung liegt in bootstrap/articles.py. Ereignisverarbeitung und CLI folgen separat.
