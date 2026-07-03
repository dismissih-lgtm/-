import os
import streamlit as st
import pandas as pd
from src.subtitle_remover import remove_subtitles
from src.subtitle_generator import build_srt_from_rows, retime_rows_cumulative, save_srt
from src.video_editor import (
    get_video_duration, extract_multi_video_segments, add_subtitles_to_video,
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
.block-container { padding-top: 1.5rem; max-width: 1100px; }
#MainMenu, footer { visibility: hidden; }

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
.hero .flow { display: inline-flex; gap: 8px; margin-top: 16px; flex-wrap: wrap; }
.hero .flow span {
    background: rgba(255,255,255,.18);
    border: 1px solid rgba(255,255,255,.35);
    border-radius: 999px;
    padding: 5px 14px;
    font-size: .85rem;
}

.step-header { display: flex; align-items: center; gap: 12px; margin: 34px 0 6px 0; }
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

[data-testid="stFileUploaderDropzone"] {
    border: 2px dashed #C4B5FD;
    border-radius: 14px;
    background: #FAF8FF;
}

/* 미리보기 카드: 이름 + 작은 영상 */
.video-name {
    font-weight: 600; font-size: .9rem; color: #4B5563;
    margin-bottom: 4px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.video-sub { font-size: .78rem; color: #9CA3AF; margin-bottom: 6px; }

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

def video_grid(items):
    """3칸 그리드로 미리보기 표시. items: [{'name', 'path', 'sub'}]"""
    cols = st.columns(3)
    for i, item in enumerate(items[:3]):
        with cols[i]:
            st.markdown(f'<div class="video-name">🎞️ {item["name"]}</div>', unsafe_allow_html=True)
            if item.get("sub"):
                st.markdown(f'<div class="video-sub">{item["sub"]}</div>', unsafe_allow_html=True)
            st.video(item["path"])

def line_duration(text: str) -> float:
    """자막 글자 수에 맞는 자연스러운 표시 시간 (읽는 속도 기준)"""
    return max(1.5, min(8.0, 0.8 + len(text) * 0.25))

def allocate_lines(durations, n):
    """대본 n줄을 영상 길이에 비례해서 배분 (합계 = n)"""
    k = len(durations)
    if n <= k:
        return [1] * n + [0] * (k - n)
    total = sum(durations)
    raw = [d / total * n for d in durations]
    base = [int(x) for x in raw]
    rest = n - sum(base)
    order = sorted(range(k), key=lambda i: raw[i] - base[i], reverse=True)
    for i in order[:rest]:
        base[i] += 1
    for i in range(k):  # 모든 영상이 최소 1줄은 갖도록
        if base[i] == 0:
            j = max(range(k), key=lambda x: base[x])
            base[j] -= 1
            base[i] += 1
    return base

st.markdown("""
<div class="hero">
  <h1>🎬 동영상 편집 프로그램</h1>
  <p>대본만 넣으면 자막 제거부터 컷 편집, 새 자막까지 자동으로. 원본 영상은 최대 3개까지!</p>
  <div class="flow">
    <span>📁 업로드 (1~3개)</span><span>🗑️ 자막 제거</span><span>✍️ 대본 입력</span><span>✂️ 자동 편집</span><span>💾 다운로드</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 1단계. 동영상 업로드 (1~3개)
# ──────────────────────────────────────────────
step_header("1", "동영상 업로드 (1~3개)", done=bool(st.session_state.get("videos")))

uploads = st.file_uploader(
    "동영상 파일을 선택하세요 (여러 개 선택 가능, 최대 3개)",
    type=["mp4", "avi", "mov", "mkv"],
    accept_multiple_files=True,
)

if uploads:
    if len(uploads) > 3:
        st.warning("⚠️ 최대 3개까지만 사용할 수 있어 앞의 3개만 사용합니다.")
        uploads = uploads[:3]

    sig = tuple((u.name, u.size) for u in uploads)
    if st.session_state.get("uploaded_sig") != sig:
        videos = []
        for i, u in enumerate(uploads):
            ext = u.name.rsplit(".", 1)[-1].lower() if "." in u.name else "mp4"
            path = os.path.join("temp", f"input_{i}.{ext}")
            with open(path, "wb") as f:
                f.write(u.getbuffer())
            videos.append({"name": u.name, "path": path})
        st.session_state.videos = videos
        st.session_state.uploaded_sig = sig
        for key in ("previews", "clean_paths", "clean_previews", "durations",
                    "rows", "rows_source", "result_path", "result_srt"):
            st.session_state.pop(key, None)

    videos = st.session_state.videos

    # 재생 가능한 미리보기 준비 (MKV/AVI 등 자동 변환)
    if "previews" not in st.session_state:
        with st.spinner("미리보기 준비 중..."):
            st.session_state.previews = [
                make_playable_preview(v["path"], os.path.join("temp", f"preview_in_{i}.mp4"))
                for i, v in enumerate(videos)
            ]

    video_grid([
        {
            "name": v["name"],
            "path": st.session_state.previews[i],
            "sub": f"{os.path.getsize(v['path']) / 1e6:.1f} MB",
        }
        for i, v in enumerate(videos)
    ])

# ──────────────────────────────────────────────
# 2단계. 자막 제거
# ──────────────────────────────────────────────
if st.session_state.get("videos"):
    videos = st.session_state.videos
    step_header("2", "기존 자막 제거", done="clean_paths" in st.session_state)

    if "clean_paths" not in st.session_state:
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🗑️ 자막 제거 시작", type="primary"):
                clean_paths = []
                ok = True
                with st.spinner(f"자막 제거 중... ({len(videos)}개)"):
                    for i, v in enumerate(videos):
                        clean = os.path.join("temp", f"clean_{i}.mp4")
                        if remove_subtitles(v["path"], clean):
                            clean_paths.append(clean)
                        else:
                            ok = False
                            break
                if ok:
                    st.session_state.clean_paths = clean_paths
                    st.session_state.durations = [get_video_duration(p) for p in clean_paths]
                    st.rerun()
                else:
                    st.error("❌ 자막 제거에 실패했습니다. 파일 형식을 확인해주세요.")
        with col_b:
            if st.button("⏭️ 건너뛰기 (자막 없는 원본)"):
                st.session_state.clean_paths = [v["path"] for v in videos]
                st.session_state.durations = [get_video_duration(v["path"]) for v in videos]
                st.rerun()
    else:
        durations = st.session_state.durations
        total_dur = sum(durations)
        st.success(
            f"✅ 영상 {len(videos)}개 준비 완료 — 총 길이 **{total_dur:.1f}초** "
            f"({' + '.join(f'{d:.0f}초' for d in durations)})"
        )

        # 자막 제거본 미리보기 (건너뛴 경우는 생략)
        if st.session_state.clean_paths[0] != videos[0]["path"]:
            if "clean_previews" not in st.session_state:
                with st.spinner("자막 제거본 미리보기 준비 중..."):
                    st.session_state.clean_previews = [
                        make_playable_preview(p, os.path.join("temp", f"preview_clean_{i}.mp4"))
                        for i, p in enumerate(st.session_state.clean_paths)
                    ]
            video_grid([
                {"name": v["name"], "path": st.session_state.clean_previews[i], "sub": "✨ 자막 제거본"}
                for i, v in enumerate(videos)
            ])
        else:
            st.caption("자막 제거를 건너뛰어 원본을 그대로 사용합니다.")

# ──────────────────────────────────────────────
# 3단계. 대본 입력 & 자막 타이밍
# ──────────────────────────────────────────────
if st.session_state.get("clean_paths"):
    videos = st.session_state.videos
    durations = st.session_state.durations
    total_dur = sum(durations)
    n_videos = len(videos)

    step_header("3", "대본 입력 & 자막 타이밍", done=bool(st.session_state.get("rows")))

    script_text = st.text_area(
        "대본을 입력하세요 (한 줄이 자막 하나가 됩니다)",
        placeholder="안녕하세요\n오늘은 요리 영상입니다\n먼저 재료를 준비해주세요\n감사합니다",
        height=160,
        key="script_text",
    )

    lines = [line.strip() for line in (script_text or "").split("\n") if line.strip()]

    if lines:
        col_len, col_method = st.columns(2)
        with col_len:
            length_options = ["자동 (자막에 맞게)"] + [f"약 {s}초" for s in range(10, 65, 5)]
            target_choice = st.selectbox(
                "🎯 편집 후 영상 길이",
                length_options,
                help="자동: 자막 글자 수에 맞는 자연스러운 길이. 초를 고르면 그 길이에 가깝게 맞춥니다.",
            )
        with col_method:
            pick_method = st.radio(
                "구간 선택 방식",
                ["영상 전체에서 고르게 뽑기 (추천)", "앞부분부터 순서대로"],
                help="고르게 뽑기: 각 영상의 처음~끝에서 골고루 잘라 요약하듯 편집합니다.",
            )

        n = len(lines)

        # 자막 글자 수 기반 자연스러운 길이 (정확한 초 맞춤이 아니라 자막에 맞게)
        durs = [line_duration(t) for t in lines]
        if target_choice != "자동 (자막에 맞게)":
            target_len = float(target_choice.replace("약 ", "").replace("초", ""))
            scale = target_len / sum(durs)
            durs = [max(1.0, d * scale) for d in durs]
        if sum(durs) > total_dur:
            durs = [d * total_dur / sum(durs) for d in durs]

        config_key = (tuple(lines), target_choice, pick_method, tuple(round(d, 1) for d in durations))
        if st.session_state.get("rows_source") != config_key:
            alloc = allocate_lines(durations, n)  # 영상별 대본 줄 수 (길이 비례)
            rows = []
            line_idx = 0
            for vi, (d, m) in enumerate(zip(durations, alloc), start=1):
                if m == 0:
                    continue
                if pick_method.startswith("영상 전체에서"):
                    window = d / m
                    for i in range(m):
                        s_len = min(durs[line_idx], window)
                        start = i * window + (window - s_len) / 2
                        rows.append({
                            "video": vi,
                            "start": round(start, 2),
                            "end": round(start + s_len, 2),
                            "text": lines[line_idx],
                        })
                        line_idx += 1
                else:
                    cursor = 0.0
                    for i in range(m):
                        s_len = min(durs[line_idx], max(0.5, d - cursor))
                        start = min(cursor, max(0.0, d - s_len))
                        rows.append({
                            "video": vi,
                            "start": round(start, 2),
                            "end": round(min(d, start + s_len), 2),
                            "text": lines[line_idx],
                        })
                        cursor = start + s_len
                        line_idx += 1
            st.session_state.rows = rows
            st.session_state.rows_source = config_key

        expected = sum(r["end"] - r["start"] for r in st.session_state.rows)
        video_hint = f" · 영상 {n_videos}개에 길이 비례로 배분" if n_videos > 1 else ""
        st.markdown(
            f"📝 자막 **{n}개** · 완성 영상 길이 **약 {expected:.0f}초** (자막 글자 수에 맞춰 배분){video_hint}. "
            "**표에서 영상 번호와 시작/종료 시간을 직접 수정**할 수 있어요 — 시간은 해당 영상 기준입니다."
        )

        edited_df = st.data_editor(
            pd.DataFrame(st.session_state.rows).rename(
                columns={"video": "영상", "start": "시작(초)", "end": "종료(초)", "text": "자막"}
            ),
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "영상": st.column_config.NumberColumn(min_value=1, max_value=n_videos, step=1,
                                                      help=f"1~{n_videos}번 영상 중 어디서 잘라올지"),
            },
            key=f"timing_editor_{abs(hash(config_key))}",  # 설정이 바뀌면 표를 새로 그림 (꼬임 방지)
        )

        # 표에서 지워지거나 잘못 입력된 칸은 건너뛰기 (빈 칸으로 인한 편집 실패 방지)
        rows = []
        for _, r in edited_df.iterrows():
            try:
                if pd.isna(r["시작(초)"]) or pd.isna(r["종료(초)"]) or pd.isna(r["영상"]):
                    continue
                rows.append({
                    "video": int(r["영상"]),
                    "start": float(r["시작(초)"]),
                    "end": float(r["종료(초)"]),
                    "text": "" if pd.isna(r["자막"]) else str(r["자막"]),
                })
            except (ValueError, TypeError):
                continue
        if not rows:
            st.warning("⚠️ 표에 올바른 구간이 없습니다. 시작/종료 시간을 확인해주세요.")

        # ──────────────────────────────────────
        # 4단계. 편집 실행
        # ──────────────────────────────────────
        step_header("4", "편집 실행", done=bool(st.session_state.get("result_path")))

        mode_options = ["✂️ 컷 편집 + 새 자막 입히기 (추천)", "✂️ 컷 편집만 (자막 없이)"]
        if n_videos == 1:
            mode_options.append("💬 자막만 입히기 (원본 그대로)")

        mode = st.radio(
            "편집 방식",
            mode_options,
            help="컷 편집: 표의 각 구간만 잘라 순서대로 이어붙입니다.",
        )

        if st.button("🚀 편집 시작", type="primary"):
            srt_path = os.path.join("temp", "subtitles.srt")
            result_path = None
            clean_paths = st.session_state.clean_paths

            with st.spinner("동영상 편집 중... (영상 길이에 따라 시간이 걸립니다)"):
                if mode.startswith("✂️"):
                    cut_path = os.path.join("temp", "cut_video.mp4")
                    if extract_multi_video_segments(clean_paths, rows, cut_path):
                        retimed = retime_rows_cumulative(rows)
                        if "새 자막" in mode:
                            save_srt(build_srt_from_rows(retimed), srt_path)
                            result_path = os.path.join("output", "edited_with_subs.mp4")
                            if not add_subtitles_to_video(cut_path, srt_path, result_path):
                                result_path = None
                        else:
                            result_path = os.path.join("output", "edited_video.mp4")
                            os.replace(cut_path, result_path)
                        if result_path:
                            st.session_state.result_srt = build_srt_from_rows(retimed)

                else:  # 자막만 입히기 (영상 1개)
                    save_srt(build_srt_from_rows(rows), srt_path)
                    result_path = os.path.join("output", "video_with_subs.mp4")
                    if add_subtitles_to_video(clean_paths[0], srt_path, result_path):
                        st.session_state.result_srt = build_srt_from_rows(rows)
                    else:
                        result_path = None

            if result_path:
                st.session_state.result_path = result_path
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
