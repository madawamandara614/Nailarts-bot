import base64
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

# Import nail_art_bot from output directory
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
sys.path.insert(0, str(OUTPUT_DIR))
import nail_art_bot  # noqa: E402


def _make_sample_jpeg_bytes(width: int = 1024, height: int = 1024) -> bytes:
    img = Image.new("RGB", (width, height), color=(135, 18, 38))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestNailArtPinterestBot(unittest.TestCase):
    def test_build_pin_content_fallback_produces_valid_seo_fields(self) -> None:
        pin = nail_art_bot.build_pin_content(use_ai_prompt=False)
        self.assertTrue(len(pin.title) > 10)
        self.assertLessEqual(len(pin.title), 100)
        self.assertIn("#", pin.description)
        self.assertIn("nail", pin.image_prompt.lower())
        self.assertIn("no watermark", pin.image_prompt.lower())

    def test_format_for_pinterest_outputs_1000x1500_vertical_jpeg(self) -> None:
        raw = _make_sample_jpeg_bytes(1024, 1024)
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "test_pin.jpg"
            saved = nail_art_bot.format_for_pinterest(raw, out_path, make_vertical=True)
            self.assertTrue(saved.exists())
            with Image.open(saved) as img:
                self.assertEqual(img.size, (1000, 1500))
                self.assertEqual(img.format, "JPEG")

    @patch("nail_art_bot.requests.post")
    def test_generate_image_cloudflare_decodes_base64(self, mock_post: MagicMock) -> None:
        sample_bytes = _make_sample_jpeg_bytes(512, 512)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "success": True,
            "result": {"image": base64.b64encode(sample_bytes).decode("ascii")},
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = nail_art_bot.generate_image_cloudflare("red butterfly nails", "acc123", "tok456", steps=6)
        self.assertEqual(result, sample_bytes)
        called_url = mock_post.call_args.args[0]
        self.assertIn("acc123/ai/run/@cf/black-forest-labs/flux-1-schnell", called_url)

    @patch("nail_art_bot.requests.post")
    def test_resolve_pinterest_target_strictly_ignores_facebook_page(self, mock_post: MagicMock) -> None:
        # Mock Buffer account containing BOTH a Facebook Page and a Pinterest channel
        org_resp = MagicMock()
        org_resp.json.return_value = {
            "data": {"account": {"organizations": [{"id": "org_1", "name": "My Workspace"}]}}
        }
        org_resp.raise_for_status.return_value = None

        ch_resp = MagicMock()
        ch_resp.json.return_value = {
            "data": {
                "channels": [
                    {
                        "id": "ch_fb_999",
                        "name": "My Facebook Page",
                        "displayName": "My Facebook Page",
                        "service": "facebook",
                        "isDisconnected": False,
                        "metadata": None,
                    },
                    {
                        "id": "ch_pin_777",
                        "name": "Aesthetia Nails",
                        "displayName": "Aesthetia Nails",
                        "service": "pinterest",
                        "isDisconnected": False,
                        "metadata": {
                            "boards": [
                                {"id": "b1", "name": "General", "serviceId": "srv_board_1"},
                                {"id": "b2", "name": "Nail Art Ideas", "serviceId": "srv_board_2"},
                            ]
                        },
                    },
                ]
            }
        }
        ch_resp.raise_for_status.return_value = None
        mock_post.side_effect = [org_resp, ch_resp]

        target = nail_art_bot.resolve_pinterest_target(
            api_key="fake_buffer_key",
            preferred_board_name="Nail Art Ideas",
        )
        self.assertEqual(target.channel_id, "ch_pin_777")
        self.assertNotEqual(target.channel_id, "ch_fb_999")
        self.assertEqual(target.board_service_id, "srv_board_2")
        self.assertEqual(target.board_name, "Nail Art Ideas")

    @patch("nail_art_bot.requests.post")
    def test_publish_pin_to_buffer_sends_only_pinterest_channel_and_metadata(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "createPost": {
                    "__typename": "PostActionSuccess",
                    "post": {
                        "id": "post_abc123",
                        "status": "sent",
                        "dueAt": "2026-11-22T09:00:00Z",
                        "text": "Save this look!",
                        "channelId": "ch_pin_777",
                        "channelService": "pinterest",
                    },
                }
            }
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        target = nail_art_bot.PinterestTarget(
            organization_id="org_1",
            channel_id="ch_pin_777",
            channel_name="Aesthetia Nails",
            board_service_id="srv_board_2",
            board_name="Nail Art Ideas",
        )
        pin = nail_art_bot.build_pin_content(use_ai_prompt=False)
        post = nail_art_bot.publish_pin_to_buffer(
            api_key="fake_buffer_key",
            target=target,
            pin=pin,
            image_url="https://raw.githubusercontent.com/user/repo/main/generated_pins/pin.jpg",
            mode="shareNow",
        )
        self.assertEqual(post["id"], "post_abc123")
        self.assertEqual(post["channelService"], "pinterest")

        sent_payload = mock_post.call_args.kwargs["json"]
        post_input = sent_payload["variables"]["input"]
        self.assertEqual(post_input["channelId"], "ch_pin_777")
        self.assertEqual(post_input["metadata"]["pinterest"]["boardServiceId"], "srv_board_2")
        self.assertNotIn("facebook", post_input["metadata"])

    def test_build_github_raw_url(self) -> None:
        url = nail_art_bot.build_github_raw_url("myuser/nail-bot", "main", Path("generated_pins/pin_1.jpg"))
        self.assertEqual(url, "https://raw.githubusercontent.com/myuser/nail-bot/main/generated_pins/pin_1.jpg")


if __name__ == "__main__":
    unittest.main(verbosity=2)
