"""Join by input identity. Original returns are role scalars; never fabricate original L/R records."""
import csv
from collections import Counter
from common import *
from detect import cases


def sev(d):return 'ALIGNED' if abs(d)<=1 else 'WARNING' if abs(d)<=441 else 'MISALIGNED'

def expected(t):
    ds=[v['d'] for v in t.values()];s={v['state'] for v in t.values()}
    if 'ERROR' in s:return 'ERROR',None
    if None not in ds and ds[0]==ds[1]:return sev(ds[0]),-ds[0]
    if 'MISALIGNED' in s:return 'MISALIGNED',None
    if 'AMBIGUOUS' in s or None not in ds:return 'AMBIGUOUS',None
    return 'INSUFFICIENT_SIGNAL',None

def outcome(x,g):
    d=x['guide_delay_samples'];s=x['classification']
    if g['d'] is not None:
        if d is None:return 'ABSTENCION_CON_MARCA'
        return 'EXACTO' if d==g['d'] and s==g['state'] else 'MEDICION_ERRONEA'
    if d is not None:return 'ATRIBUCION_SIN_UNICIDAD' if g['state']=='AMBIGUOUS' else 'NUMERO_SIN_SOPORTE'
    return 'ABSTENCION_CORRECTA' if s==g['state'] else 'CLASE_INCORRECTA'

def table(p,rows):
    cols=list(dict.fromkeys(k for v in rows for k in v));p.parent.mkdir(exist_ok=True,parents=True)
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,lineterminator='\n');w.writeheader()
        for v in rows:w.writerow({k:json.dumps(x,ensure_ascii=False,separators=(',',':')) if isinstance(x,(dict,list,tuple)) else x for k,x in v.items()})

def main():
    plan={c['id']:c for c in cases()};cl={(r['engine'],r['id']):r for r in load(EV/'cli_index.json')};rows=[];bycase=[];A=[];summary={}
    for b in 'BCD':
        e={x['id']:x for x in unpacked(EV/f'det_{b}_6C.json.gz')};o={x['id']:x for x in unpacked(EV/f'det_{b}_original.json.gz')};check(e.keys()==o.keys()==plan.keys(),b)
        for id,c in plan.items():
            r=e[id];z=o[id];g=c['truth'];cr=cl.get((b,id+'/default'));expected_roles={v:expected(g[v])[0] for v in ROLES};truth_gate='VETO' if set(expected_roles.values())-{'ALIGNED','WARNING'} else 'ADMISIBLE';check(z['files']==r['files']=={k:c['files'][k] for k in ('mix',*ROLES)},id)
            case=dict(motor=b,id=id,particion=c['partition'],verdad_por_rol=expected_roles,estados_publicados={v:r['raw'][v]['classification'] for v in ROLES},admision_esperada=truth_gate,cli_default_exit=cr['exit'] if cr else None,dsp_real=cr['reached_dsp'] if cr else None,dictamen_cli_D=cr['overall'] if cr else None)
            bycase.append(case)
            for j,role in enumerate(ROLES):
                s=r['raw'][role];base=z['raw'][role];t,kref=expected(g[role]);ds=[v['d'] for v in g[role].values()];ks=base.get('estimated_offset_samples');og=None if ks is None else -ks
                if cr:check(cr['roles'][j]['state']==s['classification'] and cr['roles'][j]['k']==s['estimated_offset_samples'],(id,role,'CLI vs detector'))
                for ch in 'LR':
                    u=s['channels'][ch];label=g[role][ch];w=u['windows'];d=label['d'];diff=None if None in ds else ds[1]-ds[0];oldexact=None if d is None else og==d;measured=u['guide_delay_samples'];y=outcome(u,label)
                    row=dict(particion=c['partition'],id=id,motor=b,rol=role,canal=ch,sha_mix=r['files']['mix'],sha_guia=r['files'][role],sha_original=z['sha256'],sha_6c=r['sha256'],d_verdad=d,alternativas_d=label['alternatives'],clase_verdad=label['state'],clase_verdad_rol=t,k_comun_verdad=kref,delta_RL_verdad=diff,
                        k_original_escalar_rol=ks,d_original_escalar_rol=og,clase_original_rol=base['classification'],rho_original_rol=base.get('correlation_peak'),conf_original_rol=base.get('alignment_confidence'),coincidencia_numerica_original=oldexact,
                        ventanas=len(w),candidatos_k_por_ventana=[[p['k'] for p in v['candidates']] for v in w],k_mejor_por_ventana=[v.get('best',{}).get('k') for v in w],rho_mejor_por_ventana=[v.get('best',{}).get('rho') for v in w],solape_mejor_por_ventana=[v.get('best',{}).get('overlap') for v in w],brechas=[v.get('relative_peak_gap') for v in w],k_publicado=u['estimated_offset_samples'],d_publicado=measured,rho_publicada=u['correlation_peak'],conf_publicada=u['alignment_confidence'],clase_canal=u['classification'],razon_canal=u['reason'],error_canal=u.get('error'),delta_RL_publicado=s['guide_delay_R_minus_L'],k_comun=s['estimated_offset_samples'],clase_rol=s['classification'],razon_rol=s['reason'],rho_rol=s['correlation_peak'],conf_rol=s['alignment_confidence'],
                        resultado_canal=y,error_d_muestras=measured-d if d is not None and measured is not None else None,rol_acierta_clase_y_k=(s['classification'],s['estimated_offset_samples'])==(t,kref),cli_default_exit=case['cli_default_exit'],cli_default_llego_DSP=case['dsp_real'],cli_default_global_D=case['dictamen_cli_D'],veto_fisico_del_caso=(truth_gate=='VETO'),accion=s['action'],primario=f'evidence/det_{b}_6C.json.gz:{id}/{role}/{ch}')
                    rows.append(row)
                    if id not in REPLICAS:continue
                    for v in w:
                        h=v['tG']-v['tM'];strength=v['best']['strength'];best_rho=v['best']['rho']
                        for typ,pts in [('propuesta_onda',v['candidates']),('semilla_envolvente',v['envelope'])]:
                            for p in pts:
                                q=p['q']; l=max(0,q);right=min(v['frames_M'],v['frames_G']+q)
                                A.append(dict(motor=b,id=id,rol=role,canal=ch,tipo=typ,origen=p.get('origin',['env']),q=q,k=p['k'],d=h-q,rho=p['rho'],strength=p.get('strength'),M=p.get('M'),G=p.get('G'),solape_frames_onda=right-l,delta_rho_onda=best_rho-p['rho'] if typ=='propuesta_onda' else None,delta_strength= strength-p['strength'] if 'strength' in p else None,k_refinado=p.get('refined_k'),brecha_rel_1_2=v['relative_peak_gap'],confianza_decision=u['alignment_confidence'],d_publicado=measured,clase=u['classification'],verdad=label['state']))
        summary[b]={}
        for partition in ['6B','A_6C','DEV','RESERVA']:
            rs=[v for v in rows if v['motor']==b and v['particion']==partition];cs=[v for v in bycase if v['motor']==b and v['particion']==partition];labels=Counter(v['clase_verdad'] for v in rs);counts=Counter(v['resultado_canal'] for v in rs)
            summary[b][partition]=dict(n=len(rs),labels=labels,outcomes=counts,
                old_scalar_matches=sum(v['coincidencia_numerica_original'] is True for v in rs),old_matches_identity=sum(v['coincidencia_numerica_original'] is True and 'IDENTITY' in v['clase_original_rol'] for v in rs),
                gain_numerical=sum(v['coincidencia_numerica_original'] is False and v['resultado_canal']=='EXACTO' for v in rs),loss_numerical=[v['id']+'/'+v['rol']+'/'+v['canal'] for v in rs if v['coincidencia_numerica_original'] is True and v['resultado_canal']!='EXACTO'],
                false_permit=[v['id'] for v in cs if v['admision_esperada']=='VETO' and v['dsp_real'] is True],false_veto=[v['id'] for v in cs if v['admision_esperada']=='ADMISIBLE' and v['dsp_real'] is False],misattributions=[v['id']+'/'+v['rol']+'/'+v['canal'] for v in rs if v['resultado_canal']=='ATRIBUCION_SIN_UNICIDAD'])
    table(OUT/'MATRIZ_RESULTADOS_6D.csv',rows);table(EV/'cli_por_caso.csv',bycase);table(EV/'candidatos_A.csv',A);save(EV/'desglose.json',summary);print(len(rows),'filas',len(bycase),'contextos',len(A),'propuestas/semillas A')
if __name__=='__main__':main()
