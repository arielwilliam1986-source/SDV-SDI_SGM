"""Auditoría sin importar motores. Ni el CSV ni las clases externas son oráculo para recalcular el lag."""
import argparse
import csv
import io
import json
import tarfile
from pathlib import Path
from scipy.io import wavfile
from base import OUT, EVID, SR, S5, ROLES, blob, digest, load, save, sha, sources, np, sf
from generar import make,plan
from ejecutar import cases_with_fault


def check_pcm(man):
    ix={x['id']:x for x in man['cases']};checks=0;seen=set()
    for c in plan():
        stored=ix[c['id']];assert all(stored[k]==v for k,v in c.items());a,tags,o=make(c);assert tags==stored['tags']
        for key,data in a.items():
            if key.rstrip('0') in o:raw=o[key.rstrip('0')][1]
            else:
                bio=io.BytesIO();wavfile.write(bio,SR,data);raw=bio.getvalue()
            h=sha(raw);assert h==stored['files'][key];seen.add(h);checks+=1
    assert len(ix)==len(plan()) and seen==set(man['wavs']);return dict(casos=len(ix),referencias_WAV_recreadas=checks,sha_distintos=len(seen),discrepancias=0)


def check_final(man):
    src=sources();assert src==load(OUT/'source_hashes.json');out=load(OUT/'RESULTADOS_DETECTORES.json')['motores'];proof=load(EVID/'oraculo.json');cs={c['id']:c for c in cases_with_fault(man)};assert set(proof['cases'])==set(cs);ref1={name:h for h,name in (l.split('  ',1) for l in blob(S5,'S5_STEREO_VALIDATION/hashes/MIEMBROS_SHA256.txt').decode().splitlines())};assert all(ref1[path]==c['files'][k] for c in cs.values() for k,path in c.get('s5_members',{}).items())
    for ar in man['archives']:assert sha((OUT/ar['path']).read_bytes())==ar['sha256'];
    with (OUT/'MATRIZ_RESULTADOS.csv').open(newline='') as f:rs=list(csv.DictReader(f,strict=True));mx={(r['motor'],r['caso'],r['rol'],r['canal']):r for r in rs}; assert len(rs)==len(mx)==len(cs)*16
    qa={};tot=0;ncal=0;er=0
    for b in 'ABCD':
        audio_fail=[];error_controls=[];role_missing=[];nr=0;n_calls=0;nr_class=0
        seen=set()
        with (EVID/f'{b}.jsonl').open() as f:
            for line,s in enumerate(f,1):
                p=json.loads(s);r=p['record'];cid=r['case'];c=cs[cid];assert cid not in seen and r['id']==b+'/'+cid;seen.add(cid);rr=out[b]['cases'][cid];assert digest(r)==p['sha256']==rr['record_sha256'] and rr['raw']==f'evidence/{b}.jsonl:{line}' and r['source_sha256']==src['motores'][b]['sha256'];assert r['sha256_resultado_nativo']==rr['native_sha256']==digest([q['raw'] for q in r['calls']]);assert not r['actions_observed'] and not r['observer_errors'] and not r['polarity_correction_attempted'] and not r['alignment_shift_attempted'] and not r['separation_started'];n_calls+=len(r['calls']);nr+=1
                if not r['complete_return']:(error_controls if c['group']=='X' else audio_fail).append(cid)
                for j,role in enumerate(ROLES):
                    q=next((q for q in r['calls'] if role in q['roles']),{});raw=q.get('raw') or {};t=q.get('trace') or {};rec=raw.get('pairs',{}).get('P1',{}).get(role,{}) if b=='A' else raw;cls=rec.get('classification');ms=rec.get('offset_ms' if b=='A' else 'estimated_offset_ms');k=rec.get('lag_samples' if b=='A' else 'estimated_offset_samples');native=round(ms*SR/1000) if ms is not None and b=='A' else (-k if k is not None else None);exc=bool(q.get('exception') or rec.get('error') or not cls);assert cls==rr['roles'][role]['estado_original'] and native==rr['roles'][role]['d_publicado']
                    if not cls:role_missing.append(cid+'/'+role)
                    else:nr_class+=1
                    if not exc:
                        if b=='A':
                            cm=1000*k/SR;assert abs(cm-rec['offset_candidate_ms'])<1e-10;guard=abs(rec['offset_candidate_ms'])>raw['max_offset_ms'] and rec['autocorr_guard']>raw['guard_autocorr'];assert cls==('PERIODIC_PEAK_IGNORED' if guard else ('MISALIGNED' if abs(rec['offset_candidate_ms'])>10 else 'ALIGNED'));assert native==(0 if guard else k)
                        else:
                            assert t['fine_score']==rec['correlation_peak']==rec['cross_correlation'] and len(t['fine_scores'])==25;h=t['tG']-t['tM'];assert t['h']==h;assert t['fine_local_integer'] in range(t['fine_start'],t['fine_end']+1);assert t['fine_local_subsample']-h==t['uncensored_global_native_subsample'];sub=t['fine_local_subsample']-h
                            if b=='C' and t['fine_score']<.15:assert (k,ms,cls)==(0,0,'ALIGNED_BY_IDENTITY')
                            else:assert k==round(sub) and cls==('ALIGNED' if abs(k)<=1 else ('WARNING' if abs(k)<=441 else 'MISALIGNED')) and abs(ms-1000*sub/SR)<1e-9
                            if b=='D':assert rec['coarse_lag_samples']==t['coarse_env_bins']*8
                    for i,ch in enumerate('LR'):
                        v=mx[b,cid,role,ch];w=proof['cases'][cid]['channel_oracle'][role][i];d=c['delays'][role][i];assert v['estado_original']==(cls or '') and v['estado_oraculo']==w['clase'] and v['sha256_mix']==c['files']['mix'] and v['sha256_guia']==(c['files'][role] or '') and v['fuente_sha256']==src['motores'][b]['sha256'] and v['sha256_retorno_nativo']==rr['native_sha256'];assert int(v['d_real'])==d and abs(float(v['d_real_ms'])-1000*d/SR)<1e-12 and not v['estimacion_nativa_por_canal'] and v['shift_intentado']=='False' and v['shift_aplicado']=='0';assert int(v['muestras'])==c['frames'] and int(v['sr'])==SR and int(v['canales'])==2 and int(v['semilla'])==c['seed']
                        expected=(native-w['lag_marca'] if w['lag_marca'] is not None and native is not None and not exc else None);assert v['error_contra_marca']==('' if expected is None else str(expected));assert v['delta_nominal']==('' if native is None else str(native-d));assert v['d_publicado_comun']==('' if native is None else str(native));assert v['error_magnitud']==('' if expected is None else str(abs(abs(native)-abs(d))));assert rr['roles'][role]['error_contra_marca_L_R'][i]==expected;tot+=1
                        if expected is not None:er+=1
                        if exc:assert v['estado_externo']=='ERROR'
                        if v['estado_externo']=='ALIGNED':assert w['lag_marca']==0 and native==0 and float(v['var_mid_G'])>0 and float(v['var_mid_M'])>0 and cls=='ALIGNED'
                if b=='D' and r['post']:
                    statuses={i['check']:i['status'] for i in r['post']['result']['items']};assert all(statuses['alignment_P1/'+ro]==rr['roles'][ro]['estado_original'] for ro in ROLES)
        assert seen==set(cs) and set(out[b]['casos_incompletos'])==set(audio_fail+error_controls);ncal+=n_calls
        for role in ROLES:
            rr=[v for v in rs if v['motor']==b and v['rol']==role and v['grupo']!='X'];known=[v for v in rr if v['d_marca']!=''];stats=out[b]['por_rol'][role];assert stats['observables']==len(known) and stats['FP_cero_MIS']==sum(v['d_marca']=='0' and v['estado_original']=='MISALIGNED' for v in known) and stats['FN_severo_aprobado']==sum(abs(int(v['d_marca']))>441 and v['estado_original'] in ('ALIGNED','ALIGNED_BY_IDENTITY') for v in known) and stats['error_signo_opuesto']==sum(int(v['d_marca'])*int(v['d_publicado_comun'])<0 for v in known if v['d_publicado_comun']!='')
        qa[b]=dict(ejecuciones=nr,llamadas_detector=n_calls,registros_con_clase=nr_class,fallos_fisicos=audio_fail,controles_tecnicos_con_fallo=error_controls,roles_sin_clase=role_missing)
    assert tot==len(rs);return dict(fuentes_y_S5='SHA y bytes verificados',matriz_filas=tot,errores_con_marca_recalculados=er,llamadas_detector=ncal,oraculo_archivos=proof['qa'],motores=qa)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--regenerar-pcm',action='store_true',help='recalcular en memoria todos los WAV, sin correr motores');args=ap.parse_args();man=load(OUT/'signals_manifest.json')
    if args.regenerar_pcm:
        q=check_pcm(man);save(EVID/'reproduccion_pcm.json',q);print(q);return
    q=check_final(man);save(EVID/'control_calidad.json',q);print(json.dumps(q,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
