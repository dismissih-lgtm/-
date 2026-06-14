"""브라우저에서 보면서 게시물을 만드는 웹 UI (Streamlit).

실행:
    streamlit run app.py

탭 두 개로 구성됩니다.
  - ✍️ 직접 만들기 : 보면서 이미지·캡션을 만들고 업로드 (수동)
  - ⏰ 자동 게시 설정 : 매일 자동 게시 시간/켜짐 설정 + 지금 한 번 실행
"""

import datetime

import streamlit as st

st.set_page_config(page_title="인스타 자동 게시", page_icon="📸")
st.title("📸 인스타그램 게시물 자동 생성")

# 설정(.env)이 안 되어 있으면 import 단계에서 막히므로 친절히 안내
try:
    from src import (
        caption_generator,
        image_generator,
        instagram_publisher,
        news_fetcher,
        settings,
    )

    setup_ok = True
except Exception as exc:  # noqa: BLE001 - 설정 미비를 사용자에게 안내
    setup_ok = False
    st.error(
        f"⚠️ 설정 오류: {exc}\n\n"
        ".env 파일에 API 키와 인스타그램 토큰을 채웠는지 확인하세요. "
        "(.env.example 참고)"
    )


def _reset() -> None:
    for key in ("image_url", "caption", "news_headline"):
        st.session_state.pop(key, None)


def _generate(image_topic: str, caption_topic: str, headline: str | None) -> None:
    """이미지·캡션을 생성해 세션에 저장합니다."""
    st.session_state.news_headline = headline
    st.session_state.image_url = image_generator.generate_image(image_topic)
    data = caption_generator.generate_caption(caption_topic)
    st.session_state.caption = caption_generator.format_full_caption(data)


if setup_ok:
    tab_manual, tab_auto = st.tabs(["✍️ 직접 만들기", "⏰ 자동 게시 설정"])

    # ─────────────────────────────────────────────────────
    # 탭 1: 직접 만들기 (수동)
    # ─────────────────────────────────────────────────────
    with tab_manual:
        mode = st.radio(
            "게시물 소재",
            ["주제 직접 입력", "오늘의 뉴스 검색"],
            horizontal=True,
        )

        topic_input = ""
        if mode == "주제 직접 입력":
            topic_input = st.text_input(
                "주제", placeholder="예: 가을 감성 카페 신메뉴 홍보"
            )

        if st.button("🎨 생성하기", type="primary"):
            with st.spinner("생성 중... (이미지·캡션 만드는 데 20~40초 걸려요)"):
                try:
                    if mode == "오늘의 뉴스 검색":
                        news = news_fetcher.fetch_top_news()
                        _generate(news["headline"], news["summary"], news["headline"])
                    else:
                        if not topic_input.strip():
                            st.warning("주제를 입력하세요.")
                            st.stop()
                        _generate(topic_input, topic_input, None)
                except Exception as exc:  # noqa: BLE001
                    st.error(f"생성 실패: {exc}")

        # 미리보기 & 업로드
        if st.session_state.get("image_url"):
            st.divider()
            st.subheader("미리보기")

            if st.session_state.get("news_headline"):
                st.caption(f"📰 {st.session_state.news_headline}")

            st.image(st.session_state.image_url, use_container_width=True)

            st.session_state.caption = st.text_area(
                "캡션 (업로드 전 수정 가능)",
                st.session_state.caption,
                height=250,
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("📤 인스타그램에 업로드", type="primary"):
                    with st.spinner("업로드 중..."):
                        try:
                            post_id = instagram_publisher.publish_photo(
                                st.session_state.image_url,
                                st.session_state.caption,
                            )
                            st.success(f"✅ 업로드 완료! 게시물 ID: {post_id}")
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"업로드 실패: {exc}")
            with col2:
                if st.button("🗑️ 초기화"):
                    _reset()
                    st.rerun()

            st.info(
                "💡 생성된 이미지 URL은 약 1시간 후 만료됩니다. "
                "확인 후 바로 업로드하세요."
            )

    # ─────────────────────────────────────────────────────
    # 탭 2: 자동 게시 설정
    # ─────────────────────────────────────────────────────
    with tab_auto:
        cfg = settings.load()

        st.subheader("매일 자동 게시 설정")

        enabled = st.toggle("매일 자동 게시 켜기", value=cfg["schedule_enabled"])

        run_time = st.time_input(
            "실행 시각 (한국 시간)",
            value=datetime.time(cfg["schedule_hour"], cfg["schedule_minute"]),
            step=300,  # 5분 단위
        )

        news_query = st.text_input(
            "뉴스 검색어 (비우면 기본값 사용)",
            value=cfg["news_query"],
            placeholder="예: 오늘의 IT 기술 뉴스",
        )

        if st.button("💾 설정 저장", type="primary"):
            settings.save(
                {
                    "schedule_enabled": enabled,
                    "schedule_hour": run_time.hour,
                    "schedule_minute": run_time.minute,
                    "news_query": news_query.strip(),
                }
            )
            st.success(
                f"저장됨 · 매일 {run_time:%H:%M} KST 자동 게시 "
                f"{'켜짐' if enabled else '꺼짐'}"
            )

        st.divider()
        st.markdown(
            "이 시간 설정으로 자동 게시하려면 **스케줄러를 켜두어야** 합니다:\n"
            "```\npython -m src.scheduler\n```\n"
            "컴퓨터를 끄더라도 자동 실행하려면 **GitHub Actions** 방식을 쓰세요 "
            "(README 참고)."
        )

        st.divider()
        st.subheader("지금 한 번 실행 (수동)")
        st.caption("자동 게시가 어떻게 동작하는지 지금 바로 테스트합니다.")
        if st.button("📰 오늘의 뉴스로 지금 게시"):
            with st.spinner("뉴스 검색 → 이미지·캡션 생성 → 업로드 중..."):
                try:
                    news = news_fetcher.fetch_top_news(news_query.strip() or None)
                    image_url = image_generator.generate_image(news["headline"])
                    data = caption_generator.generate_caption(news["summary"])
                    full_caption = caption_generator.format_full_caption(data)
                    st.image(image_url, use_container_width=True)
                    st.text(full_caption)
                    post_id = instagram_publisher.publish_photo(image_url, full_caption)
                    st.success(f"✅ 업로드 완료! 게시물 ID: {post_id}")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"실행 실패: {exc}")
