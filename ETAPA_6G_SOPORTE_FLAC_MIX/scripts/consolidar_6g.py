"""Consolida el expediente 6G: diffs, manifiesto y SHA256SUMS."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6g import EV, HERE, MOTORES, ROOT, SIX, dump, entorno, sha_file

BASE_6F = '663fb5f8b4d53c8445d482ecec4df6a0208c59f0'


def git(*args):
    return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def diffs():
    partes = []
    for motor, nombre in MOTORES.items():
        a = SIX / nombre
        b = HERE / 'motores' / nombre
        d = subprocess.run(['diff', '-u', str(a), str(b)], capture_output=True, text=True).stdout
        partes.append(f'### diff {motor} (6F -> 6G)\n\n```diff\n{d}```\n')
        n_add = sum(1 for linea in d.splitlines() if linea.startswith('+') and not linea.startswith('+++'))
        n_del = sum(1 for linea in d.splitlines() if linea.startswith('-') and not linea.startswith('---'))
        print(f'{motor}: +{n_add} -{n_del} líneas')
    a = SIX / 'atribucion_6f.py'
    b = HERE / 'motores' / 'atribucion_6f.py'
    d = subprocess.run(['diff', '-u', str(a), str(b)], capture_output=True, text=True).stdout
    partes.append(f'### diff atribucion_6f.py (6F -> 6G)\n\n```diff\n{d}```\n')
    print('atribucion: +%d -%d líneas' % (
        sum(1 for x in d.splitlines() if x.startswith('+') and not x.startswith('+++')),
        sum(1 for x in d.splitlines() if x.startswith('-') and not x.startswith('---'))))
    (EV / 'diffs_6g.md').write_text(
        '# Diffs 6G frente a las fuentes 6F\n\n'
        'Sólo validación, lectura y trazabilidad. `wav_integridad_6f.py` no se modifica.\n\n'
        + '\n'.join(partes), encoding='utf-8')


def resumen_resultados():
    out = {}
    for nombre in ('contenedores_6g.json', 'motores_6g.json', 'no_regresion_6g.json',
                   'toctou_6g.json'):
        p = EV / nombre
        if p.exists():
            data = json.loads(p.read_text())
            out[nombre] = dict(seconds=data.get('seconds'),
                               maxrss_kib=data.get('maxrss_kib'),
                               resumen=data.get('resumen'))
    return out


def main():
    diffs()
    motores = {k: dict(file=v, sha256=sha_file(HERE / 'motores' / v),
                       sha256_fuente_6f=sha_file(SIX / v),
                       bytes=(HERE / 'motores' / v).stat().st_size)
               for k, v in MOTORES.items()}
    auxiliares = {p.name: dict(sha256=sha_file(p), bytes=p.stat().st_size)
                  for p in sorted((HERE / 'motores').glob('*.py'))
                  if p.name not in set(MOTORES.values())}
    scripts = {p.name: sha_file(p) for p in sorted((HERE / 'scripts').glob('*.py'))}
    fixtures = {p.name: dict(sha256=sha_file(p), bytes=p.stat().st_size)
                for p in sorted((HERE / 'fixtures').iterdir()) if p.is_file()}
    manifiesto = dict(
        stage='6G', objetivo='Mix original WAV y FLAC sin conversión ni cambios DSP',
        repositorio='arielwilliam1986-source/SDV-SDI_SGM',
        rama=git('branch', '--show-current'),
        head=git('rev-parse', 'HEAD'),
        commit_base_6f=BASE_6F,
        commit_base_es_ancestro=subprocess.run(
            ['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', BASE_6F, 'HEAD']).returncode == 0,
        motores=motores, auxiliares=auxiliares, scripts=scripts, fixtures=fixtures,
        entorno=entorno(),
        resultados=resumen_resultados(),
        limites=dict(
            notas='6G sólo valida contenedores, lee y traza; el DSP es el de 6F',
            mqr='las máscaras de MQR se derivan por downmix mono de las guías; '
                'no equivale al modo L/R independiente de Hardened/EVO',
            no_probado='canciones reales, Termux ARM64, archivos > 2 GB, '
                       'modos no listados, FLAC con tasas distintas de 44100'),
    )
    dump(HERE / 'MANIFEST_6G.json', manifiesto)

    lineas = []
    for p in sorted(HERE.rglob('*')):
        if p.is_dir() or p.name == 'SHA256SUMS.txt':
            continue
        lineas.append(f'{sha_file(p)}  ./{p.relative_to(HERE).as_posix()}')
    (HERE / 'SHA256SUMS.txt').write_text('\n'.join(lineas) + '\n', encoding='utf-8')
    print('archivos con hash:', len(lineas))


if __name__ == '__main__':
    main()
