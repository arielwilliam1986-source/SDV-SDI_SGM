"""Audit the complete command line, exit AND actual progress, including intentionally bad WAVs."""
import argparse
import shutil
import struct
import tempfile
from common import *
from detect import cases
import numpy as np
import soundfile as sf
from scipy.io import wavfile


def manifest(mx,pairs):
    return dict(mix_original=str(mx),pairs=[dict(pair_id='P%02d'%(i+1),family='AUDIT',variant='V%02d'%i,configuration='synthetic',source='synthetic',vocal_path=str(v),vocal_guide=str(v),instrumental_path=str(g),instrumental_guide=str(g)) for i,(v,g) in enumerate(pairs)])

def from_case(c):
    paths={r:WORK/'wav'/(c['files'][r]+'.wav') for r in ('mix',*ROLES)};return manifest(paths['mix'],[(paths['vocal'],paths['instrumental'])])

def audio_stats(p):
    x,s=sf.read(p,dtype='float32',always_2d=True);info=sf.info(p);check(np.isfinite(x).all(),p)
    return dict(pcm=sha(x.astype('<f4').tobytes()),channel_sha=[sha(ch.astype('<f4').tobytes()) for ch in x.T],sr=s,frames=len(x),channels=info.channels,subtype=info.subtype)

def invoke(b,id,spec,work,orig=False,extra=(),interactive=None,dsp=False,comp=None,fault=None,mode='full_processing'):
    work.mkdir(parents=True,exist_ok=True);out=work/'out';out.mkdir();man=work/'input.json';save(man,spec)
    args=['--mode',mode,'--out',str(out)]+(['--manifest',str(man)] if interactive is None else ['--mix',spec['mix_original']])+list(extra)
    config=work/'config.json';cfg=dict(engine=b,original=orig,argv=args,dsp=dsp,compare_dir=str(comp or work),fault=str(fault) if fault else None);save(config,cfg)
    command=[sys.executable,'-Bu',str(HERE/'scripts/cli_child.py'),str(config)];pr=subprocess.run(command,input=interactive or '',capture_output=True,text=True)
    ob=load(work/'observed.json') if (work/'observed.json').exists() else {};check(ob and not ob['probe_errors'],(id,ob.get('probe_errors'),pr.stderr));files={};wavs={};texts={}
    for p in sorted(out.rglob('*')):
        if p.is_file():
            path=str(p.relative_to(out));files[path]=dict(bytes=p.stat().st_size,sha256=digest(p))
            if p.suffix in ('.json','.txt') or p.name.endswith('.log'):texts[path]=p.read_text()
            if p.suffix=='.wav':wavs[path]=audio_stats(p)
    pjs=[(k,v) for k,v in texts.items() if k.endswith('analysis.json') and '_aborted/' not in k];analysis=json.loads(pjs[0][1]) if len(pjs)==1 else {};valid=analysis.get('validation_status',{});aligned=analysis.get('alignment',analysis.get('alignment_analysis',[]))
    row=dict(id=id,engine=b,original=orig,mode=mode,flags=list(extra),exit=pr.returncode,reached_dsp=ob['calls'].get('stft_span_frames',0)>0,reached_scale=ob['calls'].get('analyze_guide_scale',0)>0,final_report=bool(analysis),wavs=len(wavs),aborted_dir=any('_aborted' in str(p) for p in out.iterdir()),
             roles=[dict(state=r.get('classification'),k=r.get('estimated_offset_samples'),channels={ch:v['classification'] for ch,v in r.get('channels',{}).items()}) for r in ob['alignment']],
             overall=valid.get('overall'),permission_BC=[r.get('continuation_permission') for r in aligned] if b!='D' else None,permission_D=[v.get('source') for v in valid.get('items',[]) if v.get('check')=='misalignment_user_authorized'],trace_error=ob.get('uncaught'),shifts=sorted(set(ob['observed_shifts'])))
    rec=dict(summary=row,manifest=spec,manifest_sha256=digest(man),config=cfg,command=command,stdin=interactive,stdout=pr.stdout,stderr=pr.stderr,native_reports=texts,observations=ob,output_files=files,wav=wavs)
    return row,rec

def main():
    items={c['id']:c for c in cases()};WORK.mkdir(exist_ok=True);rows=[]
    for b in 'BCD':
        runs=[]
        def one(id,c,flags=(),special=None,mode='full_processing'):
            with tempfile.TemporaryDirectory(dir=WORK) as tmp:
                root=Path(tmp);s=from_case(c);pa=s['pairs'][0];fault=None;stdin=None
                if special in ('missing','header','truncated','race'):
                    src=Path(pa['vocal_guide']);p=root/('volatile.wav' if special=='race' else 'test_'+special+'.wav')
                    if special=='header':p.write_bytes(src.read_bytes()[:14])
                    elif special=='truncated':p.write_bytes(src.read_bytes()[:-8192*8]) # keep RIFF/data lengths unmodified
                    elif special=='race':shutil.copyfile(src,p);fault=p
                    pa['vocal_guide']=pa['vocal_path']=str(p)
                if special in ('si','no'):stdin='1\nP01\nAUDIT\nv\ntest\n'+pa['vocal_guide']+'\n'+pa['instrumental_guide']+'\nmanual\n\n'+special+'\n'
                row,raw=invoke(b,id,s,root,extra=flags,fault=fault,interactive=stdin,mode=mode);runs.append(raw);rows.append(row)
                if special=='truncated':
                    buf=p.read_bytes();off=buf.index(b'data',36);raw['observed_container']=dict(declared_riff_bytes=struct.unpack_from('<I',buf,4)[0]+8,actual_bytes=len(buf),declared_data_bytes=struct.unpack_from('<I',buf,off+4)[0],actual_data_bytes=len(buf)-off-8,decoder_frames=sf.info(p).frames)
        for c in items.values():
            if c['partition']=='6B':continue
            one(c['id']+'/default',c)
            if c['id'] in {'Z','W','M','distintos','soloL','alarma_mudo','dc','invalida_L','R_dos_origenes','R_replica_dominante','circular','rival_R'}:one(c['id']+'/override',c,['--allow-misaligned'])
        for special in ('missing','header','truncated','race'):
            for flags,name in (([],'default'),(['--allow-misaligned'],'override')):one('fault_'+special+'/'+name,items['Z'],flags,special)
        if b=='D':
            for yes in ('si','no'):one('interactive/'+yes,items['M'],[],yes)
        else:one('request_shift',items['Z'],['--correct-alignment','--allow-misaligned'])
        one('dry_not_audit',items['M'],[],mode='dry_run');packed(EV/f'cli_{b}.json.gz',runs);print(b,len(runs),'CLI',flush=True)
    save(EV/'cli_index.json',rows)
if __name__=='__main__':main()
