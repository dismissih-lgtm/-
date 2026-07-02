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
        if st.button("🗑️ 자막 제거 시작", type="primary"):
            with st.spinner("자막 제거 중..."):
                clean_path = os.path.join("temp", "no_subtitle_video.mp4")
                if remove_subtitles(st.session_state.input_path, clean_path):
                    st.session_state.clean_path = clean_path
                    st.session_state.duration = get_video_duration(clean_path)
                    st.rerun()
                else:
                    st.error("❌ 자막 제거에 실패했습니다. 파일 형식을 확인해주세요.")
    else:
        st.success(f"✅ 자막 제거 완료 — 영상 길이 **{st.session_state.duration:.1f}초**")

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

        # 대본이 바뀌면 타이밍을 균등 분배로 다시 생성
        if st.session_state.get("rows_source") != tuple(lines):
            per = duration / len(lines)
            st.session_state.rows = [
                {"start": round(i * per, 2), "end": round((i + 1) * per, 2), "text": line}
                for i, line in enumerate(lines)
            ]
            st.session_state.rows_source = tuple(lines)

        st.markdown(
            f"📝 자막 **{len(lines)}개** · 영상 길이에 맞춰 자동 분배되었습니다. "
            "**표에서 시작/종료 시간을 직접 수정**할 수 있어요."
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
