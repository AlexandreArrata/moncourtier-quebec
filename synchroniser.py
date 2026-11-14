"""Synchronisation SOAP Centris et conservation des versions reçues."""
import argparse
import hashlib
import json
import os
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
CENTRIS = "http://diffusion.centris.ca/"
ENDPOINT = "https://diffusion.centris.ca/ServiceDiffusion.asmx"
LIMIT = 64 * 1024 * 1024
FIELDS = {
    "CodeStatut": "statut", "GenrePropriete": "genre",
    "PrixDemande": "prix_demande", "PrixLocationDemande": "loyer_demande",
    "PrixVenteOriginal": "prix_initial", "PrixLocationOriginal": "loyer_initial",
    "PrixVendu": "prix_conclu", "PrixLoue": "loyer_conclu",
    "DateVenteLoc": "date_transaction", "AnneeConstruction": "annee_construction",
    "SuperficieTerrain": "superficie_terrain", "UmSuperficieTerrain": "unite_terrain",
    "SuperficieHabitable": "superficie_habitable", "UmSuperficieHabitable": "unite_habitable",
    "EvaluationMunicipaleTotale": "evaluation_municipale", "AnneeEvaluation": "annee_evaluation",
    "TypeBatiment": "type_batiment", "CodePostal": "code_postal",
    "IndInternet": "diffusion_internet", "IndAdresseInternet": "adresse_internet",
}


def call(operation, token):
    envelope = ET.Element(f"{{{SOAP}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP}}}Body")
    action = ET.SubElement(body, f"{{{CENTRIS}}}{operation}")
    ET.SubElement(action, f"{{{CENTRIS}}}Token").text = token
    request = Request(ENDPOINT, data=ET.tostring(envelope, encoding="utf-8"),
                      headers={"Content-Type": "text/xml; charset=utf-8",
                               "SOAPAction": f'"{CENTRIS}{operation}"'})
    with urlopen(request, timeout=60) as response:
        result = response.read(LIMIT + 1)
    if len(result) > LIMIT:
        raise ValueError("Lot Centris trop volumineux.")
    return result


def result_of(xml, operation):
    root = ET.fromstring(xml)
    result = root.find(f"./{{{SOAP}}}Body/{{{CENTRIS}}}{operation}Response/"
                       f"{{{CENTRIS}}}{operation}Result")
    if result is None or result.attrib.get("{http://www.w3.org/2001/XMLSchema-instance}nil") in ("true", "1"):
        raise ValueError("Réponse SOAP Centris non reconnue.")
    return result


def decode(xml):
    result = result_of(xml, "ObtenirInscriptions")
    if any(child.tag != f"{{{CENTRIS}}}InscriptionComplete" for child in result):
        raise ValueError("Le lot contient un type de fiche inconnu.")
    records = []
    for item in result:
        details = item.find(f"{{{CENTRIS}}}Inscriptions")
        address = item.find(f"{{{CENTRIS}}}AdressesProprietes")
        if details is None:
            raise ValueError("Section Inscriptions absente.")
        number = details.findtext(f"{{{CENTRIS}}}NoInscription", "").strip()
        record = {label: value for tag, label in FIELDS.items()
                  if (value := details.findtext(f"{{{CENTRIS}}}{tag}", "").strip())}
        if not number.isdigit() or not record.get("statut"):
            raise ValueError("Numéro ou statut Centris absent.")
        if address is not None:
            for tag, label in (("NoCiviqueDebut", "numero_civique"),
                               ("NoCiviqueFin", "numero_civique_fin"),
                               ("NomRueComplet", "rue"), ("Appartement", "appartement")):
                value = address.findtext(f"{{{CENTRIS}}}{tag}", "").strip()
                if value:
                    record[label] = value
        records.append((number, record))
    return records


def persist(connection, records, timestamp):
    with connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS versions (
            numero TEXT NOT NULL, observe_le TEXT NOT NULL, empreinte TEXT NOT NULL,
            fiche TEXT NOT NULL, PRIMARY KEY (numero, observe_le))""")
        for number, record in records:
            payload = json.dumps(record, ensure_ascii=False, sort_keys=True)
            digest = hashlib.sha256(payload.encode()).hexdigest()
            latest = connection.execute(
                "SELECT empreinte FROM versions WHERE numero=? ORDER BY observe_le DESC LIMIT 1",
                (number,)).fetchone()
            if latest != (digest,):
                connection.execute("INSERT INTO versions VALUES (?, ?, ?, ?)",
                                   (number, timestamp, digest, payload))


def sync(database, token, transport=call):
    operation = "ObtenirInscriptions"
    records = decode(transport(operation, token))
    with sqlite3.connect(database) as connection:
        persist(connection, records, datetime.now(timezone.utc).isoformat())
    if records:
        operation = "ConfirmerSynchronisationInscriptions"
        confirmation = result_of(transport(operation, token), operation)
        if (confirmation.text or "").strip().lower() not in ("true", "1"):
            raise ValueError("Lot enregistré, confirmation Centris non reçue.")
    return len(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("CENTRIS_DIFFUSION_TOKEN")
    if not token:
        parser.exit(2, "CENTRIS_DIFFUSION_TOKEN doit être fourni par le serveur.\n")
    print(f"{sync(args.base, token)} fiche(s) reçue(s).")
