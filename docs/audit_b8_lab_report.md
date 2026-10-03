# Rapport d'audit de securite - Reseau satellitaire commercial (GMR-1/A5/GMR-1)
## SatRX - B8-LAB-REPORT

> **Cadre juridique** : Ce rapport est produit dans le cadre du Projet Annuel ESGI
> 5SIJ (annee 2025-2026). Toutes les analyses ont ete menees dans un environnement
> de simulation pure (aucun signal radio reel intercepte). L'architecture utilisee
> reproduit fidelement les protocoles GMR-1 (ETSI TS 101 376-5-6) et A5/GMR-1
> (Lichtman et al., USENIX Security 2012) sur des donnees synthetiques generees
> par l'equipe. Tout usage ulterieur sur un vrai reseau operateur exige une
> autorisation ecrite prealable de l'operateur/FAI.
>
> **Auteurs** : Gordibus - Naywvi
> **Date** : 22 aout 2026
> **Statut** : CONFIDENTIEL - usage interne equipe + operateur mandataire

---

## 1. Resume executif

L'audit a evalue la resistance du standard de telephonie satellitaire GMR-1 face a
trois classes de menaces : (1) cryptanalyse du chiffrement de flux A5/GMR-1,
(2) clonage d'identifiant d'abonne (IMSI cloning), (3) fraude a la facturation
par effacement d'evenements de session.

### Constatations principales

| Identifiant | Categorie         | Severite | Statut verification          |
|-------------|-------------------|----------|------------------------------|
| FIND-01     | Cryptanalyse      | CRITIQUE | ⚐ TESTE en lab simulation    |
| FIND-02     | Clonage IMSI      | HAUTE    | ⚐ TESTE en lab simulation    |
| FIND-03     | Replay de session | HAUTE    | ⚐ TESTE en lab simulation    |
| FIND-04     | Fraude facturation| MOYENNE  | ⚐ TESTE en lab simulation    |
| FIND-05     | Absence de MAC    | HAUTE    | ☑ DOCUMENTE (ETSI / Lichtman) |
| FIND-06     | Taps A5/GMR-1     | INFO     | ⚠ A VERIFIER (source unique)  |

**Legende statut** :
- ⚐ TESTE : constate et reproduit dans l'environnement lab de simulation
- ☑ DOCUMENTE : confirme par litterature academique ou standard public, non teste
- ⚠ A VERIFIER : information provenant d'une seule source, recoupement necessaire

---

## 2. Perimetre et methodologie

### 2.1 Perimetre

- **Protocoles analyses** : GMR-1 couche physique (GMSK, TDMA 8 slots), chiffrement
  A5/GMR-1 (3 LFSR, structure derivee A5/1 GSM).
- **Hors perimetre** : GMR-2 (chiffrement A5/GMR-2, non implemente), signalisation
  NAS/RRC, chiffrement de groupe, couche applicative (voix, donnees).
- **Environnement** : simulation pure Python, aucune capture radio reelle, aucun
  abonne reel, aucun IMSI en clair (hachage SHA-256 tronque 32 bits utilise
  systematiquement).

### 2.2 Modules implementes et testes

| Module                           | Fichier                              | Tests      |
|----------------------------------|--------------------------------------|------------|
| Generateur de signal IQ GMR-1    | `security/gmr1/signal_gen.py`        | 11 / 11 ✔ |
| Demodulateur GMSK differentiel   | `security/gmr1/demod.py`             | 16 / 16 ✔ |
| Chiffrement A5/GMR-1             | `security/gmr1/a5gmr1.py`           | 10 / 10 ✔ |
| Cryptanalyse (correlation LFSR)  | `security/gmr1/cryptanalysis.py`     | 14 / 14 ✔ |
| Detection de fraude              | `security/gmr1/fraud.py`             | 19 / 19 ✔ |
| **Total**                        |                                      | **70 / 70 ✔** |

### 2.3 Limites methodologiques (a signaler explicitement)

- La sequence d'apprentissage (midamble) utilisee est une sequence PN synthetique.
  La vraie sequence ETSI TS 101 376-5-6 Table 8.x n'a pas ete integree - marque
  TODO dans `constants.py`. Les detecteurs de synchronisation fonctionnent en
  simulation end-to-end mais devront etre revalides sur la vraie sequence.
- Les taps de retroaction A5/GMR-1 implementes sont ceux d'A5/1 (GSM), les taps
  GMR-1 specifiques (Lichtman 2012) sont marques TODO. La structure algorithmique
  (3 LFSR, clocking majoritaire, initialisation cle+trame) est correcte.
- Les seuils de detection de fraude (fenetre TDMA, gap de facturation) sont calibres
  sur donnees synthetiques ; un ajustement sur donnees reelles sera necessaire.

---

## 3. Constatations detaillees

### FIND-01 - Cryptanalyse A5/GMR-1 par correlation (CRITIQUE)
**Statut : ⚐ TESTE en lab simulation**

**Description** : Le chiffrement A5/GMR-1 produit 78 bits de flux de cle par burst
Normal Traffic (2 x 39 bits de donnees). La faiblesse fondamentale est identique a
A5/1 (GSM) : chaque LFSR peut etre attaque independamment en free-running mode par
maximisation de correlation.

**Observation mesuree** :
- Recuperation du flux de cle par XOR clair/chiffre : triviale, 0 ms, 100 % exact
  (`recover_keystream` - attaque a texte clair connu).
- Brute-force exhaustif de R1 (2^19 = 524 288 etats, LFSR 19 bits) :
  correlation superieure au hasard (> 1/sqrt(78) ≈ 0.113) retrouvee de maniere
  reproductible sur nos donnees de test.
- Temps de calcul R1 sur CPU numpy vectorise : < 5 s (machine de test i7-10th gen).
- La fonction `verify_state` confirme que l'etat retrouve produit une sequence
  coherente avec le flux de cle connu.

**Limitation de l'implementation actuelle** : R2 (2^22 ≈ 4M etats, ~320 MB RAM) et
R3 (2^23 ≈ 8M etats, ~640 MB RAM) peuvent etre brute-forces avec le meme algorithme
mais ont ete desactives par defaut (`search_r2_r3=False`) faute de memoire suffisante
sur la machine de test. Sur une machine >= 16 GB RAM, la recherche complete
R1+R2+R3 est faisable en quelques minutes.

**Cause racine** : cle de session 64 bits + flux de cle 78 bits/burst trop court
pour resister aux correlations individuelles sur chaque LFSR. L'absence de
renforcement algorithmique (pas d'AES, pas de SHA) est documentee par Lichtman 2012
comme une lacune de conception.

**Impact operateur** : si un attaquant capture un burst en clair connu (ex. signaux
de paging non chiffres, burst idle), il peut recuperer le flux de cle et dechiffrer
le contenu des communications du meme abonne dans la meme sequence de trame.

---

### FIND-02 - Clonage d'identifiant IMSI (HAUTE)
**Statut : ⚐ TESTE en lab simulation**

**Description** : Deux sessions avec le meme IMSI hash actives simultanement dans
des slots TDMA differents sont detectables par le reseau - mais seulement si le BSS
(Base Station Subsystem) implemente une verification de presence simultanee.

**Observation mesuree** : injection de sessions clonees (`inject_clone_attack`) et
detection par `detect_simultaneous_sessions` avec faux positif zero sur sessions
normales (19/19 cas de test).

**Vecteur d'attaque simule** :
1. Attaquant capture un burst de paging contenant le TMSI/IMSI (non chiffre).
2. Clone programme sur un autre terminal avec le meme identifiant.
3. Les deux terminaux emettent dans des slots differents du meme hyperframe.
4. Le reseau peut facturer les deux sessions ou aucune selon l'implementation du BSS.

**Impact operateur** : usage frauduleux aux frais d'un abonne legitime, double
facturation, ou acces a des services sous l'identite d'un autre.

---

### FIND-03 - Replay de contexte de session (HAUTE)
**Statut : ⚐ TESTE en lab simulation**

**Description** : Le standard GMR-1 ne prevoit pas de nonce temporel ou de compteur
de sequence lie a un secret de session pour chaque burst. Un attaquant ayant capture
un burst valide peut le retransmettre ulterieurement (replay).

**Observation mesuree** : injection de regression de numero de sequence
(`inject_replay_attack`) detectable par `detect_sequence_replay`, 0 faux positif
sur sessions normales.

**Condition de succes** : l'attaquant doit avoir acces au contenu non chiffre (burst
idle, paging) ou avoir prealablement casse le chiffrement (cf. FIND-01).

**Impact operateur** : rejeu de commandes de session (etablissement/liberation
d'appel), potentiellement rejeu d'authentification si le challenge/response
utilise un nonce trop court.

---

### FIND-04 - Fraude a la facturation par effacement de session (MOYENNE)
**Statut : ⚐ TESTE en lab simulation**

**Description** : Une modification du flux TDMA (suppression ou alteration de
bursts) peut creer des plages de session non facturees si le systeme de facturation
s'appuie uniquement sur les evenements radio plutot que sur une reconciliation
independante.

**Observation mesuree** : injection de gaps de facturation (`inject_billing_gap`)
de 8 trames (> seuil de 3 trames) detectes systematiquement par
`detect_billing_gaps`. Gaps <= seuil non signales (comportement attendu, valide).

**Condition operateur** : detecteur efficace uniquement si le systeme de supervision
radio est independant du systeme de facturation et realise une reconciliation.

---

### FIND-05 - Absence de code d'authentification de message (MAC) sur les bursts (HAUTE)
**Statut : ☑ DOCUMENTE - Lichtman et al. 2012, ETSI TS 101 376**

**Description** : Le standard GMR-1 ne prevoit pas de MAC (Message Authentication
Code) sur les bursts de trafic. L'integrite des donnees repose uniquement sur le
code correcteur d'erreur (FEC), qui detecte les erreurs de canal mais ne protege
pas contre un attaquant actif qui modifie deliberement les bits chiffres.

**Statut de verification** : non teste dans notre lab (necessite du materiel en
emission et un vrai reseau). Source : Lichtman et al. 2012, Section 3.2.

---

### FIND-06 - Incertitude sur les taps A5/GMR-1 (INFO)
**Statut : ⚠ A VERIFIER - source unique (Lichtman 2012)**

**Description** : Les taps de retroaction implementes dans `a5gmr1.py` sont ceux
d'A5/1 (GSM, domaine public depuis 2000). Les taps specifiques a A5/GMR-1 sont
references dans Lichtman 2012 mais n'ont pas ete disponibles lors de cette
implementation. Le commentaire TODO dans le code documente cette incertitude.

**Impact sur les tests** : les tests de cryptanalyse valident la structure
algorithmique et la methode de correlation ; les etats de LFSR retrouves sur
donnees simulees ne sont pas directement transposables a un vrai signal GMR-1
tant que les taps ne sont pas confirmes.

**Action requise** : obtenir l'article Lichtman 2012 (USENIX Security Symposium,
pp. 43-58) et verifier les taps Tableau 1 contre l'implementation actuelle.

---

## 4. Playbook Blue Team

### 4.1 Detection en temps reel

**PB-01 - Surveillance des sessions simultanees (contre FIND-02)**

Procedure :
1. Configurer le BSS/MSC pour journaliser chaque association IMSI → slot TDMA.
2. Appliquer une fenetre de correlation de 1 trame TDMA (4.615 ms).
3. Toute occurrence d'un meme IMSI dans 2 slots differents dans la meme fenetre
   declenche une alerte HAUTE avec suspension preventive de la session la plus
   recente (critere : TMSI le plus bas = session legitime).
4. Notifier le NOC (Network Operations Center) dans les 30 secondes.

**PB-02 - Detection de regression de sequence (contre FIND-03)**

Procedure :
1. Maintenir un journal ordered des (IMSI, seq_num, timestamp) par session active.
2. Toute regression seq_num(t+1) <= seq_num(t) pour un meme IMSI declenche une
   alerte HAUTE.
3. La session avec le seq_num regressif est marque suspecte ; l'operateur humain
   valide la suspension dans les 5 minutes.

**PB-03 - Reconciliation facturation/radio (contre FIND-04)**

Procedure :
1. Le systeme de facturation (CDR) est alimente par deux flux independants :
   (a) signalisation NAS/RRC (registration, bearer setup/teardown),
   (b) comptage volumetrique sur la trame radio (slots actifs par IMSI).
2. Reconciliation toutes les 5 minutes : tout ecart > 3 trames consecutives sans
   evenement CDR pour un abonne actif radio → alerte MOYENNE.
3. Rapport quotidien d'anomalies pour investigation manuelle.

**PB-04 - Renouvellement de cle de session (contre FIND-01)**

Procedure :
1. Forcer un renouvellement de cle de session (re-authentification AKA) toutes
   les 100 trames (environ 462 ms) au lieu du comportement par defaut GMR-1.
2. Avec 78 bits/burst de flux de cle, 100 trames = 7 800 bits de flux connu au
   maximum - insuffisant pour une attaque par correlation complete si le renouvellement
   intervient avant la 100e trame.
3. Note : cette mesure reduit la surface d'attaque mais ne corrige pas la faiblesse
   fondamentale d'A5/GMR-1 (cf. recommandation a long terme ci-dessous).

### 4.2 Mesures correctives long terme

**LT-01 - Migration vers A5/GMR-1 renforce ou algorithme de substitution**

A5/GMR-1 est un algorithme de 2001. La recommandation academique (Lichtman 2012)
est la migration vers un algorithme de chiffrement par flot moderne (ex. SNOW 3G,
ZUC) avec une cle de session >= 128 bits et un MAC sur chaque burst.

**LT-02 - Ajout d'un MAC sur les bursts de trafic**

Implementer un code d'authentification de message (ex. HMAC-SHA-256 tronque a
32 bits) sur chaque burst. Cela bloque les attaques de replay et les modifications
actives de bursts.

**LT-03 - Nonce temporel lie au timestamp reseau**

Inclure un timestamp reseau (precision >= 1 ms) dans le contexte d'initialisation
de la cle de session. Cela invalide les replays d'anciens bursts apres l'expiration
du contexte de session.

---

## 5. Regles SIEM (format Sigma)

### Regle 1 - Clonage IMSI (session simultanee)

```yaml
title: GMR-1 IMSI Simultaneous Session (Clone Attack)
id: a1b2c3d4-0001-0001-0001-000000000001
status: experimental
description: >
  Detects two active sessions with the same IMSI hash in different TDMA slots
  within a 1-frame window. Indicates a possible SIM cloning scenario.
author: SatRX / ESGI 5SIJ
date: 2026-08-22
references:
  - Lichtman et al., USENIX Security 2012
logsource:
  category: radio_session
  product: gmr1_bss
detection:
  selection:
    EventType: 'SESSION_OPEN'
  condition: |
    selection
    | groupBy imsi_hash, frame_window
    | count(distinct slot) > 1
    | within 1 frame (4.615 ms)
  timeframe: 5ms
falsepositives:
  - Legitimate handover between adjacent satellites (short overlap expected)
  - Test equipment emitting on multiple slots simultaneously
level: high
tags:
  - attack.initial_access
  - attack.t1078
fields:
  - imsi_hash
  - frame_num
  - slot
  - tmsi
```

### Regle 2 - Replay de session (regression de numero de sequence)

```yaml
title: GMR-1 Session Sequence Regression (Replay Attack)
id: a1b2c3d4-0002-0002-0002-000000000002
status: experimental
description: >
  Detects a sequence number regression for an IMSI: seq_num(t+1) <= seq_num(t).
  Indicates a session replay or captured context reuse.
author: SatRX / ESGI 5SIJ
date: 2026-08-22
logsource:
  category: radio_session
  product: gmr1_bss
detection:
  selection:
    EventType: 'BURST_DATA'
  condition: |
    selection
    | groupBy imsi_hash
    | seq_num <= prev(seq_num)
falsepositives:
  - Counter rollover (seq_num wraps to 0) - check modular arithmetic in implementation
  - BSS restart that resets sequence counters without re-authentication
level: high
tags:
  - attack.credential_access
  - attack.t1539
fields:
  - imsi_hash
  - frame_num
  - seq_num
  - prev_seq_num
```

### Regle 3 - Ecart de facturation anormal

```yaml
title: GMR-1 Billing Gap - Active Session Without CDR Event
id: a1b2c3d4-0003-0003-0003-000000000003
status: experimental
description: >
  Detects an active IMSI (slots seen in radio log) without a corresponding
  CDR billing event for more than 3 consecutive frames (~14 ms).
  May indicate billing fraud or CDR system failure.
author: SatRX / ESGI 5SIJ
date: 2026-08-22
logsource:
  category: radio_session
  product: gmr1_bss
detection:
  selection:
    EventType: 'BURST_DATA'
    billed: false
  condition: |
    selection
    | groupBy imsi_hash
    | count_consecutive(billed == false) > 3
falsepositives:
  - CDR system temporary outage
  - Legitimate idle bursts (RACH) not subject to billing
level: medium
tags:
  - attack.impact
  - attack.t1496
fields:
  - imsi_hash
  - frame_num
  - gap_size_frames
```

### Regle 4 - Correlation de flux de cle suspecte (tentative de cryptanalyse)

```yaml
title: GMR-1 Keystream Correlation Attack Attempt
id: a1b2c3d4-0004-0004-0004-000000000004
status: experimental
description: >
  Detects patterns consistent with a known-plaintext keystream recovery attempt:
  unusually high volume of idle bursts (predictable plaintext = 0x00) on a
  single IMSI, followed by rapid IMSI re-registration attempts.
author: SatRX / ESGI 5SIJ
date: 2026-08-22
logsource:
  category: radio_session
  product: gmr1_bss
detection:
  idle_burst_flood:
    EventType: 'IDLE_BURST'
  re_registration:
    EventType: 'LOCATION_UPDATE'
  condition: |
    idle_burst_flood
    | groupBy imsi_hash, 10s
    | count > 50
    | followedBy re_registration within 30s
falsepositives:
  - Legitimate handover sequences
  - Terminal in marginal coverage area
level: medium
tags:
  - attack.credential_access
  - attack.t1600
fields:
  - imsi_hash
  - idle_burst_count
  - re_registration_timestamp
```

---

## 6. Chronologie de remediation recommandee

| Priorite | Action                                       | Delai recommande  |
|----------|----------------------------------------------|-------------------|
| CRITIQUE | Deployer les regles SIEM 1 et 2              | < 2 semaines      |
| HAUTE    | Activer la reconciliation CDR/radio (PB-03)  | < 1 mois          |
| HAUTE    | Reduire la duree de vie des cles de session  | < 1 mois          |
| HAUTE    | Etude de migration vers SNOW 3G / ZUC        | < 3 mois          |
| MOYENNE  | Valider les taps A5/GMR-1 (FIND-06)          | < 3 mois          |
| BASSE    | Integration des 4 regles SIEM en production  | < 6 mois          |

---

## 7. Annexe - Infrastructure de test

### Architecture de la simulation

```
simulate_normal_sessions()     -- generateur de sessions normales
        |
        +-- inject_clone_attack()      -- injection IMSI cloning
        +-- inject_replay_attack()     -- injection replay
        +-- inject_billing_gap()       -- injection fraude facturation
        |
        v
analyze_session_log()          -- pipeline de detection complet
        |
        +-- detect_simultaneous_sessions()   -- regle SIEM 1
        +-- detect_sequence_replay()         -- regle SIEM 2
        +-- detect_billing_gaps()            -- regle SIEM 3
```

### Environnement

- Python 3.12, NumPy 1.26, pytest 8.4
- 341 tests unitaires au total (tous verts au 22/08/2026)
- mypy strict : 0 erreur sur 12 fichiers sources du module security/gmr1/
- ruff : 0 avertissement

### Enregistrements IQ

La simulation produit des fichiers IQ au format CS8 (int8 I/Q entrelace) compatibles
avec le module d'acquisition (`src/satrx/acquisition/`). Le sidecar JSON associe
documente la frequence centrale (1 621.25 MHz, bande L Thuraya/Inmarsat), le taux
d'echantillonnage et le nombre de symboles.

---

## 8. Conclusion

Les trois vulnerabilites principales d'A5/GMR-1 (FIND-01 a FIND-03) sont des
faiblesses de conception documentees, reproductibles dans notre simulation, et
coherentes avec la litterature academique. Les detecteurs implementes en
`fraud.py` permettent une surveillance operationnelle en temps quasi-reel avec
un taux de faux positifs nul sur les jeux de test synthetiques.

La mesure la plus efficace a court terme est le deploiement des regles SIEM
(Section 5) et la reconciliation CDR/radio (PB-03). La migration vers un
algorithme de chiffrement moderne (LT-01) reste la seule correction definitive
contre FIND-01.

⚠ **Rappel** : toutes les constatations marquees "TESTE en lab simulation" ont ete
produites exclusivement sur des donnees synthetiques generees par l'equipe. Aucun
signal satellitaire reel, aucun IMSI reel, et aucune infrastructure operateur n'ont
ete impliques.
