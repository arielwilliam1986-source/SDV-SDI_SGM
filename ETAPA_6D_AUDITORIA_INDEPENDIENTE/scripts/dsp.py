"""Fresh paired runs using the exact historical settings, plus signed and crest controls."""
import tempfile
from common import *
from cli import invoke,from_case
from detect import cases
import numpy as np
import soundfile as sf
from scipy.io import wavfile


def config(b):
    if b=='D':return [(n,'shared','native',False) for n in ('S3','S4','Ppos','S7','invL','side_aligned','near_side')]
    return [('S3','per_channel','magnitudes_first',False),('S4','per_channel','magnitudes_first',False),('Ppos','mono','masks_first',False),('Ppos','mono','magnitudes_first',True),('S7','per_channel','magnitudes_first',False),('invL','per_channel','magnitudes_first',False)]+([('Pneg','per_channel','hybrid_asymmetric',False)] if b=='C' else [])

def inputs(id,allc,root):
    if id=='invL':return from_case(allc[id])
    if id in ('side_aligned','near_side'):
        c=allc['lateral'];c=dict(c,files=dict(c['files'],vocal=c['files']['V0'],instrumental=c['files']['I0']));s=from_case(c)
        if id=='near_side':
            pa=s['pairs'][0];paths=[s['mix_original'],pa['vocal_path'],pa['instrumental_path']];new=[]
            for j,p in enumerate(paths):
                rate,x=wavfile.read(p);x[:,1]*=np.float32(.9921875);f=root/f'near{j}.wav';wavfile.write(f,rate,x);new.append(str(f))
            s['mix_original']=new[0];pa['vocal_path']=pa['vocal_guide']=new[1];pa['instrumental_path']=pa['instrumental_guide']=new[2]
        return s
    cat=load(S5/'signals/manifest.json');path=WORK/'s5'/cat['cases'][id]['manifest'];spec=load(path);spec['mix_original']=str((path.parent/spec['mix_original']).resolve())
    for pair in spec['pairs']:
        for r in ROLES:
            for k in (r+'_path',r+'_guide'):pair[k]=str((path.parent/pair[k]).resolve())
    return spec

def pcm_outputs(root):
    z={}
    for role in ('SDV','SDI'):
        p,=list(root.rglob('*'+role+'*.wav'));x,s=sf.read(p,always_2d=True,dtype='float64');z[role]=(x,s);check(np.isfinite(x).all(),p)
    return z

def main():
    allc={c['id']:c for c in cases()}; rows=[]
    for b in 'BCD':
        records=[]
        for name,mask,order,res in config(b):
            id=b+'/'+name+'/'+mask+'/'+order+('/res' if res else '/direct')
            with tempfile.TemporaryDirectory(dir=WORK) as td:
                root=Path(td);spec=inputs(name,allc,root);cfg=['--n-fft','4096','--hop','1024','--chunk-frames','64','--consensus','confidence_weighted_mean','--power','2' if b=='D' else '1.8','--epsilon','1e-9' if b=='D' else '1e-12'];
                if b!='D':cfg+=['--mask-mode',mask,'--consensus-order',order,'--beta','1','--smoothing','none']+(['--use-residuals'] if res else [])
                if name not in ('side_aligned','near_side'):cfg+=['--allow-misaligned']
                # On the two special controls also check 6C without override. Original may need permission.
                versions={};pcms={}
                for v in ('original','6c'):
                    flags=cfg+(['--allow-misaligned'] if v=='original' and name in ('side_aligned','near_side') else [])
                    w=root/v;summary,rec=invoke(b,id,spec,w,orig=v=='original',extra=flags,dsp=True,comp=root);versions[v]=rec
                    if summary['final_report'] and summary['exit']==0:pcms[v]=pcm_outputs(w/'out')
                orig,exp=versions.values();a,e=orig['observations'],exp['observations'];x,s=sf.read(spec['mix_original'],always_2d=True,dtype='float64')
                row=dict(id=id,case=name,engine=b,complete=len(pcms)==2,exits=[v['summary']['exit'] for v in versions.values()],params=cfg,
                         both_reached_dsp=all(v['summary']['reached_dsp'] for v in versions.values()),n=len(x),peak_mix_LR=np.max(abs(x),axis=0).tolist(),rms_mix_LR=np.sqrt(np.mean(x*x,axis=0)).tolist(),rms_mid=float(np.sqrt(np.mean(x.mean(axis=1)**2))),
                         crest_observed=[v['observations']['crest'] for v in versions.values()],validation_calls=[v['observations']['calls'].get('build_validation_status',0) for v in versions.values()])
                if row['complete']:
                    keys=set(a['tensors']);check(keys==set(e['tensors']),id);row.update(n_tensors=len(keys),different_tensors=sorted(k for k in keys if a['tensors'][k]['sha256']!=e['tensors'][k]['sha256'] or a['tensors'][k]['shape']!=e['tensors'][k]['shape']),
                        elementwise=sum('max_abs_diff' in v for v in e['tensors'].values()),max_tensor_delta=max(v.get('max_abs_diff',0.) for v in e['tensors'].values()),both_formula_error=max(max(f[1:]) for z in (a,e) for f in z['formula']),
                        identical_scale=a['factors']==e['factors'],identical_span_sign_residual=a['sign_and_residual']==e['sign_and_residual'],residual_calls=sum(v['residual_error'] is not None for v in e['sign_and_residual']),signs=sorted({z['sign'] for z in e['sign_and_residual']}),
                        shifts=sorted(set(a['observed_shifts']+e['observed_shifts'])),pcm={})
                    for r in ('SDV','SDI'):
                        l,sl=pcms['original'][r];h,sh=pcms['6c'][r];check(sl==sh==s==SR and l.shape==h.shape==x.shape,id)
                        row['pcm'][r]=dict(max_delta_LR=np.max(abs(l-h),axis=0).tolist(),different_samples=int(np.count_nonzero(l!=h)),sr=s,frames=len(l),channels=h.shape[1],seconds=len(l)/s,sha256_decoded=[sha(v.astype('<f8').tobytes()) for v in (l,h)],R_L_rms_ratio=float(np.linalg.norm(h[:,1])/np.linalg.norm(h[:,0])) if np.any(h[:,0]) else None)
                    errs=[x-v['SDV'][0]-v['SDI'][0] for v in pcms.values()];row['reconstruction_max_abs']=[float(np.max(abs(v))) for v in errs];row['reconstruction_delta']=float(np.max(abs(errs[0]-errs[1])))
                else:row['reason']='NO COMPARABLE: ver exits, excepciones y trazas nativas'
                rows.append(row);records.append(dict(id=id,versions=versions));print(id,row['exits'],row['complete'],flush=True)
        packed(EV/f'dsp_{b}.json.gz',records)
    save(EV/'dsp_index.json',rows)
if __name__=='__main__':main()
