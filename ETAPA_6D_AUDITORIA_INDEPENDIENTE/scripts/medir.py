"""Linux/Termux: out-of-process monitor, no engine patch, memory cap, or timing cut-off.
Usage: python medir.py LOG_DIR OUTPUT_DIR -- python ENGINE --manifest ... --out OUTPUT_DIR ...
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def sample(pid,dest):
    rec={}
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            key=line.split(':',1)[0]
            if key in ('VmRSS','RssAnon','RssFile','VmHWM','VmSwap'):rec[key+'_KiB']=int(line.split()[1])
    except (OSError,ValueError):pass
    n=0;allocated=0
    for base,_,files in os.walk(dest):
        for f in files:
            try:st=os.stat(os.path.join(base,f));n+=st.st_size;allocated+=st.st_blocks*512
            except FileNotFoundError:pass # native promotion from _partial to final
    return dict(rec,out_bytes=n,out_allocated=allocated)

def measure(cmd,log,out):
    log=Path(log);log.mkdir(parents=True,exist_ok=True);hist=[];start=time.monotonic()
    with (log/'stdout.log').open('wb') as a,(log/'stderr.log').open('wb') as b:
        proc=subprocess.Popen(cmd,stdout=a,stderr=b,stdin=subprocess.DEVNULL)
        while True:
            pid,status,usage=os.wait4(proc.pid,os.WNOHANG)
            if pid:break
            hist.append(dict(t_s=round(time.monotonic()-start,4),**sample(proc.pid,out)));time.sleep(.1)
        proc.returncode=os.waitstatus_to_exitcode(status)
    dt=time.monotonic()-start;final=sample(-1,out);rec=dict(argv=cmd,exit=proc.returncode,elapsed_s=dt,user_s=usage.ru_utime,sys_s=usage.ru_stime,ru_maxrss_KiB=usage.ru_maxrss,
        max_sampled_anon_KiB=max((r.get('RssAnon_KiB',0) for r in hist),default=0),max_output_bytes=max([r['out_bytes'] for r in hist]+[final['out_bytes']]),final_output_bytes=final['out_bytes'],sample_interval_s=.1,samples=hist)
    (log/'measure.json').write_text(json.dumps(rec,indent=2)+'\n');return rec
if __name__=='__main__':
    if len(sys.argv)<6 or sys.argv[3]!='--':sys.exit(__doc__)
    sys.exit(measure(sys.argv[4:],Path(sys.argv[1]),Path(sys.argv[2]))['exit'])
