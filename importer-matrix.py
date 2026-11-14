"""Importer et versionner un lot régional Matrix sans identifiants."""
import argparse
import json
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from synchroniser import persist

FIELDS = (
    "statut", "secteur", "adresse", "prix_affiche", "loyer_affiche",
    "genre", "type_batiment", "terrain_imperial", "terrain_metrique",
)


def import_matrix(path, database):
    batch = json.loads(path.read_text(encoding="utf-8"))
    rows = batch["annonces"]
    start, end = (date.fromisoformat(batch[key]) for key in ("du", "au"))
    if (batch["source"] != "Matrix Centris" or start > end
            or type(batch["total"]) is not int or batch["total"] != len(rows)):
        raise ValueError("Lot Matrix incomplet ou période invalide.")
    records = []
    seen = set()
    for row in rows:
        number = row["no_centris"]
        if not re.fullmatch(r"[0-9]{6,9}", number) or number in seen:
            raise ValueError("Numéro Centris en double ou invalide.")
        seen.add(number)
        record = {field: row[field].strip() for field in FIELDS}
        if not all(record[field] for field in ("statut", "secteur", "adresse")):
            raise ValueError(f"Fiche incomplète : {number}.")
        records.append((number, dict(record, region=batch["region"])))
    with sqlite3.connect(database) as connection:
        persist(connection, records, datetime.now(timezone.utc).isoformat())
    return len(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lot", type=Path)
    parser.add_argument("--base", type=Path, required=True)
    args = parser.parse_args()
    print(f"{import_matrix(args.lot, args.base)} fiche(s) traitée(s).")
