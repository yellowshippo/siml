from pathlib import Path
import shutil
import unittest

import numpy as np

import siml.setting as setting
import siml.trainer as trainer


class TestNetwork(unittest.TestCase):

    def test_deepsets(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/linear/deepsets.yml'))
        tr = trainer.Trainer(main_setting)
        if tr.setting.trainer.output_directory.exists():
            shutil.rmtree(tr.setting.trainer.output_directory)
        loss = tr.train()
        np.testing.assert_array_less(loss, 10.)

    def test_deepsets_permutation(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/linear/deepsets.yml'))
        tr = trainer.Trainer(main_setting)
        tr._prepare_training()
        x = np.reshape(np.arange(5*3), (1, 5, 3)).astype(np.float32) * .1

        y_wo_permutation = tr.model(x)

        x_w_permutation = np.concatenate(
            [x[0, None, 2:], x[0, None, :2]], axis=1)
        y_w_permutation = tr.model(x_w_permutation)

        np.testing.assert_almost_equal(
            np.concatenate(
                [
                    y_wo_permutation[0, None, 2:].data,
                    y_wo_permutation[0, None, :2].data],
                axis=1),
            y_w_permutation.data)

    def test_res_gcn(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/deform/res_gcn.yml'))
        tr = trainer.Trainer(main_setting)
        if tr.setting.trainer.output_directory.exists():
            shutil.rmtree(tr.setting.trainer.output_directory)
        loss = tr.train()
        np.testing.assert_array_less(loss, 5.)

    def test_nri(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/deform/nri.yml'))
        tr = trainer.Trainer(main_setting)
        if tr.setting.trainer.output_directory.exists():
            shutil.rmtree(tr.setting.trainer.output_directory)
        loss = tr.train()
        np.testing.assert_array_less(loss, 1.)

    def test_reduce(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/deform/reduce.yml'))
        tr = trainer.Trainer(main_setting)
        if tr.setting.trainer.output_directory.exists():
            shutil.rmtree(tr.setting.trainer.output_directory)
        loss = tr.train()
        np.testing.assert_array_less(loss, 1.)

    def test_reduce_mlp(self):
        main_setting = setting.MainSetting.read_settings_yaml(
            Path('tests/data/deform/reduce_mlp.yml'))
        tr = trainer.Trainer(main_setting)
        if tr.setting.trainer.output_directory.exists():
            shutil.rmtree(tr.setting.trainer.output_directory)
        loss = tr.train()
        np.testing.assert_array_less(loss, 1.)