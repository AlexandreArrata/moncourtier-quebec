"""Préparer un courriel avec les PDF approuvés, sans l’envoyer."""
import argparse
import re
from email import policy
from email.headerregistry import Address
from email.message import EmailMessage
from pathlib import Path


def prepare(number, recipient, attachments, destination):
    if not re.fullmatch(r"[0-9]{6,9}", number):
        raise ValueError("Numéro Centris invalide.")
    message = EmailMessage(policy=policy.SMTP)
    address = Address(addr_spec=recipient)
    if not address.username or not address.domain:
        raise ValueError("Adresse du destinataire invalide.")
    message["To"] = str(address)
    message["From"] = "info@alexandrearrata.com"
    message["Subject"] = f"Documents du vendeur — Centris {number}"
    message.set_content(
        f"Bonjour,\n\nVoici les documents demandés pour l’inscription Centris {number}.\n\n"
        "Alexandre Arrata\n"
    )
    seen = set()
    for attachment in attachments:
        if attachment.name.casefold() in seen:
            raise ValueError("Nom de pièce joint en double.")
        data = attachment.read_bytes()
        if attachment.suffix.lower() != ".pdf" or not data.startswith(b"%PDF-"):
            raise ValueError(f"PDF invalide : {attachment.name}")
        message.add_attachment(data, maintype="application", subtype="pdf",
                               filename=attachment.name)
        seen.add(attachment.name.casefold())
    with destination.open("xb") as output:
        output.write(message.as_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("numero")
    parser.add_argument("destinataire")
    parser.add_argument("pdf", nargs="+", type=Path, help="Les PDF que tu as approuvés")
    parser.add_argument("--sortie", required=True, type=Path)
    args = parser.parse_args()
    try:
        prepare(args.numero, args.destinataire, args.pdf, args.sortie)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
