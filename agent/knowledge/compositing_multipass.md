# Multi-Pass Compositing in ComfyUI

## What is Multi-Pass Rendering

In VFX production, a single beauty render is rarely the final deliverable. Compositors work with separate passes -- depth, normals, segmentation, edges -- that give precise control over the final image in tools like Nuke, Fusion, or After Effects.

ComfyUI can generate these passes from a single diffusion output, giving AI-generated images the same compositing flexibility as traditional 3D renders.

### Pass Types

| Pass | Node | What It Captures | Compositing Use |
|------|------|-----------------|-----------------|
| **Beauty** | VAEDecode + SaveImage | Full color render | Base plate for compositing |
| **Depth** | MiDaS-DepthMapPreprocessor | Per-pixel distance | Fog, DOF, z-depth compositing |
| **Normals** | BAE-NormalMapPreprocessor | Surface orientation | Relighting, material adjustments |
| **Segmentation** | OneFormerPreprocessor | Semantic regions | Selective color grading, masking |
| **Edges** | CannyEdgePreprocessor | Edge structure | Edge-aware effects, outline overlays |
| **Pose** | DWPosePreprocessor | Body keypoints | Character isolation, retargeting |

## ComfyUI Multi-Pass Pattern

The core pattern: generate once, branch to multiple preprocessors, save each.

### Node Flow

```
CheckpointLoader -> KSampler -> VAEDecode (beauty)
                                    |
                                    +-> SaveImage (beauty_pass)
                                    +-> MiDaS-DepthMapPreprocessor -> SaveImage (depth_pass)
                                    +-> BAE-NormalMapPreprocessor -> SaveImage (normals_pass)
                                    +-> OneFormerPreprocessor -> SaveImage (seg_pass)
```

All preprocessors receive the same decoded IMAGE output from VAEDecode. This ensures all passes are pixel-aligned with the beauty render.

### Why Branch After VAEDecode

Preprocessors operate on pixel-space images (IMAGE type), not latents. Running them on the decoded beauty pass ensures:
- Exact pixel alignment across all passes
- Consistent resolution
- The passes describe the actual generated content (not the input conditioning)

## Filename Conventions

Organized filenames make batch compositing possible. Use a consistent prefix scheme:

```
{scene}_{pass}_{seed}
```

Examples:
- `forest_beauty_42.png`
- `forest_depth_42.png`
- `forest_normals_42.png`

In ComfyUI, set the `filename_prefix` on each SaveImage node:
- Beauty: `"beauty_pass"`
- Depth: `"depth_pass"`
- Normals: `"normals_pass"`
- Segmentation: `"seg_pass"`

ComfyUI appends a counter automatically, so output looks like `beauty_pass_00001_.png`.

## Compositing Integration

### File Format Considerations

| Format | Bit Depth | HDR | Best For |
|--------|-----------|-----|----------|
| **PNG** | 8-bit | No | Standard passes, web delivery |
| **EXR** | 16/32-bit float | Yes | Depth passes, HDR compositing in Nuke |
| **TIFF** | 8/16-bit | Optional | Print workflows, Photoshop |

ComfyUI's default SaveImage outputs PNG. For EXR export (recommended for depth passes in professional pipelines), use custom nodes like `SaveEXR` from community packs.

### Per-Pass Format Recommendations

- **Beauty**: PNG (8-bit sufficient for most compositing)
- **Depth**: EXR preferred (continuous depth values benefit from float precision). PNG works but quantizes depth to 256 levels
- **Normals**: PNG (direction vectors map well to 8-bit RGB channels)
- **Segmentation**: PNG (discrete labels, no precision needed)

### Import Notes for Compositing Apps

- **Nuke**: Import as image sequence. Depth pass connects to ZDefocus or DepthGrade
- **After Effects**: Import PNG sequence. Depth pass drives Camera Lens Blur
- **Fusion (DaVinci Resolve)**: Import as loader. Use depth with DepthBlur or FogOfWar

## Quality Tips

### Run Preprocessors at Full Resolution

Always run preprocessors on the full-resolution beauty pass. Downsampling before preprocessing loses fine detail -- especially in depth edges and normal map surface transitions.

If you need faster iteration, reduce the `resolution` parameter on the preprocessor node (it handles internal resizing), but keep the input image at full res.

### Consistent Resolution Across Passes

All passes must be the same resolution for compositing alignment. Since they all branch from the same VAEDecode output, this happens automatically. Do not add resize nodes between VAEDecode and individual preprocessors.

### Depth Map Quality

- MiDaS is fast and good enough for fog/DOF effects
- DepthAnything V2 produces cleaner edges -- preferred for z-depth compositing where edge precision matters
- ZoeDepth gives metric (absolute) depth -- needed if your compositor expects real-world distance values

### Normal Map Orientation

BAE-NormalMapPreprocessor outputs normals in screen space (RGB = XYZ direction). The convention:
- R channel = X (left-right surface tilt)
- G channel = Y (up-down surface tilt)
- B channel = Z (facing camera = bright blue)

This matches the standard normal map convention used by most compositing tools.

### Batch Processing

For animation frames, run the multi-pass workflow on each frame with incrementing seeds or input images. Keep filename prefixes consistent so compositing tools can load passes as aligned sequences.
