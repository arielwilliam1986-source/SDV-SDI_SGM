"""Custodia y preflight; no importa motores para validar sus bytes."""
import ast
import hashlib
import inspect
import io
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import numpy as np
import scipy
import soundfile as sf

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parent
# Se puede regenerar en otro directorio, sin sobrescribir la publicación.
OUT = Path(os.environ.get('SDV6B_OUT', HERE)).resolve()
BUILD = OUT / 'build'
EVID = OUT / 'evidence'
BASE = 'b64f15ae8b28e46eef3c024dc62c85fe27c69494'
S5 = 'c1ce9e29e15a9c5eb2789187097f94fc13cefaa0'
PRE = '1f5d7e8f39c54f197b2bbf0a2fa520af4a39ddae'
SR = 44100
ROLES = ('vocal', 'instrumental')
NAMES = {'A':'MOTOR_SEP_SDV-SDI_v3.py', 'B':'MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py',
         'C':'MOTOR_SEP_SDV-SDI_EVO.py', 'D':'sdv_sdi_mqr_engine.py'}
ENTRY = dict(A='audit_alignment', B='analyze_alignment', C='analyze_alignment', D='analyze_alignment')

def git(*args):
    return subprocess.check_output(['git',*args], cwd=REPO)

def blob(commit,path):
    return git('show',f'{commit}:{path}')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False, sort_keys=True).encode()

def digest(value):
    return sha(canonical(value))

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    tmp=path.with_suffix(path.suffix+'.part'); tmp.write_text(data,encoding='utf-8');tmp.replace(path)

def load(path):
    return json.loads(path.read_bytes())

def sources():
    refs=json.loads(blob(S5,'S5_STEREO_VALIDATION/source_hashes.json'))['sources']
    prev=json.loads(blob(PRE,'ETAPA_6_ALINEACION_DIAGNOSTICO/DEFECTOS_REPRODUCIBLES.json'))['fuentes']
    ref1b=blob(BASE,'SDV-SDI_FASE_1B_ENTREGA/hashes/FUENTES_SHA256.txt').decode().splitlines()
    result={}
    for b,name in NAMES.items():
        p='Proyecto SDV-SDI_SGM/'+name
        orig=blob(BASE,p); local=(REPO/p).read_bytes(); h=sha(orig)
        rec=next(x for x in refs if x['block']==b); earlier=next(x for x in prev if x['motor']==b)
        one,=[s.split() for s in ref1b if s.endswith('  '+name)]
        if not (one[:3]==[h,h,'SI'] and h==rec['sha256']==earlier['sha256'] and orig==local==blob(PRE,p)==blob(S5,p)==blob(S5,'S5_STEREO_VALIDATION/'+rec['copy'])):
            raise ValueError('Fuente no idéntica: '+p)
        tree=ast.parse(orig); constants={n.targets[0].id:n.value.value for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and isinstance(n.value,ast.Constant)}
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==ENTRY[b]);caller='main' if b=='A' else 'run_experiment'
        calls=[n.lineno for n in ast.walk(next(k for k in tree.body if isinstance(k,ast.FunctionDef) and k.name==caller)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==ENTRY[b]]
        result[b]=dict(path=p,bytes=len(orig),sha256=h,git_blob=git('rev-parse',BASE+':'+p).decode().strip(),engine_name=constants['ENGINE_NAME'],version=constants['ENGINE_VERSION'],entry=ENTRY[b],arguments=ast.unparse(function.args),lines=[function.lineno,function.end_lineno],caller=caller,caller_lines=calls)
    return dict(base=BASE,s5=S5,diagnostico_previo=PRE,metodo='git show SHA:ruta; comparación binaria con checkout, copia S5, SHA de Fase 1B y E6; ejecución desde esos mismos originales del checkout',motores=result)

def environment():
    import datetime
    return dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),branch=git('branch','--show-current').decode().strip(),head_antes_de_ejecutar=git('rev-parse','HEAD').decode().strip(),python=sys.version,platform=platform.platform(),architecture=platform.machine(),numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__,libsndfile=sf.__libsndfile_version__,cpu_disponibles=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else os.cpu_count(),threads={k:os.environ[k] for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')},sample_rate=SR,canales=2,wav='IEEE_FLOAT little-endian, float32',dependencias='venv aislado, sin cambios en el sistema',semillas=[6001,6011],observacion='CPython; sólo lectura de retornos escalares y ventanas, no se reemplaza ninguna función')

if __name__=='__main__':
    report=sources();save(OUT/'source_hashes.json',report);save(OUT/'environment.json',environment());
    for b,r in report['motores'].items():print(b,r['version'],r['bytes'],r['sha256'],r['entry'],r['arguments'],r['caller_lines'])
