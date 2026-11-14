# Recherche par adresse dans les exports Matrix

Placer `matrix-proprietes-tous-statuts.json` à côté du dossier de ce prototype, puis lancer depuis ce dossier :

```sh
python3 serveur.py --export-regional ../matrix-proprietes-tous-statuts.json
```

Ouvrir http://127.0.0.1:8765/ puis entrer par exemple « 2054 rue Gosselin » et « Chomedey ».

Le secteur ou le territoire est utile pour distinguer les adresses identiques et obligatoire pour une fiche sans numéro civique. Une recherche par adresse et secteur montre les observations trouvées, regroupées par lot, avec les dates et les statuts disponibles. Les montants proviennent du tableau Matrix. Celui-ci ne sépare pas systématiquement prix demandé et prix conclu. Les champs détaillés ou les dates de transaction absents de l’export ne sont pas déduits.

Le prototype écoute en local. Pour mettre la recherche en ligne, héberger le service derrière un accès approprié et configurer le site pour appeler son API. Conserver les exports côté serveur. GitHub Pages héberge l’interface statique. Le CSV de couverture, fourni séparément, indique quels lots sont incomplets.

Chaque résultat propose une demande de documents qui ouvre le logiciel de courriel du visiteur. Le message contient l’adresse et le numéro Centris. Le courtier vérifie les pièces disponibles et décide lesquelles transmettre au demandeur.
