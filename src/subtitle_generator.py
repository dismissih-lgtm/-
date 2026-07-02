from datetime import timedelta
from typing import List, Tuple

def format_time(seconds: float) -> str:
    """초를 SRT 시간 형식으로 변환 (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')

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

    srt_content = []
    for i, (line, (start, end)) in enumerate(zip(lines, timings)):
        srt_content.append(str(i + 1))
        srt_content.append(f"{format_time(start)} --> {format_time(end)}")
        srt_content.append(line)
        srt_content.append("")

    return '\n'.join(srt_content)

def save_srt(srt_content: str, output_path: str):
    """SRT 파일로 저장"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(srt_content)

def parse_srt(srt_path: str) -> List[dict]:
    """SRT 파일 읽기"""
    subtitles = []
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read().split('\n\n')

    for block in content:
        if block.strip():
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                time_range = lines[1].split(' --> ')
                if len(time_range) == 2:
                    subtitles.append({
                        'index': int(lines[0]),
                        'start': time_to_seconds(time_range[0].strip()),
                        'end': time_to_seconds(time_range[1].strip()),
                        'text': '\n'.join(lines[2:])
                    })

    return subtitles

def time_to_seconds(time_str: str) -> float:
    """SRT 시간 형식을 초로 변환"""
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

def build_srt_from_rows(rows: List[dict]) -> str:
    """[{'start':초, 'end':초, 'text':자막}] 목록으로 SRT 생성"""
    srt_content = []
    for i, row in enumerate(rows):
        srt_content.append(str(i + 1))
        srt_content.append(f"{format_time(row['start'])} --> {format_time(row['end'])}")
        srt_content.append(row['text'])
        srt_content.append("")
    return '\n'.join(srt_content)

def retime_rows_cumulative(rows: List[dict]) -> List[dict]:
    """컷 편집 후의 새 타임라인에 맞게 자막 시간을 재계산

    각 구간을 잘라 이어붙이면 i번째 자막은
    [이전 구간 길이의 합, +해당 구간 길이] 위치에 온다.
    """
    retimed = []
    cursor = 0.0
    for row in rows:
        seg_len = max(0.0, row['end'] - row['start'])
        retimed.append({'start': cursor, 'end': cursor + seg_len, 'text': row['text']})
        cursor += seg_len
    return retimed
