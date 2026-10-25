"""Actual Windows readers may briefly retain a handle across atomic replacements."""
import ctypes,os,tempfile,threading,time,unittest,json
from pathlib import Path
from contextlib import contextmanager
from board import storage,workers
TEST_ROOT=Path(__file__).resolve().parents[1]/'work/tests'
TEST_ROOT.mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(TEST_ROOT)

@contextmanager
def transient_reader(path):
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    create=kernel.CreateFileW;create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];create.restype=wintypes.HANDLE
    close=kernel.CloseHandle;close.argtypes=[wintypes.HANDLE];close.restype=wintypes.BOOL
    handle=create(str(path),0x80000000,1,None,3,0,None)
    if handle==wintypes.HANDLE(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    released=threading.Event()
    def release():time.sleep(.1);close(handle);released.set()
    thread=threading.Thread(target=release);thread.start()
    try:yield
    finally:thread.join();assert released.is_set()

@unittest.skipUnless(os.name=='nt','Windows file sharing behavior')
class WindowsWrites(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_json_update_retries_reader_and_preserves_original_bytes(self):
        path=self.root/'attachments/state.json';storage.write(path,{'other':7,'tasks':{}});before=path.read_bytes()
        with transient_reader(path):storage.update_json(self.root,'attachments/state.json',lambda value:value['tasks'].update(A={'status':'review'}))
        self.assertEqual(storage.read(path)['other'],7)
        self.assertEqual(storage.read(path)['tasks']['A']['status'],'review')
        self.assertIn(before,[p.read_bytes() for p in (path.parent/'history').glob('*')])
    def test_lease_heartbeat_retries_reader(self):
        row=workers.claim(self.root,'A','W1',['folder'],now=1);path=self.root/'attachments/locks/A.lock'
        with transient_reader(path):workers.update(self.root,'A',row['token'],now=20)
        self.assertEqual(storage.read(path)['heartbeat'],20)
    def test_board_field_update_retries_reader(self):
        path=self.root/'board.md';path.write_bytes(b'header\r\n| A | work | queued | GPT |\r\n')
        with transient_reader(path):workers.update_board(self.root,'A','review')
        self.assertEqual(path.read_bytes(),b'header\r\n| A | work | review | GPT |\r\n')

if __name__=='__main__':unittest.main()
