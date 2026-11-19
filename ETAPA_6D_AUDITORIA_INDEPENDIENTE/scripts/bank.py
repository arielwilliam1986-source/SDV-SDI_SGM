"""Independent stimulus + oracle. This module does not load a detector or read its output."""
import io
import tarfile
import lzma
from common import *
import numpy as np
from scipy.io import wavfile

# name, guide V delays in samples; I stays in the Mix clock except where specified below.
PLAN={'DEV_cero':(0,0),'DEV_no_cero':(-511,-511),'Z':(0,0),'W':(219,219),'M':(-1529,-1529),
      'distintos':(1361,-587),'swap':(-587,1361),'invL':(-827,-827),'soloL':(0,0),'soloR':(0,0),
      'alarma_mudo':(937,0),'debil':(763,763),'ruido8':(-1541,-1541),'ruido_menos6':(367,367),
      'circular':(514,-257),'rep_igual':(0,0),'rep_035':(0,0),'rep_165':(0,0),'rival_R':(0,0),
      'lateral':(-1933,-1933),'dc':(0,0),'sin_relacion':(0,0),'corta':(821,-903),
      'larga':(-825,-825),'interior_vacio':(-18013,18103),'dos_tramos':(953,953),'invalida_L':(0,0)}

def shift(x,d,n):
    y=np.zeros(n,'f4');l=max(d,0);r=min(n,len(x)+d)
    if r>l:y[l:r]=x[l-d:r-d]
    return y

def packets(rng,n,long=False):
    x=np.zeros(n,'f4')
    times=[.75,1.3,2.,n/SR-2.1,n/SR-1.7,n/SR-.9] if long else [.24,.39,.63,.96,1.19,1.48]
    for t in times:
        start=int(t*SR)+int(rng.integers(0,735));length=int(rng.integers(303,1673));a=rng.choice([-1.,1.],length)
        x[start:start+length]+=(rng.uniform(.05,.2)*np.bartlett(length)*np.convolve(a,[.2,.6,.2],'same')).astype('f4')
    return x

def exact_tags(ref,g,gain):
    """Independent byte search in the full FLOAT column. One witness per nonzero run cluster."""
    src=(ref.astype('f8')*gain).astype('<f4');a=src.tobytes();b=np.ascontiguousarray(g,dtype='<f4').tobytes();hits=[]
    nz=np.flatnonzero(src);groups=np.split(nz,np.where(np.diff(nz)>200)[0]+1)
    for grp in groups:
        if len(grp)<100:continue
        n=int(grp[len(grp)//2]);tag=a[4*n:4*(n+43)]
        if len(tag)==172 and a.count(tag)==b.count(tag)==1 and b.index(tag)%4==0:
            at=b.index(tag)//4;hits.append(dict(ref=n,guide=at,d=at-n))
    return hits

def make(name,dv):
    seedname='distintos' if name=='swap' else 'soloL' if name=='soloR' else name
    seed=int(sha(('audit-6d-signedchips-nov/V2:'+seedname).encode())[:16],16);rng=np.random.default_rng(seed)
    long=name in ('interior_vacio','dos_tramos'); n=(36 if long else 2)*SR
    if name=='circular':n=257*360
    v,i=[np.stack([packets(rng,n,long) for _ in 'LR'],axis=1) for _ in 'VI'];di=(0,0)
    if name in ('distintos','swap'):di=(-811,331)
    if name in ('soloL','soloR','alarma_mudo'):v[:,1]=0.
    if name in ('swap','soloR'):v=v[:,::-1].copy();i=i[:,::-1].copy();di=di[::-1]
    if name=='lateral':v[:,1]=-v[:,0];i[:,1]=-i[:,0]
    if name=='dc':v.fill(.0625)
    if name=='circular':v,i=[np.tile(rng.normal(0,.075,(257,2)).astype('f4'),(360,1)) for _ in 'VI']
    gains=(-1.,1.) if name=='invL' else (3e-7,3e-7) if name=='debil' else (1.,1.)
    amps={'rep_igual':(1.,1.),'rep_035':(.35,.35),'rep_165':(1.65,1.65),'rival_R':(0.,.38)}.get(name,(0.,0.));spacing=2849
    background=i.copy()
    for ch,amp in enumerate(amps):i[:,ch]+=shift(v[:,ch],spacing,n)*amp
    base=(v.astype('f8')+i).astype('f4');noise=np.zeros_like(base);snr=None
    if name.startswith('ruido'):
        noise=rng.normal(size=(n,2)); target=8. if name=='ruido8' else -6.
        noise=(noise*(np.linalg.norm(v.astype('f8'))/np.linalg.norm(noise))*10**(-target/20)).astype('f4');snr=float(20*np.log10(np.linalg.norm(v.astype('f8'))/np.linalg.norm(noise.astype('f8'))))
    arr={'mix':(base.astype('f8')+noise).astype('f4'),'V0':v,'I0':i,'background':background,'noise':noise};truth={}
    for role,ref,delays in [('vocal',v,dv),('instrumental',i,di)]:
        truth[role]={};guides=[]
        for ch,d in enumerate(delays):
            gain=gains[ch] if role=='vocal' else 1.; ng=n+(-LSHORT if name=='corta' else 7231 if name=='larga' else 0) if role=='vocal' else n
            g=np.roll(ref[:,ch],d) if name=='circular' else shift(ref[:,ch],d,ng);g=(g.astype('f8')*gain).astype('f4');state=None;why='marca única';alts=[d];tags=[]
            if name=='circular':state='AMBIGUOUS';why='extensión circular, periodo exacto 257';alts=[d-257,d,d+257];check(np.array_equal(g[:-257],g[257:]),name)
            if np.ptp(ref[:,ch])==0:state='INSUFFICIENT_SIGNAL';why='columna constante o ausente';alts=[]
            if role=='vocal' and amps[ch]:state='AMBIGUOUS';why='dos copias en la mezcla';alts=[d,d-spacing]
            if name=='sin_relacion' and role=='vocal':g=packets(rng,n);state='INSUFFICIENT_SIGNAL';why='código no incluido en Mix';alts=[]
            if name=='dos_tramos' and role=='vocal':
                g[n//2:]=shift(ref[:,ch],-1213,n)[n//2:];state='AMBIGUOUS';alts=[d,-1213];why='dos relojes por tramo'
                tags=exact_tags(ref[:,ch],g,gain);check({t['d'] for t in tags}==set(alts),name)
            if name=='invalida_L' and role=='vocal' and ch==0:g[251]=np.nan;state='ERROR';alts=[];why='NaN de control sólo en L'
            if state is None:
                tags=exact_tags(ref[:,ch],g,gain);check({t['d'] for t in tags}=={d},(name,role,ch));state='ALIGNED' if abs(d)<=1 else 'WARNING' if abs(d)<=441 else 'MISALIGNED'
            truth[role]['LR'[ch]]=dict(state=state,d=d if len(alts)==1 else None,alternatives=alts,why=why,tags=tags);guides.append(g)
        arr[role]=np.stack(guides,axis=1)
    return arr,dict(id=name,partition='DEV' if name.startswith('DEV') else 'RESERVA',seed=seed,frames_mix=n,frames_v=len(arr['vocal']),frames_i=n,delay_v=dv,delay_i=di,gains_v=gains,replica_amplitudes=amps,replica_spacing=spacing if any(amps) else None,noise_snr_vs_V_db=snr,truth=truth)

LSHORT=11983

def main():
    check((EV/'preflight.json').exists(),'preflight');dst=WORK/'wav';cases=[];index={};sets={k:set() for k in ('DEV','RESERVA')}
    for name,d in PLAN.items():
        arr,c=make(name,d);c['files']={}
        for key,x in arr.items():
            buf=io.BytesIO();wavfile.write(buf,SR,x);raw=buf.getvalue();h=sha(raw);p=dst/(h+'.wav');p.write_bytes(raw)
            s,y=wavfile.read(p);check(s==SR and y.tobytes()==x.tobytes(),p);index[h]=dict(bytes=len(raw),frames=len(x),pcm_sha256=sha(x.astype('<f4').tobytes()),nonfinite_by_channel=(~np.isfinite(x)).sum(axis=0).tolist());c['files'][key]=h
            if key in ('mix',*ROLES):sets[c['partition']].add(h)
        cases.append(c)
    historical=set(load(B6/'signals_manifest.json')['wavs'])|set(load(C6/'evidence/reserva_manifest.json')['wavs']);check(not (sets['DEV']&sets['RESERVA'] or sets['RESERVA']&historical),'colisión de entradas')
    dest=EV/'banco_6d.tar.xz'
    with lzma.open(dest,'wb',preset=1) as z,tarfile.open(fileobj=z,mode='w|') as tar:
        for h,meta in sorted(index.items()):
            p=dst/(h+'.wav');m=tarfile.TarInfo(p.name);m.size=meta['bytes'];
            with p.open('rb') as f:tar.addfile(m,f)
    save(OUT/'BANCO_RESERVADO_MANIFEST.json',dict(sr=SR,channels=2,encoding='IEEE_FLOAT',generator_sha256=digest(Path(__file__)),archive_sha256=digest(dest),wavs=index,cases=cases));print('banco congelado',len(cases),len(index),digest(OUT/'BANCO_RESERVADO_MANIFEST.json'))

if __name__=='__main__':main()
