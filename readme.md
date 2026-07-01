**Français** &nbsp;|&nbsp; [English](readme.en.md)

# Add-on SoundCloud pour [Kodi](https://github.com/xbmc/xbmc) — fork v5+

<!-- version:auto -->
**Version : 5.9.6020**
<!-- /version:auto -->


<img align="right" src="https://github.com/xbmc/xbmc/raw/master/addons/webinterface.default/icon-128.png" alt="Logo Kodi">

[![Tag GitHub (dernière version SemVer)](https://img.shields.io/github/tag/TheWorms/kodi-addon-soundcloud.svg)](https://github.com/TheWorms/kodi-addon-soundcloud/releases)
[![Lien vers le forum Kodi](https://img.shields.io/badge/Kodi-Forum-informational.svg)](https://forum.kodi.tv/showthread.php?tid=206635)
[![Lien vers le wiki Kodi](https://img.shields.io/badge/Kodi-Wiki-informational.svg)](https://kodi.wiki/view/Add-on:SoundCloud)
[![Lien vers les versions Kodi](https://img.shields.io/badge/Kodi-v21%20%22Omega%22-green.svg)](https://kodi.wiki/view/Releases)

> 🍴 **Ceci est un fork communautaire** de
> [jaylinski/kodi-addon-soundcloud](https://github.com/jaylinski/kodi-addon-soundcloud)
> maintenu sur
> [github.com/TheWorms/kodi-addon-soundcloud](https://github.com/TheWorms/kodi-addon-soundcloud).
> Il ajoute une interface plein écran « à la app », l'authentification
> par jeton OAuth, une traduction française, des widgets skin pour
> l'écran d'accueil et des superpositions « en lecture » plein écran
> par-dessus l'addon d'origine. Les rapports de bug et pull requests
> pour les fonctionnalités v5+ doivent aller sur **ce** fork ; pour le
> menu plugin classique (v4 et antérieures), référez-vous au projet
> d'origine.

Cet add-on [Kodi](https://github.com/xbmc/xbmc) propose une interface
moderne et plein écran pour SoundCloud, avec une barre latérale, des
rangées de carrousel horizontales sur la page d'accueil, la lecture
automatique, un mini-lecteur intégré et quatre styles optionnels de
superposition « en lecture » plein écran (Cinéma, Vagues, Éditorial,
Vinyle).

## Nouveautés en v5

La version v5 a introduit une **toute nouvelle interface plein écran**
qui remplace le menu plugin classique par une expérience « à la app » :

* **Navigation par barre latérale** — Accueil, Recherche, J'aime, Mes
  playlists, Abonnements, Paramètres
* **Page d'accueil avec jusqu'à 4 rangées horizontales** (ordre et
  contenu configurables) : J'aime, Tendances, Mes playlists, Abonnements
* **Mini-lecteur** en bas avec pochette, titre, artiste, temps et une
  barre de progression orange SoundCloud — avec contrôles
  play/pause/suivant/précédent optionnels
* **Lecture automatique du morceau suivant** : un clic sur un morceau
  met tous les morceaux visibles en file d'attente pour que Kodi les
  joue en séquence automatiquement
* **Pagination** : les pages affichent un élément « Page suivante » à
  la fin quand il y a plus de résultats
* **La sélection suit le morceau en cours** pendant la lecture
  automatique
* **Configurable partout** — interrupteurs dans les Paramètres
  (mise en page, mode mini-lecteur, lecture auto, lecture aléatoire,
  contenu des rangées)
* **Superpositions plein écran « En lecture »** : choisissez
  parmi 4 styles visuels — *Cinéma* (Ken Burns à la Apple Music),
  *Vagues* (visualiseur audio animé), *Éditorial* (mise en page
  magazine avec citation extraite de la description du morceau),
  *Vinyle* (disque tournant avec pochette au centre). Désactivable
* **Détection du type d'abonnement** — l'addon lit votre
  abonnement consumer depuis `/me` et le mémorise (Free / Go / Go+)
  pour que les futures fonctionnalités puissent s'y adapter.
* **Navigation au clavier dans le plein écran « En lecture »**
  (v5.9.6008+) — Gauche/Droite avance/recule de 10 s, Haut passe au
  morceau suivant, Bas redémarre le morceau actuel (ou saute au
  précédent si on est dans les 3 premières secondes), OK met en
  pause / reprend.
* **Page d'aide pour récupérer le jeton en un clic** — une
  page web compagnon sur
  [theworms.github.io/kodi-addon-soundcloud](https://theworms.github.io/kodi-addon-soundcloud/)
  avec un snippet console qui récupère votre jeton OAuth SoundCloud en
  un clic — fini la manipulation manuelle F12 / onglet Network.
    entièrement si vous préférez le mini-lecteur uniquement.

Depuis la v5.7, l'interface plein écran est la seule disponible — le
menu plugin classique a été retiré. Les widgets skin pour l'accueil
continuent de fonctionner via les routes dédiées `/widget/*` (voir
« Widgets » plus bas).

## Fonctionnalités

* Recherche
* Découverte de nouvelle musique
* Lecture de morceaux, albums et playlists (compatible compte Free)
* Connexion optionnelle via jeton OAuth pour accéder à vos j'aime,
  playlists, abonnements et reposts
* Interface plein écran avec barre latérale, rangées en carrousel et
  mini-lecteur (v5)
* Superpositions plein écran « En lecture » dans 4 styles (v5.8+)
* Raccourcis clavier dans le plein écran (v5.9.6008+)
* Service optionnel en arrière-plan pour un démarrage instantané
  (v5.9.6017+)

## Installation

**Recommandé — dépôt TheWorms** (mises à jour automatiques).

Télécharge le dépôt en cliquant **[ICI](https://raw.githubusercontent.com/TheWorms/kodi-repo/main/zips/repository.theworms/repository.theworms.zip)**, puis dans Kodi :

1. **Add-ons** → **Installer depuis un fichier zip** → sélectionne le zip téléchargé
   *(si Kodi bloque, active **Sources inconnues** dans Système → Add-ons)*
2. **Installer depuis un dépôt** → **TheWorms Repository** → choisis l'addon
3. Les mises à jour seront ensuite automatiques

**Installation manuelle (alternative) :** télécharge le zip de l'addon depuis la page [Releases](../../releases), puis **Add-ons** → **Installer depuis un fichier zip**.

## Lancer SoundCloud sans le flash du navigateur musique

Quand vous cliquez sur SoundCloud depuis *Musique → Add-ons* dans
Kodi, Kodi affiche brièvement le navigateur musique avant que
l'interface plein écran ne prenne le relais. Il y a trois façons de
gérer ça, de la moins à la plus invasive :

### Option 1 — Service en arrière-plan (v5.9.6017+, recommandée)

L'addon inclut un service optionnel en arrière-plan qui tourne du
démarrage de Kodi jusqu'à son arrêt. Son seul rôle est de pré-créer
l'écran de chargement pour qu'il apparaisse en ~50 ms quand vous
cliquez sur l'addon, masquant entièrement le navigateur musique.

1. *Paramètres → Compte → Service en arrière-plan (ouverture rapide)*
   → activer
2. Redémarrer Kodi (le service ne démarre qu'à l'ouverture de session)
3. Cliquer sur SoundCloud — l'écran de chargement apparaît maintenant
   instantanément, cachant le navigateur musique

Coût : quelques Mo de RAM consommés en continu par le service.
Par défaut : désactivé (opt-in).

### Option 2 — Ajouter un favori Kodi

Cette option contourne entièrement le navigateur musique et donne le
lancement le plus rapide possible.

1. Clic droit (ou menu contextuel) sur SoundCloud dans
   *Musique → Add-ons*
2. Choisir **Ajouter aux favoris** — appelez-le « SoundCloud » ou ce
   que vous voulez
3. Éditer votre fichier de favoris dans
   `~/.kodi/userdata/favourites.xml` et changer la ligne pour
   SoundCloud de
   `ActivateWindow(...)` à
   `RunScript(plugin.audio.soundcloud)`
4. Utiliser le favori depuis l'écran d'accueil de Kodi (ou l'épingler
   dans le menu d'accueil de votre skin)

### Option 3 — Ajouter un raccourci dans le menu d'accueil du skin

Dans Arctic Zephyr Reloaded :
1. *Paramètres → Interface → Skin → Configurer le skin → Personnaliser
   le menu d'accueil*
2. Choisir (ou ajouter) un élément de menu
3. Pour « Activer une fenêtre » ou « Action », utiliser :
   `RunScript(plugin.audio.soundcloud)`

Dans Estuary / Estuary MOD :
1. *Personnaliser le menu d'accueil → choisir un élément → Action*
2. Mettre : `RunScript(plugin.audio.soundcloud)`

Avec ces deux approches, l'interface s'ouvre immédiatement par-dessus
l'écran d'accueil Kodi — pas de flash du navigateur musique, pas de
détour.

## Authentification (optionnelle)

L'add-on peut accéder à vos données SoundCloud personnelles (j'aime,
playlists, abonnements, reposts) en s'authentifiant avec un jeton
OAuth que vous collez dans les paramètres.

Il n'y a pas de bouton « Se connecter » : l'enregistrement à l'API
publique de SoundCloud est fermé depuis 2021, donc on réutilise le
jeton que le site SoundCloud utilise lui-même. Le jeton est stocké
localement dans les paramètres de l'addon Kodi et envoyé uniquement
à `api-v2.soundcloud.com`.

### Comment obtenir votre jeton OAuth

Ouvrez la page d'aide :
**[https://theworms.github.io/kodi-addon-soundcloud/](https://theworms.github.io/kodi-addon-soundcloud/)**

La page vous guide à travers un snippet console en un clic qui
récupère votre jeton depuis soundcloud.com et l'affiche dans une popup
avec un bouton Copier. Le snippet s'exécute entièrement dans votre
navigateur — le jeton ne quitte jamais votre machine.

La page d'aide inclut aussi une procédure manuelle de secours (F12
DevTools, en-tête `Authorization`) pour les rares cas où le snippet ne
fonctionne pas.

Les jetons expirent après quelques mois ou quand vous vous déconnectez
de soundcloud.com — refaites simplement la procédure sur la page
d'aide si nécessaire. L'addon prend en compte les changements de jeton
immédiatement, pas besoin de redémarrer Kodi.

### Free, Go, Go+ — qu'est-ce qui marche ?

Depuis v5.9.6005, l'addon détecte votre niveau d'abonnement SoundCloud
depuis `/me` et le mémorise. Aujourd'hui, les trois niveaux
fonctionnent pour la lecture de vos propres morceaux et des morceaux
marqués comme entièrement lisibles. Les morceaux exclusifs Go+
renvoient un extrait de 30 secondes sur les comptes Free (c'est une
limitation côté serveur SoundCloud, pas une limitation de l'addon).

Vous pouvez voir votre type d'abonnement détecté dans
*Paramètres → Compte → Tester l'authentification*.

### Confidentialité

* Le jeton est stocké **uniquement** sur votre appareil, dans le
  dossier de profil de l'addon Kodi.
* Il est envoyé **uniquement** à `api-v2.soundcloud.com` comme
  en-tête de requête `Authorization`.
* Il est **masqué** dans les journaux de debug (la valeur de
  l'en-tête est remplacée par `<redacted>` dans `kodi.log`).

## Superpositions plein écran « En lecture »

Quand la lecture audio démarre, l'addon peut ouvrir une superposition
plein écran custom par-dessus l'interface d'accueil, affichant la
pochette, le titre, l'artiste et la progression. Choisissez un des
quatre styles visuels dans *Paramètres → Lecture → Plein écran à la
lecture*, ou laissez-le désactivé pour vous contenter du mini-lecteur.

| Style         | Apparence                                                                                                          |
| ------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Désactivé** | Pas de superposition. Le mini-lecteur en bas de l'interface est le seul retour visuel.                            |
| **Cinéma**    | Style Apple Music. Pochette centrée avec zoom Ken Burns lent, fond flouté, grand titre et artiste en-dessous.    |
| **Vagues**    | 90 barres orange en bas, animées en continu pour simuler un visualiseur audio. Vraie barre de progression au-dessus. |
| **Éditorial** | Mise en page magazine. Pochette sur le tiers gauche, grand titre et artiste à droite, avec une citation extraite de la description du morceau (URLs et chaînes de hashtags supprimées, tronquée à une limite de phrase). |
| **Vinyle**    | Un disque vinyle noir détaillé à gauche avec la pochette intégrée dans le centre, les deux tournant ensemble à ~33⅓ tours/min. Titre et artiste à droite. |

### Raccourcis clavier en mode « En lecture » (v5.9.6008+)

Quand une superposition plein écran est visible, les touches suivantes
fonctionnent :

| Touche          | Action                                                              |
| --------------- | ------------------------------------------------------------------- |
| **OK / Entrée** | Mettre en pause / reprendre                                         |
| **Gauche**      | Reculer de 10 secondes                                              |
| **Droite**      | Avancer de 10 secondes                                              |
| **Haut**        | Morceau suivant                                                     |
| **Bas**         | Redémarrer le morceau — ou aller au précédent si on est dans les 3 premières secondes |
| **Retour**      | Fermer la superposition (la lecture continue, la superposition réapparaît au morceau suivant) |

### Limitations honnêtes

* **Vagues n'est en réalité pas audio-réactif.** L'API Python de Kodi
  n'expose pas les échantillons audio aux addons, donc les barres
  sont animées par un motif sinusoïdal pseudo-aléatoire. Ça
  **ressemble** à de l'audio-réactif mais c'est décorrélé de la
  musique réelle. La barre de progression au-dessus du visualiseur
  reflète par contre la vraie position de lecture.
* **La rotation du Vinyle** utilise l'animation de rotation continue
  native de Kodi. C'est fluide sur les boxes modernes mais peut
  saccader sur les appareils plus anciens (Raspberry Pi 3 etc.). Si
  c'est le cas, passez à un autre style.
* **La citation Éditorial** dépend du fait que le morceau SoundCloud
  ait une description. Beaucoup d'uploads d'utilisateurs n'en ont pas,
  auquel cas la zone de citation reste vide (retenue éditoriale
  intentionnelle, pas un bug).
* **Polices personnalisées** : le système WindowXML Python de Kodi ne
  permet pas aux addons d'enregistrer leurs propres polices TTF.
  Toutes les superpositions utilisent donc les noms de polices Kodi
  standard. Le style Éditorial obtient son ambiance par la mise en
  page et la hiérarchie, pas par une police serif embarquée.

## Intégration avec Kodi

Depuis la v5.7, il n'y a plus de menu plugin classique — l'addon
s'ouvre directement dans son interface plein écran « à la app ».

Pour les différentes façons de lancer l'addon (navigateur musique,
raccourci skin, favori Kodi, service en arrière-plan), voir la section
[Lancer SoundCloud sans le flash du navigateur musique](#lancer-soundcloud-sans-le-flash-du-navigateur-musique)
plus haut. Cette section couvre l'intégration sur l'écran d'accueil de
Kodi via les widgets de skin.

### Widgets (menu d'accueil du skin)

Pour les utilisateurs qui veulent du contenu SoundCloud directement
sur leur menu d'accueil Kodi (par exemple, un carrousel « Mes j'aime »
sur Arctic Zephyr Reloaded), l'addon expose des routes de répertoire
plates que le panneau de widgets de n'importe quel skin peut cibler :

| Route | Retourne |
|---|---|
| `plugin://plugin.audio.soundcloud/widget/likes/` | Morceaux que vous avez aimés (nécessite un jeton OAuth) |
| `plugin://plugin.audio.soundcloud/widget/playlists/` | Vos propres playlists (nécessite un jeton OAuth) |
| `plugin://plugin.audio.soundcloud/widget/following/` | Artistes que vous suivez (nécessite un jeton OAuth) |
| `plugin://plugin.audio.soundcloud/widget/trending/` | Tendances mondiales |
| `plugin://plugin.audio.soundcloud/widget/discover/` | Le mix « Discover » de SoundCloud |
| `plugin://plugin.audio.soundcloud/widgets/` | Liste parcourable de tout ce qui précède |

#### Configurer les widgets dans Arctic Zephyr Reloaded

Arctic Zephyr Reloaded ne permet aux widgets de pointer que sur l'URL
racine d'un addon — il ne permet pas de choisir un sous-répertoire
spécifique comme `/widget/likes/`. Pour contourner ça, l'addon a un
paramètre **Mode widget** qui change ce que retourne l'URL racine :

1. Dans Kodi, ouvrez les **Paramètres → Affichage** de SoundCloud,
   descendez en bas et trouvez **Widget d'accueil skin → Mode widget**.
2. Choisissez le contenu que vous voulez que le widget affiche (J'aime
   / Mes playlists / Abonnements / Tendances / Discover).
3. Allez maintenant dans *Paramètres → Interface → Skin → Configurer
   le skin → Personnaliser le menu d'accueil* dans Arctic Zephyr
   Reloaded.
4. Choisissez un élément de menu et cliquez sur **+ Utiliser comme
   widget** sur SoundCloud.
5. Le widget affiche maintenant le contenu que vous avez choisi à
   l'étape 2.

Important : tant que le Mode widget est sur autre chose que « Off »,
ouvrir SoundCloud depuis l'écran Add-ons retournera *aussi* le
contenu choisi au lieu de l'interface plein écran. Pour récupérer
l'interface complète, remettez le Mode widget sur « Off (afficher
l'interface complète) » dans les paramètres de l'addon.

Si vous voulez **plusieurs widgets différents** (par exemple, un pour
J'aime et un pour Tendances), Arctic Zephyr Reloaded seul ne peut pas
le faire car tous les widgets SoundCloud partagent la même URL racine.
Vous avez besoin d'un skin plus avancé qui supporte les chemins de
widget personnalisés (par exemple via Skin Helper Service) pour
pointer chaque widget vers une route `/widget/...` différente.

#### Configurer les widgets dans Estuary / Estuary MOD

Estuary vous permet de naviguer dans les sous-répertoires quand vous
choisissez un widget. Allez dans *Personnaliser le menu d'accueil →
choisir un élément → Ajouter un widget* et naviguez jusqu'à
*Add-ons → Add-ons musique → SoundCloud → Widgets* — choisissez
directement le widget que vous voulez sans avoir besoin du
contournement par Mode widget.

## Crédits

Ce fork v5+ est maintenu par
**[TheWorms](https://github.com/TheWorms)**, qui a contribué
l'interface plein écran, l'intégration du jeton OAuth, les routes de
widget, les quatre styles de superposition « en lecture » plein
écran, la traduction française, l'architecture de service en
arrière-plan, et de nombreuses améliorations UX.

Il est construit sur la base de
[l'add-on Kodi SoundCloud de jaylinski](https://github.com/jaylinski/kodi-addon-soundcloud),
qui était lui-même fortement inspiré par
[l'add-on d'origine](https://github.com/SLiX69/plugin.audio.soundcloud)
développé par [bromix](https://kodi.tv/addon-author/bromix) et
[SLiX](https://github.com/SLiX69).

Toutes les contributions amont et d'origine restent sous licence MIT —
voir `LICENSE.txt` et les dépôts amont pour plus de détails.

## Copyright et licence

Cet add-on est sous licence MIT — voir `LICENSE.txt` pour plus de
détails.
