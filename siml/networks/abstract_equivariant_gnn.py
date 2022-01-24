
import einops
import torch

from .. import setting
from . import abstract_gcn
from . import activations
from . import identity
from . import mlp
from . import tensor_operations


class AbstractEquivariantGNN(abstract_gcn.AbstractGCN):
    """Abstract class for equivariant GNN."""

    def __init__(self, block_setting):
        self.is_first = True  # For block setting validation

        len_support = len(block_setting.support_input_indices)
        if len_support < 2:
            raise ValueError(
                'len(support_input_indices) should be larger than 1 '
                f"({len_support} found.)")

        self.create_subchain = block_setting.optional.get(
            'create_subchain', True)
        super().__init__(
            block_setting, create_subchain=False,
            multiple_networks=False, residual=block_setting.residual)
        if self.create_subchain:
            n_layer = len(self.block_setting.nodes) - 1
            if n_layer == 0:
                raise ValueError(
                    f"# of layers is zero for: {block_setting}")

            if n_layer == 1:
                self.subchains = torch.nn.ModuleList([
                    torch.nn.ModuleList([
                        torch.nn.Linear(
                            self.block_setting.nodes[0],
                            self.block_setting.nodes[-1],
                            bias=self.block_setting.bias)])])
                self.has_coefficient_network = False
            else:
                self.subchains = torch.nn.ModuleList([
                    torch.nn.ModuleList([
                        torch.nn.Linear(
                            self.block_setting.nodes[0],
                            self.block_setting.nodes[-1],
                            bias=False)])])
                self.coefficient_network = mlp.MLP(self.block_setting)
                print(f"Coefficient network created for: {block_setting.name}")
                self.has_coefficient_network = True
                self.contraction = tensor_operations.Contraction(
                    setting.BlockSetting())

        else:
            print(f"Skip subchain creation for: {block_setting.name}")
            self.subchains = [[identity.Identity(block_setting)]]
            self.has_coefficient_network = False

        if self.has_coefficient_network:
            self.last_activation = activations.identity
        else:
            self.last_activation = self.activations[-1]

        self.dim = block_setting.optional.get('dim', 3)
        self.support_tensor_rank = block_setting.optional.get(
            'support_tensor_rank', 1)
        self.symmetric = block_setting.optional.get('symmetric', False)
        if self.symmetric:
            print(f"Output symmetric matrix for: {block_setting.name}")

        if 'factor' in block_setting.optional:
            self.factor = block_setting.optional['factor']
            print(f"Factor: {self.factor}")
        else:
            self.factor = 1.

        self.ah_w = block_setting.optional.get(
            'ah_w', False)
        if self.ah_w:
            print('Matrix multiplication mode: (AH) W')
        else:
            print('Matrix multiplication mode: A (HW)')

        if 'propagations' not in block_setting.optional:
            raise ValueError(
                f"Specify 'propagations' in optional for: {block_setting}")

        self.propagation_functions = self._create_propagation_functions()

        # Setting for Neumann BC
        if self.block_setting.input_names is not None:
            if len(self.block_setting.input_names) != 3:
                raise ValueError(
                    f"# of input names invalid for {self.block_setting}")
            self.has_neumann = True
            self._init_neumann()
        else:
            self.has_neumann = False
        return

    def _init_neumann(self):
        self.create_neumann_linear = self.block_setting.optional.get(
            'create_neumann_linear', False)
        self.neumann_factor = self.block_setting.optional.get(
            'neumann_factor', 1.)
        self.create_neumann_ratio = self.block_setting.optional.get(
            'create_neumann_ratio', False)

        if self.create_neumann_linear:
            self.neumann_linear = torch.nn.Linear(
                *self.subchains[0][0].weight.shape,
                bias=False)
        else:
            self.neumann_linear = self.subchains[0][0]

        if self.neumann_linear.bias is not None:
            raise ValueError(
                'IsoGCN with Neumann should have no bias: '
                f"{self.block_setting}")

        if self.create_neumann_ratio:
            self.neumann_ratio = torch.nn.Linear(1, 1, bias=False)

        return

    def _validate_block(self, x, supports):
        shape = x.shape
        self.x_tensor_rank \
            = len(shape) - 2  # (n_vertex, dim, dim, ..., n_feature)

        if len(supports) != self.dim**self.support_tensor_rank:
            raise ValueError(
                f"{self.dim**self.support_tensor_rank} ength of supports "
                f"expected (actual: {len(supports)} for: {self.block_setting}")

        if not self.create_subchain:
            return

        str_propagations = self.block_setting.optional['propagations']
        n_propagation = len(str_propagations)
        n_contraction = sum([
            s == 'contraction' for s in str_propagations])
        n_rank_raise_propagation = n_propagation - n_contraction
        estimated_output_tensor_rank = \
            self.x_tensor_rank - n_contraction + n_rank_raise_propagation

        if self.has_coefficient_network:
            return

        if estimated_output_tensor_rank > 0 \
                and self.block_setting.activations[-1] != 'identity':
            raise ValueError(
                'Set identity activation for rank '
                f"{estimated_output_tensor_rank} output: {self.block_setting}")

        if self.x_tensor_rank == 0:
            if estimated_output_tensor_rank > 0:
                # rank 0 -> rank k tensor
                if self.block_setting.bias and self.ah_w:
                    raise ValueError(
                        'Set bias = False for rank 0 -> k with (AH) W: '
                        f"{self.block_setting}")

        else:
            if estimated_output_tensor_rank == 0:
                # rank k -> rank 0 tensor
                if self.block_setting.bias and not self.ah_w:
                    raise ValueError(
                        'Set bias = False for rank k -> 0 with A (HW): '
                        f"{self.block_setting}")
            else:
                # rank k -> rank l tensor
                if self.block_setting.bias:
                    raise ValueError(
                        'Set bias = False for rank k -> l with A (HW): '
                        f"{self.block_setting}")
        return

    def _forward_single(self, x, *args, supports=None):
        if self.is_first:
            self._validate_block(x, supports)
            self.is_first = False
        if self.residual:
            shortcut = self.shortcut(x)
        else:
            shortcut = 0.
        h_res = self._propagate(x, supports)

        if self.has_neumann:
            directed_neumann = args[0]
            inversed_moment_tensors = args[1]
            h_res = self._add_neumann(
                h_res, directed_neumann=directed_neumann,
                inversed_moment_tensors=inversed_moment_tensors)

        if self.has_coefficient_network:
            if self.x_tensor_rank == 0:
                coeff = self.coefficient_network(x)
            else:
                coeff = self.coefficient_network(self.contraction(x))
            h_res = torch.einsum('i...f,if->i...f', h_res, coeff)

        if self.block_setting.activation_after_residual:
            h_res = self.last_activation(h_res + shortcut)
        else:
            h_res = self.last_activation(h_res) + shortcut

        return h_res

    def _add_neumann(self, grad, directed_neumann, inversed_moment_tensors):
        neumann = torch.einsum(
            'ikl,il...f->ik...f',
            inversed_moment_tensors[..., 0],
            self.neumann_linear(directed_neumann)) * self.neumann_factor
        if self.create_neumann_ratio:
            sigmoid_coeff = torch.sigmoid(self.coeff.weight[0, 0])
            return (sigmoid_coeff * grad + (1 - sigmoid_coeff) * neumann) * 2
        else:
            return grad + neumann

    def _propagate(self, x, support):
        h = x
        if not self.ah_w:
            # A (H W)
            h = self.subchains[0][0](h)

        h = self._propagete_core_explicit(h, support)

        if self.ah_w:
            # (A H) W
            h = self.subchains[0][0](h)

        if self.symmetric:
            h = (h + einops.rearrange(
                h, 'element x1 x2 feature -> element x2 x1 feature')) / 2

        h = torch.nn.functional.dropout(
            h, p=self.dropout_ratios[0], training=self.training)
        return h

    def _propagate_core_explicit(self, x, support):
        h = x
        for propagation_function in self.propagation_functions:
            h = propagation_function(h, support) * self.factor
        return h

    def _create_propagation_functions(self):
        str_propagations = self.block_setting.optional['propagations']
        propagation_functions = [
            self._create_propagation_function(str_propagation)
            for str_propagation in str_propagations]

        return propagation_functions

    def _create_propagation_function(self, str_propagation):
        if str_propagation == 'convolution':
            return self._convolution
        elif str_propagation == 'contraction':
            return self._contraction
        elif str_propagation == 'tensor_product':
            return self._tensor_product
        elif str_propagation == 'rotation':
            return self._rotation
        else:
            raise ValueError(
                f"Unexpected propagation method: {str_propagation}")

    def _calculate_dim(self, supports, n_vertex):
        dim, mod = divmod(supports.shape[0], n_vertex)
        if mod != 0:
            raise ValueError(
                'IsoGCN not supported for\n'
                f"    Sparse shape: {[s.shape for s in supports]}\n",
                f"    n_vertex: {n_vertex}")
        return dim
