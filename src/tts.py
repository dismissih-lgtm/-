import os
import asyncio
import edge_tts

# 무료 마이크로소프트 한국어 음성 (API 키 불필요, 인터넷 필요)
VOICES = {
    "선희 (여성 · 밝고 또렷한 목소리)": "ko-KR-SunHiNeural",
    "인준 (남성 · 차분한 목소리)": "ko-KR-InJoonNeural",
    "현수 (남성 · 젊은 목소리)": "ko-KR-HyunsuMultilingualNeural",
}

def generate_speech(text: str, voice_id: str, output_path: str):
    """대본을 음성 파일로 변환. (성공 여부, 오류 메시지) 반환"""
    try:
        async def run():
            communicate = edge_tts.Communicate(text, voice_id)
            await communicate.save(output_path)

        asyncio.run(run())

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True, ""
        return False, "빈 파일이 생성되었습니다. 잠시 후 다시 시도해주세요."
    except Exception as e:
        return False, str(e)
