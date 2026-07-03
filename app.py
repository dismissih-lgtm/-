import os
import streamlit as st
import pandas as pd
from src.subtitle_remover import remove_subtitles
from src.subtitle_generator import build_srt_from_rows, retime_rows_cumulative, save_srt
from src.video_editor import (
    get_video_duration, extract_video_segments, add_subtitles_to_video,
    make_playable_preview,
)

st.set_page_config(page_title="동영상 편집 프로그램", page_icon="🎬", layout="wide")

os.makedirs("temp", exist_ok=True)
os.makedirs("output", exist_ok=True)

# ──────────────────────────────────────────────
# 스타일
# ──────────────────────────────────────────────
st.markdown("""
<style>
/* 전체 폰트 & 여백 */
.block-container { padding-top: 1.5rem; max-width: 1100px; }
#MainMenu, footer { visibility: hidden; }

/* 히어로 배너 */
.hero {
    background: linear-gradient(120deg, #7C3AED 0%, #C026D3 55%, #F472B6 100%);
    border-radius: 18px;
    padding: 34px 38px;
    margin-bottom: 28px;
    color: white;
    box-shadow: 0 10px 30px rgba(124, 58, 237, .25);
}
.hero h1 { margin: 0 0 8px 0; font-size: 2rem; color: white; }
.hero p  { margin: 0; opacity: .92; font-size: 1.02rem; }
.hero .flow {
    display: inline-flex; gap: 8px; margin-top: 16px; flex-wrap: wrap;
}
.hero .flow span {
    background: rgba(255,255,255,.18);
    border: 1px solid rgba(255,255,255,.35);
    border-radius: 999px;
    padding: 5px 14px;
    font-size: .85rem;
    backdrop-filter: blur(4px);
}

/* 단계 헤더 */
.step-header {
    display: flex; align-items: center; gap: 12px;
    margin: 34px 0 6px 0;
}
.step-num {
    width: 34px; height: 34px; flex: none;
    display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, #7C3AED, #C026D3);
    color: white; font-weight: 700; font-size: 1.05rem;
    border-radius: 10px;
    box-shadow: 0 4px 10px rgba(124, 58, 237, .3);
}
.step-title { font-size: 1.35rem; font-weight: 700; color: #1F2937; }
.step-done .step-num { background: linear-gradient(135deg, #059669, #10B981); box-shadow: 0 4px 10px rgba(16,185,129,.3); }

/* 버튼 */
.stButton > button, .stDownloadButton > button {
    border-radius: 12px;
    padding: .55rem 1.4rem;
    font-weight: 600;
    transition: transform .15s, box-shadow .15s;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(124, 58, 237, .25);
}

/* 파일 업로더 */
[data-testid="stFileUploaderDropzone"] {
    border: 2px dashed #C4B5FD;
    border-radius: 14px;
    background: #FAF8FF;
}

/* 완료 카드 */
.result-banner {
    background: linear-gradient(120deg, #059669, #10B981);
    border-radius: 16px;
    padding: 22px 30px;
    color: white;
    margin: 30px 0 18px 0;
    box-shadow: 0 8px 24px rgba(16, 185, 129, .25);
}
.result-banner h2 { margin: 0; color: white; font-size: 1.4rem; }
.result-banner p { margin: 6px 0 0 0; opacity: .92; }
</style>
""", unsafe_allow_html=True)

def step_header(num: str, title: str, done: bool = False):
    cls = "step-header step-done" if done else "step-header"
    st.markdown(
        f'<div class="{cls}"><div class="step-num">{"✓" if done else num}</div>'
        f'<div class="step-title">{title}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("""
<div class="hero">
  <h1>🎬 동영상 편집 프로그램</h1>
  <p>대본만 넣으면 자막 제거부터 컷 편집, 새 자막까지 자동으로.</p>
  <div class="flow">
    <span>📁 업로드</span><span>🗑️ 자막 제거</span><span>✍️ 대본 입력</span><span>✂️ 자동 편집</span><span>💾 다운로드</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 1단계. 동영상 업로드
# ──────────────────────────────────────────────
step_header("1", "동영상 업로드", done="input_path" in st.session_state)

uploaded = st.file_uploader("동영상 파일을 선택하세요", type=["mp4", "avi", "mov", "mkv"])

if uploaded is not None:
    # 새 파일이 올라온 경우에만 저장 (rerun마다 다시 쓰지 않도록)
    if st.session_state.get("uploaded_name") != uploaded.name:
        ext = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else "mp4"
        input_path = os.path.join("temp", f"input_video.{ext}")
        with open(input_path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.session_state.uploaded_name = uploaded.name
        st.session_state.input_path = input_path
        # 이전 작업 상태 초기화
        for key in ("clean_path", "duration", "rows", "rows_source",
                    "result_path", "result_srt", "preview_input", "preview_clean"):
            st.session_state.pop(key, None)

    # 브라우저에서 재생 가능한 미리보기 준비 (MKV/AVI 등도 재생되도록 자동 변환)
    if "preview_input" not in st.session_state:
        with st.spinner("미리보기 준비 중..."):
            st.session_state.preview_input = make_playable_preview(
                st.session_state.input_path, os.path.join("temp", "preview_input.mp4")
            )

    col_v, col_i = st.columns([2, 1])
    with col_v:
        st.markdown("**🎞️ 원본 미리보기**")
        st.video(st.session_state.preview_input)
    with col_i:
        size_mb = os.path.getsize(st.session_state.input_path) / 1e6
        st.metric("파일", st.session_state.uploaded_name)
        st.metric("크기", f"{size_mb:.1f} MB")

# ──────────────────────────────────────────────
# 2단계. 자막 제거
# ──────────────────────────────────────────────
if "input_path" in st.session_state:
    step_header("2", "기존 자막 제거", done="clean_path" in st.session_state)

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

        # 원본 vs 자막 제거본 비교 미리보기
        if st.session_state.clean_path != st.session_state.input_path:
            if "preview_clean" not in st.session_state:
                with st.spinner("자막 제거본 미리보기 준비 중..."):
                    st.session_state.preview_clean = make_playable_preview(
                        st.session_state.clean_path, os.path.join("temp", "preview_clean.mp4")
                    )
            col_before, col_after = st.columns(2)
            with col_before:
                st.markdown("**🎞️ 원본**")
                st.video(st.session_state.preview_input)
            with col_after:
                st.markdown("**✨ 자막 제거본**")
                st.video(st.session_state.preview_clean)
        else:
            st.caption("자막 제거를 건너뛰어 원본을 그대로 사용합니다.")

# ──────────────────────────────────────────────
# 3단계. 대본 입력 & 자막 타이밍
# ──────────────────────────────────────────────
if "clean_path" in st.session_state:
    step_header("3", "대본 입력 & 자막 타이밍", done=bool(st.session_state.get("rows")))

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
        step_header("4", "편집 실행", done=bool(st.session_state.get("result_path")))

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
    st.markdown("""
    <div class="result-banner">
      <h2>🎉 편집 완료!</h2>
      <p>아래에서 미리보고, 동영상과 자막 파일을 저장하세요.</p>
    </div>
    """, unsafe_allow_html=True)

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
