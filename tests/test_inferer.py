import glob
from pathlib import Path
import shutil
import unittest

from Cryptodome import Random
import femio
import numpy as np

import siml.prepost as prepost
import siml.setting as setting
import siml.inferer as inferer


class TestInferer(unittest.TestCase):

    def test_infer_with_preprocessed_data(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/linear/pretrained/settings.yml'))
        main_setting.inferer.converter_parameters_pkl = Path(
            'tests/data/linear/preprocessed/preprocessors.pkl')
        main_setting.inferer.output_directory_root = Path(
            'tests/data/linear/inferred')
        ir = inferer.Inferer(main_setting)
        if ir.setting.trainer.output_directory.exists():
            shutil.rmtree(ir.setting.trainer.output_directory)
        res = ir.infer(
            model=Path('tests/data/linear/pretrained'),
            data_directories=Path('tests/data/linear/preprocessed/validation'))
        np.testing.assert_almost_equal(
            res[0]['dict_y']['y'],
            np.load('tests/data/linear/interim/validation/0/y.npy'), decimal=3)
        np.testing.assert_array_less(res[0]['loss'], 1e-7)

    def test_infer_with_raw_data_deform(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/deform/pretrained/settings.yml'))

        def conversion_function(fem_data, raw_directory=None):
            adj = fem_data.calculate_adjacency_matrix_element()
            nadj = prepost.normalize_adjacency_matrix(adj)
            return {'adj': adj, 'nadj': nadj}

        ir = inferer.Inferer(
            main_setting, conversion_function=conversion_function)
        if ir.setting.trainer.output_directory.exists():
            shutil.rmtree(ir.setting.trainer.output_directory)
        ir.setting.inferer.converter_parameters_pkl = Path(
            'tests/data/deform/preprocessed/preprocessors.pkl')
        ir.setting.inferer.save = False
        ir.setting.inferer.perform_preprocess = True

        res_from_raw = ir.infer(
            model=Path('tests/data/deform/pretrained'),
            data_directories=Path(
                'tests/data/deform/raw/test/tet2_4_modulusx0.9500'))

        ir.setting.inferer.perform_preprocess = False
        res_from_preprocessed = ir.infer(
            model=Path('tests/data/deform/pretrained'),
            data_directories=Path(
                'tests/data/deform/preprocessed/test/tet2_4_modulusx0.9500'))

        np.testing.assert_almost_equal(
            res_from_raw[0]['dict_y']['elemental_stress'],
            res_from_preprocessed[0]['dict_y']['elemental_stress'],
            decimal=3)
        np.testing.assert_almost_equal(
            res_from_raw[0]['loss'], res_from_preprocessed[0]['loss'])
        np.testing.assert_array_less(res_from_raw[0]['loss'], 1e-2)

    def test_infer_with_raw_data_wo_answer_w_model_directory(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/deform/pretrained/settings.yml'))

        def conversion_function(fem_data, raw_directory=None):
            adj = fem_data.calculate_adjacency_matrix_element()
            nadj = prepost.normalize_adjacency_matrix(adj)
            return {'adj': adj, 'nadj': nadj}

        ir = inferer.Inferer(
            main_setting, conversion_function=conversion_function)
        ir.setting.inferer.converter_parameters_pkl = Path(
            'tests/data/deform/preprocessed/preprocessors.pkl')
        ir.setting.inferer.save = False
        ir.setting.inferer.perform_preprocess = True
        if ir.setting.trainer.output_directory.exists():
            shutil.rmtree(ir.setting.trainer.output_directory)

        res_from_raw = ir.infer(
            model=Path('tests/data/deform/pretrained'),
            data_directories=Path(
                'tests/data/deform/external/tet2_4_modulusx0.9500'))

        ir.setting.inferer.perform_preprocess = False
        res_from_preprocessed = ir.infer(
            model=Path('tests/data/deform/pretrained'),
            data_directories=Path(
                'tests/data/deform/preprocessed/test/tet2_4_modulusx0.9500'))
        np.testing.assert_almost_equal(
            res_from_raw[0]['dict_y']['elemental_stress'],
            res_from_preprocessed[0]['dict_y']['elemental_stress'],
            decimal=3)

    def test_infer_with_raw_data_wo_answer_with_model_file(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/deform/incomplete_pretrained/settings.yml'))

        def conversion_function(fem_data, raw_directory=None):
            adj = fem_data.calculate_adjacency_matrix_element()
            nadj = prepost.normalize_adjacency_matrix(adj)
            return {'adj': adj, 'nadj': nadj}

        ir = inferer.Inferer(
            main_setting, conversion_function=conversion_function)
        if ir.setting.trainer.output_directory.exists():
            shutil.rmtree(ir.setting.trainer.output_directory)

        ir.setting.inferer.converter_parameters_pkl = Path(
            'tests/data/deform/preprocessed/preprocessors.pkl')
        ir.setting.inferer.save = False

        ir.setting.inferer.perform_preprocess = True
        res_from_raw = ir.infer(
            model=Path(
                'tests/data/deform/incomplete_pretrained/'
                'snapshot_epoch_5000.pth'),
            data_directories=Path(
                'tests/data/deform/external/tet2_4_modulusx0.9500'))

        ir.setting.inferer.perform_preprocess = False
        res_from_preprocessed = ir.infer(
            model=Path('tests/data/deform/pretrained'),
            data_directories=Path(
                'tests/data/deform/preprocessed/test/'
                'tet2_4_modulusx0.9500'))
        np.testing.assert_almost_equal(
            res_from_raw[0]['dict_y']['elemental_stress'],
            res_from_preprocessed[0]['dict_y']['elemental_stress'],
            decimal=3)

    def test_infer_to_write_simulation_file(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/deform/incomplete_pretrained/settings.yml'))
        output_directory = Path('tests/data/deform/write_simulation')

        ir = inferer.Inferer(main_setting)
        if output_directory.exists():
            shutil.rmtree(output_directory)
        ir.setting.inferer.converter_parameters_pkl = Path(
            'tests/data/deform/preprocessed/preprocessors.pkl')
        ir.setting.inferer.output_directory = output_directory
        ir.setting.inferer.write_simulation_base = Path(
            'tests/data/deform/raw')
        ir.setting.inferer.write_simulation = True
        ir.setting.inferer.write_simulation_type = 'ucd'

        res_from_preprocessed = ir.infer(
            model=Path('tests/data/deform/pretrained'),
            data_directories=Path(
                'tests/data/deform/preprocessed/test/'
                'tet2_4_modulusx0.9500'))
        fem_data = femio.FEMData.read_files(
            'ucd', [output_directory / 'mesh.inp'])
        np.testing.assert_almost_equal(
            fem_data.elemental_data.get_attribute_data(
                'predicted_elemental_stress'),
            res_from_preprocessed[0]['dict_y']['elemental_stress'],
            decimal=2)
        np.testing.assert_almost_equal(
            fem_data.elemental_data.get_attribute_data(
                'difference_elemental_stress'),
            res_from_preprocessed[0]['dict_y']['elemental_stress']
            - res_from_preprocessed[0]['dict_answer']['elemental_stress'],
            decimal=2)

        desired_raw_loss = np.mean((
            fem_data.elemental_data.get_attribute_data(
                'predicted_elemental_stress')
            - fem_data.elemental_data.get_attribute_data(
                'answer_elemental_stress'))**2)
        np.testing.assert_almost_equal(
            res_from_preprocessed[0]['raw_loss'], desired_raw_loss)

    def test_infer_simplified_model(self):
        setting_yaml = Path('tests/data/simplified/mlp.yml')
        model_file = Path(
            'tests/data/simplified/pretrained/snapshot_epoch_1000.pth')
        converter_parameters_pkl = Path(
            'tests/data/simplified/pretrained/preprocessors.pkl')
        ir = inferer.Inferer.read_settings(setting_yaml)
        ir.setting.inferer.converter_parameters_pkl = converter_parameters_pkl

        seed_a = np.random.rand(10, 1)
        raw_dict_x = {
            'a': np.concatenate([seed_a, seed_a * 2, seed_a * 3], axis=1),
            'b': np.random.rand(10, 1) * 100.}

        answer_raw_dict_y = {'c': raw_dict_x['a'] * raw_dict_x['b']}
        result = ir.infer_simplified_model(
            model_file, raw_dict_x, answer_raw_dict_y=answer_raw_dict_y)
        rmse = np.mean(
            (result['dict_y']['c'] - answer_raw_dict_y['c'])**2)**.5
        self.assertLess(rmse, 5.)
        self.assertLess(result['loss'], 3e-3)

    def test_infer_timeseries(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/deform_timeseries/pretrained/settings.yml'))
        ir = inferer.Inferer(main_setting)
        if ir.setting.trainer.output_directory.exists():
            shutil.rmtree(ir.setting.trainer.output_directory)
        ir.setting.inferer.converter_parameters_pkl = Path(
            'tests/data/deform_timeseries/preprocessed/preprocessors.pkl')

        preprocessed_data_directory = Path(
            'tests/data/deform_timeseries/preprocessed/train'
            '/tet2_3_modulusx1.0000')
        res = ir.infer(
            model=Path('tests/data/deform_timeseries/pretrained'),
            data_directories=preprocessed_data_directory)
        np.testing.assert_almost_equal(
            res[0]['dict_y']['stress'] * 1e-5,
            np.load(
                'tests/data/deform_timeseries/interim/train'
                '/tet2_3_modulusx1.0000/stress.npy') * 1e-5,
            decimal=3)
        np.testing.assert_array_less(res[0]['loss'], 1e-1)

    def test_infer_res_gcn(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/deform/pretrained_res_gcn/settings.yml'))
        ir = inferer.Inferer(main_setting)
        if ir.setting.trainer.output_directory.exists():
            shutil.rmtree(ir.setting.trainer.output_directory)
        ir.setting.inferer.converter_parameters_pkl = Path(
            'tests/data/deform/preprocessed/preprocessors.pkl')
        preprocessed_data_directory = Path(
            'tests/data/deform/preprocessed/train/tet2_3_modulusx1.0000')
        res = ir.infer(
            model=Path('tests/data/deform/pretrained_res_gcn'),
            data_directories=preprocessed_data_directory)
        np.testing.assert_almost_equal(
            res[0]['dict_y']['elemental_stress'] * 1e-5,
            np.load(
                'tests/data/deform/interim/train'
                '/tet2_3_modulusx1.0000/elemental_stress.npy') * 1e-5,
            decimal=3)
        np.testing.assert_array_less(res[0]['loss'], 1e-3)

    def test_infer_encrypted_data(self):
        encrypt_key = Random.get_random_bytes(16)
        deploy_wo_encrypt_directory = Path(
            'tests/data/linear/deploy_wo_encrypt')
        deploy_w_encrypt_directory = Path('tests/data/linear/deploy_w_encrypt')

        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/linear/pretrained/settings.yml'))
        main_setting.inferer.converter_parameters_pkl = Path(
            'tests/data/linear/preprocessed/preprocessors.pkl')
        ir = inferer.Inferer(main_setting)

        if deploy_wo_encrypt_directory.exists():
            shutil.rmtree(deploy_wo_encrypt_directory)
        ir.deploy(
            output_directory=deploy_wo_encrypt_directory,
            model=Path('tests/data/linear/pretrained'))

        if deploy_w_encrypt_directory.exists():
            shutil.rmtree(deploy_w_encrypt_directory)
        ir.deploy(
            output_directory=deploy_w_encrypt_directory,
            model=Path('tests/data/linear/pretrained'),
            encrypt_key=encrypt_key)

        ir_wo_encrypt = inferer.Inferer.from_model_directory(
            deploy_wo_encrypt_directory)
        res_wo_encrypt = ir_wo_encrypt.infer(
            data_directories=Path('tests/data/linear/preprocessed/validation'))

        ir_w_encrypt = inferer.Inferer.from_model_directory(
            deploy_w_encrypt_directory, decrypt_key=encrypt_key)
        res_w_encrypt = ir_w_encrypt.infer(
            data_directories=Path('tests/data/linear/preprocessed/validation'))

        np.testing.assert_almost_equal(
            res_wo_encrypt[0]['dict_y']['y'], res_w_encrypt[0]['dict_y']['y'])

    def test_infer_multiple_data(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/deform/pretrained/settings.yml'))

        def conversion_function(fem_data, raw_directory=None):
            adj = fem_data.calculate_adjacency_matrix_element()
            nadj = prepost.normalize_adjacency_matrix(adj)
            return {'adj': adj, 'nadj': nadj}

        ir = inferer.Inferer(
            main_setting, conversion_function=conversion_function,
            converter_parameters_pkl=Path(
                'tests/data/deform/preprocessed/preprocessors.pkl'))
        ir.setting.inferer.save = True
        ir.setting.inferer.perform_preprocess = False
        ir.setting.inferer.write_simulation = True
        ir.setting.inferer.write_simulation_base = Path(
            'tests/data/deform/raw')
        ir.setting.inferer.write_simulation_type = 'ucd'

        output_directory_base = Path('tests/data/deform/inferred/multiple')
        if output_directory_base.exists():
            shutil.rmtree(output_directory_base)
        res_from_raw = ir.infer(
            model=Path('tests/data/deform/pretrained'),
            data_directories=Path('tests/data/deform/preprocessed/test'),
            output_directory_base=output_directory_base)

        raw_directory_base = Path('tests/data/deform/raw/test')
        for i_data, data_basename in enumerate([
                'tet2_3_modulusx1.0500', 'tet2_4_modulusx0.9500']):
            raw_directory = glob.glob(
                str(raw_directory_base / f"**/{data_basename}"),
                recursive=True)[0]
            raw_fem_data = femio.FEMData.read_directory(
                'fistr', raw_directory)
            inferred_directory = glob.glob(
                str(output_directory_base / f"**/{data_basename}"),
                recursive=True)[0]
            inferred_fem_data = femio.FEMData.read_directory(
                'ucd', inferred_directory)
            np.testing.assert_almost_equal(
                inferred_fem_data.elemental_data.get_attribute_data(
                    'predicted_elemental_stress'),
                res_from_raw[i_data]['dict_y']['elemental_stress'], decimal=3)
            np.testing.assert_almost_equal(
                res_from_raw[i_data]['dict_answer']['elemental_stress'],
                raw_fem_data.elemental_data.get_attribute_data(
                    'ElementalSTRESS'), decimal=2)
            np.testing.assert_almost_equal(
                inferred_fem_data.elemental_data.get_attribute_data(
                    'predicted_elemental_stress'),
                raw_fem_data.elemental_data.get_attribute_data(
                    'ElementalSTRESS'), decimal=-1)
        return
