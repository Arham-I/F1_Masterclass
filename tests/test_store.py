"""Regression test: parquet round-trips a missing value in an object column as Python None,
not the np.nan it was written with. Caught via a pandas FutureWarning in test_data_freshness,
not by any test - assert_frame_equal currently tolerates the mismatch but says it will stop."""
import numpy as np
import pandas as pd

from f1cc import store


def test_object_column_nulls_survive_a_parquet_round_trip_as_nan(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    df = pd.DataFrame({"main_compound": ["SOFT", np.nan, "HARD"]})
    store.write("features", 2099, df)

    back = store.read("features", [2099])
    assert isinstance(back["main_compound"].iloc[1], float)      # not None
    assert np.isnan(back["main_compound"].iloc[1])
    pd.testing.assert_frame_equal(df, back)                       # the actual guarantee that matters
