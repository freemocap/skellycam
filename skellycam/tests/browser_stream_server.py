"""Loopback-only HTTP harness for testing the browser stream in Electron."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from skellycam.core.recorders.videos.browser_stream import BrowserStreamRequest, browser_video_chunks


class BrowserStreamServer(ThreadingHTTPServer):
    def __init__(self, *, paths: tuple[Path, ...]) -> None:
        self.paths = paths
        super().__init__(("127.0.0.1", 0), BrowserStreamHandler)


class BrowserStreamHandler(BaseHTTPRequestHandler):
    server: BrowserStreamServer

    def do_GET(self) -> None:
        query = parse_qs(urlsplit(self.path).query)
        try:
            index = int(query["video"][0])
            if index < 0:
                raise ValueError("Video index must be nonnegative")
            request = BrowserStreamRequest(path=self.server.paths[index],
                start_seconds=float(query["start"][0]), duration_seconds=float(query["duration"][0]))
            chunks = browser_video_chunks(request=request)
            first = next(chunks)
        except (KeyError, IndexError, ValueError) as error:
            self.send_error(400, str(error))
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(first)
            for chunk in chunks:
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Disconnect cancels this request's encoder, without affecting other viewers.
            return
        finally:
            chunks.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("port_file", type=Path)
    parser.add_argument("videos", type=Path, nargs="+")
    args = parser.parse_args()
    with BrowserStreamServer(paths=tuple(args.videos)) as server:
        args.port_file.write_text(str(server.server_port), encoding="utf-8")
        server.serve_forever()


if __name__ == "__main__":
    main()
