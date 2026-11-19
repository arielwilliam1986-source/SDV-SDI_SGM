"""Actual processes, sequential; a sparse logical >1 GiB is a dry-run fixture, not a DSP run."""
import argparse
import gc
import struct
import tempfile
import time
import tracemalloc
from common import *
from cli import manifest
from medir import measure
import numpy as np
import soundfile as sf


def fixtures(root,n):
    root.mkdir(parents=True,exist_ok=True);large=n>=2**27;size=n*8;sr=SR
    header=struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',size+36,b'WAVE',b'fmt ',16,3,2,sr,8*sr,8,32,b'data',size)
    files=[root/('mix.wav' if k==0 else ('v' if k%2 else 'i')+str((k+1)//2)+'.wav') for k in range(13)]
    rng=np.random.default_rng(610209+n);spots=[]
    for t in (.24,.48,.79):
        a,b=[(rng.normal(0,.04,(1543,2))*np.hanning(1543)[:,None]).astype('<f4') for _ in range(2)];spots.append((int(n*t),a,b))
    for j,p in enumerate(files):
        with p.open('wb') as w:
            w.write(header);w.truncate(size+44)
            for t,v,i in spots:
                w.seek(44+t*8);x=v+i if j==0 else (v if j%2 else i)*(1.+j/64.);w.write(x.astype('<f4').tobytes())
        check(sf.info(p).frames==n,p)
    return files

def suite(parent_monitor=False):
    plan=[(2*SR,range(1,7)),(14*SR,[1,6]),(40*SR,[1,6]),(2**27+131072,[1,6])];rows=[];raw=[];mem=[]
    for n,counts in plan:
        with tempfile.TemporaryDirectory(dir=WORK) as td:
            root=Path(td);fs=fixtures(root/'inputs',n);meta={str(p):dict(bytes=p.stat().st_size,allocated_bytes=p.stat().st_blocks*512,sha256=digest(p)) for p in fs};check(len(set(v['sha256'] for v in meta.values()))==13,'unique physical containers')
            for b in 'BCD':
                for count in counts:
                    with tempfile.TemporaryDirectory(dir=root) as sub:
                        d=Path(sub);o=d/'native';o.mkdir();f=fs[:2*count+1];spec=manifest(f[0],list(zip(f[1::2],f[2::2])));man=d/'manifest.json';save(man,spec);mode='dry_run' if n>=2**27 else 'full_processing';cmd=[sys.executable,'-Bu',str(source(b)),'--mode',mode,'--manifest',str(man),'--out',str(o)]
                        if parent_monitor:rec=measure(cmd,d/'monitor',o)
                        else:
                            # The wait4 parent must not have imported NumPy or retained the last detector arrays.
                            mon=[sys.executable,'-Bu',str(HERE/'scripts/medir.py'),str(d/'monitor'),str(o),'--',*cmd];proc=subprocess.run(mon);rec=load(d/'monitor/measure.json');check(proc.returncode==rec['exit'],mon)
                        docs={str(p.relative_to(o)):p.read_text() for p in o.rglob('*') if p.is_file() and p.suffix in ('.txt','.json','.log')}
                        row={k:v for k,v in rec.items() if k not in ('argv','samples')};row.update(id=f'{b}_{n}_{count}',engine=b,mode=mode,pairs=count,frames=n,duration_s=n/SR,bytes_each=f[0].stat().st_size,input_bytes=sum(meta[str(p)]['bytes'] for p in f),allocated_inputs=sum(meta[str(p)]['allocated_bytes'] for p in f),final_analyses=sum(k.endswith('analysis.json') for k in docs),wavs=len(list(o.rglob('*.wav'))))
                        rows.append(row);raw.append(dict(summary=row,measurement=rec,manifest=spec,input_files={str(p):meta[str(p)] for p in f},stdout=(d/'monitor/stdout.log').read_text(),stderr=(d/'monitor/stderr.log').read_text(),native_reports=docs));print(row['id'],mode,row['exit'],row['ru_maxrss_KiB'],round(row['elapsed_s'],2),flush=True)
                if n<2**27:
                    mod=engine(b);mi=mod.probe_file(str(fs[0]),'mix');gu=mod.probe_file(str(fs[1]),'vocal_guide');gc.collect();tracemalloc.start();t=time.monotonic();r=mod.analyze_alignment(mi,gu);dt=time.monotonic()-t;ret,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                    mem.append(dict(engine=b,frames=n,scope='one guide call, tracemalloc; not RSS',after_return_bytes=ret,peak_bytes=peak,transient_above_return_bytes=peak-ret,elapsed_s=dt,state=r['classification']))
        prefix='resources_piloto' if parent_monitor else 'resources';packed(EV/(prefix+'_raw.json.gz'),raw);save(EV/(prefix+'_index.json'),dict(cli=rows,traced_detector=mem))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',type=Path,help='only generate synthetic input for external measurement');ap.add_argument('--frames',type=int,default=88200);ap.add_argument('--monitor-en-padre',action='store_true',help='reproduce first benchmark; wait4 may include inherited RSS');args=ap.parse_args()
    if args.prepare:
        check(not args.prepare.exists(),'choose a new fixture directory');f=fixtures(args.prepare.resolve(),args.frames)
        for n in range(1,7):save(args.prepare/f'p{n}.json',manifest(f[0],list(zip(f[1:2*n+1:2],f[2:2*n+1:2]))))
    else:suite(args.monitor_en_padre)
