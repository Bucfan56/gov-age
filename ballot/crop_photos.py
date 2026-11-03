#!/usr/bin/env python3
"""
Crop every candidate photo to the card's photo window (3:2), centered on the face, whole face in frame.

    py ballot/crop_photos.py            # crops new photos only
    py ballot/crop_photos.py --all      # re-crops everything

Reads ballot/photos.json, writes ballot/photos/c/<file>.jpg and records {"c": "<file>", "face": true|false} back
into photos.json. Faces are found with OpenCV YuNet (largest confident face wins); a photo with no
detectable face falls back to the upper-middle of the frame and is marked face:false for a hand check.
Face model: OpenCV Zoo YuNet (ballot/models/face_detection_yunet_2023mar.onnx, from github.com/opencv/opencv_zoo).
"""
import json, sys
from pathlib import Path

import cv2

ROOT = Path(__file__).parent
SRC = ROOT / "photos"
OUT = SRC / "c"
ASPECT = 1.5          # width / height of the card's photo window
W_OUT = 720

MODEL = str(ROOT / "models" / "face_detection_yunet_2023mar.onnx")


def face_box(img):
    h, w = img.shape[:2]
    scale = 640 / max(h, w) if max(h, w) > 640 else 1.0
    im = cv2.resize(img, (int(w * scale), int(h * scale))) if scale != 1.0 else img
    det = cv2.FaceDetectorYN.create(MODEL, "", (im.shape[1], im.shape[0]), 0.6, 0.3, 50)
    _, faces = det.detect(im)
    if faces is None or not len(faces):
        return None
    f = max(faces, key=lambda f: f[2] * f[3] * f[14])        # biggest confident face
    x, y, fw, fh = (f[:4] / scale).tolist()
    return int(x), int(y), int(fw), int(fh)


def crop(img, box):
    h, w = img.shape[:2]
    if box is not None:
        x, y, fw, fh = box
        cx, cy = x + fw / 2, y + fh * 0.62          # a little below face center: keeps chin + a touch of shoulders
        ch = min(h, max(fh * 2.6, h * 0.2))         # face takes ~38% of the window height
    else:
        cx, cy, ch = w / 2, h * 0.38, h * 0.62
    cw = ch * ASPECT
    if cw > w:                                       # narrow (portrait) photo: full width, shorter window
        cw = w; ch = cw / ASPECT
    x0 = int(min(max(cx - cw / 2, 0), w - cw)); y0 = int(min(max(cy - ch / 2, 0), h - ch))
    out = img[y0:y0 + int(ch), x0:x0 + int(cw)]
    return cv2.resize(out, (W_OUT, int(W_OUT / ASPECT)), interpolation=cv2.INTER_AREA)


def main():
    pm = json.loads((ROOT / "photos.json").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    done = noface = 0
    for name, p in pm.items():
        f = SRC / p["f"]
        if not f.exists() or (p.get("c") and "--all" not in sys.argv and (OUT / p["c"]).exists()):
            continue
        img = cv2.imread(str(f), cv2.IMREAD_COLOR)
        if img is None:
            print("unreadable", name, p["f"]); continue
        box = face_box(img)
        out_name = Path(p["f"]).stem + ".jpg"
        cv2.imwrite(str(OUT / out_name), crop(img, box), [cv2.IMWRITE_JPEG_QUALITY, 86])
        p["c"] = out_name; p["face"] = box is not None
        done += 1; noface += box is None
    (ROOT / "photos.json").write_text(json.dumps(pm, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"cropped {done}, no face found in {noface}")


if __name__ == "__main__":
    main()
