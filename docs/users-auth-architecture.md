# Users und Auth: Ports und Adapter

Users verwaltet Benutzer und Rollen. Auth verwaltet Anmeldung, Zugriffstokens
und Refresh-Sessions. Beide Komponenten besitzen einen frameworkfreien Core.

## Aufbau

| Ort | Verantwortung |
| --- | --- |
| `app/core/users/domain` | Benutzer, Rollen und Änderungen an Rollenzuordnungen |
| `app/core/users/application` | `CreateUser`, `AddUserRole`, `RemoveUserRole`, Commands, DTOs und Ports |
| `app/core/users/public.py` | Expliziter Vertrag für Auth und Events |
| `app/core/auth/domain` | Refresh-Session und Regeln für ihre Verwendung |
| `app/core/auth/application` | `Login`, `RefreshAccess`, `Logout`, `GetCurrentUser` und Ports |
| `app/adapters/inbound/http/users` und `auth` | FastAPI-Routen, Pydantic-Schemas, Cookies, Fehlerübersetzung und Dependencies |
| `app/adapters/outbound/persistence/users` und `auth` | SQLModel-Tabellen, Repositories, Reader und Unit of Work |
| `app/adapters/outbound/security` | Argon-Passwörter und JWT-/Refresh-Token-Technik |
| `app/bootstrap/users.py` und `auth.py` | Zusammensetzen der konkreten Adapter und Usecases |

Ein Router erhält beispielsweise `Login` über eine HTTP-Dependency und ruft
`execute(LoginCommand(...))` auf. Bootstrap baut die Klasse mit Reader,
Passwortadapter, Tokenadapter, Unit of Work, Uhr und Token-Laufzeit auf.
Die Klasse kennt weder FastAPI noch die Settings noch SQLModel.

`dependencies.py` verbindet FastAPIs Request-Lebenszyklus mit diesen Fabriken.
Bootstrap entscheidet, welche Implementierungen verwendet werden. Es ist keine
weitere fachliche Schicht. Die HTTP-Dependency besitzt und schließt die
Datenbanksession; die Unit of Work steuert Commit und Rollback.

## Komponentenverträge und Transaktionen

Auth liest Benutzer über `users.public.UserReader`. `UserDetails` enthält keine
Passwortdaten; nur der interne Auth-Lesevertrag `UserCredentials` liefert den
Hash für die Passwortprüfung. HTTP-Antworten nutzen ausschließlich sichere
Projektionen. Events bezieht Erstellernamen über denselben öffentlichen Reader.

Schreib-Usecases arbeiten mit Repository-Ports und Domain-Objekten.
Repositories speichern und flushen, führen aber kein Commit aus. Die Unit of
Work ist ein eigener Transaktionsport, keine Überklasse der Repositories.
Die konkreten SQL-Adapter teilen innerhalb eines Requests dieselbe Session.

Beim Refresh werden das verbrauchte Token und sein Nachfolger atomar gespeichert.
Die SQL-Abfrage sperrt die gelesene Session mit `FOR UPDATE`, damit PostgreSQL
gleichzeitige Verwendungen desselben Tokens serialisiert. Bei Wiederverwendung
wird die Token-Familie widerrufen. Dieser Widerruf wird bewusst vor der
Fehlermeldung committed; ein Rollback würde die Sicherheitsmaßnahme aufheben.
Logout widerruft ebenfalls die zugehörige Familie. Gespeichert werden weiterhin
nur Hashes der Refresh-Tokens.

Deaktivierte Benutzer können nun auch beim Refresh keine neuen Tokens erhalten.
Das ergänzt die bereits vorhandenen Prüfungen beim Login und bei geschützten
Requests. Endpunkte, Rollenberechtigungen und Cookie-Konfiguration bleiben gleich.

## Prüfung und offene Arbeit

Die Berichtautomatik ergänzt `User.system_key` als eindeutige Kennzeichnung
einer technischen Identität. Migration `f3b82e0a7c51` erstellt den inaktiven
Systemautor ohne Rollen und ohne gültigen Passwort-Hash. Öffentliche interne
Benutzerprojektionen enthalten `is_system`; HTTP-Antworten bleiben unverändert.
Login, Refresh und Zugriffstoken-Verwendung lehnen Systemidentitäten unabhängig
von `is_active` ab. Der Artikeladapter bezieht die System-ID über den öffentlichen
Users-Reader. Details: [Content-Automation](content-automation.md).

Tests prüfen Domain-Regeln, einen Login mit Test-Ports, Core-Importgrenzen sowie
HTTP-Abläufe mit SQLite: Benutzerverwaltung, Rollen, Login, Cookies, Rotation,
Wiederverwendung, Logout, deaktivierte Benutzer und Transaktions-Rollbacks.
SQLite prüft keine PostgreSQL-Zeilensperren unter parallelen Requests.

Der vollständige OpenAPI-Vertrag und die generierten PostgreSQL-Definitionen
für User, Role, UserRoleLink und RefreshSession wurden vor und nach dem Umbau
verglichen. Die spätere Berichtautomatik ergänzt die oben beschriebene Systemkennung
und wird einschließlich Migration an PostgreSQL geprüft.

`EnsureDefaultRoles` erhält die bisherige idempotente Rollenerstellung als
Usecase; `build_ensure_default_roles` verdrahtet ihn. Der FastAPI-Lifespan in
`app/bootstrap/lifespan.py` führt ihn vor Annahme von Anfragen mit einer eigenen
Datenbanksitzung aus. Fehlende Rollen werden ergänzt; vorhandene Rollen und IDs
bleiben erhalten. PostgreSQL-Inserts verwenden `ON CONFLICT (name) DO NOTHING`,
damit parallele API-Starts keine doppelten Rollen erzeugen. Andere Datenbankfehler
brechen den Start ab. Migrationen müssen weiterhin vorher separat ausgeführt
werden; der Start erstellt weder Tabellen noch Benutzer.
Der erste Administrator wird ausdrücklich über `python -m scripts.users create-admin`
eingerichtet. Der CLI-Adapter validiert die E-Mail und fragt das Passwort verdeckt
mit Bestätigung ab. `CreateFirstAdmin` prüft die Passwortlänge (12 bis 128 Zeichen),
sperrt die ADMIN-Zeile und speichert Konto und Rollenzuordnung in einer Transaktion.
Auch deaktivierte Administratoren verhindern eine erneute Ersteinrichtung;
vorhandene Konten werden weder hochgestuft noch zurückgesetzt. Die Verdrahtung
verwendet den bestehenden Argon2-Adapter. Migrationen und Rollen müssen vorhanden sein.
Die später ergänzte Competition-Domain und die verschobenen Members-/Media-
Persistenzmodelle sind in [der Architekturübersicht](architecture.md) beschrieben.

## Benutzerverwaltung im CMS

`/admin/users` ist ausschließlich für ADMIN zugänglich. Die Übersicht bietet
Suche, Rollen-/Statusfilter, Seiten mit jeweils 25 Konten, eine kompakte Anzeige der vergebenen Rollen,
Passwort-Link-Versand, Aktivierung/Deaktivierung und Löschen.
Rollen werden im Benutzerformular bearbeitet; Konten ohne Rollen zeigen „Keine CMS-Rolle“.
Technische Systemkonten sind aus der Liste ausgeschlossen und vor Änderungen geschützt.
`/admin/users/new` und `/admin/users/:id/edit` verwenden ein gemeinsames Formular
mit Schutz vor dem Verlassen ungespeicherter Änderungen.

Benutzerkonto und Vereinsmitglied bleiben getrennte Datensätze. Das Formular
kann ein neues Mitglied erfassen, ein vorhandenes Mitglied zuordnen oder ein
Konto ohne Mitglied erstellen. Ein Mitglied kann nur einem Konto zugeordnet
werden. Kontostatus und aktive/passive Mitgliedschaft sind unabhängig.
Spielerkennungen und QTTR-Verläufe werden durch dieses Formular nicht verändert.

`SaveManagedUser` speichert Konto, Rollen und Mitgliedsdaten atomar über die
Users-Unit-of-Work. Der öffentliche Vertrag `core/members/public.py` enthält
das frameworkfreie Mitgliedsobjekt und den Mitglieder-Port; der SQL-Adapter
nutzt dieselbe Session. Die neue Members-Domain enthält die Felder des bereits
vorhandenen Persistenzmodells. Eigenständige Mitgliederverwaltung bleibt geplant.
Lese-Usecases verwenden einen separaten Reader mit sicheren Projektionen.

Die Verwaltungs-API liegt unter `/api/admin/users`:

| Methode / Pfad | Funktion |
| --- | --- |
| GET / | Suche, Rollen-/Statusfilter, limit/offset |
| POST / | Konto mit Rollen und optionalem Mitglied anlegen; liefert die ID |
| GET /{id} | Konto einschließlich zugeordnetem Mitglied lesen |
| PUT /{id} | Vollständige Formulardaten speichern |
| PATCH /{id}/active | Zugang aktivieren oder deaktivieren |
| DELETE /{id} | Konto löschen, Mitglied erhalten |
| POST /{id}/password-link | Einladungs-/Passwort-Link per SMTP senden |
| GET /members | Auswahl mit bestehender Kontozuordnung |
| GET /members/{id} | Mitgliedsdaten für das Formular |

Die bestehenden `/api/users`-Endpunkte bleiben kompatibel. Auch die bisherigen
Rollen-Endpunkte erzwingen die neuen Schutzregeln. Alle verwaltenden Änderungen
und das Einlösen von Passwort-Links serialisieren auf der ADMIN-Rollenzeile.
Damit kann der letzte aktive Administrator auch bei konkurrierenden Anfragen
nicht gelöscht, deaktiviert oder seiner Rolle beraubt werden. Dieses bewusst
einfache Sperrkonzept passt zur kleinen Vereinsverwaltung.

Beim Löschen prüft der SQL-Adapter alle registrierten Fremdschlüssel auf die
Benutzertabelle, einschließlich `ON DELETE SET NULL`. Vorhandene Inhaltsbezüge
blockieren das Löschen mit HTTP 409; Deaktivieren bleibt möglich. Rollenlinks,
Passwort-Links und Refresh-Sessions werden zusammen mit dem Konto entfernt.
Mitglied, Spielerdaten und Inhalte bleiben erhalten. Datenbank-Fremdschlüssel
sichern zusätzlich gegen konkurrierende restriktive Referenzen ab.

## Einladungen und Passwort-Links

Neue CMS-Konten haben zunächst einen ungültigen Passwort-Hash (`!`). Das
Frontend sendet bei aktivierter Einladungsoption nach erfolgreichem Speichern
eine separate Versand-Anfrage. Ein SMTP-Fehler wird ausdrücklich gemeldet;
das gespeicherte Konto bleibt erhalten. Der Administrator kann den Versand über
„Passwort zurücksetzen“ erneut auslösen. Es gibt keinen automatischen Versand
beim Start und keinen öffentlichen Endpunkt zum Anfordern von E-Mails.

`SendPasswordLink` erstellt ein zufälliges 256-Bit-Token. Gespeichert wird nur
dessen SHA-256-Hash in `password_link`, mit einem Link pro Konto und standardmäßig
60 Minuten Gültigkeit. Ein erneuter Versand ersetzt den vorherigen Link. Die
Transaktion wird vor SMTP abgeschlossen; ein Versandfehler erfordert einen
expliziten Wiederholungsversuch. Fehlende SMTP-Konfiguration wird vor dem
Erzeugen eines Links geprüft.

Die E-Mail enthält `/passwort-festlegen#token=...`. Das Fragment erreicht weder
den Webserver noch Referrer-Header und wird beim Laden aus der Browseradresse
entfernt. Die öffentliche Seite sendet Token und Passwort an
`POST /api/auth/set-password`. Erfolgreiches Einlösen löscht den Link atomar,
speichert einen Argon2-Hash und widerruft bestehende Refresh-Sessions.
Passwörter müssen 12 bis 128 Zeichen lang sein; der Link ist nur einmal nutzbar.

Migration `d4f26a41b735` ergänzt die Link-Tabelle und `user.auth_invalid_before`.
Access-Tokens enthalten jetzt `iat`; Auth prüft den Ausgabezeitpunkt gegen diesen
Zeitstempel. Alte Tokens werden nach Passwortwechsel, E-Mail-Änderung oder
Deaktivierung sofort abgelehnt, auch nach späterer Reaktivierung. Bestehende
Tokens ohne `iat` bleiben nur für Konten ohne Sperrzeitstempel bis zum Ablauf gültig.
Öffentliche Benutzerantworten enthalten den internen Sperrzeitstempel nicht.

SMTP-Konfiguration und Prüfbefehle stehen im [Entwicklungsleitfaden](development.md).
