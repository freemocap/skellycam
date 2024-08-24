from typing import List, Union

import numpy as np
from pydantic import BaseModel

Z_SCORE_95_CI = 1.96  # Z-score for 95% confidence interval

SamplesType = Union[List[Union[float, int]], np.ndarray]


def validate_samples(data: np.ndarray) -> None:
    """Validate the input sample data."""
    if not isinstance(data, np.ndarray):
        raise ValueError("Sample list must be a numpy array")
    if data.size == 0:
        raise ValueError("Sample list cannot be empty")
    if len(data.shape) != 1:
        raise ValueError("Sample list must be one-dimensional")
    if not np.issubdtype(data.dtype, np.number):
        raise ValueError("Sample list must contain only numerical values")
    if np.isnan(data).all():
        raise ValueError("Sample list is all NaN values")
    if np.isinf(data).all():
        raise ValueError("Sample list is all infinite values")
    if np.isclose(np.sum(data), 0):
        raise ValueError("Sample list sum is close to zero")


class SampleData(BaseModel):
    data: np.ndarray

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_samples(cls, samples: SamplesType):
        if isinstance(samples, list):
            samples = np.array(samples)

        if not len(samples.shape) == 1:
            raise ValueError(f"Sample list must be one-dimensional (for now) - received shape: {samples.shape}")
        return cls(data=samples)

    @property
    def samples(self) -> SamplesType:
        return self.data.tolist()

    @property
    def number_of_samples(self) -> int:
        return len(self.data)


class CentralTendencyMeasures(BaseModel):
    mean: float
    median: float

    @classmethod
    def from_samples(cls, samples: SampleData) -> 'CentralTendencyMeasures':
        return cls(
            mean=np.nanmean(samples.data),
            median=np.nanmedian(samples.data),
        )


class VariabilityMeasures(BaseModel):
    standard_deviation: float
    median_absolute_deviation: float
    interquartile_range: float
    confidence_interval_95: float
    coefficient_of_variation: float

    @classmethod
    def from_samples(cls, samples: SampleData) -> 'VariabilityMeasures':
        return cls(
            standard_deviation=np.nanstd(samples.data),
            median_absolute_deviation=np.nanmedian(np.abs(samples.data - np.nanmedian(samples.data))),
            interquartile_range=np.nanpercentile(samples.data, 75) - np.nanpercentile(samples.data, 25),
            confidence_interval_95=Z_SCORE_95_CI * np.nanstd(samples.data) / np.sqrt(samples.data.size),
            coefficient_of_variation=np.nanstd(samples.data) / np.nanmean(samples.data),
        )


class DescriptiveStatistics(BaseModel):
    sample_data: SampleData

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_samples(cls, samples: SamplesType) -> 'DescriptiveStatistics':
        return cls(sample_data=SampleData.from_samples(samples))

    @property
    def samples(self) -> SamplesType:
        return self.sample_data.samples

    @property
    def measures_of_central_tendency(self) -> CentralTendencyMeasures:
        return CentralTendencyMeasures.from_samples(self.sample_data)

    @property
    def measures_of_variability(self) -> VariabilityMeasures:
        return VariabilityMeasures.from_samples(self.sample_data)

    @property
    def data(self) -> np.ndarray:
        return self.sample_data.data

    @property
    def mean(self) -> float:
        return self.measures_of_central_tendency.mean

    @property
    def median(self) -> float:
        return self.measures_of_central_tendency.median

    @property
    def standard_deviation(self) -> float:
        return self.measures_of_variability.standard_deviation

    @property
    def median_absolute_deviation(self) -> float:
        return self.measures_of_variability.median_absolute_deviation

    @property
    def interquartile_range(self) -> float:
        return self.measures_of_variability.interquartile_range

    @property
    def confidence_interval_95(self) -> float:
        return self.measures_of_variability.confidence_interval_95

    @property
    def number_of_samples(self) -> int:
        return self.sample_data.number_of_samples

    def to_dict(self):
        return {
            "mean": self.mean,
            "median": self.median,
            "stddev": self.standard_deviation,
            "mad": self.median_absolute_deviation,
            "iqr": self.interquartile_range,
            "ci95": self.confidence_interval_95,
            "number_of_samples": self.number_of_samples,
        }

    def __str__(self) -> str:
        return (
            f"Descriptive Statistics:\n"
            f"\tNumber of Samples: {self.number_of_samples}\n"
            f"\tMean: {self.mean:.3f}\n"
            f"\tMedian: {self.median:.3f}\n"
            f"\tStandard Deviation: {self.standard_deviation:.3f}\n"
            f"\tMedian Absolute Deviation: {self.median_absolute_deviation:.3f}\n"
            f"\tInterquartile Range: {self.interquartile_range:.3f}\n"
            f"\t95% Confidence Interval: {self.confidence_interval_95:.3f}\n"
        )


if __name__ == "__main__":
    dummy_data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    stats = DescriptiveStatistics.from_samples(samples=dummy_data)

    print(stats)
