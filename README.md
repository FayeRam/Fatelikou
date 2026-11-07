# Fatelikou

Application mobile pour se rappeler de nos défunts et lire pour eux **11 fois la sourate Al-Ikhlass**.

## Ce que fait l'application

| Écran | Contenu |
|---|---|
| **Accueil** | Date du jour, statistiques, liste **« À prier aujourd'hui »** : les défunts pour qui vous n'avez pas lu depuis X jours (réglable), ceux qui n'ont encore aucune lecture, et ceux dont c'est **l'anniversaire du décès**. Bouton pour prier pour tous à la suite. |
| **Mes défunts** | **Arborescence** : Famille › Côté paternel / maternel / Parents & fratrie / Belle-famille, Amis, Voisins, Collègues, Communauté… Vous pouvez créer, renommer et supprimer des groupes et sous-groupes, prier pour tout un groupe, et rechercher un nom. |
| **Fiche** | Prénom, nom, lien, naissance (date + lieu), décès (date + lieu), **âge calculé automatiquement**, notes, historique des lectures. |
| **11 Ikhlass** | Texte de la sourate (translittération + traduction) et un grand **compteur** à toucher après chaque lecture, avec vibration. À 11, la lecture est enregistrée et une invocation s'affiche avec le nom du défunt. |
| **Réglages** | Fréquence des rappels (chaque jour → chaque mois), vibration, **sauvegarde / restauration** (fichier dans *Téléchargements* ou presse-papiers). |

Toutes les données restent sur le téléphone (base SQLite).

## Fichiers

- `main.py` : l'interface (Kivy)
- `db.py` : les données (défunts, groupes, lectures, rappels, sauvegarde) – sans dépendance
- `buildozer.spec` : configuration Android
- `.github/workflows/apk.yml` : compile l'APK automatiquement sur GitHub
- `.github/workflows/publication.yml` : compile la version **Play Store** (.aab signé)
- `icon.png`, `presplash.png` : icône et écran de démarrage
- `docs/confidentialite.html` : politique de confidentialité (mise en ligne via GitHub Pages)
- `playstore/` : bannière, textes de la fiche, réponses aux questionnaires, message aux testeurs

## 1. Tester sur le PC

```bash
pip install kivy plyer
python main.py
```

## 2. Obtenir l'APK Android (le plus simple : GitHub, rien à installer)

1. Créez un compte sur github.com puis un **nouveau dépôt** (ex. `fatelikou`).
2. Cliquez sur **« uploading an existing file »** et glissez **tout le contenu** de ce dossier,
   y compris le dossier `.github` (s'il est caché dans l'explorateur Windows : *Affichage › Éléments masqués*).
   Avec git, c'est plus fiable :
   ```bash
   git init && git add . && git commit -m "Fatelikou"
   git branch -M main
   git remote add origin https://github.com/VOTRE_NOM/fatelikou.git
   git push -u origin main
   ```
3. Onglet **Actions** : la compilation démarre seule (20 à 40 min la première fois).
4. Quand elle est verte, ouvrez-la et téléchargez **Fatelikou-APK** (un .zip contenant l'.apk).
5. Envoyez l'.apk sur le téléphone, ouvrez-le et autorisez « Installer des applications inconnues ».

### Alternative : compiler soi-même (Linux ou WSL sous Windows)

```bash
pip install buildozer "cython==3.0.11"
buildozer android debug        # l'APK sort dans bin/
```

## 3. Publier gratuitement sur le Play Store

> La **clé de signature** (`fatelikou-upload.keystore` + mot de passe) est livrée **à part**,
> dans le dossier `CLE_SECRETE`. Ne la mettez jamais dans le dépôt GitHub.

### Étape A – Mettre le projet sur GitHub (dépôt public)
Comme au point 2. Le dépôt peut être **public** : la clé n'y est pas, elle est rangée dans les
« secrets » de GitHub, invisibles pour tout le monde.

### Étape B – Ajouter les 3 secrets
Dans le dépôt : **Settings › Secrets and variables › Actions › New repository secret**.
Créez `KEYSTORE_BASE64`, `KEYSTORE_PASSWORD` et `KEY_ALIAS` avec les valeurs indiquées dans
`CLE_SECRETE/A_GARDER_SECRET.txt`.

### Étape C – Mettre en ligne la politique de confidentialité
1. Ouvrez `docs/confidentialite.html` et remplacez les 2 `VOTRE_EMAIL` par votre adresse de contact.
2. Sur GitHub : **Settings › Pages › Source : Deploy from a branch › Branch : main / dossier `/docs`** › Save.
3. Après 1 à 2 minutes, la page est en ligne à :
   `https://VOTRE_NOM.github.io/fatelikou/confidentialite.html`

### Étape D – Compiler la version Play Store
**Actions › « Version Play Store (.aab signé) » › Run workflow**. À la fin, téléchargez
**Fatelikou-PlayStore-AAB** : le zip contient le fichier `.aab` à envoyer à Google.

### Étape E – Faire des captures d'écran
Lancez `python main.py` sur le PC (la fenêtre a le format d'un téléphone), ajoutez quelques
défunts d'exemple, puis faites 3 ou 4 captures avec l'Outil Capture de Windows
(`Windows + Maj + S`) : accueil, arbre, fiche, compteur.

### Étape F – Play Console
1. **play.google.com/console** : créez le compte (25 $, une seule fois) et vérifiez votre identité.
2. **Créer une application** : nom `Fatelikou`, langue Français, Application, **Gratuite**.
3. Remplissez la fiche et les questionnaires avec `playstore/FICHE_PLAY_STORE.md`.
4. **Tester › Test fermé › Créer une version** : envoyez le `.aab`. Acceptez la
   « Signature d'application par Google Play » proposée.
5. Ajoutez vos testeurs (adresses Gmail) et envoyez-leur le lien
   (`playstore/MESSAGE_TESTEURS.md`).
6. Après **14 jours avec au moins 12 testeurs inscrits** : **Tableau de bord › Demander l'accès
   à la production**, puis publiez la version en production.

### Mises à jour
Augmentez `version` dans `buildozer.spec` (1.0.0 → 1.0.1), relancez l'étape D et envoyez le
nouveau `.aab`. Google refuse un fichier qui n'a pas un numéro de version plus élevé.

## Limite à connaître

Les rappels s'affichent **dans l'application** (écran d'accueil, mis à jour à chaque ouverture).
L'application n'envoie pas encore de notification quand elle est fermée : sur Android cela demande
un service natif en Java. En attendant, une alarme quotidienne du téléphone nommée « Fatelikou »
fait très bien l'affaire.
