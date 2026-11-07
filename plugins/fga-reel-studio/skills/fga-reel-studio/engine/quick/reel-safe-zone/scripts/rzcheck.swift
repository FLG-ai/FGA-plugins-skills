// Reel Safe Zone: reads the text in each frame with the Mac's built-in text recognition (Vision),
// flags text inside Instagram's Reels red zone, and draws annotated copies of flagged frames.
// Usage: rzcheck <frames_dir> <out_dir> <fps>
import Foundation
import Vision
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let a = CommandLine.arguments
guard a.count >= 4, let fps = Double(a[3]) else { print("usage: rzcheck <frames_dir> <out_dir> <fps>"); exit(1) }
let framesDir = URL(fileURLWithPath: a[1]), outDir = URL(fileURLWithPath: a[2])
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

// Zones on a 1080x1920 frame, scaled to the real frame size.
// top 250 (Reels header), bottom from 1480 (name, caption, music), sides 60, and the button column right of 940 below 1050.
func zones(_ w: CGFloat, _ h: CGFloat) -> [(String, CGRect)] {
    let sx = w / 1080, sy = h / 1920
    return [("top", CGRect(x: 0, y: 0, width: w, height: 250 * sy)),
            ("bottom", CGRect(x: 0, y: 1480 * sy, width: w, height: h - 1480 * sy)),
            ("left edge", CGRect(x: 0, y: 0, width: 60 * sx, height: h)),
            ("right edge", CGRect(x: w - 60 * sx, y: 0, width: 60 * sx, height: h)),
            ("buttons", CGRect(x: 940 * sx, y: 1050 * sy, width: w - 940 * sx, height: 430 * sy))]
}

func load(_ u: URL) -> CGImage? {
    guard let s = CGImageSourceCreateWithURL(u as CFURL, nil) else { return nil }
    return CGImageSourceCreateImageAtIndex(s, 0, nil)
}

func save(_ img: CGImage, _ u: URL) {
    guard let d = CGImageDestinationCreateWithURL(u as CFURL, UTType.jpeg.identifier as CFString, 1, nil) else { return }
    CGImageDestinationAddImage(d, img, [kCGImageDestinationLossyCompressionQuality: 0.85] as CFDictionary)
    CGImageDestinationFinalize(d)
}

let files = (try? FileManager.default.contentsOfDirectory(at: framesDir, includingPropertiesForKeys: nil))?
    .filter { $0.pathExtension.lowercased() == "png" }.sorted { $0.lastPathComponent < $1.lastPathComponent } ?? []
var rows: [[String: Any]] = []

for (i, f) in files.enumerated() {
    guard let img = load(f) else { continue }
    let w = CGFloat(img.width), h = CGFloat(img.height)
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage: img, options: [:]).perform([req])
    let obs = (req.results ?? [])
    let zs = zones(w, h)
    var found: [(String, Float, CGRect, [String])] = []
    for o in obs {
        guard let c = o.topCandidates(1).first, c.confidence >= 0.4 else { continue }
        let b = o.boundingBox
        let r = CGRect(x: b.minX * w, y: (1 - b.maxY) * h, width: b.width * w, height: b.height * h)
        if r.height < 14 * h / 1920 { continue } // tiny background text
        let hit = zs.filter { $0.1.insetBy(dx: -2, dy: -2).intersects(r.insetBy(dx: 8, dy: 8)) }.map { $0.0 }
        found.append((c.string, c.confidence, r, hit))
    }
    let t = Double(i) / fps
    let bad = found.filter { !$0.3.isEmpty }
    for x in bad {
        rows.append(["frame": i, "t": (t * 100).rounded() / 100, "text": x.0, "conf": Double(x.1),
                     "x": Int(x.2.minX), "y": Int(x.2.minY), "w": Int(x.2.width), "h": Int(x.2.height), "zones": x.3])
    }
    if !bad.isEmpty, let ctx = CGContext(data: nil, width: img.width, height: img.height, bitsPerComponent: 8, bytesPerRow: 0,
                                         space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) {
        ctx.draw(img, in: CGRect(x: 0, y: 0, width: w, height: h))
        ctx.translateBy(x: 0, y: h); ctx.scaleBy(x: 1, y: -1) // top-left origin
        ctx.setFillColor(CGColor(red: 1, green: 0, blue: 0, alpha: 0.28))
        for z in zs { ctx.fill(z.1) }
        ctx.setLineWidth(6 * w / 1080)
        for x in found {
            ctx.setStrokeColor(x.3.isEmpty ? CGColor(red: 0.2, green: 0.9, blue: 0.3, alpha: 1) : CGColor(red: 1, green: 0.1, blue: 0.1, alpha: 1))
            ctx.stroke(x.2.insetBy(dx: -6, dy: -6))
        }
        if let out = ctx.makeImage() { save(out, outDir.appendingPathComponent(String(format: "flag_%05d.jpg", i))) }
    }
}
let data = try JSONSerialization.data(withJSONObject: ["frames": files.count, "fps": fps, "hits": rows], options: [.prettyPrinted])
try data.write(to: outDir.appendingPathComponent("hits.json"))
print("checked \(files.count) frames, \(rows.count) text hits in the red zone")
