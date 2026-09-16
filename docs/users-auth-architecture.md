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
Usecase; `build_ensure_default_roles` verdrahtet ihn. Er wird nicht automatisch
beim Start ausgeführt. Ein Einrichtungsablauf für den ersten Administrator bleibt
geplant. Die später ergänzte Competition-Domain und die verschobenen Members-/Media-
Persistenzmodelle sind in [der Architekturübersicht](architecture.md) beschrieben.
