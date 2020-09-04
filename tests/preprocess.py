import pathlib
import shutil

import femio
import matplotlib.pyplot as plt
import numpy as np
import siml.prepost as prepost
import siml.setting as setting


PLOT = False


def conversion_function(fem_data, data_directory):
    adj = fem_data.calculate_adjacency_matrix_element()
    nadj = prepost.normalize_adjacency_matrix(adj)
    x_grad, y_grad, z_grad = \
        fem_data.calculate_spatial_gradient_adjacency_matrices('elemental')
    x_grad_2, y_grad_2, z_grad_2 = \
        fem_data.calculate_spatial_gradient_adjacency_matrices(
            'elemental', n_hop=2)
    global_modulus = np.mean(
        fem_data.elemental_data.get_attribute_data('modulus'), keepdims=True)

    tensor_stress = fem_data.convert_array2symmetric_matrix(
        fem_data.elemental_data.get_attribute_data('ElementalSTRESS'),
        from_engineering=False)[:, :, :, None]
    tensor_strain = fem_data.convert_array2symmetric_matrix(
        fem_data.elemental_data.get_attribute_data('ElementalSTRAIN'),
        from_engineering=True)[:, :, :, None]
    tensor_gauss_strain1 = fem_data.convert_array2symmetric_matrix(
        fem_data.elemental_data.get_attribute_data('GaussSTRAIN1'),
        from_engineering=True)[:, :, :, None]
    tensor_gauss_strain2 = fem_data.convert_array2symmetric_matrix(
        fem_data.elemental_data.get_attribute_data('GaussSTRAIN2'),
        from_engineering=True)[:, :, :, None]
    tensor_gauss_strain3 = fem_data.convert_array2symmetric_matrix(
        fem_data.elemental_data.get_attribute_data('GaussSTRAIN3'),
        from_engineering=True)[:, :, :, None]
    tensor_gauss_strain4 = fem_data.convert_array2symmetric_matrix(
        fem_data.elemental_data.get_attribute_data('GaussSTRAIN4'),
        from_engineering=True)[:, :, :, None]
    return {
        'adj': adj, 'nadj': nadj, 'global_modulus': global_modulus,
        'x_grad': x_grad, 'y_grad': y_grad, 'z_grad': z_grad,
        'x_grad_2': x_grad_2, 'y_grad_2': y_grad_2, 'z_grad_2': z_grad_2,
        'tensor_stress': tensor_stress, 'tensor_strain': tensor_strain,
        'tensor_gauss_strain1': tensor_gauss_strain1,
        'tensor_gauss_strain2': tensor_gauss_strain2,
        'tensor_gauss_strain3': tensor_gauss_strain3,
        'tensor_gauss_strain4': tensor_gauss_strain4,
    }


def conversion_function_heat_time_series(fem_data, raw_directory=None):
    nodal_grad_x, nodal_grad_y, nodal_grad_z = \
        fem_data.calculate_spatial_gradient_adjacency_matrices(
            'nodal', n_hop=2)
    nodal_laplacian = (
        nodal_grad_x.dot(nodal_grad_x)
        + nodal_grad_y.dot(nodal_grad_y)
        + nodal_grad_z.dot(nodal_grad_z)).tocoo() / 6

    temperature = fem_data.nodal_data.get_attribute_data('TEMPERATURE')
    raw_conductivity = fem_data.elemental_data.get_attribute_data(
        'thermal_conductivity')
    elemental_conductivity = np.array([a[0][:, 0] for a in raw_conductivity])
    nodal_conductivity = fem_data.convert_elemental2nodal(
        elemental_conductivity, mode='mean')
    global_conductivity = np.mean(
        elemental_conductivity, axis=0, keepdims=True)
    dict_data = {
        f"t_{i}": t for i, t in enumerate(temperature)}
    dict_data.update({
        'nodal_grad_x': nodal_grad_x,
        'nodal_grad_y': nodal_grad_y,
        'nodal_grad_z': nodal_grad_z,
        'nodal_laplacian': nodal_laplacian,
        'elemental_conductivity': elemental_conductivity,
        'nodal_conductivity': nodal_conductivity,
        'global_conductivity': global_conductivity})
    return dict_data


def conversion_function_rotation_thermal_stress(fem_data, raw_directory=None):
    nodal_grad_x, nodal_grad_y, nodal_grad_z = \
        fem_data.calculate_spatial_gradient_adjacency_matrices(
            'nodal', n_hop=2)
    nodal_hess_xx = nodal_grad_x.dot(nodal_grad_x).tocoo()
    nodal_hess_xy = nodal_grad_x.dot(nodal_grad_y).tocoo()
    nodal_hess_xz = nodal_grad_x.dot(nodal_grad_z).tocoo()
    nodal_hess_yx = nodal_grad_y.dot(nodal_grad_x).tocoo()
    nodal_hess_yy = nodal_grad_y.dot(nodal_grad_y).tocoo()
    nodal_hess_yz = nodal_grad_y.dot(nodal_grad_z).tocoo()
    nodal_hess_zx = nodal_grad_z.dot(nodal_grad_x).tocoo()
    nodal_hess_zy = nodal_grad_z.dot(nodal_grad_y).tocoo()
    nodal_hess_zz = nodal_grad_z.dot(nodal_grad_z).tocoo()

    filter_ = fem_data.filter_first_order_nodes()

    node = fem_data.nodes.data[filter_]
    nodal_mean_volume = fem_data.convert_elemental2nodal(
        fem_data.calculate_element_volumes(), mode='mean')
    nodal_concentrated_volume = fem_data.convert_elemental2nodal(
        fem_data.calculate_element_volumes(), mode='effective')
    initial_temperature = fem_data.nodal_data.get_attribute_data(
        'INITIAL_TEMPERATURE')[filter_]
    cnt_temperature = fem_data.nodal_data.get_attribute_data(
        'CNT_TEMPERATURE')[filter_]

    elemental_lte_array = fem_data.elemental_data.get_attribute_data(
        'linear_thermal_expansion_coefficient_full')
    nodal_lte_array = fem_data.convert_elemental2nodal(
        elemental_lte_array, mode='mean')
    global_lte_array = np.mean(
        elemental_lte_array, axis=0, keepdims=True)

    elemental_lte_mat = fem_data.convert_array2symmetric_matrix(
        elemental_lte_array, from_engineering=True)
    nodal_lte_mat = fem_data.convert_array2symmetric_matrix(
        nodal_lte_array, from_engineering=True)
    global_lte_mat = np.mean(
        elemental_lte_mat, axis=0, keepdims=True)

    elemental_strain_array = fem_data.elemental_data.get_attribute_data(
        'ElementalSTRAIN')
    nodal_strain_array = fem_data.nodal_data.get_attribute_data(
        'NodalSTRAIN')[filter_]
    elemental_strain_mat = fem_data.convert_array2symmetric_matrix(
        elemental_strain_array, from_engineering=True)
    nodal_strain_mat = fem_data.convert_array2symmetric_matrix(
        nodal_strain_array, from_engineering=True)

    dict_data = {
        'nodal_grad_x': nodal_grad_x,
        'nodal_grad_y': nodal_grad_y,
        'nodal_grad_z': nodal_grad_z,
        'nodal_hess_xx': nodal_hess_xx,
        'nodal_hess_xy': nodal_hess_xy,
        'nodal_hess_xz': nodal_hess_xz,
        'nodal_hess_yx': nodal_hess_yx,
        'nodal_hess_yy': nodal_hess_yy,
        'nodal_hess_yz': nodal_hess_yz,
        'nodal_hess_zx': nodal_hess_zx,
        'nodal_hess_zy': nodal_hess_zy,
        'nodal_hess_zz': nodal_hess_zz,
        'node': node,
        'nodal_strain_array': nodal_strain_array,
        'elemental_strain_array': elemental_strain_array,
        'nodal_strain_mat': nodal_strain_mat[..., None],
        'elemental_strain_mat': elemental_strain_mat[..., None],
        'nodal_mean_volume': nodal_mean_volume,
        'nodal_concentrated_volume': nodal_concentrated_volume,
        'initial_temperature': initial_temperature,
        'cnt_temperature': cnt_temperature,
        'elemental_lte_array': elemental_lte_array,
        'nodal_lte_array': nodal_lte_array,
        'global_lte_array': global_lte_array,
        'elemental_lte_mat': elemental_lte_mat[..., None],
        'nodal_lte_mat': nodal_lte_mat[..., None],
        'global_lte_mat': global_lte_mat[..., None],
    }
    return dict_data


def preprocess_deform():
    main_setting = setting.MainSetting.read_settings_yaml(
        pathlib.Path('tests/data/deform/data.yml'))

    raw_converter = prepost.RawConverter(
        main_setting, recursive=True, force_renew=True,
        conversion_function=conversion_function)
    raw_converter.convert()

    preprocessor = prepost.Preprocessor(main_setting, force_renew=True)
    preprocessor.preprocess_interim_data()
    return


def preprocess_rotation_thermal_stress():
    main_setting = setting.MainSetting.read_settings_yaml(
        pathlib.Path('tests/data/rotation_thermal_stress/data.yml'))

    raw_converter = prepost.RawConverter(
        main_setting, recursive=True, force_renew=True,
        to_first_order=True,
        conversion_function=conversion_function_rotation_thermal_stress)
    raw_converter.convert()

    preprocessor = prepost.Preprocessor(main_setting, force_renew=True)
    preprocessor.preprocess_interim_data()
    return


def preprocess_heat_time_series():
    main_setting = setting.MainSetting.read_settings_yaml(
        pathlib.Path('tests/data/heat_time_series/data.yml'))

    raw_converter = prepost.RawConverter(
        main_setting, recursive=True, force_renew=True,
        conversion_function=conversion_function_heat_time_series,
        write_ucd=False)
    raw_converter.convert()

    preprocessor = prepost.Preprocessor(main_setting, force_renew=True)
    preprocessor.preprocess_interim_data()
    return


def preprocess_deform_timeseries():
    main_setting = setting.MainSetting.read_settings_yaml(
        pathlib.Path('tests/data/deform_timeseries/data.yml'))

    preprocessor = prepost.Preprocessor(main_setting, force_renew=True)
    preprocessor.preprocess_interim_data()
    return


def rotation_conversion_function(fem_data, raw_directory):
    nodal_mean_volume = fem_data.convert_elemental2nodal(
        fem_data.calculate_element_volumes(), mode='mean')
    nodal_concentrated_volume = fem_data.convert_elemental2nodal(
        fem_data.calculate_element_volumes(), mode='effective')

    nodal_grad_x, nodal_grad_y, nodal_grad_z = \
        fem_data.calculate_spatial_gradient_adjacency_matrices(
            'nodal', n_hop=2)
    nodal_laplacian = (
        nodal_grad_x.dot(nodal_grad_x)
        + nodal_grad_y.dot(nodal_grad_y)
        + nodal_grad_z.dot(nodal_grad_z)).tocoo() / 6
    node = fem_data.nodes.data
    t_init = fem_data.nodal_data.get_attribute_data('t_init')
    ucd_data = femio.FEMData.read_files(
        'ucd', [raw_directory / 'mesh_vis_psf.0100.inp'])
    t_100 = ucd_data.nodal_data.get_attribute_data('TEMPERATURE')
    return {
        'nodal_mean_volume': nodal_mean_volume,
        'nodal_concentrated_volume': nodal_concentrated_volume,
        'nodal_grad_x': nodal_grad_x,
        'nodal_grad_y': nodal_grad_y,
        'nodal_grad_z': nodal_grad_z,
        'nodal_laplacian': nodal_laplacian,
        'node': node, 't_init': t_init, 't_100': t_100}


def preprocess_rotation():
    main_setting = setting.MainSetting.read_settings_yaml(
        pathlib.Path('tests/data/rotation/data.yml'))

    raw_converter = prepost.RawConverter(
        main_setting, recursive=True, force_renew=True,
        conversion_function=rotation_conversion_function)
    raw_converter.convert()

    preprocessor = prepost.Preprocessor(main_setting, force_renew=True)
    preprocessor.preprocess_interim_data()
    return


def preprocess_linear():
    p = prepost.Preprocessor.read_settings(
        pathlib.Path('tests/data/linear/linear.yml'), force_renew=True)
    p.preprocess_interim_data()
    return


def generate_ode():
    time_range = (10., 50.)
    delta_t = .1

    def f0(ts, xs):
        ys = np.zeros(list(xs.shape[:2]) + [1])
        ys[0] = np.random.rand(*list(ys.shape)[1:])
        for i in range(1, len(ts)):
            ys[i, :, 0] = ys[i - 1, :, 0] + delta_t * (- .1 * ys[i - 1, :, 0])
        return ys

    def f1(ts, xs):
        ys = np.zeros(list(xs.shape[:2]) + [1])
        ys[0] = np.random.rand(*list(ys.shape)[1:])
        for i in range(1, len(ts)):
            ys[i, :, 0] = ys[i - 1, :, 0] + delta_t * xs[i, :, 0] * .1
        return ys

    def f2(ts, xs):
        ys = np.zeros(list(xs.shape[:2]) + [1])
        ys[0] = np.random.rand(*list(ys.shape)[1:])
        for i in range(1, len(ts)):
            ys[i, :, 0] = ys[i - 1, :, 0] + delta_t * (
                .01 * xs[i, :, 1] - .01 * xs[i, :, 0] * xs[i, :, 3]
                - .01 * ys[i - 1, :, 0])
        return ys

    def f3(ts, xs):
        ys = np.zeros(list(xs.shape[:2]) + [2])
        ys[0] = np.random.rand(*list(ys.shape)[1:]) * 2 - 1
        for i in range(1, len(ts)):
            ys[i, :, 0] = ys[i - 1, :, 0] + delta_t * (
                - .05 * ys[i - 1, :, 1]
                + .01 * (1 - ys[i - 1, :, 1]**2) * ys[i - 1, :, 0])
            ys[i, :, 1] = ys[i - 1, :, 1] + delta_t * ys[i - 1, :, 0]
        return ys

    def generate_ode(root_dir, n_data):
        if root_dir.exists():
            shutil.rmtree(root_dir)

        for i in range(n_data):
            n_element = np.random.randint(3, 10)
            t_max = np.random.rand() * (
                time_range[1] - time_range[0]) + time_range[0]
            ts = np.arange(0., t_max, delta_t)
            x0 = np.random.rand() * np.sin(
                2 * np.pi * (np.random.rand() / 10. * ts + np.random.rand()))
            x1 = np.random.rand() * np.sin(
                2 * np.pi * (np.random.rand() / 20. * ts + np.random.rand()))
            x2 = np.random.rand() * (
                1 - np.exp(- ts / 5. * np.random.rand())) + np.random.rand()
            x3 = np.exp(- ts / 10. * np.random.rand()) + np.random.rand()
            _xs = np.stack([x0, x1, x2, x3], axis=1)[:, None, :]
            xs = np.concatenate([
                _xs * a for a in np.linspace(1., 2., n_element)], axis=1)

            y0 = f0(ts, xs)
            y1 = f1(ts, xs)
            y2 = f2(ts, xs)
            y3 = f3(ts, xs)

            stacked_ts = np.concatenate(
                [ts[:, None, None]] * n_element, axis=1)

            output_directory = root_dir / f"{i}"
            output_directory.mkdir(parents=True)
            np.save(output_directory / 't.npy', stacked_ts.astype(np.float32))
            np.save(output_directory / 'x.npy', xs.astype(np.float32))
            np.save(output_directory / 'y0.npy', y0.astype(np.float32))
            np.save(output_directory / 'y1.npy', y1.astype(np.float32))
            np.save(output_directory / 'y2.npy', y2.astype(np.float32))
            np.save(output_directory / 'y3.npy', y3.astype(np.float32))
            np.save(
                output_directory / 'y0_initial.npy',
                (np.ones(y0.shape) * y0[0, :, :]).astype(np.float32))
            np.save(
                output_directory / 'y1_initial.npy',
                (np.ones(y1.shape) * y1[0, :, :]).astype(np.float32))
            np.save(
                output_directory / 'y2_initial.npy',
                (np.ones(y2.shape) * y2[0, :, :]).astype(np.float32))
            np.save(
                output_directory / 'y3_initial.npy',
                (np.ones(y3.shape) * y3[0, :, :]).astype(np.float32))
            (output_directory / 'converted').touch()

            if PLOT:
                plt.plot(ts, x0, label='x0')
                plt.plot(ts, x1, label='x1')
                plt.plot(ts, x2, label='x2')
                plt.plot(ts, x3, label='x3')
                plt.plot(ts, y0[:, 0, 0], label='y0')
                plt.plot(ts, y1[:, 0, 0], label='y1')
                plt.plot(ts, y2[:, 0, 0], label='y2')
                plt.plot(ts, y3[:, 0, 0], label='y3-0')
                plt.plot(ts, y3[:, 0, 1], label='y3-1')
                plt.legend()
                plt.savefig(output_directory / 'plot.pdf')
                plt.show()
        return

    generate_ode(pathlib.Path('tests/data/ode/interim/train'), 100)
    generate_ode(pathlib.Path('tests/data/ode/interim/validation'), 10)
    generate_ode(pathlib.Path('tests/data/ode/interim/test'), 10)

    main_setting = setting.MainSetting.read_settings_yaml(
        pathlib.Path('tests/data/ode/data.yml'))
    preprocessor = prepost.Preprocessor(main_setting, force_renew=True)
    preprocessor.preprocess_interim_data()
    return


def generate_large():
    n_feat = 10
    n_element = 2000

    def generate_data(root_dir, n_data):
        if root_dir.exists():
            shutil.rmtree(root_dir)
        for i in range(n_data):
            r1 = np.random.rand()
            r2 = np.random.rand()
            floor = min(r1, r2)
            ceil = max(r1, r2)

            x = np.random.rand(n_element, n_feat) * (ceil - floor) + floor
            y = np.sin(x * 4. * np.pi)

            output_directory = root_dir / f"{i}"
            output_directory.mkdir(parents=True)
            np.save(output_directory / 'x.npy', x.astype(np.float32))
            np.save(output_directory / 'y.npy', y.astype(np.float32))

    output_root = pathlib.Path('tests/data/large/preprocessed')
    train_root = output_root / 'train'
    n_train_data = 20
    generate_data(train_root, n_train_data)

    validation_root = output_root / 'validation'
    n_validation_data = 2
    generate_data(validation_root, n_validation_data)

    test_root = output_root / 'test'
    n_test_data = 2
    generate_data(test_root, n_test_data)
    return


if __name__ == '__main__':
    preprocess_rotation_thermal_stress()
    preprocess_heat_time_series()
    generate_ode()
    preprocess_deform()
    preprocess_deform_timeseries()
    preprocess_rotation()
    preprocess_linear()
    generate_large()
