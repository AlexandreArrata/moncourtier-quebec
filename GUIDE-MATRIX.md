# Import des modifications Matrix

Dans Matrix, choisir Recherche → Multicatégories → Générale. Sélectionner la région et les cinq statuts, puis saisir une période dans « Inscriptions modifiées ». Exporter le tableau vers le format JSON du lot fourni et vérifier le total et les numéros distincts avant import.

```sh
python3 importer-matrix.py ../matrix-laval-modifications-2026-11-14.json --base /chemin/prive/matrix.sqlite
```

Utiliser une base distincte de celle du flux SOAP. Le tableau Matrix fournit le montant affiché et le statut. Il ne garantit pas que le prix demandé et le prix conclu soient tous deux disponibles. L’import mémorise une version par changement observé. Une disparition des résultats sur une période ne signifie pas qu’une fiche a été retirée. Une comparaison des statuts et un rapprochement périodique avec un relevé complet sont nécessaires pour vérifier la couverture.

Pour une mise à jour régulière, utiliser des fenêtres de dates qui se chevauchent et importer les lots dans l’ordre de leur extraction. Le collecteur doit utiliser une session Matrix valide. Si Matrix demande de se reconnecter, reprendre après authentification. L’import local ne se connecte pas à Matrix et ne publie pas les données sur GitHub Pages. Le service public devra interroger une base côté serveur et exposer uniquement les champs autorisés.

Pour vérifier la recherche sans ouvrir Matrix de nouveau, lancer
`python3 serveur.py --matrix /chemin/prive/matrix.sqlite`, puis ouvrir
`http://127.0.0.1:8765/`. Saisir l’adresse telle qu’elle figure dans le lot et
le secteur (par exemple Chomedey). Le code postal sert au mode SOAP uniquement.
