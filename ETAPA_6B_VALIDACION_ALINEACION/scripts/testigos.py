"""Testigos enlazados: diagnóstico auxiliar sobre PCM, más evidencia histórica del consumidor. Sin motor."""
import io
import tarfile
from base import S5, PRE, ROLES, OUT, EVID, blob, sha, np, sf, json, load, save


def rho(x,g,k):
    l,h=max(0,k),min(len(x),len(g)+k)
    if h-l<2:return None
    a,b=x[l:h],g[l-k:h-k];a=a-a.mean();b=b-b.mean();den=np.sqrt((a@a)*(b@b));return float(a@b/den) if den>0 else None


def historical():
    p='S5_STEREO_VALIDATION/';ref=json.loads(blob(PRE,p+'AUDIT_INDEPENDIENTE/VERIFICACION_INTEGRIDAD.json'))['matriz']['corridas'];hashes={name:h for h,name in (l.split('  ',1) for l in blob(S5,p+'hashes/MIEMBROS_SHA256.txt').decode().splitlines())};cases={}
    for key,name in [('B/S7_per_channel','s5_b_hardened'),('D/S5_shared','s5_d_mqr')]:
        b,c=key.split('/');ix=ref[key];rp=p+'results/'+name+'.json';r=next(r for r in json.loads(blob(S5,rp))['runs'] if r['id']==c);pkg=p+'evidence/S5-'+b+'.tar.xz';arc=blob(S5,pkg)
        paths=[ix['informe_nativo'],ix['mascara'],*ix['WAV'].values()];verified={}
        with tarfile.open(fileobj=io.BytesIO(arc),mode='r|xz') as t:
            for m in t:
                if m.name in paths:
                    data=t.extractfile(m).read();assert sha(data)==hashes[m.name];verified[m.name]=hashes[m.name]
                    if m.name==ix['informe_nativo']:native=json.loads(data)
        assert set(verified)==set(paths)
        cases[key]=dict(commit=S5,paquete=pkg,miembros=verified,indice=rp,exit=r['engine_exit'],estado=r['status'],allow_misaligned=r['parsed_options']['allow_misaligned'],correct_alignment=r['parsed_options'].get('correct_alignment'),forma_mascara_real=r['observation']['shape'],roles=native.get('alignment_analysis',native.get('alignment')),resumen_MQR=(native.get('validation_status') if b=='D' else None))
    return cases


def main():
    man=load(OUT/'signals_manifest.json');com=load(OUT/'RESULTADOS_DETECTORES.json')['motores'];cases={c['id']:c for c in man['cases']};target=[('C_archivo_S2_4s','instrumental'),('C_archivo_S5_4s','instrumental'),('E_invertida_1103_4s','vocal'),('B_solo_R_4s','vocal')];keys={cases[i]['files'][k] for i,role in target for k in ('mix',role)};pcm={}
    with tarfile.open(EVID/'wav_4s.tar.xz','r|xz') as t:
        for m in t:
            h=m.name.removesuffix('.wav')
            if h in keys:
                raw=t.extractfile(m).read();assert sha(raw)==h;pcm[h]=sf.read(io.BytesIO(raw),always_2d=True,dtype='float64')[0]
    tests=[]
    for i,role in target:
        c=cases[i];rr=com['B']['cases'][i]['roles'][role];k=rr['k_nativo'];x,g=[pcm[c['files'][j]] for j in ('mix',role)]
        def pair(x,g,ktrue):return dict(en_cero=rho(x,g,0),en_candidato_fino_B=rho(x,g,k),en_lag_construccion=None if ktrue is None else rho(x,g,ktrue))
        mid=pair(x.mean(1),g.mean(1),None);assert abs(mid['en_candidato_fino_B']-rr['score'])<1e-12
        tests.append(dict(caso=i,rol=role,sha256_Mix=c['files']['mix'],sha256_guia=c['files'][role],k_nativo_B=k,mid_solo_explicacion=mid,L=pair(x[:,0],g[:,0],-c['delays'][role][0]),R=pair(x[:,1],g[:,1],-c['delays'][role][1])))
    save(EVID/'testigos.json',dict(nota='Nuevos contrastes Pearson sobre WAV existentes; no son retornos adicionales del detector. S5 se consulta para el consumidor real sin volver a separar.',ondas=tests,flujo_historico=historical()))

if __name__=='__main__':main()
