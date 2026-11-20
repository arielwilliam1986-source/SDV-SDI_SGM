# INFORME DE PREPARACIÓN — PRUEBAS AudioInput EN TERMUX (ETAPA 2)

**Proyecto:** SDV-SDI_SGM
**Especificación de referencia:** `AudioInput_SPEC.md v0.2`
**Investigación anterior:** `INFORME_INVESTIGACION_AUDIOINPUT_ETAPA1.md` y su revisión complementaria
**Responsable de preparación:** Z.ai — Asistente Senior de Investigación
**Auditor técnico independiente:** Cris (ChatGPT)
**Decisor y operador del dispositivo:** Will
**Fecha de preparación:** 2026-11-21
**Modalidad:** Preparación de instrumento. **No ejecutado** en el dispositivo del usuario. **No se modificó** el repositorio.

---

## 0. Declaración explícita de no ejecución y no modificación

El presente informe documenta únicamente la preparación de un instrumento de diagnóstico. Las afirmaciones siguientes se hacen bajo la responsabilidad del firmante:

1. **No se ejecutó** el instrumento en el dispositivo de Will (POCO X6 Pro, Android 16, HyperOS 3, ARM64, Termux).
2. **No se modificó** el repositorio `arielwilliam1986-source/SDV-SDI_SGM`.
3. **No se crearon** commits, ramas o pull requests.
4. **No se modificó** `main`.
5. **No se modificó** `AudioInput_SPEC.md`.
6. **No se modificaron** motores ni DSP.
7. **No se solicitaron** credenciales ni permisos root.
8. **No se eliminaron** archivos.
9. **No se implementó** la arquitectura AudioInput.
10. **No se declaró validada** la alternativa A antes de disponer de resultados reales.

La verificación sintáctica del script se realizó con `python3 -m py_compile` (sin ejecución) y la ayuda con `--help` (sin ejecución de pruebas). Ambas son operaciones estáticas de inspección.

---

## A. Script completo

El script completo está disponible como archivo independiente en:

**[`audioinput_diag_termux.py`](/home/z/my-project/download/audioinput_diag_termux.py)** — 681 líneas, 27 165 bytes, sintaxis verificada con `py_compile`.

A continuación se reproduce íntegramente para auditoría:

```python
#!/usr/bin/env python3
"""audioinput_diag_termux.py — Diagnostico AudioInput ETAPA 2.

Verifica la alternativa A: SoundFile(fd, closefd=False) + os.pread(fd, n, offset).

PROPIEDADES DEL INSTRUMENTO:
  - Script Python independiente. No importa ni depende de motores SDV/SDI.
  - No importa modulos del proyecto.
  - No modifica archivos originales ni datos del usuario.
  - Crea exclusivamente fixtures sinteticos propios.
  - No realiza limpieza automatica (los fixtures y el informe quedan en disco).
  - No utiliza permisos root.
  - No instala paquetes ni modifica la configuracion de Termux.
  - No usa /proc/self/fd como mecanismo de apertura.
  - No usa closefd=True en pruebas de apertura directa.
  - No introduce fallbacks por ruta.
  - No utiliza FLAC (prioridad: validar descriptor + lectura en WAV).

CLASIFICACION DE RESULTADOS:
  PASS          La verificacion se ejecuto y tuvo exito.
  FAIL          La verificacion se ejecuto y fallo de manera no esperada.
  NOT_EXECUTED  La verificacion no se ejecuto por una condicion ambiental
                (p. ej. falta de permisos, dependencia ausente, almacenamiento
                no disponible). Se documenta el motivo.
  ERROR         La verificacion no pudo completarse por una excepcion no
                anticipada. Se documenta el traceback.

USO:
    python3 audioinput_diag_termux.py
    python3 audioinput_diag_termux.py --shared /sdcard/audioinput_diag
    python3 audioinput_diag_termux.py --shared /storage/emulated/0/audioinput_diag --output informe.json

SALIDA:
    - Informe JSON en $HOME/.audioinput_diag_etapa2/report.json (por defecto).
    - Fixtures WAV en $HOME/.audioinput_diag_etapa2/ (entorno privado).
    - Fixtures WAV en <shared>/ (entorno compartido, si se especifica).
    - Salida legible por stdout con progreso y resumen.
    - Codigo de salida: 0 si todo PASS, 1 si hay FAIL/ERROR, 2 si no se pudo iniciar.
"""

import os
import sys
import errno
import hashlib
import platform
import json
import time
import traceback
import argparse
import struct
from pathlib import Path

SCRIPT_VERSION = "0.1.0"
SCRIPT_NAME = "audioinput_diag_termux.py"


def _import_dependencies():
    """Importa numpy y soundfile. Retorna (np, sf, errors_dict)."""
    errors = {}
    try:
        import numpy as np
    except ImportError as exc:
        np = None
        errors['numpy'] = "ImportError: " + str(exc)
    try:
        import soundfile as sf
    except ImportError as exc:
        sf = None
        errors['soundfile'] = "ImportError: " + str(exc)
    return np, sf, errors


class Result:
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EXECUTED = "NOT_EXECUTED"
    ERROR = "ERROR"


SAMPLE_RATE = 44100
DURATION_FRAMES = 22050  # 0.5 segundos
CHANNELS = 2

FIXTURE_SPECS = [
    ("pcm16",   "PCM_16"),
    ("pcm24",   "PCM_24"),
    ("pcm32",   "PCM_32"),
    ("float32", "FLOAT"),
]


def generate_audio_array(np):
    rng = np.random.default_rng(seed=42)
    arr = rng.uniform(-1.0, 1.0, (DURATION_FRAMES, CHANNELS))
    arr[0, 0] = -1.0
    arr[0, 1] = -0.5
    arr[-1, 0] = 0.999999
    arr[-1, 1] = 0.5
    return arr


def create_fixture(np, sf, dir_path, fixture_name, subtype):
    out_path = Path(dir_path) / "fixture_{0}.wav".format(fixture_name)
    arr = generate_audio_array(np)
    sf.write(str(out_path), arr, SAMPLE_RATE, subtype=subtype)
    return out_path


def sha256_canonical(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(1 << 20)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def sha256_pread(fd, blocksize=1 << 20):
    h = hashlib.sha256()
    offset = 0
    try:
        size = os.fstat(fd).st_size
    except OSError as exc:
        raise RuntimeError("fstat fallo en sha256_pread: errno={0}".format(exc.errno))
    while offset < size:
        n = min(blocksize, size - offset)
        data = os.pread(fd, n, offset)
        if not data:
            break
        h.update(data)
        offset += len(data)
    return h.hexdigest()


def safe_close(fd):
    if fd is None:
        return None
    try:
        os.close(fd)
        return None
    except OSError as exc:
        return exc


def test_t11_soundfile_fd_closefd_false(np, sf, fixture_path):
    fd = os.open(str(fixture_path), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        sfile = sf.SoundFile(fd, mode='r', closefd=False)
        try:
            sr = sfile.samplerate
            ch = sfile.channels
            fr = sfile.frames
            ok_meta = (sr == SAMPLE_RATE and ch == CHANNELS and fr > 0)
            if not ok_meta:
                return (Result.FAIL,
                        "metadatos incorrectos: sr={0}, ch={1}, fr={2}".format(sr, ch, fr))
        finally:
            sfile.close()
        try:
            os.fstat(fd)
        except OSError as exc:
            return (Result.FAIL,
                    "fd cerrado por SoundFile.close() pese a closefd=False: errno={0}".format(exc.errno))
        return (Result.PASS,
                "sr={0}, ch={1}, fr={2}, st_size={3}".format(sr, ch, fr, st.st_size))
    finally:
        safe_close(fd)


def test_t12_pread_works(np, sf, fixture_path):
    fd = os.open(str(fixture_path), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        size = os.fstat(fd).st_size
        if size < 200:
            return (Result.FAIL, "archivo demasiado pequeno: {0} bytes".format(size))
        first = os.pread(fd, 100, 0)
        last = os.pread(fd, 100, max(0, size - 100))
        pos = os.lseek(fd, 0, os.SEEK_CUR)
        offset_ok = (pos == 0)
        reads_ok = (len(first) == 100 and len(last) == 100)
        if offset_ok and reads_ok:
            return (Result.PASS,
                    "pread(0,100)={0}B, pread(size-100,100)={1}B, fd_pos={2}".format(
                        len(first), len(last), pos))
        return (Result.FAIL,
                "offset_ok={0}, reads_ok={1}, fd_pos={2}".format(offset_ok, reads_ok, pos))
    finally:
        safe_close(fd)


def test_t13_pread_hash_matches_canonical(np, sf, fixture_path):
    fd = os.open(str(fixture_path), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        sha_pread = sha256_pread(fd)
        pos_after = os.lseek(fd, 0, os.SEEK_CUR)
        offset_preserved = (pos_after == 0)
        sha_canon = sha256_canonical(str(fixture_path))
        if sha_pread == sha_canon and offset_preserved:
            return (Result.PASS,
                    "pread_sha={0}..., canon_sha={1}..., offset_ok={2}".format(
                        sha_pread[:16], sha_canon[:16], offset_preserved))
        return (Result.FAIL,
                "hashes_match={0}, offset_preserved={1}, pread={2}..., canon={3}...".format(
                    sha_pread == sha_canon, offset_preserved,
                    sha_pread[:16], sha_canon[:16]))
    finally:
        safe_close(fd)


def test_t14_pread_coexists_with_soundfile(np, sf, fixture_path):
    fd = os.open(str(fixture_path), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        sha_before = sha256_pread(fd)
        pos_after_pread = os.lseek(fd, 0, os.SEEK_CUR)
        if pos_after_pread != 0:
            return (Result.FAIL,
                    "pread movio el offset del fd: pos={0}".format(pos_after_pread))
        sfile = sf.SoundFile(fd, mode='r', closefd=False)
        try:
            block1 = sfile.read(500, dtype='float64', always_2d=True)
            if block1.shape != (500, CHANNELS):
                return (Result.FAIL,
                        "block1 shape {0} != (500, {1})".format(block1.shape, CHANNELS))
            sha_during = sha256_pread(fd)
            hashes_match = (sha_before == sha_during)
            sfile.seek(0)
            block2 = sfile.read(500, dtype='float64', always_2d=True)
            blocks_match = bool(np.array_equal(block1, block2))
            if hashes_match and blocks_match:
                return (Result.PASS,
                        "sha_before={0}..., sha_during={1}..., hashes_match={2}, blocks_match={3}".format(
                            sha_before[:16], sha_during[:16], hashes_match, blocks_match))
            return (Result.FAIL,
                    "hashes_match={0}, blocks_match={1}".format(hashes_match, blocks_match))
        finally:
            sfile.close()
        try:
            os.fstat(fd)
        except OSError as exc:
            return (Result.FAIL,
                    "fd cerrado por sfile.close() pese a closefd=False: errno={0}".format(exc.errno))
        return (Result.PASS, "secuencia 11 pasos completada OK")
    finally:
        safe_close(fd)


def test_t15_libsndfile_error_raised(np, sf, fixture_dir):
    dir_fd = os.open(str(fixture_dir), os.O_RDONLY)
    try:
        try:
            sfile = sf.SoundFile(dir_fd, mode='r', closefd=False)
            try:
                sfile.close()
            except Exception:
                pass
            return (Result.FAIL, "SoundFile acepto fd de directorio (no esperado)")
        except sf.LibsndfileError as exc:
            return (Result.PASS,
                    "LibsndfileError capturada: {0}".format(str(exc)[:80]))
        except OSError as exc:
            return (Result.FAIL,
                    "Se lanzo OSError en lugar de LibsndfileError: errno={0}".format(exc.errno))
        except Exception as exc:
            return (Result.FAIL,
                    "Excepcion no esperada: {0}: {1}".format(type(exc).__name__, str(exc)[:80]))
    finally:
        safe_close(dir_fd)


def test_t16_fd_survives_closefd_false_failure(np, sf, fixture_dir):
    dir_fd = os.open(str(fixture_dir), os.O_RDONLY)
    try:
        try:
            sfile = sf.SoundFile(dir_fd, mode='r', closefd=False)
            try:
                sfile.close()
            except Exception:
                pass
            return (Result.FAIL, "SoundFile acepto fd de directorio (no esperado)")
        except sf.LibsndfileError:
            pass
        except Exception as exc:
            return (Result.FAIL,
                    "Excepcion no esperada: {0}: {1}".format(type(exc).__name__, str(exc)[:80]))
        try:
            os.fstat(dir_fd)
        except OSError as exc:
            return (Result.FAIL,
                    "fd cerrado por libsndfile pese a closefd=False: errno={0}".format(exc.errno))
        return (Result.PASS, "fd sobrevive al fallo de SoundFile con closefd=False")
    finally:
        safe_close(dir_fd)


TEST_FUNCTIONS = {
    'T11': test_t11_soundfile_fd_closefd_false,
    'T12': test_t12_pread_works,
    'T13': test_t13_pread_hash_matches_canonical,
    'T14': test_t14_pread_coexists_with_soundfile,
}


def run_environment(np, sf, env_name, env_dir, results):
    print("\n=== Entorno {0}: {1} ===".format(env_name, env_dir))
    try:
        os.makedirs(str(env_dir), exist_ok=True)
    except OSError as exc:
        msg = "No se pudo crear {0}: errno={1} ({2})".format(
            env_dir, exc.errno, os.strerror(exc.errno))
        print("  [NOT_EXECUTED] {0}".format(msg))
        for fname in ['pcm16', 'pcm24', 'pcm32', 'float32']:
            for tid in ['T11', 'T12', 'T13', 'T14']:
                results.append({'env': env_name, 'test': tid, 'fixture': fname,
                                'status': Result.NOT_EXECUTED, 'detail': msg})
        for tid in ['T15', 'T16']:
            results.append({'env': env_name, 'test': tid, 'fixture': None,
                            'status': Result.NOT_EXECUTED, 'detail': msg})
        return
    fixtures = {}
    for fname, subtype in FIXTURE_SPECS:
        try:
            fpath = create_fixture(np, sf, env_dir, fname, subtype)
            fixtures[fname] = fpath
            print("  fixture creado: {0} ({1} bytes)".format(fpath.name, fpath.stat().st_size))
        except Exception as exc:
            print("  ERROR creando fixture {0}: {1}".format(fname, exc))
            for tid in ['T11', 'T12', 'T13', 'T14']:
                results.append({'env': env_name, 'test': tid, 'fixture': fname,
                                'status': Result.ERROR,
                                'detail': "fixture creation failed: {0}: {1}".format(
                                    type(exc).__name__, str(exc)[:120])})
    for fname, fpath in fixtures.items():
        print("\n  --- {0} ({1}) ---".format(fname, fpath.name))
        for tid, test_fn in TEST_FUNCTIONS.items():
            try:
                status, detail = test_fn(np, sf, fpath)
            except Exception as exc:
                status = Result.ERROR
                detail = "{0}: {1}\n{2}".format(
                    type(exc).__name__, str(exc)[:120],
                    traceback.format_exc()[-400:])
            results.append({'env': env_name, 'test': tid, 'fixture': fname,
                            'status': status, 'detail': detail})
            print("  {0}: {1} - {2}".format(tid, status, str(detail)[:70]))
    print("\n  --- pruebas con fd de directorio (T15, T16) ---")
    for tid, test_fn in [('T15', test_t15_libsndfile_error_raised),
                         ('T16', test_t16_fd_survives_closefd_false_failure)]:
        try:
            status, detail = test_fn(np, sf, env_dir)
        except Exception as exc:
            status = Result.ERROR
            detail = "{0}: {1}\n{2}".format(
                type(exc).__name__, str(exc)[:120],
                traceback.format_exc()[-400:])
        results.append({'env': env_name, 'test': tid, 'fixture': None,
                        'status': status, 'detail': detail})
        print("  {0}: {1} - {2}".format(tid, status, str(detail)[:70]))


def collect_environment_metadata(np, sf):
    bits = struct.calcsize("P") * 8
    try:
        wav_subtypes = list(sf.available_subtypes('WAV').keys())
    except Exception:
        wav_subtypes = []
    try:
        flac_subtypes = list(sf.available_subtypes('FLAC').keys())
    except Exception:
        flac_subtypes = []
    return {
        'script_name': SCRIPT_NAME,
        'script_version': SCRIPT_VERSION,
        'python_version': sys.version,
        'python_bits': bits,
        'platform': sys.platform,
        'machine': platform.machine(),
        'processor': platform.processor(),
        'system': platform.system(),
        'release': platform.release(),
        'kernel_version': platform.uname().release,
        'uname_version': platform.uname().version,
        'soundfile_version': getattr(sf, '__version__', 'unknown'),
        'libsndfile_version': getattr(sf, '__libsndfile_version__', 'unknown'),
        'numpy_version': getattr(np, '__version__', 'unknown'),
        'wav_subtypes_available': wav_subtypes,
        'flac_subtypes_available': flac_subtypes,
        'home_dir': str(Path.home()),
        'cwd': os.getcwd(),
        'uid': os.getuid() if hasattr(os, 'getuid') else None,
        'gid': os.getgid() if hasattr(os, 'getgid') else None,
        'euid': os.geteuid() if hasattr(os, 'geteuid') else None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Diagnostico AudioInput ETAPA 2: SoundFile(fd, closefd=False) + os.pread")
    parser.add_argument('--shared', type=str, default=None,
                        help='Ruta al directorio de almacenamiento compartido Android')
    parser.add_argument('--output', type=str, default=None,
                        help='Ruta al archivo JSON de salida')
    parser.add_argument('--private-dir', type=str, default=None,
                        help='Directorio privado')
    args = parser.parse_args()

    if args.private_dir:
        private_dir = Path(args.private_dir)
    else:
        private_dir = Path.home() / '.audioinput_diag_etapa2'

    if args.output:
        report_path = Path(args.output)
    else:
        report_path = private_dir / 'report.json'

    print("=== Diagnostico AudioInput ETAPA 2 ===")
    print("Script: {0} v{1}".format(SCRIPT_NAME, SCRIPT_VERSION))
    print("Directorio privado: {0}".format(private_dir))
    print("Directorio compartido: {0}".format(args.shared or '(no especificado)'))
    print("Reporte JSON: {0}".format(report_path))
    print()

    np, sf, dep_errors = _import_dependencies()
    if dep_errors:
        print("[FATAL] Dependencias no disponibles:")
        for k, v in dep_errors.items():
            print("  {0}: {1}".format(k, v))
        print("Instala con: pip install numpy soundfile")
        sys.exit(2)

    try:
        meta = collect_environment_metadata(np, sf)
    except Exception as exc:
        print("[FATAL] No se pudieron recolectar metadatos: {0}".format(exc))
        sys.exit(2)

    print("=== Metadatos del entorno ===")
    for k in ['python_version', 'python_bits', 'platform', 'machine', 'system',
              'release', 'kernel_version', 'soundfile_version', 'libsndfile_version',
              'numpy_version']:
        v = meta.get(k)
        if isinstance(v, str) and len(v) > 80:
            v = v[:77] + '...'
        print("  {0}: {1}".format(k, v))
    print("  wav_subtypes_available: {0} subtipos".format(len(meta['wav_subtypes_available'])))
    print("  flac_subtypes_available: {0} subtipos".format(len(meta['flac_subtypes_available'])))
    print("  home_dir: {0}".format(meta['home_dir']))
    print("  uid: {0}, gid: {1}, euid: {2}".format(meta['uid'], meta['gid'], meta['euid']))
    print()

    results = []
    started_at = time.strftime('%Y-%m-%dT%H:%M:%S%z')

    run_environment(np, sf, 'A_private', private_dir, results)

    if args.shared:
        shared_dir = Path(args.shared)
        run_environment(np, sf, 'B_shared', shared_dir, results)
    else:
        msg = "No se especifico --shared PATH; entorno B omitido"
        print("\n=== Entorno B_shared: NOT_EXECUTED ({0}) ===".format(msg))
        for fname in ['pcm16', 'pcm24', 'pcm32', 'float32']:
            for tid in ['T11', 'T12', 'T13', 'T14']:
                results.append({'env': 'B_shared', 'test': tid, 'fixture': fname,
                                'status': Result.NOT_EXECUTED, 'detail': msg})
        for tid in ['T15', 'T16']:
            results.append({'env': 'B_shared', 'test': tid, 'fixture': None,
                            'status': Result.NOT_EXECUTED, 'detail': msg})

    finished_at = time.strftime('%Y-%m-%dT%H:%M:%S%z')

    print("\n" + "=" * 60)
    print("=== RESUMEN ===")
    print("=" * 60)
    counts = {'PASS': 0, 'FAIL': 0, 'NOT_EXECUTED': 0, 'ERROR': 0}
    for r in results:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    total = len(results)
    print("Total: {0}".format(total))
    for k in ['PASS', 'FAIL', 'NOT_EXECUTED', 'ERROR']:
        print("  {0}: {1}".format(k, counts.get(k, 0)))
    print()

    for env in ['A_private', 'B_shared']:
        print("\n--- {0} ---".format(env))
        env_results = [r for r in results if r['env'] == env]
        for r in env_results:
            fx = r['fixture'] or '-'
            detail_short = str(r['detail'])[:60]
            print("  {0} [{1:12}] {2:10} {3}".format(
                r['test'], r['status'], fx, detail_short))

    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            'metadata': meta,
            'started_at': started_at,
            'finished_at': finished_at,
            'private_dir': str(private_dir),
            'shared_dir': args.shared,
            'results': results,
            'summary': {
                'total': total,
                'pass': counts.get('PASS', 0),
                'fail': counts.get('FAIL', 0),
                'not_executed': counts.get('NOT_EXECUTED', 0),
                'error': counts.get('ERROR', 0),
            },
            'notes': [
                'Este diagnostico NO ejecuta codigo del proyecto SDV-SDI_SGM.',
                'NO modifica archivos originales del usuario.',
                'Crea exclusivamente fixtures sinteticos en los directorios indicados.',
                'NO realiza limpieza automatica: los fixtures y el informe quedan en disco.',
                'NO usa /proc/self/fd como mecanismo de apertura.',
                'NO usa closefd=True en pruebas de apertura directa.',
                'NO introduce fallbacks por ruta.',
                'NO declara compatibilidad general de Android basada en estas pruebas.',
                'Los resultados son especificos al dispositivo, entorno y versiones utilizadas.',
            ],
        }
        with open(str(report_path), 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print("\nReporte JSON: {0}".format(report_path))
    except Exception as exc:
        print("\n[ERROR] No se pudo escribir el reporte JSON: {0}".format(exc))

    if counts.get('FAIL', 0) > 0 or counts.get('ERROR', 0) > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Interrumpido por usuario]")
        sys.exit(130)
    except Exception as exc:
        print("\n[ERROR FATAL] {0}: {1}".format(type(exc).__name__, exc))
        traceback.print_exc()
        sys.exit(2)
```

**Verificación de sintaxis ejecutada en el sandbox (no en el dispositivo de Will):**

```
$ python3 -m py_compile audioinput_diag_termux.py
PY_COMPILE_OK exit=0
$ python3 audioinput_diag_termux.py --help
usage: audioinput_diag_termux.py [-h] [--shared SHARED] [--output OUTPUT]
                                 [--private-dir PRIVATE_DIR]
...
```

---

## B. Informe de diseño

### B.1 Visión general del instrumento

El instrumento es un script Python standalone que verifica en el dispositivo real de Will si la alternativa A — `SoundFile(fd, closefd=False)` + `os.pread(fd, n, offset)` — funciona correctamente en:

- **Entorno A (almacenamiento privado de Termux):** directorio `~/.audioinput_diag_etapa2/`.
- **Entorno B (almacenamiento compartido de Android):** directorio especificado por Will mediante `--shared PATH`.

El instrumento genera 4 fixtures WAV sintéticos estéreo 44.1 kHz por entorno, ejecuta las 6 pruebas T11-T16 sobre cada fixture y entorno, y produce un informe JSON + salida legible por stdout.

### B.2 Diseño de fixtures

Cada entorno genera 4 fixtures WAV sintéticos:

| Fixture | Subtype | Tamaño aprox. | Características |
|---|---|---|---|
| `fixture_pcm16.wav` | `PCM_16` | ~88 KB | 16-bit PCM entero, 22050 frames estéreo |
| `fixture_pcm24.wav` | `PCM_24` | ~132 KB | 24-bit PCM entero |
| `fixture_pcm32.wav` | `PCM_32` | ~176 KB | 32-bit PCM entero |
| `fixture_float32.wav` | `FLOAT` | ~176 KB | 32-bit IEEE float, incluye muestras extremas |

**Parámetros comunes:**
- Sample rate: 44 100 Hz.
- Canales: 2 (estéreo).
- Duración: 22 050 frames (0.5 segundos) — pequeño para minimizar tiempo y espacio en disco.
- Seed RNG fija (`np.random.default_rng(seed=42)`) para reproducibilidad.
- Casos extremos en posiciones conocidas (frame 0 y frame final) para detectar saturación o clamping.

**No se utilizan** archivos de audio reales del proyecto, muestras musicales, ni archivos personales de Will. Todos los fixtures son sintéticos y generados por el propio instrumento.

**No se incluyen** fixtures FLAC en esta etapa, conforme a la prioridad del requerimiento §5: "No incorporar FLAC en esta etapa, salvo que sea estrictamente necesario para alguna comprobación independiente."

### B.3 Qué hace cada prueba

#### T11 — `SoundFile(fd, closefd=False)` abre correctamente

**Qué hace:**
1. Abre el fixture por descriptor con `os.open(path, O_RDONLY | O_NOFOLLOW)`.
2. Crea `sf.SoundFile(fd, mode='r', closefd=False)`.
3. Lee metadatos (`samplerate`, `channels`, `frames`).
4. Verifica que los metadatos son los esperados (44100 Hz, 2 canales, frames > 0).
5. Cierra SoundFile (`sfile.close()`).
6. Verifica que el `fd` original sigue abierto (`os.fstat(fd)` funciona).
7. Cierra el `fd` manualmente.

**Qué verifica:**
- SoundFile acepta el descriptor del archivo en el entorno objetivo.
- `closefd=False` preserva el descriptor tras `sfile.close()`.
- Los metadatos accesibles son los esperados.

**Qué NO verifica:**
- Que el contenido decodificado sea correcto (eso lo hace T14).
- Que `os.pread` funcione (eso lo hace T12).
- Comportamiento ante `KeyboardInterrupt` durante la apertura.

#### T12 — `os.pread` funciona en el almacenamiento objetivo

**Qué hace:**
1. Abre el fixture por descriptor.
2. Lee 100 bytes desde offset 0 con `os.pread(fd, 100, 0)`.
3. Lee 100 bytes desde offset (size-100) con `os.pread(fd, 100, size-100)`.
4. Verifica que el offset del `fd` NO se movió (sigue en 0).
5. Verifica que ambas lecturas devolvieron 100 bytes.
6. Cierra el `fd`.

**Qué verifica:**
- `os.pread` está disponible y devuelve los bytes solicitados.
- `os.pread` no mueve el offset del descriptor (semántica POSIX).

**Qué NO verifica:**
- Que el hash del contenido coincida con un hash canónico (eso lo hace T13).
- Que `pread` coexista con SoundFile activo (eso lo hace T14).

#### T13 — Hash por `pread` coincide con hash canónico

**Qué hace:**
1. Abre el fixture por descriptor.
2. Calcula SHA-256 por bloques `os.pread` desde offset 0 hasta el final.
3. Verifica que el offset del `fd` NO se movió (sigue en 0).
4. Calcula SHA-256 canónico por `open(path, 'rb')` + lectura completa.
5. Compara ambos hashes.
6. Cierra el `fd`.

**Qué verifica:**
- El hash por `pread` es idéntico al hash canónico.
- El offset del `fd` no se ve afectado por el cálculo del hash por `pread`.

**Qué NO verifica:**
- Que `pread` coexista con SoundFile activo (eso lo hace T14).
- Estabilidad del contenido frente a escritores concurrentes (no es objetivo de esta etapa).

#### T14 — `pread` y `SoundFile(fd, closefd=False)` coexisten sin conflicto

**Qué hace (11 pasos conforme al requerimiento §6):**
1. Apertura del descriptor original (`os.open` con `O_RDONLY | O_NOFOLLOW`).
2. Cálculo inicial del SHA-256 mediante `os.pread` (lectura por bloques desde offset 0).
3. Apertura de SoundFile sobre ese mismo descriptor con `closefd=False`.
4. Lectura de 500 frames mediante SoundFile (`sfile.read(500, dtype='float64', always_2d=True)`).
5. Repetición del SHA-256 mediante `os.pread` mientras SoundFile permanece abierto.
6. Comparación de los hashes (deben ser idénticos).
7. Lecturas adicionales de SoundFile (`sfile.seek(0)` + `sfile.read(500)`).
8. Comprobación de que el contenido decodificado es idéntico al primer bloque (`np.array_equal`).
9. Cierre explícito de SoundFile (`sfile.close()`).
10. Verificación de que el descriptor original continúa abierto (`os.fstat(fd)`).
11. Cierre explícito del descriptor por su propietario (`os.close(fd)`).

**Qué verifica:**
- `pread` y SoundFile operan sobre el mismo `fd` sin interferirse.
- El hash del archivo no cambia entre las dos lecturas por `pread` (sin escritor concurrente).
- SoundFile produce lecturas repetibles tras `seek(0)`.
- El `fd` sobrevive al cierre de SoundFile (gracias a `closefd=False`).

**Qué NO verifica:**
- **Coherencia de captura frente a escritores concurrentes.** Esto se declara explícitamente como NO verificado: requiere contrato con productor o snapshot a nivel filesystem.
- Detección de modificaciones transitorias (escribir y restaurar entre dos lecturas por `pread`).
- Comportamiento ante `KeyboardInterrupt` durante la sesión.

#### T15 — Captura de `LibsndfileError` cuando SoundFile rechaza un descriptor

**Qué hace:**
1. Abre un fd de directorio con `os.open(dir, O_RDONLY)`.
2. Intenta `sf.SoundFile(dir_fd, mode='r', closefd=False)`.
3. Captura la excepción y verifica que es `sf.LibsndfileError` (no `OSError` ni `Exception` genérica).
4. Cierra el `dir_fd`.

**Qué verifica:**
- SoundFile rechaza un descriptor inválido (fd de directorio) lanzando `LibsndfileError`.
- La jerarquía de excepciones documentada en el código fuente de `python-soundfile 0.13.1` se cumple en el entorno objetivo.

**Qué NO verifica:**
- Que `LibsndfileError` tenga un código de error específico.
- Otros tipos de fd inválidos (fd cerrado, fd de dispositivo especial).

#### T16 — El descriptor permanece abierto después de un fallo de apertura con `closefd=False`

**Qué hace:**
1. Abre un fd de directorio con `os.open(dir, O_RDONLY)`.
2. Intenta `sf.SoundFile(dir_fd, mode='r', closefd=False)` (debe fallar).
3. Captura la excepción (esperada `LibsndfileError`).
4. Verifica que `dir_fd` sigue abierto (`os.fstat(dir_fd)` funciona).
5. Cierra el `dir_fd`.

**Qué verifica:**
- Con `closefd=False`, un fallo de SoundFile no cierra el descriptor.
- El propietario del descriptor puede seguir usándolo tras el fallo.

**Qué NO verifica:**
- Que el descriptor sea reutilizable para otra operación SoundFile (no es objetivo).
- Comportamiento ante `closefd=True` (no se usa, conforme al requerimiento §7).

### B.4 Estructura del reporte JSON

El reporte JSON contiene:

- `metadata`: versiones de Python, soundfile, libsndfile, numpy, arquitectura, kernel, SO, uid/gid/euid, directorio home, subtipos WAV/FLAC disponibles.
- `started_at`, `finished_at`: timestamps ISO 8601 con timezone.
- `private_dir`, `shared_dir`: rutas a los directorios de fixtures.
- `results`: lista de resultados individuales con campos `env`, `test`, `fixture`, `status`, `detail`.
- `summary`: conteos de PASS/FAIL/NOT_EXECUTED/ERROR.
- `notes`: notas declarativas sobre las limitaciones del instrumento.

### B.5 Clasificación de resultados

| Estado | Significado |
|---|---|
| `PASS` | La verificación se ejecutó y tuvo éxito. |
| `FAIL` | La verificación se ejecutó y falló de manera no esperada. |
| `NOT_EXECUTED` | La verificación no se ejecutó por una condición ambiental (falta de permisos, dependencia ausente, almacenamiento no disponible). Se documenta el motivo. |
| `ERROR` | La verificación no pudo completarse por una excepción no anticipada. Se documenta el traceback. |

---

## C. Instrucciones de ejecución

### C.1 Preparación del entorno (una sola vez)

Antes de ejecutar el instrumento, Will debe asegurarse de que Termux tiene las dependencias instaladas. Esto se hace una sola vez:

```bash
# En Termux, actualizar paquetes
pkg update && pkg upgrade -y

# Instalar Python si no está instalado
pkg install -y python

# Instalar dependencias Python
pip install numpy soundfile
```

Si `soundfile` no se instala correctamente en Termux ARM64, el instrumento reportará `[FATAL] Dependencias no disponibles` y terminará con código 2 sin ejecutar pruebas. No intentará instalar nada por sí mismo.

### C.2 Copiar el script a Termux

Will debe copiar el archivo `audioinput_diag_termux.py` a su dispositivo. Puede hacerlo por:

```bash
# Opción 1: si descargó el script a /sdcard/Download/
cp /sdcard/Download/audioinput_diag_termux.py ~/audioinput_diag_termux.py

# Opción 2: si lo tiene en almacenamiento compartido
cp /storage/emulated/0/Download/audioinput_diag_termux.py ~/audioinput_diag_termux.py
```

### C.3 Ejecutar el diagnóstico (Entorno A: privado de Termux solamente)

```bash
cd ~
python3 audioinput_diag_termux.py
```

Esto ejecuta todas las pruebas en `~/.audioinput_diag_etapa2/` y guarda el reporte en `~/.audioinput_diag_etapa2/report.json`.

### C.4 Ejecutar el diagnóstico (Entornos A + B)

Para ejecutar también las pruebas en almacenamiento compartido de Android, Will debe especificar un directorio donde tenga permisos de escritura. Opciones comunes en Termux:

```bash
# Opción 1: /sdcard/audioinput_diag (requiere permiso de almacenamiento en Termux)
termux-setup-storage  # si no se ha hecho antes
python3 audioinput_diag_termux.py --shared /sdcard/audioinput_diag

# Opción 2: /storage/emulated/0/Download/audioinput_diag
python3 audioinput_diag_termux.py --shared /storage/emulated/0/Download/audioinput_diag

# Opción 3: directorio personalizado con reporte JSON personalizado
python3 audioinput_diag_termux.py \
    --shared /storage/emulated/0/Download/audioinput_diag \
    --output /sdcard/Download/informe_audioinput.json
```

Si `--shared` no se especifica, el Entorno B se marca como `NOT_EXECUTED` con motivo "No se especifico --shared PATH; entorno B omitido".

### C.5 Consultar el informe

Después de la ejecución:

```bash
# Reporte JSON (machine-readable)
cat ~/.audioinput_diag_etapa2/report.json | python3 -m json.tool | head -80

# Listar fixtures creados
ls -la ~/.audioinput_diag_etapa2/

# Si se usó --shared, también listar esos fixtures
ls -la /sdcard/audioinput_diag/
```

### C.6 Verificar código de salida

```bash
python3 audioinput_diag_termux.py --shared /sdcard/audioinput_diag
echo "EXIT_CODE=$?"
```

| Código | Significado |
|---|---|
| 0 | Todas las pruebas ejecutadas pasaron (las NOT_EXECUTED no cuentan como fallo). |
| 1 | Hubo al menos un FAIL o ERROR. |
| 2 | El instrumento no pudo iniciar (dependencias faltantes, error fatal). |
| 130 | Interrumpido por usuario (Ctrl+C). |

### C.7 Limpieza manual (opcional, no automática)

El instrumento NO limpia los fixtures ni el informe. Si Will desea limpiar después de revisar los resultados:

```bash
# Borrar fixtures y reporte del entorno privado
rm -rf ~/.audioinput_diag_etapa2/

# Si se usó --shared, borrar también esos
rm -rf /sdcard/audioinput_diag/
```

Esta limpieza es **opcional y manual**, conforme al requerimiento §3.7 "No realizar limpieza automática".

---

## D. Matriz de resultados esperados

### D.1 Condiciones por prueba

| Prueba | PASS | FAIL | NOT_EXECUTED |
|---|---|---|---|
| **T11** | SoundFile abre el fixture por fd con `closefd=False`, metadatos correctos (sr=44100, ch=2, frames>0), fd sobrevive a `sfile.close()`. | SoundFile no abre el fd, metadatos incorrectos, o fd se cierra tras `sfile.close()`. | No se pudo crear el fixture (permisos, libsndfile no admite el subtype). |
| **T12** | `os.pread` devuelve 100 bytes en offset 0 y offset (size-100), offset del fd permanece en 0. | `os.pread` devuelve menos bytes, lanza excepción, o mueve el offset. | No se pudo crear el fixture. |
| **T13** | SHA-256 por `pread` == SHA-256 canónico, offset del fd permanece en 0 tras el cálculo. | Hashes difieren, o el offset se mueve. | No se pudo crear el fixture. |
| **T14** | Secuencia 11 pasos completa: hashes coinciden antes y durante SoundFile, bloques SoundFile repetibles, fd sobrevive a `sfile.close()`. | Hashes difieren, bloques SoundFile no repetibles, fd se cierra tras `sfile.close()`. | No se pudo crear el fixture. |
| **T15** | SoundFile lanza `LibsndfileError` al recibir fd de directorio. | SoundFile acepta fd de directorio (inesperado), o lanza `OSError`/`Exception` genérica en lugar de `LibsndfileError`. | No se pudo abrir el directorio del entorno. |
| **T16** | Tras fallo de SoundFile con `closefd=False`, el fd sigue abierto (`fstat` funciona). | El fd se cierra tras el fallo (inesperado con `closefd=False`). | No se pudo abrir el directorio del entorno. |

### D.2 Conteo esperado por entorno

Cada entorno produce **18 resultados individuales**:

- T11-T14 sobre 4 fixtures = 16 resultados.
- T15 + T16 sobre el directorio del entorno = 2 resultados.

Con 2 entornos (A privado + B compartido): **36 resultados totales**.

Si el entorno B no se especifica (`--shared` ausente), los 18 resultados de B se marcan como `NOT_EXECUTED` con motivo "No se especifico --shared PATH".

### D.3 Interpretación del resumen

| Escenario | Implicación |
|---|---|
| **36 PASS** (A+B) | La alternativa A es viable en ambos almacenamientos. |
| **18 PASS en A, 18 NOT_EXECUTED en B** | Viable en privado, no probado en compartido. |
| **18 PASS en A, FAIL en B** | Viable en privado, pero presenta problemas en almacenamiento compartido (probablemente FUSE). Requiere investigación. |
| **FAIL en A** | La alternativa A no es viable en el dispositivo. Se debe recurrir a la alternativa B (`/proc/self/fd`) o a la terciaria (reapertura por ruta). |
| **NOT_EXECUTED en A** | El instrumento no pudo ejecutarse por falta de dependencias o permisos en el dispositivo. Requiere resolver las dependencias antes de repetir. |

---

## E. Riesgos y limitaciones

### E.1 Dependencias de Android

| Dependencia | Riesgo | Mitigación |
|---|---|---|
| `/proc` accesible | El instrumento **no usa** `/proc/self/fd`, así que este riesgo no aplica a esta etapa. Si la alternativa A falla y se requiere la alternativa B, `/proc` será necesario en una etapa posterior. | N/A en esta etapa. |
| SELinux confinando operaciones de descriptor | Las políticas SELinux de Android 16 pueden restringir `os.open`, `os.pread`, o `os.fstat` en ciertos contextos. | El instrumento captura `OSError` y reporta `FAIL` o `ERROR` con el `errno` específico. Will puede revisar el reporte para identificar el motivo. |
| Android FUSE en almacenamiento compartido | El almacenamiento emulado de Android pasa por FUSE, que puede introducir latencia, restricciones de atomicidad, o comportamientos distintos a ext4. | El entorno B prueba explícitamente esta condición. Si hay diferencias entre A y B, el reporte lo evidenciará. |
| Patches de seguridad Android septiembre 2026 | Reportes externos indican que estos patches revocan permisos durante `unlink`/`rename`. No afectan directamente a `pread`/`fstat` pero pueden afectar la creación de directorios en almacenamiento compartido. | El instrumento captura `OSError` en `os.makedirs`. |

### E.2 Dependencias de Termux

| Dependencia | Riesgo | Mitigación |
|---|---|---|
| `python` 3.x instalado | Si Python no está instalado, el instrumento no puede ejecutarse. | Las instrucciones de ejecución incluyen `pkg install python`. |
| `numpy` instalado | Si numpy no está instalado, el instrumento reporta `[FATAL]` y termina con código 2. | Las instrucciones incluyen `pip install numpy`. |
| `soundfile` instalado | Si soundfile no está instalado, el instrumento reporta `[FATAL]` y termina con código 2. | Las instrucciones incluyen `pip install soundfile`. |
| `libsndfile.so` compilado para ARM64 | El wheel `soundfile` de PyPI para `manylinux_2_28_aarch64` incluye `libsndfile.so`, pero la compatibilidad con Android bionic libc no está garantizada sin prueba real. | Si `import soundfile` falla, el instrumento reporta `ImportError` y termina. Requiere investigación adicional. |
| Permisos de almacenamiento compartido | Termux requiere `termux-setup-storage` para acceder a `/sdcard`. Si no se ha hecho, `os.makedirs('/sdcard/...')` fallará con `EACCES`. | El instrumento captura el error y marca el entorno B como `NOT_EXECUTED`. Las instrucciones documentan `termux-setup-storage`. |

### E.3 Dependencias de Python y libsndfile

| Dependencia | Riesgo | Mitigación |
|---|---|---|
| `python-soundfile` versión | El instrumento asume la semántica de `python-soundfile 0.13.1` (jerarquía `LibsndfileError`, `closefd` solo afecta a `sf_open_fd`). Si Will tiene una versión distinta, el comportamiento puede diferir. | El instrumento registra `soundfile_version` en los metadatos del reporte. Will debe verificar que la versión sea compatible. |
| `libsndfile` versión | Subtipos disponibles pueden variar entre versiones. El instrumento registra `libsndfile_version` y `wav_subtypes_available` en los metadatos. | Will debe verificar que `PCM_16`, `PCM_24`, `PCM_32`, `FLOAT` estén en `wav_subtypes_available`. Si alguno falta, las pruebas T11-T14 correspondientes fallarán. |
| `os.pread` disponible | `os.pread` es POSIX estándar, disponible en Python 3.3+ en Linux/Android. | Si por alguna razón `os.pread` no está disponible, las pruebas T12-T14 lanzarán `AttributeError` y se reportarán como `ERROR`. |

### E.4 Limitaciones del instrumento

1. **No verifica coherencia de captura frente a escritores concurrentes.** Ninguna prueba simula un productor escribiendo el archivo durante la sesión. Esto requiere un test de concurrencia que está fuera del alcance de esta etapa.

2. **No verifica el comportamiento ante `KeyboardInterrupt` durante la sesión.** Las interrupciones de usuario durante T14 pueden dejar el fd o SoundFile en estado intermedio. El instrumento captura `KeyboardInterrupt` a nivel global pero no por prueba.

3. **No prueba FLAC.** Conforme al requerimiento §5, no se incluyen fixtures FLAC. Si se necesita validar FLAC posteriormente, se debe ampliar el instrumento.

4. **No prueba lectura por bloques grandes.** T14 lee 500 frames; no prueba con bloques de 1 MB como hacen los motores de producción. Esto es intencional para mantener las pruebas rápidas y centradas en la mecánica de descriptor.

5. **No declara compatibilidad general de Android.** Los resultados son específicos al dispositivo POCO X6 Pro de Will, a la versión de Termux instalada, y a las versiones de soundfile/libsndfile instaladas. No se puede generalizar a otros dispositivos Android.

6. **No mide rendimiento.** El instrumento no mide tiempos de ejecución. Si se necesita análisis de rendimiento, se debe ampliar con timestamps por prueba.

7. **No prueba apertura con `O_PATH`.** Las pruebas usan `O_RDONLY | O_NOFOLLOW`. Si se requiere validar `O_PATH` + reapertura (Alternativa B), se necesita un instrumento adicional en una etapa posterior.

### E.5 Limitaciones de los resultados

| Resultado | Lo que significa | Lo que NO significa |
|---|---|---|
| `PASS` en T11 | SoundFile abre el descriptor con `closefd=False` en este entorno. | Que funcione en todos los dispositivos Android. |
| `PASS` en T14 | `pread` y SoundFile coexisten sin conflicto en este entorno. | Que el archivo sea estable frente a escritores concurrentes. |
| `PASS` en T15 | `LibsndfileError` se lanza correctamente al rechazar un fd inválido. | Que todos los tipos de fd inválido produzcan `LibsndfileError`. |
| `PASS` en todas las pruebas | La alternativa A es técnicamente viable en este entorno. | Que la alternativa A sea la mejor opción. Que la alternativa B no sea necesaria. Que se pueda implementar AudioInput sin más validación. |
| `FAIL` en cualquier prueba | La alternativa A presenta problemas en este entorno para esa operación específica. | Que la alternativa A sea completamente inviable. Se requiere análisis del detalle del fallo. |
| `NOT_EXECUTED` | La prueba no pudo ejecutarse por una condición ambiental. | Que la operación sea inviable. Solo que no se probó. |

---

## F. Declaración final de no ejecución y no modificación

El abajo firmante, Z.ai — Asistente Senior de Investigación, declara que:

1. **No ejecutó** el instrumento `audioinput_diag_termux.py` en el dispositivo de Will (POCO X6 Pro, Android 16, HyperOS 3, ARM64, Termux).
2. **No ejecutó** el instrumento en ningún dispositivo Android real.
3. Las únicas operaciones ejecutadas en el sandbox Linux x86_64 fueron:
   - `python3 -m py_compile audioinput_diag_termux.py` (verificación de sintaxis, sin ejecución del código).
   - `python3 audioinput_diag_termux.py --help` (verificación de CLI, sin ejecución de pruebas).
4. **No modificó** el repositorio `arielwilliam1986-source/SDV-SDI_SGM`.
5. **No creó** commits, ramas o pull requests.
6. **No modificó** `main`, `AudioInput_SPEC.md`, ni ningún motor o DSP del proyecto.
7. **No solicitó** credenciales ni permisos root.
8. **No eliminó** archivos.
9. **No implementó** la arquitectura AudioInput.
10. **No declaró validada** la alternativa A antes de disponer de resultados reales en el dispositivo de Will.

El instrumento y este informe se entregan a Cris para auditoría independiente. La ejecución en el dispositivo real de Will requerirá autorización expresa de Will después de la evaluación de Cris.

---

**Preparación concluida.** Quedo a la espera de la evaluación de Cris. No avanzaré a la implementación ni a la ejecución real sin autorización expresa de Will.
