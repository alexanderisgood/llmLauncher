import copy
import unittest
from pathlib import Path
from unittest import mock
import launcher


class ExpertOffloadTests(unittest.TestCase):
    def setUp(self):
        self.config = {'model_type':'qwen4_exp', 'quantization':{'bits':4,'group_size':64},
                       'text_config':{'num_experts':16,'num_hidden_layers':2,'hidden_size':64,'moe_intermediate_size':64}}
        self.ple = {'supported':True,'inventoryFingerprint':'fixture','residentBytes':80_000_000_000,
                    'checkpointBytes':112_000_000_000,'pleBytes':32_000_000_000}
        self.tensors = {}
        for layer in range(2):
            for proj in ('gate_proj','up_proj','down_proj'):
                for field in ('weight','scales','biases'):
                    self.tensors[f'language_model.model.layers.{layer}.mlp.switch_mlp.{proj}.{field}'] = {
                        'shape':[16,64,8 if field=='weight' else 1],
                        'dtype':'U32' if field=='weight' else 'BF16',
                        'data_offsets':[0,32768 if field=='weight' else 2048]}

    def profile(self, version='0.7.0.dev2'):
        with mock.patch.object(launcher,'safetensors_inventory',return_value=(True,self.tensors,[])):
            return launcher.qwen4_expert_offload_profile(Path('/unused'),self.config,self.ple,version)

    def test_complete_layout_and_exact_runtime_required(self):
        self.assertTrue(self.profile()['supported'])
        self.assertEqual(self.profile()['expertBytes'],6*(32768+4096))
        for v in ('0.7.0.dev1','0.7.0.dev3','0.7.0'):
            self.assertFalse(self.profile(v)['supported'])

    def test_missing_expert_metadata_or_shape_is_not_discounted(self):
        key=next(k for k in self.tensors if k.endswith('biases'))
        original=self.tensors.pop(key)
        self.assertFalse(self.profile()['supported'])
        self.tensors[key]=original
        self.tensors[key]['shape'][0]=15
        self.assertFalse(self.profile()['supported'])

    def test_unsupported_packing_is_rejected(self):
        self.config['quantization']['group_size']=96
        self.assertFalse(self.profile()['supported'])

    def test_user_memory_share_survives_profile_round_trip(self):
        m={'omlxExpertOffload':self.profile(),'rootModelType':'qwen4_exp','qwen4Ple':self.ple}
        cap={'kv':False,'mtp':False,'dflash':False,'depthMax':1}
        options={'acceleration':'off','expertResidentPercent':37.5,'omlxMemoryGB':41}
        with mock.patch.object(launcher,'physical_memory_bytes',return_value=48*1024**3):
            kept=launcher._profile_request_whitelist({'options':options})['options']
            result=launcher.validated_profile_options('omlx',m,cap,kept)
        self.assertEqual(result['expertResidentPercent'],37.5)
        self.assertEqual(result['omlxMemoryGB'],41)
        self.assertEqual(result['memoryGuard'],'high')
        self.assertEqual(launcher.benchmark_engine_settings('omlx',result)['expertResidentPercent'],37.5)

    def test_invalid_memory_and_speculative_combinations_rejected(self):
        model={'omlxExpertOffload':self.profile(),'rootModelType':'qwen4_exp','qwen4Ple':self.ple}
        with mock.patch.object(launcher,'physical_memory_bytes',return_value=48*1024**3):
            for options in ({'expertResidentPercent':True},{'expertResidentPercent':30},{'omlxMemoryGB':float('nan')},{'omlxMemoryGB':60}):
                with self.assertRaises(ValueError):launcher.omlx_expert_offload_options(model,options)
            for mode in ('mtp','dflash'):
                with self.assertRaises(ValueError):launcher.validated_profile_options('omlx',model,{'mtp':False,'dflash':False},{'acceleration':mode})

    def test_capacity_discount_applies_once_and_preserves_kv(self):
        model={'omlxExpertOffload':{'supported':True,'expertBytes':64_000_000_000},'qwen4Ple':self.ple,
               'memoryGeometry':{'ready':True,'qwen4Qsa':True,'fullBytesPerToken':28704,'qsaAllocationStepTokens':8192}}
        with mock.patch.object(launcher,'physical_memory_bytes',return_value=48*1024**3):
            a=launcher.launch_memory_estimate({'backend':'omlx','context':32768,'options':{'expertResidentPercent':25,'omlxMemoryGB':41}},model,{})
            b=launcher.launch_memory_estimate({'backend':'omlx','context':32768,'options':{'expertResidentPercent':50,'omlxMemoryGB':41}},model,{})
        self.assertEqual(a['modelBytes'],32_000_000_000)
        self.assertEqual(b['modelBytes'],48_000_000_000)
        self.assertEqual(a['kvCacheBytes'],b['kvCacheBytes'])
        self.assertEqual(a['memoryGuardCeilingBytes'],41_000_000_000)
        self.assertTrue(a['expertOffload'])

    def test_old_sweep_settings_remain_valid_but_offload_requires_identity(self):
        settings={'burst':'balanced','anePrefill':'off','memoryGuard':'high'}
        self.assertTrue(launcher._engine_settings_sweep_settings_valid('omlx',settings,{}))
        self.assertFalse(launcher._engine_settings_sweep_settings_valid('omlx',settings,{'expertOffload':True}))
        with mock.patch.object(launcher,'physical_memory_bytes',return_value=48*1024**3):
            self.assertTrue(launcher._engine_settings_sweep_settings_valid('omlx',dict(settings,expertResidentPercent=25,omlxMemoryGB=41),{'expertOffload':True}))

if __name__=='__main__':unittest.main()
