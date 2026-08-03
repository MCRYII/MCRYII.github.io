# -*- coding: utf-8 -*-
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import blog_tool as bt
from PIL import Image


with tempfile.TemporaryDirectory() as tmp:
    comfy_dir = os.path.join(tmp, "comfy")
    images_dir = os.path.join(tmp, "blog", "images")
    moments_dir = os.path.join(images_dir, "moments")
    os.makedirs(comfy_dir)
    os.makedirs(images_dir)
    os.makedirs(moments_dir)
    bt.COMFY_OUTPUT_DIR = comfy_dir
    bt.IMAGES_DIR = images_dir
    bt.MOMENTS_IMAGES_DIR = moments_dir

    png_path = os.path.join(comfy_dir, "photo.png")
    Image.frombytes("RGB", (512, 512), os.urandom(512 * 512 * 3)).save(png_path)
    alpha_path = os.path.join(comfy_dir, "sticker.png")
    Image.frombytes("RGBA", (256, 256), os.urandom(256 * 256 * 4)).save(alpha_path)

    names = {x["name"] for x in bt._comfy_list_images()}
    assert names == {"photo.png", "sticker.png"}, names

    data, ext = bt._optimize_blog_image(png_path)
    assert ext == ".jpg", ext
    assert data

    data, ext = bt._optimize_blog_image(alpha_path)
    assert ext == ".png", ext
    assert data

    url = bt._import_comfy_image("photo.png", "post")
    assert url.startswith("/images/"), url
    assert os.path.isfile(os.path.join(images_dir, os.path.basename(url)))

    url2 = bt._import_comfy_image("sticker.png", "moment")
    assert url2.startswith("/images/moments/"), url2
    assert os.path.isfile(os.path.join(moments_dir, os.path.basename(url2)))

    workflow = bt._build_comfy_workflow({
        "model": "m.safetensors", "prompt": "a cat",
        "width": "1024", "height": "1024", "steps": "20", "cfg": "7",
    })
    assert workflow["2"]["inputs"]["text"] == "a cat"
    assert workflow["5"]["inputs"]["steps"] == 20
    assert workflow["7"]["class_type"] == "SaveImage"

    history = {"outputs": {"7": {"images": [
        {"filename": "a.png", "subfolder": "", "type": "output"}
    ]}}}
    assert bt._comfy_history_images(history) == [
        {"filename": "a.png", "subfolder": "", "type": "output"}
    ]

    orig_running = bt._comfy_running
    orig_popen = bt.subprocess.Popen
    calls = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_running():
        return False

    def fake_popen(cmd, **kw):
        calls["cmd"] = cmd
        calls["kw"] = kw
        return FakeProc()

    bt._comfy_running = fake_running
    bt.subprocess.Popen = fake_popen
    bt._COMFY_PROCESS = None
    try:
        assert bt._comfy_start() == {"started": True}
        assert "main.py" in calls["cmd"]
        assert "--disable-auto-launch" in calls["cmd"]
        assert "--port" in calls["cmd"]
        expected = getattr(bt.subprocess, "CREATE_NO_WINDOW", 0)
        assert expected != 0
        assert calls["kw"].get("creationflags", 0) == expected
    finally:
        bt._comfy_running = orig_running
        bt.subprocess.Popen = orig_popen
        bt._COMFY_PROCESS = None

print("ai workflow ok")
