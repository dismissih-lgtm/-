"""화면에 새겨진(하드) 자막 제거 — 글자를 감지해 주변 배경으로 복원(인페인팅)"""
import subprocess
import cv2
import numpy as np

def build_text_mask(frame, band_top_ratio: float = 0.68):
    """화면 하단에서 '검은 테두리를 두른 밝은 글자'(자막의 특징)만 골라 마스크 생성

    밝은 배경(하늘·눈·흰 벽 등)은 테두리가 밝아서 제외되므로 오탐이 적다.
    """
    h, w = frame.shape[:2]
    y0 = int(h * band_top_ratio)
    roi = frame[y0:h, :]
    rh, rw = roi.shape[:2]

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    H, S, V = cv2.split(hsv)

    # 후보: 흰 자막(밝고 채도 낮음) + 노란 자막(중국 영상에 흔함)
    # 작은 글씨는 픽셀이 흐려지므로 문턱을 낮게 잡고, 외곽선 검사로 정밀도를 확보
    white = ((V > 160) & (S < 110)).astype(np.uint8) * 255
    yellow = ((H >= 15) & (H <= 40) & (S >= 80) & (V >= 140)).astype(np.uint8) * 255
    cand = cv2.bitwise_or(white, yellow)

    # 글자 조각(획) 단위로 검사 — 주 판정은 '검은 외곽선을 둘렀는가'
    n, labels, stats, _ = cv2.connectedComponentsWithStats(cand, connectivity=8)

    keep = np.zeros_like(cand)
    ring_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        # 너무 큰 덩어리(배경)와 티끌만 크기로 제외 — 글자 조각은 통과되도록 관대하게
        if bh > h * 0.2 or bw > rw * 0.98 or area < 6:
            continue
        comp = (labels == i).astype(np.uint8) * 255
        # 조각 바로 옆 1~2픽셀 — 자막은 검은 외곽선/그림자를 두르므로 어두운 픽셀이 많음
        ring = cv2.dilate(comp, ring_kernel) & ~comp
        ring_v = V[ring > 0]
        if ring_v.size == 0:
            continue
        dark_ratio = float((ring_v < 95).mean())
        if dark_ratio < 0.3:
            continue  # 주변이 밝으면 배경(하늘·흰 벽 등)으로 판단
        keep |= comp

    # 확인된 글자 조각들을 가로로 묶어 '자막 줄' 영역을 만들고,
    # 그 줄 전체를 지움 — 흐릿한 픽셀·외곽선·그림자까지 남김없이
    line_glue = cv2.dilate(keep, cv2.getStructuringElement(cv2.MORPH_RECT, (35, 11)))
    n2, labels2, stats2, _ = cv2.connectedComponentsWithStats(line_glue, connectivity=8)
    mask = np.zeros_like(cand)
    for j in range(1, n2):
        x, y, bw, bh, area = stats2[j]
        confirmed = cv2.countNonZero(keep[y:y + bh, x:x + bw])
        if confirmed < 50:  # 확인된 글자 픽셀이 너무 적으면 무시 (오탐 방지)
            continue
        x0, y0b = max(0, x - 5), max(0, y - 5)
        x1, y1 = min(rw, x + bw + 5), min(rh, y + bh + 5)
        mask[y0b:y1, x0:x1] = 255

    full = np.zeros((h, w), np.uint8)
    full[y0:h, :] = mask
    return full

def remove_hard_subtitles(input_video: str, output_video: str, progress_cb=None) -> bool:
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
            mask = build_text_mask(frame)
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
