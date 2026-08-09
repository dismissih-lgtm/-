"""브라우저에서 보면서 게시물을 만드는 웹 UI (Streamlit).

실행:
    streamlit run app.py

탭 세 개로 구성됩니다.
  - ✍️ 직접 만들기 : 보면서 이미지·캡션을 만들고 업로드 (수동)
  - 🛒 쿠팡 카드뉴스 : 쿠팡 파트너스 URL → 카드뉴스 3~4장 생성
  - ⏰ 자동 게시 설정 : 매일 자동 게시 시간/켜짐 설정 + 지금 한 번 실행
"""

import datetime
import io
import zipfile

import streamlit as st

st.set_page_config(page_title="인스타 자동 게시", page_icon="📸")
st.title("📸 인스타그램 게시물 자동 생성")

# 설정(.env)이 안 되어 있으면 import 단계에서 막히므로 친절히 안내
try:
    from src import (
        caption_generator,
        card_generator,
        coupang_fetcher,
        image_generator,
        kakao_sender,
        main,
        news_fetcher,
        screenshot_analyzer,
        settings,
    )

    setup_ok = True

    DEST_LABELS = {"kakao": "💬 카카오톡으로 받기", "instagram": "📤 인스타그램 자동 업로드"}
    DEST_KEYS = list(DEST_LABELS.keys())
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
    tab_manual, tab_coupang, tab_auto = st.tabs(
        ["✍️ 직접 만들기", "🛒 쿠팡 카드뉴스", "⏰ 자동 게시 설정"]
    )

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
                "캡션 (전송 전 수정 가능)",
                st.session_state.caption,
                height=250,
            )

            saved_dest = settings.load().get("destination", "kakao")
            dest = st.radio(
                "전송 방법",
                DEST_KEYS,
                format_func=lambda k: DEST_LABELS[k],
                index=DEST_KEYS.index(saved_dest),
                horizontal=True,
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 전송", type="primary"):
                    with st.spinner("전송 중..."):
                        try:
                            headline = st.session_state.get("news_headline") or "게시물"
                            if dest == "kakao":
                                kakao_sender.send_post(
                                    st.session_state.image_url,
                                    headline,
                                    st.session_state.caption,
                                )
                                st.success("✅ 카카오톡으로 전송 완료!")
                            else:
                                main._deliver(
                                    "instagram",
                                    st.session_state.image_url,
                                    headline,
                                    st.session_state.caption,
                                )
                                st.success("✅ 인스타그램 업로드 완료!")
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"전송 실패: {exc}")
            with col2:
                if st.button("🗑️ 초기화"):
                    _reset()
                    st.rerun()

            st.info(
                "💡 생성된 이미지 URL은 약 1시간 후 만료됩니다. "
                "확인 후 바로 업로드하세요."
            )

    # ─────────────────────────────────────────────────────
    # 탭 2: 쿠팡 파트너스 카드뉴스
    # ─────────────────────────────────────────────────────
    with tab_coupang:
        st.caption(
            "휴대폰에서 쿠팡 상품 화면을 **캡처해서 올리면**, 상품 정보를 읽고 "
            "상품 사진을 잘라내 인스타그램 규격 카드뉴스 3~4장과 캡션을 만듭니다."
        )
        cp_shot = st.file_uploader(
            "📱 쿠팡 화면 캡처 업로드",
            type=["png", "jpg", "jpeg", "webp"],
            key="cp_shot",
            help="쿠팡 앱에서 상품 화면(사진·상품명·가격이 보이게)을 캡처해서 올려주세요.",
        )
        if cp_shot:
            st.image(cp_shot, width=180)

        cp_url = st.text_input(
            "쿠팡 파트너스 URL (선택 — 캡션에 링크를 넣고 싶을 때)",
            placeholder="https://link.coupang.com/a/xxxxx",
            key="cp_url",
        )

        with st.expander("상품 정보/사진 직접 입력 (자동 인식이 이상할 때)"):
            cp_name = st.text_input("상품명", key="cp_name")
            cp_price = st.text_input("가격 (예: 29,900원)", key="cp_price")
            cp_features = st.text_area(
                "특징 (한 줄에 하나씩)", key="cp_features", height=110
            )
            cp_photo = st.file_uploader(
                "카드에 넣을 상품 사진 (선택 — 캡처에서 자동 추출이 실패할 때)",
                type=["png", "jpg", "jpeg", "webp"],
                key="cp_photo",
            )

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            cp_cards = st.radio("카드 장수", [4, 3], horizontal=True, key="cp_cards")
        with col2:
            cp_theme = st.selectbox("테마", list(card_generator.THEMES), key="cp_theme")
        with col3:
            cp_ratio = st.selectbox(
                "비율", list(card_generator.RATIOS), key="cp_ratio",
                help="1:1 정사각형 / 4:5 세로형 (인스타 피드 최대)",
            )
        with col4:
            cp_handle = st.text_input("인스타 핸들 (선택)", placeholder="@my_shop", key="cp_handle")

        if st.button("🎨 카드뉴스 생성", type="primary", key="cp_generate"):
            manual_name = cp_name.strip()
            if not (cp_shot or cp_url.strip() or manual_name):
                st.warning("화면 캡처를 올리거나, URL 또는 상품명을 입력하세요.")
                st.stop()
            with st.spinner("캡처 분석 → 문구 생성 → 카드 렌더링 중... (30~60초 걸려요)"):
                try:
                    features = [f.strip() for f in cp_features.splitlines() if f.strip()]

                    # 카드에 넣을 상품 사진 (직접 업로드가 우선)
                    product_photo = None
                    if cp_photo:
                        product_photo = screenshot_analyzer.load_image(cp_photo.getvalue())

                    if cp_shot:
                        # 캡처 이미지에서 정보 + 상품 사진 추출
                        product, cropped = screenshot_analyzer.analyze_screenshot(
                            cp_shot.getvalue()
                        )
                        if product_photo is None:
                            product_photo = cropped
                        product["url"] = cp_url.strip()
                    elif manual_name:
                        product = {
                            "name": manual_name, "price": cp_price.strip(),
                            "category": "", "url": cp_url.strip(),
                            "features": features, "summary": "",
                        }
                    else:
                        product = coupang_fetcher.fetch_product_info(cp_url.strip())

                    # 직접 입력값이 있으면 우선 적용
                    if manual_name:
                        product["name"] = manual_name
                    if cp_price.strip():
                        product["price"] = cp_price.strip()
                    if features:
                        product["features"] = features

                    if not product.get("name"):
                        st.error(
                            "상품 정보를 찾지 못했습니다. 캡처에 상품명이 잘 보이는지 "
                            "확인하거나, '상품 정보 직접 입력'에 상품명을 넣고 다시 "
                            "시도해 주세요."
                        )
                        st.stop()

                    copy_data = card_generator.generate_copy(product, n_cards=cp_cards)
                    out_dir = (
                        "output/coupang_"
                        + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    )
                    paths = card_generator.render_cards(
                        copy_data, out_dir, theme_name=cp_theme,
                        ratio=cp_ratio, handle=cp_handle.strip(),
                        product_image=product_photo,
                    )
                    st.session_state.cp_paths = [str(p) for p in paths]
                    st.session_state.cp_caption = card_generator.format_caption(
                        copy_data, url=cp_url.strip()
                    )
                    st.session_state.cp_product_name = product["name"]
                except Exception as exc:  # noqa: BLE001
                    st.error(f"생성 실패: {exc}")

        if st.session_state.get("cp_paths"):
            st.divider()
            st.subheader("미리보기")
            st.caption(f"🛒 {st.session_state.get('cp_product_name', '')}")

            cols = st.columns(len(st.session_state.cp_paths))
            for col, path in zip(cols, st.session_state.cp_paths):
                with col:
                    st.image(path, use_container_width=True)

            st.session_state.cp_caption = st.text_area(
                "캡션 (파트너스 고지 문구 포함 — 복사해서 사용하세요)",
                st.session_state.cp_caption,
                height=260,
            )

            # 이미지 + 캡션을 zip 으로 묶어 다운로드
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                for path in st.session_state.cp_paths:
                    zf.write(path, path.split("/")[-1])
                zf.writestr("caption.txt", st.session_state.cp_caption)
            st.download_button(
                "📥 카드 이미지 + 캡션 다운로드 (zip)",
                data=buf.getvalue(),
                file_name="coupang_cards.zip",
                mime="application/zip",
            )
            st.info(
                "💡 다운로드한 이미지를 인스타그램에 여러 장 게시물(캐러셀)로 올리고, "
                "캡션을 붙여넣으세요. 파트너스 링크는 프로필 링크나 댓글에 넣는 것을 "
                "추천합니다. 쿠팡 파트너스 고지 문구는 반드시 유지해야 해요."
            )

    # ─────────────────────────────────────────────────────
    # 탭 3: 자동 게시 설정
    # ─────────────────────────────────────────────────────
    with tab_auto:
        cfg = settings.load()

        st.subheader("매일 자동 게시 설정")

        enabled = st.toggle("매일 자동 실행 켜기", value=cfg["schedule_enabled"])

        run_time = st.time_input(
            "실행 시각 (한국 시간)",
            value=datetime.time(cfg["schedule_hour"], cfg["schedule_minute"]),
            step=300,  # 5분 단위
        )

        saved_dest = cfg.get("destination", "kakao")
        dest = st.radio(
            "전송 방법",
            DEST_KEYS,
            format_func=lambda k: DEST_LABELS[k],
            index=DEST_KEYS.index(saved_dest),
            horizontal=True,
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
                    "destination": dest,
                }
            )
            st.success(
                f"저장됨 · 매일 {run_time:%H:%M} KST · {DEST_LABELS[dest]} · "
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
        st.caption("자동 실행이 어떻게 동작하는지 지금 바로 테스트합니다.")
        if st.button("📰 오늘의 뉴스로 지금 실행"):
            with st.spinner("뉴스 검색 → 이미지·캡션 생성 → 전송 중..."):
                try:
                    news = news_fetcher.fetch_top_news(news_query.strip() or None)
                    image_url = image_generator.generate_image(news["headline"])
                    data = caption_generator.generate_caption(news["summary"])
                    full_caption = caption_generator.format_full_caption(data)
                    st.image(image_url, use_container_width=True)
                    st.text(full_caption)
                    main._deliver("instagram" if dest == "instagram" else "kakao",
                                  image_url, news["headline"], full_caption)
                    st.success(f"✅ 전송 완료! ({DEST_LABELS[dest]})")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"실행 실패: {exc}")
