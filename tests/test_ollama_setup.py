import pytest

from userbot.ollama_setup import MODELS, Hardware, recommend_model


@pytest.mark.parametrize(
    "hardware, expected",
    [
        (Hardware(ram_gb=16, apple_silicon=True, nvidia_vram_gb=None), "qwen3.5:9b"),
        (Hardware(ram_gb=32, apple_silicon=False, nvidia_vram_gb=12), "qwen3.5:9b"),
        (Hardware(ram_gb=8, apple_silicon=True, nvidia_vram_gb=None), "qwen3.5:2b"),
        (Hardware(ram_gb=16, apple_silicon=False, nvidia_vram_gb=None), "qwen3.5:4b"),
        (Hardware(ram_gb=8, apple_silicon=False, nvidia_vram_gb=6), "qwen3.5:4b"),
        (Hardware(ram_gb=8, apple_silicon=False, nvidia_vram_gb=None), "qwen3.5:2b"),
        (Hardware(ram_gb=4, apple_silicon=False, nvidia_vram_gb=None), "qwen3.5:0.8b"),
    ],
)
def test_recommended_model_fits_the_machine(hardware, expected):
    assert recommend_model(hardware) == expected


def test_every_recommendation_is_in_the_model_list():
    names = {m.name for m in MODELS}
    for ram in (2, 4, 8, 12, 16, 64):
        assert recommend_model(Hardware(ram_gb=ram, apple_silicon=False, nvidia_vram_gb=None)) in names
