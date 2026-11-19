"""Second read-only oracle: archived bytes and component equations, no generator/detector imports."""
import io
import tarfile
from common import *
import numpy as np
import soundfile as sf


def translated(src,delay,n):
    grid=np.arange(n)-delay;use=(0<=grid)&(grid<len(src));out=np.zeros(n,np.float32);out[use]=src[grid[use]];return out

def audit():
    manifest=load(OUT/'BANCO_RESERVADO_MANIFEST.json');pack=EV/'banco_6d.tar.xz';check(digest(pack)==manifest['archive_sha256'],'archive');seen=set()
    with tarfile.open(pack,'r|xz') as tar:
        for m in tar:
            data=tar.extractfile(m).read();h=sha(data);meta=manifest['wavs'][h];buf=io.BytesIO(data);inf=sf.info(buf);buf.seek(0);pcm,sr=sf.read(buf,always_2d=True,dtype='float32');check(inf.subtype=='FLOAT' and sr==SR and inf.frames==len(pcm)==meta['frames'] and pcm.shape[1]==2,h);check(h not in seen and m.name==h+'.wav' and sha(pcm.astype('<f4').tobytes())==meta['pcm_sha256'] and len(data)==meta['bytes'],h);check(digest(WORK/'wav'/m.name)==h,h);seen.add(h)
    check(seen==set(manifest['wavs']),'inventory');res={};ids={}
    for c in manifest['cases']:
        x={k:sf.read(WORK/'wav'/(h+'.wav'),dtype='float32',always_2d=True)[0] for k,h in c['files'].items()};id=c['id'];ids.setdefault(c['partition'],set()).update(c['files'][k] for k in ('mix',*ROLES));n=len(x['mix']);v=x['V0'];i=x['I0'];r=x['background'].copy();tags=0;counts={};decor=[]
        for j,amp in enumerate(c['replica_amplitudes']):
            if amp:r[:,j]+=np.float32(amp)*translated(v[:,j],c['replica_spacing'],n)
        check(np.array_equal(r,i) and np.array_equal(((v.astype('f8')+i).astype('f4').astype('f8')+x['noise']).astype('f4'),x['mix']),id)
        for role,src in [('vocal',v),('instrumental',i)]:
            for j,ch in enumerate('LR'):
                lab=c['truth'][role][ch];g=x[role][:,j];a=src[:,j];state=lab['state'];delay=c['delay_v' if role=='vocal' else 'delay_i'][j];gain=c['gains_v'][j] if role=='vocal' else 1.;gainref=(a.astype('f8')*gain).astype('f4');pred=translated(gainref,delay,len(g));alts=[delay]
                if id=='circular':pred=a[(np.arange(len(g))-delay)%len(a)];check(np.array_equal(g[:-257],g[257:]),id);alts=lab['alternatives'];check(len(set(alts))>1 and all((z-delay)%257==0 for z in alts),id)
                elif role=='vocal' and c['replica_amplitudes'][j]:alts=[delay,delay-c['replica_spacing']];check(np.linalg.norm(i[:,j]-x['background'][:,j])>0,id)
                elif role=='vocal' and id=='dos_tramos':pred[n//2:]=translated(gainref,-1213,len(g))[n//2:];alts=[delay,-1213]
                elif id=='sin_relacion' and role=='vocal':
                    # No code is present in the component actually used to form the Mix, not a lag argmax.
                    ix=np.flatnonzero(g);a0=int(ix[len(ix)//2]);tag=g[a0:a0+43].tobytes();check(tag not in a.tobytes() and tag not in i[:,j].tobytes() and np.any(g),'negative');pred=g;alts=[];decor.append(ch)
                elif state=='ERROR':check(ch=='L' and id=='invalida_L' and np.flatnonzero(~np.isfinite(g)).tolist()==[251],id);pred[251]=np.nan;alts=[]
                elif np.ptp(a)==0:alts=[];check(state=='INSUFFICIENT_SIGNAL',id)
                check(np.array_equal(g,pred,equal_nan=True) and set(alts)==set(lab['alternatives']),(id,role,ch));check(lab['d']==(alts[0] if len(alts)==1 else None),id)
                if len(alts)==1:check(lab['tags'] and lab['state']==('ALIGNED' if abs(delay)<=1 else 'WARNING' if abs(delay)<=441 else 'MISALIGNED'),id)
                if len(alts)>1:check(state=='AMBIGUOUS',id)
                for hit in lab['tags']:
                    l,h=hit['ref'],hit['guide'];tag=g[h:h+43].tobytes();check(len(tag)==172 and tag==gainref[l:l+43].tobytes() and gainref.tobytes().count(tag)==g.tobytes().count(tag)==1 and h-l==hit['d'],(id,role,ch));tags+=1
                counts[role+'/'+ch]=state
        snr=None
        if np.any(x['noise']):snr=float(20*np.log10(np.linalg.norm(v.astype('f8'))/np.linalg.norm(x['noise'].astype('f8'))));check(abs(snr-c['noise_snr_vs_V_db'])<1e-10,id)
        res[id]=dict(exact_components=True,verified_tag_occurrences=tags,independent_negative_columns=decor,states=counts,snr_vs_V_db=snr)
    historic=set(load(B6/'signals_manifest.json')['wavs'])|set(load(C6/'evidence/reserva_manifest.json')['wavs']);check(not (ids['DEV']&ids['RESERVA'] or historic&ids['RESERVA']),'input leak');return dict(unique_wav=len(seen),n_dev_reserve_common_inputs=0,n_historical_reserve_common_inputs=0,cases=res)
if __name__=='__main__':
    r=audit();save(EV/'oraculo_pcm.json',r);print(r['unique_wav'],'WAV',sum(v['verified_tag_occurrences'] for v in r['cases'].values()),'testigos')
