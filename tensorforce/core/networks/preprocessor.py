# Copyright 2020 Tensorforce Team. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

from tensorforce import TensorforceError
from tensorforce.core import SignatureDict, TensorDict, TensorSpec, TensorsSpec, tf_function, \
    tf_util
from tensorforce.core.layers import MultiInputLayer, PreprocessingLayer, Register, StatefulLayer
from tensorforce.core.networks import LayeredNetwork


class Preprocessor(LayeredNetwork):
    """
    Special preprocessor network following a sequential layer-stack architecture, which can be
    specified as either a single or a list of layer specifications.

    Args:
        layers (iter[specification] | iter[iter[specification]]): Layers configuration, see the
            [layers documentation](../modules/layers.html)
            (<span style="color:#C00000"><b>required</b></span>).
        device (string): Device name
            (<span style="color:#00C000"><b>default</b></span>: inherit value of parent module).
        l2_regularization (float >= 0.0): Scalar controlling L2 regularization
            (<span style="color:#00C000"><b>default</b></span>: inherit value of parent module).
        name (string): <span style="color:#0000C0"><b>internal use</b></span>.
        input_spec (specification): <span style="color:#0000C0"><b>internal use</b></span>.
    """

    def __init__(self, *, layers, device=None, l2_regularization=None, name=None, input_spec=None):
        if not isinstance(input_spec, TensorSpec):
            raise TensorforceError.type(
                name='preprocessor', argument='inputs_spec', dtype=type(input_spec)
            )

        super().__init__(
            layers=[layers], device=device, l2_regularization=l2_regularization, name=name,
            inputs_spec=TensorsSpec(x=input_spec)
        )

    @property
    def internals_spec(self):
        raise NotImplementedError

    def internals_init(self):
        raise NotImplementedError

    def max_past_horizon(self, *, on_policy):
        raise NotImplementedError

    def past_horizon(self, *, on_policy):
        raise NotImplementedError

    def input_signature(self, *, function):
        if function == 'apply':
            return self.inputs_spec.signature(batched=True)

        elif function == 'reset':
            return SignatureDict()

        else:
            return super().input_signature(function=function)

    @tf_function(num_args=0)
    def reset(self):
        operations = list()

        for layer in self.layers:
            if isinstance(layer, PreprocessingLayer):
                operations.append(layer.reset())

        if len(operations) > 0:
            return tf_util.identity(input=operations[0])
        else:
            return tf_util.constant(value=False, dtype='bool')

    @tf_function(num_args=1)
    def apply(self, *, x, independent):
        registered_tensors = TensorDict(x=x)

        for layer in self.layers:
            if isinstance(layer, Register):
                if layer.tensor in registered_tensors:
                    raise TensorforceError.exists(name='registered tensor', value=layer.tensor)
                x = layer.apply(x=x)
                registered_tensors[layer.tensor] = x

            elif isinstance(layer, MultiInputLayer):
                if layer.tensors not in registered_tensors:
                    raise TensorforceError.exists_not(name='registered tensor', value=layer.tensors)
                x = layer.apply(x=registered_tensors[layer.tensors])

            elif isinstance(layer, StatefulLayer):
                x = layer.apply(x=x, independent=independent)

            else:
                x = layer.apply(x=x)

        return x
