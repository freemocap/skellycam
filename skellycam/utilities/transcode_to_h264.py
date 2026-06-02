import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def transcode_to_h264(input_path: Path, output_path: Path) -> None:
    """Transcode a video to H264/MP4 using pyav/libx264.

    Writes atomically via a sibling temp file — ``output_path`` is only
    created if encoding succeeds.  Raises on failure; the temp file is
    always cleaned up.

    The caller is responsible for any post-transcode file management
    (e.g. deleting the original or leaving it as a sidecar source).
    """
    import av  # noqa: TC002 — lazy: av carries dylib baggage on macOS

    tmp_path = output_path.parent / (output_path.stem + '.__tmp__.mp4')
    try:
        with av.open(str(input_path)) as video_in, av.open(str(tmp_path), mode='w') as out:
            v_in = video_in.streams.video[0]
            fps = v_in.average_rate or 30
            v_out = out.add_stream('libx264', rate=fps)
            v_out.width = v_in.codec_context.width
            v_out.height = v_in.codec_context.height
            v_out.pix_fmt = 'yuv420p'
            v_out.options = {'crf': '18', 'preset': 'fast'}

            for frame in video_in.decode(v_in):
                for packet in v_out.encode(frame):
                    out.mux(packet)
            for packet in v_out.encode():
                out.mux(packet)

        tmp_path.rename(output_path)
        logger.info(f"Transcoded to H264: {output_path.name}")
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        logger.error(f"Transcode failed ({input_path.name} → {output_path.name}): {e}")
        raise
