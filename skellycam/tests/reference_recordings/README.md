# Reference-video capture tests

From the polyrepo workspace (`project`):

```powershell
poe -C repos/skellycam test-reference
poe -C repos/skellycam test-reference-sample
poe -C repos/skellycam test-reference-loop
poe -C repos/skellycam test-reference-concurrent
poe -C repos/skellycam test-camera-lifecycle
poe -C repos/skellycam test-recording-safety
poe -C repos/skellycam test-recording-lifecycle
```

From a standalone SkellyCam checkout, omit `-C repos/skellycam`. The existing
SkellyCam `.venv` environment must include its development dependencies. These
tasks use it directly without running uv sync or installing packages. The first task
runs all 222 frames of each of three test cameras, two injected read-failure
cases, and acquisition-helper tests. The second runs all 1,108 frames of each
of three sample cameras. Plain pytest on this directory runs both datasets.
The first task also includes camera-loop failure regressions and the real shared-memory
tests available separately through `test-reference-loop`, plus concurrent replay
available through `test-reference-concurrent`. The lifecycle task
runs the focused camera/group shutdown and worker tests without datasets or hardware.

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
Injected grab/retrieve failures verify no successful-frame increment. Additional
failure tests run the production camera loop and worker cleanup with mocked captures
and shared-memory publication spies: exhausted retries and shutdown during a failed
read must not publish stale frames. A two-camera test checks that one failing camera
stops its synchronization-waiting sibling, preserves its error status, releases both
capture handles, and closes both shared-memory attachments without stopping the app.

The lifecycle suite checks pause/resume acknowledgements, failure detection and the
10-second response deadline, plus bounded non-recording worker shutdown despite stale status flags.
It also checks that closed groups report inactive and that recording failure does not
block group cleanup. Existing worker-isolation tests exercise actual thread/process
exceptions and abrupt process exit. Failure policy is to stop the affected group;
there is no automatic camera restart. Python threads cannot be forcibly killed:
shutdown raises if a worker survives escalation, rather than reporting success.

The shared-memory tests replay all 222 frames from each of the three test videos
through the production camera worker and capture loop. Hardware setup is replaced
with a file-backed capture; publication writes into a real four-slot ring buffer.
A separately attached consumer checks every frame's pixels, camera identity, frame
number and capture timestamps, including repeated buffer wraparound. Synchronous
observation hooks consume each frame before the next write and request pause/resume.
While paused, neither the video cursor nor the publication index may advance.
Each video tests both requested shutdown and EOF failure, with no stale publication.
The worker must release capture and close all nine shared-memory handles, and fixture
cleanup must remove all nine named allocations. No recording outputs are written.

The concurrent tests run three production camera workers in separate threads,
with a shared production orchestrator and separate real four-slot buffers. Each
publication is read through a separate shared-memory attachment and compared with
an independent decoder. Extra work in one camera exercises unequal progress;
published frame counts must stay within one frame of one another. There are no
test barriers between ordinary frames. Group pause/resume uses the real orchestrator
and checks that all video cursors and publication indices stay fixed while paused.
One case completes all 222 frames per camera; the other seeks one capture to EOF
after resuming and requires production code to stop all three workers while the
other two videos still have unread frames. Both cases check capture release,
worker exit, and removal of all 27 shared-memory allocations. Test cleanup also
signals stop and joins workers before releasing their buffers if assertions fail.

Recording-safety tests reuse the concurrent replay with real H.264 writers, covering
shutdown during recording and failure of one camera while the others are recording.
Every saved video is reopened and every accepted frame decoded; lossy pixel error
must remain below a mean absolute difference of 8/255 outside the text overlay.
Recording-finished messages must contain every accepted frame number. This validates
video finalization and its completion messages, not the later group timing/metadata
export pipeline. Test outputs live in fresh temporary directories under
`~/freemocap_data/testing/skellycam/`, with a conspicuous deletion warning at the root,
and are removed after workers exit and saved videos have been checked. Source videos
and retained processed reference data are untouched.

The recording-lifecycle tests use the same three concurrent file-backed cameras and
call the real camera group's start/stop methods. One case completes two recordings
without reconnecting cameras; another completes the first recording and fails a
camera during the second. Successful stops must leave capture running. For each
successful recording, tests decode every saved frame against its original source
frame, check camera/video associations, recording-local and connection frame indices,
camera and multiframe timing, and statistics. The playback HTTP routes must list the
generated videos, return the recorded timing, and serve the saved MP4 bytes.
The second session must leave every file from the first unchanged. After camera
failure, all workers must exit and every frame reported saved must remain decodable;
stopping the failed group must raise without producing successful group metadata.
These cases use fresh disposable folders under the same testing root and remove
them after worker shutdown, so previous runs cannot satisfy output assertions.
They exercise real writers and group finalization with threads; physical camera
setup, audio recording, frontend rendering, and process spawning are outside this test.

Active recordings take priority over shutdown deadlines. Camera workers are not
daemon workers; automatic termination waits while their recording flag is set.
The API asks the worker monitor to shut down after saves finish. Electron requests
the API shutdown and waits for backend exit instead of killing the process tree.
A failed request leaves the backend running for a retry. Backend startup no longer
kills an existing server occupying the port. A stuck save can therefore hold shutdown
open indefinitely; automatic timeouts must not sacrifice recordings. External force
kills, power loss, and storage/encoder failures cannot be made lossless by this policy.

Additional safety tests use a real child process with a buffered H.264 writer and
verify terminate/kill requests wait for finalization, then decode every written frame.
Fault injection checks that flush errors still attempt container closure and that
completion-notification errors do not prevent playable video output.
Electron shutdown protocol tests use Node's TypeScript stripping (tested with Node 24):
`npm.cmd --prefix skellycam-ui run test:recording-shutdown` on Windows from the SkellyCam
checkout (`npm` instead of `npm.cmd` on macOS/Linux).

These tests do not prove cross-process multi-camera delivery, physical camera driver
behavior, or wall-clock replay pacing. Timestamps are execution-clock measurements,
not original sensor capture times. Sample-video decoding here does not run the
expensive sample-data calibration or motion-capture pipeline.
