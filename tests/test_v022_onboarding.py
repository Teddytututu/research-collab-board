import tempfile, unittest
from pathlib import Path
from PIL import Image
from board.project import initialize
from board import onboarding, provider_bridge

ROOT=Path(__file__).resolve().parents[1]
(ROOT/'work/tests').mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(ROOT/'work/tests')
class Onboarding(unittest.TestCase):
    def test_service_initialization_uses_bundled_artwork_and_keeps_native_control_pending(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);initialize(root,'Fictional study')
            result=onboarding.prepare(root,'GPT')
            self.assertEqual((result['artwork']['expected'],result['artwork']['valid']),(2,2))
            self.assertEqual((result['generated_artwork']['expected'],result['generated_artwork']['valid']),(14,0))
            self.assertTrue(result['quota_reported']);self.assertFalse(result['complete'])
            self.assertTrue(result['checks']['artwork']);self.assertIn('native_control',result['pending'])
    def test_opaque_png_and_placeholder_sized_image_are_not_finished_artwork(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);initialize(root,'Fictional study');path=root/'attachments/generated/GPT/avatar.png';path.parent.mkdir(parents=True)
            Image.new('RGB',(512,512),'blue').save(path)
            self.assertEqual(onboarding.artwork(root,'GPT')['valid'],0)
            im=Image.new('RGBA',(512,512),(0,0,0,0));im.paste((0,100,200,255),(100,100,400,400));im.save(path)
            self.assertEqual(onboarding.artwork(root,'GPT')['valid'],1)
    def test_runtime_host_ack_is_separate_from_a_pending_goal_request(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);initialize(root,'Fictional study');request=provider_bridge.request_goal(root,'GPT','Finish setup')
            self.assertFalse(onboarding.status(root,'GPT')['native_control'])
            provider_bridge.acknowledge(root,request['id'],{'provider':'codex-app-server','thread_id':'synthetic-thread','status':'active'})
            self.assertTrue(onboarding.status(root,'GPT')['native_control'])

if __name__=='__main__':unittest.main()
