import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote, urlsplit

from app.core.users.application.errors import MailDeliveryError


class SmtpPasswordMail:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        starttls: bool,
        public_url: str,
        lifetime_minutes: int,
    ):
        self.host, self.port, self.username, self.password = (
            host,
            port,
            username,
            password,
        )
        self.sender, self.starttls = sender, starttls
        self.public_url, self.lifetime_minutes = (
            public_url.rstrip("/"),
            lifetime_minutes,
        )

    def ensure_configured(self) -> None:
        url = urlsplit(self.public_url)
        if (
            not self.host
            or not self.sender
            or url.scheme not in ("http", "https")
            or not url.netloc
        ):
            raise MailDeliveryError(
                "Der E-Mail-Versand ist noch nicht konfiguriert. Bitte SMTP und die öffentliche Website-URL einrichten."
            )

    def send(self, email: str, token: str) -> None:
        self.ensure_configured()
        message = EmailMessage()
        message["Subject"] = "TTC – Passwort festlegen"
        message["From"], message["To"] = self.sender, email
        # Fragment keeps the secret out of web-server URLs and referrer headers.
        url = f"{self.public_url}/passwort-festlegen#token={quote(token, safe='')}"
        message.set_content(
            f"Für dein TTC-Benutzerkonto wurde ein Passwort-Link angefordert.\n\n"
            f"Öffne diesen Link, um dein Passwort festzulegen:\n{url}\n\n"
            f"Der Link ist {self.lifetime_minutes} Minuten gültig und nur einmal verwendbar.\n"
            "Falls du dies nicht erwartet hast, kontaktiere bitte die Vereinsadministration."
        )
        try:
            with smtplib.SMTP(self.host, self.port, timeout=15) as smtp:
                if self.starttls:
                    smtp.starttls(context=ssl.create_default_context())
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as error:
            raise MailDeliveryError(
                "Die E-Mail konnte nicht versendet werden. Das Konto bleibt erhalten; bitte den Versand erneut auslösen."
            ) from error
