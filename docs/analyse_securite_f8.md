# F8 - Analyse de sécurité « clair vs protégé »

> Document de synthèse pour le rapport technique / la soutenance. Périmètre strictement
> défensif et informatif : réception passive de diffusions ouvertes, aucune action contre
> des systèmes tiers. Cohérent avec le cadre légal du projet (cf. cahier des charges).

## 1. Constat général

Une grande partie du trafic radio spatial (et adjacent) circule en clair, non pas par
négligence mais par choix de conception : les données météo, la télémétrie de nombreux
satellites scientifiques, et certains protocoles de mesh radio grand public sont pensés
pour être largement accessibles (diffusion publique, interopérabilité, coût de mise en
œuvre du chiffrement embarqué). Ce projet illustre concrètement ce que cela signifie en
pratique, sur des cas réels et documentés publiquement.

## 2. Cas étudiés

### 2.1. LRPT / APT - imagerie météo (Meteor-M, historiquement NOAA)

- **Statut** : diffusion intentionnellement en clair. Les agences météorologiques
  (Roscosmos pour Meteor-M) publient ces images pour un usage public et scientifique
  large ; il n'y a pas de confidentialité recherchée sur le contenu lui-même.
- **Ce qui est exposé** : image complète, horodatage, identité du satellite émetteur.
- **Risque réel** : faible sur le contenu (public par design). Le risque se déplace sur
  la **télémétrie associée** (voir 2.2) et sur l'usage détourné de l'infrastructure de
  réception (ex. un tiers pourrait cataloguer les zones couvertes, les horaires de
  passage, etc. - plutôt un enjeu d'inventaire/reconnaissance que de confidentialité du
  contenu).

### 2.2. Télémétrie CCSDS

- **Statut** : très variable selon la mission. De nombreux satellites scientifiques et
  météo publient leur télémétrie en clair (état des sous-systèmes, température,
  orientation, charge batterie), car le standard CCSDS lui-même ne chiffre rien par
  défaut - la protection, quand elle existe, est ajoutée au-dessus (ex. CCSDS Space Data
  Link Security, SDLS).
- **Ce qui est exposé** : état de santé du satellite, parfois des informations
  d'orientation ou de position affinées, régime de fonctionnement des instruments.
- **Risque réel** : modéré. Une télémétrie en clair permet à un observateur extérieur de
  déduire l'état opérationnel d'un satellite (panne partielle, mode dégradé, manœuvre en
  cours) - une forme de renseignement passif à faible coût. Le canal de **commande**
  (uplink), lui, est presque toujours protégé sur les systèmes opérationnels réels - la
  vraie criticité sécuritaire est là, pas sur la télémétrie descendante.

### 2.3. Iridium

- **Statut** : documenté publiquement depuis plusieurs années (recherche académique et
  communauté SDR/radioamateur) - une partie significative du trafic Iridium legacy
  (messages de paging/ring alert, certains canaux de signalisation) circule sans
  chiffrement, malgré la nature globale et parfois sensible des communications relayées.
- **Ce qui est exposé** : messages courts, métadonnées de signalisation, parfois du
  trafic voix sur certains canaux plus anciens.
- **Risque réel** : documenté comme significatif dans la littérature publique
  (interception passive possible avec du matériel grand public, cf. recherches
  publiques sur Iridium depuis le milieu des années 2010). Ce projet se limite à
  constater la réceptibilité du signal (cf. `hackrf_sweep` sur 1616-1626.5 MHz), sans
  chercher à décoder ou exploiter le contenu de communications privées - hors périmètre
  du cahier des charges (§ Hors périmètre : « interception de communications privées »).

### 2.4. Meshtastic (axe secondaire, F12)

- **Statut** : chiffrement LoRa activé **par défaut**, mais avec une **clé par défaut
  publique et documentée** dans le projet lui-même (AES, clé `1PG7OiApB1nwvP+rz05pAQ==`
  en configuration « LongFast » standard, changeable par l'utilisateur). Ce n'est pas
  une faille cachée - c'est documenté ouvertement par le projet Meshtastic, précisément
  pour que les opérateurs sachent qu'ils doivent changer la clé pour une confidentialité
  réelle.
- **Risque réel** : élevé si l'opérateur ne change pas la clé (cas fréquent en pratique
  pour des déploiements grand public/loisir) - tout le trafic sur cette configuration
  par défaut est déchiffrable par quiconque connaît la clé publique. C'est un exemple
  pédagogique fort de l'écart entre « chiffré » et « protégé ».

## 3. Ce que la démonstration technique du projet (module `security/`) illustre

- `security/entropy.py` : classification heuristique clair/chiffré par entropie de
  Shannon (bits/octet) - un texte structuré ou répétitif (télémétrie, en-têtes) a une
  entropie nettement inférieure à 8 bits/octet ; un flux chiffré ou compressé en est
  très proche. Appliqué par APID sur un flux CCSDS dégroupé, cela permet de repérer en
  un coup d'œil quels canaux méritent une attention particulière.
- `security/crypto_demo.py` : chiffrement authentifié AES-256-GCM appliqué à une charge
  utile de démonstration, montrant concrètement l'effet d'une protection - le même
  contenu passe d'une entropie basse (clair, structuré) à une entropie quasi maximale
  (chiffré), mesurable et démontrable en direct lors de la soutenance.

## 4. Recommandations générales (protection)

1. **Séparer contenu public et télémétrie opérationnelle** : rien n'empêche de publier
   l'imagerie en clair (c'est le choix assumé) tout en chiffrant la télémétrie
   d'état interne, qui n'a pas vocation à être publique.
2. **Chiffrement authentifié plutôt que confidentialité seule** : AES-GCM (ou
   équivalent) protège à la fois la confidentialité et l'intégrité - pertinent pour la
   télémétrie, critique pour tout canal de commande.
3. **Ne jamais s'appuyer sur une clé par défaut** publiée dans la documentation d'un
   protocole (cas Meshtastic) sans la faire tourner (key rotation) pour un usage où la
   confidentialité est réellement recherchée.
4. **Gestion de clé adaptée au contexte spatial** : contrainte spécifique - une fois un
   satellite lancé, la mise à jour de clé est coûteuse/impossible sans liaison de
   commande déjà sécurisée ; le choix cryptographique doit anticiper la durée de vie de
   la mission (plusieurs années à décennies).
