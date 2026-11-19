"""Check the two immutable commits and every archived WAV before importing engines."""
import io
import platform
import tarfile
from common import *
import numpy as np
import scipy
import soundfile as sf


def verify_refs():
    check(git('rev-parse',RC+'^').decode().strip()==RB,'parent of 6C')
    a=json.loads(blob(RB,B6/'source_hashes.json'))['motores']; out={};exp={}
    c=json.loads(blob(RC,C6/'experimental_hashes.json'))['motores']
    for b,r in a.items():
        p=ROOT/r['path'];raw=blob(RB,p);h=sha(raw)
        check(raw==blob(RC,p)==p.read_bytes() and h==r['sha256']==load(C6/'source_hashes.json')['fuentes'][b]['sha256'],p)
        out[b]=dict(path=r['path'],sha256=h,bytes=len(raw),blob=r['git_blob'],role='reference_only' if b=='A' else 'original_comparator')
        if b!='A':
            x=c[b];path=C6/x['path'];z=blob(RC,path);check(z==path.read_bytes() and sha(z)==x['sha256'] and x['input_sha256']==h,path)
            exp[b]=dict(path=str(path.relative_to(ROOT)),sha256=sha(z),bytes=len(z),blob=git('rev-parse',RC+':'+str(path.relative_to(ROOT))).decode().strip(),input_sha256=h)
    lists={}
    for p,rel,ref in ((B6,'SHA256SUMS.txt',RB),(C6,'SHA256SUMS.txt',RC),(S5,'hashes/SHA256SUMS.txt',RB)):
        f=p/rel;check(f.read_bytes()==blob(ref,f),f); ls=f.read_text().splitlines()
        for row in ls:
            h,name=row.split('  ',1);check(digest(p/name)==h,p/name)
        lists[p.name]=dict(n=len(ls),sha256=digest(f))
    save(OUT/'source_hashes.json',dict(commit_6B=RB,also_at_6C=RC,engines=out));save(OUT/'experimental_hashes.json',dict(commit_6C=RC,engines=exp));return lists


def bank(root,man,packs,wanted,channelkey):
    seen={};dst=WORK/'wav';dst.mkdir(parents=True,exist_ok=True)
    for path,h in packs:
        check(digest(path)==h,path)
        with tarfile.open(path,'r|xz') as tar:
            for m in tar:
                buf=tar.extractfile(m).read();d=sha(buf);meta=man['wavs'][d];check(m.isfile() and m.name==d+'.wav' and d not in seen and len(buf)==meta['bytes'],m.name)
                x,sr=sf.read(io.BytesIO(buf),always_2d=True,dtype='float32');pcm=sha(x.astype('<f4').tobytes());chs=[sha(v.astype('<f4').tobytes()) for v in x.T]
                check(pcm==meta['pcm_sha256'] and chs==meta[channelkey] and sr==SR and x.shape==(meta['frames'],2) and np.isfinite(x).all(),d)
                seen[d]=len(buf)
                if d in wanted:(dst/m.name).write_bytes(buf)
    check(set(seen)==set(man['wavs']) and wanted<=set(seen),root);return dict(unique=len(seen),bytes=sum(seen.values()),all_wav_pcm_L_R_verified=True,selected=len(wanted))

def selected(man,ids):
    cases={r['id']:r for r in man['cases']};return {h for k in ids for h in cases[k]['files'].values()}

def main():
    lists=verify_refs();b=load(B6/'signals_manifest.json');c=load(C6/'evidence/reserva_manifest.json');rb=bank(B6,b,[(B6/a['path'],a['sha256']) for a in b['archives']],selected(b,WITNESSES),'channel_sha256');rc=bank(C6,c,[(C6/'evidence'/c['archive']['name'],c['archive']['sha256'])],selected(c,REPLICAS),'column_sha256')
    # Safe extraction of named S5 inputs only, under the audit's scratch directory.
    with tarfile.open(S5/'evidence/inputs.tar.xz','r|xz') as tar:
        for m in tar:
            path=Path(m.name);check(m.isfile() and path.parts[0]=='inputs' and '..' not in path.parts,path);dest=WORK/'s5'/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(tar.extractfile(m).read())
    for name,r in load(S5/'signals/manifest.json')['audio'].items():check(digest(WORK/'s5/inputs'/name)==r['sha256'],name)
    save(OUT/'environment.json',dict(commit_6C=RC,commit_6B=RB,branch=git('branch','--show-current').decode().strip(),python=sys.version,numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__,libsndfile=sf.__libsndfile_version__,platform=platform.platform(),machine=platform.machine(),cpu_affinity=len(os.sched_getaffinity(0)),threads={k:os.environ[k] for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')},meminfo=Path('/proc/meminfo').read_text().splitlines()[:1]))
    save(EV/'preflight.json',dict(reference_6B=RB,reference_6C=RC,lists=lists,bank_6B=rb,bank_6C=rc,s5_inputs='verified',engines_imported=False)); print(rb,rc)

if __name__=='__main__':main()
