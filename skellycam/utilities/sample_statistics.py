import numpy as np
from numpydantic import NDArray
from pydantic import BaseModel, ConfigDict, computed_field
from functools import cached_property

Z_SCORE_95_CI = 1.96  # Z-score for 95% confidence interval

SamplesType = list[float | int] | np.ndarray


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
    data: NDArray

    @classmethod
    def from_samples(cls, samples: SamplesType):
        if isinstance(samples, list):
            samples = np.array(samples)

        if not len(samples.shape) == 1:
            raise ValueError(f"Sample list must be one-dimensional (for now) - received shape: {samples.shape}")

        if samples.shape[0] < 1:
            raise ValueError(f"Sample list must have at least 1 sample - received shape: {samples.shape}")
        return cls(data=samples)

    @property
    def samples(self) -> SamplesType:
        return self.data.tolist()

    @property
    def number_of_samples(self) -> int:
        return len(self.data)

    def has_min_samples(self, min_count: int) -> bool:
        """Check if the sample has at least the minimum required count."""
        return self.number_of_samples > min_count


class CentralTendencyMeasures(BaseModel):
    mean: float
    median: float | None = None

    @classmethod
    def from_samples(cls, samples: SampleData) -> 'CentralTendencyMeasures':
        # Mean requires at least 1 sample
        mean = np.nanmean(samples.data) if samples.has_min_samples(1) else np.nan

        # Median requires at least 1 sample
        median = np.nanmedian(samples.data) if samples.has_min_samples(1) else np.nan

        return cls(
            mean=mean,
            median=median,
        )


class VariabilityMeasures(BaseModel):
    standard_deviation: float | None = None
    median_absolute_deviation: float | None = None
    interquartile_range: float | None = None
    confidence_interval_95: float | None = None
    coefficient_of_variation: float | None = None

    @classmethod
    def from_samples(cls, samples: SampleData) -> 'VariabilityMeasures':
        # Standard deviation requires at least 2 samples
        std_dev = np.nanstd(samples.data) if samples.has_min_samples(2) else np.nan

        # Mean for coefficient of variation
        mean = np.nanmean(samples.data) if samples.has_min_samples(1) else np.nan

        # Median absolute deviation requires at least 2 samples
        mad = np.nan
        if samples.has_min_samples(2):
            mad = np.nanmedian(np.abs(samples.data - np.nanmedian(samples.data)))

        # Interquartile range requires at least 4 samples for meaningful quartiles
        iqr = np.nan
        if samples.has_min_samples(4):
            iqr = np.nanpercentile(samples.data, 75) - np.nanpercentile(samples.data, 25)

        # Confidence interval requires at least 3 samples for meaningful estimation
        ci_95 = np.nan
        if samples.has_min_samples(3):
            size = np.sqrt(samples.number_of_samples)
            ci_95 = Z_SCORE_95_CI * std_dev / size

        # Coefficient of variation requires at least 2 samples and non-zero mean
        cv = np.nan
        if samples.has_min_samples(2) and mean != 0 and not np.isnan(mean):
            cv = std_dev / mean

        return cls(
            standard_deviation=std_dev,
            median_absolute_deviation=mad,
            interquartile_range=iqr,
            confidence_interval_95=ci_95,
            coefficient_of_variation=cv,
        )


class DescriptiveStatistics(BaseModel):
    name: str = ""
    units: str = ""
    sample_data: SampleData

    model_config = ConfigDict(model_title_generator=lambda x: f"DescriptiveStatistics[{x.name}] (units:{x.units})")

    @classmethod
    def from_samples(cls, samples: SamplesType, name: str = "", units: str = "") -> 'DescriptiveStatistics':
        return cls(
            name=name,
            units=units,
            sample_data=SampleData.from_samples(samples)
        )

    @cached_property
    def max(self) -> float:
        """Maximum value in the data."""
        if not self.sample_data.has_min_samples(1) or np.isnan(self.data).all():
            return np.nan
        return float(np.nanmax(self.data))

    @cached_property
    def min(self) -> float:
        """Minimum value in the data."""
        if not self.sample_data.has_min_samples(1) or np.isnan(self.data).all():
            return np.nan
        return float(np.nanmin(self.data))

    @cached_property
    def range(self) -> float:
        """Range of the data (max - min)."""
        if not self.sample_data.has_min_samples(1) or np.isnan(self.data).all():
            return np.nan
        return self.max - self.min

    @cached_property
    def number_of_samples(self) -> int:
        return self.sample_data.number_of_samples

    @cached_property
    def measures_of_central_tendency(self) -> CentralTendencyMeasures:
        return CentralTendencyMeasures.from_samples(self.sample_data)

    @cached_property
    def measures_of_variability(self) -> VariabilityMeasures:
        return VariabilityMeasures.from_samples(self.sample_data)

    @property
    def samples(self) -> SamplesType:
        return self.sample_data.samples

    @property
    def data(self) -> np.ndarray:
        return self.sample_data.data

    @cached_property
    def mean(self) -> float:
        return self.measures_of_central_tendency.mean

    @cached_property
    def median(self) -> float:
        return self.measures_of_central_tendency.median if self.sample_data.has_min_samples(1) else np.nan

    @cached_property
    def max_index(self) -> int:
        """Index of the maximum value in the data."""
        if not self.sample_data.has_min_samples(1) or np.isnan(self.data).all():
            return -1
        return int(np.nanargmax(self.data))

    @cached_property
    def min_index(self) -> int:
        """Index of the minimum value in the data."""
        if not self.sample_data.has_min_samples(1) or np.isnan(self.data).all():
            return -1
        return int(np.nanargmin(self.data))

    @cached_property
    def standard_deviation(self) -> float:
        return self.measures_of_variability.standard_deviation

    @cached_property
    def median_absolute_deviation(self) -> float:
        return self.measures_of_variability.median_absolute_deviation

    @cached_property
    def interquartile_range(self) -> float:
        return self.measures_of_variability.interquartile_range

    @cached_property
    def confidence_interval_95(self) -> float:
        return self.measures_of_variability.confidence_interval_95

    @cached_property
    def coefficient_of_variation(self) -> float:
        return self.measures_of_variability.coefficient_of_variation
    def __str__(self) -> str:
        # Helper function to format values properly
        def format_value(value):
            if np.isnan(value):
                return "nan"
            return f"{value:.3f}"

        return (
            f"{self.name} Descriptive Statistics:\n"
            f"\tUnits: {self.units}\n"
            f"\tNumber of Samples: {self.number_of_samples}\n"
            f"\tMean: {format_value(self.mean)}\n"
            f"\tMedian: {format_value(self.median)}\n"
            f"\tStandard Deviation: {format_value(self.standard_deviation)}\n"
            f"\tMaximum (index): {format_value(self.max)}({self.max_index})\n"
            f"\tMinimum (index): {format_value(self.min)}({self.min_index})\n"
            f"\tRange (max-min): {format_value(self.range)}\n"
            f"\tCoefficient of Variation (%): {format_value(self.coefficient_of_variation)}\n"
            f"\tMedian Absolute Deviation: {format_value(self.median_absolute_deviation)}\n"
            f"\tInterquartile Range: {format_value(self.interquartile_range)}\n"
            f"\t95% Confidence Interval: {format_value(self.confidence_interval_95)}\n"
        )


if __name__ == "__main__":
    dummy_data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    stats = DescriptiveStatistics.from_samples(samples=dummy_data, name="Test Data", units="units")
    print(stats)

    dummy_too_few_data = [1.0, 2.0]
    too_few_stats = DescriptiveStatistics.from_samples(samples=dummy_too_few_data, name="Test Data (too few samples)",
                                                       units="units")
    print(too_few_stats)

    print(stats.model_dump_json(exclude={'sample_data'}, indent=4))
