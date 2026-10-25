"""A real new venv can install the shipped requirements through the installer."""
from pathlib import Path
import os,subprocess,sys,tempfile,unittest,shutil
ROOT=Path(__file__).resolve().parents[1]
(ROOT/'work/tests').mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(ROOT/'work/tests')
class Dependencies(unittest.TestCase):
    def installer(self):
        import runpy
        return runpy.run_path(str(ROOT/'scripts/install_deps.py'))
    def test_temporary_directory_rejects_an_outside_parent(self):
        with self.assertRaises(ValueError):self.installer()['project_temp'](dir=str(ROOT.parent/'outside-test-project'))
    def test_temporary_basename_rejects_path_traversal(self):
        with self.assertRaises(ValueError):self.installer()['project_temp'](prefix='../../outside-',dir=str(ROOT/'work/tests'))
    def test_new_venv_installs_pip_and_declared_runtime_dependencies(self):
        with tempfile.TemporaryDirectory() as folder:
            package=Path(folder)/'fresh-package';package.mkdir()
            for name in ['board','scripts']:
                shutil.copytree(ROOT/name,package/name,ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copy2(ROOT/'requirements.txt',package/'requirements.txt')
            env=package/'.venv'
            made=subprocess.run([sys.executable,'-m','venv','--without-pip',str(env)],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(made.returncode,0,made.stderr)
            python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            install=subprocess.run([str(python),'-B',str(ROOT/'scripts/install_deps.py')],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=180)
            self.assertEqual(install.returncode,0,install.stdout+'\n'+install.stderr)
            check=subprocess.run([str(python),'-B','-c','import pip,PIL;print("ready")'],capture_output=True,text=True)
            self.assertEqual((check.returncode,check.stdout.strip()),(0,'ready'))
            for script,args in [('onboarding.py',['status','GPT']),('artwork.py',['list']),('post_message.py',['--recent'])]:
                routed=subprocess.run([sys.executable,'-B','-S',str(package/'scripts'/script),*args],cwd=package,capture_output=True,text=True,encoding='utf-8')
                self.assertEqual(routed.returncode,0,routed.stderr)

if __name__=='__main__':unittest.main()
