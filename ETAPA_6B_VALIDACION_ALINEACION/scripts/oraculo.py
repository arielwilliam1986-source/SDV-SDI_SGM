"""Oráculo externo: sólo PCM estéreo de los paquetes, no usa el estimador de ningún motor."""
import tarfile
import tempfile
from pathlib import Path
from scipy.io import wavfile
from base import OUT, SR, ROLES, load, save, sha, np, sf
from ejecutar import cases_with_fault


def positions(column,needle):
    """Primeras dos coincidencias exactas en fronteras de muestra; búsqueda en TODO el canal."""
    b=column.astype('<f4',copy=False).tobytes();word=needle.astype('<f4',copy=False).tobytes();found=[];i=0
    while len(found)<2:
        i=b.find(word,i)
        if i<0:break
        if i%4==0:found.append(i//4)
        i+=1
    return found


def unpack(man,work):
    seen=set();size=0
    for rec in man['archives']:
        p=OUT/rec['path'];assert sha(p.read_bytes())==rec['sha256'] and p.stat().st_size==rec['bytes']
        with tarfile.open(p,'r|xz') as t:
            for m in t:
                h=m.name.removesuffix('.wav');w=man['wavs'][h];assert m.isfile() and len(h)==64 and h not in seen and w['member']==m.name==h+'.wav' and w['archive']==rec['path'];v=t.extractfile(m).read();assert sha(v)==h and len(v)==w['bytes'];p=work/m.name;p.write_bytes(v);seen.add(h);size+=len(v)
                rate,x=wavfile.read(p);info=sf.info(p);assert (rate,x.shape,x.dtype.str,info.subtype)==(SR,(w['frames'],2),'<f4','FLOAT');assert np.isfinite(x).all() and sha(x.tobytes())==w['pcm_sha256'] and [sha(x[:,c].tobytes()) for c in (0,1)]==w['channel_sha256'];assert list(np.max(abs(x),axis=0))==w['peak']
    assert seen==set(man['wavs']);return dict(unique_wavs=len(seen),total_uncompressed_bytes=size,independent_decoder='scipy.io.wavfile.read; FORMAT/subtipo también con SoundFile',channels=2,sr=SR,non_finite=0)


def measure(c,work):
    def read(key):return wavfile.read(work/(c['files'][key]+'.wav'))[1]
    x=read('mix');orig={r:read(r+'0') for r in ROLES};mixerr=float(np.max(abs(x.astype('f8')-(orig['vocal'].astype('f8')+orig['instrumental']).astype('f4'))));assert mixerr<6e-8 if c.get('s5_members') else mixerr==0
    out={}; n=len(x)
    for role in ROLES:
        g=read(role) if c['files'][role] else None;v=orig[role];out[role]=[]
        for ch in (0,1):
            d=c['delays'][role][ch];gain=c['gain'][role][ch]*c['sign'][role][ch];r={'d_inyectado':d,'d_ms':1000*d/SR,'lag_marca':None,'clase':None,'razon':None,'ubicacion_ref':None,'ubicacion_guia':None}
            if g is None:r.update(clase='ERROR',razon='archivo deliberadamente ausente; sin observación de guía')
            else:
                lo=max(0,d);hi=min(n,n+d);expected=(gain*v[lo-d:hi-d,ch].astype('f8')).astype('f4');assert np.array_equal(g[lo:hi,ch],expected),(c['id'],role,ch)
                # El oráculo de un stem proviene del generador y de su contribución a Mix, no del downmix ni de su RMS.
                if np.ptp(x[:,ch])==0 or np.ptp(v[:,ch])==0 or np.ptp(g[:,ch])==0:r.update(clase='INSUFFICIENT_SIGNAL',razon='Mix, contribución o guía constante en esta columna')
                elif c['kind'] in ('harmonics','tone','S2','S7'):
                    assert all(np.array_equal(y[:-100,ch],y[100:,ch]) for y in (x,v,g));r.update(clase='AMBIGUOUS',razon='PCM se repite exactamente cada 100 muestras, sin marca de origen; tiempos separados por un período son indistinguibles',periodo_testigo=100)
                else:
                    start,w=c['tags'][role][ch];word=v[start:start+w,ch];wordg=(gain*word.astype('f8')).astype('f4');pr=positions(v[:,ch],word);pg=positions(g[:,ch],wordg)
                    if pr==[start] and len(pg)==1 and np.ptp(word)>0 and np.ptp(wordg)>0:
                        found=pg[0]-pr[0];assert found==d,(c['id'],role,ch,found,d);r.update(lag_marca=found,ubicacion_ref=pr[0],ubicacion_guia=pg[0],longitud_marca=w,clase='ALIGNED' if found==0 else 'MISALIGNED',razon='marca única localizada en referencia del rol y en guía, con signo/ganancia de construcción; suma de referencias cotejada con Mix')
                    else:r.update(clase='WARNING',razon='marca sin unicidad demostrada; no usar valor nominal como reloj observado',matches=[pr,pg])
            out[role].append(r)
    return dict(max_error_mix_vs_suma_float32=mixerr,channel_oracle=out)


def main():
    man=load(OUT/'signals_manifest.json');cases=cases_with_fault(man)
    with tempfile.TemporaryDirectory(prefix='sdv6b-custodia-') as td:
        work=Path(td);qa=unpack(man,work);result={c['id']:measure(c,work) for c in cases}
    # Equivalencias observacionales que discriminan entre verdad, convenciones de signo y reloj identificable.
    ix={c['id']:c for c in cases};pairs=[]
    for T in (4,30,70):
        for aa,bb,swap in [('C_tono+0','C_tono+1200',False),('C_tono+0','C_tono-1200',False),('C_armonicos+0','C_armonicos+1200',False),('B_distintos','B_swap_distintos',True),('B_solo_L','B_solo_R',True)]:
            l=ix[f'{aa}_{T}s'];r=ix[f'{bb}_{T}s'];
            for k in ('mix',*ROLES):
                lh,rh=l['files'][k],r['files'][k]
                if swap:assert man['wavs'][lh]['channel_sha256']==man['wavs'][rh]['channel_sha256'][::-1]
                else:assert lh==rh
            pairs.append(dict(a=l['id'],b=r['id'],relationship='permuta exacta L/R en los tres WAV' if swap else 'idénticos tres WAV, reloj inyectado distinto'))
    save(OUT/'evidence/oraculo.json',dict(qa=qa,contrastes=pairs,cases=result));print(qa,'; casos:',len(result),flush=True)

if __name__=='__main__':main()
