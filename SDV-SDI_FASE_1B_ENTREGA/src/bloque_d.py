"""BLOQUE D — auditoria de `orquestador_maestro.py` + prototipo por perfiles.

No modifica nada de la fuente inmutable. El original se ejecuta UNICAMENTE en
directorios de trabajo desechables bajo `work/d/`, para observar su comportamiento.
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import soundfile as sf

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)

from senales import escenario                                   # noqa: E402

FUENTE = "/home/user/fase1b/fuentes/Proyecto SDV-SDI_SGM"
ORIGINAL = os.path.join(FUENTE, "orquestador_maestro.py")
PERFILES = os.path.join(RAIZ, "configs", "perfiles_orquestador.json")
WORK = os.path.join(RAIZ, "work", "d")
RES = os.path.join(RAIZ, "results")
SR = 44100


# ---------------------------------------------------------------- utilidades
def escribir(p, x, sr=SR, subtype="FLOAT"):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    sf.write(p, x, sr, subtype=subtype)
    return p


def base_senales(dur=2.0, seed=20261117):
    """Estereo con L/R asimetrico y un evento SOLO en el canal L."""
    sc = escenario("voz_armonica", dur=dur, sr=SR, seed=seed)
    sr = sc["sr"]
    V, I = sc["V_true"].copy(), sc["I_true"].copy()
    n0 = min(int(0.9 * sr), max(0, sc["n"] - 1))
    n1 = min(int(1.1 * sr), sc["n"])
    V[n0:n1, 0] += 0.35 * np.hanning(n1 - n0)      # evento exclusivo de L
    M = V + I
    return sr, V, I, M


def leer(p):
    return sf.read(p, dtype="float64", always_2d=True)[0]


# ------------------------------------------------- 1. auditoria estatica
def auditoria():
    """Cada afirmacion se comprueba sobre el texto del original, con su linea."""
    lineas = open(ORIGINAL, encoding="utf-8").read().splitlines()

    def busca(frag, desde=0):
        for i in range(desde, len(lineas)):
            if frag in lineas[i]:
                return i + 1, lineas[i].strip()
        return None, None

    hallazgos = []

    def add(codigo, tipo, afirmacion, frag, evitar=None):
        ln, txt = busca(frag)
        if evitar:
            ln_e, _ = busca(evitar)
            ok = ln is not None and (ln_e is None or ln_e != ln)
        else:
            ok = ln is not None
        hallazgos.append({"id": codigo, "tipo": tipo, "afirmacion": afirmacion,
                          "linea": ln, "texto": txt, "confirmado": bool(ok)})

    add("D-01", "VERIFICADO",
        "Solo busca pares con sufijo _instrum.wav / _vocals.wav",
        '*_instrum.wav"')
    add("D-02", "VERIFICADO",
        "Si falta _vocals.wav para un _instrum.wav, se salta EN SILENCIO",
        'if os.path.exists(vocals_path):')
    add("D-03", "VERIFICADO",
        "En Reverb Removal itera SOLO dos nombres de modelo cableados",
        'for model in ["sucial", "anvuew"]:')
    add("D-04", "VERIFICADO",
        "Reconoce A, C y D; no hay ninguna referencia a [B] ni a [E]",
        'if "_[A]" in f:')
    lnB, _ = busca('"[B]"')
    lnE, _ = busca('"[E]"')
    hallazgos.append({"id": "D-05", "tipo": "VERIFICADO",
                      "afirmacion": "no existe '[B]' ni '[E]' en todo el fichero",
                      "linea": lnB or lnE, "texto": None,
                      "confirmado": lnB is None and lnE is None})
    add("D-06", "VERIFICADO", "Formula SDV en Reverb: mix - A + D",
        'sdv = mix[:min_len] - A[:min_len] + D[:min_len]')
    add("D-07", "VERIFICADO", "Formula SDI en Reverb: mix - C - D",
        'sdi = mix[:min_len] - C[:min_len] - D[:min_len]')
    add("D-08", "VERIFICADO",
        "Asignacion por recorrido: un segundo fichero con el mismo rol PISA al "
        "primero sin diagnostico", 'for f in os.listdir(dir_reverb):')
    add("D-09", "VERIFICADO", "Recorta todo al minimo de muestras (Reverb)",
        'min_len = min(len(mix), len(A), len(C), len(D))')
    add("D-10", "VERIFICADO", "Recorta todo al minimo de muestras (Simples)",
        'min_len = min(len(mix), len(instrum), len(vocals))')
    add("D-11", "VERIFICADO",
        "Escribe SIEMPRE con el sample rate del Mix, sin comprobar el de los stems",
        "sf.write(out_sdv, sdv, sr, subtype='FLOAT')")
    add("D-12", "VERIFICADO",
        "Exige A, C y D a la vez; si falta uno, el modelo se omite EN SILENCIO",
        'if path_A and path_C and path_D:')
    ln_sr, _ = busca("samplerate")
    hallazgos.append({"id": "D-13", "tipo": "VERIFICADO",
                      "afirmacion": "no se comprueba sample rate en ningun punto",
                      "linea": ln_sr, "texto": None, "confirmado": ln_sr is None})
    ln_ch, _ = busca("channels")
    hallazgos.append({"id": "D-14", "tipo": "VERIFICADO",
                      "afirmacion": "no se comprueba numero de canales en ningun punto",
                      "linea": ln_ch, "texto": None, "confirmado": ln_ch is None})
    ln_hash, _ = busca("sha256")
    hallazgos.append({"id": "D-15", "tipo": "VERIFICADO",
                      "afirmacion": "el manifiesto no guarda ningun hash",
                      "linea": ln_hash, "texto": None, "confirmado": ln_hash is None})
    ln_out, _ = busca('out_dir = os.path.join(base_dir, "Residuales_Finales")')
    hallazgos.append({"id": "D-16", "tipo": "VERIFICADO",
                      "afirmacion": "escribe DENTRO del arbol de entrada (no hay --out)",
                      "linea": ln_out, "texto": None, "confirmado": ln_out is not None})
    return {"fichero": ORIGINAL, "lineas_totales": len(lineas),
            "sha256": _sha(ORIGINAL),
            "hallazgos": hallazgos,
            "confirmados": sum(1 for h in hallazgos if h["confirmado"]),
            "total": len(hallazgos)}


def _sha(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ------------------------- 2. demos empiricas ejecutando el ORIGINAL en scratch
def _correr_original(scratch):
    r = subprocess.run([sys.executable, ORIGINAL, "--dir", scratch, "--mix", "Mix.wav"],
                       capture_output=True, text=True, cwd=scratch, timeout=180)
    man = os.path.join(scratch, "manifest_maestro.json")
    pares = []
    if os.path.isfile(man):
        pares = json.load(open(man, encoding="utf-8")).get("pairs", [])
    return {"rc": r.returncode, "stdout": r.stdout, "stderr": r.stderr,
            "n_pares": len(pares), "pares": pares,
            "salidas": sorted(os.listdir(os.path.join(scratch, "Residuales_Finales")))
            if os.path.isdir(os.path.join(scratch, "Residuales_Finales")) else []}


def demos_original():
    """Ejecuta el original sobre fixtures desechables y mide lo que hace."""
    sr, V, I, M = base_senales(dur=2.0)
    out = []
    if os.path.isdir(WORK):
        pass
    os.makedirs(WORK, exist_ok=True)

    def nuevo(nombre):
        d = os.path.join(WORK, "orig_" + nombre)
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)
        escribir(os.path.join(d, "Mix.wav"), M, sr)
        return d

    # a) nombres REALES del manifiesto entregado
    d = nuevo("nombres_reales")
    s = os.path.join(d, "Stems Masks Simples")
    escribir(os.path.join(s, "par1_roformer_instrum_only.wav"), I, sr)
    escribir(os.path.join(s, "par1_roformer_vocals_full.wav"), V, sr)
    r = _correr_original(d)
    r.update({"demo": "a_nombres_reales_del_manifiesto", "esperado": "0 pares",
              "observado": f"{r['n_pares']} pares"})
    out.append(r)

    # b) nombres que el original SI espera
    d = nuevo("nombres_orquestador")
    s = os.path.join(d, "Stems Masks Simples")
    escribir(os.path.join(s, "roformer_instrum.wav"), I, sr)
    escribir(os.path.join(s, "roformer_vocals.wav"), V, sr)
    r = _correr_original(d)
    r.update({"demo": "b_nombres_que_el_original_espera", "esperado": "1 par",
              "observado": f"{r['n_pares']} pares"})
    out.append(r)

    # c) modelo de Reverb no listado
    d = nuevo("modelo_no_listado")
    rv = os.path.join(d, "Stems Masks Reverb Removal")
    for tag, x in (("[A]", I), ("[C]", I * .8), ("[D]", V)):
        escribir(os.path.join(rv, f"otromodelo_{tag}.wav"), x, sr)
    r = _correr_original(d)
    r.update({"demo": "c_modelo_reverb_no_listado", "esperado": "0 pares, sin aviso",
              "observado": f"{r['n_pares']} pares"})
    out.append(r)

    # d) falta un componente obligatorio
    d = nuevo("falta_componente")
    rv = os.path.join(d, "Stems Masks Reverb Removal")
    escribir(os.path.join(rv, "sucial_[A].wav"), I, sr)
    escribir(os.path.join(rv, "sucial_[C].wav"), I * .8, sr)
    r = _correr_original(d)
    r.update({"demo": "d_falta_D_en_reverb", "esperado": "0 pares, sin aviso",
              "observado": f"{r['n_pares']} pares"})
    out.append(r)

    # e) dos candidatos para el mismo rol
    d = nuevo("duplicado_C")
    rv = os.path.join(d, "Stems Masks Reverb Removal")
    escribir(os.path.join(rv, "sucial_[A].wav"), I, sr)
    escribir(os.path.join(rv, "sucial_[D].wav"), V, sr)
    escribir(os.path.join(rv, "sucial_uno_[C].wav"), I * 0.5, sr)
    escribir(os.path.join(rv, "sucial_dos_[C].wav"), I * 0.9, sr)
    r = _correr_original(d)
    r.update({"demo": "e_dos_candidatos_C", "esperado": "1 par, gana el ultimo, sin aviso",
              "observado": f"{r['n_pares']} pares"})
    out.append(r)

    # f) SR distinta en un stem
    d = nuevo("sr_distinta")
    rv = os.path.join(d, "Stems Masks Reverb Removal")
    escribir(os.path.join(rv, "sucial_[A].wav"), I, sr)             # 44100
    escribir(os.path.join(rv, "sucial_[C].wav"), I * .8, 48000)     # 48000 !
    escribir(os.path.join(rv, "sucial_[D].wav"), V, sr)
    r = _correr_original(d)
    sal = os.path.join(d, "Residuales_Finales")
    med = {}
    if os.path.isdir(sal):
        for f in sorted(os.listdir(sal)):
            i = sf.info(os.path.join(sal, f))
            med[f] = {"sr": i.samplerate, "frames": i.frames,
                      "dur_s": round(i.frames / i.samplerate, 4)}
    r.update({"demo": "f_sr_distinta_48000_vs_44100", "esperado": "rc=0 sin aviso",
              "observado": json.dumps(med), "meta_salidas": med})
    out.append(r)

    # g) longitudes distintas
    d = nuevo("longitud_distinta")
    rv = os.path.join(d, "Stems Masks Reverb Removal")
    escribir(os.path.join(rv, "sucial_[A].wav"), I, sr)
    escribir(os.path.join(rv, "sucial_[C].wav"), I[:int(1.5 * sr)] * .8, sr)
    escribir(os.path.join(rv, "sucial_[D].wav"), V, sr)
    r = _correr_original(d)
    sal = os.path.join(d, "Residuales_Finales")
    med = {}
    if os.path.isdir(sal):
        for f in sorted(os.listdir(sal)):
            i = sf.info(os.path.join(sal, f))
            med[f] = {"sr": i.samplerate, "frames": i.frames,
                      "dur_s": round(i.frames / i.samplerate, 4)}
    r.update({"demo": "g_longitud_distinta_1.5s_vs_2.0s",
              "esperado": "recorte silencioso a 1.5 s", "observado": json.dumps(med),
              "meta_salidas": med})
    out.append(r)

    # h) estéreo contra mono
    d = nuevo("mono_vs_estereo")
    rv = os.path.join(d, "Stems Masks Reverb Removal")
    escribir(os.path.join(rv, "sucial_[A].wav"), I, sr)
    escribir(os.path.join(rv, "sucial_[C].wav"), (I * .8)[:, :1], sr)
    escribir(os.path.join(rv, "sucial_[D].wav"), V, sr)
    r = _correr_original(d)
    sal = os.path.join(d, "Residuales_Finales")
    med = {}
    if os.path.isdir(sal):
        for f in sorted(os.listdir(sal)):
            i = sf.info(os.path.join(sal, f))
            med[f] = {"canales": i.channels, "sr": i.samplerate}
    r.update({"demo": "h_mono_vs_estereo", "esperado": "rc=0, sin aviso",
              "observado": json.dumps(med), "meta_salidas": med})
    out.append(r)

    for x in out:
        x.pop("pares", None)
    return out


# ======================================== 3. fixtures sinteticos del orquestador
_ULTIMO = {"dir": None}


def _caso(nombre):
    d = os.path.join(WORK, "fx", nombre)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    _ULTIMO["dir"] = d
    return d


def construir_fixtures():
    """26 fixtures; cada uno declara el resultado esperado (4.8)."""
    sr, V, I, M = base_senales()
    S, RV = "Stems Masks Simples", "Stems Masks Reverb Removal"
    casos = []

    def add(nombre, esperado, formulas, kwargs=None, n_grupos=1, nota=""):
        casos.append({"nombre": nombre, "dir": _ULTIMO["dir"],
                      "esperado_estado": esperado,
                      "esperado_formulas": set(formulas), "kwargs": kwargs or {},
                      "esperado_n_grupos": n_grupos, "nota": nota})

    # 1 par valido simple
    d = _caso("01_simple_par_valido")
    escribir(f"{d}/Mix.wav", M, sr)
    escribir(f"{d}/{S}/par1_roformer_instrum_only.wav", I, sr)
    escribir(f"{d}/{S}/par1_roformer_vocals_full.wav", V, sr)
    add("01_simple_par_valido", "ACCEPT", {"SDV_SIMPLE", "SDI_SIMPLE"})

    # 2 falta vocals
    d = _caso("02_simple_vocals_ausente")
    escribir(f"{d}/Mix.wav", M, sr)
    escribir(f"{d}/{S}/par1_roformer_instrum_only.wav", I, sr)
    add("02_simple_vocals_ausente", "INCOMPLETE", {"SDV_SIMPLE"})

    # 3 duplicado real: dos convenciones de IGUAL prioridad en la misma corrida
    d = _caso("03_simple_duplicado")
    escribir(f"{d}/Mix.wav", M, sr)
    escribir(f"{d}/{S}/par1_roformer_instrum_only.wav", I, sr)
    escribir(f"{d}/{S}/par1_roformer_instrumental.wav", I * .5, sr)
    escribir(f"{d}/{S}/par1_roformer_vocals_full.wav", V, sr)
    add("03_simple_duplicado", "AMBIGUOUS", set(),
        nota="dos ficheros reclaman INSTRUMENTAL en la misma corrida: no se elige ninguno")

    # 3b dos corridas cuyos nombres comparten prefijo
    d = _caso("03b_simple_corridas_vecinas")
    escribir(f"{d}/Mix.wav", M, sr)
    escribir(f"{d}/{S}/par1_roformer_instrum_only.wav", I, sr)
    escribir(f"{d}/{S}/par1_roformer_vocals_full.wav", V, sr)
    escribir(f"{d}/{S}/par1_otro_instrum_only.wav", I * .5, sr)
    add("03b_simple_corridas_vecinas", "INCOMPLETE", {"SDV_SIMPLE", "SDI_SIMPLE"},
        n_grupos=2, nota="se separan por corrida; no se mezclan")

    # 4 dos corridas en la misma carpeta
    d = _caso("04_simple_dos_corridas")
    escribir(f"{d}/Mix.wav", M, sr)
    for k, (a, b) in enumerate(((I, V), (I * .7, V * .8)), start=1):
        escribir(f"{d}/{S}/par{k}_roformer_instrum_only.wav", a, sr)
        escribir(f"{d}/{S}/par{k}_roformer_vocals_full.wav", b, sr)
    add("04_simple_dos_corridas", "ACCEPT", {"SDV_SIMPLE", "SDI_SIMPLE"}, n_grupos=2)

    # 5 C agregado
    d = _caso("05_reverb_c_agregado")
    escribir(f"{d}/Mix.wav", M, sr)
    for tag, x in (("[A]", I * .9), ("[C]", I * .8), ("[D]", V * .95)):
        escribir(f"{d}/{RV}/sucial_{tag}.wav", x, sr)
    add("05_reverb_c_agregado", "INCOMPLETE", {"SDV2", "SDI2"},
        nota="B y E ausentes: SDV1/SDI1 quedan INCOMPLETE")

    # 6 C dividido
    d = _caso("06_reverb_c_dividido")
    escribir(f"{d}/Mix.wav", M, sr)
    escribir(f"{d}/{RV}/sucial_[A].wav", I * .9, sr)
    escribir(f"{d}/{RV}/sucial_Reverb [C].wav", I * .5, sr)
    escribir(f"{d}/{RV}/sucial_Others [C].wav", I * .3, sr)
    escribir(f"{d}/{RV}/sucial_[D].wav", V * .95, sr)
    add("06_reverb_c_dividido", "INCOMPLETE", {"SDV2", "SDI2"},
        nota="C_total = Reverb + Others")

    # 7 solo un subcomponente
    d = _caso("07_reverb_solo_reverb")
    escribir(f"{d}/Mix.wav", M, sr)
    escribir(f"{d}/{RV}/sucial_[A].wav", I * .9, sr)
    escribir(f"{d}/{RV}/sucial_Reverb [C].wav", I * .5, sr)
    escribir(f"{d}/{RV}/sucial_[D].wav", V * .95, sr)
    add("07_reverb_solo_reverb", "INCOMPLETE", {"SDV2"},
        nota="no se infiere C_total")

    # 8 agregado + subcomponentes = conflicto
    d = _caso("08_reverb_conflicto")
    escribir(f"{d}/Mix.wav", M, sr)
    escribir(f"{d}/{RV}/sucial_[A].wav", I * .9, sr)
    escribir(f"{d}/{RV}/sucial_[C].wav", I * .8, sr)
    escribir(f"{d}/{RV}/sucial_Reverb [C].wav", I * .5, sr)
    escribir(f"{d}/{RV}/sucial_Others [C].wav", I * .3, sr)
    escribir(f"{d}/{RV}/sucial_[D].wav", V * .95, sr)
    add("08_reverb_conflicto", "AMBIGUOUS", set(), nota="nunca se suman agregado+subs")

    # 9 A/B/C/D/E completos
    d = _caso("09_reverb_abcde")
    escribir(f"{d}/Mix.wav", M, sr)
    for tag, x in (("[A]", I * .9), ("[B]", I * .97), ("[C]", I * .8),
                   ("[D]", V * .95), ("[E]", V * .99)):
        escribir(f"{d}/{RV}/anvuew_{tag}.wav", x, sr)
    add("09_reverb_abcde", "ACCEPT", {"SDV1", "SDV2", "SDI1", "SDI2"})

    # 10 solo B
    d = _caso("10_reverb_solo_b")
    escribir(f"{d}/Mix.wav", M, sr)
    escribir(f"{d}/{RV}/anvuew_[B].wav", I * .97, sr)
    add("10_reverb_solo_b", "INCOMPLETE", {"SDV1"})

    # 11a/b/c  E frente a C_total + D
    for etq, fE in (("11a_e_vs_cd_exacto", "exacto"),
                    ("11b_e_vs_cd_leve", "leve"),
                    ("11c_e_vs_cd_severo", "severo")):
        d = _caso(etq)
        escribir(f"{d}/Mix.wav", M, sr)
        C_ = I * .8
        D_ = V * .95
        rng = np.random.default_rng(7)
        if fE == "exacto":
            E_ = C_ + D_
        elif fE == "leve":
            E_ = (C_ + D_) * 1.01
        else:
            E_ = (C_ + D_) * 1.5 + 0.02 * rng.standard_normal(M.shape)
        for tag, x in (("[A]", I * .9), ("[C]", C_), ("[D]", D_), ("[E]", E_)):
            escribir(f"{d}/{RV}/mdxb_{tag}.wav", x, sr)
        add(etq, "INCOMPLETE", {"SDV2", "SDI1", "SDI2"}, nota=f"relacion E~C+D: {fE}")

    # 12 modelo nuevo, nombres completamente distintos
    d = _caso("12_modelo_nuevo_nombres_alt")
    escribir(f"{d}/Mix.wav", M, sr)
    for tag, x in (("__restored", I * .9), ("__backing", I * .97), ("__wet", I * .8),
                   ("__dryvox", V * .95), ("__vox", V * .99)):
        escribir(f"{d}/{RV}/SA3v2{tag}.wav", x, sr)
    add("12_modelo_nuevo_nombres_alt", "ACCEPT", {"SDV1", "SDV2", "SDI1", "SDI2"})

    # 13 dos corridas mezcladas en la misma carpeta
    d = _caso("13_corridas_mezcladas")
    escribir(f"{d}/Mix.wav", M, sr)
    for run, esc in (("runA", .9), ("runB", .7)):
        for tag, x in (("[A]", I * esc), ("[C]", I * .8 * esc), ("[D]", V * .95)):
            escribir(f"{d}/{RV}/{run}_{tag}.wav", x, sr)
    add("13_corridas_mezcladas", "INCOMPLETE", {"SDV2", "SDI2"}, n_grupos=2)

    # 14 metadatos incompatibles (5 variantes)
    def _base_meta(nombre):
        d = _caso(nombre)
        escribir(f"{d}/Mix.wav", M, sr)
        escribir(f"{d}/{RV}/sucial_[C].wav", I * .8, sr)
        escribir(f"{d}/{RV}/sucial_[D].wav", V * .95, sr)
        return d

    d = _base_meta("14a_sr_distinta")
    escribir(f"{d}/{RV}/sucial_[A].wav", I * .9, 48000)
    add("14a_sr_distinta", "INCOMPATIBLE", {"SDI2"})
    d = _base_meta("14b_canales_distintos")
    escribir(f"{d}/{RV}/sucial_[A].wav", (I * .9)[:, :1], sr)
    add("14b_canales_distintos", "INCOMPATIBLE", {"SDI2"})
    d = _base_meta("14c_longitud_distinta")
    escribir(f"{d}/{RV}/sucial_[A].wav", (I * .9)[: int(1.5 * sr)], sr)
    add("14c_longitud_distinta", "INCOMPATIBLE", {"SDI2"})
    d = _base_meta("14d_subtype_distinto")
    escribir(f"{d}/{RV}/sucial_[A].wav", I * .9, sr, subtype="PCM_16")
    add("14d_subtype_distinto", "INCOMPATIBLE", {"SDI2"})
    d = _base_meta("14e_nan_inf")
    A_ = I * .9
    A_[100, 0] = np.nan
    escribir(f"{d}/{RV}/sucial_[A].wav", A_, sr)
    add("14e_nan_inf", "REJECTED", {"SDI2"})

    # 15 L/R asimetrico con ground truth exacta (B = I, E = V)
    d = _caso("15_lr_asimetrico_gt")
    escribir(f"{d}/Mix.wav", M, sr)
    for tag, x in (("[A]", I * .9), ("[B]", I), ("[C]", I * .8),
                   ("[D]", V * .95), ("[E]", V)):
        escribir(f"{d}/{RV}/sucial_{tag}.wav", x, sr)
    add("15_lr_asimetrico_gt", "ACCEPT", {"SDV1", "SDV2", "SDI1", "SDI2"},
        nota="SDV1 y SDI1 deben coincidir EXACTO con V_true e I_true")

    # 16 corrupto / no WAV
    d = _caso("16a_corrupto")
    escribir(f"{d}/Mix.wav", M, sr)
    escribir(f"{d}/{RV}/sucial_[C].wav", I * .8, sr)
    escribir(f"{d}/{RV}/sucial_[D].wav", V * .95, sr)
    with open(f"{d}/{RV}/sucial_[A].wav", "wb") as fh:
        fh.write(b"no soy un wav" * 100)
    add("16a_corrupto", "REJECTED", {"SDI2"})

    d = _caso("16b_no_wav")
    escribir(f"{d}/Mix.wav", M, sr)
    escribir(f"{d}/{RV}/sucial_[A].wav", I * .9, sr)
    escribir(f"{d}/{RV}/sucial_[C].wav", I * .8, sr)
    escribir(f"{d}/{RV}/sucial_[D].wav", V * .95, sr)
    with open(f"{d}/{RV}/notas.txt", "w") as fh:
        fh.write("no es audio")
    add("16b_no_wav", "INCOMPLETE", {"SDV2", "SDI2"},
        nota="el .txt se ignora y se registra en el inventario")

    # 17 mix ausente / dos mix / hash cambiado
    d = _caso("17a_mix_ausente")
    escribir(f"{d}/{RV}/sucial_[A].wav", I * .9, sr)
    add("17a_mix_ausente", "REJECTED", set())

    d = _caso("17b_dos_mix")
    escribir(f"{d}/Mix.wav", M, sr)
    escribir(f"{d}/Mix_alt.wav", M * .9, sr)
    escribir(f"{d}/{RV}/sucial_[A].wav", I * .9, sr)
    add("17b_dos_mix", "REJECTED", set(), kwargs={"mix": None})

    d = _caso("17c_hash_cambiado")
    escribir(f"{d}/Mix.wav", M, sr)
    escribir(f"{d}/{RV}/sucial_[A].wav", I * .9, sr)
    add("17c_hash_cambiado", "REJECTED", set(), kwargs={"sha": "0" * 64})

    return casos


# ================================================== 4. ejecucion de la matriz
def correr_fixtures():
    from orchestrator_spec import orquestador

    casos = construir_fixtures()
    filas = []
    for c in casos:
        out = os.path.join(WORK, "out", c["nombre"])
        if os.path.isdir(out):
            shutil.rmtree(out)
        kw = c["kwargs"]
        try:
            r = orquestador.ejecutar(c["dir"], PERFILES,
                                     mix_nombre=kw.get("mix", "Mix.wav"),
                                     out_dir=out, mix_sha_esperado=kw.get("sha"))
        except Exception as e:                                  # noqa: BLE001
            filas.append({"caso": c["nombre"], "estado": "EXCEPCION",
                          "error": f"{type(e).__name__}: {e}",
                          "esperado": c["esperado_estado"], "pasa": False})
            continue
        got = set()
        for g in r["grupos"]:
            for x in g["residuales"]:
                if x.get("estado") == "OK":
                    got.add(x["formula"])
        checks = {"estado": r["estado"] == c["esperado_estado"],
                  "formulas": got == c["esperado_formulas"]}
        if c["esperado_estado"] != "REJECTED":
            checks["n_grupos"] = len(r["grupos"]) == c["esperado_n_grupos"]
        filas.append({
            "caso": c["nombre"], "estado": r["estado"],
            "esperado": c["esperado_estado"], "formulas": sorted(got),
            "esperado_formulas": sorted(c["esperado_formulas"]),
            "n_grupos": len(r["grupos"]), "checks": checks,
            "pasa": all(checks.values()), "nota": c["nota"],
            "motivo": r["motivo"] or "; ".join(
                m for g in r["grupos"] for m in g.get("motivos", []))[:400],
            "resultado": r, "dir": c["dir"], "out": out,
        })
    return filas


def verificaciones_extra(filas):
    """Comprobaciones que no se pueden expresar como estado: L/R, C_total, motivos."""
    extra = {}

    def fila(nombre):
        f = next((x for x in filas if x["caso"] == nombre), None)
        if not f or "resultado" not in f:
            return None
        return f

    # --- L/R: fidelidad exacta a ground truth y deteccion de intercambio ---
    sr, V, I, M = base_senales()
    f = fila("15_lr_asimetrico_gt")
    if f and f["estado"] == "ACCEPT":
        g = f["resultado"]["grupos"][0]
        rutas = {x["formula"]: x["ruta"] for x in g["residuales"]}
        sdv1 = leer(rutas["SDV1"])
        sdi1 = leer(rutas["SDI1"])
        i = sf.info(rutas["SDV1"])
        extra["lr"] = {
            "max_abs_SDV1_menos_Vtrue": float(np.max(np.abs(sdv1 - V))),
            "max_abs_SDI1_menos_Itrue": float(np.max(np.abs(sdi1 - I))),
            "max_abs_si_se_intercambiaran_LR": float(np.max(np.abs(sdv1 - V[:, ::-1]))),
            "evento_solo_L_detectado_EN_L": float(np.max(np.abs(sdv1[39690:48510, 0]
                                                              - V[39690:48510, 0]))),
            "sr_salida": i.samplerate, "frames_salida": i.frames,
            "frames_mix": int(M.shape[0]), "sr_mix": sr,
            "subtype_salida": i.subtype,
            "duracion_igual": i.frames == M.shape[0],
            "canales": i.channels,
        }

    # --- C_total dividido: estrategia y suma de dos sumandos ---
    f = fila("06_reverb_c_dividido")
    if f:
        g = f["resultado"]["grupos"][0]
        extra["c_dividido"] = {"estrategia": g["c_total"]["estrategia"],
                               "formula": g["c_total"].get("formula"),
                               "n_sumandos": len(g["c_total"]["sumandos"]),
                               "roles_sumandos": [s["rol"] for s in g["c_total"]["sumandos"]]}
    f = fila("05_reverb_c_agregado")
    if f:
        g = f["resultado"]["grupos"][0]
        extra["c_agregado"] = {"estrategia": g["c_total"]["estrategia"],
                               "n_sumandos": len(g["c_total"]["sumandos"])}
    f = fila("07_reverb_solo_reverb")
    if f:
        g = f["resultado"]["grupos"][0]
        extra["c_parcial"] = {"estrategia": g["c_total"]["estrategia"],
                              "estado": g["c_total"]["estado"],
                              "motivos": g["c_total"]["motivos"]}
    f = fila("08_reverb_conflicto")
    if f:
        g = f["resultado"]["grupos"][0]
        extra["c_conflicto"] = {"estado": g["c_total"]["estado"],
                                "motivos": g["c_total"]["motivos"]}

    # --- E frente a C_total + D, tres niveles ---
    extra["e_vs_cd"] = {}
    for nombre in ("11a_e_vs_cd_exacto", "11b_e_vs_cd_leve", "11c_e_vs_cd_severo"):
        f = fila(nombre)
        if f and f["resultado"]["grupos"]:
            m = f["resultado"]["grupos"][0].get("e_vs_c_total_d")
            if m:
                extra["e_vs_cd"][nombre] = m

    # --- 4b: los motivos son los correctos ---
    extra["motivos"] = {}
    for nombre in ("14a_sr_distinta", "14b_canales_distintos", "14c_longitud_distinta",
                   "14d_subtype_distinto", "14e_nan_inf", "16a_corrupto",
                   "17a_mix_ausente", "17b_dos_mix", "17c_hash_cambiado"):
        f = fila(nombre)
        if f:
            extra["motivos"][nombre] = (f["motivo"] or "")[:300]
    return extra


# ========================================== 5. tests unitarios del prototipo
def tests_unitarios():
    """Comprobaciones de contrato de cada fase, sin pasar por el CLI."""
    from orchestrator_spec import agrupador, c_total, clasificador
    from orchestrator_spec import perfiles as P
    from orchestrator_spec import validador as V

    res = []

    def t(nombre, cond, detalle=""):
        res.append({"test": nombre, "pasa": bool(cond), "detalle": detalle})

    doc = P.cargar_perfiles(PERFILES)
    t("perfiles: 3 perfiles y esquema valido", len(doc["perfiles"]) == 3)

    # el clasificador NO confunde C agregado con subcomponentes
    nombres = ["m_[C].wav", "m_Reverb [C].wav", "m_Others [C].wav", "m_[A].wav"]
    fic = [{"nombre": n, "rel": n, "ruta": "/tmp/" + n, "dir": "", "bytes": 0}
           for n in nombres]
    r = clasificador.clasificar(fic, doc)
    roles = {x["nombre"]: x["rol"] for x in r["ficheros"]}
    t("clasificador: [C] agregado != Reverb [C]", roles["m_[C].wav"] == "C_AGGREGATE"
      and roles["m_Reverb [C].wav"] == "C_REVERB")
    t("clasificador: Others [C] separado", roles["m_Others [C].wav"] == "C_OTHERS")

    # empate de prioridad => AMBIGUO, no primer match
    doc2 = json.loads(json.dumps(doc))
    doc2["perfiles"].append({
        "model_id": "trampa", "version": "0",
        "roles": {"A_RESTORED": [{"regex": "^(?P<run>.+?)_\\[A\\]\\.wav$", "prioridad": 20}],
                  "D_DRY_VOCAL": [{"regex": "^(?P<run>.+?)_\\[A\\]\\.wav$", "prioridad": 20}]}})
    r2 = clasificador.clasificar(fic[:1] + [{"nombre": "m_[A].wav", "rel": "m_[A].wav",
                                             "ruta": "/tmp/m_[A].wav", "dir": "", "bytes": 0}], doc2)
    amb = [x for x in r2["ficheros"] if x["estado"] == "AMBIGUO"]
    t("clasificador: empate => AMBIGUO", len(amb) >= 1)

    # agrupador: corridas distintas no se mezclan
    fic3 = [{"nombre": "runA_[A].wav", "rel": "x/runA_[A].wav", "ruta": "/t/x/runA_[A].wav",
             "dir": "x", "bytes": 0, "rol": "A_RESTORED", "perfil": "reverb_tagged",
             "run": "runA", "estado": "CLASIFICADO", "prioridad": 20, "evidencia": {},
             "descartados": []},
            {"nombre": "runB_[A].wav", "rel": "x/runB_[A].wav", "ruta": "/t/x/runB_[A].wav",
             "dir": "x", "bytes": 0, "rol": "A_RESTORED", "perfil": "reverb_tagged",
             "run": "runB", "estado": "CLASIFICADO", "prioridad": 20, "evidencia": {},
             "descartados": []}]
    gs = agrupador.agrupar({"ficheros": fic3, "ambiguos": []})
    t("agrupador: 2 corridas => 2 grupos", len(gs) == 2)

    # C_total: nunca suma agregado + subcomponentes
    pf = next(p for p in doc["perfiles"] if p["model_id"] == "reverb_tagged")
    pr = c_total.construir({"C_AGGREGATE": [{"rel": "a.wav", "ruta": "/nope"}],
                            "C_REVERB": [{"rel": "b.wav", "ruta": "/nope"}],
                            "C_OTHERS": [{"rel": "c.wav", "ruta": "/nope"}]}, pf)
    t("c_total: agregado+subs => AMBIGUOUS sin leer audio", pr["estado"] == "AMBIGUOUS")
    pr = c_total.construir({"C_REVERB": [{"rel": "b.wav", "ruta": "/nope"}]}, pf)
    t("c_total: un solo subcomponente => INCOMPLETE", pr["estado"] == "INCOMPLETE")

    # validador: detecta NaN y geometria
    sr, V_, I_, M_ = base_senales(dur=0.5)
    d = os.path.join(WORK, "unit")
    os.makedirs(d, exist_ok=True)
    a = I_.copy()
    a[10, 0] = np.inf
    escribir(f"{d}/ok.wav", I_)
    escribir(f"{d}/nan.wav", a)
    escribir(f"{d}/lista.wav", I_)
    v = V.validar_entradas([("a", f"{d}/ok.wav"), ("b", f"{d}/nan.wav")])
    t("validador: NaN => rechazado", v["ok"] is False and v.get("rechazado"))
    escribir(f"{d}/corto.wav", I_[:100])
    v = V.validar_entradas([("a", f"{d}/ok.wav"), ("b", f"{d}/corto.wav")])
    t("validador: frames distintos => INCOMPATIBLE",
      v["ok"] is False and any("frames" in m for m in v["motivos"]))
    v = V.validar_entradas([("a", f"{d}/ok.wav"), ("b", f"{d}/lista.wav")])
    t("validador: entradas identicas => ok", v["ok"] is True)
    return res


# ============================================================== 6. principal
def main():
    os.makedirs(RES, exist_ok=True)
    os.makedirs(os.path.join(RES, "logs"), exist_ok=True)
    print("### 1. auditoria estatica de orquestador_maestro.py", flush=True)
    au = auditoria()
    print(f"  {au['confirmados']}/{au['total']} afirmaciones confirmadas sobre "
          f"{au['lineas_totales']} lineas (sha256 {au['sha256'][:16]}...)", flush=True)
    for h in au["hallazgos"]:
        if not h["confirmado"]:
            print(f"  !! NO CONFIRMADO {h['id']}: {h['afirmacion']}", flush=True)

    print("\n### 2. demos: ejecutando el ORIGINAL en scratch", flush=True)
    dm = demos_original()
    for x in dm:
        print(f"  {x['demo']:<38} rc={x['rc']} pares={x['n_pares']:<2} "
              f"(esperado: {x['esperado']})", flush=True)

    print("\n### 3. matriz de fixtures (26 casos)", flush=True)
    filas = correr_fixtures()
    for f in filas:
        marca = "ok " if f["pasa"] else "FALLA"
        print(f"  [{marca}] {f['caso']:<30} {f.get('estado','?'):<12} "
              f"esperado={f['esperado']:<12} {f.get('formulas')}", flush=True)

    print("\n### 4. verificaciones extra", flush=True)
    ex = verificaciones_extra(filas)
    if "lr" in ex:
        lr = ex["lr"]
        print(f"  L/R: max|SDV1-V_true|={lr['max_abs_SDV1_menos_Vtrue']:.3e}  "
              f"max|SDI1-I_true|={lr['max_abs_SDI1_menos_Itrue']:.3e}  "
              f"si se intercambiaran={lr['max_abs_si_se_intercambiaran_LR']:.3f}", flush=True)
    for k in ("c_agregado", "c_dividido", "c_parcial", "c_conflicto"):
        if k in ex:
            print(f"  {k:<14} {json.dumps(ex[k], ensure_ascii=False)[:150]}", flush=True)
    for k, v in ex.get("e_vs_cd", {}).items():
        print(f"  {k:<22} max|E-C-D|={v['max_abs_global']:.3e}  "
              f"SNR_L={v['canales']['L']['snr_db']:.2f} dB  exacta={v['exacta']}", flush=True)

    print("\n### 5. tests unitarios", flush=True)
    tu = tests_unitarios()
    for t in tu:
        print(f"  [{'ok ' if t['pasa'] else 'FALLA'}] {t['test']}", flush=True)

    todo = {"auditoria": au, "demos_original": dm,
            "fixtures": [{k: v for k, v in f.items() if k != "resultado"}
                         for f in filas],
            "resultado_completo": {f["caso"]: f["resultado"] for f in filas},
            "verificaciones_extra": ex, "tests_unitarios": tu}

    def limpiar(o):
        if isinstance(o, dict):
            return {k: limpiar(v) for k, v in o.items() if k != "C_total"}
        if isinstance(o, list):
            return [limpiar(x) for x in o]
        if isinstance(o, (np.ndarray,)):
            return f"<array {o.shape}>"
        return o

    with open(os.path.join(RES, "bloque_d_orquestador.json"), "w", encoding="utf-8") as fh:
        json.dump(limpiar(todo), fh, indent=1, ensure_ascii=False, default=str)

    n_ok = sum(1 for f in filas if f["pasa"])
    n_t = sum(1 for t in tu if t["pasa"])
    print(f"\n=== fixtures {n_ok}/{len(filas)} · tests {n_t}/{len(tu)} · "
          f"auditoria {au['confirmados']}/{au['total']} ===", flush=True)
    return 0 if (n_ok == len(filas) and n_t == len(tu)) else 1


if __name__ == "__main__":
    sys.exit(main())
