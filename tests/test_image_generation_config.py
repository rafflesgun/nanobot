from nanobot.config.schema import Config, ImageGenerationToolConfig


def test_image_generation_config_defaults() -> None:
    cfg = ImageGenerationToolConfig()

    assert cfg.enabled is False
    assert cfg.provider == "openai"
    assert cfg.model == "gpt-image-1"
    assert cfg.size == "1024x1024"
    assert cfg.quality == "auto"


def test_tools_image_generation_accepts_camel_case() -> None:
    cfg = Config.model_validate(
        {
            "tools": {
                "imageGeneration": {
                    "enabled": True,
                    "provider": "openai",
                    "model": "gpt-image-1",
                    "size": "1024x1536",
                    "quality": "high",
                }
            }
        }
    )

    assert cfg.tools.image_generation.enabled is True
    assert cfg.tools.image_generation.provider == "openai"
    assert cfg.tools.image_generation.model == "gpt-image-1"
    assert cfg.tools.image_generation.size == "1024x1536"
    assert cfg.tools.image_generation.quality == "high"


def test_image_generation_config_accepts_custom_openai_compatible_provider() -> None:
    cfg = Config.model_validate(
        {
            "tools": {
                "imageGeneration": {
                    "enabled": True,
                    "provider": "custom",
                    "model": "image-model",
                }
            }
        }
    )

    assert cfg.tools.image_generation.provider == "custom"
