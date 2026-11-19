"""Check the complete delivery inventory, excluding scratch and the seal itself. No engine imports."""
import argparse
from common import HERE,check,digest


def entries():
    out=[]
    for p in sorted(HERE.rglob('*')):
        r=p.relative_to(HERE)
        if r.parts[0]=='build' or '__pycache__' in r.parts or str(r)=='SHA256SUMS.txt' or p.is_dir():continue
        check(not p.is_symlink() and not p.name.endswith('.part'),r);out.append(digest(p)+'  '+r.as_posix())
    return '\n'.join(out)+'\n'
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--crear',action='store_true',help='initial seal only; never replace an existing checksum list');a=ap.parse_args();p=HERE/'SHA256SUMS.txt';expected=entries()
    if a.crear:
        with p.open('x',encoding='utf-8') as f:f.write(expected)
    check(p.read_text()==expected,'inventory, order or digest mismatch');print(len(expected.splitlines()),'archivos; SHA256 de SHA256SUMS.txt:',digest(p))
