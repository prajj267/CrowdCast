# 06 — Object detection with YOLOX

Code: `backend/crowdcast/vision/yolox_onnx.py`. Method: `DOCUMENTATION/09` §2–4.
Model source and checksums: `configs/vision/yolox_models.yaml`.

## What a detector does

Input: an image. Output: a list of **boxes** (x1, y1, x2, y2), each with a **class** ("person")
and a **score** (how confident). We count people per zone from these boxes later (doc 09 §6),
using the *foot point* (bottom-centre of the box), because zones are areas on the floor.

## Pretrained on COCO

YOLOX was trained by its authors on **COCO**, a public dataset of everyday photos labelled with 80
object classes; class 0 is "person". We use the weights as they are (no training of our own) and
keep only the person class. That is why it also recognises dogs and bicycles, which we used for
the smoke test.

## YOLOX variants

nano, tiny and s are the same design at different sizes: smaller = faster but less accurate. The
exported files have a **fixed input size**: nano and tiny take 416×416 pixels, s takes 640×640.
Which one we use is decided by measured speed and accuracy (tasks 1.4.2–1.4.3, 7.1), not guessed.

## The pipeline, step by step

1. **Letterbox.** The network needs a square input. Stretching the image would distort people, so
   we scale it by one ratio `r = min(416/h, 416/w)`, keeping its shape, and fill the leftover area
   with grey (value 114). We remember `r` to map boxes back to the original image afterwards.
2. **Network.** For every **anchor point** on three grids it outputs one row of 85 numbers: box
   position/size (4), **objectness** ("is there an object here?", 1) and 80 class probabilities.
   The grids have **strides** 8, 16 and 32: the image is divided into cells of 8, 16 or 32 pixels.
   Fine grids find small (distant) people; coarse grids find large ones. For a 416 input:
   52² + 26² + 13² = 3549 rows (we confirmed the model outputs exactly `[1, 3549, 85]`).
3. **Decode.** The raw box numbers are relative to the cell: centre = (offset + cell index) ×
   stride, width = e^(raw) × stride. This turns them into pixel boxes.
4. **Score.** person score = objectness × P(person). Keep rows above a threshold (0.1 for
   tracking, so the tracker also gets weak detections; see ByteTrack in doc 09 §5).
5. **NMS (non-maximum suppression).** Many neighbouring anchor points fire on the same person.
   NMS sorts boxes by score, keeps the best, deletes others that overlap it too much
   (**IoU** = intersection area ÷ union area > 0.45), and repeats.
6. **Undo the letterbox** (divide by `r`) and clip boxes to the image.

## ONNX and ONNX Runtime

- **ONNX** is an open file format for trained networks, independent of the framework they were
  trained in (YOLOX was trained in PyTorch).
- **ONNX Runtime** runs ONNX files efficiently on the CPU. This lets us avoid installing PyTorch
  and needing a GPU — important on this laptop (no NVIDIA, no CUDA).
- We use YOLOX rather than Ultralytics YOLO because of the **licence**: YOLOX is Apache-2.0
  (permissive); Ultralytics is AGPL-3.0 (decision D2).

## A finding from the smoke test (good viva story)

YOLOX changed its input convention between versions: old code converted to RGB and normalised with
ImageNet mean/std; newer code feeds raw BGR pixels. The official ONNX downloads are from the old
release, but the docs pair them with the new code. Rather than guess, we ran all three models on
YOLOX's own sample image both ways: the raw-BGR input found the dog, bicycle and vehicle; the
legacy input found nothing. The answer and how it was found are recorded in the manifest.
Lesson: verify assumptions with a test whose correct answer you know.

## Privacy

Only boxes and scores leave the detector. No frames, crops, faces or appearance features are
stored, and tracks exist only in memory (doc 19).

## Viva questions

- **Why might counts be too low in dense crowds?** People overlap; the detector misses occluded
  bodies and NMS can merge two close people into one. Doc 09 §7 flags such windows as lower bounds.
- **What does the score threshold trade off?** Lower → more people found but more false boxes;
  higher → fewer false boxes but more misses.
- **Why the foot point rather than the box centre?** Zones are floor areas; a tall person standing
  near a boundary has a centre that can project into the wrong zone.
- **Why not train your own detector?** No GPU and no labelled data of our own (D6); a pretrained
  COCO detector is the documented starting point, and its error is measured on public data.
