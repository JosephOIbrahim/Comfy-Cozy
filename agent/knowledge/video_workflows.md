# Video Workflow Patterns

## LTX-2 / LTX Video (Primary Video Models)

The LTX-2 family (Lightricks) is the primary video generation pipeline in this installation.
Models range from 13B to 22B parameters, with FP8 quantized variants for RTX 4090.

### Models Available
- **ltx-2.3-22b-dev** (43GB full / 28GB FP8) — latest, highest quality
- **ltx-2-19b-dev** (41GB full / 26GB FP8) — proven workhorse
- Spatial upscaler: `ltxv-spatial-upscaler-0.9.8.safetensors`
- Temporal upscaler: `ltxv-temporal-upscaler-0.9.8.safetensors`
- Text encoder: Gemma-3 12B (with built-in prompt enhancement)
- LoRAs: camera control (dolly), distilled (fast inference)

### Workflow Variants
- **Text-to-Video (T2V):** `video_ltx2_3_t2v.json`, `video_ltx2_t2v.json`
- **Image-to-Video (I2V):** `video_ltx2_3_i2v.json`, `video_ltx2_i2v.json`
- **First-Last-Frame-to-Video (FLF2V):** `video_ltx2_3_flf2v.json`
- **Fast variants:** `video_ltx2_t2v_FAST.json`, `video_ltx2_i2v_FAST.json`
- **Quality variants:** `video_ltx2_t2v_QUALITY.json`, `video_ltx2_i2v_QUALITY.json`
- **With LoRA:** `LTX-2_T2V_Full_wLora.json`, `LTX-2_I2V_Full_wLora.json`

### Key Parameters
- `steps`: ~121 (high step count, model-specific)
- `cfg`: ~25 (much higher than image models — LTX-specific guidance)
- `resolution`: 1920x1088 or 1280x720 (width/height divisible by 32+1 or 64)
- `frame_count`: divisible by 8+1 (e.g., 41, 81, 121, 241)
- `fps`: 24-30
- Text encoder context: 1024 tokens (Gemma-3, much larger than CLIP)

### Resolution Constraints
- Width and height must be divisible by 32 (some workflows require 64)
- Frame count must follow pattern: `(N * 8) + 1` (e.g., 9, 17, 25, 41, 81, 121, 241)
- Native resolutions: 1280x720 (720p), 1920x1088 (close to 1080p)

### LoRA Stacking (LTX-2)
- Camera control LoRAs: `ltx-2-19b-lora-camera-control-dolly-left.safetensors`
- Distilled LoRAs: `ltx-2.3-22b-distilled-lora-384.safetensors` (strength ~0.6)
- CausVid LoRAs: `Wan21_CausVid_14B_T2V_lora_rank32.safetensors`
- Typical stack: camera LoRA @ 1.0 + distilled @ 0.6

### Node Types (Custom)
LTX-2 uses custom UUID-identified node classes, not standard ComfyUI names.
These are provided by `ComfyUI-LTXVideo` custom node pack.
Key functional nodes:
- Generation node (text-to-video / image-to-video core)
- Scheduler node (step scheduling)
- Loader node (model + text encoder loading)
- Spatial/temporal upscaler nodes

---

## WAN 2.1 / 2.2 (Video Generation)

WAN (Alibaba) models provide video generation with ControlNet-style guidance.
Multiple variants for different use cases.

### Models Available
- **wan2.1_vace_14B_fp16** (33GB) — VACE video autoencoder, 14B params
- **wan2.1_vace_1.3B_fp16** (4.1GB) — lightweight VACE variant
- **wan2.1_flf2v_720p_14B_fp16** (31GB) — first-last-frame to video
- **wan2.2_fun_control_high/low_noise_14B** (14GB each, FP8) — ControlNet-style
- **wan2.2_i2v_high/low_noise_14B** (14GB each, FP8) — image-to-video
- **wan2.2_ti2v_5B_fp16** (9.4GB) — text+image to video
- VAE: `wan2.2_vae.safetensors`, `wan_2.1_vae.safetensors`
- Distilled LoRAs: LightX2V 4-step variants

### Workflow Variants
- **Fun Control:** `video_wan2_2_14B_fun_control.json` — Canny edge guided video
- **Fun Inpaint:** `video_wan2_2_14B_fun_inpaint.json`

### Key Parameters
- `steps`: 4-20 (much lower than LTX-2)
- `cfg`: 1.0-3.5 (low guidance, similar to Flux)
- `sampler`: euler
- `scheduler`: simple
- `resolution`: 640x640 (standard), up to 720p
- `fps`: 16
- Uses standard CLIP text encoder (not Gemma)

### Fun Control Pattern
```
CLIPLoader -> CLIPTextEncode (positive/negative)
UNETLoader -> Wan22FunControlToVideo
                + Canny edge input (from source video/image)
                + VAE encode of source
             -> KSamplerAdvanced -> VAEDecode -> CreateVideo (mp4)
```

### Dual-Noise Architecture
WAN 2.2 uses a high_noise + low_noise model pair:
- Load both UNETs
- KSampler runs with high_noise model first, low_noise model second
- This produces smoother temporal transitions

---

## HunyuanVideo 1.5

Tencent's video model with super-resolution and image-to-video capabilities.

### Models Available
- **hunyuanvideo1.5_1080p_sr_distilled_fp16** (16GB) — super-resolution upscaler
- **hunyuanvideo1.5_720p_i2v_fp16** (16GB) — image-to-video
- VAE: `hunyuanvideo15_vae_fp16.safetensors`

### Key Characteristics
- Produces 720p natively, with dedicated 1080p super-resolution model
- Two-stage pipeline: generate at 720p, then SR to 1080p
- Distilled variant for faster inference

---

## Output Nodes (All Video Models)

- **VHS_VideoCombine**: Primary — GIF, MP4, WebM output with fps control
- **CreateVideo**: Alternative — direct mp4 output (h264 codec)
- **SaveAnimatedWEBP**: WebP animation output
- Image sequence: use standard SaveImage with frame numbering

## Performance Notes (RTX 4090)

- Use FP8 quantized checkpoints when available (half the VRAM)
- LTX-2 22B FP8 fits in 24GB VRAM at 720p
- WAN 2.2 14B FP8 fits comfortably with room for ControlNet
- Enable `--enable-dynamic-vram` in ComfyUI launch for automatic offloading
- `--reserve-vram 1.5` leaves headroom for 6K display compositor
- Distilled LoRAs (LightX2V) reduce WAN step count from 20 to 4
- Spatial/temporal upscalers for LTX-2 run as separate post-process nodes
