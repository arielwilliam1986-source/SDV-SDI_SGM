import contextlib
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from comun import *
import numpy as np
from scipy.io import wavfile


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mods={b:module(b) for b in 'BCD'}

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)
        self.rng=np.random.default_rng(60231)

    def audio(self,name,x,sr=SR):
        p=self.p/(name+'.wav');wavfile.write(p,sr,x.astype('f4'));return str(p)

    def record(self,m,a,b):
        return m.analyze_alignment(m.probe_file(self.audio('x',a),'mix'),m.probe_file(self.audio('g',b),'vocal'))

    def test_curve_vs_literal_overlap_both_signs(self):
        for m in self.mods.values():
            a=self.rng.normal(size=311)+.04;b=self.rng.normal(size=239)-.07
            lo,valid,rho,score=m._lag_curve(a,b,-90,172,83)
            for j in range(len(valid)):
                k=lo+j;l=max(k,0);r=min(len(a),len(b)+k);x=a[l:r];y=b[l-k:r-k]
                self.assertTrue(valid[j]);self.assertAlmostEqual(rho[j],np.corrcoef(x,y)[0,1],places=12)
                self.assertAlmostEqual(score[j],abs(np.dot(x-x.mean(),y-y.mean()))/(np.linalg.norm(a-a.mean())*np.linalg.norm(b-b.mean())),places=12)
            self.assertFalse(m._lag_curve(a,b*0+2.,-90,172,83)[1].any())

    def test_stereo_sign_swap_and_no_common(self):
        a=self.rng.normal(0,.05,(17001,2)); b=np.column_stack((np.roll(a[:,0],537),-np.roll(a[:,1],-223)))
        for m in self.mods.values():
            for x,g,truth in ((a,b,(537,-223)),(a[:,::-1],b[:,::-1],(-223,537))):
                r=self.record(m,x,g);self.assertEqual(r['classification'],'MISALIGNED');self.assertIsNone(r['estimated_offset_samples'])
                self.assertEqual(r['guide_delay_R_minus_L'],truth[1]-truth[0]);self.assertEqual(r['action']['applied_shift_samples'],0)
                for d,ch in zip(truth,'LR'):
                    rec=r['channels'][ch]; self.assertEqual(rec['estimated_offset_samples'],-d);self.assertGreater(rec['alignment_confidence'],0)
                    self.assertEqual(np.sign(rec['correlation_peak']), -1 if d==-223 else 1)

    def test_no_fabricated_channels_or_identity(self):
        a=self.rng.normal(size=(9000,2));bad=a.copy();bad[200,0]=np.nan
        for m in self.mods.values():
            for x,g in ((a,np.zeros_like(a)),(a,a*0.+.1),(a[:3000],a[:3000])):
                r=self.record(m,x,g);self.assertEqual(r['classification'],'INSUFFICIENT_SIGNAL');self.assertIsNone(r['alignment_confidence']);self.assertIsNone(r['estimated_offset_ms']);m._alignment_line(r)
            r=self.record(m,a,bad);self.assertEqual(r['classification'],'ERROR');self.assertEqual(r['channels']['R']['guide_delay_samples'],0);self.assertIn('Non-finite',r['error'])
            r=self.record(m,a,a[:,0]);self.assertFalse(r['channels']);self.assertEqual(r['classification'],'INSUFFICIENT_SIGNAL')
            r=self.record(m,a[:,1],a[:,1]);self.assertEqual(list(r['channels']),['M']);self.assertEqual(r['estimated_offset_samples'],0)

    def test_shift_request_and_read_failure_block_actual_cli(self):
        for b,m in self.mods.items():
            x=self.rng.normal(0,.05,(16001,2));mx=self.audio('mix',x);v=self.audio('v',x);i=self.audio('i',x)
            manifest=self.p/'input.json';save(manifest,dict(mix_original=mx,pairs=[dict(pair_id='P1',family='test',variant='unit',configuration='none',vocal_path=v,instrumental_path=i,vocal_guide=v,instrumental_guide=i)]))
            out=self.p/'forbidden';argv=['--manifest',str(manifest),'--out',str(out),'--mode','full_processing','--allow-misaligned']
            with contextlib.redirect_stdout(io.StringIO()) as log:
                if b!='D':
                    self.assertEqual(m.main([*argv,'--correct-alignment']),m.EXIT_VALIDATION);self.assertIn('no está autorizado',log.getvalue())
                # Real race AFTER successful native preflight, on a disposable test WAV only.
                def race(frame,event,arg):
                    if event=='call' and frame.f_code is m.analyze_alignment.__code__ and Path(v).exists():Path(v).unlink()
                sys.setprofile(race)
                try:code=m.main(argv)
                finally:sys.setprofile(None)
                self.assertEqual(code,m.EXIT_VALIDATION);self.assertIn('ERROR',log.getvalue());self.assertFalse(list(out.rglob('*.wav')))

    def test_ambiguity_default_gate(self):
        t=np.tile(self.rng.normal(0,.03,(59,2)),(420,1));mfile=self.audio('mix',t);v=self.audio('v',t);i=self.audio('i',t)
        p=self.p/'manifest.json';save(p,dict(mix_original=mfile,pairs=[dict(pair_id='p',family='test',variant='v',configuration='test',vocal_guide=v,vocal_path=v,instrumental_guide=i,instrumental_path=i)]))
        for m in self.mods.values():
            with contextlib.redirect_stdout(io.StringIO()) as log:code=m.main(['--manifest',str(p),'--mode','full_processing','--out',str(self.p/'out')])
            self.assertEqual(code,m.EXIT_VALIDATION);self.assertIn('AMBIGUOUS',log.getvalue());self.assertFalse(list((self.p/'out').rglob('*.wav')))

    def test_mqr_summary_fails_closed(self):
        m=self.mods['D'];info=SimpleNamespace(valid=True,sample_rate=SR,errors=[],warnings=[]); p=SimpleNamespace(pair_id='p',vocal=info,instrumental=info)
        def make(role,cls):
            return dict(role=role,pair_id='p',classification=cls,estimated_offset_samples=0 if cls=='ALIGNED' else 2,
                        alignment_confidence=.65,channels={'L':dict(classification=cls),'R':dict(classification=cls)})
        a=make('vocal','ALIGNED');b=make('instrumental','ALIGNED')
        def validate(recs,full=False,**kw):
            return m.build_validation_status(dict(mix_info=info,pairs=[p],alignment=recs,**kw),SimpleNamespace(mode=m.MODE_FULL_PROCESSING if full else m.MODE_ANALYSIS_ONLY))['overall']
        self.assertEqual(validate([a,b]),'pass'); self.assertEqual(validate([a,make('instrumental','WARNING')]),'pass_with_warnings')
        for s in ('MISALIGNED','AMBIGUOUS','INSUFFICIENT_SIGNAL','ERROR','pass','other'):
            self.assertEqual(validate([a,make('instrumental',s)],misalignment_user_authorized=True),'fail')
        for broken in ([a],[a,a],[a,dict(b,error='read')],[a,dict(b,alignment_confidence=0)],[a,dict(b,estimated_offset_samples=None)]):self.assertEqual(validate(broken),'fail')
        self.assertEqual(validate([a,b],full=True),'fail');self.assertEqual(validate([a,b],post_wav_validation={'status':'length_mismatch'}),'fail');self.assertEqual(validate([a,b],errors=['critical']),'fail')
        info.valid=False;self.assertEqual(validate([a,b]),'fail')

if __name__=='__main__':unittest.main(verbosity=2)
