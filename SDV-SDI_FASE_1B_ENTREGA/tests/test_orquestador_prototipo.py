"""Tests del prototipo `orchestrator_spec`.

Ejecutables con pytest (`python3 -m pytest tests/ -q`) o directamente
(`python3 tests/test_orquestador_prototipo.py`), sin dependencias extra.
"""
import json
import os
import sys

import numpy as np
import soundfile as sf

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))

from orchestrator_spec import agrupador, c_total, clasificador, inventario  # noqa: E402
from orchestrator_spec import perfiles as P                                   # noqa: E402
from orchestrator_spec import validador as V                                  # noqa: E402

PERFILES = os.path.join(RAIZ, "configs", "perfiles_orquestador.json")
SR = 44100


def _doc():
    return P.cargar_perfiles(PERFILES)


def _fic(nombres):
    return [{"nombre": n, "rel": n, "ruta": "/tmp/" + n, "dir": "", "bytes": 0}
            for n in nombres]


def _wav(path, x, sr=SR, subtype="FLOAT"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, x, sr, subtype=subtype)
    return path


def _senales(dur=0.5):
    rng = np.random.default_rng(1)
    n = int(dur * SR)
    V_ = 0.3 * rng.standard_normal((n, 2))
    I_ = 0.2 * rng.standard_normal((n, 2))
    return V_, I_, V_ + I_


# --------------------------------------------------------------- perfiles
def test_perfiles_esquema_y_cantidad():
    d = _doc()
    assert len(d["perfiles"]) >= 3
    assert {p["model_id"] for p in d["perfiles"]} >= {"mvsep_simple", "reverb_tagged"}


def test_perfil_invalido_se_rechaza(tmp_path):
    malo = {"schema": P.ESQUEMA, "perfiles": [{"model_id": "x", "version": "1",
                                               "roles": {"ROL_INVENTADO": [{"regex": "a"}]}}]}
    p = tmp_path / "malo.json"
    p.write_text(json.dumps(malo), encoding="utf-8")
    try:
        P.cargar_perfiles(str(p))
    except P.PerfilInvalido as e:
        assert "rol desconocido" in str(e)
    else:
        raise AssertionError("deberia haber rechazado el perfil")


def test_regex_invalida_se_rechaza(tmp_path):
    malo = {"schema": P.ESQUEMA, "perfiles": [{"model_id": "x", "version": "1",
                                              "roles": {"A_RESTORED": [{"regex": "([a"}]}}]}
    p = tmp_path / "malo.json"
    p.write_text(json.dumps(malo), encoding="utf-8")
    try:
        P.cargar_perfiles(str(p))
    except P.PerfilInvalido:
        pass
    else:
        raise AssertionError("deberia haber rechazado la regex")


# ----------------------------------------------------------- clasificador
def test_c_agregado_no_se_confunde_con_subcomponentes():
    r = clasificador.clasificar(
        _fic(["m_[C].wav", "m_Reverb [C].wav", "m_Others [C].wav"]), _doc())
    roles = {x["nombre"]: x["rol"] for x in r["ficheros"]}
    assert roles["m_[C].wav"] == "C_AGGREGATE"
    assert roles["m_Reverb [C].wav"] == "C_REVERB"
    assert roles["m_Others [C].wav"] == "C_OTHERS"


def test_roles_a_b_d_e():
    r = clasificador.clasificar(_fic(["m_[A].wav", "m_[B].wav", "m_[D].wav", "m_[E].wav"]),
                                _doc())
    roles = {x["nombre"]: x["rol"] for x in r["ficheros"]}
    assert roles == {"m_[A].wav": "A_RESTORED", "m_[B].wav": "B_INSTRUMENT",
                     "m_[D].wav": "D_DRY_VOCAL", "m_[E].wav": "E_VOCALS"}


def test_empate_de_prioridad_es_ambiguo():
    d = _doc()
    d["perfiles"].append({"model_id": "trampa", "version": "0", "roles": {
        "A_RESTORED": [{"regex": "^x_\\[A\\]\\.wav$", "prioridad": 50}],
        "D_DRY_VOCAL": [{"regex": "^x_\\[A\\]\\.wav$", "prioridad": 50}]}})
    r = clasificador.clasificar(_fic(["x_[A].wav"]), d)
    assert r["ficheros"][0]["estado"] == "AMBIGUO"


def test_nombre_real_del_manifiesto_se_clasifica():
    r = clasificador.clasificar(
        _fic(["par1_roformer_instrum_only.wav", "par1_roformer_vocals_full.wav"]), _doc())
    roles = {x["nombre"]: x["rol"] for x in r["ficheros"]}
    assert roles["par1_roformer_instrum_only.wav"] == "INSTRUMENTAL"
    assert roles["par1_roformer_vocals_full.wav"] == "VOCALS"


# -------------------------------------------------------------- agrupador
def test_corridas_distintas_no_se_mezclan():
    fic = []
    for run in ("runA", "runB"):
        fic.append({"nombre": f"{run}_[A].wav", "rel": f"x/{run}_[A].wav",
                    "ruta": f"/t/x/{run}_[A].wav", "dir": "x", "bytes": 0,
                    "rol": "A_RESTORED", "perfil": "reverb_tagged", "run": run,
                    "estado": "CLASIFICADO", "prioridad": 20, "evidencia": {},
                    "descartados": []})
    gs = agrupador.agrupar({"ficheros": fic, "ambiguos": []})
    assert len(gs) == 2
    assert all(len(g["roles"]["A_RESTORED"]) == 1 for g in gs)


def test_duplicado_en_misma_corrida():
    fic = []
    for n in ("runA_[C].wav", "runA_Reverb [C].wav"):
        fic.append({"nombre": n, "rel": f"x/{n}", "ruta": f"/t/x/{n}", "dir": "x",
                    "bytes": 0, "rol": "C_AGGREGATE", "perfil": "reverb_tagged",
                    "run": "runA", "estado": "CLASIFICADO", "prioridad": 10,
                    "evidencia": {}, "descartados": []})
    gs = agrupador.agrupar({"ficheros": fic, "ambiguos": []})
    assert len(gs) == 1 and gs[0]["duplicados"]


# ---------------------------------------------------------------- C_total
def test_c_total_nunca_suma_agregado_y_subcomponentes():
    pf = next(p for p in _doc()["perfiles"] if p["model_id"] == "reverb_tagged")
    r = c_total.construir({"C_AGGREGATE": [{"rel": "a", "ruta": "/nope"}],
                           "C_REVERB": [{"rel": "b", "ruta": "/nope"}],
                           "C_OTHERS": [{"rel": "c", "ruta": "/nope"}]}, pf)
    assert r["estado"] == "AMBIGUOUS" and "C_total" not in r


def test_c_total_un_solo_subcomponente_no_se_infiere():
    pf = next(p for p in _doc()["perfiles"] if p["model_id"] == "reverb_tagged")
    r = c_total.construir({"C_OTHERS": [{"rel": "c", "ruta": "/nope"}]}, pf)
    assert r["estado"] == "INCOMPLETE"


def test_c_total_dividido_suma_dos_sumandos(tmp_path):
    V_, I_, _ = _senales()
    a = _wav(str(tmp_path / "rev.wav"), I_ * 0.5)
    b = _wav(str(tmp_path / "oth.wav"), I_ * 0.3)
    pf = next(p for p in _doc()["perfiles"] if p["model_id"] == "reverb_tagged")
    r = c_total.construir({"C_REVERB": [{"rel": "rev.wav", "ruta": a}],
                           "C_OTHERS": [{"rel": "oth.wav", "ruta": b}]}, pf)
    assert r["estado"] == "OK"
    assert r["estrategia"] == "split_reverb_others"
    assert len(r["sumandos"]) == 2
    assert np.allclose(r["C_total"], I_ * 0.8, atol=1e-7)


def test_c_total_agregado_un_sumando(tmp_path):
    V_, I_, _ = _senales()
    a = _wav(str(tmp_path / "c.wav"), I_ * 0.8)
    pf = next(p for p in _doc()["perfiles"] if p["model_id"] == "reverb_tagged")
    r = c_total.construir({"C_AGGREGATE": [{"rel": "c.wav", "ruta": a}]}, pf)
    assert r["estado"] == "OK" and r["estrategia"] == "single_aggregate"
    assert len(r["sumandos"]) == 1


# -------------------------------------------------------------- validador
def test_validador_frames_distintos(tmp_path):
    V_, I_, _ = _senales()
    a = _wav(str(tmp_path / "a.wav"), I_)
    b = _wav(str(tmp_path / "b.wav"), I_[:100])
    r = V.validar_entradas([("a", a), ("b", b)])
    assert r["ok"] is False and any("frames" in m for m in r["motivos"])


def test_validador_sr_distinta(tmp_path):
    V_, I_, _ = _senales()
    a = _wav(str(tmp_path / "a.wav"), I_, SR)
    b = _wav(str(tmp_path / "b.wav"), I_, 48000)
    r = V.validar_entradas([("a", a), ("b", b)])
    assert r["ok"] is False and any("sample_rate" in m for m in r["motivos"])


def test_validador_canales_distintos(tmp_path):
    V_, I_, _ = _senales()
    a = _wav(str(tmp_path / "a.wav"), I_)
    b = _wav(str(tmp_path / "b.wav"), I_[:, :1])
    r = V.validar_entradas([("a", a), ("b", b)])
    assert r["ok"] is False and any("canales" in m for m in r["motivos"])


def test_validador_subtype(tmp_path):
    V_, I_, _ = _senales()
    a = _wav(str(tmp_path / "a.wav"), I_)
    b = _wav(str(tmp_path / "b.wav"), I_, SR, "PCM_16")
    r = V.validar_entradas([("a", a), ("b", b)])
    assert r["ok"] is False and any("subtype" in m for m in r["motivos"])


def test_validador_nan_rechazado(tmp_path):
    V_, I_, _ = _senales()
    a = I_.copy()
    a[5, 0] = np.nan
    f1 = _wav(str(tmp_path / "a.wav"), I_)
    f2 = _wav(str(tmp_path / "b.wav"), a)
    r = V.validar_entradas([("a", f1), ("b", f2)])
    assert r["ok"] is False and r["rechazado"] is True


def test_validador_identicas_ok(tmp_path):
    V_, I_, _ = _senales()
    f1 = _wav(str(tmp_path / "a.wav"), I_)
    f2 = _wav(str(tmp_path / "b.wav"), I_)
    assert V.validar_entradas([("a", f1), ("b", f2)])["ok"] is True


# ------------------------------------------------------------- inventario
def test_inventario_registra_ignorados(tmp_path):
    V_, I_, _ = _senales()
    _wav(str(tmp_path / "x.wav"), I_)
    (tmp_path / "notas.txt").write_text("hola")
    inv = inventario.inventariar(str(tmp_path), [".wav"])
    assert inv["n_ficheros"] == 1
    assert any(i["nombre"] == "notas.txt" for i in inv["ignorados"])


def test_inventario_no_abre_audio(tmp_path):
    (tmp_path / "falso.wav").write_bytes(b"no soy audio")
    inv = inventario.inventariar(str(tmp_path), [".wav"])
    assert inv["n_ficheros"] == 1          # se inventaria sin intentar leerlo


def _ejecutar_todos():
    import inspect
    fallos, total = [], 0
    import tempfile
    for nombre, fn in sorted(globals().items()):
        if not nombre.startswith("test_") or not callable(fn):
            continue
        total += 1
        args = []
        if "tmp_path" in inspect.signature(fn).parameters:
            args = [__import__("pathlib").Path(tempfile.mkdtemp())]
        try:
            fn(*args)
        except Exception as e:                                          # noqa: BLE001
            fallos.append((nombre, f"{type(e).__name__}: {e}"))
    print(f"{total - len(fallos)}/{total} tests OK")
    for n, m in fallos:
        print(f"  FALLA {n}: {m}")
    return 0 if not fallos else 1


if __name__ == "__main__":
    sys.exit(_ejecutar_todos())
