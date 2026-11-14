"""Serveur local de démonstration pour la recherche par adresse."""
import argparse
import json
import re
import sqlite3
import unicodedata
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent


def normalize(value):
    plain = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z]+|\d+", plain))


def load_dataset(path, historical):
    dataset = json.loads(path.read_text(encoding="utf-8"))
    scope = {
        "region": dataset["region"],
        "statut": dataset["statut"],
        "du": dataset.get("du"),
        "au": dataset.get("au"),
        "extraction": dataset.get("date_extraction") or path.stat().st_mtime,
    }
    if not isinstance(scope["extraction"], str):
        scope["extraction"] = date.fromtimestamp(scope["extraction"]).isoformat()
    rows = []
    for row in dataset["annonces"]:
        entry = {
            "numero": row["no_centris"],
            "adresse": row["adresse"],
            "secteur": row["municipalite_arrondissement"],
            "prix": row.get("prix_matrix" if historical else "prix_vente") or "",
            "loyer": row.get("prix_location_matrix" if historical else "prix_location") or "",
        }
        rows.append((normalize(entry["adresse"]), normalize(entry["secteur"]), entry))
    return scope, rows


def lookup(datasets, address, sector):
    key = normalize(address)
    if not re.match(r"^\d+.* [a-z]", key):
        raise ValueError("Entre le numéro civique et le nom de la rue.")
    scope_key = normalize(sector)
    groups = []
    for scope, rows in datasets:
        matches = [
            row for normalized_address, normalized_sector, row in rows
            if normalized_address == key and
            (not scope_key or scope_key in (normalized_sector, normalize(scope["region"])))
        ]
        groups.append(dict(scope, total=len(matches), resultats=matches[:25]))
    return groups


def lookup_feed(database, address, postal, unit):
    if not postal or not re.fullmatch(r"[a-z] \d [a-z] \d [a-z] \d", normalize(postal)):
        raise ValueError("Indiquez le code postal pour identifier la propriété.")
    key = normalize(address)
    if not key or not key[0].isdigit():
        raise ValueError("Indiquez le numéro civique et la rue.")
    matches = []
    with sqlite3.connect(database) as connection:
        rows = connection.execute("""
            WITH current AS (
                SELECT numero, MAX(observe_le) AS observe_le FROM versions GROUP BY numero
            )
            SELECT v.numero, v.observe_le, v.fiche FROM current c
            JOIN versions v USING (numero, observe_le)
            WHERE replace(upper(json_extract(v.fiche, '$.code_postal')), ' ', '') = ?
        """, ("".join(postal.upper().split()),))
        for number, observed, payload in rows:
            record = json.loads(payload)
            street = " ".join(record.get(field, "") for field in ("numero_civique", "rue"))
            if normalize(street) != key or normalize(record.get("appartement", "")) != normalize(unit):
                continue
            history = connection.execute(
                "SELECT observe_le, fiche FROM versions WHERE numero=? ORDER BY observe_le",
                (number,))
            matches.append({
                "numero": number,
                "observe_le": observed,
                "fiche": record,
                "versions": [{"observe_le": t, "fiche": json.loads(p)} for t, p in history],
            })
    return {"source": "Centris", "couverture": "Versions reçues par le flux", "fiches": matches}


def lookup_matrix(database, address, sector):
    key, area = normalize(address), normalize(sector)
    if not key or not key[0].isdigit() or not area:
        raise ValueError("Indiquez l’adresse complète et le secteur.")
    matches = []
    with sqlite3.connect(database) as connection:
        rows = connection.execute("""
            WITH current AS (
                SELECT numero, MAX(observe_le) AS observe_le FROM versions GROUP BY numero
            )
            SELECT v.numero, v.observe_le, v.fiche FROM current c
            JOIN versions v USING (numero, observe_le)
        """)
        for number, observed, payload in rows:
            record = json.loads(payload)
            if normalize(record["adresse"]) != key or normalize(record["secteur"]) != area:
                continue
            history = connection.execute(
                "SELECT observe_le, fiche FROM versions WHERE numero=? ORDER BY observe_le",
                (number,))
            matches.append({"numero": number, "observe_le": observed, "fiche": record,
                            "versions": [{"observe_le": t, "fiche": json.loads(p)} for t, p in history]})
    return {"source": "Matrix Centris", "couverture": "Versions observées dans les lots importés",
            "fiches": matches}


def load_regional_export(path):
    bundle = json.loads(path.read_text(encoding="utf-8"))
    indexed = {}
    coverage = {scope["id"]: scope for scope in bundle["couverture"]}
    for row in bundle["annonces"]:
        indexed.setdefault(normalize(row["adresse"]), []).append(row)
    return indexed, coverage


def lookup_regional(dataset, address, sector):
    key = normalize(address)
    area = normalize(sector)
    index, scope = dataset
    if not key or (not area and not re.match(r"^\d+.* [a-z]", key)):
        raise ValueError("Indiquez le numéro civique et la rue, ou la rue et le secteur.")
    rows = [row for row in index.get(key, [])
            if not area or area in (normalize(row["secteur"]), normalize(row["territoire"]))]
    groups = {}
    for row in rows:
        lot = scope[row["lot"]]
        group = groups.setdefault(row["lot"], {
            "region": lot["territoire"], "statut": lot["filtre"], "du": lot["du"],
            "au": lot["au"], "extraction": lot["date_extraction"], "resultats": []
        })
        group["resultats"].append({
            "numero": row["no_centris"], "adresse": row["adresse"], "secteur": row["secteur"],
            "prix": row["prix_affiche"], "loyer": row["loyer_affiche"], "statut": row["statut"],
            "genre": row["genre"], "terrain": row["terrain_metrique"] or row["terrain_imperial"]
        })
    for group in groups.values():
        group["total"] = len(group["resultats"])
    return {"groupes": list(groups.values()), "partiel": True}


def handler_for(datasets, database=None, matrix_database=None, regional=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format_string, *args):
            # Ne pas journaliser les adresses recherchées.
            pass

        def send_body(self, status, content_type, content):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def send_json(self, status, payload):
            self.send_body(status, "application/json; charset=utf-8",
                           json.dumps(payload, ensure_ascii=False).encode("utf-8"))

        def do_GET(self):
            path = urlsplit(self.path)
            if path.path in ("/", "/index.html"):
                self.send_body(200, "text/html; charset=utf-8", (ROOT / "index.html").read_bytes())
                return
            if path.path != "/api/recherche":
                self.send_json(404, {"erreur": "Page introuvable."})
                return
            params = parse_qs(path.query)
            address = params.get("adresse", [""])[0]
            sector = params.get("secteur", [""])[0]
            if len(address) > 160 or len(sector) > 100:
                self.send_json(400, {"erreur": "L’adresse ou le secteur est trop long."})
                return
            try:
                if regional is not None:
                    self.send_json(200, lookup_regional(regional, address, sector))
                elif matrix_database is not None:
                    self.send_json(200, lookup_matrix(matrix_database, address, sector))
                elif database is not None:
                    postal = params.get("code_postal", [""])[0]
                    unit = params.get("appartement", [""])[0]
                    self.send_json(200, lookup_feed(database, address, postal, unit))
                else:
                    self.send_json(200, {"groupes": lookup(datasets, address, sector)})
            except ValueError as error:
                self.send_json(400, {"erreur": str(error)})
    return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actives", type=Path)
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--base", type=Path)
    sources.add_argument("--matrix", type=Path)
    sources.add_argument("--export-regional", type=Path)
    parser.add_argument("--historique", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    options = parser.parse_args()
    database = options.base or options.matrix
    if not (database or options.export_regional) and not (options.actives and options.historique):
        parser.error("Indiquez --base, --matrix ou les deux exports --actives et --historique.")
    if database and not database.is_file():
        parser.error("Importez d’abord un lot dans la base.")
    regional = load_regional_export(options.export_regional) if options.export_regional else None
    datasets = [] if database or regional else [
        load_dataset(options.actives, False), load_dataset(options.historique, True)]
    with ThreadingHTTPServer(("127.0.0.1", options.port), handler_for(datasets, options.base, options.matrix, regional)) as server:
        print(f"Ouvre http://127.0.0.1:{server.server_port}/", flush=True)
        server.serve_forever()
