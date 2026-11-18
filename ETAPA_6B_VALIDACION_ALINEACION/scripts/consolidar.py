"""Distingue observabilidad, retorno nativo, escalar proyectado y política. No corre motores."""
import collections
import csv
import json
import statistics
from base import OUT, EVID, ROLES, SR, digest, load, save, sources, np
from ejecutar import cases_with_fault


def get_records(engine,cases):
    path=EVID/(engine+'.jsonl');recs={};expected={engine+'/'+c['id'] for c in cases}
    with path.open(encoding='utf-8') as f:
        for line_no,line in enumerate(f,1):
            z=json.loads(line);r=z['record'];assert line.endswith('\n') and digest(r)==z['sha256'] and r['id'] not in recs and r['engine']==engine;recs[r['id']]=(r,z['sha256'],line_no)
    if set(recs)!=expected:raise RuntimeError(f'Expediente {engine} incompleto: {len(recs)}/{len(expected)}; no computar como éxito.')
    return recs


def project(c,b,r,role,oracle):
    matches=[v for v in r['calls'] if role in v['roles']];q=matches[0] if matches else {};raw=q.get('raw');t=q.get('trace',{});a=(b=='A');exc=q.get('exception') or (raw or {}).get('error') or ('\n'.join(r['exceptions']) or None)
    n=((raw or {}).get('pairs',{}).get('P1',{}).get(role,{}) if a else (raw or {}));cls=n.get('classification');k=n.get('lag_samples' if a else 'estimated_offset_samples');ms=n.get('offset_ms' if a else 'estimated_offset_ms');sgn=1 if a else -1
    pub=None if ms is None or k is None else (int(round(ms*SR/1000)) if a else -int(k))
    cand=k if a else (None if 'uncensored_global_native_subsample' not in t else -round(t['uncensored_global_native_subsample']))
    rho=n.get('ncc' if a else 'correlation_peak');conf=n.get('alignment_confidence');mids=t.get('mids_en_orden_M_V_I',[])
    i=ROLES.index(role);vm=(mids[0]['variance'] if a and mids else t.get('mid_variance_M'));vg=(mids[1+i]['variance'] if a and len(mids)>1+i else t.get('mid_variance_G'))
    g0,m0=(0,0) if a else (t.get('tG'),t.get('tM'));ng=t.get('prefix_frames') if a else t.get('frames_G');nm=t.get('prefix_frames') if a else t.get('frames_M')
    no_measure=bool(exc or r['observer_errors'] or r['actions_observed'] or not cls or cls=='ERROR' or (not a and ('fine_score' not in t or 'coarse_score' not in t)))
    assert not (r['alignment_shift_attempted'] or r['separation_started'] or r['actions_observed'] or r['polarity_correction_attempted'])
    for ch,w in enumerate(oracle):
        d=c['delays'][role][ch];assert d==w['d_inyectado'];meas=w['lag_marca'];err=None if pub is None or meas is None or no_measure else pub-meas
        policy=(('ALIGNED' if abs(d)<=441 else 'MISALIGNED') if a else ('ALIGNED' if abs(d)<=1 else ('WARNING' if abs(d)<=441 else 'MISALIGNED'))) if meas is not None else None
        both_measured=all(x['lag_marca'] is not None for x in oracle);disagree=both_measured and len(set(c['delays'][role]))>1
        if no_measure or w['clase']=='ERROR':ext,why='ERROR','excepción/falta retorno o evidencia íntegra'
        elif w['clase'] in ('INSUFFICIENT_SIGNAL','AMBIGUOUS','WARNING'):ext,why=w['clase'],w['razon']
        elif vm==0 or vg==0 or t.get('valid_env_bins')==0 or t.get('overlaps_at_least_4096')==0:ext,why='INSUFFICIENT_SIGNAL','sin varianza o soporte en el tramo/proyección realmente usado'
        elif cls=='PERIODIC_PEAK_IGNORED':ext,why='AMBIGUOUS','el detector retira el candidato por su guarda; no es lag cero medido'
        elif cls=='ALIGNED_BY_IDENTITY' or conf==0 or rho==0 or rho is None or abs(rho)>1+1e-12:ext,why='WARNING','valor sustituido o sin apoyo en el propio score; no certificar'
        elif disagree or not both_measured:ext,why='WARNING','el escalar no acredita dos relojes distintos o un canal sin información'
        elif err!=0:ext,why='WARNING','el escalar no coincide exactamente con la marca conocida; ver error continuo'
        else:ext,why=w['clase'],'compatible con la marca en esta columna; no es estimación L/R nativa'
        in_window=None if w['ubicacion_ref'] is None or m0 is None or ng is None else (m0<=w['ubicacion_ref'] and w['ubicacion_ref']+w['longitud_marca']<=m0+nm and g0<=w['ubicacion_guia'] and w['ubicacion_guia']+w['longitud_marca']<=g0+ng)
        yield dict(run=r['id'],caso=c['id'],grupo=c['group'],prueba=c['test'],motor=b,version=r['version'],fuente_sha256=r['source_sha256'],semilla=c['seed'],sr=SR,canales=2,muestras=c['frames'],duracion_s=c['T'],par='P1',rol=role,canal='LR'[ch],sha256_mix=c['files']['mix'],sha256_guia=c['files'][role],sha256_retorno_nativo=r['sha256_resultado_nativo'],d_real=d,d_real_ms=1000*d/SR,signo_polaridad=c['sign'][role][ch],ganancia_guia=c['gain'][role][ch],d_marca=meas,estado_oraculo=w['clase'],politica_nativa_si_identificado=policy,estimacion_nativa_por_canal=None,lag_nativo=k,offset_ms_nativo=ms,d_publicado_comun=pub,d_publicado_ms=None if ms is None else sgn*ms,d_candidato_antes_de_veto=cand,delta_nominal=None if pub is None else pub-d,error_contra_marca=err,error_marca_ms=None if err is None else err*1000/SR,error_magnitud=None if err is None else abs(abs(pub)-abs(d)),estado_original=cls,criterio='max_abs_onda_y_AC' if a else 'coseno_RMS_y_max_Pearson_firmado',coarse_local=t.get('coarse_local_samples'),coarse_global=None if t.get('h') is None else t['coarse_local_samples']-t['h'],coarse_score=t.get('coarse_score'),rho_final=rho,confianza=conf,AC_mix=n.get('autocorr_guard'),tG=g0,tM=m0,frames_G=ng,frames_M=nm,var_mid_G=vg,var_mid_M=vm,marca_en_ventanas=in_window,estado_externo=ext,motivo_externo=why,lectura_cli_guia_valida=r['preflight'].get(role,{}).get('valid'),excepcion=(exc.splitlines()[-1] if exc else None),estado_ejecucion_rol=('NO_EJECUTADO_TRAS_ABORTO_DEL_PAR' if a and c['group']=='X' and role=='instrumental' else ('FALLO' if no_measure else 'RETORNO')),fallo_rol=no_measure,retorno_caso_completo=r['complete_return'],resumen_MQR_aislado=(r['post']['result']['overall'] if r['post'] else None),shift_intentado=False,shift_aplicado=0,polaridad_corregida=False,separacion=False)


def metrics(rows):
    # Denominadores independientes del éxito del detector. Un registro es una comparación canal-escalar.
    rows=list(rows);obs=[s for s in rows if s['d_marca'] is not None and s['grupo']!='X'];z=[s for s in obs if s['d_real']==0];nz=[s for s in obs if s['d_real']!=0];severe=[s for s in nz if abs(s['d_real'])>441];signed=[s for s in nz if s['error_contra_marca'] is not None];ev=[s for s in obs if s['error_contra_marca'] is not None];errs=[s['error_contra_marca'] for s in ev];ae=[abs(x) for x in errs];mag=[s['error_magnitud'] for s in ev];na=[s for s in rows if s['estado_oraculo']=='AMBIGUOUS'];ins=[s for s in rows if s['estado_oraculo']=='INSUFFICIENT_SIGNAL'];approved={'ALIGNED','ALIGNED_BY_IDENTITY'}
    return dict(filas=len(rows),casos=len(set(s['run'] for s in rows)),observables=len(obs),con_numero_y_marca=len(ev),cero=len(z),no_cero=len(nz),severos=len(severe),cero_lag_exacto=sum(s['error_contra_marca']==0 for s in z),cero_compatible_con_evidencia=sum(s['estado_externo']=='ALIGNED' for s in z),cero_por_identidad_legacy=sum(s['estado_original']=='ALIGNED_BY_IDENTITY' for s in z),no_cero_compatible_con_evidencia=sum(s['estado_externo']=='MISALIGNED' for s in nz),no_cero_lag_exacto=sum(s['error_contra_marca']==0 for s in nz),severo_lag_exacto=sum(s['error_contra_marca']==0 for s in severe),pico_fuera_de_rango=sum(s['rho_final'] is not None and abs(s['rho_final'])>1+1e-12 for s in rows),FP_cero_MIS=sum(s['estado_original']=='MISALIGNED' for s in z),cero_WARNING=sum(s['estado_original']=='WARNING' for s in z),FN_no_cero_aprobado=sum(s['estado_original'] in approved for s in nz),FN_severo_aprobado=sum(s['estado_original'] in approved for s in severe),severo_sin_MIS=sum(s['estado_original']!='MISALIGNED' for s in severe),incierto_en_severo=sum(s['estado_original']=='PERIODIC_PEAK_IGNORED' for s in severe),clase_de_su_politica=sum(s['estado_original']==s['politica_nativa_si_identificado'] for s in obs),lag_publicado_exacto=ae.count(0),lag_a_una_muestra=sum(x<=1 for x in ae),compatibles_con_evidencia=sum(s['estado_externo'] in ('ALIGNED','MISALIGNED') for s in obs),error_signo_opuesto=sum(s['d_publicado_comun']*s['d_real']<0 for s in signed),no_cero_estimado_cero=sum(s['d_publicado_comun']==0 for s in signed),sesgo_muestras=statistics.mean(errs) if errs else None,MAE_muestras=statistics.mean(ae) if ae else None,mediana_error_abs=statistics.median(ae) if ae else None,max_error_abs=max(ae,default=None),MAE_magnitud=statistics.mean(mag) if mag else None,ambiguos=len(na),ambiguos_reconocidos=sum(s['estado_original'] in ('PERIODIC_PEAK_IGNORED','AMBIGUOUS') for s in na),ambiguos_aprobados=sum(s['estado_original'] in approved for s in na),ambiguos_MIS=sum(s['estado_original']=='MISALIGNED' for s in na),sin_senal=len(ins),sin_senal_rechazo_explicito=sum(s['estado_original']=='INSUFFICIENT_SIGNAL' for s in ins),sin_senal_aprobados=sum(s['estado_original'] in approved for s in ins),sin_senal_MIS=sum(s['estado_original']=='MISALIGNED' for s in ins),fallos_rol_canal=sum(s['fallo_rol'] for s in rows))


def write_csv(p,rows):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def analyze():
    man=load(OUT/'signals_manifest.json');cases=cases_with_fault(man);src=sources();assert src==load(OUT/'source_hashes.json');proof=load(EVID/'oraculo.json');rows=[];result={};log=[]
    for b in 'ABCD':
        recs=get_records(b,cases);by_case={}
        for c in cases:
            r,h,line=recs[b+'/'+c['id']];assert r['source_sha256']==src['motores'][b]['sha256'] and r['inputs']=={k:c['files'][k] for k in ('mix',*ROLES)} and r['truth_samples']==c['delays'];assert r['sha256_resultado_nativo']==digest([q['raw'] for q in r['calls']]);start=len(rows);o=proof['cases'][c['id']]['channel_oracle']
            for role in ROLES:rows.extend(project(c,b,r,role,o[role]))
            cr=rows[start:];by_case[c['id']]=dict(raw=f'evidence/{b}.jsonl:{line}',record_sha256=h,native_sha256=r['sha256_resultado_nativo'],complete_return=r['complete_return'],roles={s['rol']:{'estado_original':s['estado_original'],'k_nativo':s['lag_nativo'],'d_publicado':s['d_publicado_comun'],'d_candidato':s['d_candidato_antes_de_veto'],'score':s['rho_final'],'confianza':s['confianza'],'error_contra_marca_L_R':[t['error_contra_marca'] for t in cr if t['rol']==s['rol']],'validacion_externa_L_R':[t['estado_externo'] for t in cr if t['rol']==s['rol']]} for s in cr if s['canal']=='L'})
            def logit(layer,msg):log.append(f"{r['id']} | {layer}\n{msg}\n")
            for role,x in r['preflight'].items():
                if not x['valid']:logit('preflight separado '+role,x.get('exception') or x.get('reason') or repr(x['errors']))
                for w in x.get('warnings',[]):logit('warning de entrada '+role,w)
            for q in r['calls']:
                if q['exception']:logit('excepción propagada '+str(q['roles']),q['exception'])
                if (q['raw'] or {}).get('error'):logit('error devuelto por detector '+str(q['roles']),q['raw']['error']+' | '+q['raw']['classification'])
                if q['trace'].get('fine_score',0)<-1.00000001:logit('anomalía (no excepción)',f"{q['roles']} pico fino = {q['trace']['fine_score']}; no es correlación válida")
            for k in ('exceptions','observer_errors','python_warnings','actions_observed'):
                for x in r[k]:logit(k,x)
            for k in ('stdout','stderr'):
                if r[k]:logit(k,r[k])
        result[b]=dict(version=src['motores'][b]['version'],source_sha256=src['motores'][b]['sha256'],cases=by_case)
    assert len(rows)==len(cases)*4*2*2 and len({(s['run'],s['rol'],s['canal']) for s in rows})==len(rows)
    agg=[]
    for b in 'ABCD':
        br=[s for s in rows if s['motor']==b];rs=[s for s in br if s['grupo']!='X'];result[b]['por_rol']={role:metrics(s for s in rs if s['rol']==role) for role in ROLES};result[b]['ejecuciones']=len(cases);result[b]['casos_incompletos']=[k for k,r in result[b]['cases'].items() if not r['complete_return']]
        for kind,keys in [('grupo',['grupo']),('duracion',['duracion_s']),('magnitud',['magnitud']),('retardo_firmado',['d_real']),('canal',['canal']),('grupo_duracion',['grupo','duracion_s']),('cruce',['grupo','duracion_s','magnitud','canal'])]:
            groups=collections.defaultdict(list)
            for s in rs:
                group=tuple(abs(s['d_real']) if k=='magnitud' else s[k] for k in keys);groups[(s['rol'],group)].append(s)
            for (role,group),items in sorted(groups.items()):agg.append(dict(motor=b,rol=role,estrato=kind,valor=':'.join(map(str,group)),**metrics(items)))
    save(OUT/'RESULTADOS_DETECTORES.json',dict(schema='6B.1',unidad='caso/motor con dos roles; cada offset único se confronta con dos canales. En el CSV null es campo vacío.',fuentes='source_hashes.json',entradas='signals_manifest.json',oraculo='evidence/oraculo.json',matriz='MATRIZ_RESULTADOS.csv',desglose='DESGLOSE_METRICAS.csv',motores=result));write_csv(OUT/'MATRIZ_RESULTADOS.csv',rows);write_csv(OUT/'DESGLOSE_METRICAS.csv',agg)
    (OUT/'ERRORES_Y_EXCEPCIONES.log').write_text('6B | Registro de incidencias. Las clases MISALIGNED, WARNING, ID y guarda (incluso sin excepción) están íntegras en la matriz y nativos.\n\n'+'\n'.join(log),encoding='utf-8');print(len(rows),'filas;',len(agg),'estratos;',len(log),'entradas de incidencias.')

if __name__=='__main__':analyze()
