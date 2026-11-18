"""Recetas y oráculo de reserva. No importa módulos de los motores ni usa retardos estimados."""
import io
import tarfile
import lzma
from comun import *
import numpy as np
import soundfile as sf
from scipy.io import wavfile
from scipy.signal import lfilter

SALT = 'SDV-SDI/6C/reserva-sin-reajuste/ruido-coloreado/v1'
# nombre, segundos, dV[L,R], dI[L,R]. G posterior a su fuente => d positivo.
PLAN = [
 ('cero',6.75,(0,0),(0,0)), ('cruzado',7.125,(-733,1559),(317,-563)),
 ('tarde',7.375,(17413,17413),(-927,-927)), ('antifase',8.125,(-2039,-2039),(303,303)),
 ('debil_unilateral',7.25,(917,917),(0,0)), ('periodo719',719*340/SR,(1438,-719),(0,0)),
 ('dc_L',6.875,(0,-837),(0,0)), ('cola',70.25,(-3083,3049),(173,-201)),
 ('fuera_C',8.75,(72011,-72011),(0,0)), ('dos_origenes',7.5,(0,0),(0,0)),
 ('replica_dominante',7.5,(0,0),(0,0)), ('sin_relacion',6.625,(0,0),(0,0)),
 ('corta',3019/SR,(0,0),(0,0))]


def late(v,d):
    y=np.zeros_like(v); l=max(d,0); r=min(len(v),len(v)+d); y[l:r]=v[l-d:r-d]; return y


def packets(rng,n,tail=False):
    y=np.zeros(n,dtype='f4'); lo,hi=(68.3*SR,n-.28*SR) if tail else (.29*n,.71*n)
    for _ in range(11):
        width=min(int(rng.integers(517,1701)),n//12); start=int(rng.uniform(lo,hi))
        z=lfilter([1., .19],[1.,-rng.uniform(.15,.86)],rng.normal(size=width))
        y[start:start+width] += (.12*np.hanning(width)*z/max(abs(z))).astype('f4')
    return y


def oracle(state, reason, nominal, ref, guide, gain, circular, alternatives=None):
    def result(measured,where=None):
        return dict(clase=state or ('ALIGNED' if abs(measured)<=1 else 'WARNING' if abs(measured)<=441 else 'MISALIGNED'),
                    razon=reason,d_inyectado=nominal,lag_marca=measured,ubicaciones=where,alternativas_d=alternatives)
    if state:
        return result(None)
    ref=(ref.astype('f8')*gain).astype('<f4'); x=np.ascontiguousarray(ref).tobytes(); y=guide.astype('<f4').tobytes()
    pos=int(np.argmax(abs(ref)))-37; tag=x[4*pos:4*(pos+89)]
    require(len(tag)==4*89 and x.count(tag)==y.count(tag)==1,'marca reservada no única')
    t,g=x.index(tag),y.index(tag); require(t%4==g%4==0 and (g-t)//4==nominal,'marca reservada no coincide')
    return result((g-t)//4,[t//4,g//4])


def generate():
    exp=custody(); dest=BUILD/'reserva'; dest.mkdir(parents=True,exist_ok=True)
    cases=[]; files={}
    for name,seconds,dv,di in PLAN:
        seed=int(sha((SALT+'/'+name).encode())[:16],16); rng=np.random.Generator(np.random.PCG64(seed)); n=round(SR*seconds)
        v,i=[np.stack([packets(rng,n,name=='cola') for _ in range(2)],axis=1) for _ in range(2)]
        gains={'vocal':[-1.,1.] if name=='cruzado' else [1.,1.], 'instrumental':[1.,1.]}; periodic=name=='periodo719'
        if name=='antifase':
            v[:,1]=-v[:,0]; i[:,1]=-i[:,0]; gains['vocal']=[-1.,-1.]
        if name=='debil_unilateral':gains['vocal']=[2e-7,0.]
        if name=='dc_L':v[:,0]=.0625; i[:,0]=.125
        if periodic:
            v,i=[np.tile(rng.normal(0,.07,(719,2)).astype('f4'),(340,1)) for _ in range(2)]
        replicas=name in ('dos_origenes','replica_dominante'); r=3217
        if replicas:
            i=(i+late(v,r)*(1. if name=='dos_origenes' else 1.8)).astype('f4')
        mix=(v.astype('f8')+i).astype('f4'); arrays=dict(mix=mix,vocal0=v,instrumental0=i); truth={}
        for role,ref,delays in [('vocal',v,dv),('instrumental',i,di)]:
            gs=[];truth[role]=[]
            for ch,(d,gain) in enumerate(zip(delays,gains[role])):
                g=((np.roll(ref[:,ch],d) if periodic else late(ref[:,ch],d)).astype('f8')*gain).astype('f4')
                state=None; reason='marca binaria única, guía y referencia; suma verificada';alts=None
                if periodic:state='AMBIGUOUS';reason='portadora circular de período 719 sin origen'
                if gain==0 or (name=='dc_L' and ch==0) or name=='corta':state='INSUFFICIENT_SIGNAL';reason='sin varianza o menos de 4096 muestras'
                if role=='vocal' and replicas:state='AMBIGUOUS';reason='dos copias temporales de la misma fuente en el Mix';alts=[d,d-r]
                if role=='vocal' and name=='sin_relacion':
                    g=packets(rng,n);state='INSUFFICIENT_SIGNAL';reason='guía nueva no incluida en Mix; no hay reloj impuesto'
                truth[role].append(oracle(state,reason,d,ref[:,ch],g,gain,periodic,alts));gs.append(g)
            arrays[role]=np.stack(gs,axis=1)
        refs={}
        for key,a in arrays.items():
            buf=io.BytesIO();wavfile.write(buf,SR,a);data=buf.getvalue();h=sha(data);p=dest/(h+'.wav')
            if not p.exists():p.write_bytes(data)
            x,s=sf.read(p,dtype='float32',always_2d=True)
            require(file_sha(p)==h and s==SR and x.shape==(n,2) and np.array_equal(x,a) and np.isfinite(x).all(),p)
            refs[key]=h;files[h]=dict(bytes=len(data),frames=n,sr=s,channels=2,subtype=sf.info(p).subtype,
                                        pcm_sha256=sha(x.astype('<f4').tobytes()),column_sha256=[sha(x[:,ch].astype('<f4').tobytes()) for ch in (0,1)])
        require(np.array_equal(arrays['mix'],(arrays['vocal0'].astype('f8')+arrays['instrumental0']).astype('f4')),name)
        cases.append(dict(id='R_'+name,seed=seed,frames=n,delays=dict(vocal=dv,instrumental=di),gains=gains,
                          files=refs,channel_oracle=truth))
    EVID.mkdir(parents=True,exist_ok=True); pack=EVID/'reserva_wav.tar.xz'
    with lzma.open(pack,'wb',preset=2) as z,tarfile.open(fileobj=z,mode='w|',format=tarfile.USTAR_FORMAT) as tar:
        for h in sorted(files):
            p=dest/(h+'.wav'); m=tarfile.TarInfo(p.name);m.size=files[h]['bytes'];m.mode=0o644
            with p.open('rb') as f:tar.addfile(m,f)
    save(EVID/'reserva_manifest.json',dict(salt=SALT,freeze=exp,oracle='referencias anteriores al desplazamiento; sin acceso al detector',
                                           cases=cases,wavs=files,archive=dict(name=pack.name,sha256=file_sha(pack))))
    print('Reserva:',len(cases),'casos,',len(files),'WAV;',pack.stat().st_size,'bytes comprimidos')

if __name__=='__main__':generate()
