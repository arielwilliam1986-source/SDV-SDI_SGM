"""I/O and provenance for independent audit. Never import earlier test harnesses."""
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parents[1]; ROOT=HERE.parent
OUT=Path(os.environ.get('SDV6D_OUT',HERE)).resolve(); WORK=OUT/'build'; EV=OUT/'evidence'
B6=ROOT/'ETAPA_6B_VALIDACION_ALINEACION'; C6=ROOT/'ETAPA_6C_CORRECCION_EXPERIMENTAL'; S5=ROOT/'S5_STEREO_VALIDATION'
RB='7092c6cee764861d4bd8230eccb700f1d4d0556c'; RC='00979914d77870f2151bc9ea8af4bd60e2df524b'
ROLES=('vocal','instrumental'); SR=44100

def check(ok,msg):
    if not ok: raise ValueError(str(msg))

def sha(data): return hashlib.sha256(data).hexdigest()
def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def git(*argv):return subprocess.check_output(['git',*argv],cwd=ROOT)
def blob(ref,path):return git('show',ref+':'+str(path.relative_to(ROOT)))
def load(p):return json.loads(Path(p).read_bytes())
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True); tmp=p.with_suffix(p.suffix+'.part');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(p)
def packed(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(gzip.compress(json.dumps(x,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode(),compresslevel=6,mtime=0))
def unpacked(p):return json.loads(gzip.decompress(p.read_bytes()))

def source(b,orig=False):
    check((EV/'preflight.json').exists(),'primero preflight.py')
    r=load(OUT/('source_hashes.json' if orig else 'experimental_hashes.json'))['engines'][b]; p=ROOT/r['path'];check(digest(p)==r['sha256'],p);return p

def engine(b,orig=False):
    check(b in 'BCD','v3 no se ejecuta');p=source(b,orig);s=importlib.util.spec_from_file_location('audit6d_'+('orig' if orig else 'exp')+b,p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m

WITNESSES=('A_frontera+442_4s','B_solo_L_4s','B_solo_R_4s','C_tonos_marcas_4s','C_archivo_S5_4s','D_archivo_S7_4s','D_DC_4s','D_lateral_exacto_4s','E_invertida_1103_4s','F_interior_-22050_30s','F_interior_+22050_30s','F_tail_+22050_70s','A_d+0_70s')
REPLICAS=('R_dos_origenes','R_replica_dominante')
