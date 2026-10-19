"""Missing-data acquisition preserves existing inputs and rejects unsafe archives."""

from io import BytesIO
from zipfile import ZipFile

import pytest

from skellycam.tests.reference_recordings import datasets


def archive_bytes(names):
    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        for name in names:
            archive.writestr(name, b"video")
    return payload.getvalue()


@pytest.mark.parametrize("folder", ["synchronized_videos", "videos/synchronized"])
def test_download_then_reuse_without_network(tmp_path, monkeypatch, folder):
    payload = archive_bytes([f"recording/{folder}/cam{index}.mp4" for index in range(3)])
    monkeypatch.setattr(datasets, "urlopen", lambda *args, **kwargs: BytesIO(payload))
    paths = datasets.acquire(datasets.TEST, recordings_root=tmp_path)
    assert len(paths) == 3
    assert all(path.is_relative_to(tmp_path / datasets.TEST.name) for path in paths)

    def unexpected_download(*args, **kwargs):
        pytest.fail("Existing recording triggered a download")

    monkeypatch.setattr(datasets, "urlopen", unexpected_download)
    assert datasets.acquire(datasets.TEST, recordings_root=tmp_path) == paths
    assert list(tmp_path.iterdir()) == [tmp_path / datasets.TEST.name]


@pytest.mark.parametrize("member", ["../escape.mp4", "C:/escape.mp4", "/escape.mp4"])
def test_unsafe_archive_is_not_published(tmp_path, monkeypatch, member):
    payload = archive_bytes([member])
    monkeypatch.setattr(datasets, "urlopen", lambda *args, **kwargs: BytesIO(payload))
    with pytest.raises(ValueError, match="Unsafe"):
        datasets.acquire(datasets.TEST, recordings_root=tmp_path)
    assert not list(tmp_path.iterdir())


def test_incomplete_existing_recording_is_preserved(tmp_path, monkeypatch):
    recording = tmp_path / datasets.TEST.name
    recording.mkdir()
    sentinel = recording / "keep.txt"
    sentinel.write_text("keep")
    with pytest.raises(ValueError, match="preserved"):
        datasets.acquire(datasets.TEST, recordings_root=tmp_path)
    assert sentinel.read_text() == "keep"


def test_incomplete_download_does_not_publish_recording(tmp_path, monkeypatch):
    payload = archive_bytes(["recording/synchronized_videos/cam.mp4"])
    monkeypatch.setattr(datasets, "urlopen", lambda *args, **kwargs: BytesIO(payload))
    with pytest.raises(ValueError, match="three"):
        datasets.acquire(datasets.TEST, recordings_root=tmp_path)
    assert not list(tmp_path.iterdir())
