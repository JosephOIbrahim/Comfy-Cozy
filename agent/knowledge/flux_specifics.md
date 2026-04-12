# Flux Model Specifics

## Architecture Differences

Flux uses a DiT (Diffusion Transformer) architecture, different from UNet-based SD/SDXL.

### Loading
- **UNETLoader** or **CheckpointLoaderSimple** -- loads the Flux model
- Flux uses dual CLIP encoders: **CLIPLoader** with `clip_type="flux"`
- VAE is separate -- use standard **VAELoader**
- Flux dev/schnell models are in `models/diffusion_models/` or `models/unet/`

### Key Differences from SD/SDXL
- **No negative prompt** -- Flux ignores negative conditioning. Set negative to empty or don't connect
- **CFG scale**: Use 1.0 for Flux (guidance is built into the model via FluxGuidance)
- **FluxGuidance** node: Controls generation strength (3.5 typical for dev, 0.0 for schnell)
- **Sampler**: `euler` works well; `uni_pc` and `dpmpp_2m` also supported
- **Scheduler**: `simple` or `normal` (not karras)
- **Steps**: 20-28 for dev, 1-4 for schnell

### Resolution
- Native: 1024x1024 (1 megapixel)
- Supports non-square: any resolution that's ~1MP total
- Must be divisible by 16 (not just 8 like SD)

### LoRA
- Flux LoRAs use a different format -- not compatible with SD/SDXL LoRAs
- Load with standard **LoraLoader**, connects to both MODEL and CLIP

### Common Pipeline
```
UNETLoader -> FluxGuidance -> KSampler.model
CLIPLoader (flux) -> CLIPTextEncode -> KSampler.positive
EmptyLatentImage (1024x1024) -> KSampler.latent_image
KSampler -> VAEDecode -> SaveImage
```

## FluxGuidance Node

The FluxGuidance node replaces CFG (Classifier-Free Guidance) in the Flux architecture. Unlike SD/SDXL where you set `cfg` on the KSampler, Flux bakes guidance into the model conditioning.

### How It Works

- Connects between the model loader and the KSampler: `UNETLoader -> FluxGuidance -> KSampler.model`
- The `guidance` parameter controls how strongly the model follows the prompt
- Set KSampler `cfg` to 1.0 when using FluxGuidance (they do different things)

### Parameter Range

| Value | Effect | Use Case |
|-------|--------|----------|
| 1.0-2.0 | Minimal guidance, more creative freedom | Abstract art, loose prompts |
| 2.5-3.5 | Balanced (default for dev) | General use, most prompts |
| 3.5-5.0 | Strong guidance, tighter prompt adherence | Specific compositions, detailed prompts |
| 0.0 | No guidance | Required for Schnell (distilled model handles it internally) |

### Common Mistake

Setting both `FluxGuidance.guidance=3.5` AND `KSampler.cfg=7.0` double-applies guidance. Always keep KSampler `cfg` at 1.0 with Flux.

## T5 Encoder

Flux uses a T5-XXL text encoder alongside CLIP, giving it much better text understanding than SD/SDXL.

### Memory Requirements

| Variant | VRAM | Notes |
|---------|------|-------|
| T5-XXL (full fp16) | ~8GB | Best quality. Load with DualCLIPLoader type "flux" |
| T5-XXL-fp8 | ~4.5GB | Quantized. Minimal quality loss, recommended for 24GB cards |
| T5-XXL-GGUF (Q4/Q5) | ~2-3GB | Community quantized. More quality loss but fits on 12GB cards |

### Loading Pattern

```
DualCLIPLoader (type="flux", clip_name1="t5xxl_fp16.safetensors", clip_name2="clip_l.safetensors")
  -> CLIPTextEncode -> KSampler.positive
```

The DualCLIPLoader combines T5-XXL and CLIP-L into a single CLIP output. Both encoders process the prompt -- T5 handles the semantic understanding while CLIP-L provides SDXL-compatible embeddings.

### Offloading

If VRAM is tight, ComfyUI can offload the T5 encoder to CPU after encoding. Enable `--enable-dynamic-vram` at launch. The T5 is only needed during text encoding, not during sampling.

## Resolution and Aspect Ratios

Flux is trained on ~1 megapixel images across many aspect ratios. Unlike SD1.5 (locked to 512x512) or SDXL (locked to 1024x1024), Flux handles non-square well.

### Supported Resolutions

All dimensions must be divisible by 16. Target ~1MP total pixels.

| Aspect | Resolution | Pixels | Use Case |
|--------|-----------|--------|----------|
| 1:1 | 1024x1024 | 1.05M | Default, portraits, icons |
| 3:4 | 768x1024 | 0.79M | Portrait orientation |
| 4:3 | 1024x768 | 0.79M | Landscape, scenes |
| 16:9 | 1344x768 | 1.03M | Widescreen, cinematic |
| 9:16 | 768x1344 | 1.03M | Phone wallpapers, stories |
| 2:3 | 832x1216 | 1.01M | Book covers, posters |
| 3:2 | 1216x832 | 1.01M | Photography standard |

### VRAM Scaling

Higher resolutions require more VRAM during sampling. At 1536x1536 (~2.4MP), expect 20-22GB VRAM on an RTX 4090. Stay at or below 1MP for comfortable headroom.

## LoRA with Flux

Flux LoRAs are architecturally incompatible with SD/SDXL LoRAs. Never mix them.

### Loading Pattern

```
UNETLoader -> LoraLoader (model, clip) -> FluxGuidance -> KSampler
DualCLIPLoader -> LoraLoader (model, clip) -> CLIPTextEncode
```

The LoraLoader takes both MODEL and CLIP from their respective loaders, applies the LoRA weights, and outputs modified MODEL and CLIP. Chain multiple LoraLoaders for stacking.

### Common Flux LoRA Types

| Type | Description | Typical Strength |
|------|-------------|-----------------|
| **Style** | Artistic style transfer (watercolor, oil paint, anime) | 0.7-1.0 |
| **Subject** | Specific character or object (trained on reference images) | 0.8-1.0 |
| **Concept** | Abstract concepts (lighting moods, composition patterns) | 0.5-0.8 |

### Strength Guidelines

- Start at 0.8 and adjust. Flux LoRAs tend to be more sensitive than SDXL LoRAs
- Stacking: reduce each LoRA to 0.5-0.7 when using two or more
- If output looks "fried" or over-stylized, reduce strength by 0.1-0.2 increments

## Flux Schnell vs Dev

Two official Flux variants serve different purposes.

### Comparison

| Aspect | Schnell | Dev |
|--------|---------|-----|
| Steps | 1-4 | 20-28 |
| Quality | Good (distilled) | Best |
| Speed | 2-5 seconds | 20-60 seconds |
| FluxGuidance | 0.0 (built-in) | 3.5 (adjustable) |
| License | Apache 2.0 | Non-commercial |
| LoRA support | Limited | Full |

### When to Use Each

- **Schnell for iteration**: Rapid prompt testing, composition exploration, batch previews. The speed advantage is massive (10-20x faster)
- **Dev for final renders**: When quality matters and you've locked in the prompt and composition via Schnell testing
- **Workflow**: Iterate with Schnell at 2-4 steps -> switch checkpoint to Dev -> run at 24 steps for final

### Switching Between Them

Same pipeline structure works for both. Change the checkpoint and adjust:
- `FluxGuidance.guidance`: 0.0 (Schnell) vs 3.5 (Dev)
- `KSampler.steps`: 4 (Schnell) vs 24 (Dev)

## Common Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Output is blurry or undercooked | Too few steps on Dev | Increase to 24-28 steps |
| Prompt not being followed | Guidance too low or T5 not loaded | Set FluxGuidance to 3.5; verify DualCLIPLoader has T5 |
| Out of VRAM | Full fp16 T5 + high resolution | Use T5-XXL-fp8 quantized variant; reduce resolution to 1024x1024 |
| Negative prompt not working | Expected behavior | Flux does not use negative prompts. Remove or leave empty |
| Output looks "double-guided" | Both FluxGuidance and KSampler.cfg active | Set KSampler cfg to 1.0 |
| LoRA has no effect | Wrong LoRA format | Verify the LoRA was trained for Flux, not SD/SDXL |
| Colors look wrong / washed out | Wrong VAE | Use the Flux-specific VAE, not the SDXL VAE |
