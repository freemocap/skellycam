"""Decode every accepted frame after normal shutdown or camera failure mid-recording."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from skellycam.tests.reference_recordings.test_concurrent_camera_replay import run_concurrent_replay


@pytest.mark.real_data
@pytest.mark.parametrize("fail_camera", [False, True], ids=["shutdown-recording", "camera-failure-recording"])
async def test_recorded_videos_are_finalized(monkeypatch, fail_camera):
    root = Path.home() / "freemocap_data" / "testing" / "skellycam"
    root.mkdir(parents=True, exist_ok=True)
    warning = root / "FILES_IN_THIS_FOLDER_GET_DELETED_AUTOMATICALLY_DO_NOT_PUT_ANYTHING_YOU_CARE_ABOUT_HERE.txt"
    warning.write_text("Disposable SkellyCam test outputs. Source and prepared recordings are kept elsewhere.\n")
    # A fresh directory prevents old files from satisfying assertions. It is
    # removed on both success and failure, after the harness joins every worker.
    with TemporaryDirectory(prefix="recording-finalization-", dir=root) as temporary:
        await run_concurrent_replay(monkeypatch, fail_camera, recording_directory=Path(temporary))
    assert not Path(temporary).exists()
