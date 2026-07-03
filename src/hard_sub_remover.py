"""화면에 새겨진(하드) 자막 제거 — 글자를 감지해 주변 배경으로 복원(인페인팅)

판별 기준: 자막은 '가로로 긴 줄' 모양으로 놓인 '여러 글자 조각'이며
경계선이 많다(획 구조). 매끈한 흰 물체(세면대·제품 등)는 경계선 밀도가
낮고 덩어리가 커서 제외된다. 검은 테두리가 없는 흰 자막도 감지한다.
"""
import subprocess
import cv2
import numpy as np

# 자막 위치 선택지 → 검사할 세로 구간 (시작비율, 끝비율)
BANDS = {
    "상단+하단": [(0.0, 0.40), (0.60, 1.0)],
    "하단만": [(0.60, 1.0)],
    "상단만": [(0.0, 0.40)],
    "화면 전체": [(0.0, 1.0)],
}

def _mask_for_band(frame, y0, y1):
    """한 구간에서 자막 글자 마스크 생성"""
    h, w = frame.shape[:2]
    roi = frame[y0:y1]
    rh, rw = roi.shape[:2]

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    H, S, V = cv2.split(hsv)

    # 후보: 흰 글자(밝고 채도 낮음) + 노란 글자(중국 영상에 흔함)
    white = ((V > 165) & (S < 80)).astype(np.uint8) * 255
    yellow = ((H >= 15) & (H <= 40) & (S >= 80) & (V >= 140)).astype(np.uint8) * 255
    cand = cv2.bitwise_or(white, yellow)

    # 글자 '조각' 수집 — 큰 덩어리(흰 물체·배경)는 여기서 걸러짐
    n, labels, stats, _ = cv2.connectedComponentsWithStats(cand, connectivity=8)
    frags = np.zeros_like(cand)
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < 6 or bh > h * 0.15 or bw > rw * 0.9:
            continue
        frags |= (labels == i).astype(np.uint8) * 255

    # 조각들을 가로로 묶어 '자막 줄' 후보 생성
    glued = cv2.dilate(frags, cv2.getStructuringElement(cv2.MORPH_RECT, (35, 11)))
    n2, labels2, stats2, _ = cv2.connectedComponentsWithStats(glued, connectivity=8)

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    mask = np.zeros_like(cand)
    for j in range(1, n2):
        x, y, bw, bh, _ = stats2[j]
        conf = cv2.countNonZero(frags[y:y + bh, x:x + bw])
        if conf < 50:
            continue
        # 자막 블록의 모양: 1~3줄 높이까지 허용, 세로로 길쭉하면 제외
        if not (h * 0.015 <= bh <= h * 0.35) or bw / max(bh, 1) < 1.0:
            continue
        # 채움 비율: 글자는 듬성듬성(획), 매끈한 물체는 꽉 참
        fill = conf / float(bw * bh)
        if not (0.05 <= fill <= 0.80):
            continue
        # 경계선 밀도: 글자 획은 경계선이 많음, 매끈한 표면은 적음
        patch = gray[y:y + bh, x:x + bw]
        edges = cv2.Canny(patch, 80, 160)
        if float((edges > 0).mean()) < 0.08:
            continue
        x0, y0b = max(0, x - 5), max(0, y - 5)
        x1, y1b = min(rw, x + bw + 5), min(rh, y + bh + 5)
        mask[y0b:y1b, x0:x1] = 255

    full = np.zeros((h, w), np.uint8)
    full[y0:y1] = mask
    return full

def build_text_mask(frame, bands=None):
    """선택한 구간들에서 자막 마스크 생성"""
    h = frame.shape[0]
    if bands is None:
        bands = BANDS["상단+하단"]
    total = np.zeros(frame.shape[:2], np.uint8)
    for r0, r1 in bands:
        total |= _mask_for_band(frame, int(h * r0), int(h * r1))
    return total

def remove_hard_subtitles(input_video: str, output_video: str,
                          bands=None, progress_cb=None) -> bool:
    """프레임마다 자막을 감지해 지우고, 원본 소리를 다시 입힘"""
    try:
        cap = cv2.VideoCapture(input_video)
        if not cap.isOpened():
            print("영상을 열 수 없습니다")
            return False

        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

        tmp_video = output_video + ".noaudio.mp4"
        writer = cv2.VideoWriter(tmp_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

        i = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            mask = build_text_mask(frame, bands)
            if cv2.countNonZero(mask) > 60:  # 자막이 있는 프레임만 복원
                frame = cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
            writer.write(frame)
            i += 1
            if progress_cb and i % 20 == 0:
                progress_cb(min(i / total, 1.0))

        cap.release()
        writer.release()

        # 원본 소리 합치기 + 재생 호환 코덱으로 변환
        cmd = ['ffmpeg', '-i', tmp_video, '-i', input_video,
               '-map', '0:v', '-map', '1:a?',
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
               '-c:a', 'aac', '-sn', '-shortest',
               '-y', output_video]
        result = subprocess.run(cmd, capture_output=True, text=True)

        import os
        if os.path.exists(tmp_video):
            os.remove(tmp_video)

        if result.returncode != 0:
            print(f"오디오 합치기 실패: {result.stderr[-300:]}")
            return False
        return True

    except Exception as e:
        print(f"하드 자막 제거 실패: {e}")
        return False
