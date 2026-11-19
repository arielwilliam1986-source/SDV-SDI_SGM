"""Run a pinned, unmodified script as __main__. Profiling observes, never replaces DSP or gates."""
import runpy
import traceback
from collections import Counter
from common import *
import numpy as np


def run(config):
    c=load(config);p=source(c['engine'],c['original']);target=str(p);r=dict(alignment=[],validation=[],crest=[],factors=[],observed_shifts=[],calls={},tensors={},formula=[],sign_and_residual=[],probe_errors=[],faults=[]);cnt=Counter();cache={};latest={};dsp=c['dsp'];refdir=Path(c['compare_dir'])
    def tensor(key,x,compare=False):
        check(key not in r['tensors'] and np.isfinite(x).all(),key);a=np.ascontiguousarray(x);v=dict(sha256=sha(a.tobytes()),shape=list(x.shape),dtype=x.dtype.str)
        if compare:
            f=refdir/(key.replace('/','_')+'.npy')
            if c['original']:np.save(f,a,allow_pickle=False)
            else:
                other=np.load(f,allow_pickle=False,mmap_mode='r');check(a.shape==other.shape and a.dtype==other.dtype,key);v['max_abs_diff']=float(np.max(abs(a-other)))
        r['tensors'][key]=v
    def trace(f,ev,arg):
        if ev not in ('call','return') or f.f_globals.get('__file__')!=target:return
        name=f.f_code.co_name
        if name not in ('analyze_alignment','run_experiment','build_validation_status','finalize','analyze_guide_scale','stft_span_frames','update_freq','read_span'):return
        try:
            t=f.f_locals
            if ev=='call':cnt[name]+=1
            if name=='analyze_alignment':
                if ev=='call' and c.get('fault') and not r['faults']:
                    victim=Path(c['fault']);check(victim.name=='volatile.wav' and victim.parent==config.parent and victim==Path(t['guide_info'].path),'fault restricted to disposable copy');victim.unlink();r['faults'].append('temporary V removed after probe')
                if ev=='return' and isinstance(arg,dict):r['alignment'].append(dict(arg))
            if name=='build_validation_status' and ev=='return' and arg:r['validation'].append(arg)
            if name=='finalize' and ev=='call' and 'self' in t and type(t['self']).__name__=='CandidateMetrics' and c['engine']=='D':
                a=t['self'];r['crest'].append({k:getattr(a,k) for k in ('n_samples','sum_mix2','sum_sdv2','sum_sdi2','sum_err2','peak_sdv','peak_mix')})
            if name=='read_span' and ev=='return' and arg is not None:
                r['observed_shifts'].append(t.get('shift_samples',0));
                if dsp:latest[str(Path(t['handle'].name).resolve())]=arg
            if not dsp:return
            if name=='analyze_guide_scale' and ev=='return' and arg:r['factors'].append(arg[1])
            if ev!='call' or name not in ('update_freq','stft_span_frames'):return
            u=f.f_back.f_locals;f0=u['f0'];key=str(f0)+'/'
            if name=='stft_span_frames':
                x=t['x2d'];label='mix'
                if x is not u['mix_span']:
                    s=next(k for k in ('v_res','i_res','v_span','i_span','v_mono','i_mono') if isinstance(u.get(k),np.ndarray) and np.shares_memory(x,u[k]));role='vocal' if s[0]=='v' else 'instrumental';pa=u['p'];fac=u['scale_factors'][pa.pair_id];sgn=fac.get(role+'_polarity',1.);orig=latest[str(Path(getattr(pa,role+'_path')).resolve())];diff=float(np.max(abs(u[s[0]+'_span']-sgn*orig)));res=None
                    if s.endswith('_res'):
                        other='instrumental' if role=='vocal' else 'vocal';res=float(np.max(abs(x[:,0]-(u['m_mono']-fac[other]*u[other[0]+'_mono']))))
                    label=pa.pair_id+'/'+s;r['sign_and_residual'].append(dict(f0=f0,role=role,label=label,sign=sgn,sign_error=diff,residual_error=res))
                tensor('stft_in/'+key+label,x,True);return
            if type(t['self']).__name__!='CandidateMetrics':return
            cid=u['runner'].cand_id;x=t['mix_stft'];v=t['sdv_stft'];i=t['sdi_stft'];mv=u['mv_c'];mi=u['mi_c'];suffix=key+cid
            for k,y in (('Mv',mv),('Mi',mi),('X',x),('SDV',v),('SDI',i)):tensor(k+'/'+suffix,y,k in ('Mv','Mi'))
            if f0 not in cache:
                for k,y in u['consensus'].items():tensor('consensus/'+key+k,y,True)
                cache[f0]=True
            r['formula'].append([suffix,float(np.max(abs(v-x*mv))),float(np.max(abs(i-x*mi))),float(np.max(abs(1.-mv-mi)))])
        except Exception:r['probe_errors'].append(traceback.format_exc())
    sys.argv=[target,*c['argv']];sys.setprofile(trace);code=0
    try:runpy.run_path(target,run_name='__main__')
    except SystemExit as e:code=e.code
    except Exception:r['uncaught']=traceback.format_exc();traceback.print_exc();code=99
    finally:sys.setprofile(None)
    r['calls']=dict(cnt);save(config.parent/'observed.json',r);return code
if __name__=='__main__':sys.exit(run(Path(sys.argv[1]).resolve()))
