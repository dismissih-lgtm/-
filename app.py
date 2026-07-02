import streamlit as st
import os
from pathlib import Path
from src.subtitle_remover import remove_subtitles
from src.subtitle_generator import generate_srt, save_srt, parse_srt
from src.video_editor import get_video_duration, extract_video_segments, add_subtitles_to_video

st.set_page_config(page_title="동영상 편집 프로그램", layout="wide")
st.title("🎬 동영상 편집 프로그램")

st.write("**동작 원리:**")
st.write("1. 동영상 업로드 → 기존 자막 제거")
st.write("2. 대본 입력 → 자막 생성")
st.write("3. 자막 타이밍에 맞게 동영상 자동 편집")

# 폴더 생성
os.makedirs("temp", exist_ok=True)
os.makedirs("output", exist_ok=True)

# 탭 분리
tab1, tab2 = st.tabs(["📹 자막 제거", "✏️ 자막 생성 & 편집"])

with tab1:
    st.header("Step 1: 자막 제거")

    uploaded_video = st.file_uploader("동영상 파일 업로드", type=["mp4", "avi", "mov", "mkv"])

    if uploaded_video is not None:
        # 임시 파일 저장
        temp_video_path = os.path.join("temp", "input_video.mp4")
        with open(temp_video_path, "wb") as f:
            f.write(uploaded_video.getbuffer())

        st.success("✅ 동영상 업로드 완료")

        if st.button("🗑️ 자막 제거 시작"):
            st.info("자막 제거 중...")

            output_video_path = os.path.join("temp", "no_subtitle_video.mp4")

            if remove_subtitles(temp_video_path, output_video_path):
                st.success("✅ 자막 제거 완료!")
                st.video(output_video_path)

                # 다음 단계를 위해 세션에 저장
                st.session_state.video_path = output_video_path
                st.session_state.video_duration = get_video_duration(output_video_path)
                st.info(f"동영상 길이: {st.session_state.video_duration:.1f}초")
            else:
                st.error("❌ 자막 제거 실패")

with tab2:
    st.header("Step 2: 자막 생성 & 편집")

    if "video_path" not in st.session_state:
        st.warning("⚠️ 먼저 Step 1에서 동영상을 처리해주세요")
    else:
        video_path = st.session_state.video_path
        duration = st.session_state.video_duration

        st.info(f"📹 처리 중인 동영상: {duration:.1f}초")

        # 대본 입력
        st.subheader("대본 입력")
        script_text = st.text_area(
            "대본을 입력하세요 (한 줄에 하나씩)",
            placeholder="예시:\n안녕하세요\n이것은 두 번째 자막입니다\n마지막 자막입니다",
            height=150
        )

        if script_text:
            lines = [line.strip() for line in script_text.split('\n') if line.strip()]
            st.info(f"📝 {len(lines)}개의 자막이 입력되었습니다")

            # 자막 생성
            srt_content = generate_srt(script_text, duration, method="equal")
            srt_path = os.path.join("temp", "subtitles.srt")
            save_srt(srt_content, srt_path)

            st.subheader("생성된 자막 미리보기")
            st.code(srt_content, language="text")

            # 편집 옵션
            st.subheader("편집 옵션")
            col1, col2 = st.columns(2)

            with col1:
                edit_option = st.radio(
                    "편집 방식 선택",
                    ["자막에 맞게 편집", "자막 오버레이만 추가"]
                )

            with col2:
                if st.button("🚀 편집 시작"):
                    st.info("처리 중...")

                    if edit_option == "자막에 맞게 편집":
                        # 각 자막 구간만 추출해서 이어붙이기
                        output_path = os.path.join("output", "edited_video.mp4")

                        if extract_video_segments(video_path, srt_path, output_path):
                            st.success("✅ 편집 완료!")
                            st.video(output_path)
                            st.download_button(
                                label="💾 편집된 동영상 다운로드",
                                data=open(output_path, "rb").read(),
                                file_name="edited_video.mp4",
                                mime="video/mp4"
                            )
                        else:
                            st.error("❌ 편집 실패")

                    else:
                        # 원본 동영상에 자막만 오버레이
                        output_path = os.path.join("output", "video_with_subtitles.mp4")

                        if add_subtitles_to_video(video_path, srt_path, output_path):
                            st.success("✅ 자막 추가 완료!")
                            st.video(output_path)
                            st.download_button(
                                label="💾 자막이 추가된 동영상 다운로드",
                                data=open(output_path, "rb").read(),
                                file_name="video_with_subtitles.mp4",
                                mime="video/mp4"
                            )
                        else:
                            st.error("❌ 자막 추가 실패")
