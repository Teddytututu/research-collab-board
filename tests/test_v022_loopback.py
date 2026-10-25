"""Real loopback listener and retired-route behaviour for the local project."""
from pathlib import Path
import argparse,contextlib,http.client,importlib.util,io,json,os,subprocess,sys,tempfile,threading,unittest
from unittest.mock import patch
from board import __main__ as cli,project
from board.app import create_server

ROOT=Path(__file__).resolve().parents[1]
(ROOT/'work/tests').mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(ROOT/'work/tests')

class Loopback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        project.initialize(cls.root,'Fictional local project')
        cls.server=create_server(cls.root,port=0);cls.port=cls.server.server_port
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def request(self,path,method='GET',headers=None,body=None):
        values={'Host':f'127.0.0.1:{self.port}','Origin':f'http://127.0.0.1:{self.port}'}
        values.update(headers or {})
        if method=='POST':values['Content-Type']='application/json';body=json.dumps({} if body is None else body)
        connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        connection.request(method,path,body=body,headers=values);response=connection.getresponse()
        result=response.status,response.read(),dict(response.getheaders());connection.close();return result
    def test_socket_binds_only_ipv4_loopback_and_serves_the_project(self):
        self.assertEqual(self.server.socket.getsockname()[0],'127.0.0.1')
        self.assertEqual(self.request('/api/project')[0],200)
        identity=json.loads(self.request('/api/me')[1])
        self.assertEqual(identity['local'],True);self.assertEqual(identity['listener'],'127.0.0.1')
    def test_retired_pages_and_apis_return_404_for_all_supported_methods(self):
        for route in ['/pair','/pair.html','/pairing.py','/api/pair','/api/pairing','/api/pairing/qr','/api/devices','/api/devices/revoke']:
            for method in ['GET','HEAD','POST']:
                with self.subTest(route=route,method=method):
                    status,body,headers=self.request(route,method)
                    self.assertEqual(status,404)
                    self.assertNotIn('Set-Cookie',headers)
        self.assertFalse((self.root/'attachments/devices.json').exists())
    def test_host_origin_and_forwarded_protections_survive(self):
        for headers in [{'Host':'other.invalid'},{'Host':'192.0.2.8'},{'Forwarded':'for=192.0.2.8'},{'X-Forwarded-For':'127.0.0.1'},{'X-Forwarded-Host':'localhost'}]:
            with self.subTest(headers=headers):self.assertEqual(self.request('/',headers=headers)[0],403)
        self.assertEqual(self.request('/api/project','POST',headers={'Origin':'http://other.invalid'})[0],403)
        self.assertEqual(self.request('/api/project','POST',headers={'Origin':''})[0],403)
    def test_project_settings_save_without_a_device_identity(self):
        status,body,headers=self.request('/api/project','POST',body={'question':'Which local workflow helps?','deliverable':'A local comparison','user_name':'Example user'})
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['user_name'],'Example user')
        identity=json.loads(self.request('/api/me')[1]);self.assertNotIn('lan',identity)
        self.assertNotIn('Set-Cookie',headers)
    def test_listener_api_rejects_the_removed_option(self):
        try:
            server=create_server(self.root,port=0,lan=True)
        except TypeError:return
        server.server_close();self.fail('Removed listener option was accepted')

class LocalStartup(unittest.TestCase):
    def bootstrap(self):
        spec=importlib.util.spec_from_file_location('local_bootstrap',ROOT/'scripts/bootstrap.py')
        bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap);return bootstrap
    def test_both_command_entries_reject_old_listening_options(self):
        bootstrap=self.bootstrap()
        for parse,args in [(cli.parse_args,['start','Example project']),(bootstrap.parse_args,['Example project'])]:
            for old in [['--lan'],['--host','0.0.0.0'],['--bind','0.0.0.0']]:
                with self.subTest(args=args,option=old),contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:parse(args+old)
                    self.assertEqual(error.exception.code,2)
    def test_bootstrap_reuses_only_a_confirmed_local_listener(self):
        for identity,accept in [({'listener':'127.0.0.1'},True),({},False),({'listener':'0.0.0.0'},False)]:
            with self.subTest(identity=identity),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);record=project.initialize(root/'data','Fictional startup')
                python=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
                python.parent.mkdir(parents=True);python.write_bytes(b'')
                bootstrap=self.bootstrap();args=argparse.Namespace(project=None,port=8799,question='',deliverable='',user_name='Example user',agent='GPT')
                responses=[io.BytesIO(json.dumps(record).encode()),io.BytesIO(json.dumps(identity).encode())]
                with patch.object(bootstrap,'ROOT',root),patch.object(bootstrap,'parse_args',return_value=args),patch.object(bootstrap.subprocess,'run',return_value=subprocess.CompletedProcess([],0)),patch.object(bootstrap.subprocess,'Popen',side_effect=AssertionError('Reused service started a child')),patch.object(bootstrap.urllib.request,'urlopen',side_effect=responses),contextlib.redirect_stdout(io.StringIO()):
                    if accept:bootstrap.main()
                    else:
                        with self.assertRaises(SystemExit):bootstrap.main()

if __name__=='__main__':unittest.main()
