import os
from typing import Optional
import discord



def get_banner_file(channel_name: str):
    base_dir = os.getcwd()  # /app no docker
    name = channel_name.lower()

    # MOBILE
    if "1x1-mob" in name:
        path = os.path.join(base_dir, "assets", "assets", "1x1_mobile.png")
        return discord.File(path, filename="banner.png")

    if "2x2-mob" in name:
        path = os.path.join(base_dir, "assets", "assets", "2x2_mobile.png")
        return discord.File(path, filename="banner.png")

    if "3x3-mob" in name:
        path = os.path.join(base_dir, "assets", "assets", "3x3_mobile.png")
        return discord.File(path, filename="banner.png")

    if "4x4-mob" in name:
        path = os.path.join(base_dir, "assets", "assets", "4x4_mobile.png")
        return discord.File(path, filename="banner.png")

    # EMULADOR
    if "1x1-emu" in name:
        path = os.path.join(base_dir, "assets", "assets", "1x1_emulador.png")
        return discord.File(path, filename="banner.png")

    if "2x2-emu" in name:
        path = os.path.join(base_dir, "assets", "assets", "2x2_emulador.png")
        return discord.File(path, filename="banner.png")

    if "3x3-emu" in name:
        path = os.path.join(base_dir, "assets", "assets", "3x3_emulador.png")
        return discord.File(path, filename="banner.png")

    if "4x4-emu" in name:
        path = os.path.join(base_dir, "assets", "assets", "4x4_emulador.png")
        return discord.File(path, filename="banner.png")

    # MISTO
    if "2x2-misto" in name:
        path = os.path.join(base_dir, "assets", "assets", "2x2_misto.png")
        return discord.File(path, filename="banner.png")

    if "3x3-misto" in name:
        path = os.path.join(base_dir, "assets", "assets", "3x3_misto.png")
        return discord.File(path, filename="banner.png")

    if "4x4-misto" in name:
        path = os.path.join(base_dir, "assets", "assets", "4x4_misto.png")
        return discord.File(path, filename="banner.png")

    return None