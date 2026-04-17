import os
from typing import Optional
import discord



def get_banner_file(channel_name: str):
    base_dir = os.getcwd()  # /app no docker
    name = channel_name.lower()

    # MOBILE
    if "1x1-mob" in name:
        path = os.path.join(base_dir, "assets", "assets", "1x1_mobile.gif")
        return discord.File(path, filename=os.path.basename(path))

    if "2x2-mob" in name:
        path = os.path.join(base_dir, "assets", "assets", "2x2_mobile.gif")
        return discord.File(path, filename=os.path.basename(path))

    if "3x3-mob" in name:
        path = os.path.join(base_dir, "assets", "assets", "3x3_mobile.gif")
        return discord.File(path, filename=os.path.basename(path))

    if "4x4-mob" in name:
        path = os.path.join(base_dir, "assets", "assets", "4x4_mobile.gif")
        return discord.File(path, filename=os.path.basename(path))

    # EMULADOR
    if "1x1-emu" in name:
        path = os.path.join(base_dir, "assets", "assets", "1x1_emulador.gif")
        return discord.File(path, filename=os.path.basename(path))

    if "2x2-emu" in name:
        path = os.path.join(base_dir, "assets", "assets", "2x2_emulador.gif")
        return discord.File(path, filename=os.path.basename(path))

    if "3x3-emu" in name:
        path = os.path.join(base_dir, "assets", "assets", "3x3_emulador.gif")
        return discord.File(path, filename=os.path.basename(path))

    if "4x4-emu" in name:
        path = os.path.join(base_dir, "assets", "assets", "4x4_emulador.gif")
        return discord.File(path, filename=os.path.basename(path))

    # MISTO
    if "2x2-misto" in name:
        path = os.path.join(base_dir, "assets", "assets", "2x2_misto.gif")
        return discord.File(path, filename=os.path.basename(path))

    if "3x3-misto" in name:
        path = os.path.join(base_dir, "assets", "assets", "3x3_misto.gif")
        return discord.File(path, filename=os.path.basename(path))

    if "4x4-misto" in name:
        path = os.path.join(base_dir, "assets", "assets", "4x4_misto.gif")
        return discord.File(path, filename=os.path.basename(path))

    return None
