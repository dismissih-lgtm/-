import os
import streamlit as st
import pandas as pd
from src.subtitle_remover import remove_subtitles
from src.subtitle_generator import build_srt_from_rows, retime_rows_cumulative, save_srt
from src.video_editor import get_video_duration, extract_video_segments, add_subtitles_to_video

st.set_page_config(page_title="동영상 편집 프로그램", page_icon="🎬", layout="wide")

os.makedirs("temp", exist_ok=True)
os.makedirs("output", exist_ok=True)

st.title("🎬 동영상 편집 프로그램")
st.caption("동영상 업로드 → 기존 자막 제거 → 대본 입력 → 자막 타이밍에 맞게 자동 편집")

# ──────────────────────────────────────────────
# 1단계. 동영상 업로드
# ──────────────────────────────────────────────
st.header("1️⃣ 동영상 업로드")

uploaded = st.file_uploader("동영상 파일을 선택하세요", type=["mp4", "avi", "mov", "mkv"])

if uploaded is not None:
    # 새 파일이 올라온 경우에만 저장 (rerun마다 다시 쓰지 않도록)
    if st.session_state.get("uploaded_name") != uploaded.name:
        input_path = os.path.join("temp", "input_video.mp4")
        with open(input_path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.session_state.uploaded_name = uploaded.name
        st.session_state.input_path = input_path
        # 이전 작업 상태 초기화
        for key in ("clean_path", "duration", "rows", "result_path", "result_srt"):
            st.session_state.pop(key, None)

    col_v, col_i = st.columns([2, 1])
    with col_v:
        st.video(st.session_state.input_path)
    with col_i:
        size_mb = os.path.getsize(st.session_state.input_path) / 1e6
        st.metric("파일", st.session_state.uploaded_name)
        st.metric("크기", f"{size_mb:.1f} MB")

# ──────────────────────────────────────────────
# 2단계. 자막 제거
# ──────────────────────────────────────────────
if "input_path" in st.session_state:
    st.header("2️⃣ 기존 자막 제거")

    if "clean_path" not in st.session_state:
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🗑️ 자막 제거 시작", type="primary"):
                with st.spinner("자막 제거 중..."):
                    clean_path = os.path.join("temp", "no_subtitle_video.mp4")
                    if remove_subtitles(st.session_state.input_path, clean_path):
                        st.session_state.clean_path = clean_path
                        st.session_state.duration = get_video_duration(clean_path)
                        st.rerun()
                    else:
                        st.error("❌ 자막 제거에 실패했습니다. 파일 형식을 확인해주세요.")
        with col_b:
            if st.button("⏭️ 건너뛰기 (자막 없는 원본)"):
                st.session_state.clean_path = st.session_state.input_path
                st.session_state.duration = get_video_duration(st.session_state.input_path)
                st.rerun()
    else:
        st.success(f"✅ 영상 준비 완료 — 길이 **{st.session_state.duration:.1f}초**")

# ──────────────────────────────────────────────
# 3단계. 대본 입력 & 자막 타이밍
# ──────────────────────────────────────────────
if "clean_path" in st.session_state:
    st.header("3️⃣ 대본 입력 & 자막 타이밍")

    script_text = st.text_area(
        "대본을 입력하세요 (한 줄이 자막 하나가 됩니다)",
        placeholder="안녕하세요\n오늘은 요리 영상입니다\n먼저 재료를 준비해주세요\n감사합니다",
        height=160,
        key="script_text",
    )

    lines = [line.strip() for line in (script_text or "").split("\n") if line.strip()]

    if lines:
        duration = st.session_state.duration

        # 목표 영상 길이 & 구간 선택 방식
        col_len, col_method = st.columns(2)
        with col_len:
            length_options = ["원본 전체"] + [f"{s}초" for s in range(10, 65, 5)]
            target_choice = st.selectbox(
                "🎯 편집 후 영상 길이",
                length_options,
                help="원본에서 필요한 만큼만 잘라내 이 길이로 만듭니다.",
            )
        with col_method:
            pick_method = st.radio(
                "구간 선택 방식",
                ["영상 전체에서 고르게 뽑기 (추천)", "앞부분부터 순서대로"],
                help="고르게 뽑기: 긴 원본을 처음~끝에서 골고루 잘라 요약하듯 편집합니다.",
            )

        if target_choice == "원본 전체":
            target_len = duration
        else:
            target_len = float(target_choice.replace("초", ""))
            if target_len > duration:
                st.warning(f"⚠️ 원본({duration:.1f}초)보다 길게 만들 수 없어 원본 길이로 맞춥니다.")
                target_len = duration

        # 대본·목표 길이·방식이 바뀌면 타이밍을 다시 생성
        n = len(lines)
        config_key = (tuple(lines), round(target_len, 2), pick_method)
        if st.session_state.get("rows_source") != config_key:
            seg = target_len / n
            if pick_method.startswith("영상 전체에서"):
                # 원본을 n개 구역으로 나누고, 각 구역 가운데에서 seg초씩 추출
                window = duration / n
                seg = min(seg, window)
                st.session_state.rows = [
                    {
                        "start": round(i * window + (window - seg) / 2, 2),
                        "end": round(i * window + (window - seg) / 2 + seg, 2),
                        "text": line,
                    }
                    for i, line in enumerate(lines)
                ]
            else:
                # 앞에서부터 연속으로 추출
                st.session_state.rows = [
                    {"start": round(i * seg, 2), "end": round((i + 1) * seg, 2), "text": line}
                    for i, line in enumerate(lines)
                ]
            st.session_state.rows_source = config_key

        st.markdown(
            f"📝 자막 **{n}개** · 완성 영상 길이 **약 {target_len:.0f}초** (자막당 {target_len / n:.1f}초). "
            "**표에서 시작/종료 시간을 직접 수정**할 수 있어요 — 시간은 원본 영상 기준입니다."
        )

        edited_df = st.data_editor(
            pd.DataFrame(st.session_state.rows).rename(
                columns={"start": "시작(초)", "end": "종료(초)", "text": "자막"}
            ),
            use_container_width=True,
            num_rows="fixed",
            key="timing_editor",
        )

        # 편집된 값 반영
        rows = [
            {"start": float(r["시작(초)"]), "end": float(r["종료(초)"]), "text": str(r["자막"])}
            for _, r in edited_df.iterrows()
        ]

        # ──────────────────────────────────────
        # 4단계. 편집 실행
        # ──────────────────────────────────────
        st.header("4️⃣ 편집 실행")

        mode = st.radio(
            "편집 방식",
            [
                "✂️ 컷 편집 + 새 자막 입히기 (추천)",
                "✂️ 컷 편집만 (자막 없이)",
                "💬 자막만 입히기 (원본 그대로)",
            ],
            help="컷 편집: 표의 각 구간만 잘라 순서대로 이어붙입니다.",
        )

        if st.button("🚀 편집 시작", type="primary"):
            srt_path = os.path.join("temp", "subtitles.srt")
            result_path = None

            with st.spinner("동영상 편집 중... (영상 길이에 따라 시간이 걸립니다)"):
                if mode.startswith("✂️ 컷 편집 +"):
                    save_srt(build_srt_from_rows(rows), srt_path)
                    cut_path = os.path.join("temp", "cut_video.mp4")
                    if extract_video_segments(st.session_state.clean_path, srt_path, cut_path):
                        # 컷 편집 후 새 타임라인에 맞게 자막 재계산
                        new_srt_path = os.path.join("temp", "subtitles_retimed.srt")
                        save_srt(build_srt_from_rows(retime_rows_cumulative(rows)), new_srt_path)
                        result_path = os.path.join("output", "edited_with_subs.mp4")
                        if not add_subtitles_to_video(cut_path, new_srt_path, result_path):
                            result_path = None

                elif mode.startswith("✂️ 컷 편집만"):
                    save_srt(build_srt_from_rows(rows), srt_path)
                    result_path = os.path.join("output", "edited_video.mp4")
                    if not extract_video_segments(st.session_state.clean_path, srt_path, result_path):
                        result_path = None

                else:  # 자막만 입히기
                    save_srt(build_srt_from_rows(rows), srt_path)
                    result_path = os.path.join("output", "video_with_subs.mp4")
                    if not add_subtitles_to_video(st.session_state.clean_path, srt_path, result_path):
                        result_path = None

            if result_path:
                st.session_state.result_path = result_path
                st.session_state.result_srt = build_srt_from_rows(
                    retime_rows_cumulative(rows) if mode.startswith("✂️ 컷 편집 +") else rows
                )
                st.rerun()
            else:
                st.error("❌ 편집에 실패했습니다. 타이밍 값을 확인해주세요.")

# ──────────────────────────────────────────────
# 5단계. 결과
# ──────────────────────────────────────────────
if st.session_state.get("result_path") and os.path.exists(st.session_state.result_path):
    st.header("✅ 편집 완료!")

    result_path = st.session_state.result_path
    col_v, col_d = st.columns([2, 1])

    with col_v:
        st.video(result_path)

    with col_d:
        st.metric("결과 영상 길이", f"{get_video_duration(result_path):.1f}초")
        with open(result_path, "rb") as f:
            st.download_button(
                "💾 동영상 다운로드",
                data=f.read(),
                file_name=os.path.basename(result_path),
                mime="video/mp4",
                type="primary",
            )
        st.download_button(
            "📄 자막(SRT) 다운로드",
            data=st.session_state.result_srt,
            file_name="subtitles.srt",
            mime="text/plain",
        )
