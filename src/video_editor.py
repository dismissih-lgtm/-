import subprocess
import platform
from moviepy import VideoFileClip, concatenate_videoclips
from .subtitle_generator import parse_srt

def default_korean_font() -> str:
    """운영체제별 한글 지원 기본 폰트"""
    system = platform.system()
    if system == "Windows":
        return "Malgun Gothic"
    if system == "Darwin":
        return "Apple SD Gothic Neo"
    return "NanumGothic"

def get_video_duration(video_path: str) -> float:
    """비디오 길이 반환 (초)"""
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration
        clip.close()
        return duration
    except Exception as e:
        print(f"비디오 길이 조회 실패: {e}")
        return 0

def extract_video_segments(video_path: str, srt_path: str, output_path: str) -> bool:
    """자막 타이밍에 맞게 비디오 편집 (각 자막 구간만 추출해서 연결)"""
    try:
        subtitles = parse_srt(srt_path)
        video = VideoFileClip(video_path)

        clips = []
        for sub in subtitles:
            start_time = max(0, sub['start'])
            end_time = min(video.duration, sub['end'])
            if start_time < end_time:
                clips.append(video.subclipped(start_time, end_time))

        if not clips:
            video.close()
            return False

        final_video = concatenate_videoclips(clips)
        final_video.write_videofile(output_path, logger=None)
        final_video.close()
        video.close()
        return True

    except Exception as e:
        print(f"비디오 편집 실패: {e}")
        return False

def add_subtitles_to_video(video_path: str, srt_path: str, output_path: str,
                           font_name: str = None, font_size: int = 22) -> bool:
    """ffmpeg 자막 필터로 비디오에 자막을 입힘 (한글 지원)"""
    try:
        if font_name is None:
            font_name = default_korean_font()
        # subtitles 필터 경로에서 특수문자를 이스케이프
        escaped_srt = srt_path.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")
        style = f"FontName={font_name},FontSize={font_size},OutlineColour=&H80000000,BorderStyle=1,Outline=2"
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vf', f"subtitles='{escaped_srt}':force_style='{style}'",
            '-c:a', 'copy',
            '-y',
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg 자막 오버레이 오류: {result.stderr[-500:]}")
            return False
        return True

    except Exception as e:
        print(f"자막 오버레이 실패: {e}")
        return False
