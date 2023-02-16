from typing import List

from sentry.dynamic_sampling.rules.biases.base import (
    Bias,
    BiasData,
    BiasDataProvider,
    BiasParams,
    BiasRulesGenerator,
)
from sentry.dynamic_sampling.rules.helpers.prioritise_project import get_cached_sample_rate
from sentry.dynamic_sampling.rules.utils import RESERVED_IDS, PolymorphicRule, RuleType


class UniformDataProvider(BiasDataProvider):
    def get_bias_data(self, bias_params: BiasParams) -> BiasData:
        return {
            "id": RESERVED_IDS[RuleType.UNIFORM_RULE],
            "sampleRate": get_cached_sample_rate(
                bias_params.project, default_samplerate=bias_params.base_sample_rate
            ),
        }


class UniformRulesGenerator(BiasRulesGenerator):
    def _generate_bias_rules(self, bias_data: BiasData) -> List[PolymorphicRule]:
        return [
            {
                "samplingValue": {
                    "type": "sampleRate",
                    "value": bias_data["sampleRate"],
                },
                "type": "trace",
                "active": True,
                "condition": {
                    "op": "and",
                    "inner": [],
                },
                "id": bias_data["id"],
            }
        ]


class UniformBias(Bias):
    def __init__(self) -> None:
        super().__init__(UniformDataProvider, UniformRulesGenerator)
