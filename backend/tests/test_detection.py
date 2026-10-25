import pytest
from terraguavd_detection.processing import fixture, score, valid_footprint, mock_classification


def test_baseline_retains_provenance_and_rejects_invalid_values():
    features=fixture(6)
    assert score(features) >= .65
    assert score(fixture(0)) is None
    assert score({**features,'quality':.2}) is None
    for value in [float('nan'),float('inf'),-1,1.1]:
        with pytest.raises(ValueError):
            score({**features,'gpr_response':value})
    with pytest.raises(ValueError):
        score({**features,'provenance':'unverified-real-sensor'})


def test_coverage_requires_good_sensor_data_and_valid_profile():
    assert valid_footprint(fixture(0),5,2)
    assert not valid_footprint(None,5,2)
    assert not valid_footprint(fixture(0),50,2)
    assert not valid_footprint(fixture(0),5,12)
    assert not valid_footprint({**fixture(0),'quality':.4},5,2)


def test_demo_labels_are_varied_explicit_fixtures_not_predictions():
    examples=[fixture(6+12*i) for i in range(6)]
    assert [mock_classification(f) for f in examples]==['potential_mine','metallic_object','potential_mine','unknown','potential_mine','rock']
    assert all(score(f)>=.65 and f['fixture_version']=='demo/2' for f in examples)
    assert mock_classification({'provenance':'synthetic-fixture'})=='potential_target'
    with pytest.raises(ValueError):
        mock_classification({'provenance':'real','mock_classification':'potential_mine'})
