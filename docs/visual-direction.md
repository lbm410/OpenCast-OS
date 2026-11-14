# OpenCast visual direction and landscape asset

Owner request, 2026-11-14: a clean, elegant interface with subtle liquid-glass inspiration, a landscape background and optional gentle movement only when measured performance permits. Keep an original OpenCast identity, clear remote focus, large readable controls and restrained visual detail.

The initial shell uses a local static landscape, translucent tinted panels, thin highlights and ordinary CSS fallbacks. Do not depend on backdrop-filter, real-time blur, WebGL or continuous animation. Movement remains deferred pending actual-device timing and memory observations. Transparency and a small compressed asset alone do not prove good performance.

## Background artifact

- Workspace asset: `prototypes/opencast-shell/assets/landscape.jpg`.
- 1280×720, JPEG quality setting 78, 97,188 bytes. An RGBA decode alone is about 3.52 MiB; browser/compositor buffers and caches can add more.
- Created with the built-in image generation tool, then resized and converted with the host's sips tool. The original PNG remains in the local generated-images directory; the shell references only the workspace JPEG.
- Visual inspection: calm lake and layered mountain silhouettes, restrained blue-hour tones and warm horizon; no text, logos or UI baked into the background.
- Local generation mode was built-in, not an API/CLI fallback. No API key or new image-generation dependency was required.

Final generation prompt:

> Use case: photorealistic-natural. Asset type: original landscape wallpaper for OpenCast OS, a subtle premium television interface on a 16:9 screen. Create a beautiful wide cinematic natural landscape at blue hour: a quiet alpine lake, soft distant mountain silhouettes, restrained pale warm light near the horizon, atmospheric mist and gentle water reflections. Refined, calm, realistic photography, elegant and understated. Broad smooth areas and low visual clutter so white UI text and translucent dark glass panels will remain legible, particularly across the left and lower portions. No people, buildings, objects, logos, letters, typography, UI panels or watermark. The image is a background only, not a screenshot of an interface. Wide 16:9 composition, full bleed, opaque background. Favor subtle colors and natural detail over oversaturated fantasy.

The launcher artifact is an implementation candidate, not evidence of native installation or automatic startup. Keep capability-dependent TV controls unavailable until their adapters are verified.

## Revised direction: open landscape and compact dock

The owner rejected the first preview as too busy, with overly prominent borders. The revised direction gives most of the screen to a warm rolling-hills landscape, with a compact bottom dock, a discreet input selector above, a selected-item title and clock. Keep focus visible without heavy framing. Native actions remain capability-gated; the screenshot must be identified as a desktop preview.

New workspace asset: `prototypes/opencast-shell/assets/landscape-v2.jpg`, 1280×720, JPEG quality 78. The original landscape remains available. Built-in image generation was used, followed by host `sips` conversion; no API/CLI fallback. Original local filename: `exec-fabdd216-f45f-45cc-998e-bb2ee15ad451.png` in the generated-images directory. Visual inspection confirmed warm hills, mist and a quiet foreground with no baked-in UI.

Final generation prompt:

> Use case: photorealistic-natural. Asset type: original full-screen landscape wallpaper for a minimal television launcher. Wide 16:9 landscape photograph of softly rolling green and golden agricultural hills at sunrise, inspired by the quiet atmosphere of the Palouse. Long gentle curves of cultivated fields, layered low hills fading into warm atmospheric haze, pale gold sunlight near the upper right horizon, subtle wisps of mist in valleys, natural olive green and muted amber tones. Elevated wide viewpoint, horizon in the upper quarter, richly natural but visually quiet detail, shadowed foreground, broad clean areas suitable for white interface text. Elegant calm realistic photography, not fantasy, not oversaturated. Background landscape only: no interface, cards, icons, borders, text, logos, watermark, people, vehicles or buildings. Full bleed opaque image.
