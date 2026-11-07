// Scores each frame for a cover: face capture quality (sharp, eyes open, facing the camera) plus face box and head turn.
// Usage: facequality <frames_dir>. Prints JSON rows {"file","q","x","y","w","h","yaw","pitch"} (box as fractions, top-left origin).
import Foundation
import Vision
import ImageIO
let a = CommandLine.arguments
guard a.count >= 2 else { print("usage: facequality <frames_dir>"); exit(1) }
let files = (try? FileManager.default.contentsOfDirectory(at: URL(fileURLWithPath: a[1]), includingPropertiesForKeys: nil))?
    .filter { ["png", "jpg", "jpeg"].contains($0.pathExtension.lowercased()) }.sorted { $0.lastPathComponent < $1.lastPathComponent } ?? []
var out: [[String: Any]] = []
for f in files {
    guard let s = CGImageSourceCreateWithURL(f as CFURL, nil), let img = CGImageSourceCreateImageAtIndex(s, 0, nil) else { continue }
    let rect = VNDetectFaceRectanglesRequest()
    if #available(macOS 12.0, *) { rect.revision = VNDetectFaceRectanglesRequestRevision3 }
    try? VNImageRequestHandler(cgImage: img, options: [:]).perform([rect])
    var row: [String: Any] = ["file": f.lastPathComponent, "q": 0.0]
    if let face = (rect.results ?? []).max(by: { $0.boundingBox.width < $1.boundingBox.width }) {
        let q = VNDetectFaceCaptureQualityRequest(); q.inputFaceObservations = [face]
        try? VNImageRequestHandler(cgImage: img, options: [:]).perform([q])
        let b = face.boundingBox
        row["q"] = Double(q.results?.first?.faceCaptureQuality ?? 0)
        row["x"] = Double(b.minX); row["y"] = Double(1 - b.maxY); row["w"] = Double(b.width); row["h"] = Double(b.height)
        if #available(macOS 12.0, *) { row["yaw"] = face.yaw?.doubleValue ?? 0; row["pitch"] = face.pitch?.doubleValue ?? 0 }
    }
    out.append(row)
}
print(String(data: try JSONSerialization.data(withJSONObject: out), encoding: .utf8)!)
