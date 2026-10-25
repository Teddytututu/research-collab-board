"""Bootstrap and the actual reaction renderer respect first-run choices."""
from pathlib import Path
import contextlib, importlib.util, io, json, os, shutil, subprocess, sys, tempfile, unittest
from unittest.mock import Mock, patch
from board import onboarding, project

ROOT=Path(__file__).resolve().parents[1]
(ROOT/'work/tests').mkdir(parents=True,exist_ok=True)
tempfile.tempdir=str(ROOT/'work/tests')


def load_bootstrap():
    spec=importlib.util.spec_from_file_location('first_run_bootstrap',ROOT/'scripts/bootstrap.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FirstRunIntegration(unittest.TestCase):
    def test_fresh_bootstrap_continues_after_registration_failure_with_zero_emote_network(self):
        bootstrap=load_bootstrap()
        with tempfile.TemporaryDirectory() as folder:
            package=Path(folder)
            python=package/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            python.parent.mkdir(parents=True)
            python.write_bytes(b'local interpreter fixture')
            calls=[]
            def run(command,**kwargs):
                calls.append(command)
                if '--init-only' in command:
                    project.initialize(package/'data','Fresh project','Which workflow?','A local report')
                elif any('onboarding.py' in str(x) for x in command):
                    self.assertTrue(onboarding.status(package/'data','GPT')['checks']['artwork'])
                self.assertFalse(any('install_emotes.py' in str(x) for x in command))
                return subprocess.CompletedProcess(command,0,stdout='',stderr='')
            def request(url,**kwargs):
                self.assertTrue(url.startswith('http://127.0.0.1:8780/'))
                if len(calls)==3 and not (package/'data/service.json').exists():
                    raise OSError('Fresh listener')
                return io.BytesIO((package/'data/project.json').read_bytes())
            child=Mock(pid=12345)
            child.poll.return_value=None
            output=io.StringIO()
            args=bootstrap.parse_args(['Fresh project','--question','Which workflow?','--deliverable','A local report','--port','8780'])
            watch=dict(status='manual',manual_command='python scripts/install_night_watch.py --install',error='Scheduler fixture error')
            with patch.object(bootstrap,'ROOT',package),patch.object(bootstrap,'parse_args',return_value=args),patch.object(bootstrap.subprocess,'run',side_effect=run),patch.object(bootstrap.subprocess,'Popen',return_value=child),patch.object(bootstrap,'register_night_watch',return_value=watch) as register,patch.object(bootstrap.urllib.request,'urlopen',side_effect=request),patch('builtins.input',side_effect=AssertionError('stdin read')),contextlib.redirect_stdout(output):
                bootstrap.main()
            self.assertTrue((package/'data/service.json').is_file())
            self.assertEqual(output.getvalue().count(onboarding.EMOTE_PROMPT),1)
            self.assertIn('http://127.0.0.1:8780',output.getvalue())
            self.assertIn('Scheduler fixture error',output.getvalue())
            self.assertEqual(onboarding.emote_preferences(package/'data')['mode'],'unicode')
            self.assertFalse((package/'data/attachments/generated').exists())
            register.assert_called_once()

    def test_first_run_reuses_registration_and_decline_without_child_commands(self):
        bootstrap=load_bootstrap()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch.object(bootstrap,'register_night_watch',return_value=dict(status='registered')) as register,patch.object(bootstrap.subprocess,'run',side_effect=AssertionError('External child command')),contextlib.redirect_stdout(io.StringIO()):
                first=bootstrap.first_run_options(sys.executable,root,'unicode')
                again=bootstrap.first_run_options(sys.executable,root)
            register.assert_called_once()
            self.assertEqual(first['night_watch'],again['night_watch'])
            self.assertEqual(again['emotes']['choice'],'unicode')

    def test_actual_installer_dry_run_uses_the_integrated_interface(self):
        bootstrap=load_bootstrap()
        with tempfile.TemporaryDirectory() as folder:
            result=bootstrap.register_night_watch(sys.executable,Path(folder),dry_run=True)
        self.assertEqual(result['status'],'preview',result)
        self.assertEqual(result['report']['interval_minutes'],10)

    def test_consent_flags_are_mutually_exclusive(self):
        bootstrap=load_bootstrap()
        self.assertEqual(bootstrap.parse_args(['--download-emotes']).emotes,'download')
        self.assertEqual(bootstrap.parse_args(['--unicode-emotes']).emotes,'unicode')
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            bootstrap.parse_args(['--download-emotes','--unicode-emotes'])

    def test_saved_unicode_choice_can_be_recorded_from_noninteractive_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/onboarding.py'),'emotes','--unicode-emotes','--data-dir',folder],cwd=ROOT,input='',capture_output=True,text=True,encoding='utf-8',timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['choice'],'unicode')
            self.assertEqual(onboarding.emote_preferences(folder)['decision_required'],False)

    @unittest.skipUnless(shutil.which('node'),'Node executes the actual reaction renderer')
    def test_reaction_renderer_outputs_unicode_and_clears_old_download_catalog(self):
        script=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.hidden=false;this.style={};this.dataset={};this.attributes={};this.listeners={};}
  append(...nodes){this.children.push(...nodes);}
  setAttribute(name,value){this.attributes[name]=String(value);}
  getAttribute(name){return this.attributes[name]??null;}
  addEventListener(type,listener){(this.listeners[type]||=[]).push(listener);}
  replaceChildren(...nodes){this.children=nodes;}
  replaceWith(node){this.replacement=node;}
  closest(){return null;}
  getBoundingClientRect(){return {left:0,right:200};}
  scrollIntoView(){}
  focus(){context.document.activeElement=this;}
  querySelector(selector){return this.children.find(n=>n.tag===selector)||this.children.map(n=>n.querySelector(selector)).find(Boolean);}
}
const context={window:{},BoardIdentity:{me:{id:'owner'},accounts:[]},document:{createElement:tag=>new Element(tag),addEventListener(){},documentElement:{clientWidth:1000},activeElement:null},innerWidth:1000,fetch(){throw Error('External request');}};
vm.runInNewContext(fs.readFileSync('board/room-extras.js','utf8'),context);
const api=context.window.RoomExtras;
const tree=()=>api.reactions({id:'message',reactions:[{emoji:'👍',count:1,mine:false},{emoji:'bili:42',count:1,mine:false}]},['👍','❤️','😂','🎉','👀','💡','bili:42'],()=>{},()=>{});
let box=tree();
assert.equal(box.children[0].dataset.emoji,'👍');
assert.equal(box.children[0].children[0].tag,'span');
assert.equal(box.children[0].children[0].textContent,'👍');
assert.equal(box.children[1].children[0].textContent,'🙂');
box.children.at(-2).onclick();
assert.equal(box.children.at(-1).children[0].children.length,6);
assert.ok(box.children.at(-1).children[0].children.every(b=>b.children[0].tag==='span'));
api.setReactionCatalog([{key:'bili:42',label:'Local emote',url:'/room-reactions/42.png',fallback:'🙂'}]);
box=tree();let image=box.children[1].children[0];
assert.equal(image.tag,'img');assert.equal(image.src,'/room-reactions/42.png');
image.onerror();assert.equal(image.replacement.textContent,'🙂');
api.setReactionCatalog([]);box=tree();
assert.equal(box.children[1].children[0].tag,'span');
assert.equal(box.children[1].children[0].textContent,'🙂');
console.log('Unicode picker, local upgrade and fallback verified');
'''
        result=subprocess.run(['node','-e',script],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
