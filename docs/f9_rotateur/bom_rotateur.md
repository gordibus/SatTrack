# Nomenclature F9 - Rotateur d'antenne SatRX

## Pieces a imprimer (PLA, buse 0.4mm, couche 0.2mm, remplissage 30%)

Chaque piece est fournie en **STL** (`stl/`, impression directe) et en **STEP**
(`step/*.stp`, echange CAO). Voir la section « Formats de fichiers » plus bas.

### Set structurel (genere par `gen_parts_cq.py`)

| Fichier STL                  | Qte | Temps est. | Filament | Notes                              |
|------------------------------|-----|-----------|----------|------------------------------------|
| `platine_mat.stl`            |  1  | ~2h30     | ~40g     | Anneau ∅120/∅52, h=13mm           |
| `plateau_az.stl`             |  1  | ~2h       | ~35g     | Disque ∅100, siege 608ZZ          |
| `bras_elevation.stl`         |  2  | ~1h15 x2  | ~20g x2  | Imprimer 2 fois                   |
| `collier_antenne.stl`        |  1  | ~1h       | ~15g     | ∅33/∅25 pour boom Yagi            |
| `boitier_arduino.stl`        |  1  | ~3h       | ~50g     | Slots cables marques 1/2/3 bumps  |
| `couvercle_arduino.stl`      |  1  | ~1h       | ~20g     | Jupe d'insertion + 4xM3           |
| `adaptateur_trepied.stl`     |  1  | ~3h       | ~55g     | Socle 80x80 + collier ∅70/∅52    |

### Set interfaces (genere par `gen_parts_cq.py`)

Pieces d'accueil du materiel liste en quincaillerie (servos, 608ZZ, axe ∅6,
cables) qui manquaient au set v2.

| Fichier STL / STP            | Qte | Temps est. | Filament | Notes                              |
|------------------------------|-----|-----------|----------|------------------------------------|
| `support_servo_mg996r`       |  2  | ~1h x2    | ~28g x2  | Berceau MG996R, sert pour AZ et EL |
| `palonnier_servo`            |  2  | ~20min x2 | ~6g x2   | Accouplement palonnier OEM ∅6      |
| `chapeau_roulement_az`       |  1  | ~40min    | ~10g     | Chapeau top-hat, bloque le 608ZZ   |
| `bague_pivot_el`             |  2  | ~15min x2 | ~4g x2   | Bague ∅6.9/∅6.2 pour axe elevation |
| `serre_cable`                |  2  | ~20min x2 | ~5g x2   | Peigne 3 canaux (servo AZ/EL/USB)  |

**Total filament estime : ~255g (v2) + ~100g (v3) = ~355g (1/3 bobine 1kg)**

---

## Quincaillerie

| Reference                        | Qte | Prix est. | Ou acheter              | Notes                            |
|----------------------------------|-----|-----------|-------------------------|----------------------------------|
| Roulement 608ZZ (8x22x7mm)      |  1  | ~0.50€    | AliExpress / Mr Bricolage | Standard skateboard/imprimante 3D |
| Servo MG996R metal gear          |  2  | ~8€ x2    | AliExpress / Amazon     | Full metal gear, 11kg.cm         |
| Arduino Nano (ATmega328P)        |  1  | ~5€       | AliExpress / Amazon     | Clone accepte, port USB-C prefere|
| Vis M3x8 inox                    | 12  | ~1€/lot   | AliExpress / Leroy Merlin | Fixation servo + couvercle      |
| Vis M3x16 inox                   |  4  | ~1€/lot   | AliExpress / Leroy Merlin | Fixation plateau sur collier     |
| Vis M4x20 + ecrous M4            |  2  | ~1€/lot   | AliExpress / Leroy Merlin | Serrage collier trepied          |
| Axe inox ∅6mm L=60mm            |  1  | ~1.50€    | AliExpress (tige filetee coupee) | Pivot elevation        |
| Colliers de serrage PVC 55mm     |  2  | ~1€/lot   | Leroy Merlin / Brico    | Section plomberie                |
| Tube PVC ∅50mm (1m)             |  1  | ~5€       | Leroy Merlin / Brico    | Section plomberie                |
| Cable servo 3 fils (×2, 50cm)   |  2  | ~1€/lot   | AliExpress              | JST-SH ou Dupont 3 pins         |
| Cable USB-A vers USB-B mini      |  1  | ~2€       | AliExpress / FNAC       | Arduino → Laptop                 |

---

## Pieds (trepied) a acheter

### Option recommandee - Trepied photo standard (le plus pratique)

Le **Rollei C5i** ou equivalent est le meilleur rapport qualite/prix pour ce projet :
- Hauteur deployee : 150-165cm (passe de satellite visible depuis le sol)
- Charge max : 5kg (rotateur + antenne ~1.5kg)
- Tete avec vis 1/4" + adaptateur 3/8" inclus
- L'`adaptateur_trepied.stl` (trou central ∅10mm) se visse directement sur la tete 3/8"

**References specifiques (Amazon.fr / FNAC) :**

| Modele                         | Prix est. | Remarque                           |
|--------------------------------|-----------|------------------------------------|
| Rollei C5i                     | ~35€      | ⚠ Meilleur rapport Q/P, leger     |
| Andoer 72" Professional        | ~25€      | Budget, aluminium, 3/8" inclus    |
| Manfrotto Compact Advanced     | ~80€      | Plus robuste, utile si vent fort  |
| K&M 26700 (pied micro)         | ~45€      | Colonne centrale seule, plus stable sur sol dur |

**Recherche Amazon.fr** : "trepied photo aluminium 3/8 pouces" → filtrer >= 150cm, >= 5kg

### Option permanente (terrasse/toit)

- Bride de scellement PVC ∅50 + socle beton 20x20x10cm (~10€ plomberie)
- Plus stable mais non portable

---

## Ordre de cablage (guide pour le boitier Arduino)

Les marqueurs en relief sur le boitier indiquent :

```
Cote droit du boitier (slots de cable) :

  [1 bump]   → Slot D9  → Servo AZ (fil blanc=signal, rouge=5V, noir=GND)
                           Brancher sur D9 de l'Arduino Nano

  [2 bumps]  → Slot D10 → Servo EL (meme code couleur)
                           Brancher sur D10 de l'Arduino Nano

  [3 bumps]  → Slot USB → Cable USB vers laptop (alimentation + serial 9600 baud)
```

**Alimentation servos** : les servos MG996R consomment jusqu'a 2.5A sous charge.
Ne PAS les alimenter depuis le 5V de l'Arduino Nano (limite 500mA via USB).
Utiliser une alimentation externe 5V/3A (chargeur USB-C PD ou alimentation labo)
branchee directement sur les fils rouge/noir des servos.
Connecter le GND de l'alimentation externe au GND de l'Arduino (masse commune).

---

## Schema electrique simplifie

```
Laptop
  |
  | USB
  |
Arduino Nano
  | D9 PWM ------- Servo AZ (signal)
  | D10 PWM ------ Servo EL (signal)
  | GND ---------- GND commun servos ──┐
                                       |
Alim 5V/3A externe ──────────────────  + → Rouge servos AZ + EL
                                       - → Noir servos AZ + EL (= GND commun)
```

---

## Formats de fichiers

| Format | Dossier  | Usage                                   | Nature                         |
|--------|----------|-----------------------------------------|--------------------------------|
| STL    | `stl/`   | Impression 3D (import direct slicer)    | Maillage triangule (binaire)   |
| STEP   | `step/`  | Echange CAO (FreeCAD, Fusion, SolidWorks) | Solide B-rep ISO-10303-21 AP214 |

Les **12 pieces** sont generees par **`gen_parts_cq.py`** (CadQuery / noyau
OpenCASCADE) : chaque `.stp` est un **vrai solide B-rep parametrique**
(`MANIFOLD_SOLID_BREP`), avec **trous reellement evides** (plus de reperes de
percage), et chaque `.stl` est etanche. Verification a la generation, sur les
12 pieces : relecture STEP dans OpenCASCADE = 1 solide ferme par piece,
`isValid()=True` ; STL = 0 arete non-manifold.

### Qualite / cotation visee (niveau normatif, sans certification)

- Percages a l'**ISO 273** (jeu moyen) : M3 -> ∅3.4, M4 -> ∅4.5, M5 -> ∅5.5 ;
  trous filetables dans le PLA : M3 -> ∅2.6, M2 -> ∅1.8.
- Ajustements : portee chapeau ∅7.8 dans le ∅8 du 608ZZ (jeu 0.2) ; bague pivot
  ∅6.9 emmanchee dans l'alesage ∅7 du bras, alesage ∅6.2 sur axe ∅6.
- Tolerance generale visee **ISO 2768-m**, a confirmer par un tirage d'essai :
  le **retrait PLA (~0.2-0.4%) n'est pas compense** dans les modeles.
- Chanfreins 0.4-0.5 mm sur les entrees d'alesage et aretes exposees.

Attention (rappel) : ni un fichier STL/STEP ni une piece prototype ne sont
« certifies CE/ISO » - la certification vise un produit mis sur le marche ou un
systeme qualite (ISO 9001), pas une geometrie. Le format STEP, lui, est bien
defini par la norme ISO 10303.

### Dependance d'outillage (CadQuery)

CadQuery n'est PAS dans l'environnement Poetry du projet (noyau OpenCASCADE lourd,
sans rapport avec le paquet `satrx`). Le regenerer dans un venv dedie :

```
python3 -m venv cadenv
./cadenv/bin/pip install cadquery
./cadenv/bin/python gen_parts_cq.py
```

## Fichiers dans ce dossier

```
docs/f9_rotateur/
  bom_rotateur.md          - ce fichier (nomenclature + references)
  gen_parts_cq.py          - generateur CadQuery unique des 12 pieces (solides B-rep, trous reels)
  prompt_opus_f9.md        - prompt complet pour implémenter F9 en Python
  stl/                     - 12 pieces au format impression
    platine_mat.stl  plateau_az.stl  bras_elevation.stl  collier_antenne.stl
    boitier_arduino.stl  couvercle_arduino.stl  adaptateur_trepied.stl
    support_servo_mg996r.stl  palonnier_servo.stl  chapeau_roulement_az.stl
    bague_pivot_el.stl  serre_cable.stl
  step/                    - les 12 pieces au format CAO (.stp, solides B-rep)
    platine_mat.stp  plateau_az.stp  bras_elevation.stp  collier_antenne.stp
    boitier_arduino.stp  couvercle_arduino.stp  adaptateur_trepied.stp
    support_servo_mg996r.stp  palonnier_servo.stp  chapeau_roulement_az.stp
    bague_pivot_el.stp  serre_cable.stp
  images/
    01_schema_initial.jpeg
    02_antenne_amovible.jpeg
    03_assemblage_etapes.jpeg
    04_en_operation_v1.jpeg
    05_schema_3d.jpeg
    06_en_operation_v2.png
    07_schema_technique_final.jpg   - schema de reference (Gemini, session 23/09/2026)
```
