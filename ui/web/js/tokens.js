/**
 * Shared design tokens and slot color mapping.
 *
 * Consolidates slot colors that were previously duplicated between
 * chat.js and CSS. All JS modules import from here.
 */

export const SLOT_COLORS = {
  CLIP: "#FFD500",
  CLIP_VISION: "#A8DADC",
  CONDITIONING: "#FFA931",
  CONTROL_NET: "#6EE7B7",
  IMAGE: "#64B5F6",
  LATENT: "#FF9CF9",
  MASK: "#81C784",
  MODEL: "#B39DDB",
  STYLE_MODEL: "#C2FFAE",
  VAE: "#FF6E6E",
  NOISE: "#B0B0B0",
  GUIDER: "#66FFFF",
  SAMPLER: "#ECB4B4",
  SIGMAS: "#CDFFCD",
};

export const AGENT_COLORS = {
  router: "#00BB81",
  intent: "#FFD500",
  execution: "#64B5F6",
  verify: "#FF6E6E",
  doctor: "#B39DDB",
};

/**
 * Get the slot color for a node class type.
 * Maps common node patterns to their data type colors.
 */
export function slotColorForNode(classType) {
  if (!classType) return SLOT_COLORS.MODEL;
  const ct = classType.toLowerCase();
  if (ct.includes("checkpoint") || ct.includes("lora") || ct.includes("model"))
    return SLOT_COLORS.MODEL;
  if (ct.includes("clip") && ct.includes("vision"))
    return SLOT_COLORS.CLIP_VISION;
  if (ct.includes("clip") || ct.includes("textencode"))
    return SLOT_COLORS.CLIP;
  if (ct.includes("conditioning"))
    return SLOT_COLORS.CONDITIONING;
  if (ct.includes("controlnet"))
    return SLOT_COLORS.CONTROL_NET;
  if (ct.includes("latent") || ct.includes("empty"))
    return SLOT_COLORS.LATENT;
  if (ct.includes("image") || ct.includes("save") || ct.includes("preview"))
    return SLOT_COLORS.IMAGE;
  if (ct.includes("mask"))
    return SLOT_COLORS.MASK;
  if (ct.includes("vae"))
    return SLOT_COLORS.VAE;
  if (ct.includes("sampler") || ct.includes("ksampler"))
    return SLOT_COLORS.SAMPLER;
  if (ct.includes("noise"))
    return SLOT_COLORS.NOISE;
  if (ct.includes("guider") || ct.includes("cfg"))
    return SLOT_COLORS.GUIDER;
  if (ct.includes("sigmas") || ct.includes("scheduler"))
    return SLOT_COLORS.SIGMAS;
  return SLOT_COLORS.MODEL;
}
