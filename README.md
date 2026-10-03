# SatTrack / SatRX - Réception et suivi de satellites par SDR

> Projet de recherche open source - tous droits réservés.
> Utilisation commerciale interdite (licence CC BY-NC 4.0).

Chaîne logicielle complète pour **comprendre comment les satellites fonctionnent et
émettent leurs données** : réception du signal radio, identification de la fréquence
émise par chaque satellite, prédiction de l'heure de passage au-dessus d'un point
géographique, et orientation automatique de l'antenne (ou du matériel connecté au
programme) en direction du satellite durant le passage.

## Fonctionnalités principales

- **Détection et réception de signal** : enregistrement IQ via HackRF / RTL-SDR sur
  les fréquences satellite (VHF 137 MHz, L-band 1.6 GHz, bande S/X)
- **Identification des satellites et de leurs fréquences** : base TLE mise à jour
  (NOAA, Meteor-M, ISS, etc.), correspondance fréquence ↔ satellite
- **Prédiction de passage** : heure AOS/LOS, élévation maximale, azimut, correction
  Doppler en temps réel - pour un point GPS donné
- **Orientation d'antenne automatique** : pilotage d'un rotateur 2 axes AZ/EL via
  Arduino Nano (protocole Hamlib série), avec calcul de trajectoire en direct
- **Décodage du signal** : démodulation QPSK/OQPSK, synchro trame CCSDS,
  Viterbi K=7 + Reed-Solomon, reconstruction d'image météo (LRPT Meteor-M)
- **Dashboard TUI** : interface terminal en direct (Textual) - trajectoire animée,
  fréquence, Doppler, état de la capture, images décodées
- **Analyse de sécurité** : classification signal chiffré/clair par entropie de
  Shannon, démonstration AES-256-GCM, audit protocolaire GMR-1 en environnement lab

## Périmètre légal

Réception **passive** uniquement de diffusions satellite ouvertes (LRPT/HRPT,
télémétrie CCSDS en clair). Toute émission RF sans licence ou interception de
communications privées est hors périmètre. L'audit protocolaire GMR-1 (module
`security/gmr1/`) est conditionné à une autorisation écrite de l'opérateur et un
environnement lab isolé.

## Auteurs

- **Gordibus** - `tracking/`, `antenna/` (suivi orbital, Doppler, rotateur)
- **Naywvi** - `decode/`, `image/`, `telemetry/`, `security/` (décodage, images, sécurité)
- `acquisition/` et `demod/` : communs

---

## Sommaire

1. [Architecture](#architecture)
2. [Matériel](#matériel)
3. [Installation](#installation)
4. [Démarrage rapide](#démarrage-rapide)
5. [Modules et fonctionnalités](#modules-et-fonctionnalités)
6. [TUI Dashboard](#tui-dashboard)
7. [Pipeline de décodage LRPT](#pipeline-de-décodage-lrpt)
8. [Analyse de sécurité](#analyse-de-sécurité)
9. [Tests](#tests)
10. [État d'avancement](#état-davancement)
11. [Captures réelles](#captures-réelles)

---

## Architecture

```
src/satrx/
  acquisition/        # F1  - enregistrement IQ (HackRF / RTL-SDR)
  tracking/           # F2  - TLE, prédiction passages, correction Doppler
  demod/              # F3  - démodulation QPSK/OQPSK, Costas loop, timing recovery
  decode/             # F4  - maillons réimplémentés : synchro trame, Viterbi, RS, CCSDS
  image/              # F5  - reconstruction LRPT, composition couleur RGB
  telemetry/          # F7  - décodage télémétrie CCSDS (temps CUC, paramètres bit à bit)
  security/           # F8  - entropie de Shannon, classification chiffré/clair
    gmr1/             # B8  - audit lab GMR-1 : simulation IQ, GMSK, A5/GMR-1, fraude
  dashboard/          # F11 - rapport HTML statique (images + métadonnées)
  tui/                # F10 - TUI Textual : capture programmée + dashboard 7 onglets
    tabs/             # 7 onglets du dashboard
tests/                # miroir exact de src/satrx/
scripts/              # CLIs : schedule_capture, decode_lrpt, generate_dashboard
docs/                 # rapports, schémas d'architecture, analyses de sécurité
data/
  raw/                # enregistrements IQ bruts (non versionnés, .cs8 + .json sidecar)
  processed/          # images décodées, données de télémétrie (non versionnés)
```

### Schéma de la chaîne de traitement

```
Antenne → LNA/filtre → HackRF → acquisition IQ (F1)
                                        │
              suivi orbital (F2) ───────┤  correction Doppler
                                        │
                               démodulation QPSK (F3)
                               Costas loop / timing recovery
                                        │
                               synchro trame ASM (F4)
                               Viterbi K=7 + dérandomisation + RS(255,223)×4
                                        │
                               dégroupage CCSDS (F4)
                                        │
                    ┌───────────────────┴─────────────────┐
               image LRPT (F5)                    télémétrie (F7)
               JPEG/DCT + composition RGB          temps CUC + paramètres
```

---

## Matériel

| Élément           | Détail                                        |
|-------------------|-----------------------------------------------|
| SDR               | HackRF One (S/N …c66c63dc301c7b83, firmware 2024.02.1) |
| Antenne VHF       | QFH 137 MHz - LRPT Meteor-M / APT NOAA       |
| Antenne L-band    | WiFi directionnelle (Yagi/plat) - 1.6 GHz    |
| Convertisseur     | LNB + bias-tee pour bandes > 6 GHz (futur F6) |

Règle de sélection d'antenne par fréquence :
- < 300 MHz (bande VHF) → antenne TV QFH ou dipôle
- 300 MHz – 3 GHz (L/S-band) → antenne WiFi directionnelle (Yagi ou patch)
- > 6 GHz → LNB downconverter + bias-tee

---

## Installation

### Prérequis système

```bash
# Debian/Ubuntu
sudo apt install gnuradio gr-satellites hackrf rtl-sdr libhackrf0
```

GNU Radio et ses bindings Python sont installés au niveau système ; le venv Poetry
y accède via `system-site-packages` (déjà configuré dans `pyproject.toml`).

### Environnement Python

**Option A - Poetry (recommandé)**

```bash
git clone https://github.com/gordibus/SatTrack.git
cd SatTrack

poetry install
poetry run python -m satrx.tui
```

**Option B - pip + requirements.txt**

```bash
git clone https://github.com/gordibus/SatTrack.git
cd SatTrack

python3 -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python -m satrx.tui
```

> Note : GNU Radio (`gnuradio`, `gr-satellites`) ne s'installe pas via pip.
> Il est uniquement requis pour les flowgraphs de démodulation avancés.
> Le TUI, le décodage LRPT et le suivi orbital fonctionnent sans lui.

---

## Démarrage rapide

### TUI dashboard (recommandé)

```bash
poetry run python -m satrx.tui
```

Lance le dashboard 7 onglets : prédiction de passages, planification de capture,
décodage LRPT interactif, analyse de sécurité, archives.

### Capture programmée en ligne de commande

```bash
# Calculer les prochains passages et lancer une capture
poetry run python scripts/schedule_capture.py --help

# Exemple : METEOR-M2 3, 137.7 MHz, gain LNA 32 dB + VGA 30 dB
poetry run python scripts/schedule_capture.py \
  --norad 57166 \
  --freq-hz 137700000 \
  --lna-db 32 --gain-db 30 \
  --duration 700
```

### Décodage LRPT

```bash
poetry run python scripts/decode_lrpt.py \
  data/raw/20260822T202850Z_METEOR-M2-3_137.700MHz.cs8
```

### Dashboard HTML des archives

```bash
poetry run python scripts/generate_dashboard.py
# Génère data/processed/dashboard.html
```

---

## Modules et fonctionnalités

### F1 - Acquisition IQ (`acquisition/`)

- `params.py` : `RecordingParams`, `SdrDevice` (HACKRF / RTLSDR), `duration_from_pass`
- `commands.py` : construction des commandes `hackrf_transfer` / `rtl_sdr`, nommage horodaté UTC
- `recorder.py` : `record_iq` (wrapper subprocess), `start_recording_process` (Popen non bloquant),
  `parse_hackrf_stats_line` (puissance/temps réel), `write_metadata_sidecar` (JSON sidecar `.cs8.json`)

Chaque enregistrement produit un fichier `.cs8` (int8 I+Q) et un sidecar JSON contenant
la fréquence centrale, le taux d'échantillonnage, la durée, les gains et l'horodatage UTC.

### F2 - Suivi orbital (`tracking/`)

- `station.py` : `GroundStation` (latitude, longitude, altitude)
- `tle.py` : `parse_tle_text`, `load_satellite`, `fetch_tle_celestrak` (fetch CelesTrak en direct)
- `passes.py` : `find_passes` (wrapper skyfield `find_events`), `SatellitePass`,
  `compute_trajectory` (liste de `TrajectoryPoint` azimut/élévation/Doppler)
- `doppler.py` : `range_rate_m_per_s` (différence finie centrée), `doppler_shift_hz`,
  `corrected_rx_freq_hz`

La correction Doppler est calculée par différence finie de la distance oblique sur ±0.5 s,
sans dépendance à une fonction de dérivée analytique non disponible dans skyfield.

### F3 - Démodulation et décodage LRPT (maillons réimplémentés)

#### Démodulation (`demod/`)

- `costas.py` :
  - `estimate_frequency_offset_4th_power` - estimation grossière par élévation à la puissance 4
    (supprime la modulation QPSK, range ±Fs/8)
  - `costas_loop_qpsk` - PLL décision-dirigée, bande passante et facteur d'amortissement
    configurables ; retourne `CostasLoopResult` (symboles corrigés, historique phase/fréquence)
  - `resolve_qpsk_phase_ambiguity` - lève l'ambiguïté de phase à 4 états en cherchant l'ASM
    sur les 4 rotations possibles

- `timing_recovery.py` :
  - `estimate_symbol_timing_offset` - maximisation d'énergie moyenne (non-data-aided, par bloc)
  - `extract_symbols_at_offset` - extraction des symboles à un offset fractionnaire donné

- `qpsk.py` :
  - `downsample_to_symbol_rate` - décimation à taux de symbole fixe
  - `downsample_oqpsk_symbols` - réalignement I/Q avec décalage demi-symbole (OQPSK)
  - `slice_qpsk_symbols` - décision Gray indépendante par signe I/Q

#### Décodage (`decode/`)

- `frame_sync.py` :
  - `find_sync_markers` - corrélation ASM tolérante aux erreurs (distance de Hamming configurable)
  - `extract_frames` - extraction de trames de longueur fixe avec resynchronisation
  - Constante réelle confirmée : `METEOR_LRPT_CADU_LENGTH_BITS = 8192`

- `viterbi.py` :
  - `convolutional_encode` - encodeur de référence (tests)
  - `viterbi_decode` - décodage à décision dure, treillis K=7, vectorisé numpy
  - Polynômes NASA/CCSDS confirmés : G1=0o171, G2=0o133

- `reed_solomon.py` :
  - Arithmétique GF(2^8) complète (polynôme primitif réel Meteor-M : 0x187)
  - `rs_encode` / `rs_decode` (syndromes, Berlekamp-Massey, recherche de Chien)
  - `rs_decode_batch` - lot vectorisé numpy (syndromes en une passe, ~5.6× plus rapide)
  - `interleave_codewords` / `deinterleave_codewords` (profondeur 4 CCSDS)
  - `rs_encode_interleaved` / `rs_decode_interleaved`

- `derandomize.py` :
  - `generate_pn_sequence` - registre 8 bits, masque 0x95, 255 octets, période exacte 255
  - `derandomize` - XOR avec la séquence PN (sa propre inverse)

- `jpeg_entropy.py` :
  - Huffman canonique JPEG (tables DC/AC luminance standard ITU T.81, vérifiées contre OpenJDK)
  - `decode_block` / `encode_block` - décodage/encodage entropique JPEG-baseline
    (DC différentiel + AC avec ZRL/EOB)

- `ccsds.py` :
  - `parse_primary_header`, `parse_packet`, `parse_all_packets`
  - `demux_by_apid`, `reassemble_apid_stream`

#### Reconstruction image (`image/`)

- `dct.py` : `dct_8x8` / `idct_8x8`, `ZIGZAG_ORDER`, `dequantize`, `quantize`,
  `STANDARD_LUMINANCE_QUANT_TABLE`, `scale_quantization_table` (formule IJG qualité)
- `mcu.py` : `decode_mcu_image` / `encode_mcu_image` (orchestration complète bloc par bloc,
  DC différentiel chaîné, ordre raster)
- `compose.py` : `compose_rgb`, `compose_from_channel_map`, `normalize_channel`,
  `METEOR_LRPT_APID_CHANNELS` (mapping confirmé : APID 64→canal 1, 65→canal 2, 67→canal 4)
- `io.py` : `save_image` (PNG via matplotlib)

### F7 - Télémétrie CCSDS (`telemetry/`)

- `cuc_time.py` : `CucTime`, `decode_cuc_time` (CCSDS Unsegmented Time Code, coarse+fine)
- `frame.py` : `TelemetryParameterSpec`, `extract_raw_bits` (extraction bit à bit sur frontières
  d'octet), `extract_parameter` (échelle + offset), `decode_telemetry_frame`
- `onboard_time.py` : `OnboardTime`, `parse_onboard_time` (APID 70, confirmé dans la source
  `met_packet.pas` du décodeur LRPT de référence)

### F8 - Analyse de sécurité (`security/`)

- `entropy.py` : `shannon_entropy`, `classify_payload` (seuils : > 7.5 bit/B → chiffré,
  < 6.0 → clair structuré), `analyze_packets_by_apid`
- `crypto_demo.py` : `generate_key`, `encrypt_payload` / `decrypt_payload` (AES-256-GCM
  via `cryptography`) - démonstration de l'effet du chiffrement sur l'entropie

Résultats sur données réelles (22/08/2026) : LRPT entropie ~6.8 bit/B (non chiffré,
structure JPEG visible par blocs), APT ~5.5 bit/B (signal analogique FM reconverti en
numérique, moins aléatoire).

Rapport de synthèse : `docs/analyse_securite_f8.md`

### B8 - Audit lab GMR-1 (`security/gmr1/`)

⚠ Ce module n'est utilisable que dans le cadre d'un audit lab avec accord écrit de
l'opérateur et environnement isolé (cage de Faraday ou simulation pure) - cf. cahier des charges.

- `signal_gen.py` : générateur IQ GMR-1 synthétique (burst TDMA, GMSK, A5/GMR-1)
- `gmsk.py` : démodulateur GMSK (BT=0.3, index 0.5)
- `protocol.py` : extraction de trames GMR-1 (en-têtes TDMA, identifiants de session)
- `crypto.py` : `recover_keystream`, `brute_force_r1`, `verify_state`,
  `attack_known_plaintext` (cryptanalyse A5/GMR-1, algorithme faible documenté)
- `fraud.py` : `detect_simultaneous_sessions`, `detect_sequence_replay`,
  `detect_billing_gaps`, `analyze_session_log`

Rapport d'audit complet (6 findings, playbook Blue Team 4 procédures, 4 règles SIEM
format Sigma) : `docs/audit_b8_lab_report.md`

Findings principaux :
- ☠ FIND-01 (CRITIQUE) : cryptanalyse A5/GMR-1 - algorithme factorisé GEA-1 faible
- ⚠ FIND-02 (HAUTE) : clonage IMSI possible
- ⚠ FIND-03 (HAUTE) : replay de session
- ⚠ FIND-05 (HAUTE) : absence de MAC sur les trames de contrôle
- ℹ FIND-04 (MOYENNE) : billing gap par désynchronisation intentionnelle
- ℹ FIND-06 (INFO) : taps A5/GMR-1 documentés publiquement (Lichtman 2012, Welte 2012)

### F11 - Dashboard HTML (`dashboard/`)

- `scan.py` : `scan_recordings` - parcourt les sidecars `.cs8.json`, associe les images
  décodées correspondantes dans `data/processed/`
- `report.py` : `render_html_report` / `write_report` - rapport HTML autonome (thème sombre,
  images encodées base64, échappement HTML)

```bash
poetry run python scripts/generate_dashboard.py
# → data/processed/dashboard.html
```

---

## TUI Dashboard

```bash
# Avec Poetry
poetry run python -m satrx.tui

# Avec pip (venv activé)
python -m satrx.tui
```

Interface terminal thème cyberpunk (Textual). Fonctionne dans n'importe quel terminal
256 couleurs (GNOME Terminal, Kitty, Windows Terminal, iTerm2...).

| Touche | Action                    |
|--------|---------------------------|
| 1-7    | Changer d'onglet          |
| f      | Ajouter/retirer favoris   |
| r      | Actualiser TLE            |
| q      | Quitter                   |

---

### Premiere utilisation - guide pas a pas

#### Etape 1 - Configurer votre station sol (onglet 7 - CONFIG)

Au premier lancement, aller directement dans l'onglet 7 :

- **Nom de station** : nom libre (ex: `Paris-Nord`)
- **Latitude / Longitude** : coordonnees GPS de votre position
  (ex: `48.9101` / `2.2549` pour Saint-Denis)
- **Altitude** : altitude en metres (ex: `35`)
- **Correction PPM** : decalage de l'oscillateur de votre SDR
  (HackRF : mesurer avec `hackrf_transfer`, RTL-SDR : utiliser `kalibrate-rtl`)
- **Gains LNA/VGA** : valeurs par defaut 30/30 dB, a ajuster selon le bruit
- Cliquer **Sauvegarder** - les coordonnees sont utilisees pour tous les calculs de passage

#### Etape 2 - Trouver un satellite et planifier une capture (onglet 1 - PASSES)

1. L'onglet charge automatiquement les TLE depuis CelesTrak au demarrage
2. La liste affiche les prochains passages dans les 24h, tries par heure AOS
3. Pour rechercher un satellite specifique : taper son nom ou NORAD ID dans la barre
   (ex: `METEOR-M` ou `57166` pour Meteor-M2 4)
4. Appuyer sur **f** pour mettre un satellite en favori - il remonte en tete de liste
5. Selectionner une ligne et appuyer sur **Entree** pour planifier automatiquement
   une capture sur ce passage - vous basculerez sur l'onglet 2

Satellites recommandes pour debuter :
- **Meteor-M2 3** (NORAD 57166) - images meteo LRPT 137.9 MHz, passages frequents
- **NOAA 18** (NORAD 28654) - images APT 137.9125 MHz, signal fort
- **NOAA 19** (NORAD 33591) - images APT 137.1 MHz, signal fort

#### Etape 3 - Lancer la capture (onglet 2 - PLANIFIE)

- La file d'attente affiche la capture avec son heure AOS, la frequence et le statut
- **ATTENTE** : la capture se declenchera automatiquement a l'heure AOS
- Verifier que le materiel SDR est connecte - le TUI le detecte et affiche
  `HackRF detecte` ou `RTL-SDR detecte` en bas d'ecran
- Orienter l'antenne vers l'azimut affiche (ou laisser le rotateur le faire si connecte)
- La capture passe en **EN COURS** automatiquement et bascule sur l'onglet 3

#### Etape 4 - Suivre le passage (onglet 3 - EN COURS)

- La trajectoire du satellite s'anime en temps reel (azimut/elevation)
- La correction Doppler est affichee et appliquee en continu
- Le fichier `.cs8` est ecrit dans `data/raw/` avec un sidecar `.json`
  (frequence, gain, taux d'echantillonnage, satellite, heure AOS/LOS)
- Cocher **Decoder a la fin** pour lancer automatiquement le pipeline apres LOS

#### Etape 5 - Decoder le signal (onglet 4 - DECODAGE)

1. Selectionner le fichier `.cs8` enregistre dans `data/raw/`
2. Le protocole est detecte automatiquement depuis le sidecar :
   - 137 MHz + taux >= 200 ksps -> LRPT (Meteor-M, image meteo couleur)
   - 137 MHz + taux < 200 ksps -> APT (NOAA, image noir et blanc)
3. Cliquer **Decoder** - la barre de progression suit chaque etape du pipeline
4. En cas de succes, l'image est sauvegardee dans `data/processed/`
   et s'ouvre dans l'onglet ARCHIVES

> Si le decodage echoue (BER trop eleve, NOSYNC) : le signal etait trop faible.
> Causes habituelles : elevation maximale < 15 deg, antenne non adaptee,
> ou SDR centre pile sur la frequence (fuite oscillateur local a 0 Hz -
> decaler de 100-200 kHz et corriger dans les parametres PPM).

#### Etape 6 - Consulter les archives (onglet 6 - ARCHIVES)

- Toutes les captures passees avec taille, image associee et statut de lisibilite
- Colonne **Lisible** : verifie les magic bytes PNG/JPEG et l'entropie du signal
  (`✓` image propre, `✗ chiffre ?` entropie trop elevee, `✗ corrompu` fichier tronque)
- Bouton **Dashboard HTML** pour generer un rapport complet dans `data/processed/`

---

### Onglet 1 - PASSES

- Calcule les passages des 24h pour tous les favoris et satellites connus (NORAD IDs)
- Recherche d'un satellite par nom ou NORAD ID (interrogation CelesTrak en direct)
- Favoris en tête de liste (étoile ★), tri par prochain passage ou par ordre alphabétique
- Sélectionner une ligne + Entrée → planifie automatiquement une capture (onglet 2)

### Onglet 2 - PLANIFIÉ

- File d'attente des captures, avec fréquence et statut (ATTENTE / EN COURS / TERMINÉ)
- Détection automatique du matériel SDR connecté (HackRF / RTL-SDR) + suggestion d'antenne
- Déclenchement automatique à l'heure AOS

### Onglet 3 - EN COURS

- Capture active avec trajectoire satellite animée (azimut/élévation en temps réel)
- Correction Doppler affichée en temps réel
- Bouton « Décoder à la fin » pour enchaîner automatiquement sur l'onglet 4

### Onglet 4 - DÉCODAGE

- Sélection d'un fichier IQ (`.cs8`) dans `data/raw/`
- Détection automatique du protocole depuis le sidecar JSON
  (LRPT : 137 MHz + taux ≥ 200 ksps, APT : 137 MHz + taux < 200 ksps)
- Barre de progression par étape du pipeline : Costas → timing → dérandomisation →
  Viterbi → RS → synchro trame → JPEG/DCT
- Log en temps réel (nombre de trames, corrections RS, erreurs)

### Onglet 5 - SÉCURITÉ

- Sélection d'un fichier IQ ou image PNG
- Analyse d'entropie de Shannon globale + par blocs de 64 ko
- Détection automatique du protocole et du chiffrement
- Tableau de bord des findings B8 (FIND-01 à FIND-06)

### Onglet 6 - ARCHIVES

- Historique de toutes les captures IQ avec taille, image associée, gain
- Colonne **Lisible** : vérifie les en-têtes magic bytes PNG/JPEG et l'entropie
  (✓ OK, ✗ chiffré ?, ✗ corrompu)
- Boutons : Décoder, Analyser sécurité, Dashboard HTML, Ouvrir image

### Onglet 7 - CONFIG

- Station sol : nom, latitude, longitude, altitude
- Paramètres SDR : gains LNA/VGA, amplificateur, taux d'échantillonnage, correction PPM
- Répertoires `data/raw` et `data/processed`
- Détection matériel à la demande

---

## Pipeline de décodage LRPT

Ordre réel confirmé par les tests d'intégration et le décodeur de référence
`artlav/meteor_decoder` :

```
bits bruts (IQ → décision QPSK)
  │
  ├─ Recherche ASM (0x1ACFFC1D) dans le flux brut
  │    L'ASM est transmis sans encodage convolutionnel
  │
  └─ Pour chaque frame (après ASM) :
       Viterbi K=7 (rate 1/2, polynômes 171/133 oct.)
         → 1020 octets
       Dérandomisation CCSDS (XOR séquence PN, masque 0x95)
         → 1020 octets dérandomisés
       RS(255,223) × 4 avec désentrelacement profondeur 4
         → 4 × 223 = 892 octets de données CCSDS
       Dégroupage CCSDS → paquets par APID
         → APID 64 (canal 1), 65 (canal 2), 67 (canal 4)
       JPEG/DCT → MCU → image PNG
```

Structure d'un CADU Meteor-M2 :

```
┌──────────────────────────────────────────────────────────────┐
│ ASM 4 o    │ Payload RS interleaved 1020 o                   │
│ 0x1ACFFC1D │ = 4 × RS(255,223) entrelacés octet par octet    │
└──────────────────────────────────────────────────────────────┘
             ↑ après Viterbi et dérandomisation
```

### Commande de décodage

```bash
# Décodage depuis le début du fichier (chunk 50 Mo = ~12 s de signal)
poetry run python scripts/decode_lrpt.py \
  data/raw/20260822T202850Z_METEOR-M2-3_137.700MHz.cs8

# Avec offset (sauter les premières secondes de montée en gain)
poetry run python scripts/decode_lrpt.py \
  data/raw/20260822T202850Z_METEOR-M2-3_137.700MHz.cs8 \
  --offset-mb 200 --chunk-mb 100

# Sortie dans un répertoire spécifique
poetry run python scripts/decode_lrpt.py <fichier>.cs8 \
  --out-dir data/processed/
```

---

## Analyse de sécurité

La comparaison « clair vs protégé » porte sur trois niveaux :

**1. Au niveau du signal (entropie) :**
Un signal en clair (LRPT, APT) présente une entropie de Shannon inférieure à 7.5 bit/B
car la structure du protocole (en-têtes CCSDS, blocs DCT JPEG) est prévisible.
Un payload chiffré AES-256-GCM atteint ~8.0 bit/B (pseudo-aléatoire uniforme).

**2. Au niveau protocolaire (LRPT/APT) :**
LRPT et APT n'intègrent aucun mécanisme de chiffrement par conception - la diffusion
est publique et ouverte. La protection est assurée uniquement par l'absence de
récepteurs accessibles au grand public, non par des moyens cryptographiques.

**3. Au niveau des liens commerciaux (GMR-1, cadre audit lab) :**
GMR-1 utilise A5/GMR-2 (dérivé d'A5/2 GSM), dont les faiblesses cryptanalytiques
sont documentées publiquement depuis 2012 (Lichtman, Welte). Cf. `docs/audit_b8_lab_report.md`.

---

## Tests

```bash
# Tous les tests unitaires
poetry run pytest

# Avec couverture
poetry run pytest --cov=satrx --cov-report=term-missing

# Module spécifique
poetry run pytest tests/decode/
poetry run pytest tests/tracking/

# Typage et style
poetry run mypy src/
poetry run ruff check .
```

**341 tests unitaires** couvrant :
- Cas nominaux, cas limites/erreurs, interopérabilité entre modules
- Tests de pipeline bout en bout (IQ synthétique → bits → ASM → Viterbi → RS)
- Tests de non-régression vectorisation numpy (résultats bit à bit identiques
  à l'implémentation séquentielle de référence)

Règles de test :
- Pas de mock pour ce qui peut être testé avec de vraies données
- Pour les modules `decode/` : comparaison à la sortie de SatDump sur le même
  enregistrement IQ dès qu'un enregistrement réel est disponible
- Fonctions I/O (SDR, réseau) : logique testable isolée en fonctions pures ;
  couverture matérielle dans `tests/integration/`

---

## État d'avancement

| ID  | Fonctionnalité                                   | État      | Responsable  |
|-----|--------------------------------------------------|-----------|--------------|
| F1  | Acquisition IQ HackRF / RTL-SDR                  | ✓ complet | commun       |
| F2  | Suivi orbital + correction Doppler               | ✓ complet | Gordibus        |
| F3  | Décodage LRPT (maillon réimplémenté)             | ✓ complet | Naywvi        |
| F4  | Synchro trame + dégroupage CCSDS                 | ✓ complet | Naywvi        |
| F5  | Reconstruction image LRPT + composition RGB      | ✓ complet | Naywvi        |
| F6  | Réception bande L HRPT                           | ⚐ backlog | Gordibus        |
| F7  | Télémétrie CCSDS (moteur générique)              | ✓ complet | Naywvi        |
| F8  | Analyse de sécurité clair vs protégé             | ✓ complet | Naywvi        |
| F9  | Pointage d'antenne assisté/motorisé              | ⚐ backlog | Gordibus        |
| F10 | Capture programmée + TUI live                    | ✓ complet | commun       |
| F11 | Dashboard HTML de visualisation                  | ✓ complet | commun       |
| F12 | Comparaison réseau résilient (Meshtastic)        | ✓ complet | commun       |
| B8  | Audit lab GMR-1 (avec accord opérateur)          | ✓ complet | Naywvi        |
| B8+ | Décodage sur capture réelle (22/08/2026)         | ⚙ en cours| commun       |
| B1-7| Module SatScan passif (Rust, après Must/Should)  | ⚐ futur   | -            |

**⚠ Point en attente :**
La validation de la chaîne de décodage (F3/F4) sur données réelles et la comparaison
avec SatDump reste à compléter - c'est l'exigence centrale du cahier des charges pour
marquer F3 définitivement `[x]`. La capture du 22/08/2026 (METEOR-M2 3, 71.1°,
2.7 Go) est le fichier cible.

---

## Captures réelles

| Date       | Satellite      | Fréquence    | Élévation | Durée  | Résultat                              |
|------------|----------------|--------------|-----------|--------|---------------------------------------|
| 16/08/2026 | IRIDIUM        | 1621.25 MHz  | -         | 20 s   | ✓ Rafales détectées (+26 dB, 1621.318 MHz) - validation chaîne |
| 16/08/2026 | METEOR-M2-3    | 137.9 MHz    | 39.6°     | 660 s  | ✗ Gain VGA non configuré - sans signal |
| 22/08/2026 | METEOR-M2-3    | 137.7 MHz    | 71.1°     | 700 s  | ⚙ Décodage en cours (2.7 Go)          |
| 22/08/2026 | NOAA-18        | 137.7 MHz    | -         | -      | ⚙ Capturé                             |
| 22/08/2026 | NOAA-19        | 137.3 MHz    | -         | -      | ⚙ Capturé                             |

Note sur le désaccord de fréquence HackRF : le HackRF présente une dérive d'oscillateur
local de +300 ppm empiriquement confirmée. Pour cibler 137.9 MHz (METEOR-M2-3), le
récepteur est centré à 137.7 MHz (–200 kHz de désaccord) de sorte que la fuite LO reste
à l'extérieur de la bande d'intérêt. Le pipeline de décodage applique une correction de
+200 kHz avant la boucle de Costas.

---

## Contribuer / Workflow

```bash
# Vérifications avant commit (automatisées par pre-commit)
poetry run mypy src/
poetry run ruff check .
poetry run pytest

# Lancer le pre-commit manuellement
pre-commit run --all-files
```

Les tâches courantes sont suivies dans `TODO_LIST.md` (IDs F1–F12, B1–B8).

Convention de commit : message en français, pas de caractères décoratifs hors
du jeu autorisé (✓ ✖ ⚠ ℹ ⚙ 🛡).

---

## Licence

[CC BY-NC 4.0](LICENSE) - Copyright (c) 2026 Gordibus, Naywvi

---

*SatRX - ESGI 5SIJ - Gordibus & Naywvi*
