"""Directly contrast the S7 pre-DSP veto and original post-probe error path, separately from DSP parity."""
import shutil
import tempfile
from common import *
from cli import invoke,from_case
from detect import cases
from dsp import inputs


def main():
    c={v['id']:v for v in cases()};rec=[]
    with tempfile.TemporaryDirectory(dir=WORK) as td:
        root=Path(td);s=inputs('S7',c,root);cfg=['--n-fft','4096','--hop','1024','--chunk-frames','64','--consensus','confidence_weighted_mean','--power','2','--epsilon','1e-9']
        for orig in (True,False):
            _,r=invoke('D','S7/default',s,root/str(orig),orig=orig,extra=cfg);rec.append(r)
        for b in 'BCD':
            d=root/b;d.mkdir();s=from_case(c['Z']);pa=s['pairs'][0];p=d/'volatile.wav';shutil.copyfile(pa['vocal_path'],p);pa['vocal_path']=pa['vocal_guide']=str(p)
            _,r=invoke(b,'race_original/override',s,d,orig=True,extra=['--allow-misaligned'],fault=p);rec.append(r)
    packed(EV/'testigos_cli_original.json.gz',rec)
    for r in rec:
        z=r['summary'];print(z['engine'],z['original'],z['id'],z['roles'],z['exit'],z['reached_scale'],z['trace_error'] is not None)
if __name__=='__main__':main()
