
import torch


DEFAULT_NEGATIVE_SLOPE_FOR_LEAKY_RELU = .5


def identity(x):
    return x


def one(x):
    return 1


def atanh(x, epsilon=1e-5):
    if torch.any(x > 1 + epsilon) or torch.any(x < -1 - epsilon):
        raise ValueError(
            'Input range not in (-1, 1), but '
            f"[{torch.min(x)}, {torch.max(x)}])")
    x[x > 1 - epsilon] = 1 - epsilon
    x[x < -1 + epsilon] = -1 + epsilon
    return torch.atanh(x)


class ATanh(torch.nn.Module):

    def __init__(self, epsilon):
        super().__init__()
        self.epsilon = epsilon
        return

    def forward(self, x):
        return atanh(x, epsilon=self.epsilon)


def derivative_tanh(x):
    return 1 / torch.cosh(x)**2


def max_pool(x, original_shapes):
    split_x = split(x, original_shapes)
    dim = len(original_shapes[0]) - 1
    return torch.stack([
        torch.max(
            s, dim=dim, keepdim=False
        )[0]  # [0] to unwrap tuple output of torch.max
        for s in split_x], dim=dim)


def mean(x, original_shapes):
    split_x = split(x, original_shapes)
    dim = len(original_shapes[0]) - 1
    return torch.stack([
        torch.mean(s, dim=dim, keepdim=False) for s in split_x], dim=dim)


def min(x, original_shapes):
    split_x = split(x, original_shapes)
    dim = len(original_shapes[0]) - 1
    return torch.stack([
        min_func(s, dim=dim, keepdim=False) for s in split_x], dim=dim)


def min_func(*args, **kwargs):
    ret = torch.min(*args, **kwargs)
    if isinstance(ret, tuple):
        return ret[0]
    else:
        return ret


def normalize(x):
    norms = torch.norm(x, dim=-1, keepdim=True)
    return x / (norms + 1e-5)


def split(x, original_shapes):
    if isinstance(original_shapes, dict):
        raise ValueError(
            'Input is dict. Specify dict_key in the block_setting.optional.')
    if len(original_shapes) == 1:
        return (x,)

    if len(original_shapes[0]) == 1:
        return torch.split(x, [s[0] for s in original_shapes])
    elif len(original_shapes[0]) == 2:
        return torch.split(x, [s[1] for s in original_shapes], dim=1)
    else:
        raise ValueError(f"Unexpected original_shapes: {original_shapes}")


def mish(x):
    return x * torch.tanh(torch.nn.functional.softplus(x))


class InversedLeakyReLU(torch.nn.Module):

    def __init__(self, original_lrelu=None):
        super().__init__()
        if original_lrelu is None:
            original_lrelu = torch.nn.LeakyReLU(
                negative_slope=DEFAULT_NEGATIVE_SLOPE_FOR_LEAKY_RELU)
        original_negative_slope = original_lrelu.negative_slope
        assert original_negative_slope > 1e-5, \
            f"Too small original negative slope: {original_negative_slope}"
        inversed_negative_slope = 1 / original_negative_slope
        self.inversed_leaky_relu = torch.nn.LeakyReLU(
            negative_slope=inversed_negative_slope)
        return

    def forward(self, x):
        return self.inversed_leaky_relu(x)


class DerivativeLeakyRELU(torch.nn.Module):

    def __init__(self, original_lrelu=None):
        super().__init__()
        if original_lrelu is None:
            original_lrelu = torch.nn.LeakyReLU(
                negative_slope=DEFAULT_NEGATIVE_SLOPE_FOR_LEAKY_RELU)
        self.original_negative_slope = original_lrelu.negative_slope
        self.center_value = (1 + self.original_negative_slope) / 2
        return

    def forward(self, x):
        return torch.heaviside(x, self.center_value) \
            + torch.heaviside(-x, self.center_value) \
            * self.original_negative_slope


DICT_ACTIVATIONS = {
    'identity': identity,
    'relu': torch.relu,
    'sigmoid': torch.sigmoid,
    'tanh': torch.tanh,
    'max_pool': max_pool,
    'max': max_pool,
    'mean': mean,
    'mish': mish,
    'normalize': normalize,
    'softplus': torch.nn.functional.softplus,
    'sqrt': torch.sqrt,
    'leaky_relu': torch.nn.LeakyReLU(
        negative_slope=DEFAULT_NEGATIVE_SLOPE_FOR_LEAKY_RELU),
    'inversed_leaky_relu': InversedLeakyReLU(),
}
