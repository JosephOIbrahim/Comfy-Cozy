"""The built-in recipe library.

Distilled from two specs already in the repo:
  * CLAUDE.md "Artistic Intent Translation" table  -> ParamMutation recipes
  * agent/knowledge/common_recipes.md graphs        -> ToolStep recipes

All tool calls use the REAL signatures verified against agent/tools/workflow_patch.py:
  set_input(node_id, input_name, value)
  connect_nodes(from_node, from_output:int, to_node, to_input)
  add_node(class_type, inputs) -> {"node_id": ...}
"""

from __future__ import annotations

from .base import ParamMutation, Recipe, RecipeRegistry, ToolStep


def _intent_recipes() -> list[Recipe]:
    """Parameter-edit recipes from the Artistic Intent Translation table."""
    return [
        Recipe(
            name="dreamier",
            description="Soften the look: lower CFG, more steps, a smoother sampler",
            triggers=[r"\b(dreamier|softer|more dreamy|dreamy|soften (it|the look))\b"],
            requires_workflow=True,
            category="intent",
            steps=[
                ParamMutation("KSampler", "cfg", "set", 6.0),
                ParamMutation("KSampler", "steps", "adjust_up", 8),
                ParamMutation("KSampler", "sampler_name", "set", "dpmpp_2m"),
                ParamMutation("KSampler", "scheduler", "set", "karras"),
            ],
        ),
        Recipe(
            name="sharper",
            description="Crisper, more defined output: higher CFG, a crisp sampler",
            triggers=[r"\b(sharper|crisper|more (sharp|crisp|defined)|crisp)\b"],
            requires_workflow=True,
            category="intent",
            steps=[
                ParamMutation("KSampler", "cfg", "set", 9.0),
                ParamMutation("KSampler", "sampler_name", "set", "euler"),
            ],
        ),
        Recipe(
            name="faster",
            description="Trade some quality for speed: fewer sampling steps",
            triggers=[r"\b(faster|quicker|speed (it|this) up|make it fast)\b"],
            requires_workflow=True,
            category="intent",
            steps=[ParamMutation("KSampler", "steps", "set", 18)],
        ),
        Recipe(
            name="higher_quality",
            description="Push quality: noticeably more sampling steps",
            triggers=[r"\b(higher quality|more detail|better quality|more refined)\b"],
            requires_workflow=True,
            category="intent",
            steps=[ParamMutation("KSampler", "steps", "adjust_up", 12)],
        ),
        Recipe(
            name="more_variation",
            description="Loosen the guidance for more variety between seeds",
            triggers=[r"\b(more variation|more variety|looser|less rigid)\b"],
            requires_workflow=True,
            category="intent",
            steps=[ParamMutation("KSampler", "cfg", "adjust_down", 1.0)],
        ),
        Recipe(
            name="less_variation",
            description="Tighten the guidance to stay closer to the prompt",
            triggers=[r"\b(less variation|more consistent|tighter|stick to the prompt)\b"],
            requires_workflow=True,
            category="intent",
            steps=[ParamMutation("KSampler", "cfg", "adjust_up", 1.0)],
        ),
    ]


def _build_recipes() -> list[Recipe]:
    """Graph-building recipes from common_recipes.md (shows $var + @find dataflow)."""
    return [
        Recipe(
            name="upscale_2x_pixel",
            description="Add a pixel-space 2x upscale after the VAE decode (RealESRGAN x2)",
            triggers=[
                r"\bupscale( it| the (image|output))?( by)?\s*2x\b",
                r"\b2x upscale\b",
                r"\bmake it (2x )?bigger\b",
            ],
            requires_workflow=True,
            category="build",
            steps=[
                ToolStep(
                    "add_node",
                    {"class_type": "UpscaleModelLoader",
                     "inputs": {"model_name": "RealESRGAN_x2.pth"}},
                    out="loader",
                ),
                ToolStep("add_node", {"class_type": "ImageUpscaleWithModel"}, out="up"),
                ToolStep(
                    "connect_nodes",
                    {"from_node": "$loader.node_id", "from_output": 0,
                     "to_node": "$up.node_id", "to_input": "upscale_model"},
                ),
                ToolStep(
                    "connect_nodes",
                    {"from_node": "@find:VAEDecode", "from_output": 0,
                     "to_node": "$up.node_id", "to_input": "image"},
                ),
            ],
        ),
    ]


def build_default_registry() -> RecipeRegistry:
    """Assemble the default recipe registry (intent recipes first, then build recipes)."""
    return RecipeRegistry(_intent_recipes() + _build_recipes())
