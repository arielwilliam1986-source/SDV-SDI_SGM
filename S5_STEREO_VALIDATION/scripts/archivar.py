"""Empaqueta sin pérdidas los WAV, máscaras aplicadas, bitácoras e informes nativos (también el aborto)."""
from io import BytesIO
import tarfile

from medidas import ROOT, WORK, dump, sha


def main():
    dest = ROOT/'evidence'
    dest.mkdir(exist_ok=True)
    packs, lines = [], []
    for group in ['inputs','runs/A','runs/B','runs/C','runs/D']:
        folder = WORK/group
        paths = sorted(p for p in folder.rglob('*') if p.is_file())
        if not paths:
            raise ValueError(f'No hay evidencia para {group}')
        pack = dest/(group.replace('runs/','S5-')+'.tar.xz')
        raw_size = 0
        with tarfile.open(pack, 'w:xz', preset=4) as out:
            for p in paths:
                data = p.read_bytes()
                member = p.relative_to(WORK).as_posix()
                item = tarfile.TarInfo(member)
                item.size = len(data)
                out.addfile(item, BytesIO(data))
                lines.append(f'{sha(data)}  {member}\n')
                raw_size += len(data)
        packs.append(dict(path=pack.relative_to(ROOT).as_posix(), files=len(paths), raw_bytes=raw_size,
                          packed_bytes=pack.stat().st_size, sha256=sha(pack.read_bytes())))
    hashes = ROOT/'hashes'
    hashes.mkdir(exist_ok=True)
    (hashes/'MIEMBROS_SHA256.txt').write_text(''.join(lines),encoding='utf-8')
    dump(dest/'index.json', dict(format='tar.xz (LZMA2) sin pérdidas; rutas relativas a build/', archives=packs))
    total = sum(p['packed_bytes'] for p in packs)
    print(len(lines),'archivos;',sum(p['raw_bytes'] for p in packs),'bytes originales;',total,'bytes en tar.xz')
    if total >= 120_000_000 or any(p['packed_bytes']>=95_000_000 for p in packs):
        raise SystemExit('NO PUBLICAR binarios: supera el presupuesto. Solicitar almacenamiento alternativo sin pérdida.')


if __name__ == '__main__':
    main()
