"""Controls distinct from the sealed holdout; never edit a motor or its input archive."""
import copy
import tempfile
from types import SimpleNamespace
from common import *
from cli import invoke,from_case,manifest
from detect import cases
import numpy as np
from scipy.io import wavfile


def aggregate(c):
    m=engine('D');s=from_case(c);pa=s['pairs'][0];mx=m.validate_mix(m.probe_file(s['mix_original'],'mix'));info={r:m.validate_guide(m.probe_file(pa[r+'_guide'],r)) for r in ROLES};p=SimpleNamespace(pair_id='P01',**info)
    baseline=[dict(m.analyze_alignment(mx,info[r]),role=r,pair_id=p.pair_id) for r in ROLES];res={}
    for name in ('control','reported_error','missing_role','missing_R','inconsistent_R','post_incomplete','post_fail','unknown_state','permission_does_not_clear_MIS'):
        rec=copy.deepcopy(baseline);mode=m.MODE_ANALYSIS_ONLY;ctx=dict(mix_info=mx,pairs=[p],alignment=rec,warnings=[])
        if name=='reported_error':rec[0]['channels']['R']['classification']='ERROR'
        if name=='missing_role':rec.pop()
        if name=='missing_R':rec[0]['channels'].pop('R')
        if name=='inconsistent_R':rec[0]['channels']['R'].update(estimated_offset_samples=-1,guide_delay_samples=1)
        if name.startswith('post_'):mode=m.MODE_FULL_PROCESSING;ctx['post_wav_validation']={'status':'ok' if name=='post_incomplete' else 'length_mismatch'}
        if name=='unknown_state':rec[0]['classification']='NOT_A_STATE'
        if name.startswith('permission_'):rec[0]['classification']='MISALIGNED';ctx.update(misalignment_user_authorized=True,alignment_permission='test_only')
        res[name]=dict(scope='standalone aggregator with explicitly altered COPY of record; not a CLI run',result=m.build_validation_status(ctx,SimpleNamespace(mode=mode)))
    return res

def main():
    c={v['id']:v for v in cases()};rows=[];obs=[];invariant={};plain=[]
    for b in 'BCD':
        m=engine(b); z=from_case(c['Z']);p=z['pairs'][0];mx=m.probe_file(z['mix_original'],'mix');mi=m.probe_file(p['vocal_path'],'vocal');base=m.analyze_alignment(mx,mi)
        with tempfile.TemporaryDirectory(dir=WORK) as td:
            root=Path(td);rate,x=wavfile.read(p['vocal_path']);y=x.copy();y[::2,1]*=-1;y[222,1]=np.nan;f=root/'changed_R.wav';wavfile.write(f,rate,y);r=m.analyze_alignment(mx,m.probe_file(str(f),'vocal'));invariant[b]=dict(left_identical=base['channels']['L']==r['channels']['L'],before=base,after=r)
            trunc=root/'cut.wav';trunc.write_bytes(Path(p['vocal_path']).read_bytes()[:-8192*8]);s=manifest(z['mix_original'],[(trunc,p['instrumental_path'])]);
            for j,flags in enumerate(([],['--allow-misaligned'])):
                rr,raw=invoke(b,'original_truncated/'+str(j),s,root/f'orig{j}',orig=True,extra=flags);rows.append(rr);obs.append(raw)
            for name in ('Z','rep_035','R_replica_dominante'):
                s=from_case(c[name]);path=root/(name+'.json');save(path,s);out=root/('plain'+name);out.mkdir();cmd=[sys.executable,'-Bu',str(source(b)),'--manifest',str(path),'--mode','full_processing','--out',str(out)];pr=subprocess.run(cmd,capture_output=True,text=True)
                docs={str(f.relative_to(out)):f.read_text() for f in out.rglob('*') if f.suffix in ('.txt','.log','.json')};plain.append(dict(engine=b,case=name,argv=cmd,exit=pr.returncode,stdout=pr.stdout,stderr=pr.stderr,manifest=s,native_reports=docs))
    with tempfile.TemporaryDirectory(dir=WORK) as td:
        root=Path(td);z=c['lateral']['files'];rate,vs=wavfile.read(WORK/'wav'/(z['V0']+'.wav'));_,igs=wavfile.read(WORK/'wav'/(z['I0']+'.wav'));_,side=wavfile.read(WORK/'wav'/(z['mix']+'.wav'))
        for case in ('nonzero_side_output','absent_v_healthy_mix'):
            mx,v,i=(side,np.repeat(vs[:,:1],2,axis=1),np.repeat(igs[:,:1],2,axis=1)) if case.startswith('nonzero') else (np.repeat(igs[:,:1],2,axis=1),np.zeros_like(vs),np.repeat(igs[:,:1],2,axis=1));files=[]
            for nm,x in zip(('mix','v','i'),(mx,v,i)):
                f=root/(case+nm+'.wav');wavfile.write(f,rate,x);files.append(f)
            s=manifest(files[0],[(files[1],files[2])]);
            for orig in (True,False):
                rr,raw=invoke('D',case,s,root/(case+str(orig)),orig=orig,extra=['--allow-misaligned'] if orig or case.startswith('absent') else []);rows.append(rr);obs.append(raw)
    ag=aggregate(c['Z'])
    save(EV/'extra_index.json',dict(cli=rows,metamorphic_L={b:v['left_identical'] for b,v in invariant.items()},plain=[dict(engine=r['engine'],case=r['case'],exit=r['exit']) for r in plain],aggregator={k:v['result']['overall'] for k,v in ag.items()}))
    packed(EV/'extra_raw.json.gz',dict(cli=obs,plain=plain,metamorphic=invariant,aggregator=ag));print('Additional CLI',len(rows),'unprofiled',len(plain))
if __name__=='__main__':main()
