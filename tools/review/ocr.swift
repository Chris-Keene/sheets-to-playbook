// Vision text recognition: prints JSON [{t, c, x, y, w, h}] with a top-left origin, as fractions of the image.
import Foundation
import Vision
import AppKit
let path = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("[]"); exit(1) }
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = true
req.recognitionLanguages = ["en-GB", "en-US"]
try VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
var out: [[String: Any]] = []
for o in (req.results ?? []) {
  guard let top = o.topCandidates(1).first else { continue }
  let b = o.boundingBox
  // corner points give the baseline direction, so rotated text can be told from upright text
  out.append(["t": top.string, "c": top.confidence, "x": b.minX, "y": 1 - b.maxY, "w": b.width, "h": b.height,
              "tlx": o.topLeft.x, "tly": o.topLeft.y, "trx": o.topRight.x, "try": o.topRight.y])
}
print(String(data: try JSONSerialization.data(withJSONObject: out), encoding: .utf8)!)
