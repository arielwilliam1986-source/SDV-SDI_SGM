"""Ejecuta las funciones completas usadas por main/run_experiment; sin sustituciones ni DSP."""
import argparse
import contextlib
import copy
import importlib.util
import inspect
import io
import os
import sys
import time
import traceback
import warnings
from types import SimpleNamespace
from base import BUILD, OUT, REPO, EVID, ROLES, ENTRY, canonical, digest, load, np, sha, sources
from generar import path_for,restore


def cases_with_fault(man):
    base=next(c for c in man['cases'] if c['id']=='A_d+0_4s');x=copy.deepcopy(base)
    x.update(id='X_lectura_ausente_4s',group='X',test='lectura_ausente',kind='fault',metadata_template=x['files']['vocal'])
    x['files']['vocal']=None
    return [*man['cases'],x]


def error():return traceback.format_exc()


class Observer:
    """Captura de escalares de la invocación original, sin reejecutar auxiliares ni escribir en frames."""
    def __init__(self,m,b):
        self.global_dict=m.__dict__;self.b=b;self.trace={};self.violations=[];self.errors=[]

    def __call__(self,frame,event,arg):
        if event!='call' or frame.f_globals is not self.global_dict:return None
        name=frame.f_code.co_name
        if name in ('read_span','stft_span','stft_span_frames','audit_polarity','analyze_guide_scale','run_processing','_run_core'):
            self.violations.append(name)
        names=('audit_alignment','mono_downmix') if self.b=='A' else ('_ncc_fft_coarse','_refine_alignment','analyze_alignment')
        if name not in names:return None
        frame.f_trace_lines=False
        return self.at_return

    def at_return(self,frame,event,arg):
        if event=='return' and arg is not None:
            try:self.record(frame.f_code.co_name,frame.f_locals,arg)
            except Exception:self.errors.append(error())
        return self.at_return

    def record(self,name,x,arg):
        out=self.trace
        if name=='mono_downmix':out.setdefault('mids_en_orden_M_V_I',[]).append(dict(frames=len(arg),variance=float(arg.var())))
        elif name=='audit_alignment':out.update(prefix_frames=x['win'],nfft=x['nfft'])
        elif name=='_ncc_fft_coarse':
            k=x['lags'];na,nb=x['A'],x['B'];l=np.maximum(0,k);r=np.minimum(na,nb+k)
            valid=(r-l>=x['min_overlap']) & (x['sa2'][r]>x['sa2'][l]) & (x['sb2'][r-k]>x['sb2'][l-k]);v=x['vals'];i=x['j_best']
            out.update(coarse_env_bins=int(arg[0]),coarse_local_samples=int(arg[0])*8,coarse_score=float(arg[1]),env_score_at_local_zero=float(v[len(v)//2]),coarse_bins_examined=len(v),valid_env_bins=int(valid.sum()),winning_env_bin_valid=bool(valid[i]),exact_max_ties=int((v==v[i]).sum()),coarse_range_local_samples=[int(k[0])*8,int(k[-1])*8])
        elif name=='_refine_alignment':
            ll=x['lags'];n,m=len(x['mix_mono']),len(x['guide_mono']);scores=[float(f) for f in x['vals']]
            out.update(fine_local_integer=int(arg[0]),fine_score=float(arg[1]),fine_local_subsample=float(arg[2]),fine_start=ll[0],fine_end=ll[-1],fine_scores=scores,overlaps_at_least_4096=sum(min(n,m+k)-max(0,k)>=4096 for k in ll),mid_variance_M=float(x['mix_mono'].var()),mid_variance_G=float(x['guide_mono'].var()),frames_M=n,frames_G=m)
        elif name=='analyze_alignment' and 'fine_local_integer' in out:
            g=int(x.get('best_pos',0));m=int(x.get('mix_start',0));out.update(tG=g,tM=m,h=g-m,uncensored_global_native_subsample=out['fine_local_subsample']-(g-m))


def observed(obs,fn,*args):
    inspect.signature(fn).bind(*args);old=sys.gettrace();sys.settrace(obs)
    try:return fn(*args)
    finally:sys.settrace(old)


def run_case(mod,b,source,c):
    paths={k:v+'.wav' if v else 'AUSENTE_6B.wav' for k,v in c['files'].items()}
    if c['group']=='X' and os.path.exists(paths['vocal']):raise ValueError('El control negativo exige ruta ausente')
    r=dict(id=b+'/'+c['id'],case=c['id'],engine=b,version=source['version'],source_sha256=source['sha256'],entry=ENTRY[b],inputs={k:c['files'][k] for k in ('mix',*ROLES)},seed=c['seed'],sr=44100,channels=2,frames=c['frames'],seconds=c['T'],truth_samples=c['delays'],truth_ms={k:[1000*x/44100 for x in v] for k,v in c['delays'].items()},calls=[],exceptions=[],preflight={},post=None,actions_observed=[],observer_errors=[],alignment_shift_attempted=False,polarity_correction_attempted=False,separation_started=False)
    std,err=io.StringIO(),io.StringIO();start=time.monotonic()
    with contextlib.redirect_stdout(std),contextlib.redirect_stderr(err),warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter('always')
        try:
            mx=mod.probe_file(paths['mix'],'mix');infos={}
            for role in ROLES:
                if role=='vocal' and c['group']=='X':
                    # Metadatos previamente sondeados; la ruta de lectura no existe. Sólo el argumento de prueba.
                    infos[role]=copy.copy(mod.probe_file(c['metadata_template']+'.wav',role));infos[role].path=paths[role]
                    r['preflight'][role]={'valid':False,'reason':'control posterior al sondeo; ruta deliberadamente ausente','sha256':None};continue
                infos[role]=mod.probe_file(paths[role],role)
                if b=='A':
                    try:mod.check_degeneration(infos[role]);r['preflight'][role]={'valid':True}
                    except Exception:r['preflight'][role]={'valid':False,'exception':error()}
                else:
                    z=mod.validate_guide(infos[role]);r['preflight'][role]={'valid':z.valid,'errors':z.errors,'warnings':z.warnings}
            if b!='A':
                mx=mod.validate_mix(mx);r['preflight']['mix']={'valid':mx.valid,'errors':mx.errors,'warnings':mx.warnings}
            if b=='A':
                pair=mod.PairMeta('P1','sintetica','6B',paths['vocal'],paths['instrumental']);o=Observer(mod,b)
                call={'roles':list(ROLES),'function':ENTRY[b],'raw':None,'exception':None};r['calls'].append(call)
                try:call['raw']=observed(o,mod.audit_alignment,[pair],mx)
                except Exception:call['exception']=error()
                call['trace']=o.trace;r['actions_observed']+=o.violations;r['observer_errors']+=o.errors
            else:
                for role in ROLES:
                    o=Observer(mod,b);call={'roles':[role],'function':ENTRY[b],'raw':None,'exception':None};r['calls'].append(call)
                    try:call['raw']=observed(o,mod.analyze_alignment,mx,infos[role])
                    except Exception:call['exception']=error()
                    call['trace']=o.trace;r['actions_observed']+=o.violations;r['observer_errors']+=o.errors
                if b=='D' and all(q['raw'] is not None for q in r['calls']):
                    pair=mod.PairMeta('P1','sintetica','6B','6B',paths['vocal'],paths['instrumental'],source='sintetica',vocal=infos['vocal'],instrumental=infos['instrumental'])
                    records=[dict(q['raw'],role=q['roles'][0],pair_id='P1') for q in r['calls']]
                    ctx=dict(mix_info=mx,pairs=[pair],alignment=records,warnings=list(mx.warnings)+[w for role in ROLES for w in infos[role].warnings]);opt=SimpleNamespace(mode=mod.MODE_ANALYSIS_ONLY)
                    r['post']={'function':'build_validation_status','scope':'Agregador original aislado; contexto de entradas y detección, NO es exit ni validación post-WAV.','result':mod.build_validation_status(ctx,opt)}
        except Exception:r['exceptions'].append(error())
        r['python_warnings']=[dict(category=w.category.__name__,message=str(w.message),file=os.path.basename(w.filename),line=w.lineno) for w in ws]
    r.update(stdout=std.getvalue(),stderr=err.getvalue(),elapsed_seconds=round(time.monotonic()-start,6))
    # Un retorno con error interno, una excepción o un retorno ausente no son éxitos.
    r['complete_return']=len(r['calls'])==(1 if b=='A' else 2) and all(isinstance(q['raw'],dict) and not q['exception'] and not q['raw'].get('error') for q in r['calls']) and not (r['exceptions'] or r['observer_errors'] or r['actions_observed'])
    r['sha256_resultado_nativo']=digest([q['raw'] for q in r['calls']]);return r


def main():
    ap=argparse.ArgumentParser();ap.add_argument('motores',choices=['A','B','C','D','AC','BD','AB','CD','ABCD']);a=ap.parse_args();verified=sources();assert verified==load(OUT/'source_hashes.json');man=load(OUT/'signals_manifest.json');cases=cases_with_fault(man)
    # Si se reproduce sólo desde custodia, ejecutar generar.py --restaurar primero.
    for h in man['wavs']:
        if not path_for(h).is_file() or sha(path_for(h).read_bytes())!=h:raise ValueError('Restaurar primero el WAV: '+h)
    os.chdir(BUILD/'wav')
    for b in a.motores:
        source=verified['motores'][b];src=REPO/source['path'];assert sha(src.read_bytes())==source['sha256'];spec=importlib.util.spec_from_file_location('original_6b_'+b,src);mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod);assert mod.ENGINE_VERSION==source['version'];f=EVID/f'{b}.jsonl'
        with f.open('xb') as out:
            for i,c in enumerate(cases,1):
                r=run_case(mod,b,source,c);out.write(canonical(dict(sha256=digest(r),record=r))+b'\n');out.flush()
                if i%10==0 or i==len(cases):print(b,i,'/',len(cases),c['id'],flush=True)
        assert sha(src.read_bytes())==source['sha256']

if __name__=='__main__':main()
