# Recherche et synchronisation MonCourtier Québec

Ce dossier contient un prototype séparé du site public. La recherche locale fonctionne sur les exports Matrix de Laval. Le connecteur Centris reçoit les changements du service officiel et conserve les versions successives des champs pris en charge dans SQLite. Il confirme un lot à Centris après son enregistrement.

## Démonstration locale

Avec les deux exports Matrix dans le dossier parent :

```sh
python3 serveur.py --actives ../matrix-laval-annonces-actives.json --historique ../matrix-laval-vendu-2026-11-08-au-14.json
```

Ouvrir http://127.0.0.1:8765/ puis chercher « 2054, rue Gosselin », secteur Chomedey.

## Flux Centris

1. Valider avec Centris le type d’accès, les champs diffusables et la période d’historique fournie.
2. Si l’accès correspond au service SOAP, renseigner la variable CENTRIS_DIFFUSION_TOKEN dans le gestionnaire de secrets du serveur. Garder le fichier SQLite hors du dépôt et du répertoire web.
3. Exécuter `python3 synchroniser.py --base /chemin/prive/centris.sqlite` avec une tâche planifiée qui interdit les exécutions simultanées et signale les échecs. Utiliser un jeton dédié à cette application.
4. Tester un premier lot avec les données autorisées avant d’ouvrir l’API aux visiteurs.

La synchronisation conserve les changements reçus à partir de son activation. Un historique antérieur exige un lot de départ fourni par Centris. La documentation du service distingue prix demandé, prix vendu et loyer conclu. Le connecteur conserve les indicateurs de diffusion, mais la publication de fiches et de montants historiques exige une politique de diffusion adaptée au contrat. Le prototype ne sert pas la base SQLite sur le web.

Documentation : https://diffusion.centris.ca/

Pour examiner la base du flux localement après le premier import, lancer
`python3 serveur.py --base /chemin/prive/centris.sqlite`. Le formulaire utilise
l’adresse, le code postal et, le cas échéant, le numéro d’appartement. Il affiche
les versions reçues et distingue les montants demandés et conclus. Le serveur
de démonstration écoute uniquement sur la boucle locale. La mise en production
nécessite un serveur, une politique d’accès et de diffusion, et une tâche planifiée.
Ce lot ne comprend pas encore de modèle conversationnel, de connecteur de photos
ou d’import de l’historique antérieur.
