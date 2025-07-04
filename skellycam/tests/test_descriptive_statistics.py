import numpy as np
import pytest
from skellycam.utilities.descriptive_statistics import DescriptiveStatistics


def test_descriptive_statistics_single_sample():
    """Test that DescriptiveStatistics handles a single sample correctly."""
    # Create a DescriptiveStatistics object with a single sample
    single_sample = [42.0]
    stats = DescriptiveStatistics.from_samples(single_sample, name="Single Sample", units="units")
    
    # Check measures of central tendency
    assert stats.mean == 42.0
    assert stats.median == 42.0
    
    # Check measures of variability (should all be zero)
    assert stats.standard_deviation == 0.0
    assert stats.median_absolute_deviation == 0.0
    assert stats.interquartile_range == 0.0
    assert stats.confidence_interval_95 == 0.0
    assert stats.coefficient_of_variation == 0.0
    
    # Check other properties
    assert stats.max == 42.0
    assert stats.min == 42.0
    assert stats.max_index == 0
    assert stats.min_index == 0
    assert stats.number_of_samples == 1


def test_descriptive_statistics_multiple_samples():
    """Test that DescriptiveStatistics handles multiple samples correctly."""
    # Create a DescriptiveStatistics object with multiple samples
    multiple_samples = [1.0, 2.0, 3.0, 4.0, 5.0]
    stats = DescriptiveStatistics.from_samples(multiple_samples, name="Multiple Samples", units="units")
    
    # Check measures of central tendency
    assert stats.mean == 3.0
    assert stats.median == 3.0
    
    # Check measures of variability (should be calculated)
    assert stats.standard_deviation == pytest.approx(np.std(multiple_samples))
    assert stats.median_absolute_deviation == pytest.approx(np.median(np.abs(np.array(multiple_samples) - 3.0)))
    assert stats.interquartile_range == pytest.approx(4.0 - 2.0)  # Q3 - Q1
    
    # Check other properties
    assert stats.max == 5.0
    assert stats.min == 1.0
    assert stats.max_index == 4
    assert stats.min_index == 0
    assert stats.number_of_samples == 5


def test_descriptive_statistics_empty_samples():
    """Test that DescriptiveStatistics raises an error for empty samples."""
    # Try to create a DescriptiveStatistics object with empty samples
    with pytest.raises(ValueError):
        DescriptiveStatistics.from_samples([], name="Empty Samples", units="units")