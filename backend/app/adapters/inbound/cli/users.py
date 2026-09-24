"""Interactive, explicit first administrator setup."""

import argparse
import getpass
import sys
import warnings

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.adapters.outbound.persistence.database import engine
from app.bootstrap.users import build_create_first_admin
from app.core.users.application.dto import CreateUserCommand


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Benutzereinrichtung")
    parser.add_argument("command", choices=["create-admin"])
    parser.parse_args(argv)
    try:
        name = input("Name: ").strip()
        if not name:
            raise ValueError("Name darf nicht leer sein.")
        try:
            email = str(TypeAdapter(EmailStr).validate_python(input("E-Mail: ").strip()))
        except ValidationError:
            raise ValueError("Bitte eine gültige E-Mail-Adresse eingeben.") from None
        # Never fall back to echoed passwords when no terminal is available.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Passwort (12 bis 128 Zeichen): ")
            confirmation = getpass.getpass("Passwort wiederholen: ")
        if password != confirmation:
            raise ValueError("Die Passwörter stimmen nicht überein.")
        with Session(engine) as session:
            build_create_first_admin(session).execute(
                CreateUserCommand(name=name, email=email, password=password)
            )
    except (EOFError, KeyboardInterrupt):
        print("\nEinrichtung abgebrochen.", file=sys.stderr)
        return 1
    except getpass.GetPassWarning:
        print("Ein interaktives Terminal für die verdeckte Passwortabfrage ist erforderlich.", file=sys.stderr)
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("Datenbankfehler. Verbindung und Migrationen prüfen; Einrichtung nicht abgeschlossen.", file=sys.stderr)
        return 1
    print("Administrator wurde angelegt.")
    return 0
