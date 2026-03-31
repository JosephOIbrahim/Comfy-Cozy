"""SuperDuper Panel — Cognitive UI for ComfyUI.

Registers web directory for the panel extension and mounts
server routes on PromptServer for agent communication.
"""

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

try:
    from .server.routes import setup_routes
    setup_routes()
except Exception as e:
    import logging
    logging.getLogger("superduper-panel").warning("Route setup skipped: %s", e)
