from pathlib import Path
import hashlib,tempfile,unittest
from PIL import Image
from board import artwork,storage
ROOT=Path(__file__).resolve().parents[1]
(ROOT/'work/tests').mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(ROOT/'work/tests')
class ArtworkDeploy(unittest.TestCase):
    def fixture(self,root):
        records={};ids=[]
        for i in range(7):
            path=root/('native-'+str(i)+'.png');im=Image.new('RGBA',(256,256),(0,0,0,0));im.paste((i*30,100,200,255),(40,40,210,210));im.save(path)
            job='native-job-'+str(i);ids.append(job);records[job]=dict(status='completed',saved_path=str(path),revised_prompt='Original fixture expression '+str(i))
        storage.write(root/'attachments/provider-images.json',records);return ids,records
    def test_seven_native_pngs_deploy_byte_identically_with_actual_prompt_and_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ids,records=self.fixture(root);rows=artwork.deploy(root,'GPT',ids)
            self.assertEqual(len(rows),7)
            for row in rows:
                self.assertEqual(hashlib.sha256((root/row['file']).read_bytes()).hexdigest(),row['sha256'])
                self.assertEqual(row['prompt'],records[row['native_job_id']]['revised_prompt'])
    def test_incomplete_job_is_preserved_for_collection_without_deployment(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ids,records=self.fixture(root);records[ids[-1]]['status']='in_progress';storage.write(root/'attachments/provider-images.json',records)
            with self.assertRaises(ValueError):artwork.deploy(root,'GPT',ids)
            self.assertFalse((root/'attachments/generated/GPT').exists())
    def test_redeployment_preserves_existing_asset_bytes_in_history(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ids,records=self.fixture(root);target=root/'attachments/generated/Claude/avatar.png';target.parent.mkdir(parents=True);target.write_bytes(b'previous-image')
            artwork.deploy(root,'Claude',ids)
            self.assertTrue(any(p.read_bytes()==b'previous-image' for p in (target.parent/'history').iterdir()))

if __name__=='__main__':unittest.main()
