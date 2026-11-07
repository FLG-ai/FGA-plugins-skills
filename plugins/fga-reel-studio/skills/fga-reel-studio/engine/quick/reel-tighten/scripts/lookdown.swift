// Flags moments the person looks down, using the Mac's face detection (Vision). Usage: lookdown <frames_dir> <fps>
// Prints JSON: [{"t": seconds, "pitch": radians, "face": true/false}] for every frame.
import Foundation
import Vision
import ImageIO
let a = CommandLine.arguments
guard a.count >= 3, let fps = Double(a[2]) else { print("usage: lookdown <frames_dir> <fps>"); exit(1) }
let files = (try? FileManager.default.contentsOfDirectory(at: URL(fileURLWithPath: a[1]), includingPropertiesForKeys: nil))?
    .filter { $0.pathExtension == "png" }.sorted { $0.lastPathComponent < $1.lastPathComponent } ?? []
var out: [[String: Any]] = []
for (i, f) in files.enumerated() {
    guard let s = CGImageSourceCreateWithURL(f as CFURL, nil), let img = CGImageSourceCreateImageAtIndex(s, 0, nil) else { continue }
    let req = VNDetectFaceRectanglesRequest()
    if #available(macOS 12.0, *) { req.revision = VNDetectFaceRectanglesRequestRevision3 }
    try? VNImageRequestHandler(cgImage: img, options: [:]).perform([req])
    let face = (req.results ?? []).max { $0.boundingBox.width < $1.boundingBox.width }
    var row: [String: Any] = ["t": Double(i) / fps, "face": face != nil]
    if #available(macOS 12.0, *), let p = face?.pitch { row["pitch"] = p.doubleValue }
    out.append(row)
}
let data = try JSONSerialization.data(withJSONObject: out)
FileManager.default.createFile(atPath: "/dev/stdout", contents: nil)
print(String(data: data, encoding: .utf8)!)
