"""Rutas, sellos y carga de módulos; nunca escribe en los paquetes anteriores."""
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
Q = ROOT/'ETAPA_6B_VALIDACION_ALINEACION'
P = ROOT/'S5_STEREO_VALIDATION'
OUT = Path(os.environ.get('SDV6C_OUT', HERE)).resolve()
BUILD = OUT/'build'
EVID = OUT/'evidence'
REF = '7092c6cee764861d4bd8230eccb700f1d4d0556c'
ROLES = ('vocal','instrumental')
SR = 44100


def require(ok, message):
    if not ok:
        raise ValueError(str(message))


def sha(b):
    return hashlib.sha256(b).hexdigest()


def file_sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def blob(p):
    return subprocess.check_output(['git','show',REF+':'+str(p.relative_to(ROOT))],cwd=ROOT)


def load(p):
    def invalid(v):
        raise ValueError('No finito: '+v)
    return json.loads(Path(p).read_bytes(),parse_constant=invalid)


def canon(x):
    return json.dumps(x,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':')).encode()


def save(p, x):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp = p.with_suffix(p.suffix+'.part')
    tmp.write_text(json.dumps(x,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(p)


def custody():
    sources = load(HERE/'source_hashes.json'); exp = load(HERE/'experimental_hashes.json')['motores']
    require(sources['commit']==REF, 'base 6C')
    refs = {k:blob(ROOT/p) for k,p in sources['referencias'].items()}
    for b,r in sources['fuentes'].items():
        p = ROOT/r['path']; original = blob(p); h = sha(original)
        require(len(original)==r['bytes'] and original==p.read_bytes() and h==r['sha256'],p)
        require(any(line.split()[:3]==[h,h,'SI'] and line.endswith('  '+p.name) for line in refs['fase1b'].decode().splitlines()),'1B '+b)
        for stage,field,key in [('s5','sources','block'),('auditoria','fuentes','bloque'),('e6','fuentes','motor')]:
            v, = [x for x in json.loads(refs[stage])[field] if x[key]==b]
            require(v['sha256']==h,(b,stage))
        require(json.loads(refs['6b'])['motores'][b]['sha256']==h and blob(P/'sources'/p.name)==original,b)
        if b!='A':
            e = exp[b]; copy = HERE/e['path']
            require(e['input_sha256']==h and e['sha256']==file_sha(copy) and copy.stat().st_size==e['bytes'],copy)
    require(set(exp)==set('BCD') and {p.name for p in (HERE/'motores').glob('*.py')}=={Path(v['path']).name for v in exp.values()},'inventario de copias')
    return exp


def module(b, original=False):
    r = custody()[b]
    p = ROOT/load(HERE/'source_hashes.json')['fuentes'][b]['path'] if original else HERE/r['path']
    spec = importlib.util.spec_from_file_location('motor6c_'+('original_' if original else 'experimental_')+b,p)
    mod = importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod


def verified_prior(p):
    require(p.read_bytes()==blob(p),p)
    return p


def wav6b(man):
    """Read a verified cache or extract into 6C build; never repair the 6B cache."""
    path = Q/'build'/'wav'
    if not all((path/(h+'.wav')).is_file() for h in man['wavs']):
        path = BUILD/'wav6b'; path.mkdir(parents=True,exist_ok=True)
        for pack in man['archives']:
            src = Q/pack['path']; require(file_sha(src)==pack['sha256'],src)
            with tarfile.open(src,'r|xz') as tar:
                for item in tar:
                    h = item.name.removesuffix('.wav')
                    require(item.isfile() and h in man['wavs'] and item.name==h+'.wav',item.name)
                    p = path/item.name
                    if not p.exists():
                        tmp = p.with_suffix('.part'); tmp.write_bytes(tar.extractfile(item).read()); tmp.replace(p)
    for h,meta in man['wavs'].items():
        p = path/(h+'.wav'); require(p.stat().st_size==meta['bytes'] and file_sha(p)==h,p)
    return path


def records(b, phase):
    with gzip.open(EVID/(phase+'_'+b+'.jsonl.gz'),'rt',encoding='utf-8') as f:
        for line in f:
            v = json.loads(line); require(sha(canon(v['record']))==v['sha256'],'fila alterada')
            yield v['record']
