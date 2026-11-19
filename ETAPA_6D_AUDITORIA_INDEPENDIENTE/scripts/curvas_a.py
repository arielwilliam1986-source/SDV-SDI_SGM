"""Re-open *every* native bin for the selected priority-A condition, not just top-five.
Streams CSV to stdout; --picos enumerates all local maxima eligible in the selected band.
"""
import argparse
import csv
from common import *
import numpy as np


def read_curve(z):
    with np.load(OUT/z['file'],allow_pickle=False) as data:
        off=z['lo']-int(data['lo']);check(off>=0 and off+z['physical_bins']<=len(data['valid']),z);s=slice(off,off+z['physical_bins']);arrays=tuple(data[k][s] for k in ('valid','rho','strength'))
    for a,k in zip(arrays,('valid_sha','rho_sha','strength_sha')):check(sha(a.tobytes())==z[k],(k,z['file']))
    return arrays

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('motor',choices=list('BCD'));p.add_argument('case',choices=REPLICAS);p.add_argument('role',choices=ROLES);p.add_argument('channel',choices=list('LR'));p.add_argument('band',choices=['wave','env']);p.add_argument('--picos',action='store_true');args=p.parse_args();r=next(v for v in unpacked(EV/f'det_{args.motor}_6C.json.gz') if v['id']==args.case);z,= [v for v in r['curves'] if (v['role'],v['ch'],v['band'])==(args.role,args.channel,args.band)];win,=r['raw'][args.role]['channels'][args.channel]['windows'];ok,rho,score=read_curve(z);eligible=ok&(score>0) if args.band=='wave' else ok&(rho>0);peak=eligible&np.r_[True,(~eligible[:-1])|(score[1:]>=score[:-1])]&np.r_[(~eligible[1:])|(score[:-1]>=score[1:]),True];step=8 if args.band=='env' else 1;na,nb=win['frames_M']//step,win['frames_G']//step
    w=csv.writer(sys.stdout);w.writerow(['q_bin','q_samples','k_samples','d_samples','overlap_bins','valid','eligible_peak','rho_signed','strength']);
    for j in np.flatnonzero(peak) if args.picos else range(len(ok)):
        q=z['lo']+j;k=q*step+win['tM']-win['tG'];w.writerow([q,q*step,k,-k,min(na,nb+q)-max(0,q),int(ok[j]),int(peak[j]),rho[j] if ok[j] else '',score[j] if ok[j] else ''])
if __name__=='__main__':main()
