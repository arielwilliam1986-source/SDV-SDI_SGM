"""Audita custodia, aplicación byte-exacta de los parches y coherencia de la evidencia 6C."""
import argparse
import ast
from collections import Counter
import csv
import difflib
import io
import math
import tempfile
from comun import *
import numpy as np
import soundfile as sf


def patches(write=False):
    exp=custody(); result={}; sources=load(HERE/'source_hashes.json')['fuentes']
    for b,title in zip('BCD',('HARDENED','EVO','MQR')):
        r=sources[b];name=Path(r['path']).name;original=blob(ROOT/r['path']);copy=(HERE/exp[b]['path']).read_bytes()
        d=b''.join(difflib.diff_bytes(difflib.unified_diff,original.splitlines(True),copy.splitlines(True),('a/'+name).encode(),('b/'+name).encode()))
        p=OUT/('DIFF_'+title+'.patch')
        if write:p.write_bytes(d)
        require(p.read_bytes()==d,p)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/name;path.write_bytes(original)
            subprocess.run(['patch','--fuzz=0','-s','-p1','-i',str(p)],cwd=td,check=True)
            require(path.read_bytes()==copy,'aplicación del parche '+b)
        trees=[ast.parse(z) for z in (original,copy)]; compile(copy,name,'exec')
        nodes=[{n.name:n for n in t.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))} for t in trees];o,c=nodes
        changed=sorted(k for k in o.keys() & c.keys() if ast.dump(o[k])!=ast.dump(c[k]))
        permitted={'analyze_alignment','run_experiment','write_analysis_txt','build_arg_parser'}|({'build_validation_status','run_self_test','build_document_meta'} if b=='D' else set())
        require(set(changed)==permitted and ast.dump(o['analyze_alignment'].args)==ast.dump(c['analyze_alignment'].args),'alcance AST '+b)
        require(o.keys()-c.keys()=={'_ncc_fft_coarse','_refine_alignment','_aligned_pair','_pearson'},'helpers retirados '+b)
        result[b]=dict(patch=p.name,sha256=file_sha(p),compiled=True,exact_reapplication=True,changed_existing_functions=changed,
            added_functions=sorted(c.keys()-o.keys()),identical_existing_definitions=len(o.keys()&c.keys())-len(changed),
            entry_lines=[c['analyze_alignment'].lineno,c['analyze_alignment'].end_lineno])
    return result


def check_lists():
    report={}
    for base,name in [(Q,'SHA256SUMS.txt'),(P,'hashes/SHA256SUMS.txt'),(P/'AUDIT_INDEPENDIENTE','SHA256SUMS.txt'),(ROOT/'ETAPA_6_ALINEACION_DIAGNOSTICO','SHA256SUMS.txt')]:
        p=verified_prior(base/name);lines=p.read_text().splitlines()
        for row in lines:
            h,rel=row.split('  ',1);require(file_sha(base/rel)==h,base/rel)
        report[str(p.relative_to(ROOT))]=dict(entries=len(lines),list_sha256=file_sha(p))
    return report


def qawav():
    man=load(Q/'signals_manifest.json');rman=load(EVID/'reserva_manifest.json'); seen=set();wav6b(man)
    require(not set(man['wavs']) & set(rman['wavs']) and rman['freeze']==custody(),'contaminación/congelación')
    for ar in man['archives']:require(file_sha(Q/ar['path'])==ar['sha256'],ar)
    pack=EVID/rman['archive']['name'];require(file_sha(pack)==rman['archive']['sha256'],pack)
    with tarfile.open(pack,'r|xz') as tar:
        for m in tar:
            buf=tar.extractfile(m).read();h=sha(buf);meta=rman['wavs'][h];require(m.name==h+'.wav' and h not in seen,m.name);seen.add(h)
            x,sr=sf.read(io.BytesIO(buf),dtype='float32',always_2d=True)
            require(sr==SR and np.isfinite(x).all() and x.shape==(meta['frames'],2) and sha(x.astype('<f4').tobytes())==meta['pcm_sha256'],h)
    require(seen==set(rman['wavs']),'reserva incompleta')
    return dict(wav_6b=file_sha(Q/'signals_manifest.json'),unique_6B=len(man['wavs']),unique_reserve=len(seen),wav_hash_intersection=0,all_reserve_pcm_finite=True)


def finite(obj):
    if isinstance(obj,dict):
        for v in obj.values():finite(v)
    elif isinstance(obj,list):
        for v in obj:finite(v)
    elif isinstance(obj,float):require(math.isfinite(obj),'no finito')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--parches',action='store_true');opt=ap.parse_args()
    files=patches(opt.parches)
    if opt.parches:
        print('Tres diffs reaplicados y compilados',flush=True); return
    qa=dict(prior=check_lists(),patches=files,wav=qawav(),label='EXPERIMENTAL_RESULT',verdict='CONFIRMADO CON LIMITACIONES'); counts=Counter(); post=Counter();reg=load(OUT/'RESULTADOS_REGRESION.json');st=load(OUT/'RESULTADOS_ESTEREO.json')
    with (OUT/'MATRIZ_PRUEBAS_REGRESION.csv').open() as f:mat=list(csv.DictReader(f))
    key=lambda r:(r['engine'],r['case'],r['role'],r['channel']); matrix={key(r):r for r in mat}; supplied={(r['engine'],r['case'],r['role']):r for r in st['rows']}
    require(len(mat)==len(matrix)==3*(201+13)*4 and 2*len(supplied)==len(mat),'dimensiones')
    ids={v['id'] for v in load(Q/'signals_manifest.json')['cases']}|{'X_lectura_ausente_4s'};rs={v['id'] for v in load(EVID/'reserva_manifest.json')['cases']}
    truth = load(Q/'evidence/oraculo.json')['cases'] | {v['id']:v for v in load(EVID/'reserva_manifest.json')['cases']}
    for b in 'BCD':
        for phase,expected in [('6B',ids),('reserva',rs)]:
            cases=set()
            for r in records(b,phase):
                finite(r);cid=r['id']; require(cid not in cases,cid);cases.add(cid);counts['contexts']+=1
                require(not r['forbidden_calls'] and not r['unexpected_exceptions'],cid); counts['python_warnings']+=len(r['python_warnings'])
                require(r['complete']==(not cid.startswith('X_')),cid); idx=reg['index'][b][phase][cid];require(idx['record_sha256']==sha(canon(r)),cid)
                for role in ROLES:
                    a=r['raw'][role];states=[];ds=[];counts['calls']+=1
                    require(a['action']==dict(applied_shift_samples=0,polarity_changed=False,shift_authorized=False) and set(a['channels'])==set('LR'),cid)
                    if a.get('error'):
                        require(cid.startswith('X_') and role=='vocal' and a['classification']=='ERROR',cid);counts['expected_read_errors']+=1
                    for ch,u in a['channels'].items():
                        counts['channel_rows']+=1;k=u['estimated_offset_samples'];d=u['guide_delay_samples'];s=u['classification'];ds.append(d);states.append(s)
                        row=matrix[(b,cid,role,ch)];sr=supplied[(b,cid,role)]; require(row['state_ch']==s==sr['channels'][ch]['state'] and row['d_ch']==('' if d is None else str(d)),cid)
                        target=truth[cid]['channel_oracle'][role]['LR'.index(ch)]; mark=target['lag_marca']
                        expected_state=target['clase'] if mark is None else ('MISALIGNED' if abs(mark)>441 else 'WARNING' if abs(mark)>1 else 'ALIGNED')
                        require(row['expected']==expected_state and row['d_mark']==('' if mark is None else str(mark)),cid)
                        require((row['comparison']=='EXACT')==(mark is not None and d==mark and s==expected_state),cid)
                        require((row['comparison']=='EXPECTED_ABSTENTION_OR_ERROR')==(mark is None and d is None and s==expected_state),cid)
                        for w in u.get('windows',[]):
                            for cand in w['candidates']+([w['zero']] if w.get('zero') else []):
                                require(abs(cand['rho'])<=1 and cand['q']==cand['k']+w['tG']-w['tM'] and cand['d']==-cand['k'] and cand['overlap']>=w['min_overlap'],cid)
                                l,e=cand['M'];lg,eg=cand['G'];require(e-l==eg-lg==cand['overlap'] and (l-lg)==cand['k'] and 0<=lg<eg and 0<=l<e,cid)
                        if k is None:require(d is u['alignment_confidence'] is None and s in ('ERROR','AMBIGUOUS','INSUFFICIENT_SIGNAL'),cid)
                        else:
                            require(d==-k and 0<u['alignment_confidence']<=1 and s==('ALIGNED' if abs(k)<=1 else 'WARNING' if abs(k)<=441 else 'MISALIGNED'),cid)
                    # dict order in compressed canonical JSON is L,R
                    common=a['estimated_offset_samples']; complete=None not in ds and len(set(ds))==1
                    require(complete==(common is not None) and (not complete or common==-ds[0]),cid)
                    require(a['guide_delay_R_minus_L']==(None if None in ds else ds[1]-ds[0]),cid)
                    if a['classification']=='ALIGNED':require(states==['ALIGNED','ALIGNED'] and common is not None,cid)
                if b=='D':
                    s=r['aggregator_only']['overall'];post[phase+'/'+s]+=1
                    crit=any(v['classification'] not in ('ALIGNED','WARNING') for v in r['raw'].values()) or not all(p['valid'] for p in r['preflight'].values())
                    require((s=='fail')==crit,cid)
            require(cases==expected,(b,phase))
    nr=load(OUT/'RESULTADOS_NO_REGRESION.json')['runs'];complete=[r for r in nr if r['complete_both']];bad=[r for r in nr if not r['complete_both']]
    require(len(complete)==14 and len(bad)==1 and bad[0]['status']=='ABORTO_CREST_NO_COMPARABLE','matriz DSP')
    with gzip.open(EVID/'no_regresion.jsonl.gz','rt',encoding='utf-8') as f:
        for line,summary in zip(f,nr,strict=True):
            versions=json.loads(line)['versions']; a,e=versions['original'],versions['experimental']
            require(a['argv']==e['argv'] and '--correct-alignment' not in e['argv'],summary['id'])
            if not summary['complete_both']:
                require(all(v['exit_code']!=0 and 'ZeroDivisionError' in v['native_log'] for v in (a,e)),summary['id']);continue
            oa,oe=a['observation'],e['observation']; require(oa['tensors']==oe['tensors'] and len(oe['tensors'])==summary['tensors'],summary['id'])
            require(len(oe['elementwise_max_abs'])==summary['direct_array_comparisons'] and max(oe['elementwise_max_abs'].values())==0,summary['id'])
            for role in ('SDV','SDI'):
                x,y=a['outputs'][role],e['outputs'][role]
                require(x['riff']['data']==y['riff']['data'] and x['channel_sha256']==y['channel_sha256'],summary['id'])
                for k in x['riff']:
                    if k=='PEAK':require(x['riff'][k]['except_timestamp_sha256']==y['riff'][k]['except_timestamp_sha256'],summary['id'])
                    else:require(x['riff'][k]==y['riff'][k],summary['id'])
    for r in complete:
        require(r['status']=='IDENTICO_PCM_Y_DSP' and r['shift_values']==[0] and not r['max_abs_formula'] and not r['max_signed_span_error'],r['id'])
        require(not max(r['reconstruction']['difference_LR']) and all(c['decoded_sha256'][0]==c['decoded_sha256'][1] for c in r['pcm_comparison'].values()),r['id'])
    qa.update(regression=dict(counts),mqr_summary_counts=dict(post),uncontrolled_exceptions=0,forbidden_calls=0,no_regression=dict(complete_pairs=len(complete),incomplete_pairs=len(bad),tensor_comparisons=sum(r['tensors'] for r in complete),elementwise=sum(r['direct_array_comparisons'] for r in complete)),
              tests='evidence/tests.log',native_self_test='evidence/mqr_self_test.log')
    save(EVID/'control_calidad.json',qa); print('QA OK',qa['regression'],qa['mqr_summary_counts'])

if __name__=='__main__':main()
