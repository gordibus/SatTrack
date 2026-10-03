# Introduction aux satellites

> Document pedagogique de reference pour le projet SatRX. Objectif : comprendre, du principe physique le plus elementaire jusqu'aux questions de securite et de droit, comment un satellite emet un signal, pourquoi il le fait a telle frequence plutot qu'une autre, et comment ce signal finit par etre capte par notre chaine de reception (HackRF, demodulation, decodage). Les sections 11 et suivantes font explicitement le lien avec le code et les documents deja produits dans ce depot.

---

## 1. Preambule - de la radio terrestre au satellite

### 1.1 Rappel : onde radio, frequence, longueur d'onde

Une onde radio est une onde electromagnetique : un champ electrique et un champ magnetique qui s'entretiennent mutuellement et se propagent dans le vide a la vitesse de la lumiere (c ≈ 299 792 458 m/s), sans avoir besoin d'un support materiel comme l'air ou l'eau. Deux grandeurs la caracterisent completement : sa frequence f, exprimee en hertz (nombre d'oscillations par seconde), et sa longueur d'onde λ, la distance parcourue pendant une oscillation complete. Les deux sont liees par λ = c / f. Plus la frequence est elevee, plus la longueur d'onde est courte : un signal a 137 MHz (LRPT) a une longueur d'onde d'environ 2,19 metres, tandis qu'un signal a 12 GHz (television par satellite en bande Ku) a une longueur d'onde de 2,5 centimetres. Cette relation n'est pas un detail academique : elle dicte directement la taille physique des antennes necessaires pour recevoir efficacement chaque signal (une antenne efficace a des dimensions de l'ordre d'une fraction de la longueur d'onde, typiquement λ/4 ou λ/2), ce qui explique pourquoi une antenne VHF mesure plusieurs dizaines de centimetres alors qu'une antenne bande Ku tient dans une parabole de quelques dizaines de centimetres de diametre avec un cornet minuscule.

### 1.2 Radio terrestre classique : la limite de la ligne de vue

Une emission radio terrestre classique (FM, television hertzienne, talkie-walkie, WiFi) se heurte a une limite physique fondamentale au-dela d'une certaine frequence : la Terre est courbe, et les frequences superieures a quelques dizaines de MHz ne se reflechissent plus sur l'ionosphere (contrairement aux ondes decametriques HF utilisees historiquement pour les liaisons transocean­iques). Elles se propagent en ligne de vue quasi directe (propagation dite "espace libre" ou "line of sight"), avec une portee au sol limitee par l'horizon radioelectrique : pour un emetteur a 30 metres de hauteur recu par une antenne au niveau du sol, la portee typique ne depasse guere 20 a 25 kilometres avant que la courbure terrestre n'interrompe la ligne de vue directe. C'est pourquoi la radiodiffusion terrestre repose sur un maillage dense de pylones (rehausser l'emetteur repousse l'horizon radioelectrique, la portee croissant approximativement avec la racine carree de la hauteur), et pourquoi la couverture d'un territoire entier necessite des dizaines, voire des centaines d'emetteurs relais.

### 1.3 L'idee du relais spatial

Un satellite renverse ce probleme en placant l'emetteur (ou le relais) a une altitude telle que l'horizon radioelectrique englobe un territoire immense d'un seul coup. Un satellite en orbite basse a 800 km d'altitude "voit" un disque au sol de plusieurs milliers de kilometres de diametre ; un satellite geostationnaire a 35 786 km voit environ un tiers de la surface du globe en permanence. Le compromis est le suivant : plus le satellite est haut, plus sa couverture est large et stable dans le temps, mais plus la distance a parcourir est grande, donc plus le signal recu au sol est affaibli (voir 3.3) et plus la latence de propagation augmente (environ 240 millisecondes aller-retour pour un lien geostationnaire, contre quelques millisecondes pour un lien en orbite basse).

### 1.4 Comparaison directe : pylone terrestre vs satellite

Le principe electromagnetique est rigoureusement identique entre un pylone de television hertzienne et un satellite de diffusion : un emetteur module un signal sur une porteuse, une antenne le rayonne, un recepteur au sol le capte et le demodule. La seule difference structurelle est la position du relais : au sol, contraint par la courbure terrestre et les obstacles (batiments, relief, vegetation) ; dans l'espace, libere de ces contraintes mais soumis a des contraintes propres extremement severes (vide, rayonnement, temperature, alimentation en energie, absence de maintenance possible une fois lance). Un satellite de telecommunications geostationnaire peut ainsi remplacer, pour la diffusion television, un nombre considerable d'emetteurs terrestres avec une seule infrastructure orbitale - au prix d'un cout de fabrication et de lancement sans commune mesure avec un pylone.

---

## 2. A quoi sert un satellite

### 2.1 Les grandes familles d'usage

On distingue generalement six grandes familles de satellites artificiels selon leur mission :

- **Telecommunications** : relais de television, de telephonie, d'internet (VSAT, megaconstellations comme Starlink), de radio. Le satellite recoit un signal, le retransmet (transpondeur, voir 5.7).
- **Navigation (GNSS - Global Navigation Satellite System)** : GPS (Etats-Unis), Galileo (Union europeenne), GLONASS (Russie), BeiDou (Chine). Le satellite ne fait que diffuser un signal horodate avec une precision extreme (voir 5.6) ; c'est le recepteur au sol qui calcule sa position par triangulation.
- **Observation de la Terre / imagerie** : satellites civils (Pleiades, Sentinel), militaires (reconnaissance), agricoles, cartographiques.
- **Meteorologie** : Meteor-M et NOAA POES (orbite basse polaire), Meteosat et GOES (orbite geostationnaire) - ce sont precisement les familles de satellites que ce projet recoit et decode.
- **Science et exploration** : telescopes spatiaux (Hubble, James Webb), sondes d'etude de la Terre (gravimetrie, climat), stations habitees (ISS).
- **Militaire et gouvernemental** : reconnaissance, communications securisees, alerte precoce - hors de portee et hors perimetre legal de ce projet.

### 2.2 Pourquoi certains usages doivent etre spatiaux

Tous les usages ne justifient pas necessairement une infrastructure orbitale, dont le cout de fabrication, de lancement et d'assurance reste tres eleve compare a une infrastructure terrestre equivalente. Le spatial s'impose principalement dans trois cas : lorsque la couverture doit etre globale et uniforme (navigation GNSS, qui n'aurait aucun sens avec des emetteurs terrestres discontinus au-dessus des oceans) ; lorsque la zone a couvrir est physiquement inaccessible ou trop vaste pour une infrastructure terrestre dense (regions polaires, oceans, zones desertiques) ; et lorsque la vue globale et repetee est la donnee elle-meme (meteorologie, observation de la Terre, ou seule une plateforme en altitude peut fournir une image synoptique reguliere d'un hemisphere entier). A l'inverse, pour une desserte internet urbaine dense, la fibre optique terrestre reste largement plus performante et moins couteuse par utilisateur ; le satellite y devient pertinent surtout en complement, pour les zones non couvertes par un reseau terrestre.

---

## 3. Comment ca fonctionne - la liaison satellite

### 3.1 Liaison montante et liaison descendante

Une liaison satellite bidirectionnelle se decompose en deux trajets distincts, presque toujours a des frequences differentes : la **liaison montante** (uplink), du sol vers le satellite, et la **liaison descendante** (downlink), du satellite vers le sol. Utiliser deux frequences differentes evite que l'emetteur puissant au sol ne sature le recepteur du satellite ou que le signal descendant, beaucoup plus faible, ne soit noye par la retransmission montante sur la meme bande (probleme dit d'auto-interference ou de "duplexage"). Pour un satellite purement diffusant comme Meteor-M ou NOAA (pas de liaison montante utilisateur, seulement une commande de telemetrie/telecommande depuis une station de controle dediee), on ne s'interesse en pratique qu'a la liaison descendante - c'est elle que ce projet recoit.

### 3.2 Le trajet complet du signal

Le trajet type d'un signal de diffusion satellite suit la chaine suivante : un instrument de mesure a bord (radiometre pour l'imagerie meteo, capteur de telemetrie pour l'etat du satellite) produit des donnees numeriques ; ces donnees sont mises en trame, codees pour la correction d'erreur (Viterbi, Reed-Solomon - voir la reimplementation faite dans `src/satrx/decode/`), modulees sur une porteuse RF (QPSK pour LRPT, FM analogique pour APT), puis rayonnees par l'antenne du satellite. Au sol, une antenne captee un signal extremement affaibli, un LNA (amplificateur faible bruit) le remonte au-dessus du plancher de bruit du recepteur, un SDR (HackRF dans notre cas) le numerise, et une chaine logicielle inverse chaque etape (demodulation, decodage FEC, degroupage des trames, reconstruction d'image) pour retrouver les donnees d'origine.

### 3.3 Affaiblissement de parcours (free-space path loss)

La puissance d'un signal radio decroit avec le carre de la distance parcourue en espace libre. La formule de Friis exprime cet affaiblissement en decibels : `FSPL(dB) = 20·log10(d) + 20·log10(f) + 32,44` (d en kilometres, f en MHz). Pour un satellite en orbite basse a 800 km observe pres du zenith, avec une frequence de 137,9 MHz, cet affaiblissement atteint deja environ 137 dB - c'est-a-dire que la puissance recue represente une fraction de l'ordre de 10⁻¹⁴ de la puissance emise. C'est la raison directe pour laquelle le rapport signal/bruit mesure sur nos captures reelles (NOAA 18 : +4,4 dB ; NOAA 19 : +1,5 dB, cf. `CONTEXT.md`) est si faible malgre une puissance d'emission de plusieurs watts a bord du satellite, et pourquoi le choix de l'antenne (gain, directivite, polarisation) devient determinant plutot qu'un simple detail de confort.

### 3.4 Effet Doppler

Un satellite en orbite basse se deplace a une vitesse relative au sol de l'ordre de 7 a 7,5 km/s. Cette vitesse, projetee sur l'axe reliant le satellite au recepteur, produit un decalage Doppler de la frequence percue : le signal est recu plus haut en frequence lorsque le satellite s'approche, plus bas lorsqu'il s'eloigne, avec un passage par la frequence nominale au point de plus courte distance (l'instant du passage au plus pres, pas necessairement au zenith geometrique). Pour Meteor-M a 137,9 MHz, ce decalage peut atteindre plusieurs kilohertz en debut et fin de passage, ce qui deplace significativement le signal hors de la bande de capture etroite d'un recepteur non corrige. C'est exactement ce que corrige le module `tracking/` du projet (F2) : a partir des elements orbitaux (TLE) et de la position de la station sol, il precalcule la vitesse radiale du satellite a chaque instant du passage et applique la correction de frequence correspondante.

### 3.5 Le segment sol

On appelle "segment sol" l'ensemble des infrastructures terrestres necessaires a l'exploitation d'un satellite : stations de reception (antennes, recepteurs), centres de controle (envoi de telecommande, suivi de sante du satellite), et reseaux de distribution des donnees recues. Pour un operateur professionnel, le segment sol comprend generalement plusieurs stations reparties sur le globe pour maximiser le temps de contact avec les satellites en orbite basse (dont la visibilite depuis un point donne est intermittente, voir 4.6). Dans ce projet, le segment sol se reduit a une seule station amateur (HackRF, antenne, ordinateur), ce qui est representatif d'un cas d'usage radioamateur/observation plutot que d'une exploitation operationnelle.

---

## 4. Les orbites

### 4.1 Orbite basse - LEO (Low Earth Orbit)

L'orbite basse s'etend approximativement de 400 a 2000 kilometres d'altitude. C'est la plus proche de la Terre, donc celle qui offre le signal le plus fort a puissance d'emission egale, mais aussi celle dont la couverture d'un point donne au sol est la plus breve et la plus intermittente : un satellite LEO n'est visible depuis une station fixe que quelques minutes par passage, plusieurs fois par jour. Meteor-M, NOAA POES, Iridium, Starlink et la Station spatiale internationale evoluent tous en LEO.

### 4.2 Orbite moyenne - MEO (Medium Earth Orbit)

Autour de 20 000 kilometres d'altitude, l'orbite moyenne est le domaine quasi exclusif des constellations de navigation : GPS orbite a environ 20 200 km, Galileo a environ 23 222 km. A cette altitude, un satellite reste visible depuis un point au sol pendant plusieurs heures, et une constellation d'une trentaine de satellites suffit a garantir une couverture mondiale continue avec plusieurs satellites visibles simultanement partout sur le globe - condition necessaire au calcul de position par triangulation.

### 4.3 Orbite geostationnaire - GEO

A 35 786 kilometres d'altitude exactement au-dessus de l'equateur, un satellite parcourt son orbite en 23 heures 56 minutes et 4 secondes - precisement la duree d'une rotation siderale de la Terre. Vu depuis le sol, il apparait donc immobile en permanence au meme point du ciel, ce qui permet de pointer une antenne au sol une fois pour toutes sans systeme de poursuite. C'est le domaine des satellites de television par satellite (Astra, Eutelsat), de meteorologie geostationnaire (Meteosat, GOES) et de telecommunications a couverture continentale (Inmarsat, Thuraya). Le revers de cette stabilite est l'altitude elevee, qui impose une puissance d'emission bien plus importante ou une antenne de reception bien plus grande pour compenser l'affaiblissement de parcours.

### 4.4 Orbites elliptiques hautes - HEO

Certaines missions necessitent une couverture prolongee des hautes latitudes, mal desservies par les satellites geostationnaires (dont l'elevation apparente devient tres faible, voire negative, au-dela d'environ 70 degres de latitude). Les orbites de type Molniya, tres elliptiques (perigee bas autour de 500 km, apogee haut autour de 40 000 km) et inclinees a 63,4 degres - l'inclinaison critique qui annule la precession de l'apside due a l'aplatissement terrestre -, passent la majeure partie de leur periode orbitale de 12 heures immobilisees pres de l'apogee, offrant une couverture prolongee des regions polaires. La Russie a historiquement utilise ce type d'orbite pour ses telecommunications aux hautes latitudes ou le geostationnaire est geometriquement desavantageux.

### 4.5 Orbite polaire et orbite heliosynchrone

Une orbite polaire a une inclinaison proche de 90 degres : le satellite survole successivement toutes les latitudes, y compris les poles, alors que la Terre tourne sous lui. Un cas particulier tres utilise en meteorologie et en observation de la Terre est l'orbite **heliosynchrone** : l'inclinaison et l'altitude sont choisies (typiquement autour de 98 degres et 700 a 850 km) de sorte que le plan orbital derive exactement au meme rythme que la Terre tourne autour du Soleil, ce qui garantit que le satellite survole chaque point du globe toujours a la meme heure solaire locale. Cette propriete est essentielle pour la meteorologie : elle garantit un eclairage solaire comparable d'une orbite a l'autre, rendant les images successives directement comparables. Meteor-M et NOAA POES sont tous deux en orbite heliosynchrone.

### 4.6 Vitesse orbitale, periode, et elements orbitaux (TLE)

La vitesse necessaire pour maintenir une orbite circulaire decroit avec l'altitude : environ 7,7 km/s en orbite basse, 3,9 km/s en orbite GPS, 3,07 km/s en orbite geostationnaire - consequence directe de la troisieme loi de Kepler, qui relie le carre de la periode orbitale au cube du demi-grand axe. La position exacte d'un satellite a un instant donne est publiee sous forme de **TLE** (Two-Line Element set), un format normalise par le NORAD qui encode l'ensemble des parametres orbitaux (inclinaison, excentricite, argument du perigee, mouvement moyen, etc.) necessaires a la propagation de la trajectoire via un modele comme SGP4. Ce projet telecharge ces TLE directement depuis CelesTrak (cf. session du 22/08/2026 dans `CONTEXT.md`, TLE de Meteor-M2 3, NORAD 57166) pour calculer les horaires, l'elevation maximale et l'azimut de chaque passage.

---

## 5. Composition technique d'un satellite

### 5.1 Bus et charge utile

Un satellite se decompose fonctionnellement en deux ensembles. Le **bus** (ou plateforme) regroupe toutes les fonctions de support necessaires a la survie et au fonctionnement du satellite : structure mecanique, alimentation electrique, controle thermique, controle d'attitude et de propulsion, telemetrie et telecommande. La **charge utile** (payload) regroupe les instruments qui accomplissent la mission proprement dite : radiometre imageur pour un satellite meteo, transpondeurs pour un satellite de telecommunications, horloge atomique et generateur de signal pour un satellite de navigation. Un meme bus standardise peut porter des charges utiles tres differentes selon la mission, ce qui explique la logique de plateformes satellites reutilisables dans l'industrie spatiale.

### 5.2 Structure et materiaux

La structure d'un satellite doit resister aux vibrations et accelerations extremes du lancement (plusieurs g soutenus, chocs pyrotechniques lors des separations d'etage) tout en restant la plus legere possible, chaque kilogramme lance ayant un cout tres eleve. Les materiaux privilegies sont les alliages d'aluminium (legerete, usinabilite), le titane (resistance thermique et mecanique pour les elements les plus sollicites) et les composites a fibre de carbone (rigidite et legerete pour les panneaux et les structures porteuses). La surface exterieure est generalement recouverte d'un revetement multicouche isolant (MLI - Multi-Layer Insulation), ces feuillets dores ou argentes caracteristiques visibles sur les photographies de satellites, qui limitent les echanges thermiques par rayonnement avec l'environnement spatial.

### 5.3 Alimentation electrique

L'energie electrique d'un satellite provient quasi systematiquement de panneaux solaires photovoltaiques, dimensionnes pour couvrir a la fois la consommation instantanee et la recharge de batteries (generalement lithium-ion aujourd'hui) utilisees durant les phases d'eclipse, lorsque la Terre masque le Soleil. En orbite basse heliosynchrone, ces eclipses sont frequentes et courtes (une par orbite, soit environ toutes les 100 minutes) ; en orbite geostationnaire, elles ne surviennent que pendant des periodes limitees autour des equinoxes. Le dimensionnement du systeme electrique est l'une des contraintes de conception les plus structurantes d'un satellite, car elle limite directement la puissance disponible pour l'emission radio - un facteur qui, combine a l'affaiblissement de parcours (3.3), explique pourquoi les signaux satellite recus au sol restent toujours tres faibles.

### 5.4 Regulation thermique

Dans le vide spatial, il n'existe aucune convection : les seuls mecanismes d'echange thermique sont la conduction (entre elements en contact physique) et le rayonnement. Un satellite est simultanement expose a un flux solaire intense sur sa face eclairee et au froid radiatif de l'espace profond (environ 2,7 kelvins) sur sa face opposee, ce qui cree des gradients thermiques extremes. La regulation thermique repose sur une combinaison de revetements passifs (MLI, peintures a emissivite controlee), de radiateurs dedies evacuant la chaleur produite par l'electronique interne, et parfois de systemes actifs (caloducs, resistances chauffantes) pour maintenir chaque sous-systeme dans sa plage de temperature de fonctionnement.

### 5.5 Propulsion et maintien a poste

La plupart des satellites embarquent un systeme de propulsion, non pas pour atteindre leur orbite (role reserve au lanceur), mais pour la corriger et la maintenir dans le temps. Les perturbations orbitales (aplatissement terrestre, attraction lunisolaire, pression de radiation solaire, trainee residuelle de l'atmosphere en orbite basse) devient progressivement un satellite de sa position nominale. Pour un satellite geostationnaire, dont la position doit rester tres precisement fixee dans une fenetre orbitale attribuee (voir 9.2), des manœuvres de maintien a poste regulieres sont indispensables et consomment un ergol embarque en quantite finie, dont l'epuisement marque generalement la fin de vie operationnelle du satellite.

### 5.6 Horloge atomique embarquee

Les satellites de navigation (GPS, Galileo, GLONASS, BeiDou) embarquent des horloges atomiques (au rubidium ou au cesium) d'une stabilite extreme, de l'ordre de 10⁻¹³ a 10⁻¹⁴ en valeur relative, soit une derive de quelques nanosecondes par jour. Cette precision est indispensable au principe meme de la navigation par satellite : le recepteur au sol calcule sa position en mesurant le temps de propagation du signal depuis plusieurs satellites simultanement (la lumiere parcourant environ 30 centimetres par nanoseconde, une erreur d'horloge de quelques nanosecondes se traduit directement par une erreur de position de plusieurs metres). Un phenomene remarquable, verifiable empiriquement grace a cette precision, est la necessite de corriger les effets de la relativite restreinte et de la relativite generale : la vitesse orbitale du satellite ralentit son horloge d'environ 7,2 microsecondes par jour (relativite restreinte), tandis que le champ gravitationnel plus faible en altitude l'accelere d'environ 45,7 microsecondes par jour (relativite generale) ; l'effet net, environ +38,6 microsecondes par jour, est corrige en reglant la frequence nominale de l'horloge legerement plus bas avant le lancement (10,22999999543 MHz au lieu de 10,23 MHz pour le GPS) de sorte qu'elle affiche la bonne frequence une fois en orbite. Sans cette correction, l'erreur de positionnement cumulee atteindrait plusieurs kilometres par jour.

### 5.7 Antennes et electronique de communication embarquees

La charge utile de communication d'un satellite de telecommunications repose sur des **transpondeurs** : chaque transpondeur recoit un signal montant sur une frequence donnee, le filtre, l'amplifie (generalement via un tube a ondes progressives ou un amplificateur a etat solide) et le retransmet sur une frequence descendante decalee. Les antennes embarquees varient fortement selon la mission : antennes omnidirectionnelles simples pour la telemetrie de base, reflecteurs paraboliques formant des faisceaux etroits (spot beams) pour concentrer la puissance sur une zone geographique precise et reutiliser les memes frequences sur des zones differentes, ou reseaux phases pour un pointage electronique sans piece mobile.

### 5.8 Lancement et mise a poste

Un satellite est place en orbite par un lanceur (fusee), dont la coiffe le protege des contraintes aerodynamiques et thermiques durant la traversee de l'atmosphere. Selon l'orbite visee, un ou plusieurs etages du lanceur puis, frequemment, un moteur d'apogee propre au satellite realisent les manœuvres necessaires pour passer d'une orbite de transfert elliptique a l'orbite operationnelle finale (circularisation pour le GEO, ajustement d'inclinaison, etc.). Cette phase reste l'une des plus risquees du cycle de vie d'un satellite, la grande majorite des echecs de mission spatiale intervenant lors du lancement ou de la mise a poste initiale.

---

## 6. Les frequences utilisees, par bande normalisee

### 6.1 Nomenclature des bandes

Le spectre radioelectrique utilise pour les communications satellite est decoupe en bandes normalisees, historiquement designees par des lettres dont l'origine remonte a la Seconde Guerre mondiale (nomenclature radar) :

| Bande | Plage approximative | Longueur d'onde |
|---|---|---|
| VHF | 30 - 300 MHz | 1 - 10 m |
| UHF | 300 MHz - 1 GHz | 30 cm - 1 m |
| L | 1 - 2 GHz | 15 - 30 cm |
| S | 2 - 4 GHz | 7,5 - 15 cm |
| C | 4 - 8 GHz | 3,75 - 7,5 cm |
| X | 8 - 12 GHz | 2,5 - 3,75 cm |
| Ku | 12 - 18 GHz | 1,7 - 2,5 cm |
| Ka | 26,5 - 40 GHz | 0,75 - 1,1 cm |

### 6.2 Le compromis frequence / atmosphere / taille d'antenne

Le choix d'une bande pour une mission donnee resulte toujours d'un compromis entre plusieurs contraintes physiques opposees. Les basses frequences (VHF, UHF, bande L) traversent l'atmosphere avec tres peu d'attenuation, y compris par mauvais temps, ce qui les rend fiables pour des liaisons critiques (telemetrie, navigation, detresse), mais elles exigent des antennes de reception relativement grandes pour obtenir un gain suffisant, et la largeur de bande disponible y est etroite (donc le debit de donnees transportable est limite). A l'inverse, les hautes frequences (Ku, Ka) permettent des antennes compactes a fort gain (paraboles de quelques dizaines de centimetres) et offrent une largeur de bande considerable, donc des debits eleves - au prix d'une sensibilite marquee a l'attenuation atmospherique, en particulier a l'affaiblissement par la pluie (rain fade), qui peut interrompre une liaison Ka lors d'un orage. C'est ce compromis qui explique pourquoi la meteorologie et la navigation, qui exigent une fiabilite maximale, restent en bande L/S/UHF, tandis que la television par satellite haut debit a bascule vers le Ku puis le Ka.

### 6.3 Tableau recapitulatif par usage

| Usage | Frequence typique | Bande | Satellites concernes |
|---|---|---|---|
| LRPT (imagerie meteo LEO) | 137,1 - 137,9 MHz | VHF | Meteor-M |
| APT (imagerie meteo LEO, analogique) | 137,1 - 137,9125 MHz | VHF | NOAA POES |
| HRPT (imagerie meteo LEO, haute resolution) | ~1,7 GHz | Bande L | Meteor-M, NOAA, FengYun |
| GPS L1 / Galileo E1 | 1575,42 MHz | Bande L | GPS, Galileo |
| Iridium | 1616 - 1626,5 MHz | Bande L | Iridium |
| Inmarsat / Thuraya (GMR-1/GMR-2) | ~1525 - 1660 MHz | Bande L | Inmarsat, Thuraya |
| Television par satellite (Europe, DTH) | 10,7 - 12,75 GHz | Ku | Astra, Eutelsat |
| Liaisons professionnelles haut debit | 26,5 - 40 GHz | Ka | HTS (High Throughput Satellites) |

Ce tableau recoupe directement la grille de selection d'antenne deja etablie pour ce projet : les usages sub-1GHz (LRPT/APT) relevent d'antennes de type television large bande, les usages 1-3GHz (HRPT, GPS, Iridium, GMR-1/GMR-2) relevent d'antennes directionnelles de type WiFi (Yagi ou parabole), et les usages au-dela de 6GHz (television par satellite Ku/Ka) exigent un downconverter LNB.

---

## 7. Panorama des satellites - connus et moins connus

### 7.1 Les tres connus

Le grand public connait principalement les systemes de navigation GPS et, de plus en plus, Galileo ; les bouquets de television par satellite (Astra, Eutelsat, Hotbird) ; les megaconstellations d'acces internet recentes comme Starlink (SpaceX, plusieurs milliers de satellites en orbite basse) ; la Station spatiale internationale, visible a l'œil nu au crepuscule ; et les grands telescopes spatiaux comme Hubble ou James Webb, davantage connus pour leurs images que pour leur fonctionnement radio.

### 7.2 Les moins connus, mais centraux pour ce projet

Ce projet s'appuie sur des satellites beaucoup moins mediatises mais parfaitement accessibles a une station de reception amateur : **Meteor-M** (serie russe de satellites meteorologiques en orbite heliosynchrone, diffusant LRPT en clair a 137,9 MHz - c'est la cible principale de F3) ; **NOAA POES** (serie americaine equivalente, diffusant APT analogique, en fin de vie operationnelle mais encore recue avec succes sur ce projet le 22/08/2026) ; **Iridium** (constellation de telephonie satellite en orbite basse, dont les rafales caracteristiques a 1621 MHz sont detectables sans decodage de contenu, ce dernier etant hors perimetre legal) ; et **Inmarsat/Thuraya**, systemes geostationnaires de telephonie satellite utilisant le protocole GMR-1/GMR-2 etudie dans le volet audit de securite B8 du projet.

### 7.3 Bref historique

Le premier satellite artificiel, **Spoutnik 1**, a ete lance par l'Union sovietique le 4 octobre 1957. Simple sphere de 58 centimetres de diametre et 83,6 kilogrammes, il n'emettait qu'un signal de balise repetitif sur 20,005 et 40,002 MHz, sans aucune charge utile scientifique - mais son lancement a suffi a declencher la course spatiale de la guerre froide et, indirectement, la creation de la NASA des 1958. Les decennies suivantes ont vu se succeder les premiers satellites de telecommunications (Telstar 1, 1962), les premiers satellites meteorologiques (TIROS-1, 1960), le deploiement du GPS a partir des annees 1970-1980, puis, a partir des annees 2010, l'emergence des megaconstellations en orbite basse portees par la baisse spectaculaire du cout de lancement.

---

## 8. Securite des liaisons satellite

### 8.1 Signal en clair contre signal chiffre

Un signal satellite peut etre diffuse en clair, c'est-a-dire sans aucune protection cryptographique, ou protege par un mecanisme de chiffrement. Le choix depend entierement de la mission : les diffusions meteorologiques comme LRPT ou APT sont volontairement en clair par conception, car leur valeur reside precisement dans une distribution la plus large et la plus gratuite possible aupres des services meteorologiques du monde entier - chiffrer ces flux irait a l'encontre de leur objet meme. A l'inverse, les liaisons de telephonie satellite (Inmarsat, Thuraya, Iridium) protegent le contenu des communications par un chiffrement au niveau de la couche radio, dans la mesure ou elles vehiculent des communications privees d'abonnes.

### 8.2 Vulnerabilites documentees

Certains de ces mecanismes de chiffrement, concus il y a plusieurs decennies, presentent des faiblesses cryptographiques aujourd'hui documentees dans la litterature academique de securite - c'est le cas des algorithmes A5/GMR-1 et GMR-2 utilises par les systemes de telephonie satellite geostationnaire, et des algorithmes GEA-1/GEA-2 dans un contexte proche. L'analyse de ces faiblesses, dans un cadre lab strictement autorise (accord operateur, environnement isole), fait l'objet du volet B8 de ce projet ; le rapport complet, avec distinction explicite entre ce qui a ete effectivement teste sur du trafic simule et ce qui reste une vulnerabilite documentee mais non exercee, se trouve dans `docs/audit_b8_lab_report.md`.

### 8.3 Reception passive contre interception active

Une distinction juridique et ethique fondamentale separe deux activites qui peuvent sembler techniquement proches : la **reception passive** d'un signal diffuse ouvertement (comme LRPT, dont l'operateur sait et accepte que quiconque possedant l'equipement adequat puisse le recevoir) est legale sans condition particuliere, exactement comme ecouter une station de radio FM publique. L'**interception active** de communications privees non destinees au public - decoder le contenu d'un appel telephonique Iridium ou Inmarsat sans l'accord de l'abonne concerne - constitue en revanche une atteinte au secret des correspondances, penalement sanctionnee dans la plupart des juridictions (en France, article 226-15 du Code penal), independamment du fait que le signal soit techniquement recevable. Ce projet respecte strictement cette frontiere : la reception de la porteuse Iridium (detection de la presence d'une rafale) est dans le perimetre autorise, le decodage de son contenu ne l'est pas (cf. article 226-15 du Code penal).

---

## 9. Cadre juridique et reglementaire

### 9.1 Le traite de l'espace de 1967

Le **Traite sur les principes regissant les activites des Etats en matiere d'exploration et d'utilisation de l'espace extra-atmospherique** (1967), texte fondateur du droit spatial international, pose deux principes essentiels pour ce projet. L'article II interdit toute appropriation nationale de l'espace extra-atmospherique par revendication de souverainete : aucun Etat ne peut declarer l'espace, ou une portion de celui-ci, comme son territoire. L'article VIII, a l'inverse, precise qu'un Etat conserve sa juridiction et son controle sur tout objet qu'il a lance et immatricule, ou qu'il figure sur son registre national - un satellite reste donc sous la loi de son Etat de lancement meme en orbite. Ces deux articles combines signifient que l'espace n'est pas un vide juridique : un satellite n'est pas hors-la-loi, il est simplement regi par le droit de l'Etat qui l'a immatricule plutot que par un droit territorial classique.

### 9.2 Le role de l'Union internationale des telecommunications (UIT/ITU)

L'**Union internationale des telecommunications**, agence specialisee des Nations unies, attribue au niveau mondial les bandes de frequence utilisables par chaque type de service (fixe, mobile, satellite, radioamateur, etc.) et coordonne les positions orbitales geostationnaires entre Etats membres, au travers de son Reglement des radiocommunications et de conferences mondiales periodiques (les WRC - World Radiocommunication Conferences). Cette coordination est necessaire parce que le spectre radioelectrique et les positions orbitales geostationnaires sont des ressources physiquement limitees et partagees : sans attribution coordonnee, deux operateurs emettant sur la meme frequence depuis des positions orbitales proches interfereraient mutuellement de maniere destructrice. C'est ce cadre qui garantit, par exemple, que la bande 137-138 MHz reste internationalement reservee aux satellites meteorologiques a defilement, permettant a Meteor-M et NOAA d'y emettre sans craindre d'interference d'un autre service.

### 9.3 Reglementation nationale - le cas francais (ANFR)

En France, l'**Agence nationale des frequences (ANFR)** gere l'attribution du spectre radioelectrique au niveau national, en application des decisions de l'UIT, et delivre les licences necessaires a toute emission radio (licence radioamateur, autorisations professionnelles). La reception passive, en revanche, n'est en principe pas soumise a licence : ecouter un signal deja diffuse librement dans l'espace radioelectrique, sans emettre soi-meme, ne constitue pas une activite reglementee au meme titre que l'emission - c'est cette distinction qui permet a ce projet d'operer legalement en reception pure avec un simple SDR, sans autorisation prealable, tout en rappelant qu'emettre (meme a titre experimental) necessiterait une licence radioamateur, hors perimetre actuel du projet.

### 9.4 Perimetre legal du projet

Le cadre legal complet retenu pour ce projet distingue ce qui est toujours autorise (reception passive de diffusions ouvertes), ce qui est autorise sous conditions strictes (audit lab avec accord operateur, B8) et ce qui est explicitement hors perimetre (toute emission non licenciee, toute interception de communication privee sans accord individuel de l'abonne concerne ni ordonnance judiciaire).

---

## 10. Fin de vie et durabilite

### 10.1 Desorbitation et orbite cimetiere

En fin de mission, un satellite en orbite basse epuise generalement le peu de carburant qu'il lui reste pour abaisser son perigee et acceler sa rentree dans l'atmosphere, ou il se consume par frottement (desorbitation controlee ou naturelle sur quelques annees a quelques decennies selon l'altitude residuelle). Un satellite geostationnaire, dont l'energie necessaire pour revenir vers la Terre serait prohibitive, est a l'inverse pousse vers une **orbite cimetiere** situee quelques centaines de kilometres au-dessus de la ceinture geostationnaire operationnelle, afin de liberer sa position orbitale pour un autre satellite sans presenter de risque de collision avec les satellites actifs.

### 10.2 Debris spatiaux et syndrome de Kessler

L'accumulation de satellites hors service, d'etages de fusee abandonnes et de fragments issus de collisions ou d'explosions accidentelles constitue une population croissante de debris orbitaux, suivie et cataloguee (c'est de ce meme catalogue que proviennent les TLE utilises par ce projet pour calculer les passages). Le physicien Donald Kessler a formalise en 1978 un scenario aujourd'hui connu sous le nom de **syndrome de Kessler** : au-dela d'une certaine densite de debris, les collisions entre objets deviennent auto-entretenues - chaque collision produit de nouveaux fragments qui augmentent la probabilite de collisions futures - jusqu'a rendre certaines orbites basses impraticables sur le long terme. Ce risque, longtemps theorique, est devenu un sujet de preoccupation operationnelle avec la multiplication recente des megaconstellations en orbite basse, chacune ajoutant plusieurs milliers d'objets a suivre et a eviter.

---

## 11. Lien avec ce projet (SatRX)

### 11.1 Ce qu'on recoit reellement, et pourquoi ces satellites precisement

Ce projet cible delibitement des satellites en orbite basse heliosynchrone diffusant en clair et en bande VHF (137 MHz), pour trois raisons convergentes directement issues des sections precedentes : l'orbite basse maximise la puissance recue malgre l'affaiblissement de parcours (3.3) ; la bande VHF minimise l'attenuation atmospherique et reste accessible avec une antenne simple (6.2) ; et la diffusion en clair rend le decodage entierement licite sans qu'aucune autorisation operateur ne soit necessaire (8.1, 9.4). Les premieres images reelles obtenues le 22/08/2026 (NOAA 18 et NOAA 19 en APT, cf. `CONTEXT.md`) illustrent concretement cette chaine complete, de l'orbite du satellite jusqu'a l'image meteorologique reconstruite.

### 11.2 Documents techniques associes

Ce document pose les bases theoriques ; les documents suivants, deja produits dans ce depot, approfondissent chacun un aspect specifique deja evoque ici : `docs/analyse_securite_f8.md` (classification clair/protege appliquee aux donnees du projet), `docs/audit_b8_lab_report.md` (cryptanalyse GMR-1 et playbook Blue Team, section 8.2 ci-dessus), et `docs/comparaison_reseau_resilient_f12.md` (comparaison architecturale avec un reseau mesh terrestre, Meshtastic, en contrepoint de la topologie de diffusion satellite decrite en section 3).



Types de Satellite: 
- Communication utilisé pour la radio, tv, internet et téléphone.
- Remote Sensing Climat, géographie, plan et autre...
- Navigation lémétrie, donnée (data incluant la position dans l'espace et le temps), utilisé pour la géolocalisation, ==**Global Navigation Satellite System**== (en français, _Système mondial de navigation par satellite_
- Astronomique utilisé recherche telescope, photo, dans l'espace etc...
