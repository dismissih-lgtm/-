from moviepy.editor import VideoFileClip, concatenate_videoclips, CompositeVideoClip, TextClip
import pysrt
from pathlib import Path

def get_video_duration(video_path: str) -> float:
    """비디오 길이 반환 (초)"""
    clip = VideoFileClip(video_path)
    duration = clip.duration
    clip.close()
    return duration

def extract_video_segments(video_path: str, srt_path: str, output_path: str) -> bool:
    """자막 타이밍에 맞게 비디오 편집"""
    try:
        # SRT 파일 읽기
        subtitles = pysrt.open(srt_path)

        # 비디오 로드
        video = VideoFileClip(video_path)

        # 각 자막 구간에 해당하는 비디오 부분 추출
        clips = []
        for sub in subtitles:
            start_time = sub.start.total_seconds()
            end_time = sub.end.total_seconds()

            # 클립 추출
            clip = video.subclipped(start_time, end_time)
            clips.append(clip)

        # 클립들 연결
        if clips:
            final_video = concatenate_videoclips(clips)
            final_video.write_videofile(output_path, verbose=False, logger=None)
            final_video.close()
            video.close()
            return True
        else:
            video.close()
            return False

    except Exception as e:
        print(f"비디오 편집 실패: {e}")
        return False

def add_subtitles_to_video(video_path: str, srt_path: str, output_path: str) -> bool:
    """비디오에 자막 오버레이 추가"""
    try:
        subtitles = pysrt.open(srt_path)
        video = VideoFileClip(video_path)

        # 자막 클립 생성
        text_clips = []
        for sub in subtitles:
            start_time = sub.start.total_seconds()
            end_time = sub.end.total_seconds()
            duration = end_time - start_time

            text_clip = TextClip(
                sub.content,
                fontsize=24,
                color='white',
                font='Arial',
                method='caption',
                size=(video.w - 40, None)
            ).set_position(('center', 'bottom')).set_duration(duration).set_start(start_time)

            text_clips.append(text_clip)

        # 비디오와 자막 합치기
        final_video = CompositeVideoClip([video] + text_clips)
        final_video.write_videofile(output_path, verbose=False, logger=None)
        final_video.close()
        video.close()
        return True

    except Exception as e:
        print(f"자막 오버레이 실패: {e}")
        return False
