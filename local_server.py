"""Reliable local ASGI entry point for the NutriGuide Gradio interface."""
import os

import uvicorn

from meal_photo_app import demo

if __name__ == "__main__":
    uvicorn.run(demo.app, host="127.0.0.1", port=int(os.getenv("NUTRIGUIDE_PORT", "9001")))
