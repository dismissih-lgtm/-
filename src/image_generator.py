"""OpenAI DALL·E 3로 게시물 이미지를 생성합니다.

Instagram Graph API는 이미지를 '공개적으로 접근 가능한 URL'로 받습니다.
DALL·E가 반환하는 임시 URL(약 1시간 유효)을 그대로 넘기면 되므로,
별도의 이미지 호스팅이 필요 없습니다.
"""

from openai import OpenAI

from . import config


def _client() -> OpenAI:
    return OpenAI(api_key=config.require("OPENAI_API_KEY"))


def generate_image(topic: str) -> str:
    """주제를 받아 생성된 이미지의 URL을 반환합니다.

    인스타그램 피드에 맞춰 정사각형(1024x1024)으로 생성합니다.
    """
    prompt = (
        f"인스타그램 게시물에 어울리는 고품질의 매력적인 이미지. 주제: {topic}. "
        "선명하고 시선을 끄는 구도, 텍스트 없이 시각적으로 완성도 높게."
    )
    result = _client().images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    return result.data[0].url
