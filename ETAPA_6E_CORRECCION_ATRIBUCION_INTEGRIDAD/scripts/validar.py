"""Post-freeze reserve, no imports or material from 6D. Writes audit evidence."""
import ast
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import tempfile
import time

for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '1'
import numpy as np
import scipy
import soundfile as sf

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
EV = HERE/'evidence'
BASE = 'ceae641aaa60e4545ac3ebadf393b01bf090b7ca'
FREEZE = 'b50d30e'
SR = 44100
SEED = 609174223
REF = ROOT/'ETAPA_6C_CORRECCION_EXPERIMENTAL/motores'
ORIG = ROOT/'Proyecto SDV-SDI_SGM'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False, ensure_ascii=False)+'\n')


def load_engine(p):
    sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location(p.stem, p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def delay(g, d):
    z = np.zeros_like(g)
    if d > 0:
        z[d:] = g[:-d]
    elif d < 0:
        z[:d] = g[-d:]
    else:
        z[:] = g
    return z


def reserve():
    rng = np.random.default_rng(SEED)
    n = SR
    v, i, j = [rng.integers(-2048, 2048, (n, 2)).astype('float32')/32768 for _ in range(3)]
    side = lambda x: np.column_stack((x[:, 0], -x[:, 0]))
    sine = np.broadcast_to((np.arange(n)%32 == 0)[:, None], v.shape)*np.float32(.125)
    clock = v.copy()
    clock[n//2:] = delay(v, 53)[n//2:]
    right = v+i+.125*delay(v, 123)
    right[:, 0] = (v+i)[:, 0]
    shifted_mix = np.pad(v+i, ((0, 567), (0, 0)))
    shifted_guide = np.pad(v, ((567, 0), (0, 0)))
    return {
        'clean': (v+i,v,i,'UNIQUE',0),
        'signed': (v+i,-v,i,'UNIQUE',0),
        'side': (side(v+i),side(v),side(i),'UNIQUE',0),
        'side_output': (side(v+i),v,side(i),'INSUFFICIENT_SIGNAL',None),
        'shift': (shifted_mix,shifted_guide,np.pad(i,((0,567),(0,0))),'UNIQUE',-567),
        'dual': (v+i+delay(v, 173),v,i,'AMBIGUOUS',None),
        'dominant': (v+i+.25*delay(v, -283),v,i,'AMBIGUOUS',None),
        'piecewise': (clock+i,v,i,'AMBIGUOUS',None),
        'right_rival': (right,v,i,'AMBIGUOUS',None),
        'different_lr': (np.column_stack((v[:,0],delay(v,33)[:,1]))+i,v,i,'AMBIGUOUS',None),
        'periodic': (sine+i,sine,i,'AMBIGUOUS',None),
        'unrelated': (v+i,j,i,'INSUFFICIENT_SIGNAL',None),
        'silent': (v+i,np.zeros_like(v),i,'NON_INFORMATIVE',None),
        'dc': (v+i,np.full_like(v,.125),i,'NON_INFORMATIVE',None),
        'nonfinite': (v+i,np.full_like(v,np.nan),i,'ERROR',None),
    }


def cli(p, paths, work, flags, logs):
    work.mkdir()
    man=work/'manifest.json'; out=work/'out'; out.mkdir()
    m,v,i=map(str,paths)
    dump(man, dict(mix_original=m,pairs=[dict(pair_id='P01', family='AUDIT',variant='V01',configuration='synthetic',source='synthetic',vocal_path=v,vocal_guide=v,instrumental_path=i,instrumental_guide=i)]))
    cmd=[sys.executable,str(p),'--manifest',str(man),'--out',str(out),'--mode','full_processing',*flags]
    start=time.perf_counter()
    proc=subprocess.run(cmd,capture_output=True,text=True)
    reports=list(out.rglob('analysis.json'))
    pcm={}
    for role in ('SDV','SDI'):
        candidates=list(out.rglob(f'*{role}*.wav'))
        if len(candidates)==1:
            x,s=sf.read(candidates[0],dtype='float64',always_2d=True)
            pcm[role]=dict(sha256=sha(x.astype('<f8').tobytes()),shape=list(x.shape),sr=s,finite=bool(np.isfinite(x).all()))
    report=json.loads(reports[0].read_text()) if len(reports)==1 else {}
    logs.append(dict(run=work.name,argv=cmd,manifest=json.loads(man.read_text()),stdout=proc.stdout,stderr=proc.stderr,report=report))
    return dict(exit=proc.returncode,seconds=time.perf_counter()-start,pcm=pcm,wavs=len(list(out.rglob('*.wav'))),report=bool(report))


def main():
    t=time.perf_counter()
    sources={}
    refs={}
    branch=git('branch','--show-current').decode().strip()
    for f in sorted({*ORIG.glob('*.py'),*REF.glob('*.py'),*(HERE/'motores').glob('*.py')}):
        rel=f.relative_to(ROOT).as_posix(); digest=sha(f.read_bytes())
        frozen=f.parent == HERE/'motores'
        assert digest==sha(git('show',f'{FREEZE if frozen else BASE}:{rel}')), rel
        (refs if frozen else sources)[rel]=digest
    rows=[]; clirows=[]; logs=[]; stimuli={}; astrows={}
    with tempfile.TemporaryDirectory(prefix='sdv6e-') as tmp:
        root=Path(tmp); pairs={}
        for case,(m,v,i,state,k) in reserve().items():
            paths=[root/f'{case}-{r}.wav' for r in 'MVI']
            for p,x in zip(paths,(m,v,i)):
                sf.write(p,x,SR,subtype='FLOAT')
            stimuli[case]=dict(expected=state,k=k,wav={p.name:sha(p.read_bytes()) for p in paths})
            pairs[case]=paths
        m,v,i=pairs['clean']
        corrupt=root/'truncated.wav'; corrupt.write_bytes(v.read_bytes()[:-1032]); pairs['truncated']=[m,corrupt,i]
        broken=root/'data_overrun.wav'; b=bytearray(v.read_bytes()); off=b.index(b'data',12); b[off+4:off+8]=(len(b)).to_bytes(4,'little'); broken.write_bytes(b); pairs['data_overrun']=[m,broken,i]
        for f in (corrupt,broken):
            try: decoder=sf.info(f).frames
            except RuntimeError: decoder=None
            stimuli[f.stem]=dict(wav={f.name:sha(f.read_bytes())},decoder_frames=decoder)
        for p in sorted((HERE/'motores').glob('*.py')):
            if p.stem=='atribucion_6e': continue
            name='MQR' if 'mqr' in p.name else 'EVO' if 'EVO' in p.name else 'Hardened'
            engine=load_engine(p)
            def defs(path):
                return {n.name:ast.dump(n) for n in ast.parse(path.read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
            a,b=defs(REF/p.name),defs(p)
            astrows[name]=dict(changed=sorted(k for k in a if a[k]!=b.get(k)),added=sorted(b.keys()-a.keys()),unchanged_count=sum(a[k]==b.get(k) for k in a))
            for case, paths in pairs.items():
                infos=[engine.probe_file(str(f),r) for f,r in zip(paths,('mix','vocal','instrumental'))]
                result=engine.analyze_alignment(*infos[:2]); want=stimuli[case].get('expected','ERROR'); k=stimuli[case].get('k')
                rows.append(dict(engine=name,case=case,expected=want,attribution=result['attribution'],k=result['estimated_offset_samples'],expected_k=k,ok=want==result['attribution'] and k==result['estimated_offset_samples'],details=result,probe_errors=infos[1].errors))
            for case,override in [('clean',False),('signed',False),('side',False),('side_output',True),('dual',False),('dual',True),('unrelated',False),('silent',False),('nonfinite',False),('nonfinite',True),('truncated',False),('truncated',True),('data_overrun',True)]:
                flags=['--allow-misaligned'] if override else []
                result=cli(p,pairs[case],root/f'{name}_{case}_{override}',flags,logs)
                want=0 if override and case in {'dual','side_output'} or case in {'clean','signed','side'} else 1
                clirows.append(dict(engine=name,case=case,override=override,expected_exit=want,ok=result['exit']==want and (result['wavs']==0 if want else result['report'] and len(result['pcm'])==2),**result))
                if case in ('clean','signed','side','side_output'):
                    for label, ref in [('6C',REF/p.name),('original',ORIG/p.name)]:
                        ref_flags=['--allow-misaligned']
                        prior=cli(ref,pairs[case],root/f'{name}_{case}_{label}',ref_flags,logs)
                        clirows[-1][label]=dict(**prior,identical_pcm=prior['pcm']==result['pcm'] if len(prior['pcm'])==len(result['pcm'])==2 and prior['report'] and result['report'] and prior['exit']==result['exit']==0 else None)
    dump(HERE/'MANIFEST_6E.json',dict(base=BASE,branch=branch,freeze=git('rev-parse',FREEZE).decode().strip(),seed=SEED,protected_and_references=sources,experimental=refs,stimuli=stimuli))
    dump(EV/'atribucion.json',rows); dump(EV/'cli_dsp.json',clirows); dump(EV/'auditoria_ast.json',astrows); dump(EV/'ejecuciones.json',logs)
    with (EV/'matriz.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])[:7],extrasaction='ignore',lineterminator='\n');writer.writeheader();writer.writerows(rows)
    dump(EV/'recursos.json',dict(seconds=time.perf_counter()-t,maxrss_self_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,maxrss_children_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,platform=platform.platform(),python=sys.version,numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__,libsndfile=sf.__libsndfile_version__,cpu_visible=os.cpu_count(),threads=1))
    print('Atribución:',sum(x['ok'] for x in rows),'/',len(rows),'CLI:',sum(x['ok'] for x in clirows),'/',len(clirows))


if __name__=='__main__':
    main()
