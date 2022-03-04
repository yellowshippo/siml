
import torch

from . import activations
from . import mlp
from . import siml_module


class DeepSets(siml_module.SimlModule):
    """Permutation equivalent layer published in
    https://arxiv.org/abs/1703.06114 .
    """

    @staticmethod
    def get_name():
        return 'deepsets'

    @staticmethod
    def is_trainable():
        return True

    @staticmethod
    def accepts_multiple_inputs():
        return False

    @staticmethod
    def uses_support():
        return False

    def __init__(self, block_setting):
        """Initialize the NN.

        Parameters
        -----------
        block_setting: siml.setting.BlockSetting
            BlockSetting object.
        """

        super().__init__(block_setting, create_linears=False)
        self.lambda_ = mlp.MLP(block_setting, last_identity=True)
        self.gamma = mlp.MLP(block_setting, last_identity=True)
        self.dict_key = block_setting.optional.get('dict_key', None)
        return

    def _forward_core(self, x, supports=None, original_shapes=None):
        """Execute the NN's forward computation.

        Parameters
        -----------
        x: numpy.ndarray or cupy.ndarray
            Input of the NN.
        supports: list[chainer.util.CooMatrix]
            List of support inputs.

        Returns
        --------
        y: numpy.ndarray of cupy.ndarray
            Output of the NN.
        """
        h = x
        if self.dict_key is None:
            shapes = original_shapes
        else:
            shapes = original_shapes[self.dict_key]
        dim = len(shapes[0]) - 1
        split_h = activations.split(self.lambda_(x), shapes)
        reduced_h = activations.max_pool(self.gamma(h), shapes)
        if dim == 0:
            h = torch.cat([
                sh + reduced_h[i] for i, sh in enumerate(split_h)])
        else:
            h = torch.cat([
                sh + reduced_h[:, i] for i, sh in enumerate(split_h)])
        h = self.activations[-1](h)
        return h
