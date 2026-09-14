import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('launcher_memory_launch_tests',ROOT/'launcher.py')
launcher=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=launcher
spec.loader.exec_module(launcher)
GIB=1024**3

class MemoryLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)
        self.config={'model_type':'qwen3_5','text_config':{'model_type':'qwen3_5_text',**launcher.MTPLX_LONG_CONTEXT_DENSE_GEOMETRY}}
        launcher.atomic_json(self.path/'config.json',self.config)
        self.model={'path':str(self.path),'name':'qwopus3.8-27b-flash-mxfp4-vision-mtplx'}
        self.plan=launcher.LaunchPlan(run_id='test',backend='mtplx',client='pi',model=self.model,
            project=str(self.path),context=131072,output=100000,reasoning='xhigh',port=18080,
            mode='custom',options={'acceleration':'mtp','depth':2,'kv':'q4','profile':'sustained','fan':'smart'},
            purpose='session',run_dir=self.path)
        self.cap={'runtimeVersion':'mtplx 2.11.2 (2.11.2)','mtp':True,'depthMax':3}
        self.ram=mock.patch.object(launcher,'physical_memory_bytes',return_value=48*GIB)
        self.ram.start();self.addCleanup(self.ram.stop)
        self.python=mock.patch.object(launcher,'omlx_runtime_python',return_value='/runtime/bin/python')
        self.python.start();self.addCleanup(self.python.stop)

    def test_build_preserves_context_reasoning_and_quantization(self):
        with mock.patch.object(launcher,'preserved_qwopus_template',return_value=None),mock.patch.object(launcher,'validated_mtplx_operator_route',return_value='default'):
            launcher.build_mtplx(self.plan,self.cap)
        self.assertEqual(self.plan.engine_argv[:3],['/runtime/bin/python',str(ROOT/'mtplx_hub_runtime.py'),'serve'])
        for flag,value in [('--context-window','131072'),('--paged-kv-quantization','q4'),('--reasoning-effort','xhigh'),('--depth','2')]:
            self.assertEqual(self.plan.engine_argv[self.plan.engine_argv.index(flag)+1],value)
        self.assertEqual(self.plan.engine_env['MTPLX_MEMORY_LIMIT_BYTES'],str(40*GIB))
        self.assertEqual(self.plan.engine_env['MTPLX_SESSION_BANK_PER_SESSION_BYTES'],str(12*GIB))
        self.assertEqual(self.plan.engine_env['MTPLX_SESSION_BANK_MAX_BYTES'],'auto')
        self.assertEqual(self.plan.engine_env['MTPLX_ALLOW_SWAP'],'0')

    def test_no_implicit_change_to_unreviewed_routes(self):
        for alteration in ['runtime','benchmark','moe','geometry','ram']:
            with self.subTest(alteration=alteration):
                plan=copy.deepcopy(self.plan); cap=dict(self.cap); config=copy.deepcopy(self.config)
                plan.engine_argv=['mtplx','serve'];plan.engine_env={}
                if alteration=='runtime':cap['runtimeVersion']='mtplx 2.11.3'
                if alteration=='benchmark':plan.purpose='benchmark'
                if alteration=='moe':config['text_config']['num_experts']=512
                if alteration=='geometry':config['text_config']['hidden_size']=2048
                launcher.atomic_json(self.path/'config.json',config)
                with mock.patch.object(launcher,'physical_memory_bytes',return_value=(32 if alteration=='ram' else 48)*GIB):
                    launcher.configure_mtplx_hub_memory(plan,cap)
                self.assertEqual(plan.engine_argv,['mtplx','serve'])
                self.assertEqual(plan.engine_env,{})

    def test_missing_python_is_actionable_error(self):
        with mock.patch.object(launcher,'omlx_runtime_python',return_value=None):
            with self.assertRaisesRegex(ValueError,'runtime Python is missing'):
                launcher.configure_mtplx_hub_memory(self.plan,self.cap)

if __name__=='__main__':unittest.main()
