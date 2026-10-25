"""Quantized provider reports carry measurement resolution, not zero-cost calls."""
from pathlib import Path
import tempfile,unittest
from board import project,provider_bridge as bridge,scheduler
ROOT=Path(__file__).resolve().parents[1]
(ROOT/'work/tests').mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(ROOT/'work/tests')
class QuotaResolution(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);project.initialize(self.root,'Fictional quota study')
    def tearDown(self):self.tmp.cleanup()
    def payload(self,used=30,reset=87400):return {'rateLimits':{'primary':{'usedPercent':used,'resetsAt':reset,'windowDurationMins':1440}}}
    def test_twenty_one_rounded_equal_observations_preserve_cost_and_interval(self):
        first=None
        for i in range(21):
            now=1000+i*10;bridge.observe_codex(self.root,self.payload(),now=now)
            row=scheduler.report(self.root,'GPT',**bridge.quota(self.root,'GPT',now=now+1))['agents']['GPT']
            if first is None:first=row
            self.assertAlmostEqual(row['cost'],.01)
        self.assertAlmostEqual(row['interval_minutes'],first['interval_minutes'])
    def test_exact_reported_zero_consumption_retains_original_ema(self):
        row=scheduler.compute_schedule({'GPT':dict(remaining=.7,reset_hours=24,before=.7,after=.7,precision='exact')},{},now=1000)['agents']['GPT']
        self.assertAlmostEqual(row['cost'],.007)
    def test_unattributed_percent_change_is_observed_separately_from_call_cost(self):
        bridge.observe_codex(self.root,self.payload(),now=1000);bridge.observe_codex(self.root,self.payload(31),now=1100)
        value=bridge.quota(self.root,'GPT',now=1101)
        self.assertEqual((value['observed_before'],value['observed_after']),(.7,.69))
        self.assertNotIn('before',value)
        self.assertAlmostEqual(scheduler.report(self.root,'GPT',**value)['agents']['GPT']['cost'],.01)
    def test_attributed_same_window_sample_is_counted_once(self):
        bridge.observe_codex(self.root,self.payload(30),now=1000)
        bridge.observe_codex(self.root,self.payload(32),now=1100,invocation_id='one-native-invocation')
        value=bridge.quota(self.root,'GPT',now=1101)
        for _ in range(4):
            row=scheduler.report(self.root,'GPT',**value)['agents']['GPT']
            self.assertAlmostEqual(row['cost'],.7*.01+.3*.02)
    def test_window_reset_separates_observations_from_cost(self):
        bridge.observe_codex(self.root,self.payload(30),now=1000)
        bridge.observe_codex(self.root,self.payload(40,reset=90000),now=1100,invocation_id='different-window')
        value=bridge.quota(self.root,'GPT',now=1101)
        self.assertNotIn('before',value);self.assertNotIn('observed_before',value)

if __name__=='__main__':unittest.main()
