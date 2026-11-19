"""Diagnostic controls outside the frozen bank: an inventory is not a scalar and a scalar is not a permit."""
import copy
import tempfile
from common import *
from cli import invoke,from_case
from detect import cases
from scipy.io import wavfile
import numpy as np


def main():
    new={c['id']:c for c in cases()};base=from_case(new['Z']);records=[]
    with tempfile.TemporaryDirectory(dir=WORK) as td:
        root=Path(td);pa=base['pairs'][0];rate,x=wavfile.read(pa['vocal_guide']);y=np.zeros_like(x);y[219:,0]=x[:-219,0];y[:-219,1]=x[219:,1];path=root/'opuestos.wav';wavfile.write(path,rate,y)
        six=copy.deepcopy(base);six['pairs']=[dict(pa,pair_id='P%02d'%(i+1)) for i in range(6)];bad=root/'bad_R.wav';y=x.copy();y[900,1]=np.nan;wavfile.write(bad,rate,y);six['pairs'][-1].update(vocal_guide=str(bad),vocal_path=str(bad))
        opposite=copy.deepcopy(base);opposite['pairs'][0].update(vocal_path=str(path),vocal_guide=str(path));missing=copy.deepcopy(base);del missing['pairs'][0]['instrumental_guide'],missing['pairs'][0]['instrumental_path'];dup=dict(base,pairs=[pa,dict(pa)])
        designs=[('inventory_empty',dict(base,pairs=[])),('missing_guide_field',missing),('duplicate_id',dup),('six_last_ERROR',six),('opposite_warnings',opposite)]
        for b in 'BCD':
            for id,s in designs:
                for perm in ([False,True] if id in ('six_last_ERROR','opposite_warnings') else [False]):
                    row,rec=invoke(b,id+('/override' if perm else '/default'),s,root/(b+id+str(perm)),extra=['--allow-misaligned'] if perm else []);records.append(rec)
                if id=='duplicate_id':
                    row,rec=invoke(b,id+'/original',s,root/(b+'origdup'),orig=True,extra=['--allow-misaligned']);records.append(rec)
    packed(EV/'bordes_cli.json.gz',records);print('boundary cases',len(records))
if __name__=='__main__':main()
