import dataclasses as dc
from pathlib import Path
import typing
from enum import Enum

import numpy as np
import optuna
import yaml

from . import util


@dc.dataclass
class TypedDataClass:

    @classmethod
    def read_settings_yaml(cls, settings_yaml):
        settings_yaml = Path(settings_yaml)

        dict_settings = util.load_yaml_file(settings_yaml)
        return cls(**dict_settings)

    def convert(self):
        """Convert all fields accordingly with their type definitions.  """
        for field_name, field in self.__dataclass_fields__.items():
            try:
                self._convert_field(field_name, field)
            except TypeError:
                raise TypeError(
                    f"Can't convert {getattr(self, field_name)} to "
                    f"{field.type} for {field_name}")

    def validate(self):
        for field_name, field in self.__dataclass_fields__.items():
            if not self._validate_field(field_name, field):
                raise TypeError(
                    f"{field_name} is not an instance of {field.type} "
                    f"(actual: {getattr(self, field_name).__class__})"
                )

    def _convert_field(self, field_name, field):
        if 'convert' in field.metadata and not field.metadata['convert']:
            return
        if 'allow_none' in field.metadata and field.metadata['allow_none'] \
                and getattr(self, field_name) is None:
            return

        if field.type == typing.List[Path]:
            def type_function(x):
                return [Path(_x) for _x in x]
        elif field.type == typing.List[str]:
            def type_function(x):
                return [str(_x) for _x in x]
        elif field.type == typing.List[int]:
            def type_function(x):
                return [int(_x) for _x in x]
        elif field.type == typing.List[float]:
            def type_function(x):
                return [float(_x) for _x in x]
        elif field.type == typing.List[dict]:
            def type_function(x):
                return [dict(_x) for _x in x]
        elif field.type == slice:
            def type_function(x):
                if isinstance(x, slice):
                    return x
                else:
                    return slice(*x)
        else:
            type_function = field.type

        setattr(
            self, field_name, type_function(getattr(self, field_name)))

    def _validate_field(self, field_name, field):
        return isinstance(getattr(self, field_name), field.type)

    def __post_init__(self):
        self.convert()
        # self.validate()


@dc.dataclass
class DataSetting(TypedDataClass):

    raw: Path = Path('data/raw')
    interim: Path = Path('data/interim')
    preprocessed: Path = Path('data/preprocessed')
    inferred: Path = Path('data/inferred')
    train: typing.List[Path] = dc.field(
        default_factory=lambda: [Path('data/preprocessed/train')])
    validation: typing.List[Path] = dc.field(
        default_factory=lambda: [Path('data/preprocessed/validation')])
    test: typing.List[Path] = dc.field(
        default_factory=lambda: [Path('data/preprocessed/test')])
    pad: bool = False

    def __post_init__(self):
        if self.pad:
            raise ValueError(
                f"pad = True option is deprecated. Set pad = False")
        super().__post_init__()


@dc.dataclass
class DBSetting(TypedDataClass):
    servername: str
    username: str
    password: str
    use_sqlite: bool = False


class Iter(Enum):
    SERIAL = 'serial'
    MULTIPROCESS = 'multiprocess'
    MULTITHREAD = 'multithread'


@dc.dataclass
class TrainerSetting(TypedDataClass):

    """
    inputs: list of dict
        Variable names of inputs.
    outputs: list of dict
        Variable names of outputs.
    train_directories: list of str or pathlib.Path
        Training data directories.
    output_directory: str or pathlib.Path
        Output directory name.
    validation_directories: list of str or pathlib.Path, optional [[]]
        Validation data directories.
    restart_directory: str or pathlib.Path, optional [None]
        Directory name to be used for restarting.
    pretrain_directory: str or pathlib.Path, optional [None]
        Pretrained directory name.
    loss_function: chainer.FunctionNode,
            optional [chainer.functions.mean_squared_error]
        Loss function to be used for training.
    optimizer: chainer.Optimizer, optional [chainer.optimizers.Adam]
        Optimizer to be used for training.
    compute_accuracy: bool, optional [False]
        If True, compute accuracy.
    batch_size: int, optional [1]
        Batch size for train dataset.
    validation_batch_size: int, optional [1]
        Batch size for validation dataset.
    n_epoch: int, optional [1000]
        The number of epochs.
    gpu_id: int, optional [-1]
        GPU ID. Specify non negative value to use GPU. -1 Meaning CPU.
    log_trigger_epoch: int, optional [1]
        The interval of logging of training. It is used for logging,
        plotting, and saving snapshots.
    stop_trigger_epoch: int, optional [10]
        The interval to check if training should be stopped. It is used
        for early stopping and pruning.
    optuna_trial: optuna.Trial, optional [None]
        Trial object used to perform optuna hyper parameter tuning.
    prune: bool, optional [False]
        If True and optuna_trial is given, prining would be performed.
    seed: str, optional [0]
        Random seed.
    element_wise: bool, optional [False]
        If True, concatenate data to force element wise training
        (so no graph information can be used). With this option,
        element_batch_size will be used for trainer's batch size as it is
        "element wise" training.
    element_batch_size: int, optional [-1]
        If positive, split one mesh int element_batch_size and perform update
        multiple times for one mesh. In case of element_wise is True,
        element_batch_size is the batch size in the usual sence.
    validation_element_batch_size: int, optional [-1]
        element_batch_size for validation dataset.
    simplified_model: bool, optional [False]
        If True, regard the target simulation as simplified simulation
        (so-called "1D simulation"), which focuses on only a few inputs and
        outputs. The behavior of the trainer will be similar to that with
        element_wise = True.
    time_series: bool, optional [False]
        If True, regard the data as time series. In that case, the data shape
        will be [seq, batch, element, feature] instead of the default
        [batch, element, feature] shape.
    lazy: bool, optional [True]
        If True, load data lazily.
    num_workers: int, optional [None]
        The number of workers to load data.
    display_mergin: int, optional [5]
    non_blocking: bool [True]
        If True and this copy is between CPU and GPU, the copy may occur
        asynchronously with respect to the host. For other cases, this argument
        has no effect.
    """

    inputs: typing.List[dict] = dc.field(default_factory=list)
    support_input: str = dc.field(default=None, metadata={'allow_none': True})
    support_inputs: typing.List[str] = dc.field(
        default=None, metadata={'allow_none': True})
    outputs: typing.List[dict] = dc.field(default_factory=list)

    input_names: typing.List[str] = dc.field(
        default=None, metadata={'allow_none': True})
    input_dims: typing.List[int] = dc.field(
        default=None, metadata={'allow_none': True})
    output_names: typing.List[str] = dc.field(
        default=None, metadata={'allow_none': True})
    output_dims: typing.List[int] = dc.field(
        default=None, metadata={'allow_none': True})
    output_directory: Path = None

    name: str = 'default'
    batch_size: int = 1
    validation_batch_size: int = dc.field(
        default=None, metadata={'allow_none': True})
    n_epoch: int = 100

    validation_directories: typing.List[Path] = dc.field(
        default_factory=lambda: [])
    restart_directory: Path = dc.field(
        default=None, metadata={'allow_none': True})
    pretrain_directory: Path = dc.field(
        default=None, metadata={'allow_none': True})
    loss_function: str = 'mse'
    optimizer: str = 'adam'
    compute_accuracy: bool = False
    gpu_id: int = -1
    log_trigger_epoch: int = 1
    stop_trigger_epoch: int = 10
    patience: int = 3
    optuna_trial: optuna.Trial = dc.field(
        default=None, metadata={'convert': False, 'allow_none': True})
    prune: bool = False
    snapshot_choise_method: str = 'best'
    seed: int = 0
    element_wise: bool = False
    simplified_model: bool = False
    time_series: bool = False
    element_batch_size: int = -1
    validation_element_batch_size: int = dc.field(
        default=None, metadata={'allow_none': True})
    use_siml_updater: bool = True
    iterator: Iter = Iter.SERIAL
    optimizer_setting: dict = dc.field(
        default=None, metadata={'convert': False, 'allow_none': True})
    lazy: bool = True
    num_workers: int = dc.field(
        default=None, metadata={'allow_none': True})
    display_mergin: int = 5
    non_blocking: bool = True

    def __post_init__(self):
        if self.element_wise and self.lazy:
            self.lazy = False
            print('element_wise = True found. Overwrite lazy = False.')
        if self.simplified_model and self.lazy:
            raise ValueError(
                'Both simplified_model and lazy cannot be True '
                'at the same time')

        if self.validation_batch_size is None:
            self.validation_batch_size = self.batch_size

        if self.validation_element_batch_size is None:
            self.validation_element_batch_size = self.element_batch_size

        self.input_names = [i['name'] for i in self.inputs]
        self.input_dims = [i['dim'] for i in self.inputs]
        self.output_names = [o['name'] for o in self.outputs]
        self.output_dims = [o['dim'] for o in self.outputs]

        if self.output_directory is None:
            self.update_output_directory()
        if self.support_input is not None:
            if self.support_inputs is not None:
                raise ValueError(
                    'Both support_input and support_inputs cannot be '
                    'specified.')
            else:
                self.support_inputs = [self.support_input]
        if self.optimizer_setting is None:
            self.optimizer_setting = {
                'lr': 0.001,
                'betas': (0.9, 0.99),
                'eps': 1e-8,
                'weight_decay': 0}
        if self.element_wise or self.simplified_model:
            self.use_siml_updater = False

        if self.num_workers is None:
            self.num_workers = util.determine_max_process()

        if (self.stop_trigger_epoch // self.log_trigger_epoch) == 0:
            raise ValueError(
                f"Set stop_trigger_epoch larger than log_trigger_epoch")

        super().__post_init__()

    # def overwrite_element_wise_setting(self):
    #     print(f"element_wise is True. Overwrite settings.")
    #     self.batch_size = self.element_batch_size
    #     self.element_batch_size = -1
    #     self.use_siml_updater = False

    def update_output_directory(self, *, id_=None, base=None):
        if base is None:
            base = Path('models')
        else:
            base = Path(base)
        if id_ is None:
            self.output_directory = base \
                / f"{self.name}_{util.date_string()}"
        else:
            self.output_directory = base \
                / f"{self.name}_{id_}_{util.date_string()}"


@dc.dataclass
class BlockSetting(TypedDataClass):
    name: str = 'Block'
    type: str = 'mlp'
    destinations: typing.List[str] = dc.field(
        default_factory=lambda: ['Output'])
    input_slice: slice = slice(0, None, 1)
    input_indices: typing.List[int] = dc.field(
        default=None, metadata={'allow_none': True})
    support_input_index: int = 0
    nodes: typing.List[int] = dc.field(
        default_factory=lambda: [-1, -1])
    activations: typing.List[str] = dc.field(
        default_factory=lambda: ['identity'])
    dropouts: typing.List[float] = dc.field(default_factory=lambda: [0.])

    optional: dict = dc.field(default_factory=dict)

    # Parameters for dynamic definition of layers
    hidden_nodes: int = dc.field(
        default=None, metadata={'allow_none': True})
    hidden_layers: int = dc.field(
        default=None, metadata={'allow_none': True})
    hidden_activation: str = 'rely'
    output_activation: str = 'identity'
    input_dropout: float = 0.0
    hidden_dropout: float = 0.5
    output_dropout: float = 0.0

    def __post_init__(self):

        # Dynamic definition of layers
        if self.hidden_nodes is not None and self.hidden_layers is not None:
            self.nodes = \
                [-1] + [self.hidden_nodes] * self.hidden_layers + [-1]
            self.activations = [self.hidden_activation] * self.hidden_layers \
                + [self.output_activation]
            self.dropouts = [self.input_dropout] \
                + [self.hidden_dropout] * (self.hidden_layers - 1) \
                + [self.output_dropout]
        if not(
                len(self.nodes) - 1 == len(self.activations)
                == len(self.dropouts)):
            raise ValueError('Block definition invalid')
        super().__post_init__()

        if self.input_indices is not None:
            self.input_selection = self.input_indices
        else:
            self.input_selection = self.input_slice


@dc.dataclass
class ModelSetting(TypedDataClass):
    blocks: typing.List[BlockSetting]

    def __init__(self, setting=None):
        if setting is None:
            self.blocks = [BlockSetting()]
        else:
            self.blocks = [
                BlockSetting(**block) for block in setting['blocks']]


@dc.dataclass
class OptunaSetting(TypedDataClass):
    n_trial: int = 100
    output_base_directory: Path = Path('models/optuna')
    hyperparameters: typing.List[dict] = dc.field(default_factory=list)
    setting: dict = dc.field(default_factory=dict)

    def __post_init__(self):
        for hyperparameter in self.hyperparameters:
            if hyperparameter['type'] == 'categorical':
                if len(hyperparameter['choices']) != len(np.unique([
                        c['id'] for c in hyperparameter['choices']])):
                    raise ValueError(
                        'IDs in optuna.hyperparameter.choices not unique')
        super().__post_init__()


@dc.dataclass
class ConversionSetting(TypedDataClass):
    """Dataclass for raw data converter.

    Parameters
    -----------
    mandatory_variables: list of str
        Mandatory variable names. If any of them are not found,
        ValueError is raised.
    mandatory: list of str
        An alias of mandatory_variables.
    optional_variables: list of str
        Optional variable names. If any of them are not found,
        they are ignored.
    optional: list of str
        An alias of optional_variables.
    output_base_directory: str or pathlib.Path, optional ['data/interim']
        Output base directory for the converted raw data. By default,
        'data/interim' is the output base directory, so
        'data/interim/aaa/bbb' directory is the output directory for
        'data/raw/aaa/bbb' directory.
    conversion_function: function, optional [None]
        Conversion function which takes femio.FEMData object and
        pathlib.Path (data directory) as only arguments and returns data
        dict to be saved.
    finished_file: str, optional ['converted']
        File name to indicate that the conversion is finished.
    file_type: str, optional ['fistr']
        File type to be read.
    required_file_names: list of str,
            optional [['*.msh', '*.cnt', '*.res.0.1']]
        Required file names.
    skip_femio: bool, optional [False]
        If True, skip femio.FEMData reading process. Useful for
        user-defined data format such as csv, h5, etc.
    """

    mandatory_variables: typing.List[str] = dc.field(
        default_factory=list)
    optional_variables: typing.List[str] = dc.field(
        default_factory=list)
    mandatory: typing.List[str] = dc.field(
        default_factory=list)
    optional: typing.List[str] = dc.field(
        default_factory=list)
    finished_file: str = 'converted'
    file_type: str = 'fistr'
    required_file_names: typing.List[str] = dc.field(
        default_factory=lambda: ['*.msh', '*.cnt', '*.res.0.1'])
    skip_femio: bool = False

    @classmethod
    def read_settings_yaml(cls, settings_yaml):
        dict_settings = util.load_yaml_file(settings_yaml)
        data = DataSetting(**dict_settings['data'])
        return cls(**dict_settings['raw_conversion'], data=data)

    def __post_init__(self):
        if len(self.mandatory) > len(self.mandatory_variables):
            self.mandatory_variables = self.mandatory
        elif len(self.mandatory) < len(self.mandatory_variables):
            self.mandatory = self.mandatory_variables
        else:
            pass

        if len(self.optional) > len(self.optional_variables):
            self.optional_variables = self.optional
        elif len(self.optional) < len(self.optional_variables):
            self.optional = self.optional_variables
        else:
            pass

        super().__post_init__()


@dc.dataclass
class PreprocessSetting:
    preprocess: dict = dc.field(default_factory=dict)

    @classmethod
    def read_settings_yaml(cls, settings_yaml):
        dict_settings = util.load_yaml_file(settings_yaml)
        preprocess = dict_settings['preprocess']
        return cls(preprocess=preprocess)

    def __post_init__(self):
        for key, value in self.preprocess.items():
            if isinstance(value, str):
                self.preprocess.update(
                    {key: {'method': value, 'componentwise': True}})
            elif isinstance(value, dict):
                if 'method' not in value:
                    value.update({'method': 'identity'})
                if 'componentwise' not in value:
                    value.update({'componentwise': True})
                self.preprocess.update({key: value})
            else:
                raise ValueError('Invalid format of preprocess setting')
        return


@dc.dataclass
class MainSetting:
    data: DataSetting = DataSetting()
    conversion: ConversionSetting = ConversionSetting()
    preprocess: dict = dc.field(default_factory=dict)
    trainer: TrainerSetting = TrainerSetting()
    model: ModelSetting = ModelSetting()
    optuna: OptunaSetting = OptunaSetting()

    @classmethod
    def read_settings_yaml(cls, settings_yaml):
        dict_settings = util.load_yaml(settings_yaml)
        if isinstance(settings_yaml, Path):
            name = settings_yaml.stem
        else:
            name = None
        return cls.read_dict_settings(dict_settings, name=name)

    @classmethod
    def read_dict_settings(cls, dict_settings, *, name=None):
        if 'trainer' in dict_settings \
                and 'name' not in dict_settings['trainer']:
            if name is None:
                dict_settings['trainer']['name'] = 'unnamed'
            else:
                dict_settings['trainer']['name'] = name
        if 'data' in dict_settings:
            data_setting = DataSetting(**dict_settings['data'])
        else:
            data_setting = DataSetting()
        if 'conversion' in dict_settings:
            conversion_setting = ConversionSetting(
                **dict_settings['conversion'])
        else:
            conversion_setting = ConversionSetting()
        if 'preprocess' in dict_settings:
            preprocess_setting = PreprocessSetting(
                dict_settings['preprocess']).preprocess
        else:
            preprocess_setting = PreprocessSetting().preprocess
        if 'trainer' in dict_settings:
            trainer_setting = TrainerSetting(**dict_settings['trainer'])
        else:
            trainer_setting = TrainerSetting
        if 'model' in dict_settings:
            model_setting = ModelSetting(dict_settings['model'])
        else:
            model_setting = ModelSetting()
        if 'optuna' in dict_settings:
            optuna_setting = OptunaSetting(**dict_settings['optuna'])
        else:
            optuna_setting = OptunaSetting()

        return cls(
            data=data_setting, conversion=conversion_setting,
            preprocess=preprocess_setting,
            trainer=trainer_setting, model=model_setting,
            optuna=optuna_setting)

    def __post_init__(self):

        input_length = np.sum(self.trainer.input_dims)
        output_length = np.sum(self.trainer.output_dims)

        # Infer input and output dimension if they are not specified.
        # NOTE: Basically Chainer can infer input dimension, but not the case
        # when chainer.functions.einsum is used.
        if input_length is not None:
            if self.model.blocks[0].nodes[0] < 0:
                self.model.blocks[0].nodes[0] = int(input_length)
            if self.model.blocks[-1].nodes[-1] < 0:
                self.model.blocks[-1].nodes[-1] = int(output_length)

    def update_with_dict(self, new_dict):
        original_dict = dc.asdict(self)
        return MainSetting.read_dict_settings(
            self._update_with_dict(original_dict, new_dict))

    def _update_with_dict(self, original_setting, new_setting):
        if isinstance(new_setting, str) or isinstance(new_setting, float) \
                or isinstance(new_setting, int):
            return new_setting
        elif isinstance(new_setting, list):
            # NOTE: Assume that data is complete under the list
            return new_setting
        elif isinstance(new_setting, dict):
            for key, value in new_setting.items():
                original_setting.update({
                    key: self._update_with_dict(original_setting[key], value)})
            return original_setting
        else:
            raise ValueError(f"Unknown data type: {new_setting.__class__}")


def write_yaml(data_class, file_name, *, overwrite=False):
    """Write YAML file of the specified dataclass object.

    Parameters
    -----------
        data_class: dataclasses.dataclass
            DataClass object to write.
        file_name: str or pathlib.Path
            YAML file name to write.
        overwrite: bool, optional [False]
            If True, overwrite file.
    """
    file_name = Path(file_name)
    if file_name.exists() and not overwrite:
        raise ValueError(f"{file_name} already exists")

    dict_data = dc.asdict(data_class)
    standardized_dict_data = _standardize_data(dict_data)

    with open(file_name, 'w') as f:
        yaml.dump(standardized_dict_data, f)
    return


def _standardize_data(data):
    if isinstance(data, list):
        return [_standardize_data(d) for d in data]
    elif isinstance(data, tuple):
        return [_standardize_data(d) for d in data]
    elif isinstance(data, slice):
        return [data.start, data.stop, data.step]
    elif isinstance(data, dict):
        return {k: _standardize_data(v) for k, v in data.items()}
    elif isinstance(data, Path):
        return str(data)
    elif isinstance(data, Enum):
        return data.value
    else:
        return data
