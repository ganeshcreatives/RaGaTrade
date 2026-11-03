"""Synthetic fixtures exercise correctness only; never used as model artifacts."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from features import build_features, FEATURE_ORDER
from train import walk_forward_splits, calibration_splits
import main


def bars(n=100):
    t = pd.date_range('2026-01-05T04:00:00Z', periods=n, freq='min')
    return pd.DataFrame(dict(symbol='TEST', timestamp=t, open=100., high=102., low=99., close=101., volume=100))


class ResearchTests(unittest.TestCase):
    def test_missing_minute_resets_features(self):
        data = bars().drop(index=40)
        result = build_features(data)
        self.assertTrue(result.loc[41, FEATURE_ORDER[:9]].isna().any())
        self.assertFalse(result.loc[62, FEATURE_ORDER].isna().any())

    def test_future_prices_cannot_change_past_features(self):
        data = bars()
        before = build_features(data)
        data.loc[70:, ['open','high','low','close']] *= 2
        after = build_features(data)
        pd.testing.assert_frame_equal(before.loc[:69], after.loc[:69])

    def test_invalid_ohlc_rejected(self):
        data = bars(); data.loc[40, 'high'] = 1
        self.assertNotIn(40, build_features(data).index)

    def test_session_boundary_resets_window(self):
        data = pd.concat([bars(50), bars(50).assign(timestamp=lambda d: d.timestamp + pd.Timedelta(days=1))], ignore_index=True)
        result = build_features(data)
        self.assertTrue(result.loc[50, FEATURE_ORDER[:9]].isna().any())
        self.assertAlmostEqual(result.loc[75, 'vwap_distance'], 101/((102+99+101)/3)-1)

    def test_outer_and_calibration_labels_are_purged(self):
        data = bars(1500); data['label_end'] = data.timestamp + pd.Timedelta(minutes=15)
        data['target'] = np.arange(len(data)) % 2
        for splits in [walk_forward_splits(data, 15), calibration_splits(data, 15)]:
            count = 0
            for train, valid in splits:
                self.assertLess(data.iloc[train].label_end.max(), data.iloc[valid].timestamp.min())
                count += 1
            self.assertGreaterEqual(count, 2)

    def test_unapproved_and_tampered_models_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory)/'active.joblib'; manifest = Path(directory)/'active.json'
            artifact.write_bytes(b'not a pickle')
            info = dict(approval='CANDIDATE_NOT_PROMOTED', reviewer='test', approvalNote='fixture', featureOrder=FEATURE_ORDER, artifactSha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
            with patch.object(main,'ARTIFACT',artifact), patch.object(main,'MANIFEST',manifest):
                manifest.write_text(json.dumps(info)); self.assertEqual(main.status()['source'], 'UNAPPROVED_MODEL')
                info['approval']='HUMAN_APPROVED'; info['artifactSha256']='wrong'
                manifest.write_text(json.dumps(info)); self.assertEqual(main.status()['source'], 'INVALID_ARTIFACT')

    def test_future_and_naive_timestamps_rejected(self):
        client=TestClient(main.app)
        body=dict(symbol='TEST', data_freshness_ms=0, source='POINT_IN_TIME_FEATURES', features={})
        for timestamp in [(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(), '2026-01-01T10:00:00']:
            self.assertEqual(client.post('/internal/ml/predict',json={**body,'data_as_of':timestamp}).status_code,422)

    def test_no_model_returns_no_forecast(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(main,'ARTIFACT',Path(directory)/'absent'):
            response=TestClient(main.app).post('/internal/ml/predict',json=dict(symbol='TEST',data_freshness_ms=0,data_as_of=datetime.now(timezone.utc).isoformat(),source='POINT_IN_TIME_FEATURES',features={}))
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['action'],'NO_TRADE')
            self.assertIsNone(response.json()['probabilityUp'])

if __name__ == '__main__':
    unittest.main()
