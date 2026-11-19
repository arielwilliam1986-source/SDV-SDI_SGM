"""Reconstruct latent uncorrelated background from the 6C recipe; do not call a motor."""
from common import *
import numpy as np
from scipy.signal import lfilter,correlate
from scipy.io import wavfile

def latent(seed,n):
    rng=np.random.Generator(np.random.PCG64(seed));out=[]
    for channel in range(4):
        v=np.zeros(n,'f4')
        for _ in range(11):
            size=min(int(rng.integers(517,1701)),n//12);start=int(rng.uniform(.29*n,.71*n));pole=rng.uniform(.15,.86);z=lfilter([1,.19],[1,-pole],rng.normal(size=size));v[start:start+size]+=(.12*np.hanning(size)*z/np.max(np.abs(z))).astype('f4')
        out.append(v)
    return np.stack(out[:2],axis=1),np.stack(out[2:],axis=1)

def main():
    results={}
    for c in load(C6/'evidence/reserva_manifest.json')['cases']:
        if c['id'] not in REPLICAS:continue
        data={k:wavfile.read(WORK/'wav'/(h+'.wav'))[1] for k,h in c['files'].items()};v,bg=latent(c['seed'],c['frames']);check(np.array_equal(v,data['vocal0']) and np.array_equal(v,data['vocal']),c['id']);rows={}
        for j,ch in enumerate('LR'):
            g=v[:,j];rep=data['instrumental0'][:,j].astype('f8')-bg[:,j];corr=correlate(rep,g.astype('f8'),mode='full',method='fft');r=int(np.argmax(abs(corr))-(len(g)-1));y=np.roll(g,r);y[:r]=0
            a=float(np.dot(rep,y.astype('f8'))/np.dot(y.astype('f8'),y.astype('f8')));M=data['mix'][:,j];design=np.column_stack([g,y]).astype('f8');weights,_,rank,_=np.linalg.lstsq(design,M.astype('f8')-bg[:,j],rcond=None)
            amp=round(a,5);i=(bg[:,j]+amp*y).astype('f4');mx=(g.astype('f8')+i).astype('f4');check(np.array_equal(i,data['instrumental0'][:,j]) and np.array_equal(mx,M) and r>0,c['id']);rows[ch]=dict(d_origins=[0,-r],recovered_amplitude=a,nominal_reconstruction_amplitude=amp,fit_coefficients=weights.tolist(),design_rank=int(rank),condition_number=float(np.linalg.cond(design)),joint_max_abs_error=float(np.max(abs(design@weights+bg[:,j]-M))),reconstructed_I0_and_Mix_bit_exact=True)
        results[c['id']]=dict(files=c['files'],seed=c['seed'],channels=rows,expected_V='AMBIGUOUS',expected_I='ALIGNED')
    save(EV/'verdad_doble_origen.json',results);print(results.keys())
if __name__=='__main__':main()
