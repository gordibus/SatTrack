#!/usr/bin/env python3
"""
SatRX F9 - Generateur CAO du rotateur complet (CadQuery / OpenCASCADE).

Source unique des 12 pieces (7 structurelles + 5 interfaces). Remplace l'ancien
`gen_stl_v2.py` (STL facettes, trous en reperes) : ici tout est un solide B-rep
parametrique, les trous sont REELLEMENT evides (booleen 3D), les STEP sont des
`MANIFOLD_SOLID_BREP` (pas un maillage), les STL sont etanches.

Niveau de qualite vise (au sens des normes, sans pretention de certification) :
  - Percages a l'ISO 273 (jeu moyen) : M3 -> ∅3.4, M4 -> ∅4.5, M5 -> ∅5.5 ;
    trous filetables dans le PLA (thread-forming) : M3 -> ∅2.6, M2 -> ∅1.8.
  - Ajustements d'emmanchement documentes (roulement 608ZZ, axe ∅6).
  - Tolerance generale visee : ISO 2768-m (moyenne), a confirmer par un tirage
    d'essai (retrait PLA ~0.2-0.4%, non compense ici).
  - Chanfreins 0.5 mm sur les entrees d'alesage et aretes exposees.

Dependance : CadQuery (noyau OpenCASCADE), hors env Poetry du projet. A executer
dans un venv d'outillage dedie :
    python3 -m venv cadenv && ./cadenv/bin/pip install cadquery
    ./cadenv/bin/python gen_parts_cq.py

Exporte chaque piece en STL (impression) + STEP (.stp, echange CAO).
"""

from __future__ import annotations

import math
from pathlib import Path

import cadquery as cq
from cadquery import exporters


def _polar(radius: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    return radius * math.cos(a), radius * math.sin(a)

HERE = Path(__file__).parent
OUT_STL = HERE / "stl"
OUT_STEP = HERE / "step"
OUT_STL.mkdir(exist_ok=True)
OUT_STEP.mkdir(exist_ok=True)

# -- Diametres de percage (mm) --
M3_CLEAR = 3.4   # ISO 273 jeu moyen
M4_CLEAR = 4.5
M5_CLEAR = 5.5
M3_TAP = 2.6     # filetable dans le PLA
M2_TAP = 1.8
SHAFT_CLEAR = 6.2  # passage arbre / axe ∅6


def _safe_chamfer(part: cq.Workplane, selector: str, size: float) -> cq.Workplane:
    """Chanfrein tolerant : ignore si le selecteur ne renvoie aucune arete valide."""
    try:
        return part.edges(selector).chamfer(size)
    except Exception:
        return part


def export(name: str, part: cq.Workplane) -> None:
    solid = part.val()
    vol = solid.Volume() / 1000.0  # cm^3
    exporters.export(part, str(OUT_STL / f"{name}.stl"), exportType="STL")
    exporters.export(part, str(OUT_STEP / f"{name}.stp"), exportType="STEP")
    print(f"  {name:<24s} vol={vol:6.2f} cm3  -> STL + STEP")


def _box(dx: float, dy: float, dz: float, at: tuple[float, float, float] = (0, 0, 0),
         rot_z: float = 0.0) -> cq.Workplane:
    """Boite (base a z=0 dans son repere) translatee puis tournee autour de Z."""
    b = cq.Workplane("XY").box(dx, dy, dz, centered=(True, True, False)).translate(at)
    return b.rotate((0, 0, 0), (0, 0, 1), rot_z) if rot_z else b


def _cyl_x(r: float, length: float, at: tuple[float, float, float]) -> cq.Workplane:
    """Cylindre d'axe X CENTRE sur `at` (percage/pivot/bossage horizontal traversant)."""
    ax, ay, az = at
    return cq.Workplane("YZ").circle(r).extrude(length).translate((ax - length / 2, ay, az))


# ════════════════════════════════════════════════════════════════════════════
#  SET STRUCTUREL (1-7)
# ════════════════════════════════════════════════════════════════════════════

# ── 1. Platine de mat ───────────────────────────────────────────────────────
# Anneau ∅120/∅52 h10 + collerette ∅62/∅52 h3, 4 oreilles pour colliers PVC.


def make_platine_mat() -> cq.Workplane:
    part = cq.Workplane("XY").circle(60).circle(26).extrude(10)
    part = part.union(cq.Workplane("XY").workplane(offset=10).circle(31).circle(26).extrude(3))
    for a in (0, 90, 180, 270):
        part = part.union(_box(30, 18, 10, at=(0, 64, 0), rot_z=a))
        hole = cq.Workplane("XY").circle(2.0).extrude(10).translate((0, 64, 0))
        part = part.cut(hole.rotate((0, 0, 0), (0, 0, 1), a))
    return part


# ── 2. Plateau rotatif AZ ───────────────────────────────────────────────────
# Disque ∅100 h12, alesage ∅22 (siege bague ext 608ZZ), 4 nervures, plot servo.


def make_plateau_az() -> cq.Workplane:
    part = cq.Workplane("XY").circle(50).circle(11).extrude(12)
    part = part.union(cq.Workplane("XY").workplane(offset=5).circle(13.5).circle(11).extrude(7))
    for a in (0, 90, 180, 270):
        part = part.union(_box(4, 34, 12, at=(0, 30, 0), rot_z=a))
    part = part.union(_box(40, 30, 8, at=(33, 0, 12)))
    for sx, sy in ((18, -10), (48, -10), (18, 10), (48, 10)):
        part = part.cut(
            cq.Workplane("XY").workplane(offset=12).moveTo(sx, sy).circle(M3_CLEAR / 2).extrude(8)
        )
    return part


# ── 3. Bras d'elevation (x2) ────────────────────────────────────────────────
# Pied 80x30x8, montant 8x30x70, tete a bossage perce ∅7 HORIZONTAL (axe elev.),
# 2 goussets. Correction vs v2 : l'alesage de pivot est horizontal (l'axe ∅6 est
# horizontal), coherent avec bague_pivot_el et le collier.


def make_bras_elevation() -> cq.Workplane:
    part = cq.Workplane("XY").box(80, 30, 8, centered=(True, True, False))
    part = part.union(cq.Workplane("XY").box(8, 30, 70, centered=(True, True, False)))
    # tete : bossage cylindrique d'axe X a z=66
    part = part.union(_cyl_x(10, 10, at=(0, 0, 66)))
    part = part.cut(_cyl_x(3.5, 14, at=(0, 0, 66)))          # alesage ∅7 pivot
    # 2 goussets triangulaires (± X)
    for sign in (1, -1):
        rib = (
            cq.Workplane("XZ").polyline([(4 * sign, 8), (4 * sign, 40), (22 * sign, 8)])
            .close().extrude(15).translate((0, 15, 0))
        )
        part = part.union(rib)
    # 4 trous de fixation du pied (M4)
    for cx, cy in ((-32, -10), (-32, 10), (32, -10), (32, 10)):
        part = part.cut(cq.Workplane("XY").moveTo(cx, cy).circle(M4_CLEAR / 2).extrude(8))
    return part


# ── 4. Collier antenne Yagi ─────────────────────────────────────────────────
# Collier ∅33/∅25 h30 fendu (serrage boom Yagi ∅25), 2 oreilles de serrage M3,
# lug de pivot avec alesage ∅6 horizontal cote bras.


def make_collier_antenne() -> cq.Workplane:
    part = cq.Workplane("XY").circle(16.5).circle(12.5).extrude(30)
    # fente de serrage (cote +Y)
    part = part.cut(_box(2, 8, 30, at=(0, 12.5, 0)))
    # 2 oreilles de serrage de part et d'autre de la fente
    for sx in (-1, 1):
        part = part.union(_box(6, 8, 30, at=(sx * 5, 16, 0)))
    # trou de serrage M3 traversant les 2 oreilles (axe X)
    part = part.cut(_cyl_x(M3_CLEAR / 2, 20, at=(0, 16, 15)))
    # lug de pivot cote -Y + alesage ∅6 horizontal (axe X)
    part = part.union(_box(16, 8, 12, at=(0, -18, 9)))
    part = part.cut(_cyl_x(3.1, 20, at=(0, -18, 15)))
    return part


# ── 5. Boitier Arduino Nano ─────────────────────────────────────────────────
# 72x45x35 ext, paroi 2.5mm (coque reelle, cavite evidee). 3 fentes cables +
# 4 plots de montage + marqueurs en relief 1/2/3 bumps (D9/D10/USB).


def make_boitier_arduino() -> cq.Workplane:
    part = cq.Workplane("XY").box(72, 45, 35, centered=(True, True, False)).faces(">Z").shell(-2.5)
    slots_y = ((-18, -12), (-5, 1), (10, 19))
    # fentes cables sur la paroi +X (x=36), z 10..20
    for y0, y1 in slots_y:
        part = part.cut(
            cq.Workplane("XY").box(8, y1 - y0, 10, centered=(True, True, True)).translate(
                (36, (y0 + y1) / 2, 15)
            )
        )
    # 4 plots de montage Arduino perces M2.5
    for px, py in ((-20, -6.5), (-20, 6.5), (20, -6.5), (20, 6.5)):
        part = part.union(
            cq.Workplane("XY").workplane(offset=2.5).moveTo(px, py).circle(2.5).extrude(3)
        )
        part = part.cut(
            cq.Workplane("XY").workplane(offset=2.5).moveTo(px, py).circle(1.3).extrude(3)
        )
    # marqueurs en relief (1/2/3 bumps) a cote des fentes, sur l'exterieur +X
    for n_bumps, (y0, y1) in zip((1, 2, 3), slots_y):
        yc = (y0 + y1) / 2
        for i in range(n_bumps):
            by = yc - (n_bumps - 1) * 2.25 + i * 4.5
            part = part.union(_box(1.5, 3, 3, at=(36, by, 24)))
    return part


# ── 6. Couvercle Arduino ────────────────────────────────────────────────────
# Plaque 72x45x3 + jupe d'insertion interieure + 4 trous M3.


def make_couvercle_arduino() -> cq.Workplane:
    part = cq.Workplane("XY").box(72, 45, 3, centered=(True, True, False))
    skirt = (
        cq.Workplane("XY").rect(71.4, 44.4).rect(67.4, 40.4).extrude(-4)
    )
    part = part.union(skirt)
    for cx, cy in ((-30, -18), (30, -18), (-30, 18), (30, 18)):
        part = part.cut(cq.Workplane("XY").moveTo(cx, cy).circle(M3_CLEAR / 2).extrude(3))
    return part


# ── 7. Adaptateur trepied photo -> mat PVC ──────────────────────────────────
# Socle 80x80x8 perce 3/8" (∅10) + 4 trous M5, collier ∅70/∅52 h40 fendu, 2xM4.


def make_adaptateur_trepied() -> cq.Workplane:
    part = cq.Workplane("XY").box(80, 80, 8, centered=(True, True, False))
    part = part.cut(cq.Workplane("XY").circle(5.0).extrude(8))           # 3/8" ∅10
    for cx, cy in ((-30, -30), (30, -30), (-30, 30), (30, 30)):
        part = part.cut(cq.Workplane("XY").moveTo(cx, cy).circle(M5_CLEAR / 2).extrude(8))
    part = part.union(cq.Workplane("XY").workplane(offset=8).circle(35).circle(26).extrude(40))
    # fente de serrage (+Y) : demarre a y=24 (dans l'alesage ∅52) pour trancher la
    # paroi sans tangence (evite une arete non-manifold au point x=0,y=26).
    part = part.cut(_box(2, 16, 40, at=(0, 32, 8)))
    # 2 trous M4 de serrage radial (±X, a y=0, a l'ecart de la fente)
    part = part.cut(_cyl_x(M4_CLEAR / 2, 80, at=(0, 0, 28)))
    return part


# ════════════════════════════════════════════════════════════════════════════
#  SET INTERFACES (8-12)
# ════════════════════════════════════════════════════════════════════════════

# ── 8. Berceau servo MG996R (AZ et EL, x2) ──────────────────────────────────
# Corps MG996R 40.7 x 19.7mm, pattes entraxe 49.5mm. Le servo descend dans le
# berceau, ses pattes reposent sur les abouts, vissees M2.6 (thread-forming).
# Sortie de cable par une fente laterale.


def make_support_servo_mg996r() -> cq.Workplane:
    base = cq.Workplane("XY").box(60, 44, 4, centered=(True, True, False))
    cradle = (
        cq.Workplane("XY").workplane(offset=4).box(54, 26, 30, centered=(True, True, False))
    )
    part = base.union(cradle)
    # Logement servo (ouvert vers le haut), plancher a z=8 (jeu 0.3mm/cote)
    pocket = (
        cq.Workplane("XY").workplane(offset=8).box(41.3, 20.3, 40, centered=(True, True, False))
    )
    part = part.cut(pocket)
    # Fente de sortie cable dans l'about X- (largeur 8mm)
    cable = (
        cq.Workplane("XY")
        .workplane(offset=9)
        .box(16, 8, 12, centered=(True, True, False))
        .translate((-23, 0, 0))
    )
    part = part.cut(cable)
    # Trous de vissage des pattes servo (entraxe 49.5mm) : M2.6 filetable
    for px in (-24.75, 24.75):
        hole = (
            cq.Workplane("XY").workplane(offset=34).moveTo(px, 0).circle(M2_TAP / 2).extrude(-9)
        )
        part = part.cut(hole)
    # 4 trous embase M3 (fixation sur plateau / bras)
    for cx, cy in ((-24, -16), (24, -16), (-24, 16), (24, 16)):
        part = part.cut(
            cq.Workplane("XY").moveTo(cx, cy).circle(M3_CLEAR / 2).extrude(4)
        )
    part = _safe_chamfer(part, "|Z and >Z", 0.5)
    return part


# ── 9. Palonnier d'accouplement (AZ et EL, x2) ──────────────────────────────
# Disque ∅24 x6mm : alesage central pour l'arbre, 2 vis vers le palonnier OEM,
# 4 vis M3 vers la piece entrainee (plateau AZ / collier).


def make_palonnier_servo() -> cq.Workplane:
    part = cq.Workplane("XY").circle(12).extrude(6)
    part = part.faces(">Z").workplane().hole(SHAFT_CLEAR)          # arbre servo ∅6.2
    # 2 vis palonnier OEM (thread-forming M2) a R5
    for a in (0, 180):
        hx, hy = _polar(5, a)
        part = part.cut(
            cq.Workplane("XY").moveTo(hx, hy).circle(M2_TAP / 2).extrude(6)
        )
    # 4 vis M3 vers la piece entrainee a R8
    for a in (0, 90, 180, 270):
        hx, hy = _polar(8, a)
        part = part.cut(
            cq.Workplane("XY").moveTo(hx, hy).circle(M3_CLEAR / 2).extrude(6)
        )
    part = _safe_chamfer(part, ">Z", 0.5)
    part = _safe_chamfer(part, "<Z", 0.5)
    return part


# ── 10. Chapeau de roulement AZ (top-hat 608ZZ) ─────────────────────────────
# Bloque axialement le 608ZZ (∅22/∅8/h7). Flasque ∅30 sur la bague interieure,
# portee ∅7.8 dans l'alesage ∅8, percage M5 central.


def make_chapeau_roulement_az() -> cq.Workplane:
    part = (
        cq.Workplane("XY")
        .circle(15).extrude(3)                     # flasque ∅30 x3
        .faces(">Z").workplane()
        .circle(3.9).extrude(7)                    # portee ∅7.8 x7 (jeu 0.2 dans ∅8)
    )
    part = part.faces(">Z").workplane().hole(M5_CLEAR)   # percage M5 traversant
    # Pas de chanfrein ici : sur ce top-hat les selecteurs >Z/<Z attrapent des
    # aretes ambigues et degradent le solide en coque. Le jeu d'emmanchement
    # (0.2mm dans le ∅8 du 608ZZ) suffit au guidage.
    return part


# ── 11. Bague de pivot d'elevation (x2) ─────────────────────────────────────
# Bague epaulee : flasque ∅12, fut ∅6.9 (emmanche dans l'alesage ∅7 du bras),
# alesage ∅6.2 pour l'axe inox ∅6.


def make_bague_pivot_el() -> cq.Workplane:
    part = (
        cq.Workplane("XY")
        .circle(6).extrude(2)                      # collerette ∅12 x2
        .faces(">Z").workplane()
        .circle(3.45).extrude(8)                   # fut ∅6.9 x8
    )
    part = part.faces(">Z").workplane().hole(SHAFT_CLEAR)   # alesage ∅6.2
    part = _safe_chamfer(part, ">Z", 0.4)
    part = _safe_chamfer(part, "<Z", 0.4)
    return part


# ── 12. Serre-cable / peigne guide-cable ────────────────────────────────────
# Embase 30x12 percee 2xM3, peigne 4 dents + toit -> 3 canaux (servo AZ/EL/USB).


def make_serre_cable() -> cq.Workplane:
    part = cq.Workplane("XY").box(30, 12, 3, centered=(True, True, False))
    for tx in (-12, -4, 4, 12):                    # 4 dents
        tooth = (
            cq.Workplane("XY").workplane(offset=3)
            .box(3, 12, 9, centered=(True, True, False)).translate((tx, 0, 0))
        )
        part = part.union(tooth)
    roof = (
        cq.Workplane("XY").workplane(offset=12).box(30, 12, 3, centered=(True, True, False))
    )
    part = part.union(roof)
    for cx in (-11, 11):                            # fixation M3
        part = part.cut(
            cq.Workplane("XY").moveTo(cx, 0).circle(M3_CLEAR / 2).extrude(3)
        )
    return part


PARTS = [
    # structurelles
    ("platine_mat", make_platine_mat),
    ("plateau_az", make_plateau_az),
    ("bras_elevation", make_bras_elevation),
    ("collier_antenne", make_collier_antenne),
    ("boitier_arduino", make_boitier_arduino),
    ("couvercle_arduino", make_couvercle_arduino),
    ("adaptateur_trepied", make_adaptateur_trepied),
    # interfaces
    ("support_servo_mg996r", make_support_servo_mg996r),
    ("palonnier_servo", make_palonnier_servo),
    ("chapeau_roulement_az", make_chapeau_roulement_az),
    ("bague_pivot_el", make_bague_pivot_el),
    ("serre_cable", make_serre_cable),
]


if __name__ == "__main__":
    print("SatRX F9 - Generation CAO (CadQuery, solides B-rep + trous reels)")
    print("-" * 64)
    for part_name, builder in PARTS:
        export(part_name, builder())
    print("-" * 64)
    print(f"STL  -> {OUT_STL}/")
    print(f"STEP -> {OUT_STEP}/ (solides parametriques)")
