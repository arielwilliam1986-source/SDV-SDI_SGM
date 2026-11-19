"""Check cross-stage evidence, recorded returns, assertions about progress, isolation and provenance.
A passed audit *check* includes reproducing the failures; it is not engine acceptance.
"""
import ast
import csv
from collections import Counter
from common import *
from curvas_a import read_curve
import numpy as np
import soundfile as sf


def custody():
    out={};lists=load(EV/'preflight.json')['lists'];roots=(B6,C6,S5,ROOT/'Proyecto SDV-SDI_SGM')
    for group in ('source','experimental'):
        for k,rec in load(OUT/(group+'_hashes.json'))['engines'].items():
            p=ROOT/rec['path'];h=digest(p);check(h==rec['sha256']==sha(blob(RC,p)) and git('rev-parse',RC+':'+rec['path']).decode().strip()==rec['blob'],p);out[group+'/'+k]=h
    for root,ref,rel in [(B6,RB,'SHA256SUMS.txt'),(C6,RC,'SHA256SUMS.txt'),(S5,RB,'hashes/SHA256SUMS.txt')]:
        p=root/rel;check(p.read_bytes()==blob(ref,p) and digest(p)==lists[root.name]['sha256'],root)
        for l in p.read_text().splitlines():h,f=l.split('  ',1);check(digest(root/f)==h,root/f)
    git('diff','--exit-code',RC,'--',*(str(p.relative_to(ROOT)) for p in roots))
    check(digest(OUT/'BANCO_RESERVADO_MANIFEST.json')=='9e35280d3a10cab2fa3644ab3f8340ce76f308adc7d89bcca4b65fb6016de256','frozen holdout');registry={}
    for f in (B6/'signals_manifest.json',C6/'evidence/reserva_manifest.json',OUT/'BANCO_RESERVADO_MANIFEST.json'):registry.update(load(f)['wavs'])
    n=0
    for p in (WORK/'wav').glob('*.wav'):check(p.stem in registry and digest(p)==p.stem,p);n+=1
    for name,x in load(S5/'signals/manifest.json')['audio'].items():check(digest(WORK/'s5/inputs'/name)==x['sha256'],name)
    return dict(hashes=out,lists=lists,work_wav_verified=n,s5_inputs=True,protected_paths_unchanged_from_RC=True)

def compare_ast(b):
    old,new=[{v.name:ast.dump(v,include_attributes=False) for v in ast.parse(source(b,orig).read_text()).body if isinstance(v,(ast.FunctionDef,ast.ClassDef))} for orig in (True,False)];return dict(identical=sorted(k for k in old.keys()&new.keys() if old[k]==new[k]),changed=sorted(k for k in old.keys()&new.keys() if old[k]!=new[k]),added=sorted(new.keys()-old.keys()),removed=sorted(old.keys()-new.keys()))

def history(b):
    compared={};nm=['6B','reserva'];exp={}
    for key in nm:
        with gzip.open(C6/f'evidence/{key}_{b}.jsonl.gz','rt') as f:
            for line in f:x=json.loads(line)['record'];exp[x['id']]=x['raw']
    with (B6/f'evidence/{b}.jsonl').open() as f:
        old={x['case']:{r:v['raw'] for v in x['calls'] for r in v['roles']} for line in f for x in [json.loads(line)['record']]}
    for mode,ref,count in [('6C',exp,30),('original',old,26)]:
        n=0
        for x in unpacked(EV/f'det_{b}_{mode}.json.gz'):
            if x['id'] not in ref:continue
            check(x['raw']==ref[x['id']],(b,mode,x['id']));n+=2
        check(n==count,(mode,n));compared[mode]=n
    return compared

def channels(b,log):
    c=Counter();emax=0.;pmax=0.
    for v in ['6C','original']:
        rows=unpacked(EV/f'det_{b}_{v}.json.gz');check(len(rows)==42,b)
        for r in rows:
            check(not r['exceptions'],(r['id'],r['exceptions']));c['python_warnings']+=len(r['python_warnings'])
            for role,x in r['raw'].items():
                c['native_calls']+=1
                if v=='original':continue
                ch=x['channels'];ks=[z['estimated_offset_samples'] for z in ch.values()];k=x['estimated_offset_samples'];check(set(ch)==set('LR') and (k is not None)==(ks[0] is not None and ks[0]==ks[1]),(b,r['id'],role));check(x['action']==dict(shift_authorized=False,applied_shift_samples=0,polarity_changed=False),'action');
                if None not in ks:check(x['guide_delay_R_minus_L']==ks[0]-ks[1] and x['k_R_minus_L']==ks[1]-ks[0],'delta')
                else:check(x['guide_delay_R_minus_L'] is None and x['k_R_minus_L'] is None,'no delta')
                for name,u in ch.items():
                    if 'error' in u:log.append(f"det_{b}_6C:{r['id']}/{role}/{name}: {u['error']}")
                    d=u['guide_delay_samples'];m=u['classification'] in ('ALIGNED','WARNING','MISALIGNED');check(m==(d is not None) and (not m or u['estimated_offset_samples']==-d and abs(u['correlation_peak'])<=1 and u['alignment_confidence']>0),u['reason']);check(m or all(u[key] is None for key in ('estimated_offset_samples','correlation_peak','alignment_confidence')),'abstention')
                    for w in u['windows']:
                        h=w['tG']-w['tM']
                        for pp in w['candidates']:
                            q=pp['q'];a0,a1=pp['M'];b0,b1=pp['G'];check(a1-a0==b1-b0==pp['overlap']>=w['min_overlap'] and pp['k']==q-h==a0-b0 and pp['d']==-pp['k'] and abs(pp['rho'])<=1,'candidate geometry');c['candidate_checks']+=1
                        if r['id'] in REPLICAS:
                            # Independent direct physical-domain Pearson for every wave proposal, not only rank one.
                            j='LR'.index(name);aa,bb=[sf.read(WORK/'wav'/(r['files'][key]+'.wav'),dtype='float64',always_2d=True)[0][:,j] for key in ('mix',role)]
                            for pp in w['candidates']:
                                ma=aa[slice(*pp['M'])];gb=bb[slice(*pp['G'])];val=np.corrcoef(ma,gb)[0,1];pmax=max(pmax,abs(val-pp['rho']));c['A_direct_Pearsons']+=1
            for z in r['curves']:
                ok,rr,st=read_curve(z);check(ok.sum()==z['nvalid'] and z['independent_valid_disagreements']==0,'curve');emax=max(emax,z['max_abs_rho_error'],z['max_abs_strength_error']);c['A_curves']+=1;c['A_bins']+=len(ok)
    check(emax<1e-12 and pmax<1e-12,'correlation cross-check');return dict(counts=c,max_native_vs_fftconvolve=emax,max_proposal_vs_direct=pmax)

def commandline(b,log):
    rr=unpacked(EV/f'cli_{b}.json.gz');n=Counter();rc=Counter();stage=Counter()
    for r in rr:
        z=r['summary'];s=z['id'];t=[p['state'] for p in z['roles']];rc[str(z['exit'])]+=1;n['ran']+=1
        if z['roles'] and s.endswith('/default') and not s.startswith('fault_'):check(z['reached_dsp']==(set(t)<={'ALIGNED','WARNING'}),s)
        if 'ERROR' in t:check(not z['reached_scale'] and z['exit']==1,s)
        if z['reached_dsp']:check(z['exit']==0 and z['final_report'] and z['wavs']==2 and z['shifts']==[0],s);stage['dsp']+=1
        else:check(not z['final_report'] and z['wavs']==0,s);stage['no_dsp']+=1
        if z['exit'] or 'ERROR' in t:log.append(f"cli_{b}:{s}: exit {z['exit']} estados {t}; DSP={z['reached_dsp']}; stdout/stderr y manifest en primario")
        check(not r['observations']['probe_errors'] and not z['trace_error'],s)
    return dict(counts=n,exit=rc,progress=stage)

def dsp(b,log):
    history={r['id']:r for r in load(C6/'RESULTADOS_NO_REGRESION.json')['runs']};rows=[r for r in load(EV/'dsp_index.json') if r['engine']==b];counts=Counter();err=[0.,0.];header_diffs=0;raw={r['id']:r['versions'] for r in unpacked(EV/f'dsp_{b}.json.gz')}
    for r in rows:
        id=r['id'];rr=raw[id];prior=history.get(id)
        if prior:check(r['exits']==[prior['exits'][v] for v in ('original','experimental')],id)
        if not r['complete']:
            check(r['exits']==[2,2] and r['validation_calls']==[0,0],id)
            for v,t in rr.items():check('ZeroDivisionError: float division by zero' in t['stdout']+t['stderr'] and t['summary']['aborted_dir'],id);log.append(f'dsp_{b}:{id}/{v}: ZeroDivisionError crest_factor_sdv; exit 2, _aborted, no validación final')
            counts['no_PCM_conclusion']+=1;continue
        check(r['exits']==[0,0] and r['both_reached_dsp'] and not r['different_tensors'] and r['max_tensor_delta']==r['both_formula_error']==r['reconstruction_delta']==0. and r['identical_scale'] and r['identical_span_sign_residual'] and r['shifts']==[0],id)
        for v,t in rr.items():
            oo=t['observations'];check(not oo['probe_errors'],id)
            for z in oo['sign_and_residual']:err[0]=max(err[0],z['sign_error']);err[1]=max(err[1],z['residual_error'] or 0.)
        for role,pt in r['pcm'].items():
            check(pt['different_samples']==0 and pt['max_delta_LR']==[0.,0.] and pt['frames']==r['n'] and pt['channels']==2 and pt['sr']==SR,id)
            paths=[next(f for f in t['wav'] if Path(f).stem.endswith(role)) for t in rr.values()];header_diffs+=len({t['output_files'][f]['sha256'] for t,f in zip(rr.values(),paths)})==2
            if prior:check(pt['sha256_decoded']==prior['pcm_comparison'][role]['decoded_sha256'],id);counts['same_6C_output_pairs']+=1
        counts['complete']+=1;counts['tensor_hashes']+=r['n_tensors'];counts['direct_tensor_comparisons']+=r['elementwise']
    check(max(err)==0.,'stage error');return dict(counts=counts,sign_residual_max_error=err,unequal_file_hashes_with_equal_pcm=header_diffs)

def main():
    q={};log=['Índice de incidencias observadas; trazas, stdout/stderr completos en los primarios indicados.', 'Veto de validación ≠ excepción Python. Casos provocados y fallos de instrumento se distinguen.']
    for b in 'BCD':q[b]=dict(protected_ast=compare_ast(b),raw_matches_archived_roles=history(b),detectors=channels(b,log),cli=commandline(b,log),dsp=dsp(b,log))
    for file in ('extra_raw','bordes_cli'):
        rr=unpacked(EV/(file+'.json.gz'));rr=rr['cli'] if isinstance(rr,dict) else rr
        for r in rr:
            z=r['summary'];check(not r['observations']['probe_errors'],z['id'])
            if z['exit'] or z['overall']=='fail':log.append(f"{file}:{z['engine']}/{z['id']} orig={z['original']} exit={z['exit']}, overall={z['overall']}, aborted={z['aborted_dir']}; ver consola y JSON")
    for rec in unpacked(EV/'testigos_cli_original.json.gz'):
        s=rec['summary']
        if s['id']=='S7/default':check(s['exit']==1 and not s['reached_scale'] and not rec['observations']['crest'],s['id'])
        else:check(s['trace_error'] and 'soundfile.LibsndfileError' in s['trace_error'] and s['exit']==99 and s['reached_scale'],s['id'])
        log.append(f"testigos_cli_original:{s['engine']}/{s['id']} orig={s['original']}, código={s['exit']} (99=excepción no manejada capturada por observador, NO exit nativo); ver traceback íntegro en primario")
    perf=load(EV/'resources_index.json');pp=unpacked(EV/'resources_raw.json.gz');check(len(pp)==len(perf['cli'])==36,'resource inventory')
    for v,s in zip(pp,perf['cli']):check(v['summary']==s and s['exit']==0 and (s['final_analyses'],s['wavs'])==((1,2) if s['mode']=='full_processing' else (0,0)),s['id'])
    mat=list(csv.DictReader((OUT/'MATRIZ_RESULTADOS_6D.csv').open()));check(len({(r['id'],r['rol'],r['motor'],r['canal']) for r in mat})==len(mat)==504,'matrix cardinality')
    save(EV/'control_calidad.json',dict(engines=q,resource_runs=len(pp),matrix_rows=len(mat),evidence='EXPERIMENTAL_RESULT',status='CONFIRMADO',scope='reproducibilidad de mediciones; no aprobación de motores'));save(EV/'postflight.json',custody());(OUT/'ERRORES_Y_EXCEPCIONES.log').write_text('\n'.join(log)+'\n');print('verificados: 504 filas, 168 retornos históricos pareados, controles CLI/DSP, recursos y custodia final')
if __name__=='__main__':main()
