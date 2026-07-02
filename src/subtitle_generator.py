import pysrt
from datetime import timedelta
from typing import List, Tuple

def parse_script(script_text: str) -> List[str]:
    """스크립트를 라인별로 파싱"""
    lines = script_text.strip().split('\n')
    return [line.strip() for line in lines if line.strip()]

def calculate_timing(lines: List[str], total_duration: float, method: str = "equal") -> List[Tuple[float, float]]:
    """각 자막의 시작/종료 시간 계산"""
    timings = []

    if method == "equal":
        # 동일하게 분배
        time_per_line = total_duration / len(lines)
        for i in range(len(lines)):
            start = i * time_per_line
            end = (i + 1) * time_per_line
            timings.append((start, end))

    return timings

def generate_srt(script_text: str, total_duration: float, method: str = "equal") -> str:
    """SRT 자막 생성"""
    lines = parse_script(script_text)
    timings = calculate_timing(lines, total_duration, method)

    subtitle_list = pysrt.SubRipFile()

    for i, (line, (start, end)) in enumerate(zip(lines, timings)):
        sub = pysrt.SubRip(
            index=i + 1,
            start=timedelta(seconds=start),
            end=timedelta(seconds=end),
            content=line
        )
        subtitle_list.append(sub)

    return str(subtitle_list)

def save_srt(srt_content: str, output_path: str):
    """SRT 파일로 저장"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(srt_content)

def parse_srt(srt_path: str) -> pysrt.SubRipFile:
    """SRT 파일 읽기"""
    return pysrt.open(srt_path)
