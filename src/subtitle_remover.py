import subprocess
import os
from pathlib import Path

def remove_subtitles(input_video: str, output_video: str) -> bool:
    """비디오에서 모든 자막(소프트/하드) 제거"""
    try:
        cmd = [
            'ffmpeg',
            '-i', input_video,
            '-c:v', 'copy',  # 비디오 코덱 복사 (재인코딩 안 함)
            '-c:a', 'copy',  # 오디오 코덱 복사
            '-sn',           # 자막 스트림 제거
            '-y',            # 기존 파일 덮어쓰기
            output_video
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True
        else:
            print(f"FFmpeg 오류: {result.stderr}")
            return False
    except Exception as e:
        print(f"자막 제거 실패: {e}")
        return False
