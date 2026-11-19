"""Regression tests of the dossier, NOT a certification of the engines."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import EV,OUT,load,unpacked,ROLES


class Expediente(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.det={b:{r['id']:r['raw'] for r in unpacked(EV/f'det_{b}_6C.json.gz')} for b in 'BCD'};cls.gate={(r['engine'],r['id']):r for r in load(EV/'cli_index.json')}

    def test_replicas_sin_certificar(self):
        truth=load(EV/'verdad_doble_origen.json')
        for b,d in self.det.items():
            for id,expected in [('R_dos_origenes',[0,None]),('R_replica_dominante',[-3217,-3217])]:
                self.assertTrue(all(ch['d_origins']==[0,-3217] and ch['design_rank']==2 for ch in truth[id]['channels'].values()));self.assertEqual([d[id]['vocal']['channels'][ch]['guide_delay_samples'] for ch in 'LR'],expected)
                self.assertEqual(d[id]['instrumental']['estimated_offset_samples'],0)
    def test_swap_visible_in_all_windows(self):
        for d in self.det.values():
            for before,after in [('distintos','swap'),('soloL','soloR')]:
                for role in ROLES:
                    v=d[before][role];w=d[after][role];self.assertEqual(v['channels']['L'],w['channels']['R']);self.assertEqual(v['channels']['R'],w['channels']['L'])
    def test_modify_only_right_preserves_left(self):self.assertEqual(load(EV/'extra_index.json')['metamorphic_L'],dict.fromkeys('BCD',True))
    def test_zero_opposed_signs_is_not_signed_agreement(self):
        for d in self.det.values():
            v=d['invL']['vocal'];self.assertLess(v['channels']['L']['correlation_peak'],0);self.assertGreater(v['channels']['R']['correlation_peak'],0);self.assertEqual(v['guide_delay_samples'],-827);self.assertIsNone(v['correlation_peak']);self.assertEqual(v['action']['applied_shift_samples'],0)
    def test_error_dominates_and_is_not_a_permit(self):
        for b,d in self.det.items():
            v=d['invalida_L']['vocal'];self.assertEqual((v['classification'],v['channels']['R']['guide_delay_samples']),('ERROR',0));self.assertIsNone(v['estimated_offset_samples']);self.assertFalse(self.gate[b,'invalida_L/override']['reached_dsp']);self.assertFalse(self.gate[b,'fault_race/override']['reached_scale'])
    def test_opposite_warnings_and_late_error(self):
        for r in unpacked(EV/'bordes_cli.json.gz'):
            z=r['summary'];i=z['id']
            if i.startswith('opposite_warnings'):
                v=z['roles'][0];self.assertEqual(v['channels'],dict.fromkeys('LR','WARNING'));self.assertEqual((v['state'],v['k']),('AMBIGUOUS',None));self.assertEqual(z['reached_dsp'],i.endswith('override'))
            if i.startswith('six_last_ERROR'):self.assertEqual(len(z['roles']),12);self.assertEqual(z['exit'],1);self.assertFalse(z['reached_dsp'])
    def test_holdout_strata_not_pooled(self):
        s=load(EV/'desglose.json');oracle=load(EV/'oraculo_pcm.json');self.assertEqual(oracle['unique_wav'],110)
        for b,v in s.items():
            self.assertEqual(v['RESERVA']['outcomes']['EXACTO'],79);self.assertEqual(v['RESERVA']['outcomes']['ATRIBUCION_SIN_UNICIDAD'],7 if b=='C' else 9);self.assertEqual(set(v['RESERVA']['false_permit']),{'rep_igual','rep_035','rival_R'})
            self.assertEqual(v['A_6C']['outcomes']['ATRIBUCION_SIN_UNICIDAD'],3)
    def test_overrides_are_not_an_overall_pass(self):
        for id in ('M','soloL','circular','R_dos_origenes'):
            self.assertFalse(self.gate['D',id+'/default']['reached_dsp']);self.assertEqual((self.gate['D',id+'/override']['exit'],self.gate['D',id+'/override']['overall']),(0,'fail'))
        self.assertEqual(self.gate['D','W/default']['overall'],'pass_with_warnings');self.assertEqual(self.gate['D','rep_035/default']['overall'],'pass') # reproduces false admission, not a pass of the oracle
    def test_crest_failure_is_not_compared_pcm(self):
        rows=load(EV/'dsp_index.json');self.assertEqual(sum(r['complete'] for r in rows),18)
        for z in [r for r in rows if not r['complete']]:self.assertEqual(z['engine'],'D');self.assertEqual(z['validation_calls'],[0,0]);self.assertEqual(z['exits'],[2,2]);self.assertNotIn('pcm',z);self.assertTrue(z['both_reached_dsp'])
    def test_missing_subrecord_is_a_counterexample_not_a_cli_run(self):
        a=load(EV/'extra_index.json')['aggregator'];self.assertEqual(a['missing_role'],'fail');self.assertEqual(a['missing_R'],'pass');self.assertEqual(a['inconsistent_R'],'pass');self.assertEqual(a['reported_error'],'fail')
    def test_large_is_only_dry_run(self):
        r=load(EV/'resources_index.json')['cli'];self.assertEqual(len(r),36);big=[x for x in r if x['bytes_each']>1024**3];self.assertEqual(len(big),6);self.assertTrue(all(x['mode']=='dry_run' and x['wavs']==0 and x['final_analyses']==0 for x in big))
if __name__=='__main__':unittest.main()
