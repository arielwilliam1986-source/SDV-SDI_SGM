"""Isolate comparable WHOLE detector calls, including decode. Separate from full CLI benchmark."""
from common import *
import gc
import resource
import tempfile
import time
import tracemalloc


def child(b,orig,mx,v):
    mod=engine(b,orig);mi=mod.probe_file(mx,'mix');vi=mod.probe_file(v,'vocal');gc.collect();before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    tracemalloc.start();t=time.monotonic();r=mod.analyze_alignment(mi,vi);elapsed=time.monotonic()-t;held,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    print(json.dumps(dict(engine=b,original=orig,frames=mi.frames,files_sha256=[digest(mx),digest(v)],bytes_each=Path(mx).stat().st_size,seconds=elapsed,hwm_before_KiB=before,hwm_after_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,peak_traced_bytes=peak,held_traced_bytes=held,transient_bytes=peak-held,raw=r),allow_nan=False))

def main():
    from resources import fixtures
    runs=[]
    for n in (2*SR,14*SR,40*SR):
        with tempfile.TemporaryDirectory(dir=WORK) as tmp:
            fs=fixtures(Path(tmp)/'inputs',n)
            for b in 'BCD':
                for v in ['original','6C']:
                    cmd=[sys.executable,'-Bu',str(Path(__file__).resolve()),b,v,str(fs[0]),str(fs[1])];pr=subprocess.run(cmd,capture_output=True,text=True);check(pr.returncode==0,pr.stderr);r=json.loads(pr.stdout);r.update(argv=cmd,exit=pr.returncode,stderr=pr.stderr);runs.append(r)
        print(n,flush=True)
    packed(EV/'coste_detector.json.gz',runs)
if __name__=='__main__':
    if len(sys.argv)==5:child(sys.argv[1],sys.argv[2]=='original',sys.argv[3],sys.argv[4]);
    else:main()
