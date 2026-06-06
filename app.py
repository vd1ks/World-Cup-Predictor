import streamlit as st
import json
import os

# ── Config ────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Mistrzostwa Świata 2026 – Typer",
    page_icon="⚽",
    layout="wide",
)

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
MATCHES_FILE = os.path.join(DATA_DIR, "matches.json")
BETS_FILE = os.path.join(DATA_DIR, "bets.json")
EXTRA_BETS_FILE = os.path.join(DATA_DIR, "extra_bets.json")

ADMIN_PIN = "9999"

# ── Data helpers ──────────────────────────────────────────────────────────────

def load_json(path):
    if not os.path.exists(path):
        return {} if path != MATCHES_FILE else []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_outcome(score_a, score_b):
    if score_a > score_b:
        return "A"
    elif score_a < score_b:
        return "B"
    return "X"

def calculate_points(pred_a, pred_b, real_a, real_b):
    if pred_a == real_a and pred_b == real_b:
        return 5
    if get_outcome(pred_a, pred_b) == get_outcome(real_a, real_b):
        return 2
    return 0

def recalculate_all_points(matches, bets):
    points = {}
    for match in matches:
        if not match["finished"]:
            continue
        mid = str(match["id"])
        real_a = match["real_score_a"]
        real_b = match["real_score_b"]
        for user, user_bets in bets.items():
            if mid in user_bets:
                bet = user_bets[mid]
                if bet.get("score_a") is not None and bet.get("score_b") is not None:
                    pts = calculate_points(
                        bet["score_a"], bet["score_b"], real_a, real_b
                    )
                    points[user] = points.get(user, 0) + pts
    return points

# ── Session state init ─────────────────────────────────────────────────────────

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None

# ── Login page ─────────────────────────────────────────────────────────────────

def show_login():
    st.markdown(
        """
        <div style='text-align:center; padding: 3rem 0 1rem 0;'>
            <span style='font-size:4rem;'>⚽</span>
            <h1 style='margin:0; font-size:2.4rem;'>Mistrzostwa Świata 2026</h1>
            <p style='color:#888; font-size:1.1rem; margin-top:.4rem;'>System typowania meczów</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("### 🔐 Logowanie")
        users = load_json(USERS_FILE)
        if not users:
            st.error("Brak użytkowników w bazie danych.")
            return

        name = st.selectbox("Wybierz swoje imię", ["-- wybierz --"] + sorted(users.keys()))
        pin = st.text_input("Wprowadź PIN (4 cyfry)", type="password", max_chars=4)

        if st.button("Zaloguj się", use_container_width=True, type="primary"):
            if name == "-- wybierz --":
                st.error("Wybierz swoje imię.")
            elif not pin:
                st.error("Wprowadź PIN.")
            elif users.get(name) == pin:
                st.session_state.logged_in = True
                st.session_state.username = name
                st.rerun()
            else:
                st.error("❌ Nieprawidłowy PIN. Spróbuj ponownie.")

# ── Tab 1: Obstawianie ─────────────────────────────────────────────────────────

def tab_obstawianie():
    st.header("🏟️ Obstawianie meczów")
    username = st.session_state.username
    matches = load_json(MATCHES_FILE)
    bets = load_json(BETS_FILE)
    user_bets = bets.get(username, {})

    upcoming = [m for m in matches if not m["finished"]]
    finished = [m for m in matches if m["finished"]]

    if not upcoming:
        st.info("Brak nadchodzących meczów do obstawienia.")
    else:
        st.markdown("#### 📅 Nadchodzące mecze")
        with st.form("bets_form"):
            new_bets = {}
            for match in upcoming:
                mid = str(match["id"])
                existing = user_bets.get(mid, {})
                group_label = match.get("group", "")
                date_label = match.get("date", "")
                st.markdown(
                    f"<div style='background:#1e2a3a; border-radius:10px; padding:12px 16px; margin-bottom:8px;'>"
                    f"<span style='color:#aaa; font-size:.8rem;'>Grupa {group_label} · {date_label}</span><br>"
                    f"<b style='font-size:1rem;'>{match['team_a']} vs {match['team_b']}</b>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                c1, c2, c3 = st.columns([2, 1, 2])
                with c1:
                    st.markdown(
                        f"<div style='text-align:center; font-weight:bold;'>{match['team_a']}</div>",
                        unsafe_allow_html=True,
                    )
                    score_a = st.number_input(
                        f"Gole {match['team_a']}",
                        min_value=0,
                        max_value=20,
                        value=int(existing.get("score_a", 0)),
                        key=f"a_{mid}",
                        label_visibility="collapsed",
                    )
                with c2:
                    st.markdown(
                        "<div style='text-align:center; padding-top:28px; font-size:1.5rem; color:#888;'>–</div>",
                        unsafe_allow_html=True,
                    )
                with c3:
                    st.markdown(
                        f"<div style='text-align:center; font-weight:bold;'>{match['team_b']}</div>",
                        unsafe_allow_html=True,
                    )
                    score_b = st.number_input(
                        f"Gole {match['team_b']}",
                        min_value=0,
                        max_value=20,
                        value=int(existing.get("score_b", 0)),
                        key=f"b_{mid}",
                        label_visibility="collapsed",
                    )
                new_bets[mid] = {"score_a": score_a, "score_b": score_b}

            if st.form_submit_button("💾 Zapisz wszystkie typy", use_container_width=True, type="primary"):
                bets[username] = {**user_bets, **new_bets}
                save_json(BETS_FILE, bets)
                st.success("✅ Twoje typy zostały zapisane!")
                st.rerun()

    if finished:
        st.markdown("---")
        st.markdown("#### ✅ Zakończone mecze – Twoje wyniki")
        for match in finished:
            mid = str(match["id"])
            existing = user_bets.get(mid, {})
            pred_a = existing.get("score_a")
            pred_b = existing.get("score_b")
            real_a = match["real_score_a"]
            real_b = match["real_score_b"]

            if pred_a is not None and pred_b is not None:
                pts = calculate_points(pred_a, pred_b, real_a, real_b)
                color = "#2ecc71" if pts == 5 else "#f39c12" if pts == 2 else "#e74c3c"
                badge = "🎯 Dokładny wynik!" if pts == 5 else "✓ Dobry wynik" if pts == 2 else "✗ Pudło"
                st.markdown(
                    f"<div style='background:#1e2a3a; border-radius:10px; padding:12px 16px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;'>"
                    f"<div><b>{match['team_a']} vs {match['team_b']}</b><br>"
                    f"<span style='color:#aaa; font-size:.85rem;'>Wynik: {real_a}:{real_b} · Twój typ: {pred_a}:{pred_b}</span></div>"
                    f"<div style='color:{color}; font-weight:bold;'>{badge} <span style='font-size:1.2rem;'>+{pts} pkt</span></div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='background:#1e2a3a; border-radius:10px; padding:12px 16px; margin-bottom:8px;'>"
                    f"<b>{match['team_a']} vs {match['team_b']}</b> · Wynik: {real_a}:{real_b}"
                    f"<span style='color:#e74c3c; margin-left:12px;'>Brak twojego typu</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

# ── Tab 2: Typy Dodatkowe ──────────────────────────────────────────────────────

def tab_extra():
    st.header("🏆 Typy Dodatkowe")
    username = st.session_state.username
    extra = load_json(EXTRA_BETS_FILE)
    user_extra = extra.get(username, {})

    st.markdown(
        "Wpisz swoje typy do nagród indywidualnych. Możesz edytować je w dowolnym momencie."
    )

    with st.form("extra_form"):
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### ⚽ Król Strzelców")
            top_scorer = st.text_input(
                "Imię i nazwisko zawodnika",
                value=user_extra.get("top_scorer", ""),
                placeholder="np. Robert Lewandowski",
                key="top_scorer",
            )
            st.markdown("##### 🧤 Najlepszy Bramkarz")
            best_gk = st.text_input(
                "Imię i nazwisko bramkarza",
                value=user_extra.get("best_goalkeeper", ""),
                placeholder="np. Wojciech Szczęsny",
                key="best_gk",
            )
        with col2:
            st.markdown("##### 🌟 Najlepszy Zawodnik (MVP)")
            best_player = st.text_input(
                "Imię i nazwisko zawodnika",
                value=user_extra.get("best_player", ""),
                placeholder="np. Kylian Mbappé",
                key="best_player",
            )
            st.markdown("##### 🌱 Najlepszy Młody Zawodnik U21")
            best_u21 = st.text_input(
                "Imię i nazwisko zawodnika",
                value=user_extra.get("best_u21", ""),
                placeholder="np. Endrick",
                key="best_u21",
            )

        st.markdown("---")
        if st.form_submit_button("💾 Zapisz typy dodatkowe", use_container_width=True, type="primary"):
            extra[username] = {
                "top_scorer": top_scorer.strip(),
                "best_player": best_player.strip(),
                "best_goalkeeper": best_gk.strip(),
                "best_u21": best_u21.strip(),
            }
            save_json(EXTRA_BETS_FILE, extra)
            st.success("✅ Typy dodatkowe zapisane!")
            st.rerun()

    if any(user_extra.values()):
        st.markdown("---")
        st.markdown("##### 📋 Twoje aktualne typy dodatkowe")
        col1, col2 = st.columns(2)
        items = [
            ("⚽ Król Strzelców", user_extra.get("top_scorer", "—")),
            ("🌟 MVP Turnieju", user_extra.get("best_player", "—")),
            ("🧤 Najlepszy Bramkarz", user_extra.get("best_goalkeeper", "—")),
            ("🌱 Najlepszy U21", user_extra.get("best_u21", "—")),
        ]
        for i, (label, value) in enumerate(items):
            col = col1 if i % 2 == 0 else col2
            with col:
                st.markdown(
                    f"<div style='background:#1e2a3a; border-radius:10px; padding:14px 16px; margin-bottom:10px;'>"
                    f"<div style='color:#aaa; font-size:.85rem;'>{label}</div>"
                    f"<div style='font-size:1.05rem; font-weight:bold; margin-top:4px;'>{value or '—'}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

# ── Tab 3: Ranking ─────────────────────────────────────────────────────────────

def tab_ranking():
    st.header("📊 Ranking Typerów")
    matches = load_json(MATCHES_FILE)
    bets = load_json(BETS_FILE)
    users = load_json(USERS_FILE)

    points = recalculate_all_points(matches, bets)

    finished_count = sum(1 for m in matches if m["finished"])
    total_count = len(matches)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Zakończone mecze", f"{finished_count} / {total_count}")
    with col2:
        st.metric("Liczba typerów", len(users))
    with col3:
        max_pts = max(points.values(), default=0)
        st.metric("Najwyższy wynik", f"{max_pts} pkt")

    st.markdown("---")

    all_users = sorted(users.keys())
    ranking = sorted(all_users, key=lambda u: points.get(u, 0), reverse=True)

    if finished_count == 0:
        st.info("⏳ Turniej jeszcze się nie rozpoczął. Ranking pojawi się po rozegraniu pierwszych meczów.")
    else:
        st.markdown("### 🏅 Tabela punktowa")

    medals = ["🥇", "🥈", "🥉"]

    for pos, user in enumerate(ranking, start=1):
        pts = points.get(user, 0)
        medal = medals[pos - 1] if pos <= 3 else f"#{pos}"
        is_me = user == st.session_state.username
        bg = "#1e3a2a" if is_me else "#1e2a3a"
        border = "2px solid #2ecc71" if is_me else "none"
        me_label = " <span style='color:#2ecc71; font-size:.8rem;'>(Ty)</span>" if is_me else ""

        # Bet details for this user
        user_bets = bets.get(user, {})
        correct_exact = 0
        correct_outcome = 0
        for match in matches:
            if not match["finished"]:
                continue
            mid = str(match["id"])
            if mid in user_bets:
                bet = user_bets[mid]
                if bet.get("score_a") is not None and bet.get("score_b") is not None:
                    p = calculate_points(
                        bet["score_a"], bet["score_b"],
                        match["real_score_a"], match["real_score_b"]
                    )
                    if p == 5:
                        correct_exact += 1
                    elif p == 2:
                        correct_outcome += 1

        st.markdown(
            f"<div style='background:{bg}; border:{border}; border-radius:12px; "
            f"padding:14px 20px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;'>"
            f"<div style='display:flex; align-items:center; gap:16px;'>"
            f"<span style='font-size:1.6rem;'>{medal}</span>"
            f"<div>"
            f"<b style='font-size:1.05rem;'>{user}{me_label}</b><br>"
            f"<span style='color:#aaa; font-size:.82rem;'>🎯 {correct_exact} dokładnych · ✓ {correct_outcome} trafnych wyników</span>"
            f"</div></div>"
            f"<div style='font-size:1.6rem; font-weight:bold; color:#f1c40f;'>{pts} <span style='font-size:.9rem; color:#aaa;'>pkt</span></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Extra bets summary
    extra = load_json(EXTRA_BETS_FILE)
    if extra:
        st.markdown("---")
        st.markdown("### 🎯 Typy Dodatkowe wszystkich graczy")
        extra_df_data = []
        for user in all_users:
            u_extra = extra.get(user, {})
            extra_df_data.append({
                "Uczestnik": user,
                "Król Strzelców": u_extra.get("top_scorer", "—"),
                "MVP": u_extra.get("best_player", "—"),
                "Najlepszy Bramkarz": u_extra.get("best_goalkeeper", "—"),
                "Najlepszy U21": u_extra.get("best_u21", "—"),
            })
        import pandas as pd
        st.dataframe(
            pd.DataFrame(extra_df_data),
            use_container_width=True,
            hide_index=True,
        )

# ── Tab 4: Panel Administratora ───────────────────────────────────────────────

def tab_admin():
    st.header("🔧 Panel Administratora")

    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        st.markdown("Wprowadź PIN administratora, aby uzyskać dostęp.")
        admin_pin_input = st.text_input("PIN Administratora", type="password", max_chars=4, key="admin_pin_input")
        if st.button("Zaloguj jako admin", type="primary"):
            if admin_pin_input == ADMIN_PIN:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("❌ Nieprawidłowy PIN administratora.")
        return

    st.success("✅ Zalogowano jako administrator.")

    matches = load_json(MATCHES_FILE)
    bets = load_json(BETS_FILE)

    # Section: Zarządzanie meczami
    st.markdown("---")
    st.markdown("### ⚙️ Zarządzanie meczami")

    col_add, col_sep, col_manage = st.columns([1.2, 0.1, 1])

    with col_add:
        st.markdown("##### ➕ Dodaj nowy mecz")
        with st.form("add_match_form"):
            new_team_a = st.text_input("Drużyna A", placeholder="np. Polska")
            new_team_b = st.text_input("Drużyna B", placeholder="np. Niemcy")
            new_date = st.date_input("Data meczu")
            new_group = st.text_input("Etap / Grupa", placeholder="np. A, 1/8, Finał")
            if st.form_submit_button("Dodaj mecz", use_container_width=True):
                if new_team_a.strip() and new_team_b.strip():
                    new_id = max((m["id"] for m in matches), default=0) + 1
                    matches.append({
                        "id": new_id,
                        "team_a": new_team_a.strip(),
                        "team_b": new_team_b.strip(),
                        "date": str(new_date),
                        "group": new_group.strip(),
                        "real_score_a": None,
                        "real_score_b": None,
                        "finished": False,
                    })
                    save_json(MATCHES_FILE, matches)
                    st.success(f"✅ Dodano mecz: {new_team_a} vs {new_team_b}")
                    st.rerun()
                else:
                    st.error("Podaj nazwy obu drużyn.")

    with col_manage:
        st.markdown("##### ✏️ Usuń mecz")
        unfinished_matches = [m for m in matches if not m["finished"]]
        if unfinished_matches:
            match_labels = [f"#{m['id']} {m['team_a']} vs {m['team_b']} ({m.get('date','')})" for m in unfinished_matches]
            selected_label = st.selectbox("Wybierz mecz do usunięcia", ["-- wybierz --"] + match_labels, key="del_match")
            if st.button("🗑️ Usuń wybrany mecz", type="secondary"):
                if selected_label != "-- wybierz --":
                    idx = match_labels.index(selected_label)
                    match_to_del = unfinished_matches[idx]
                    matches = [m for m in matches if m["id"] != match_to_del["id"]]
                    save_json(MATCHES_FILE, matches)
                    st.success(f"Usunięto mecz #{match_to_del['id']}")
                    st.rerun()
        else:
            st.info("Brak meczów do usunięcia.")

    # Section: Wyniki meczów
    st.markdown("---")
    st.markdown("### ⚽ Wprowadź wyniki meczów")

    pending = [m for m in matches if not m["finished"]]
    if not pending:
        st.info("Wszystkie mecze zostały już zakończone.")
    else:
        with st.form("results_form"):
            results_to_save = {}
            finished_flags = {}

            for match in pending:
                mid = str(match["id"])
                st.markdown(
                    f"<div style='background:#1e2a3a; border-radius:10px; padding:10px 14px; margin-bottom:6px;'>"
                    f"<b>#{match['id']} {match['team_a']} vs {match['team_b']}</b> "
                    f"<span style='color:#aaa; font-size:.85rem;'>· {match.get('date','')} · Gr. {match.get('group','')}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                c1, c2, c3, c4 = st.columns([2, 1, 2, 2])
                with c1:
                    score_a = st.number_input(
                        f"Gole {match['team_a']}",
                        min_value=0,
                        max_value=30,
                        value=0,
                        key=f"admin_a_{mid}",
                        label_visibility="collapsed",
                    )
                with c2:
                    st.markdown(
                        "<div style='text-align:center; padding-top:8px; color:#888;'>–</div>",
                        unsafe_allow_html=True,
                    )
                with c3:
                    score_b = st.number_input(
                        f"Gole {match['team_b']}",
                        min_value=0,
                        max_value=30,
                        value=0,
                        key=f"admin_b_{mid}",
                        label_visibility="collapsed",
                    )
                with c4:
                    mark_finished = st.checkbox("Zakończony", key=f"admin_fin_{mid}")

                results_to_save[mid] = {"score_a": score_a, "score_b": score_b}
                finished_flags[mid] = mark_finished

            if st.form_submit_button("💾 Zapisz wyniki", use_container_width=True, type="primary"):
                changed = 0
                for match in matches:
                    mid = str(match["id"])
                    if mid in finished_flags and finished_flags[mid]:
                        match["real_score_a"] = results_to_save[mid]["score_a"]
                        match["real_score_b"] = results_to_save[mid]["score_b"]
                        match["finished"] = True
                        changed += 1
                if changed:
                    save_json(MATCHES_FILE, matches)
                    st.success(f"✅ Zapisano wyniki {changed} mecz(ów). Punkty zostały przeliczone automatycznie.")
                    st.rerun()
                else:
                    st.warning("Nie zaznaczono żadnego meczu jako zakończonego.")

    # Section: Finished matches
    finished = [m for m in matches if m["finished"]]
    if finished:
        st.markdown("---")
        st.markdown("### ✅ Zakończone mecze")
        for match in finished:
            st.markdown(
                f"<div style='background:#1a3020; border-radius:10px; padding:10px 14px; margin-bottom:6px; "
                f"display:flex; justify-content:space-between;'>"
                f"<span><b>{match['team_a']} vs {match['team_b']}</b> <span style='color:#aaa; font-size:.85rem;'>· {match.get('date','')}</span></span>"
                f"<span style='font-weight:bold; color:#2ecc71;'>{match['real_score_a']} : {match['real_score_b']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # Section: Manage users
    st.markdown("---")
    st.markdown("### 👥 Zarządzanie uczestnikami")
    users = load_json(USERS_FILE)
    col_u1, col_u2 = st.columns(2)

    with col_u1:
        st.markdown("##### Dodaj uczestnika")
        with st.form("add_user_form"):
            new_name = st.text_input("Imię uczestnika")
            new_pin = st.text_input("PIN (4 cyfry)", max_chars=4)
            if st.form_submit_button("Dodaj", use_container_width=True):
                if not new_name.strip():
                    st.error("Podaj imię uczestnika.")
                elif new_name.strip() in users:
                    st.error("Uczestnik o tym imieniu już istnieje.")
                elif not new_pin.isdigit() or len(new_pin) != 4:
                    st.error("PIN musi składać się z 4 cyfr.")
                else:
                    users[new_name.strip()] = new_pin
                    save_json(USERS_FILE, users)
                    st.success(f"✅ Dodano uczestnika: {new_name.strip()}")
                    st.rerun()

    with col_u2:
        st.markdown("##### Lista uczestników")
        for uname in sorted(users.keys()):
            pts = recalculate_all_points(matches, bets).get(uname, 0)
            st.markdown(
                f"<div style='background:#1e2a3a; border-radius:8px; padding:8px 14px; margin-bottom:6px; "
                f"display:flex; justify-content:space-between;'>"
                f"<span>{uname}</span><span style='color:#f1c40f;'>{pts} pkt</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # Logout admin
    st.markdown("---")
    if st.button("🔒 Wyloguj z panelu admina"):
        st.session_state.admin_authenticated = False
        st.rerun()

# ── Main layout ───────────────────────────────────────────────────────────────

def main():
    if not st.session_state.logged_in:
        show_login()
        return

    username = st.session_state.username

    # Top bar
    col_title, col_user = st.columns([4, 1])
    with col_title:
        st.markdown(
            "<h2 style='margin:0; padding-top:4px;'>⚽ Typer MŚ 2026</h2>",
            unsafe_allow_html=True,
        )
    with col_user:
        st.markdown(
            f"<div style='text-align:right; padding-top:8px; color:#aaa;'>Zalogowany: <b>{username}</b></div>",
            unsafe_allow_html=True,
        )
        if st.button("Wyloguj", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.admin_authenticated = False
            st.rerun()

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🏟️ Obstawianie",
        "🏆 Typy Dodatkowe",
        "📊 Ranking",
        "🔧 Panel Administratora",
    ])

    with tab1:
        tab_obstawianie()
    with tab2:
        tab_extra()
    with tab3:
        tab_ranking()
    with tab4:
        tab_admin()


if __name__ == "__main__":
    main()
