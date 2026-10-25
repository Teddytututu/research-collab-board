"""Frozen ETA display contracts, with fictional dates and task descriptions."""
import unittest,subprocess,shutil
from pathlib import Path
@unittest.skipUnless(shutil.which('node'),'Node is optional for JavaScript checks')
class EtaView(unittest.TestCase):
    def test_dates_conditions_and_scope_labels(self):
        root=Path(__file__).resolve().parents[1]
        script="""const assert=require('assert'),e=require('./board/eta-view.js');
const now=new Date('2030-01-01T15:58:00Z');
assert.equal(e.label({mode:'estimate',at:'2030-01-01T16:10:00Z'},now),'预计 明天 00:10');
assert.equal(e.label({mode:'estimate',at:'2030-01-01T20:00:00+08:00',overdue:true},now),'预计待定');
assert.equal(e.label({mode:'paused',remaining_seconds:7200},now),'已暂停，恢复后约2小时');
assert.equal(e.label({mode:'conditional',condition:'参考数据准备',remaining_seconds:7200},now),'等参考数据准备后约2小时');
assert.equal(e.label({mode:'complete',completion_label:'已交示例',actual_at:'2030-01-01T20:52:00+08:00'},now),'已交示例 20:52');
assert.match(e.detail({mode:'conditional',condition:'接手',confidence:'低',basis:'小规模对照'}),/把握：低.*小规模对照/);
assert.equal(e.label({mode:'continuous'}),'随实验队列交付');
assert.equal(e.label({mode:'conditional',short_condition:'领取'},now),'等领取后更新');"""
        result=subprocess.run(['node','-e',script],cwd=root,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
