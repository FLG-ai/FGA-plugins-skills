// Finds the main face in each frame with the Mac's face detection (Vision).
// Usage: facefind <frames_dir> <fps>. Prints JSON rows: {"t", "cx", "cy", "h"} (fractions of the frame, top-left origin), or {"t"} with no face.
import Foundation
import Vision
import ImageIO
let a = CommandLine.arguments
guard a.count >= 3, let fps = Double(a[2]) else { print("usage: facefind <frames_dir> <fps>"); exit(1) }
let files = (try? FileManager.default.contentsOfDirectory(at: URL(fileURLWithPath: a[1]), includingPropertiesForKeys: nil))?
    .filter { $0.pathExtension == "png" }.sorted { $0.lastPathComponent < $1.lastPathComponent } ?? []
var out: [[String: Any]] = []
for (i, f) in files.enumerated() {
    guard let s = CGImageSourceCreateWithURL(f as CFURL, nil), let img = CGImageSourceCreateImageAtIndex(s, 0, nil) else { continue }
    let req = VNDetectFaceRectanglesRequest()
    try? VNImageRequestHandler(cgImage: img, options: [:]).perform([req])
    var row: [String: Any] = ["t": Double(i) / fps]
    if let b = (req.results ?? []).max(by: { $0.boundingBox.width < $1.boundingBox.width })?.boundingBox {
        row["cx"] = Double(b.midX); row["cy"] = Double(1 - b.midY); row["h"] = Double(b.height)
    }
    out.append(row)
}
print(String(data: try JSONSerialization.data(withJSONObject: out), encoding: .utf8)!)
