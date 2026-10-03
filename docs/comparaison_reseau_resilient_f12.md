# F12 - Comparaison avec un réseau résilient (Meshtastic)

> Document d'analyse pour le rapport technique / la soutenance. Analyse documentaire et
> architecturale - **aucun matériel Meshtastic n'a été acquis ou testé dans le cadre de ce
> projet** ; toute affirmation ci-dessous sur Meshtastic s'appuie sur sa documentation
> publique, pas sur une mesure réalisée par l'équipe. Ce document complète la section 2.4
> de `docs/analyse_securite_f8.md` (axe sécurité) par un axe résilience/architecture.

## 1. Pourquoi comparer SatRX et Meshtastic

Les deux systèmes répondent au même besoin de fond - faire circuler de l'information sans
dépendre d'une infrastructure télécom classique (opérateur mobile, box internet) - mais
avec des architectures radicalement opposées. La comparaison est pédagogiquement utile
pour le rapport : elle montre que « résilience » n'a pas un sens unique, et que le choix
d'architecture détermine complètement à quel type de panne ou de contrainte un système
résiste.

## 2. Architecture réseau

| | SatRX (réception LRPT/CCSDS) | Meshtastic |
|---|---|---|
| Topologie | Diffusion descendante un-vers-tous (broadcast), une seule source (le satellite) vers un nombre illimité de récepteurs passifs | Maillage (mesh) pair-à-pair, chaque nœud peut relayer les messages des autres |
| Infrastructure requise | Un satellite en orbite, déjà lancé et opérationnel - l'équipe ne contrôle et ne peut réparer aucun élément de la chaîne d'émission | Aucune infrastructure fixe : les nœuds eux-mêmes forment le réseau, déployables/reconfigurables à volonté |
| Point de défaillance unique | Oui, structurel : la perte du satellite (fin de vie, panne) coupe la diffusion pour toute une région du globe, sans recours | Non par conception : la perte d'un nœud est contournée par un autre chemin de relais si le maillage est assez dense |
| Portée d'un lien élémentaire | Très grande (des centaines à ~2500km au sol pour une orbite basse comme Meteor-M, cf. `tracking/passes.py`), mais **un seul lien**, non redondant | Faible par saut (de l'ordre du kilomètre à quelques kilomètres en LoRa, très dépendant du terrain et des obstacles), mais **redondant** via le relais multi-sauts |
| Sens de communication | Descendant uniquement (broadcast) tel qu'implémenté dans ce projet - aucune voie de retour vers le satellite (émission non autorisée par le cahier des charges) | Bidirectionnel : chaque nœud peut émettre et recevoir |

## 3. Résilience - ce que chaque architecture encaisse bien ou mal

- **SatRX résiste bien à** : l'absence totale d'infrastructure terrestre (pas besoin de
  relais, de câblage, ni de connectivité entre points de réception isolés - chaque
  récepteur est autonome). C'est adapté à un contexte où la zone de couverture est très
  vaste et où il n'y a justement personne au sol pour former un maillage (zones maritimes,
  polaires, désertiques).
- **SatRX résiste mal à** : la disponibilité temporelle. Un passage Meteor-M dure
  quelques minutes toutes les quelques heures (cf. les passages calculés dans ce projet,
  ~10-12 min, 2 à 4 fois par jour selon l'orbite) - hors de cette fenêtre, la réception
  est structurellement impossible, quel que soit le matériel. Ce n'est pas une panne, c'est
  une contrainte orbitale incompressible.
- **Meshtastic résiste bien à** : la perte de nœuds individuels (dégradation progressive
  plutôt que rupture totale, tant que la densité de nœuds reste suffisante pour maintenir
  un chemin), et à l'absence d'infrastructure télécom (aucun opérateur, aucune tour
  relais nécessaire - pertinent en zone sinistrée ou en montagne).
- **Meshtastic résiste mal à** : la faible densité de nœuds (en dessous d'un seuil, le
  maillage se fragmente en îlots déconnectés) et à la portée par saut, intrinsèquement
  limitée par la modulation LoRa et la puissance d'émission réglementaire (ISM, quelques
  dizaines de mW selon la région) - contrairement à un satellite, il n'y a pas de vue
  dégagée systématique, le relief et les bâtiments coupent réellement les liens.

## 4. Débit et usage

- **SatRX (LRPT)** : ~72 kBd QPSK, ~144 kbps brut avant FEC (cf. `demod/qpsk.py`,
  constantes confirmées en session, voir `CONTEXT.md`) - suffisant pour de l'image
  (imagerie météo par canal spectral) et de la télémétrie, mais à sens unique et fenêtré
  dans le temps.
- **Meshtastic** : bien plus faible (LoRa privilégie la portée et la consommation sur le
  débit - usage typique documenté : messages texte courts, position GPS, télémétrie de
  capteurs légers), mais **disponible en continu** tant que le maillage tient, sans
  fenêtre de passage à respecter.

Le compromis est donc inversé entre les deux systèmes : SatRX offre plus de débit sur une
fenêtre étroite et imprévisible du point de vue de l'utilisateur au sol (mais parfaitement
prévisible via le calcul orbital, cf. F2), Meshtastic offre moins de débit mais une
disponibilité quasi continue.

## 5. Sécurité (renvoi à F8)

Cf. `docs/analyse_securite_f8.md` § 2.4 pour le détail : Meshtastic chiffre par défaut
(AES, préréglage « LongFast ») mais avec une **clé par défaut publique et documentée**
par le projet lui-même - la protection réelle dépend d'une action explicite de
l'opérateur (changer la clé). LRPT, à l'inverse, n'a **jamais** cherché à être
confidentiel : c'est une diffusion publique par conception, pas un mécanisme de
protection non activé. La leçon pour le rapport : l'absence de chiffrement sur LRPT est
un choix assumé et documenté par l'exploitant du satellite, alors que le cas Meshtastic
illustre plutôt un chiffrement présent mais neutralisé par une configuration par défaut
non changée - deux situations différentes qui peuvent pourtant produire le même résultat
observable (« clair sur les ondes »), point qu'illustre concrètement le module
`security/entropy.py` de ce projet (l'entropie seule ne dit pas *pourquoi* un flux est en
clair, seulement *qu'il l'est*).

## 6. Synthèse

| Critère | SatRX (LRPT) | Meshtastic |
|---|---|---|
| Résilience à la panne d'un élément | Faible (source unique) | Élevée (relais multiple) |
| Résilience à l'absence d'infrastructure terrestre | Élevée | Élevée |
| Disponibilité dans le temps | Fenêtrée (passages orbitaux prévisibles) | Continue (tant que le maillage tient) |
| Portée d'un lien | Très grande (orbite basse) | Faible (LoRa, quelques km) |
| Débit | Plus élevé | Faible |
| Sens de communication | Descendant uniquement (dans ce projet) | Bidirectionnel |
| Confidentialité par défaut | Aucune, assumée | Présente mais neutralisable (clé par défaut) |

Les deux architectures ne sont pas substituables : SatRX répond à un besoin de couverture
globale ponctuelle à haut débit relatif (observation de la Terre), Meshtastic répond à un
besoin de communication locale continue sans infrastructure (coordination de terrain).
Un système réellement résilient à grande échelle combinerait probablement les deux
registres plutôt que de choisir l'un contre l'autre - ce n'est pas un axe creusé plus
loin ici (hors périmètre du cahier des charges), mais une piste de conclusion pertinente
pour la soutenance.
