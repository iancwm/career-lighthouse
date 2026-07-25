from pathlib import Path


def test_api_image_installs_python_magic_native_runtime():
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "apt-get install -y --no-install-recommends libmagic1" in dockerfile
