"""Invoca el detector COMPLETO de cada copia para ambos roles y (en D) el agregador real."""
import argparse
import copy
import gzip
import inspect
import sys
import traceback
import warnings
from types import SimpleNamespace
from comun import *


def run(mod,b,c,wav,exp,phase):
    pre, raw, violations = {}, {}, []
    def path(role):
        h = c['files'][role]
        return wav/(h+'.wav') if h else wav/'AUSENTE_6C.wav'
    def guard(frame,event,arg):
        if event=='call' and frame.f_globals is mod.__dict__ and frame.f_code.co_name in {
                'read_span','run_experiment','_run_core','analyze_guide_scale','stft_span_frames','mono_downmix'}:
            violations.append(frame.f_code.co_name)
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter('always')
        infos = {}
        for role in ('mix',*ROLES):
            p = path(role)
            if c['files'][role] is None:
                require(not p.exists(),p)
                info = copy.copy(mod.probe_file(str(wav/(c['template']+'.wav')),role))
                info.path = str(p); info.valid = False; info.errors = ['control posterior al sondeo: ruta ausente']
            else:
                info = (mod.validate_mix if role=='mix' else mod.validate_guide)(mod.probe_file(str(p),role))
            infos[role] = info; pre[role] = dict(valid=info.valid,errors=info.errors,warnings=info.warnings)
        uncaught = []
        for role in ROLES:
            try:
                args = (infos['mix'],infos[role]); inspect.signature(mod.analyze_alignment).bind(*args)
                old = sys.getprofile(); sys.setprofile(guard)
                try:
                    raw[role] = mod.analyze_alignment(*args)
                finally:
                    sys.setprofile(old)
            except Exception:
                raw[role] = None; uncaught.append(traceback.format_exc())
        post = None
        if b=='D' and all(raw.values()):
            pair = SimpleNamespace(pair_id='P1',vocal=infos['vocal'],instrumental=infos['instrumental'])
            ctx = dict(mix_info=infos['mix'],pairs=[pair],alignment=[dict(raw[r],role=r,pair_id='P1') for r in ROLES],warnings=[])
            post = mod.build_validation_status(ctx,SimpleNamespace(mode=mod.MODE_ANALYSIS_ONLY))
        msgs = [f'{w.category.__name__}: {w.message}' for w in ws]
    return dict(id=c['id'],engine=b,partition=phase,experimental_sha256=exp[b]['sha256'],inputs={k:c['files'][k] for k in ('mix',*ROLES)},
                preflight=pre,entry='analyze_alignment',raw=raw,aggregator_only=post,unexpected_exceptions=uncaught,
                forbidden_calls=violations,python_warnings=msgs,complete=not uncaught and all(r and not r.get('error') for r in raw.values()))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('phase',choices=['6B','reserva']); ap.add_argument('engines'); args=ap.parse_args()
    require(args.engines and set(args.engines)<=set('BCD'),'motores')
    exp = custody()
    if args.phase=='6B':
        man=load(verified_prior(Q/'signals_manifest.json')); wav=wav6b(man)
        base=next(c for c in man['cases'] if c['id']=='A_d+0_4s'); x=copy.deepcopy(base)
        x.update(id='X_lectura_ausente_4s',template=x['files']['vocal']); x['files']['vocal']=None
        cases=[*man['cases'],x]
    else:
        man=load(EVID/'reserva_manifest.json'); require(man['freeze']==exp,'la reserva exige los hashes congelados'); cases=man['cases'];wav=BUILD/'reserva'
        for h in man['wavs']:
            require(file_sha(wav/(h+'.wav'))==h,h)
    EVID.mkdir(parents=True,exist_ok=True)
    for b in args.engines:
        mod=module(b); p=EVID/(args.phase+'_'+b+'.jsonl.gz'); tmp=p.with_suffix('.part')
        with tmp.open('wb') as f, gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as z:
            for i,c in enumerate(cases,1):
                rec=run(mod,b,c,wav,exp,args.phase)
                z.write(canon(dict(record=rec,sha256=sha(canon(rec))))+b'\n')
                if i%20==0 or i==len(cases):
                    print(b,args.phase,i,'/',len(cases),c['id'],flush=True)
        tmp.replace(p); custody()

if __name__=='__main__':
    main()
