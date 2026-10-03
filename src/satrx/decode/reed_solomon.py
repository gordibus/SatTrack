from __future__ import annotations

import itertools

import numpy as np
from numpy.typing import NDArray

# Polynome primitif CCSDS/Meteor-M confirme (recherche du 16/08/2026, recoupe sur deux
# sources independantes dont une citant verbatim un design technique LRPT) : 0x187,
# soit x^8+x^7+x^2+x+1. Remplace l'ancien defaut generique 0x11D (convention "QR code"),
# qui n'etait qu'une supposition plausible non confirmee.
_PRIMITIVE_POLY = 0x187
_FIELD_SIZE = 256

DEFAULT_N = 255
DEFAULT_K = 223
DEFAULT_NSYM = DEFAULT_N - DEFAULT_K

# Profondeur d'entrelacement CCSDS confirmee pour Meteor-M LRPT (recherche du 16/08/2026) :
# 4 mots de code RS(255,223) entrelaces octet par octet au sein d'un CADU.
DEFAULT_INTERLEAVE_DEPTH = 4


def _build_tables() -> tuple[list[int], list[int]]:
    exp = [0] * (2 * _FIELD_SIZE)
    log = [0] * _FIELD_SIZE
    x = 1
    for i in range(_FIELD_SIZE - 1):
        exp[i] = x
        log[x] = i
        x <<= 1
        if x & _FIELD_SIZE:
            x ^= _PRIMITIVE_POLY
    for i in range(_FIELD_SIZE - 1, 2 * _FIELD_SIZE):
        exp[i] = exp[i - (_FIELD_SIZE - 1)]
    return exp, log


_GF_EXP, _GF_LOG = _build_tables()
_GF_EXP_NP: NDArray[np.int64] = np.array(_GF_EXP, dtype=np.int64)
_GF_LOG_NP: NDArray[np.int64] = np.array(_GF_LOG, dtype=np.int64)


def gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def gf_div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError("division par zero dans GF(2^8)")
    if a == 0:
        return 0
    return _GF_EXP[(_GF_LOG[a] - _GF_LOG[b]) % (_FIELD_SIZE - 1)]


def gf_pow(a: int, power: int) -> int:
    return _GF_EXP[(_GF_LOG[a] * power) % (_FIELD_SIZE - 1)]


def gf_inverse(a: int) -> int:
    if a == 0:
        raise ZeroDivisionError("0 n'a pas d'inverse dans GF(2^8)")
    return _GF_EXP[(_FIELD_SIZE - 1) - _GF_LOG[a]]


def gf_poly_scale(poly: list[int], scalar: int) -> list[int]:
    return [gf_mul(coef, scalar) for coef in poly]


def gf_poly_add(p: list[int], q: list[int]) -> list[int]:
    result = [0] * max(len(p), len(q))
    for i, coef in enumerate(p):
        result[i + len(result) - len(p)] = coef
    for i, coef in enumerate(q):
        result[i + len(result) - len(q)] ^= coef
    return result


def gf_poly_mul(p: list[int], q: list[int]) -> list[int]:
    result = [0] * (len(p) + len(q) - 1)
    for j, qj in enumerate(q):
        if qj == 0:
            continue
        for i, pi in enumerate(p):
            result[i + j] ^= gf_mul(pi, qj)
    return result


def gf_poly_eval(poly: list[int], x: int) -> int:
    y = poly[0]
    for coef in poly[1:]:
        y = gf_mul(y, x) ^ coef
    return y


def rs_generator_poly(nsym: int) -> list[int]:
    generator = [1]
    for i in range(nsym):
        generator = gf_poly_mul(generator, [1, gf_pow(2, i)])
    return generator


def rs_encode(message: list[int], nsym: int = DEFAULT_NSYM) -> list[int]:
    if nsym <= 0:
        raise ValueError(f"nsym doit etre positif, recu {nsym}")
    if any(not 0 <= symbol <= 255 for symbol in message):
        raise ValueError("chaque symbole du message doit etre dans [0, 255]")

    generator = rs_generator_poly(nsym)
    padded = list(message) + [0] * (len(generator) - 1)
    for i in range(len(message)):
        coef = padded[i]
        if coef != 0:
            for j, gcoef in enumerate(generator):
                padded[i + j] ^= gf_mul(gcoef, coef)

    parity = padded[len(message) :]
    return list(message) + parity


def _calc_syndromes(codeword: list[int], nsym: int) -> list[int]:
    return [gf_poly_eval(codeword, gf_pow(2, i)) for i in range(nsym)]


def _find_error_locator(syndromes: list[int]) -> list[int]:
    err_loc = [1]
    old_loc = [1]
    for i in range(len(syndromes)):
        old_loc = old_loc + [0]
        delta = syndromes[i]
        for j in range(1, len(err_loc)):
            delta ^= gf_mul(err_loc[-(j + 1)], syndromes[i - j])
        if delta != 0:
            if len(old_loc) > len(err_loc):
                new_loc = gf_poly_scale(old_loc, delta)
                old_loc = gf_poly_scale(err_loc, gf_inverse(delta))
                err_loc = new_loc
            err_loc = gf_poly_add(err_loc, gf_poly_scale(old_loc, delta))

    err_loc = list(itertools.dropwhile(lambda x: x == 0, err_loc))
    errs = len(err_loc) - 1
    if errs * 2 > len(syndromes):
        raise ValueError("trop d'erreurs pour etre corrigees par ce mot de code")
    return err_loc


def _find_error_positions(err_loc: list[int], codeword_len: int) -> list[int]:
    errs = len(err_loc) - 1
    positions = []
    for p in range(codeword_len):
        x_p = gf_pow(2, codeword_len - 1 - p)
        if gf_poly_eval(err_loc, gf_inverse(x_p)) == 0:
            positions.append(p)
    if len(positions) != errs:
        raise ValueError("localisation d'erreurs incoherente : le mot de code est irrecuperable")
    return positions


def _gf_solve_linear_system(matrix: list[list[int]], rhs: list[int]) -> list[int]:
    n = len(rhs)
    augmented = [list(matrix[i]) + [rhs[i]] for i in range(n)]

    for col in range(n):
        pivot_row = next((r for r in range(col, n) if augmented[r][col] != 0), None)
        if pivot_row is None:
            raise ValueError("systeme lineaire singulier : positions d'erreurs incoherentes")
        augmented[col], augmented[pivot_row] = augmented[pivot_row], augmented[col]

        inv_pivot = gf_inverse(augmented[col][col])
        augmented[col] = [gf_mul(value, inv_pivot) for value in augmented[col]]

        for row in range(n):
            if row != col and augmented[row][col] != 0:
                factor = augmented[row][col]
                augmented[row] = [
                    a ^ gf_mul(factor, b) for a, b in zip(augmented[row], augmented[col])
                ]

    return [augmented[i][n] for i in range(n)]


def _correct_errors(codeword: list[int], syndromes: list[int], err_pos: list[int]) -> list[int]:
    codeword_len = len(codeword)
    n_err = len(err_pos)
    x_values = [gf_pow(2, codeword_len - 1 - p) for p in err_pos]

    # Systeme de Vandermonde en GF(256) : S_j = somme_l e_l * X_l^j pour j=0..n_err-1,
    # resolu directement plutot que via la formule de Forney (evaluateur d'erreurs +
    # derivee formelle du polynome localisateur), pour eviter les ambiguites de convention
    # d'indexation entre les differentes presentations de l'algorithme.
    matrix = [[gf_pow(x_values[idx], j) for idx in range(n_err)] for j in range(n_err)]
    rhs = syndromes[:n_err]
    magnitudes = _gf_solve_linear_system(matrix, rhs)

    corrected = list(codeword)
    for idx, p in enumerate(err_pos):
        corrected[p] ^= magnitudes[idx]
    return corrected


def rs_decode(codeword: list[int], nsym: int = DEFAULT_NSYM) -> list[int]:
    if nsym <= 0:
        raise ValueError(f"nsym doit etre positif, recu {nsym}")
    if len(codeword) <= nsym:
        raise ValueError(
            f"codeword trop court : {len(codeword)} symboles pour nsym={nsym} symboles de parite"
        )
    if any(not 0 <= symbol <= 255 for symbol in codeword):
        raise ValueError("chaque symbole du mot de code doit etre dans [0, 255]")

    syndromes = _calc_syndromes(codeword, nsym)
    if all(s == 0 for s in syndromes):
        return list(codeword[: len(codeword) - nsym])

    err_loc = _find_error_locator(syndromes)
    err_pos = _find_error_positions(err_loc, len(codeword))
    corrected = _correct_errors(codeword, syndromes, err_pos)

    residual_syndromes = _calc_syndromes(corrected, nsym)
    if any(s != 0 for s in residual_syndromes):
        raise ValueError("echec de la correction : syndromes non nuls apres correction")

    return corrected[: len(corrected) - nsym]


def _gf_mul_array_by_scalar(a: NDArray[np.int64], scalar: int) -> NDArray[np.int64]:
    if scalar == 0:
        return np.zeros_like(a)
    result = np.zeros_like(a)
    nonzero = a != 0
    scalar_log = int(_GF_LOG_NP[scalar])
    result[nonzero] = _GF_EXP_NP[(_GF_LOG_NP[a[nonzero]] + scalar_log) % (_FIELD_SIZE - 1)]
    return result


def _calc_syndromes_batch(codewords: NDArray[np.int64], nsym: int) -> NDArray[np.int64]:
    n_codewords, codeword_len = codewords.shape
    syndromes = np.zeros((n_codewords, nsym), dtype=np.int64)
    for i in range(nsym):
        alpha = gf_pow(2, i)
        y = codewords[:, 0].copy()
        for col in range(1, codeword_len):
            y = _gf_mul_array_by_scalar(y, alpha) ^ codewords[:, col]
        syndromes[:, i] = y
    return syndromes


def rs_decode_batch(codewords: list[list[int]], nsym: int = DEFAULT_NSYM) -> list[list[int]]:
    # Vectorise le calcul des syndromes (`_calc_syndromes_batch`, via numpy) sur tout un
    # lot de mots de code de meme longueur en une seule fois : c'est le chemin critique
    # pour un enregistrement reel de plusieurs minutes (des milliers de mots de code), et
    # dans le cas courant (peu ou pas d'erreurs residuelles apres le Viterbi en amont), les
    # syndromes nuls suffisent a extraire directement le message sans passer par
    # Berlekamp-Massey/Chien (algorithmes sequentiels, non vectorisables simplement),
    # reserves aux mots de code qui ont effectivement des erreurs a corriger.
    if not codewords:
        raise ValueError("codewords ne doit pas etre vide")
    lengths = {len(cw) for cw in codewords}
    if len(lengths) != 1:
        raise ValueError("tous les mots de code du lot doivent avoir la meme longueur")
    codeword_len = lengths.pop()
    if codeword_len <= nsym:
        raise ValueError(
            f"codeword trop court : {codeword_len} symboles pour nsym={nsym} symboles de parite"
        )

    arr = np.array(codewords, dtype=np.int64)
    if np.any((arr < 0) | (arr > 255)):
        raise ValueError("chaque symbole du mot de code doit etre dans [0, 255]")

    syndromes = _calc_syndromes_batch(arr, nsym)
    all_zero = ~np.any(syndromes != 0, axis=1)
    message_len = codeword_len - nsym

    results: list[list[int]] = [[] for _ in codewords]
    for idx in np.flatnonzero(all_zero):
        results[idx] = codewords[idx][:message_len]
    for idx in np.flatnonzero(~all_zero):
        results[idx] = rs_decode(codewords[idx], nsym)

    return results


def interleave_codewords(codewords: list[list[int]]) -> list[int]:
    if not codewords:
        raise ValueError("codewords ne doit pas etre vide")
    length = len(codewords[0])
    if length == 0:
        raise ValueError("les mots de code ne doivent pas etre vides")
    if any(len(cw) != length for cw in codewords):
        raise ValueError("tous les mots de code doivent avoir la meme longueur")

    interleaved: list[int] = []
    for i in range(length):
        for codeword in codewords:
            interleaved.append(codeword[i])
    return interleaved


def deinterleave_codewords(data: list[int], depth: int = DEFAULT_INTERLEAVE_DEPTH) -> list[list[int]]:
    if depth <= 0:
        raise ValueError(f"depth doit etre positif, recu {depth}")
    if not data:
        raise ValueError("data ne doit pas etre vide")
    if len(data) % depth != 0:
        raise ValueError(f"len(data) ({len(data)}) doit etre un multiple de depth ({depth})")

    codewords: list[list[int]] = [[] for _ in range(depth)]
    for i, symbol in enumerate(data):
        codewords[i % depth].append(symbol)
    return codewords


def rs_encode_interleaved(
    messages: list[list[int]],
    nsym: int = DEFAULT_NSYM,
) -> list[int]:
    if not messages:
        raise ValueError("messages ne doit pas etre vide")
    codewords = [rs_encode(message, nsym) for message in messages]
    return interleave_codewords(codewords)


def rs_decode_interleaved(
    data: list[int],
    depth: int = DEFAULT_INTERLEAVE_DEPTH,
    nsym: int = DEFAULT_NSYM,
) -> list[list[int]]:
    codewords = deinterleave_codewords(data, depth)
    return [rs_decode(codeword, nsym) for codeword in codewords]
