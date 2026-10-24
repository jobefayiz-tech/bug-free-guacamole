#!/usr/bin/env python3
"""Compress a video so the result fits under a target size (default 30 MB).

Uses ffmpeg two-pass H.264 encoding: the bitrate is computed from the video
duration and the size you ask for, so the output lands just under the limit.

    python compress_video.py input.mp4              # -> input_30mb.mp4
    python compress_video.py input.mp4 -t 25 -o small.mp4
    python compress_video.py                        # no arguments: opens a window

ffmpeg is taken from PATH, or from `pip install imageio-ffmpeg` if missing.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

MB = 1_000_000            # decimal MB: also fits under a limit counted as MiB
SAFETY = 0.94             # aim below the target; container overhead and rate control drift
MIN_VIDEO_KBPS = 80       # below this the picture is unwatchable, so refuse instead
PROGRESS_KEY = re.compile(
    r"^(frame|fps|stream_\S+|bitrate|total_size|out_time_us|out_time_ms|out_time|"
    r"dup_frames|drop_frames|speed|progress)="
)


class CompressError(Exception):
    pass


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise CompressError(
            "ffmpeg not found. Install it from https://ffmpeg.org "
            "or run: pip install imageio-ffmpeg"
        )


def probe(ffmpeg, path):
    """Return (duration_seconds, has_audio) by parsing `ffmpeg -i` output."""
    info = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, errors="replace",
    ).stderr
    if not re.search(r"Stream #.*Video:", info):
        raise CompressError(f"{path} does not look like a video file")
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", info)
    if not m:
        raise CompressError("could not read the video duration")
    duration = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    if duration <= 0:
        raise CompressError("the video has zero duration")
    return duration, bool(re.search(r"Stream #.*Audio:", info))


def pick_audio(total_kbps):
    """Return (audio_kbps, mono): spend less on audio when the budget is tight."""
    if total_kbps < 400:
        return 48, True
    if total_kbps < 800:
        return 64, False
    return 96, False


def pick_height(video_kbps):
    """Largest frame height that still looks acceptable at this video bitrate."""
    if video_kbps < 300:
        return 360
    if video_kbps < 700:
        return 480
    if video_kbps < 1500:
        return 720
    return 1080


def run_ffmpeg(cmd, start, span, duration, on_progress):
    """Run ffmpeg, mapping its progress onto [start, start + span] of the whole job."""
    p = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, errors="replace",
    )
    tail = deque(maxlen=15)
    for line in p.stdout:
        line = line.strip()
        if line.startswith("out_time_us="):
            try:
                done = int(line.split("=", 1)[1]) / 1e6 / duration
            except ValueError:  # "N/A" before the first frame
                continue
            on_progress(start + span * min(max(done, 0.0), 1.0))
        elif line and not PROGRESS_KEY.match(line):
            tail.append(line)
    if p.wait():
        raise CompressError("ffmpeg failed:\n" + "\n".join(tail))


def encode(ffmpeg, src, dst, video_kbps, audio, height, preset, duration, on_progress):
    audio_kbps, mono = audio
    with tempfile.TemporaryDirectory() as tmp:
        base = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-i", str(src), "-map", "0:v:0",
            "-vf", f"scale=-2:min(ih\\,{height})",   # shrink only, never upscale
            "-c:v", "libx264", "-preset", preset, "-pix_fmt", "yuv420p",
            "-b:v", f"{video_kbps}k", "-maxrate", f"{video_kbps * 3 // 2}k",
            "-bufsize", f"{video_kbps * 3}k",
            "-passlogfile", os.path.join(tmp, "pass"), "-progress", "pipe:1",
        ]
        run_ffmpeg(base + ["-pass", "1", "-an", "-f", "null", os.devnull],
                   0.0, 0.4, duration, on_progress)
        if audio_kbps:
            a = ["-map", "0:a:0", "-c:a", "aac", "-b:a", f"{audio_kbps}k"]
            a += ["-ac", "1"] if mono else []
        else:
            a = ["-an"]
        run_ffmpeg(base + ["-pass", "2", *a, "-movflags", "+faststart", str(dst)],
                   0.4, 0.6, duration, on_progress)


def compress(src, dst=None, target_mb=30, preset="fast", on_progress=lambda f: None):
    """Compress `src` to at most `target_mb` MB. Returns (output_path, size_bytes)."""
    src = Path(src)
    if not src.is_file():
        raise CompressError(f"file not found: {src}")
    if target_mb <= 0:
        raise CompressError("target size must be positive")
    target_bytes = int(target_mb * MB)
    if src.stat().st_size <= target_bytes:
        raise CompressError(
            f"{src.name} is already {src.stat().st_size / MB:.1f} MB, under {target_mb:g} MB"
        )
    dst = Path(dst) if dst else src.with_name(f"{src.stem}_{target_mb:g}mb.mp4")
    if dst.resolve() == src.resolve():
        raise CompressError("output path must differ from the input file")

    ffmpeg = find_ffmpeg()
    duration, has_audio = probe(ffmpeg, src)
    budget = target_bytes * SAFETY

    for _ in range(3):
        total_kbps = budget * 8 / duration / 1000
        audio = pick_audio(total_kbps) if has_audio else (0, False)
        video_kbps = int(total_kbps - audio[0])
        if video_kbps < MIN_VIDEO_KBPS:
            raise CompressError(
                f"a {duration / 60:.1f} min video cannot fit in {target_mb:g} MB "
                "with usable quality; raise the target size"
            )
        encode(ffmpeg, src, dst, video_kbps, audio, pick_height(video_kbps),
               preset, duration, on_progress)
        size = dst.stat().st_size
        if size <= target_bytes:
            return dst, size
        budget *= target_bytes / size * 0.97   # overshot: retry with a tighter budget
    raise CompressError(f"could not get under {target_mb:g} MB (last try {size / MB:.1f} MB)")


def run_gui():
    import queue
    import threading
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("Video Compressor | ضغط الفيديو")
    root.resizable(False, False)
    path_var, size_var, status_var = tk.StringVar(), tk.StringVar(value="30"), tk.StringVar()
    events = queue.Queue()

    def browse():
        p = filedialog.askopenfilename(
            title="اختر الفيديو",
            filetypes=[("Video", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.3gp"), ("All", "*.*")],
        )
        if p:
            path_var.set(p)

    def work(src, mb):
        try:
            dst, size = compress(src, target_mb=mb,
                                 on_progress=lambda f: events.put(("progress", f)))
            events.put(("done", f"تم / Done: {dst}  ({size / MB:.1f} MB)"))
        except CompressError as e:
            events.put(("error", str(e)))
        except Exception as e:  # keep the window alive on unexpected failures
            events.put(("error", f"{type(e).__name__}: {e}"))

    def start():
        src = path_var.get().strip()
        try:
            mb = float(size_var.get())
        except ValueError:
            return messagebox.showerror("خطأ / Error", "الحجم المطلوب رقم / Size must be a number")
        if not src:
            return messagebox.showerror("خطأ / Error", "اختر فيديو أولاً / Choose a video first")
        button.config(state="disabled")
        bar["value"] = 0
        status_var.set("جاري الضغط... / Compressing...")
        threading.Thread(target=work, args=(src, mb), daemon=True).start()

    def poll():
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == "progress":
                    bar["value"] = value * 100
                    continue
                button.config(state="normal")
                if kind == "done":
                    bar["value"] = 100
                    status_var.set(value)
                else:
                    status_var.set("")
                    messagebox.showerror("خطأ / Error", value)
        except queue.Empty:
            pass
        root.after(100, poll)

    pad = {"padx": 8, "pady": 6}
    ttk.Entry(root, textvariable=path_var, width=50).grid(row=0, column=0, **pad)
    ttk.Button(root, text="اختر / Browse", command=browse).grid(row=0, column=1, **pad)
    ttk.Label(root, text="الحجم المطلوب (MB) / Target size (MB)").grid(row=1, column=0, sticky="w", **pad)
    ttk.Entry(root, textvariable=size_var, width=8).grid(row=1, column=1, **pad)
    button = ttk.Button(root, text="ابدأ الضغط / Compress", command=start)
    button.grid(row=2, column=0, columnspan=2, **pad)
    bar = ttk.Progressbar(root, length=420, maximum=100)
    bar.grid(row=3, column=0, columnspan=2, **pad)
    ttk.Label(root, textvariable=status_var, wraplength=420).grid(row=4, column=0, columnspan=2, **pad)
    poll()
    root.mainloop()


def main():
    ap = argparse.ArgumentParser(description="Compress a video to fit under a target size.")
    ap.add_argument("input", nargs="?", help="video file (omit to open the window)")
    ap.add_argument("-o", "--output", help="output file (default: <name>_<size>mb.mp4)")
    ap.add_argument("-t", "--target", type=float, default=30, help="target size in MB (default 30)")
    ap.add_argument("--preset", default="fast",
                    help="x264 speed/quality preset: ultrafast..veryslow (default fast)")
    args = ap.parse_args()
    if not args.input:
        return run_gui()
    try:
        dst, size = compress(
            args.input, args.output, args.target, args.preset,
            on_progress=lambda f: print(f"\r{f * 100:5.1f}%", end="", file=sys.stderr, flush=True),
        )
    except CompressError as e:
        print(file=sys.stderr)
        sys.exit(f"error: {e}")
    print(f"\nDone: {dst} ({size / MB:.1f} MB)")


if __name__ == "__main__":
    main()
