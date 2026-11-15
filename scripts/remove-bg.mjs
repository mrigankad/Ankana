import { mkdirSync, readdirSync } from "node:fs";
import path from "node:path";
import sharp from "sharp";

const SRC = "assets/source/images";
const OUT = "assets/source/processed";
mkdirSync(OUT, { recursive: true });
const files = readdirSync(SRC).filter((f) => /\.(jpe?g|png)$/i.test(f));

for (const file of files) {
  const img = sharp(path.join(SRC, file)).resize(768, 768, { fit: "inside" });
  const { data, info } = await img.raw().toBuffer({ resolveWithObject: true });
  const { width, height, channels } = info;
  const px = (x, y) => {
    const i = (y * width + x) * channels;
    return [data[i], data[i + 1], data[i + 2]];
  };
  // Checkerboard-flattened exports have TWO background shades: sample the
  // border ring, take the corner color as bg1 and the ring color farthest
  // from it as bg2, then key against both.
  const ring = [];
  for (let x = 0; x < width; x += 6) { ring.push(px(x, 1), px(x, height - 2)); }
  for (let y = 0; y < height; y += 6) { ring.push(px(1, y), px(width - 2, y)); }
  const bg1 = px(2, 2);
  let bg2 = bg1, best = -1;
  for (const p of ring) {
    const d = Math.hypot(p[0]-bg1[0], p[1]-bg1[1], p[2]-bg1[2]);
    if (d > best) { best = d; bg2 = p; }
  }

  const out = Buffer.alloc(width * height * 4);
  for (let i = 0, j = 0; i < width * height * channels; i += channels, j += 4) {
    const d1 = Math.hypot(data[i]-bg1[0], data[i+1]-bg1[1], data[i+2]-bg1[2]);
    const d2 = Math.hypot(data[i]-bg2[0], data[i+1]-bg2[1], data[i+2]-bg2[2]);
    const dist = Math.min(d1, d2);
    // Smoothstep alpha: fully transparent within 28, opaque past 70.
    const a = Math.max(0, Math.min(1, (dist - 28) / 42));
    out[j] = data[i]; out[j + 1] = data[i + 1]; out[j + 2] = data[i + 2];
    out[j + 3] = Math.round(a * 255);
  }
  const name = file.replace(/\.(jpe?g|png)$/i, ".webp");
  await sharp(out, { raw: { width, height, channels: 4 } })
    .trim({ threshold: 10 })
    .webp({ quality: 88 })
    .toFile(path.join(OUT, name));
}
console.log(`processed ${files.length} images`);
