"""브라우저에서 보면서 게시물을 만드는 웹 UI (Streamlit).

실행:
    streamlit run app.py

그러면 브라우저가 열리고, 주제 입력 또는 뉴스 검색 → 이미지·캡션 미리보기 →
캡션 수정 → 업로드 까지 클릭으로 진행할 수 있습니다.
"""

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


if setup_ok:
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

    # ── 생성 ──────────────────────────────────────────────
    if st.button("🎨 생성하기", type="primary"):
        with st.spinner("생성 중... (이미지·캡션 만드는 데 20~40초 걸려요)"):
            try:
                if mode == "오늘의 뉴스 검색":
                    news = news_fetcher.fetch_top_news()
                    image_topic = news["headline"]
                    caption_topic = news["summary"]
                    st.session_state.news_headline = news["headline"]
                else:
                    if not topic_input.strip():
                        st.warning("주제를 입력하세요.")
                        st.stop()
                    image_topic = caption_topic = topic_input
                    st.session_state.news_headline = None

                st.session_state.image_url = image_generator.generate_image(
                    image_topic
                )
                data = caption_generator.generate_caption(caption_topic)
                st.session_state.caption = caption_generator.format_full_caption(
                    data
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"생성 실패: {exc}")

    # ── 미리보기 & 업로드 ─────────────────────────────────
    if st.session_state.get("image_url"):
        st.divider()
        st.subheader("미리보기")

        if st.session_state.get("news_headline"):
            st.caption(f"📰 {st.session_state.news_headline}")

        st.image(st.session_state.image_url, use_container_width=True)

        # 업로드 전에 캡션을 직접 다듬을 수 있습니다.
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
            "오래 두지 말고 확인 후 바로 업로드하세요."
        )
