"""Diseño fijado antes de abrir resultados. Genera, relee y empaqueta WAV por contenido."""
import argparse
import lzma
import io
import tarfile
from base import BUILD, OUT, EVID, SR, S5, ROLES, blob, load, save, sha, sources, np, sf
from scipy.io import wavfile


def plan():
    cases=[]
    for T in (4,30,70):
        def add(group,key,dl=0,dr=None,**kw):
            dr=dl if dr is None else dr
            c=dict(id=f'{group}_{key}_{T}s',group=group,test=key,T=T,frames=T*SR,seed=6001,kind='marks',region='spread',layout='spectral',delays={'vocal':[dl,dr],'instrumental':[0,0]},sign={'vocal':[1,1],'instrumental':[1,1]},gain={'vocal':[1.,1.],'instrumental':[1.,1.]})
            c.update(kw);cases.append(c);return c
        for v in [0,1,-1,221,-221,441,-441,485,-485,1103,-1103,4410,-4410,22050,-22050]:
            add('A',f'd{v:+d}',v)
        if T==4:
            for v in [2,-2,44,-44,440,-440,442,-442]:add('A',f'frontera{v:+d}',v)
        add('A','copia_exacta',kind='identity')
        for title,d,l in [('sincronos',(0,0),'dual'),('solo_L',(1103,0),'dual'),('solo_R',(0,1103),'dual'),('opuestos',(441,-441),'dual'),('distintos',(-1103,4410),'spectral'),('nivel_1_4',(0,1103),'quarter'),('espectros',(0,1103),'spectral'),('evento_L',(1103,0),'onlyL'),('evento_R',(0,1103),'onlyR')]:
            add('B',title,*d,layout=l)
        add('B','swap_distintos',4410,-1103,layout='swap')
        add('B','I_independiente')['delays']['instrumental']=[-485,485]
        for k in [0,1200,-1200]:add('C',f'tono{k:+d}',k,kind='tone')
        for k in [0,1200]:add('C',f'armonicos{k:+d}',k,kind='harmonics')
        add('C','transitorios',485);add('C','tonos_marcas',1103,kind='combined')
        add('C','pulsos_casi_periodicos',1103,kind='neartrain');add('C','alta_AC',1200,kind='highAC')
        add('C','aperiodico',-1103,kind='noise',seed=6011)
        add('D','silencio',kind='silent');add('D','silencio_parcial',1103,region='middle')
        add('D','guia_debil',1103)['gain']['vocal']=[1e-7,1e-7]
        add('D','guia_muda',1103)['gain']['vocal']=[0.,0.]
        add('D','debil_R',0,1103)['gain']['vocal']=[1.,1e-6]
        add('D','casi_lateral',1103,layout='near_side');add('D','lateral_exacto',1103,layout='side')
        add('D','DC',kind='dc')
        for p,sign in [('normal',[1,1]),('invertida',[-1,-1]),('invL',[-1,1]),('invR',[1,-1])]:
            for d in [0,1103]:add('E',f'{p}_{d}',d,kind='lowtone_marks',layout='dual')['sign']['vocal']=sign
        for region in ['early','interior','tail']+(['post60'] if T==70 else []):
            for d in (0,-22050,22050):add('F',f'{region}_{d:+d}',d,region=region)
        if T==4:
            for group,k in [('C','S2'),('C','S5'),('D','S7')]:add(group,'archivo_'+k,kind=k)
    return cases


def regions(c):
    T=c['T'];name=c['region']
    return {'early':(.55,2.2),'interior':((1.05,2.7) if T==4 else (20.,25.)),
            'tail':{4:(2.35,3.45),30:(26.,29.35),70:(68.,69.3)}[T], 'post60':(62.,66.),
            'middle':(.28*T,.72*T)}.get(name)


def make(c):
    """V0,I0 en el reloj de Mix. d positivo genera la guía tarde; nunca se cambia un WAV de entrada."""
    N=c['frames'];T=c['T'];kind=c['kind'];layout=c['layout'];seed=c['seed'];region=regions(c);rnd=np.random.SeedSequence(seed).spawn(4)
    if kind in ('S2','S5','S7'):
        package=blob(S5,'S5_STEREO_VALIDATION/evidence/inputs.tar.xz'); out={}; original={}
        with tarfile.open(fileobj=io.BytesIO(package),mode='r:xz') as tar:
            for r,key in [('Mix','mix'),('V','vocal'),('I','instrumental')]:
                path=f'inputs/{kind}/{r}.wav';data=tar.extractfile(path).read();original[key]=(path,data);out[key]=sf.read(io.BytesIO(data),always_2d=True,dtype='float32')[0]
        for role in ROLES:out[role+'0']=out[role]
        tags={'vocal':[[int(.6*SR)+x,1800] for x in (137,2342)],'instrumental':[[int(.8*SR)+x,1900] for x in (137,2342)]} if kind=='S5' else {r:[None,None] for r in ROLES}
        return out,tags,original
    out={};tags={};frame=np.arange(N,dtype='int64')
    tone=lambda harm:np.sin((2*np.pi/100)*((frame*harm)%100))
    for ri,role in enumerate(ROLES):
        a=np.zeros((N,2),dtype='float32');tags[role]=[]
        pos=(([.23,.47,.71],[.33,.55,.80])[ri] if region is None else ([.15,.48,.80],[.28,.64,.91])[ri]);start,end=region or (0,T)
        on=[int(np.floor(SR*(start+v*(end-start))+.5)) for v in pos]
        for ch in (0,1):
            f=([410.,670.],[1130.,1410.])[ri][ch];sweep=(8100.,-2200.)[ri];samples=np.zeros(N)
            if kind=='lowtone_marks':f=(95.,173.)[ri];sweep=90.
            widths=([.025,.045,.075],[.075,.045,.025])[ri];amps=([.14,.22,.10],[.12,.12,.12])[ri];rng=np.random.Generator(np.random.PCG64(rnd[2*ri+ch]))
            if kind not in ('silent','dc','tone','harmonics'):
                for j,idx in enumerate(on):
                    w=int(round(SR*widths[j]));t=np.arange(w)/SR
                    carrier=(rng.uniform(-1.,1.,w) if kind=='noise' else np.sin(2*np.pi*(f*t+.5*sweep*t*t)))
                    samples[idx:idx+w]+=amps[j]*np.sin(np.pi*np.arange(w)/w)**2*carrier
                tag=[on[1],int(round(SR*widths[1]))]
            else:tag=None
            if kind in ('tone','harmonics','combined'):samples+=.12*tone((1+ch) if ri==0 else (3-ch))
            if kind=='harmonics':samples+=.045*tone(4+ri+ch)
            if kind=='dc':samples.fill((.0625,.125)[ri])
            if kind in ('neartrain','highAC'):
                # Tren finito: contiene marcas únicas; no se confunde con el tono circular indistinguible.
                lo,hi=int(.55*SR),N-int(.55*SR);u=frame[lo:hi]-lo
                samples[lo:hi]+=(.19 if ri==0 else .06)*tone(1+ri)[lo:hi]*(1 if kind=='highAC' else (.55+.45*np.cos(2*np.pi*(u%1001)/1001)))
            a[:,ch]=samples.astype(np.float32);tags[role].append(tag)
        if layout in ('dual','quarter','side','near_side'):
            a[:,1]=a[:,0].astype('f8')*{'dual':1,'quarter':.25,'side':-1,'near_side':-.999}[layout]; tags[role][1]=tags[role][0]
        if kind=='identity' and ri==1:a.fill(0)
        if layout=='onlyL' and ri==0:a[:,1]=0
        if layout=='onlyR' and ri==0:a[:,0]=0
        if layout=='swap':a=a[:,::-1].copy();tags[role].reverse()
        out[role+'0']=a;g=np.zeros_like(a)
        for ch,d in enumerate(c['delays'][role]):
            # Extensión periódica sólo para portadoras sin ataque; para DC también fuera del tramo.
            if kind in ('tone','harmonics','dc'):v=np.roll(a[:,ch],d)
            else:
                v=np.zeros(N,dtype='f4');l=max(d,0);h=min(N,N+d);v[l:h]=a[l-d:h-d,ch]
            g[:,ch]=v.astype('f8')*(c['sign'][role][ch]*c['gain'][role][ch])
        out[role]=g
    out['mix']=(out['vocal0'].astype('f8')+out['instrumental0']).astype('f4')
    return out,tags,{}


def path_for(h):return BUILD/'wav'/(h+'.wav')

def store(a,c,existing,original=None):
    if original is None:
        handle=io.BytesIO();wavfile.write(handle,SR,a);data=handle.getvalue()
    else:data=original[1]
    h=sha(data);p=path_for(h)
    if h not in existing:
        if not p.exists():p.write_bytes(data)
        if sha(p.read_bytes())!=h:raise ValueError('Colisión de bytes '+h)
        x,sr=sf.read(p,dtype='float32',always_2d=True);info=sf.info(p)
        if sr!=SR or info.subtype!='FLOAT' or x.shape!=(c['frames'],2) or not np.isfinite(x).all() or not np.array_equal(x,a):raise ValueError('WAV no conforme')
        ms=x.astype('f8');mid=ms.mean(axis=1)
        existing[h]=dict(archive=f"evidence/wav_{c['T']}s.tar.xz",member=p.name,bytes=len(data),pcm_sha256=sha(x.astype('<f4',copy=False).tobytes()),frames=len(x),sr=sr,channels=2,subtype=info.subtype,finite=True,peak=np.abs(ms).max(axis=0).tolist(),rms=np.sqrt((ms*ms).mean(axis=0)).tolist(),variance=ms.var(axis=0).tolist(),mid_variance=float(mid.var()),channel_sha256=[sha(x[:,i].astype('<f4',copy=False).tobytes()) for i in (0,1)])
    return h


def pack(index,T):
    path=EVID/f'wav_{T}s.tar.xz'; temp=path.with_suffix('.part')
    with temp.open('wb') as f,lzma.LZMAFile(f,mode='wb',preset=2) as gz,tarfile.open(fileobj=gz,mode='w|',format=tarfile.USTAR_FORMAT) as tar:
        for h,v in sorted(index.items()):
            if v['frames']!=T*SR:continue
            info=tarfile.TarInfo(v['member']);info.size=v['bytes'];info.mode=0o644
            with path_for(h).open('rb') as inp:tar.addfile(info,inp)
    temp.replace(path);return {'path':str(path.relative_to(OUT)),'bytes':path.stat().st_size,'sha256':sha(path.read_bytes())}


def restore(man,T=None):
    (BUILD/'wav').mkdir(parents=True,exist_ok=True)
    for rec in man['archives']:
        if T and rec['path']!=f'evidence/wav_{T}s.tar.xz':continue
        path=OUT/rec['path'];wanted={h for h,v in man['wavs'].items() if v['archive']==rec['path']};seen=set()
        if sha(path.read_bytes())!=rec['sha256']:raise ValueError('SHA de paquete '+str(path))
        with tarfile.open(path,mode='r|xz') as tar:
            for m in tar:
                h=m.name.split('.')[0]
                if h not in wanted or h in seen or not m.isfile() or m.name!=h+'.wav':raise ValueError('Miembro no autorizado')
                data=tar.extractfile(m).read();p=path_for(h)
                if sha(data)!=h:raise ValueError('SHA de miembro incorrecto')
                if not p.exists() or sha(p.read_bytes())!=h:p.write_bytes(data)
                seen.add(h)
        if seen!=wanted:raise ValueError('Archivo incompleto')


def main():
    sources();ap=argparse.ArgumentParser();ap.add_argument('--restaurar',action='store_true');args=ap.parse_args()
    if args.restaurar:restore(load(OUT/'signals_manifest.json'));return
    (BUILD/'wav').mkdir(parents=True,exist_ok=True);EVID.mkdir(parents=True,exist_ok=True)
    cases=plan();files={};archives=[];assert len(set(c['id'] for c in cases))==len(cases)
    for T in (4,30,70):
        for c in (x for x in cases if x['T']==T):
            arrays,tags,orig=make(c);c['files']={key:store(a,c,files,orig.get(key.rstrip('0'))) for key,a in arrays.items()};c['tags']=tags
            if orig:c['s5_members']={k:p for k,(p,_) in orig.items()}
            c['delays_ms']={r:[1000*d/SR for d in ds] for r,ds in c['delays'].items()}
            del arrays
        archives.append(pack(files,T));print(T,'s; acumulados',len(files),'WAV distintos;',archives[-1],flush=True)
    save(OUT/'signals_manifest.json',dict(schema='6B.1',sr=SR,channels=2,format='WAV FLOAT32LE; sin normalización ni ajuste. claves files = SHA-256 del WAV completo; 0 = referencia del rol en tiempo de Mix',truth='d>0 = guía tardía; ground truth por canal, nominal si no observable',cases=cases,wavs=files,archives=archives));print(len(cases),'casos')

if __name__=='__main__':main()
