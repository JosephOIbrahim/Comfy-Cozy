# ControlNet Workflow Patterns

## Required Nodes

- **ControlNetLoader** -- loads the ControlNet model from `models/controlnet/`
- **ControlNetApply** or **ControlNetApplyAdvanced** -- applies control signal to CONDITIONING
- A preprocessor node for the control type (depth, canny, openpose, etc.)

## Connection Pattern

```
Image -> Preprocessor -> ControlNetApply.image
ControlNetLoader -> ControlNetApply.control_net
CLIPTextEncode (positive) -> ControlNetApply.conditioning
ControlNetApply.CONDITIONING -> KSampler.positive
```

## Control Types and Preprocessors

| Control Type | Preprocessor Node | Model Pattern |
|-------------|-------------------|---------------|
| Depth | DepthAnythingPreprocessor, MiDaS-DepthMapPreprocessor | `*depth*` |
| Canny | CannyEdgePreprocessor | `*canny*` |
| OpenPose | OpenposePreprocessor | `*openpose*` |
| Lineart | LineartPreprocessor | `*lineart*` |
| Scribble | ScribblePreprocessor | `*scribble*` |
| Softedge | SoftEdgePreprocessor (HED/PiDiNet) | `*softedge*` |
| Normal | BAE-NormalMapPreprocessor | `*normal*` |
| Segmentation | OneFormerPreprocessor, SAMPreprocessor | `*seg*` |
| IP-Adapter | IPAdapterUnifiedLoader | `*ip-adapter*` (not ControlNet) |

## Key Constraints

- ControlNet image resolution must match the latent resolution (width/height divisible by 8)
- Multiple ControlNets can be chained: connect output CONDITIONING of one to input of next
- strength parameter (0.0-1.0) controls influence -- start at 0.7-0.8
- start_percent/end_percent control when ControlNet activates during sampling
- SDXL ControlNets only work with SDXL models; SD1.5 ControlNets with SD1.5 models

## Preprocessor Selection Guide

Choosing the right preprocessor is the most important decision in a ControlNet workflow. Each extracts different structural information from the source image.

### Depth Preprocessors

| Node | Best For | Speed | Notes |
|------|----------|-------|-------|
| **MiDaS-DepthMapPreprocessor** | General scenes | Fast | Good default. Params: `a` (depth weight), `bg_threshold` (background cutoff) |
| **DepthAnythingPreprocessor** | High-quality depth | Medium | Better edge preservation than MiDaS. V2 recommended over V1 |
| **Zoe-DepthMapPreprocessor** | Indoor scenes | Slow | Metric depth (absolute distances). Best for architectural interiors |

### Edge Preprocessors

| Node | Best For | Speed | Notes |
|------|----------|-------|-------|
| **CannyEdgePreprocessor** | Clean hard edges | Fast | Two thresholds: `low_threshold` (100), `high_threshold` (200). Lower = more edges |
| **HEDPreprocessor** | Soft organic edges | Medium | Better for natural forms, hair, fabric. No threshold tuning needed |
| **PiDiNetPreprocessor** | Balanced edges | Medium | Between Canny (hard) and HED (soft). Good all-rounder |

### Pose Preprocessors

| Node | Best For | Speed | Notes |
|------|----------|-------|-------|
| **OpenposePreprocessor** | Full body pose | Medium | Detects body, hands, face keypoints. The standard for character posing |
| **DWPosePreprocessor** | Better extremities | Medium | Superior hand and face detection vs OpenPose. Preferred for portraits |
| **MediaPipeFaceMeshPreprocessor** | Face only | Fast | 468 face landmarks. Use when you only need facial expression control |

### Normal Map Preprocessors

| Node | Best For | Speed | Notes |
|------|----------|-------|-------|
| **BAE-NormalMapPreprocessor** | Surface normals from RGB | Medium | Generates surface orientation maps. Useful for relighting and material transfer |

### Lineart Preprocessors

| Node | Best For | Speed | Notes |
|------|----------|-------|-------|
| **LineartPreprocessor** | Clean line extraction | Medium | Realistic line art from photos. Good for architectural drawings |
| **AnimeLineartPreprocessor** | Manga/anime style | Medium | Optimized for flat-shaded illustration styles |
| **Manga2AnimeLineartPreprocessor** | High contrast lines | Fast | Thicker, bolder lines. Good for comic book styles |

### Segmentation Preprocessors

| Node | Best For | Speed | Notes |
|------|----------|-------|-------|
| **OneFormerPreprocessor** | Semantic segmentation | Slow | Labels regions (sky, person, car). ADE20K or COCO datasets |
| **SAMPreprocessor** | Interactive segmentation | Medium | Segment Anything Model. Point/box prompts for specific regions |

## Strength Scheduling

`ControlNetApplyAdvanced` exposes `start_percent` and `end_percent` to control when the ControlNet influences the sampling process. This is one of the most powerful tuning mechanisms.

### How It Works

- `start_percent=0.0, end_percent=1.0` -- ControlNet active for the entire sampling (default)
- The sampling process goes from noise (0%) to final image (100%)
- Early steps define structure; late steps refine detail

### Common Scheduling Patterns

| Pattern | start | end | Use Case |
|---------|-------|-----|----------|
| **Full guidance** | 0.0 | 1.0 | Strict adherence to control signal |
| **Structural only** | 0.0 | 0.8 | Guide composition, let model add detail freely |
| **Detail refinement** | 0.3 | 1.0 | Loose early structure, tight detail matching |
| **Loose guidance** | 0.0 | 0.5 | Composition hint only, maximum creative freedom |
| **Mid-range** | 0.2 | 0.8 | Avoid both noise-stage artifacts and detail lock-in |

### Tips

- If the output looks "too rigid" or "overfit to the control image," reduce `end_percent` to 0.7-0.8
- If the control signal is being ignored, check that `start_percent` is 0.0 and strength is sufficient
- For iterative refinement: start with full range, then narrow to find the sweet spot

## Multi-ControlNet Stacking

ComfyUI supports chaining multiple ControlNets by connecting the output CONDITIONING of one `ControlNetApplyAdvanced` into the next.

### Wiring Pattern

```
CLIPTextEncode -> ControlNetApplyAdvanced (depth)
                    -> ControlNetApplyAdvanced (canny)
                        -> KSampler.positive
```

Each `ControlNetApplyAdvanced` takes the previous one's positive/negative outputs as its positive/negative inputs.

### Recommended Strength When Stacking

| Combo | Depth Strength | Second Strength | Notes |
|-------|---------------|-----------------|-------|
| Depth + Canny | 0.5-0.6 | 0.5-0.6 | Structure + edges. Most common combo |
| Depth + Pose | 0.6-0.7 | 0.5-0.6 | Scene layout + character positioning |
| Canny + Lineart | 0.4-0.5 | 0.5-0.6 | Redundant overlap -- keep strengths lower |
| Depth + Normal | 0.5-0.6 | 0.4-0.5 | 3D structure. Normals add surface detail |

### Rules of Thumb

- Total effective influence scales with the number of ControlNets -- reduce individual strengths when stacking
- Two ControlNets at 0.8 each will over-constrain the model. Start at 0.5 each and increase
- Order of chaining does not matter in ComfyUI (unlike some other implementations)
- Three or more ControlNets is possible but diminishing returns; two is the practical sweet spot

## Resolution Matching

Preprocessor resolution and generation resolution must align for clean results.

### The Rule

Set the preprocessor `resolution` parameter to match your target generation resolution. For SDXL at 1024x1024, use `resolution=1024` in the preprocessor. For SD1.5 at 512x512, use `resolution=512`.

### What Happens at Mismatch

- **Preprocessor res < generation res**: Control signal gets upscaled, losing fine detail. Edges become soft, depth maps lose precision
- **Preprocessor res > generation res**: Wasted computation. The control image gets downsampled anyway
- **Non-square images**: Use the shorter dimension as resolution (e.g., 768x512 -> resolution=512)

### Best Practice

Run preprocessors at the same resolution you plan to generate at. If you need to experiment at lower res first, re-run the preprocessor when you scale up for final renders.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Output looks washed out / low contrast | Strength too high | Reduce strength to 0.5-0.6 |
| Control signal being ignored | Strength too low or wrong model family | Increase strength; verify ControlNet matches checkpoint family |
| Artifacts at edges of controlled regions | Resolution mismatch | Match preprocessor resolution to generation resolution |
| Pose limbs in wrong positions | Wrong preprocessor | Switch from OpenPose to DWPose for better extremity detection |
| Output follows control too literally | Full scheduling range + high strength | Reduce `end_percent` to 0.7 or lower strength |
| Depth map looks flat / wrong | MiDaS struggling with scene | Try DepthAnything V2 or ZoeDepth instead |
| ControlNet has no effect at all | Not connected properly | Verify: preprocessor -> ControlNetApply.image AND ControlNetLoader -> ControlNetApply.control_net |
| Multiple ControlNets fighting | Both at high strength | Reduce each to 0.4-0.5; use scheduling to separate their influence ranges |
