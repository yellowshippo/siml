from pathlib import Path
import shutil
import unittest

import numpy as np
import pandas as pd

import siml.prepost as pre
import siml.setting as setting
import siml.trainer as trainer
import siml.util as util


def load_function(data_files, data_directory):
    # To be used in test_convert_raw_data_bypass_femio
    df = pd.read_csv(data_files[0], header=0, index_col=None)
    return {
        'a': np.reshape(df['a'].to_numpy(), (-1, 1)),
        'b': np.reshape(df['b'].to_numpy(), (-1, 1)),
        'c': np.reshape(df['c'].to_numpy(), (-1, 1))}, None


def conversion_function(fem_data, raw_directory=None):
    # To be used in test_preprocess_deform
    adj, _ = fem_data.calculate_adjacency_matrix_element()
    nadj = pre.normalize_adjacency_matrix(adj)
    global_modulus = np.mean(
        fem_data.access_attribute('modulus'), keepdims=True)
    return {'adj': adj, 'nadj': nadj, 'global_modulus': global_modulus}


def filter_function(fem_data, raw_directory=None, data_dict=None):
    # To be used in test_convert_raw_data_with_filter_function
    strain = fem_data.access_attribute('ElementalSTRAIN')
    return np.max(np.abs(strain)) < 1e2


class TestPrepost(unittest.TestCase):

    def test_determine_output_directory(self):
        self.assertEqual(
            pre.determine_output_directory(
                Path('data/raw/a/b'), Path('test/sth'), 'raw'),
            Path('test/sth/a/b'))

    def test_normalize_adjacency_matrix(self):
        adj = np.array([
            [2., 1., 0.],
            [1., 10., 5.],
            [0., 5., 100.],
        ])
        nadj = pre.normalize_adjacency_matrix(adj)
        d_inv_sqrt = np.array([
            [3.**-.5, 0., 0.],
            [0., 16.**-.5, 0.],
            [0., 0., 105.**-.5],
        ])
        np.testing.assert_almost_equal(
            d_inv_sqrt @ adj @ d_inv_sqrt, nadj.toarray())

    def test_split_data_arrays(self):
        true_xs = [
            np.concatenate([
                np.stack([[0., 0.]] * 10000),
                np.stack([[1., 0.]] * 10000),
                np.stack([[0., 1.]] * 10000),
                np.stack([[1., 1.]] * 10000),
            ]),
            np.concatenate([
                np.stack([[0., 0.]] * 10000),
                np.stack([[1., 0.]] * 10000),
                np.stack([[0., 1.]] * 10000),
            ]),
        ]
        noised_xs = [
            np.concatenate([
                np.array([
                    [-.5, -.5],
                    [1.5, 1.5],
                ]),
                true_x + np.random.randn(*true_x.shape) * .1])
            for true_x in true_xs]
        fs = [noised_xs[0], noised_xs[1] / 2]
        ranges, list_split_data, centers, means, stds, coverage \
            = pre.split_data_arrays(noised_xs, fs, n_split=3)

        array_means = np.transpose(np.stack(means), (1, 0, 2))
        array_stds = np.transpose(np.stack(stds), (1, 0, 2))
        answer = np.array([
            [0., 0.],
            [0., 1.],
            [1., 0.],
        ])
        np.testing.assert_array_almost_equal(centers, answer, decimal=1)
        np.testing.assert_array_almost_equal(
            array_means[0], answer, decimal=1)
        np.testing.assert_array_almost_equal(
            array_means[1], answer * .5, decimal=1)
        np.testing.assert_array_almost_equal(
            array_stds[0], np.ones(array_stds.shape[1:]) * .1, decimal=1)
        np.testing.assert_array_almost_equal(
            array_stds[1], np.ones(array_stds.shape[1:]) * .05, decimal=1)

    def test_convert_raw_data_bypass_femio(self):
        data_setting = setting.DataSetting(
            raw=Path('tests/data/csv_prepost/raw'),
            interim=Path('tests/data/csv_prepost/interim'))
        conversion_setting = setting.ConversionSetting(
            required_file_names=['*.csv'], skip_femio=True)

        main_setting = setting.MainSetting(
            data=data_setting, conversion=conversion_setting)

        shutil.rmtree(data_setting.interim, ignore_errors=True)
        shutil.rmtree(data_setting.preprocessed, ignore_errors=True)

        rc = pre.RawConverter(
            main_setting, recursive=True, load_function=load_function)
        rc.convert()

        interim_directory = data_setting.interim / 'train/1'
        expected_a = np.array([[1], [2], [3], [4]])
        expected_b = np.array([[2.1], [4.1], [6.1], [8.1]])
        expected_c = np.array([[3.2], [7.2], [8.2], [10.2]])
        np.testing.assert_almost_equal(
            np.load(interim_directory / 'a.npy'), expected_a)
        np.testing.assert_almost_equal(
            np.load(interim_directory / 'b.npy'), expected_b, decimal=5)
        np.testing.assert_almost_equal(
            np.load(interim_directory / 'c.npy'), expected_c, decimal=5)

    def test_preprocessor(self):
        data_setting = setting.DataSetting(
            interim=Path('tests/data/prepost/interim'),
            preprocessed=Path('tests/data/prepost/preprocessed'),
            pad=False
        )
        preprocess_setting = setting.PreprocessSetting(
            {
                'identity': 'identity', 'std_scale': 'std_scale',
                'standardize': 'standardize'}
        )
        main_setting = setting.MainSetting(
            preprocess=preprocess_setting.preprocess, data=data_setting)

        # Clean up data
        shutil.rmtree(data_setting.interim, ignore_errors=True)
        shutil.rmtree(data_setting.preprocessed, ignore_errors=True)
        data_setting.preprocessed.mkdir(parents=True)

        # Create data
        interim_paths = [
            data_setting.interim / 'a',
            data_setting.interim / 'b']
        for i, interim_path in enumerate(interim_paths):
            interim_path.mkdir(parents=True)
            n_element = int(1e5)
            identity = np.random.randint(2, size=(n_element, 1))
            std_scale = np.random.rand(n_element, 3) * 5 * i
            standardize = np.random.randn(n_element, 5) * 2 * i \
                + i * np.array([[.1, .2, .3, .4, .5]])
            np.save(interim_path / 'identity.npy', identity)
            np.save(interim_path / 'std_scale.npy', std_scale)
            np.save(interim_path / 'standardize.npy', standardize)
            (interim_path / 'converted').touch()

        # Preprocess data
        preprocessor = pre.Preprocessor(main_setting)
        preprocessor.preprocess_interim_data()

        # Test preprocessed data is as desired
        epsilon = 1e-5
        preprocessed_paths = [
            data_setting.preprocessed / 'a',
            data_setting.preprocessed / 'b']

        int_identity = np.concatenate([
            np.load(p / 'identity.npy') for p in interim_paths])
        pre_identity = np.concatenate([
            np.load(p / 'identity.npy') for p in preprocessed_paths])

        np.testing.assert_almost_equal(
            int_identity, pre_identity, decimal=3)

        int_std_scale = np.concatenate([
            np.load(p / 'std_scale.npy') for p in interim_paths])
        pre_std_scale = np.concatenate([
            np.load(p / 'std_scale.npy') for p in preprocessed_paths])

        np.testing.assert_almost_equal(
            int_std_scale / (np.std(int_std_scale, axis=0) + epsilon),
            pre_std_scale, decimal=3)
        np.testing.assert_almost_equal(
            np.std(pre_std_scale), 1. + epsilon, decimal=3)

        int_standardize = np.concatenate([
            np.load(p / 'standardize.npy') for p in interim_paths])
        pre_standardize = np.concatenate([
            np.load(p / 'standardize.npy') for p in preprocessed_paths])

        np.testing.assert_almost_equal(
            (int_standardize - np.mean(int_standardize, axis=0))
            / (np.std(int_standardize, axis=0) + epsilon),
            pre_standardize, decimal=3)
        np.testing.assert_almost_equal(
            np.std(pre_standardize, axis=0), 1. + epsilon, decimal=3)
        np.testing.assert_almost_equal(
            np.mean(pre_standardize, axis=0), np.zeros(5), decimal=3)

    def test_postprocessor(self):
        data_setting = setting.DataSetting(
            interim=Path('tests/data/prepost/interim'),
            preprocessed=Path('tests/data/prepost/preprocessed'),
            pad=False
        )
        preprocess_setting = setting.PreprocessSetting(
            {
                'identity': 'identity', 'std_scale': 'std_scale',
                'standardize': 'standardize'}
        )
        main_setting = setting.MainSetting(
            preprocess=preprocess_setting.preprocess, data=data_setting)

        # Clean up data
        shutil.rmtree(data_setting.interim, ignore_errors=True)
        shutil.rmtree(data_setting.preprocessed, ignore_errors=True)
        data_setting.preprocessed.mkdir(parents=True)

        # Create data
        interim_paths = [
            data_setting.interim / 'a',
            data_setting.interim / 'b']
        for i, interim_path in enumerate(interim_paths):
            interim_path.mkdir(parents=True)
            n_element = np.random.randint(1e4)
            identity = np.random.randint(2, size=(n_element, 1))
            std_scale = np.random.rand(n_element, 3) * 5 * i
            standardize = np.random.randn(n_element, 5) * 2 * i \
                + i * np.array([[.1, .2, .3, .4, .5]])
            np.save(interim_path / 'identity.npy', identity)
            np.save(interim_path / 'std_scale.npy', std_scale)
            np.save(interim_path / 'standardize.npy', standardize)
            (interim_path / 'converted').touch()

        # Preprocess data
        preprocessor = pre.Preprocessor(main_setting)
        preprocessor.preprocess_interim_data()

        postprocessor = pre.Converter(
            data_setting.preprocessed / 'preprocessors.pkl')
        preprocessed_paths = [
            data_setting.preprocessed / 'a',
            data_setting.preprocessed / 'b']
        for interim_path, preprocessed_path in zip(
                interim_paths, preprocessed_paths):
            dict_data_x = {
                'identity': np.load(preprocessed_path / 'identity.npy'),
                'std_scale': np.load(preprocessed_path / 'std_scale.npy')}
            dict_data_y = {
                'standardize': np.load(preprocessed_path / 'standardize.npy')}
            inv_dict_data_x, inv_dict_data_y = postprocessor.postprocess(
                dict_data_x, dict_data_y)
            for k, v in inv_dict_data_x.items():
                interim_data = np.load(interim_path / (k + '.npy'))
                np.testing.assert_almost_equal(interim_data, v, decimal=5)
            for k, v in inv_dict_data_y.items():
                interim_data = np.load(interim_path / (k + '.npy'))
                np.testing.assert_almost_equal(interim_data, v, decimal=5)

    def test_preprocess_deform(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/deform/data.yml'))
        main_setting.data.interim = Path(
            'tests/data/deform/test_prepost/interim')
        main_setting.data.preprocessed = Path(
            'tests/data/deform/test_prepost/preprocessed')

        shutil.rmtree(main_setting.data.interim, ignore_errors=True)
        shutil.rmtree(main_setting.data.preprocessed, ignore_errors=True)

        raw_converter = pre.RawConverter(
            main_setting, conversion_function=conversion_function)
        raw_converter.convert()
        p = pre.Preprocessor(main_setting)
        p.preprocess_interim_data()

    def test_convert_raw_data_with_filter_function(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/test_prepost_to_filter/data.yml'))
        shutil.rmtree(main_setting.data.interim, ignore_errors=True)

        raw_converter = pre.RawConverter(
            main_setting, filter_function=filter_function)
        raw_converter.convert()

        actual_directories = sorted(util.collect_data_directories(
            main_setting.data.interim,
            required_file_names=['elemental_strain.npy']))
        expected_directories = sorted([
            main_setting.data.interim / 'tet2_3_modulusx0.9000',
            main_setting.data.interim / 'tet2_3_modulusx1.1000',
            main_setting.data.interim / 'tet2_4_modulusx1.0000',
            main_setting.data.interim / 'tet2_4_modulusx1.1000'])
        np.testing.assert_array_equal(actual_directories, expected_directories)

    def test_generate_converters(self):
        preprocessors_file = Path('tests/data/prepost/preprocessors.pkl')
        real_file_converter = pre.Converter(preprocessors_file)
        with open(preprocessors_file, 'rb') as f:
            file_like_object_converter = pre.Converter(f)
        np.testing.assert_almost_equal(
            real_file_converter.converters['standardize'].converter.var_,
            file_like_object_converter.converters[
                'standardize'].converter.var_)

    def test_concatenate_preprocessed_data(self):
        preprocessed_base_directory = Path(
            'tests/data/linear/preprocessed/train')
        concatenated_directory = Path('tests/data/linear/concatenated')
        shutil.rmtree(concatenated_directory, ignore_errors=True)

        pre.concatenate_preprocessed_data(
            preprocessed_base_directory, concatenated_directory,
            variable_names=['x1', 'x2', 'y'], ratios=(1., 0., 0.))

        for name in ['x1', 'x2', 'y']:
            actual = np.load(concatenated_directory / f"train/{name}.npy")
            answer = np.concatenate([
                np.load(preprocessed_base_directory / f"0/{name}.npy"),
                np.load(preprocessed_base_directory / f"1/{name}.npy")])
            np.testing.assert_almost_equal(
                np.max(actual), np.max(answer), decimal=5)
            np.testing.assert_almost_equal(
                np.min(actual), np.min(answer), decimal=5)
            np.testing.assert_almost_equal(
                np.std(actual), np.std(answer), decimal=5)
            np.testing.assert_almost_equal(
                np.mean(actual), np.mean(answer), decimal=5)

    def test_train_concatenated_data(self):
        preprocessed_base_directory = Path(
            'tests/data/linear/preprocessed/train')
        concatenated_directory = Path('tests/data/linear/concatenated')
        shutil.rmtree(concatenated_directory, ignore_errors=True)

        pre.concatenate_preprocessed_data(
            preprocessed_base_directory, concatenated_directory,
            variable_names=['x1', 'x2', 'y'], ratios=(.9, 0.1, 0.))

        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/linear/linear_concatenated.yml'))
        tr = trainer.Trainer(main_setting)
        if tr.setting.trainer.output_directory.exists():
            shutil.rmtree(tr.setting.trainer.output_directory)
        loss = tr.train()
        np.testing.assert_array_less(loss, 1e-5)

    def test_preprocess_timeseries_data(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/csv_timeseries/lstm.yml'))

        shutil.rmtree(main_setting.data.preprocessed, ignore_errors=True)

        p = pre.Preprocessor(main_setting)
        p.preprocess_interim_data()

        c = pre.Converter(
            main_setting.data.preprocessed / 'preprocessors.pkl')
        original_dict_x = {
            'a': np.load(main_setting.data.interim / 'train/0/a.npy')}
        preprocessed_dict_x = c.preprocess(original_dict_x)
        postprocessed_dict_x, _ = c.postprocess(preprocessed_dict_x, {})
        np.testing.assert_almost_equal(
            preprocessed_dict_x['a'],
            np.load(main_setting.data.preprocessed / 'train/0/a.npy'))
        np.testing.assert_almost_equal(
            original_dict_x['a'], postprocessed_dict_x['a'])
