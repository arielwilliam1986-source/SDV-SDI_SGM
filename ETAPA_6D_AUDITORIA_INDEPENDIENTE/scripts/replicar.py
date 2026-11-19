"""Recreate independent bank, component truth and derived rows in a separate, temporary output root."""
import shutil
import tempfile
from common import *

def main():
    cmds=[];hashes={}
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);env=dict(os.environ,SDV6D_OUT=str(root));scripts=HERE/'scripts'
        for name in ('preflight','bank','origenes','oraculo_pcm','consolidar'):
            if name=='consolidar':
                for f in [*EV.glob('det_*.json.gz'),EV/'cli_index.json']:shutil.copyfile(f,root/'evidence'/f.name)
            cmd=[sys.executable,'-Bu',str(scripts/(name+'.py'))];r=subprocess.run(cmd,env=env,capture_output=True,text=True);cmds.append(dict(argv=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr));check(r.returncode==0,r.stderr)
        for f in ('source_hashes.json','experimental_hashes.json','evidence/preflight.json','BANCO_RESERVADO_MANIFEST.json','evidence/banco_6d.tar.xz','evidence/verdad_doble_origen.json','evidence/oraculo_pcm.json','MATRIZ_RESULTADOS_6D.csv','evidence/desglose.json','evidence/cli_por_caso.csv','evidence/candidatos_A.csv'):
            h=digest(root/f);check(h==digest(OUT/f),f);hashes[f]=h
    save(EV/'reproduccion_limpia.json',dict(scope='new output root: bank, truth and derivations; native engine timing NOT replayed here',argv_results=cmds,identical_sha256=hashes));print(len(hashes),'productos idénticos')
if __name__=='__main__':main()
