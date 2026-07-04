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

def probe_video_codec(video_path: str) -> tuple:
    """(비디오 코덱, 컨테이너 확장자) 반환"""
    try:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
               '-show_entries', 'stream=codec_name',
               '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        codec = result.stdout.strip().lower()
        ext = video_path.rsplit('.', 1)[-1].lower() if '.' in video_path else ''
        return codec, ext
    except Exception:
        return '', ''

def make_playable_preview(src: str, dst: str) -> str:
    """브라우저에서 재생 가능한 미리보기 파일 경로를 반환

    - mp4 + h264 → 원본 그대로 사용 (변환 없음)
    - h264인데 컨테이너만 다름(mkv 등) → 재인코딩 없이 mp4로 재포장 (빠름)
    - 그 외 코덱 → 480p h264로 변환 (미리보기 전용)
    """
    codec, ext = probe_video_codec(src)

    if codec == 'h264' and ext == 'mp4':
        return src

    if codec == 'h264':
        cmd = ['ffmpeg', '-i', src, '-c', 'copy', '-movflags', '+faststart', '-y', dst]
    else:
        cmd = ['ffmpeg', '-i', src,
               '-vf', "scale=-2:'min(480,ih)'",
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
               '-c:a', 'aac', '-movflags', '+faststart', '-y', dst]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return dst
    print(f"미리보기 변환 실패: {result.stderr[-300:]}")
    return src  # 실패하면 원본이라도 시도

def crop_out_subtitles(input_path: str, output_path: str,
                       top_ratio: float = 0.0, bottom_ratio: float = 0.0) -> bool:
    """자막이 있는 위/아래 띠를 화면에서 통째로 잘라냄 — 흔적 없이 깔끔, 빠름"""
    try:
        w, h = get_video_size(input_path)
        if w == 0:
            return False
        y0 = int(h * top_ratio)
        y0 -= y0 % 2
        h_out = h - y0 - int(h * bottom_ratio)
        h_out -= h_out % 2
        if h_out < h * 0.4:  # 화면이 너무 많이 잘리는 것 방지
            return False

        cmd = ['ffmpeg', '-i', input_path,
               '-vf', f"crop={w}:{h_out}:0:{y0}",
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
               '-c:a', 'copy', '-sn',
               '-y', output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"자막 잘라내기 실패: {result.stderr[-300:]}")
            return False
        return True
    except Exception as e:
        print(f"자막 잘라내기 실패: {e}")
        return False

def convert_to_shorts(input_path: str, output_path: str, style: str = "blur") -> bool:
    """쇼츠 세로 형식(9:16, 1080x1920)으로 변환

    style:
      - "blur": 영상을 가운데 두고 위아래 여백을 흐린 배경으로 채움 (추천)
      - "crop": 화면을 꽉 채우고 양옆(또는 위아래)을 잘라냄
    """
    try:
        if style == "crop":
            vf = ("scale=1080:1920:force_original_aspect_ratio=increase,"
                  "crop=1080:1920,setsar=1")
        else:
            vf = ("split[a][b];"
                  "[a]scale=1080:1920:force_original_aspect_ratio=increase,"
                  "crop=1080:1920,boxblur=20:5[bg];"
                  "[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
                  "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")

        cmd = ['ffmpeg', '-i', input_path,
               '-vf', vf,
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
               '-c:a', 'copy',
               '-y', output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"쇼츠 변환 실패: {result.stderr[-300:]}")
            return False
        return True
    except Exception as e:
        print(f"쇼츠 변환 실패: {e}")
        return False

def get_video_size(video_path: str) -> tuple:
    """(가로, 세로) 해상도 반환"""
    try:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
               '-show_entries', 'stream=width,height', '-of', 'csv=p=0', video_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        w, h = result.stdout.strip().split(',')
        return int(w), int(h)
    except Exception:
        return 0, 0

def change_audio_speed(audio_path: str, output_path: str, speed: float) -> bool:
    """음성 파일 재생 속도 변경 (음정 유지)"""
    try:
        filters = []
        s = float(speed)
        while s > 2.0:  # atempo 필터는 한 번에 최대 2배까지
            filters.append("atempo=2.0")
            s /= 2.0
        filters.append(f"atempo={s:.4f}")
        cmd = ['ffmpeg', '-i', audio_path,
               '-filter:a', ','.join(filters),
               '-vn', '-c:a', 'libmp3lame', '-q:a', '4',
               '-y', output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"속도 변경 실패: {result.stderr[-300:]}")
            return False
        return True
    except Exception as e:
        print(f"속도 변경 실패: {e}")
        return False

def replace_video_audio(video_path: str, audio_path: str, output_path: str) -> bool:
    """영상의 소리를 업로드한 음성으로 교체

    음성이 영상보다 짧으면 남는 부분은 무음, 길면 영상 끝에서 잘림.
    """
    try:
        cmd = ['ffmpeg', '-i', video_path, '-i', audio_path,
               '-map', '0:v', '-map', '1:a',
               '-c:v', 'copy', '-c:a', 'aac',
               '-af', 'apad', '-shortest',
               '-y', output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"음성 입히기 실패: {result.stderr[-300:]}")
            return False
        return True
    except Exception as e:
        print(f"음성 입히기 실패: {e}")
        return False

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

def extract_multi_video_segments(video_paths: list, rows: list, output_path: str) -> bool:
    """여러 원본 영상에서 구간을 뽑아 순서대로 이어붙임

    rows: [{'video': 1~N, 'start': 초, 'end': 초, 'text': 자막}]
    시작/종료 시간은 해당 영상 기준.
    """
    videos = []
    try:
        videos = [VideoFileClip(p) for p in video_paths]

        clips = []
        for row in rows:
            idx = min(max(int(row.get('video', 1)) - 1, 0), len(videos) - 1)
            v = videos[idx]
            start = max(0.0, float(row['start']))
            end = min(v.duration, float(row['end']))
            if start < end:
                clips.append(v.subclipped(start, end))

        if not clips:
            return False

        # 해상도가 서로 다르면 compose 방식으로 맞춤
        sizes = {(c.w, c.h) for c in clips}
        method = "chain" if len(sizes) == 1 else "compose"

        # 일부 영상에 소리가 없으면 오디오는 있는 것만 사용됨
        final_video = concatenate_videoclips(clips, method=method)
        fps = max((v.fps or 24) for v in videos)
        final_video.write_videofile(output_path, fps=fps, logger=None)
        final_video.close()
        return True

    except Exception as e:
        print(f"다중 영상 편집 실패: {e}")
        return False
    finally:
        for v in videos:
            try:
                v.close()
            except Exception:
                pass

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
