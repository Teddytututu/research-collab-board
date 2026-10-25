"""Pure JavaScript behavior regressions; browser acceptance uses the UI separately."""
from pathlib import Path
import shutil, subprocess, unittest
ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('node'),'Node is optional for JavaScript unit checks')
class FrontendUnitTests(unittest.TestCase):
    def run_js(self,source):
        result=subprocess.run(['node','-e',source],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
    def test_mood_selection_and_all_fifteen_overrides(self):
        self.run_js('''const assert=require('assert');const m=require('./board/mood.js');
const at=new Date(2030,0,1,15);assert.equal(m.names.length,15);
for(const name of m.names)assert.equal(m.choose({claude_mood:{mood:name}},[],at),name);
assert.equal(m.choose({},[{status:'review'}],at),'reading');
assert.equal(m.choose({todo:[{urgent:true}]},[],at),'panic');
assert.equal(m.choose({todo:Array(5).fill({})},[],at),'confused');
assert.equal(m.choose({},[],new Date(2030,0,1,2)),'sleepy');
assert.equal(m.choose({},[],at),'thinking');''')
    def test_reply_to_legacy_study_message_keeps_the_main_composer(self):
        self.run_js(r'''const vm=require('vm'),fs=require('fs'),assert=require('assert');let saved=0,composed=0,focused=0;
const source=fs.readFileSync('board/discussion.js','utf8');
const context={draft:{body:'Keep this draft',client_id:'old'},BoardIdentity:{channel:'main',setChannel:()=>{throw Error('Unified replies stay in main');}},save:()=>saved++,composer:()=>composed++,$:()=>({focus:()=>focused++})};
vm.runInNewContext(source.match(/  function reply\(item\) \{[\s\S]*?\n  \}/)[0]+'\nreply({id:"legacy-study",channel:"study"});',context);
assert.equal(context.draft.body,'Keep this draft');assert.equal(context.draft.parent_id,'legacy-study');assert.equal(context.draft.client_id,null);assert.equal(context.BoardIdentity.channel,'main');
assert.equal(saved,1);assert.equal(composed,1);assert.equal(focused,1);''')
