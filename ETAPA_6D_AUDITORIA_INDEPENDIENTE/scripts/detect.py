"""Independent invocations of the complete native detector; observational curves for priority A."""
import contextlib
import io
import traceback
import warnings
from common import *
import numpy as np
from scipy.signal import fftconvolve


def cases():
    new=load(OUT/'BANCO_RESERVADO_MANIFEST.json')['cases'];old=[];oracle=load(B6/'evidence/oraculo.json')['cases']
    for path,ids,group in ((C6/'evidence/reserva_manifest.json',REPLICAS,'A_6C'),(B6/'signals_manifest.json',WITNESSES,'6B')):
        for c in load(path)['cases']:
            if c['id'] not in ids:continue
            label=c.get('channel_oracle') or oracle[c['id']]['channel_oracle'];t={}
            for role in ROLES:
                t[role]={}
                for ch,u in zip('LR',label[role]):
                    d=u['lag_marca'];s=u['clase'] if d is None else ('ALIGNED' if abs(d)<=1 else 'WARNING' if abs(d)<=441 else 'MISALIGNED');t[role][ch]=dict(d=d,state=s,alternatives=u.get('alternativas_d') or ([] if d is None else [d]))
            old.append(dict(id=c['id'],partition=group,files=c['files'],truth=t))
    return old+new


def independently(a,b,lo,count,nmin):
    a=np.ascontiguousarray(a,dtype='f8');b=np.ascontiguousarray(b,dtype='f8');q=np.arange(lo,lo+count);l=np.maximum(0,q);r=np.minimum(len(a),len(b)+q);n=r-l
    cross=fftconvolve(a,b[::-1],'full')[q+len(b)-1]
    def diff(x,l,r):
        s=np.insert(np.cumsum(x),0,0.);return s[r]-s[l]
    sa=diff(a,l,r);sb=diff(b,l-q,r-q);va=diff(a*a,l,r)-sa**2/n;vb=diff(b*b,l-q,r-q)-sb**2/n
    ea=a.var()*len(a);eb=b.var()*len(b);valid=(n>=nmin)&(va>np.maximum(1e-20*n,ea*1e-12))&(vb>np.maximum(1e-20*n,eb*1e-12));num=cross-sa*sb/n;rho=np.zeros(count);strength=rho.copy();rho[valid]=num[valid]/np.sqrt(va[valid]*vb[valid]);strength[valid]=abs(num[valid])/np.sqrt(ea*eb)
    return valid,rho,strength


class Curves:
    def __init__(self,m,b,id,role):self.m=m;self.b=b;self.id=id;self.role=role;self.log=[];self.err=[]
    def __call__(self,f,event,arg):
        if event!='return' or arg is None or f.f_code is not self.m._lag_curve.__code__:return
        try:
            loc=f.f_locals; win=f.f_back; entry=win.f_back
            while entry is not None and entry.f_code is not self.m.analyze_alignment.__code__:entry=entry.f_back
            ch=entry.f_locals['name']; band='wave' if loc['x'] is win.f_locals['a'] else 'env'; key=self.id+'_'+self.role+'_'+ch+'_'+band
            lo,ok,rho,score=arg; hi=lo+len(ok)-1
            rec=dict(engine=self.b,case=self.id,role=self.role,ch=ch,band=band,lo=lo,hi=hi,nvalid=int(ok.sum()),nmin=loc['min_n'],valid_sha=sha(ok.tobytes()),rho_sha=sha(rho.tobytes()),strength_sha=sha(score.tobytes()))
            # Share the larger B file only after proving native C/D arrays equal the indexed slice.
            dest=EV/'curvas';dest.mkdir(exist_ok=True);p=dest/(key+'.npz');same=False
            if self.b!='B' and p.exists():
                with np.load(p,allow_pickle=False) as ref:
                    left=lo-int(ref['lo']);sl=slice(left,left+len(ok));same=left>=0 and all(np.array_equal(ref[k][sl],v) for k,v in [('valid',ok),('rho',rho),('strength',score)])
            if not same:
                if self.b!='B':p=dest/(key+'_'+self.b+'.npz')
                np.savez_compressed(p,lo=np.int64(lo),valid=ok,rho=rho,strength=score)
            rec.update(file=str(p.relative_to(OUT)),physical_bins=len(ok),all_local_maxima=int(np.sum(ok&(score>0)&np.r_[True,(~ok[:-1])|(score[1:]>=score[:-1])]&np.r_[(~ok[1:])|(score[:-1]>=score[1:]),True])))
            valid,r,s=independently(loc['x'],loc['y'],lo,len(ok),loc['min_n']);sel=ok&valid;rec.update(independent_valid_disagreements=int(np.sum(ok!=valid)),max_abs_rho_error=float(max(abs(r[sel]-rho[sel]),default=0)),max_abs_strength_error=float(max(abs(s[sel]-score[sel]),default=0)))
            self.log.append(rec)
        except Exception:self.err.append(traceback.format_exc())


def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,(float,np.floating)) and not np.isfinite(x):return {'nonfinite_native':str(x)}
    return x

def run(b,orig,c):
    m=engine(b,orig);ps={k:str(WORK/'wav'/(c['files'][k]+'.wav')) for k in ('mix',*ROLES)};raw={};curves=[];errs=[];stdout=io.StringIO();stderr=io.StringIO()
    with warnings.catch_warnings(record=True) as ws,contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
        warnings.simplefilter('always');mx=m.validate_mix(m.probe_file(ps['mix'],'mix'));pre={'mix':dict(valid=mx.valid,errors=mx.errors,warnings=mx.warnings)}
        for role in ROLES:
            inf=m.validate_guide(m.probe_file(ps[role],role));pre[role]=dict(valid=inf.valid,errors=inf.errors,warnings=inf.warnings)
            obs=Curves(m,b,c['id'],role);prev=sys.getprofile()
            try:
                if not orig and c['id'] in REPLICAS:sys.setprofile(obs)
                raw[role]=m.analyze_alignment(mx,inf)
            except Exception:raw[role]=None;errs.append(traceback.format_exc())
            finally:sys.setprofile(prev)
            curves.extend(obs.log);errs.extend(obs.err)
        msgs=[{'type':w.category.__name__,'message':str(w.message),'line':w.lineno,'file':w.filename} for w in ws]
    return clean(dict(engine=b,version='original' if orig else 'experimental',sha256=digest(source(b,orig)),partition=c['partition'],id=c['id'],files={k:c['files'][k] for k in ps},preflight=pre,raw=raw,curves=curves,exceptions=errs,python_warnings=msgs,stdout=stdout.getvalue(),stderr=stderr.getvalue()))

def main():
    plan=cases()
    for b in 'BCD':
        for orig in (False,True):
            rows=[run(b,orig,c) for c in plan];f=EV/('det_'+b+('_original' if orig else '_6C')+'.json.gz');packed(f,rows);print(f.name,len(rows),sum(len(r['exceptions']) for r in rows),flush=True)

if __name__=='__main__':main()
