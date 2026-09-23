# Reference-video capture tests

From the polyrepo workspace (`project`):

```powershell
poe -C repos/skellycam test-reference
poe -C repos/skellycam test-reference-sample
```

From a standalone SkellyCam checkout, omit `-C repos/skellycam`. The existing
SkellyCam `.venv` environment must include its development dependencies. These
tasks use it directly without running uv sync or installing packages. The first task
runs all 222 frames of each of three test cameras, two injected read-failure
cases, and acquisition-helper tests. The second runs all 1,108 frames of each
of three sample cameras. Plain pytest on this directory runs both datasets.

## Data locations and acquisition

The helper is independent of FreeMoCap, SkellyTracker, and SkellyForge. It reuses
raw videos from these locations, downloading only when the recording is absent:

| Dataset | Location | Download |
| --- | --- | --- |
| Test | `~/freemocap_data/recordings/freemocap_test_data` | https://github.com/freemocap/skellysamples/releases/download/test_data_v06_09_25/freemocap_test_data.zip |
| Sample | `~/freemocap_data/recordings/freemocap_sample_data` | https://github.com/freemocap/skellysamples/releases/download/sample_data_v06_12_25/freemocap_sample_data.zip |

On this workspace's Windows machine, `~` is `C:\Users\jonma`. Both recordings
contain the same calibration-and-body-movement recording; test data is decimated.
Neither calibration nor processed motion-capture outputs are needed here.

Downloads are staged under the recordings root, checked for unsafe extraction
paths and one recording containing three nonempty videos, then published under
the canonical name. Temporary download files are cleaned automatically. Existing
incomplete recordings fail clearly and are preserved. No normal recording outputs
are overwritten. Acquisition validates structure; the capture tests validate the
actual decoded content and expected counts. Downloads are not currently checked
against pinned archive digests.

## What this proves

For every reference frame, a real file-backed OpenCV capture passes through the
production `opencv_get_frame` grab/retrieve path into the production structured
frame buffer. Its image must match a separate sequential OpenCV reader exactly,
except for the top 80 pixel rows where the production helper stamps frame text.
Checks cover frame numbering, image shape/type, ordered capture-call timestamps,
EOF, repeated EOF, reads after release, and release of both capture handles.
Injected grab/retrieve failures verify no successful-frame increment; only those
two negative cases use a mock capture.

This exercises the same helper used for live cameras, but not physical camera
drivers, camera-loop scheduling, group synchronization, shared-memory publication,
recording, or wall-clock replay pacing. Timestamps are execution-clock measurements,
not original sensor capture times. Sample-video decoding here does not run the
expensive sample-data calibration or motion-capture pipeline.
