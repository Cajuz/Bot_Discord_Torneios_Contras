import os
from typing import Optional
import discord



def get_banner_file(channel_name: str):
    base_dir = os.getcwd()  # /app no docker

    name = channel_name.lower()

    if "1x1" in name:
        path = os.path.join(base_dir, "assets", "assets", "1x1_mobile.png")
        return discord.File(path, filename="banner.png")

    if "4x4" in name:
        path = os.path.join(base_dir, "assets", "assets", "4x4_emulador.png")
        return discord.File(path, filename="banner.png")

    return None