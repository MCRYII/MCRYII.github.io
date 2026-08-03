import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import blog_tool as bt


with tempfile.TemporaryDirectory() as tmp:
    bt.MUSIC_DIR = tmp
    bt.MUSIC_DATA_FILE = os.path.join(tmp, "music.json")
    for name in ("a.mp3", "b.mp3", "c.mp3"):
        with open(os.path.join(tmp, name), "w") as f:
            f.write("")

    bt.save_music_data({"playlists": [{"name": "全部", "order": []}]})
    assert bt.load_music_data()["playlists"][0]["order"] == ["a.mp3", "b.mp3", "c.mp3"]

    class FakeHandler:
        def __init__(self):
            self.resp = None

        def _json(self, obj, code=200):
            self.resp = (code, obj)

    h = FakeHandler()
    bt.BlogWebHandler._post_music(h, {"action": "move_to", "name": "全部", "song": "c.mp3", "to": 0})
    assert h.resp == (200, {"ok": True}), h.resp
    assert bt.load_music_data()["playlists"][0]["order"] == ["c.mp3", "a.mp3", "b.mp3"]

    h = FakeHandler()
    bt.BlogWebHandler._post_music(h, {"action": "move", "name": "全部", "song": "c.mp3", "dir": "down"})
    assert h.resp == (200, {"ok": True}), h.resp
    assert bt.load_music_data()["playlists"][0]["order"] == ["a.mp3", "c.mp3", "b.mp3"]

print("music logic ok")
