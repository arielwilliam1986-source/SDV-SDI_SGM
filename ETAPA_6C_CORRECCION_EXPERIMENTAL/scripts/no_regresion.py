"""A/B dentro de cada motor: CLI real, arrays efectivamente consumidos y WAV físicos sin realinear."""
import contextlib
import io
import struct
import tempfile
import traceback
from comun import *
import numpy as np
import soundfile as sf


def inputs(work):
    pack = verified_prior(P/'evidence/inputs.tar.xz'); catalog = load(verified_prior(P/'signals/manifest.json'))
    with tarfile.open(pack,'r:xz') as tar:
        for m in tar:
            p=Path(m.name); require(p.parts[0]=='inputs' and '..' not in p.parts and m.isfile(),p)
            dest=work/p; dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(tar.extractfile(m).read())
    for p,v in catalog['audio'].items():require(file_sha(work/'inputs'/p)==v['sha256'],p)
    return catalog


def plan(b):
    if b=='D':return [(c,'shared','masks_first',False) for c in ('S3','S4','Ppos','S7')]
    return [('S3','per_channel','magnitudes_first',False),('S4','per_channel','magnitudes_first',False),
            ('Ppos','mono','masks_first',False),('Ppos','mono','magnitudes_first',True),
            ('S7','per_channel','magnitudes_first',False)]+([('Pneg','per_channel','hybrid_asymmetric',False)] if b=='C' else [])


def peak(x):return float(np.max(np.abs(x)))


class Probe:
    def __init__(self,mod,dir_,original):
        self.mod,self.dir,self.original=mod,dir_,original
        self.tensors={};self.differences={};self.reads=[];self.factors=[];self.formula=[];self.spans=[];self.errors=[];self.latest={}

    def tensor(self,key,x,compare=False):
        require(key not in self.tensors and np.isfinite(x).all(),key)
        self.tensors[key]=dict(shape=list(x.shape),dtype=x.dtype.str,sha256=sha(np.ascontiguousarray(x).tobytes()))
        if compare:
            path=self.dir/(key.replace('/','_')+'.npy')
            if self.original:np.save(path,x,allow_pickle=False)
            else:
                y=np.load(path,mmap_mode='r',allow_pickle=False); require(x.shape==y.shape and x.dtype==y.dtype,key)
                self.differences[key]=peak(x-y)

    def __call__(self,frame,event,arg):
        if frame.f_globals is not self.mod.__dict__ or event not in ('call','return'):return
        name=frame.f_code.co_name
        if name not in ('stft_span_frames','update_freq','read_span','analyze_guide_scale'):return
        try:self.observe(frame,event,arg,name)
        except Exception:self.errors.append(traceback.format_exc())

    def observe(self,frame,event,arg,name):
        loc=frame.f_locals
        if event=='return' and name=='analyze_guide_scale' and arg:
            self.factors.append(arg[1])
        if event=='return' and name=='read_span' and arg is not None:
            f=Path(loc['handle'].name);self.latest[f.resolve()]=arg
            self.reads.append(dict(file=f.name,start=loc['start'],end=loc['end'],shift=loc.get('shift_samples',0)))
        if event!='call' or name not in ('stft_span_frames','update_freq'):return
        p=frame.f_back.f_locals; f0=p['f0']
        if name=='stft_span_frames':
            x=loc['x2d']; k='mix'
            if x is not p['mix_span']:
                k=next(key for key in ('v_res','i_res','v_span','i_span','v_mono','i_mono') if isinstance(p.get(key),np.ndarray) and np.shares_memory(x,p[key]))
                short=k[0];role='vocal' if short=='v' else 'instrumental';pair=p['p'];span=p[short+'_span']
                fac=p['scale_factors'][pair.pair_id]; sign=fac.get(role+'_polarity',1.)
                raw=self.latest[Path(getattr(pair,role+'_path')).resolve()]
                residual=None
                if k.endswith('_res'):
                    other='instrumental' if short=='v' else 'vocal';mono=p['i_mono' if short=='v' else 'v_mono']
                    residual=peak(x[:,0]-(p['m_mono']-fac[other]*mono))
                self.spans.append(dict(f0=f0,pair=pair.pair_id,role=role,source=k,sign=sign,
                                       signed_read_error=peak(span-sign*raw),residual_formula_error=residual))
                k=pair.pair_id+'/'+k
            self.tensor(f'stft_input/{f0}/{k}',x,True);return
        if frame.f_code is not self.mod.CandidateMetrics.update_freq.__code__:return
        mv,mi=p['mv_c'],p['mi_c'];mix=loc['mix_stft'];v,i=loc['sdv_stft'],loc['sdi_stft'];cid=p['runner'].cand_id
        for nm,a in [('mv',mv),('mi',mi),('SDV_spectrum',v),('SDI_spectrum',i)]:
            self.tensor(f'{nm}/{f0}/{cid}',a,nm in ('mv','mi'))
        key='consensus/'+str(f0)+'/'
        if key+'median' not in self.tensors:
            for method,a in p['consensus'].items():self.tensor(key+method,a,True)
        self.formula.append(dict(f0=f0,candidate=cid,partition=peak(mv+mi-1.),SDV=peak(v-mix*mv),SDI=peak(i-mix*mi)))

    def result(self):
        return dict(tensors=self.tensors,read_spans=self.reads,scale_factors=self.factors,polarity_and_residual=self.spans,
                    max_abs_formula=self.formula,observer_errors=self.errors,elementwise_max_abs=self.differences)


def parse_wave(p):
    data=p.read_bytes();pos=12;pieces={}
    while pos+8<=len(data):
        key=data[pos:pos+4].decode('ascii');n=struct.unpack_from('<I',data,pos+4)[0]; chunk=data[pos+8:pos+8+n]
        pieces[key]=dict(bytes=n,sha256=sha(chunk))
        if key=='PEAK':pieces[key].update(timestamp=struct.unpack_from('<I',chunk,4)[0],except_timestamp_sha256=sha(chunk[:4]+chunk[8:]))
        pos+=8+n+(n%2)
    return pieces


def outputs(run):
    pcm={};stats={}
    for role in ('SDV','SDI'):
        p,=list(run.rglob('*'+role+'*.wav')); x,s=sf.read(p,dtype='float64',always_2d=True);info=sf.info(p)
        require(s==SR and x.shape==(176400,2) and np.isfinite(x).all(),p)
        pcm[role]=x; l,r=x.T; lr=float(np.linalg.norm(r)/np.linalg.norm(l)) if np.linalg.norm(l) else None
        corr=float(np.corrcoef(l,r)[0,1]) if l.std() and r.std() else None
        stats[role]=dict(sr=s,channels=2,frames=len(x),seconds=info.duration,subtype=info.subtype,file_sha256=file_sha(p),
                         pcm_decoded_sha256=sha(x.astype('<f8').tobytes()),channel_sha256=[sha(a.astype('<f8').tobytes()) for a in x.T],
                         rms_R_over_L=lr,pearson_LR=corr,signed_L_minus_R_rms=float(np.sqrt(np.mean((l-r)**2))),riff=parse_wave(p))
    return pcm,stats


def invoke(b,orig,case,mode,order,res,manifest,out,temp):
    mod=module(b,orig); out.mkdir();argv=['--manifest',str(manifest),'--out',str(out),'--mode','full_processing','--allow-misaligned',
          '--n-fft','4096','--hop','1024','--chunk-frames','64','--consensus','confidence_weighted_mean']
    if b=='D':argv+=['--power','2','--epsilon','1e-9']
    else:
        argv+=['--mask-mode',mode,'--consensus-order',order,'--smoothing','none','--power','1.8','--epsilon','1e-12','--beta','1']
        if res:argv+=['--use-residuals']
    parsed=mod.build_arg_parser().parse_args(argv); require(not getattr(parsed,'correct_alignment',False),'shift')
    probe=Probe(mod,temp,orig); old=sys.argv; prev=sys.getprofile(); output=io.StringIO(); exc=None;code=None
    with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
        try:
            sys.argv=[mod.__file__,*argv];sys.setprofile(probe);code=mod.main(argv)
        except Exception:exc=traceback.format_exc()
        finally:sys.setprofile(prev);sys.argv=old
    rec=dict(argv=['<manifest>' if a==str(manifest) else '<out>' if a==str(out) else a for a in argv],exit_code=code,
             native_exception=exc,native_log=output.getvalue(),observation=probe.result()); pcm={};analysis={}
    if code==0:
        pcm,rec['outputs']=outputs(out); aj,=list(out.rglob('analysis.json')); analysis=load(aj)
        rec['native_alignment']=[dict(classification=r['classification'],offset=r.get('estimated_offset_samples'),confidence=r.get('alignment_confidence'))
                                 for r in analysis.get('alignment_analysis',analysis.get('alignment',[]))]
    return rec,pcm,analysis


def fields(x,y,path=''):
    if isinstance(x,dict) and isinstance(y,dict):
        for k in sorted(x.keys()|y.keys()):
            if k not in x or k not in y:yield path+'/'+k
            else:yield from fields(x[k],y[k],path+'/'+k)
    elif isinstance(x,list) and isinstance(y,list) and len(x)==len(y):
        for idx,(v,w) in enumerate(zip(x,y)):yield from fields(v,w,path+'/'+str(idx))
    elif x!=y:yield path


def compare(b,job,work,logzip):
    case,mode,order,res=job; key='/'.join([b,case,mode,order,'res' if res else 'direct']); catalog=load(P/'signals/manifest.json')
    man=work/catalog['cases'][case]['manifest'];spec=load(man); paths=[spec['mix_original']]+[p[r+'_path'] for p in spec['pairs'] for r in ROLES]
    refs={k:file_sha((man.parent/k).resolve()) for k in paths};m=sf.read(man.parent/paths[0],dtype='float64',always_2d=True)[0]
    row=dict(id=key,engine=b,case=case,mask_mode=mode,order=order,use_physical_residuals=res if b!='D' else None,
             manifest_sha256=file_sha(man),input_sha256=refs,evidence='evidence/no_regresion.jsonl.gz#'+key)
    a={};pcm={};ana={}
    with tempfile.TemporaryDirectory(dir=work) as td:
        for version in ('original','experimental'):
            a[version],pcm[version],ana[version]=invoke(b,version=='original',*job,man,Path(td)/version,Path(td))
    for v in a:
        require(not a[v]['observation']['observer_errors'],a[v]['observation']['observer_errors'])
        require(a[v]['argv']==a['original']['argv'] and a[v]['native_exception'] is None,key)
    complete=all(v['exit_code']==0 for v in a.values());row['complete_both']=complete
    row['exits']={v:r['exit_code'] for v,r in a.items()}
    if not complete:
        known=case=='S7' and b=='D' and all('ZeroDivisionError' in r['native_log'] and 'crest_factor_sdv' in r['native_log'] for r in a.values())
        row.update(status='ABORTO_CREST_NO_COMPARABLE' if known else 'INCOMPLETO',pcm_comparison=None)
    else:
        d,e=[a[k]['observation'] for k in ('original','experimental')]
        row.update(tensors=len(d['tensors']),direct_array_comparisons=len(e['elementwise_max_abs']),
                   max_abs_arrays=max(e['elementwise_max_abs'].values()),tensor_differences=list(fields(d['tensors'],e['tensors'])),
                   max_abs_formula=max(v[k] for rec in (d,e) for v in rec['max_abs_formula'] for k in ('SDV','SDI','partition')),
                   shift_values=sorted({r['shift'] for rec in (d,e) for r in rec['read_spans']}),
                   other_observation_differences=[k for k in ('max_abs_formula','read_spans','scale_factors','polarity_and_residual') if d[k]!=e[k]],
                   polarity_signs=sorted({r['sign'] for r in e['polarity_and_residual']}),
                   max_signed_span_error=max(r['signed_read_error'] for r in e['polarity_and_residual']),
                   physical_residual_calls=sum(r['residual_formula_error'] is not None for r in e['polarity_and_residual']),
                   pcm_comparison={},report_changed_paths=list(fields(ana['original'],ana['experimental'])))
        for role in ('SDV','SDI'):
            x,y=[p[role] for p in pcm.values()];o,c=[r['outputs'][role] for r in a.values()]
            row['pcm_comparison'][role]=dict(max_abs_LR=np.max(abs(x-y),axis=0).tolist(),samples_different_LR=np.sum(x!=y,axis=0).tolist(),
                       decoded_sha256=[o['pcm_decoded_sha256'],c['pcm_decoded_sha256']],sr_channels_frames_duration_subtype=[c[k] for k in ('sr','channels','frames','seconds','subtype')],
                       rms_R_over_L=c['rms_R_over_L'],pearson_LR=c['pearson_LR'],changed_output_fields=list(fields(o,c)))
        residuals=[m-p['SDV']-p['SDI'] for p in pcm.values()];row['reconstruction']=dict(max_abs_LR=[np.max(abs(r),axis=0).tolist() for r in residuals],difference_LR=np.max(abs(residuals[0]-residuals[1]),axis=0).tolist())
        row['status']='IDENTICO_PCM_Y_DSP' if not (row['tensor_differences'] or row['other_observation_differences'] or row['max_abs_arrays'] or any(max(r['max_abs_LR']) for r in row['pcm_comparison'].values())) and row['shift_values']==[0] else 'DIFERENCIA'
    logzip.write(canon(dict(id=key,versions=a))+b'\n');return row


def main():
    custody(); BUILD.mkdir(parents=True,exist_ok=True);EVID.mkdir(parents=True,exist_ok=True);rows=[]
    with tempfile.TemporaryDirectory(dir=BUILD) as td, (EVID/'no_regresion.jsonl.gz').open('wb') as raw, gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as z:
        work=Path(td);inputs(work)
        for b in 'BCD':
            for job in plan(b):
                row=compare(b,job,work,z);rows.append(row);print(row['id'],row['status'],flush=True)
    save(OUT/'RESULTADOS_NO_REGRESION.json',dict(scope='mismos WAV verificados, cada original vs su copia, CLI full_processing sin --correct-alignment',
              evidencia='EXPERIMENTAL_RESULT',dictamen='CONFIRMADO CON LIMITACIONES',runs=rows))

if __name__=='__main__':main()
