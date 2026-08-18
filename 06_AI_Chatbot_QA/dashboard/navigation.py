import streamlit as st


MENU_OPTIONS = ["성능관리", "테스트 관리", "지식 DB 관리", "Jira관리"]
# MENU_OPTIONS = ["성능관리", "테스트 관리", "지식 DB 관리", "Jira관리", "Docker 관리"]

SIDEBAR_MENU_OPTIONS = {
    "성능관리": ["운영 모니터링", "K6 성능테스트"],
    "테스트 관리": ["테스트케이스 업로드", "테스트 케이스 실행", "테스트 수행 이력", "자동 테스트 결과"],
    "지식 DB 관리": ["지식 DB 관리"],
    "Jira관리": ["Jira 등록 현황"],
    # "Docker 관리": ["Docker 통합 실행"],
}


def render_topbar():
    with st.container(key="topbar"):
        col_logo, col_menu, col_right = st.columns([2.2, 4.2, 1.6])

        with col_logo:
            st.markdown(
                '<div class="brand-title">💬 AI 교육과정 안내 챗봇 시스템</div>',
                unsafe_allow_html=True,
            )

        with col_menu:
            menu_cols = st.columns(len(MENU_OPTIONS))
            for i, menu_name in enumerate(MENU_OPTIONS):
                with menu_cols[i]:
                    is_selected = st.session_state.current_menu == menu_name
                    button_style = "primary" if is_selected else "secondary"
                    if st.button(
                        menu_name,
                        key=f"btn_{menu_name}",
                        use_container_width=True,
                        type=button_style,
                    ):
                        st.session_state.current_menu = menu_name
                        st.session_state.current_sub_menu = SIDEBAR_MENU_OPTIONS[menu_name][0]
                        st.rerun()

        with col_right:
            st.markdown(
                """
                <div class="topbar-right">
                    <div class="topbar-bell">🔔</div>
                    <div class="topbar-avatar">8</div>
                    <div class="topbar-username">최강3조</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_sidebar():
    active_menu = st.session_state.current_menu
    if active_menu not in SIDEBAR_MENU_OPTIONS:
        active_menu = MENU_OPTIONS[0]
        st.session_state.current_menu = active_menu
        st.session_state.current_sub_menu = SIDEBAR_MENU_OPTIONS[active_menu][0]

    active_sub_menu_options = SIDEBAR_MENU_OPTIONS[active_menu]

    if st.session_state.current_sub_menu not in active_sub_menu_options:
        st.session_state.current_sub_menu = active_sub_menu_options[0]

    with st.sidebar:
        st.markdown(f'<div class="sidebar-title">{active_menu}</div>', unsafe_allow_html=True)
        st.markdown("---")

        for menu_item in active_sub_menu_options:
            is_selected = st.session_state.current_sub_menu == menu_item
            button_style = "primary" if is_selected else "secondary"
            if st.button(
                menu_item,
                key=f"sidebar_{active_menu}_{menu_item}",
                use_container_width=True,
                type=button_style,
            ):
                st.session_state.current_sub_menu = menu_item
                st.rerun()

    return active_menu, st.session_state.current_sub_menu


def render_navigation():
    render_topbar()
    active_menu, sidebar_sub_menu = render_sidebar()
    st.markdown(
        f'<div class="page-kicker">홈 &gt; {active_menu} &gt; {sidebar_sub_menu}</div>',
        unsafe_allow_html=True,
    )
    return active_menu, sidebar_sub_menu
