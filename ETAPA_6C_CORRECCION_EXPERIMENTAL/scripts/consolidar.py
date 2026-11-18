"""Cruce posterior: carga el oráculo DESPUÉS de la medición. No ejecuta DSP."""
from collections import Counter
import csv
from comun import *


def severity(d):return 'ALIGNED' if abs(d)<=1 else 'WARNING' if abs(d)<=441 else 'MISALIGNED'


def metrics(rows,original=False):
    def state(r):return r['old_state_common'] if original else r['state_ch']
    def delay(r):return r['old_d_common'] if original else r['d_ch']
    aligned=('ALIGNED','ALIGNED_BY_IDENTITY'); abst=('INSUFFICIENT_SIGNAL','AMBIGUOUS','ERROR')
    marks=[r for r in rows if r['d_mark'] is not None];zs=[r for r in marks if not r['d_mark']];nz=[r for r in marks if r['d_mark']];sv=[r for r in nz if abs(r['d_mark'])>441]
    score=lambda r: r['old_confidence'] if original else r['confidence_ch']
    accepted=[r for r in marks if delay(r) is not None]
    return dict(rows=len(rows),marks=len(marks),zeros=len(zs),nonzeros=len(nz),severe=len(sv),
        zero_exact=sum(delay(r)==0 for r in zs),zero_supported=sum((r['old_external_state']=='ALIGNED' if original else (delay(r)==0 and state(r)=='ALIGNED' and (score(r) or 0)>0)) for r in zs),
        exact=sum(delay(r)==r['d_mark'] for r in marks),nonzero_exact=sum(delay(r)==r['d_mark'] for r in nz),
        fp_zero_to_MIS=sum(state(r)=='MISALIGNED' for r in zs),fp_zero_to_WARNING=sum(state(r)=='WARNING' for r in zs),
        fp_threshold_MIS=sum(state(r)=='MISALIGNED' and abs(r['d_mark'])<=441 for r in marks),
        fn_severe_to_AL_or_identity=sum(state(r) in aligned for r in sv),fn_severe_to_WARNING=sum(state(r)=='WARNING' for r in sv),
        severe_unresolved=sum(state(r) in abst for r in sv),severe_without_MIS=sum(state(r)!='MISALIGNED' for r in sv),
        nonzero_to_AL_or_identity=sum(state(r) in aligned for r in nz),nonzero_to_zero=sum(delay(r)==0 for r in nz),
        nonzero_opposite_sign=sum(delay(r) is not None and delay(r)*r['d_mark']<0 for r in nz),
        unavailable_on_marks=sum(delay(r) is None for r in marks),
        incorrect_measured_lag=sum(delay(r)!=r['d_mark'] for r in accepted),
        max_abs_error_when_issued=max((abs(delay(r)-r['d_mark']) for r in accepted),default=None),
        abstention_truth={target:dict(total=sum(r['expected']==target for r in rows),as_expected=sum(r['expected']==state(r)==target for r in rows),
              measured_instead=sum(r['expected']==target and state(r) not in abst for r in rows)) for target in abst},
        state_counts=dict(sorted(Counter(state(r) for r in rows).items())))


def main():
    exp=custody(); man=load(verified_prior(Q/'signals_manifest.json')); oracle=load(verified_prior(Q/'evidence/oraculo.json'))['cases']
    index=load(verified_prior(Q/'RESULTADOS_DETECTORES.json'))['motores'];reserve=load(EVID/'reserva_manifest.json')
    with verified_prior(Q/'MATRIZ_RESULTADOS.csv').open() as f:
        old={(r['motor'],r['caso'],r['rol'],r['canal']):r for r in csv.DictReader(f) if r['motor'] in 'BCD'}
    meta={v['id']:v for v in [*man['cases'],*reserve['cases']]};base=meta['A_d+0_4s'];meta['X_lectura_ausente_4s']=dict(base,group='X')
    rows=[];stereo=[];errors=[];summ={};criteria=['ALIGNED','WARNING','MISALIGNED'];natives={}
    for b in 'BCD':
        natives[b]={};summ[b]={};
        for phase in ('6B','reserva'):
            case_index={}; first=len(rows)
            for line,r in enumerate(records(b,phase),1):
                c=r['id'];tag='X' if c.startswith('X_') else phase; group=meta[c].get('group','R');post=r['aggregator_only'];src=f'evidence/{phase}_{b}.jsonl.gz:{line}'
                require(c not in case_index and exp[b]['sha256']==r['experimental_sha256'],c)
                case_index[c]=dict(row=src,record_sha256=sha(canon(r)),complete=r['complete'],overall=post['overall'] if post else None)
                if r['unexpected_exceptions'] or r['forbidden_calls']:errors.append([b,c,'UNEXPECTED',r['unexpected_exceptions'],r['forbidden_calls']])
                for w in r['python_warnings']:errors.append([b,c,'PYTHON_WARNING',w])
                for key,p in r['preflight'].items():
                    for w in p['warnings']+p['errors']:errors.append([b,c,key,'PREFLIGHT',w])
                for role in ROLES:
                    rec=r['raw'][role];state=rec['classification']; chs=rec['channels'];srow=dict(engine=b,partition=tag,case=c,role=role,
                        source=src,common_state=state,k_common=rec['estimated_offset_samples'],dR_minus_dL=rec['guide_delay_R_minus_L'],reason=rec['reason'],channels={})
                    if rec.get('error'):errors.append([b,c,role,state,rec['error'],rec.get('traceback'),src])
                    if state!='ALIGNED':errors.append([b,c,role,'ALIGNMENT',state,rec['reason'],src])
                    for j,ch in enumerate('LR'):
                        o=(oracle[c] if phase=='6B' else meta[c])['channel_oracle'][role][j];d=o['lag_marca']; wanted=severity(d) if d is not None else o['clase']
                        v=chs[ch];s=v['classification'];k=v['estimated_offset_samples'];result=v['guide_delay_samples'];w=v.get('windows',[])
                        outcome=('EXACT' if d is not None and result==d and s==wanted else 'EXPECTED_ABSTENTION_OR_ERROR' if d is None and s==wanted and result is None else
                                 'UNRESOLVED_MARK' if d is not None and result is None else 'UNJUSTIFIED_DECISION' if d is None and result is not None else 'WRONG_LAG_OR_STATE')
                        prev=old[(b,c,role,ch)] if phase=='6B' else {};ix=index[b]['cases'][c] if phase=='6B' else {};legacy=ix.get('roles',{}).get(role,{})
                        if prev:require(prev['estado_original']==legacy['estado_original'] and (int(prev['d_marca']) if prev['d_marca'] else None)==d,(c,ch))
                        row=dict(engine=b,partition=tag,group=group,case=c,frames=meta[c]['frames'],sr=SR,seed=meta[c]['seed'],role=role,channel=ch,
                            mix_sha256=r['inputs']['mix'],guide_sha256=r['inputs'][role],source_sha256=exp[b]['input_sha256'],experimental_sha256=exp[b]['sha256'],
                            d_recipe=o.get('d_inyectado'),d_mark=d,d_mark_ms=None if d is None else 1000*d/SR,expected=wanted,oracle_reason=o['razon'],
                            old_state_common=legacy.get('estado_original'),old_external_state=prev.get('estado_externo'),old_k_common=legacy.get('k_nativo'),old_d_common=legacy.get('d_publicado'),old_uncensored_d=legacy.get('d_candidato'),
                            old_rho=legacy.get('score'),old_confidence=legacy.get('confianza'),old_raw=ix.get('raw'),old_validation=prev.get('resumen_MQR_aislado'),
                            state_ch=s,k_ch=k,d_ch=result,d_ch_ms=None if result is None else 1000*result/SR,rho_ch=v['correlation_peak'],confidence_ch=v['alignment_confidence'],
                            reasons=';'.join([v['reason']]+[u['reason'] for u in w]),first_candidate_d=w[0].get('best',{}).get('d') if w else None,
                            tG=';'.join(str(u['tG']) for u in w),tM=';'.join(str(u['tM']) for u in w),state_role=state,k_common=rec['estimated_offset_samples'],dR_minus_dL=rec['guide_delay_R_minus_L'],
                            abs_error=None if d is None or result is None else abs(d-result),comparison=outcome,aggregator=post['overall'] if post else None,
                            complete_context=r['complete'],shift=rec['action']['applied_shift_samples'],raw=src,evidence_label='EXPERIMENTAL_RESULT',
                            verdict='CONFIRMADO' if outcome in ('EXACT','EXPECTED_ABSTENTION_OR_ERROR') else 'NO CONFIRMADO')
                        rows.append(row);srow['channels'][ch]=dict(d_mark=d,expected=wanted,k=k,d=result,confidence=v['alignment_confidence'],rho=v['correlation_peak'],state=s,comparison=outcome)
                    stereo.append(srow)
            natives[b][phase]=case_index
            for tag in (('6B','X') if phase=='6B' else ('reserva',)):
                part=[r for r in rows[first:] if r['partition']==tag];summ[b][tag]={}
                for name,subset in [('all',part)]+[(role,[r for r in part if r['role']==role]) for role in ROLES]:
                    summ[b][tag][name]=dict(experimental=metrics(subset),original_common_contrasted_to_columns=metrics(subset,True) if phase=='6B' else None)
                marked=[r for r in part if r['d_mark'] is not None]
                if phase=='6B':
                    summ[b][tag]['paired_exact_numbers']=dict(Counter(
                        ('old_exact' if r['old_d_common']==r['d_mark'] else 'old_other')+'__'+
                        ('new_exact' if r['d_ch']==r['d_mark'] else 'new_other') for r in marked))
                summ[b][tag]['by_signed_mark']={str(d):dict(n=len(rr),exact=sum(v['d_ch']==d for v in rr),
                    abstentions=sum(v['d_ch'] is None for v in rr)) for d in sorted({r['d_mark'] for r in marked})
                    if (rr:=[r for r in marked if r['d_mark']==d])}
                summ[b][tag]['outcomes']=dict(Counter(r['comparison'] for r in part));summ[b][tag]['non_exact_or_unjustified']=[r['case']+'/'+r['role']+'/'+r['channel']+':'+r['comparison'] for r in part if r['comparison'] not in ('EXACT','EXPECTED_ABSTENTION_OR_ERROR')]
    with (OUT/'MATRIZ_PRUEBAS_REGRESION.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    save(OUT/'RESULTADOS_REGRESION.json',dict(schema='6c-regression/1',unit='canal físico × rol × caso por motor. El escalar antiguo se contrasta con cada columna, no son dos estimaciones nativas.',
        signs='k=-d; verdad por marca cuando es medible. Severidad 6C ≤1/≤441/>441; FP y FN de alarma no equivalen a error de estimación.',
        evidence='EXPERIMENTAL_RESULT',verdict='CONFIRMADO CON LIMITACIONES',summary=summ,index=natives))
    save(OUT/'RESULTADOS_ESTEREO.json',dict(schema='6c-stereo/1',unit='par P1/rol, diferencia en muestras dR−dL, null si alguna columna no es medible',evidence='EXPERIMENTAL_RESULT',verdict='CONFIRMADO CON LIMITACIONES',rows=stereo))
    nr=load(OUT/'RESULTADOS_NO_REGRESION.json');
    with gzip.open(EVID/'no_regresion.jsonl.gz','rt') as f:
        for line,item in zip(f,nr['runs'],strict=True):
            rr=json.loads(line);require(item['id']==rr['id'],item['id'])
            for vv,r in rr['versions'].items():
                for msg in r['native_log'].splitlines():
                    if any(t in msg.lower() for t in ('[warn','[fatal','error:','traceback','[abort','[auto-phase','continuación explícita','autorizacion explicita')):
                        errors.append([rr['id'],vv,'CLI',msg])
                if r['exit_code']!=0:errors.append([rr['id'],vv,'INCOMPLETE',r['exit_code'],'traza íntegra en evidence/no_regresion.jsonl.gz'])
    (OUT/'ERRORES_Y_EXCEPCIONES.log').write_text('# JSON por línea. No confundir desacuerdo, warning, abstención, excepción y fallo del observador. Logs CLI completos comprimidos en evidence/no_regresion.jsonl.gz.\n'+'\n'.join(canon(v).decode() for v in errors)+'\n')
    print('Contrastes:',len(rows),'roles estéreo:',len(stereo),'incidencias:',len(errors))

if __name__=='__main__':main()
