"""Descarga o verifica, byte por byte, las cuatro copias del estudio S5."""
import argparse
import base64
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
REPO = 'arielwilliam1986-source/SDV-SDI_SGM'
BASE = 'b64f15ae8b28e46eef3c024dc62c85fe27c69494'
OFFICIAL = 'SDV-SDI_FASE_1B_ENTREGA/hashes/FUENTES_SHA256.txt'
ENGINES = {
    'A': 'MOTOR_SEP_SDV-SDI_v3.py',
    'B': 'MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py',
    'C': 'MOTOR_SEP_SDV-SDI_EVO.py',
    'D': 'sdv_sdi_mqr_engine.py',
}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def verify(download=False):
    if download and git('ls-remote', 'origin', 'refs/heads/main').split()[0].decode() != BASE:
        raise ValueError('main cambió; no se descargarán otros bytes.')
    rows = [r.split() for r in git('show', f'{BASE}:{OFFICIAL}').decode().splitlines() if not r.startswith('#') and r.strip()]
    records = []
    for block, name in ENGINES.items():
        path = 'Proyecto SDV-SDI_SGM/' + name
        original = git('show', f'{BASE}:{path}')
        expected, recorded, matched, _ = next(r for r in rows if r[-1] == name)
        blob = git('rev-parse', f'{BASE}:{path}').decode().strip()
        dest = ROOT / 'sources' / name
        if download:
            response = json.loads(subprocess.check_output([
                'gh', 'api', '--hostname', 'github.com', '--method', 'GET',
                f'repos/{REPO}/contents/{quote(path)}', '-f', f'ref={BASE}',
            ]))
            data = base64.b64decode(response['content'])
            if response['sha'] != blob or data != original or hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f'Descarga no idéntica: {name}')
            dest.parent.mkdir(exist_ok=True)
            if not dest.exists():
                with dest.open('xb') as out:
                    out.write(data)
        data = dest.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if data != original or sha != expected or sha != recorded or matched != 'SI':
            raise ValueError(f'No coincide la fuente {name}')
        records.append(dict(block=block, path=path, copy=str(dest.relative_to(ROOT)), bytes=len(data),
                            git_blob=blob, sha256=sha, phase_1b_expected=expected, match=True))
    result = dict(repo=REPO, ref='main', commit=BASE, official_hash_file=OFFICIAL, sources=records)
    manifest = ROOT / 'source_hashes.json'
    if download:
        manifest.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    elif json.loads(manifest.read_text(encoding='utf-8')) != result:
        raise ValueError('source_hashes.json no corresponde a las copias')
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descargar', action='store_true', help='leer las copias desde la API de GitHub')
    for entry in verify(parser.parse_args().descargar):
        print(entry['sha256'], entry['copy'])
