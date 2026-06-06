import streamlit as st
import json
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="Typer MŚ 2026", page_icon="⚽", layout="wide")

# ── Constants ─────────────────────────────────────────────────────────────────

DATA_DIR = "data"
USERS_FILE        = os.path.join(DATA_DIR, "users.json")
MATCHES_FILE      = os.path.join(DATA_DIR, "matches.json")
BETS_FILE         = os.path.join(DATA_DIR, "bets.json")
EXTRA_BETS_FILE   = os.path.join(DATA_DIR, "extra_bets.json")
EXTRA_RESULTS_FILE= os.path.join(DATA_DIR, "extra_results.json")

ADMIN_PIN = "9999"
GROUP_LABELS = list("ABCDEFGHIJKL")
KNOCKOUT_STAGES = {"1/16", "1/8", "QF", "SF", "3M", "FINAL"}
STAGE_LABELS = {"1/16": "1/16 Finału", "1/8": "1/8 Finału", "QF": "Ćwierćfinały",
                "SF": "Półfinały", "3M": "Mecz o 3. Miejsce", "FINAL": "⭐ FINAŁ"}

EXTRA_KEYS = ["top_scorer", "best_player", "best_goalkeeper", "best_u21",
              "winner_1st", "winner_2nd", "winner_3rd"]
EXTRA_LABELS = {
    "top_scorer":    "⚽ Król Strzelców",
    "best_player":   "🌟 Najlepszy Zawodnik (MVP)",
    "best_goalkeeper":"🧤 Najlepszy Bramkarz",
    "best_u21":      "🌱 Najlepszy Młody Zawodnik U21",
    "winner_1st":    "🥇 Mistrz Świata (1. miejsce)",
    "winner_2nd":    "🥈 Wicemistrz Świata (2. miejsce)",
    "winner_3rd":    "🥉 3. Miejsce",
}
EXTRA_PLACEHOLDERS = {
    "top_scorer":    "np. Robert Lewandowski",
    "best_player":   "np. Kylian Mbappé",
    "best_goalkeeper":"np. Wojciech Szczęsny",
    "best_u21":      "np. Endrick",
    "winner_1st":    "np. Brazylia",
    "winner_2nd":    "np. Francja",
    "winner_3rd":    "np. Niemcy",
}

# ── JSON helpers ──────────────────────────────────────────────────────────────

def load_json(path, default=None):
    if default is None:
        default = []
    if not os.path.exists(path):
        return {} if isinstance(default, dict) else default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── Match helpers ─────────────────────────────────────────────────────────────

def get_outcome(a, b):
    return "A" if a > b else ("B" if a < b else "X")

def calc_pts(pa, pb, ra, rb):
    if pa == ra and pb == rb: return 5
    if get_outcome(pa, pb) == get_outcome(ra, rb): return 2
    return 0

def match_kickoff(match):
    try:
        return datetime.strptime(f"{match['date']} {match.get('time','00:00')}", "%Y-%m-%d %H:%M")
    except Exception:
        return None

def is_locked(match):
    """Returns (locked: bool, msg: str)"""
    if match.get("finished"):
        return True, "Mecz zakończony"
    ko = match_kickoff(match)
    if not ko:
        return False, ""
    now = datetime.now()
    if now >= ko:
        return True, "🔒 Mecz już się rozpoczął"
    delta = ko - now
    total_s = int(delta.total_seconds())
    d, rem = divmod(total_s, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if total_s < 3600:
        cd = f"⏱ {m}m {rem%60:02}s"
    elif d > 0:
        cd = f"⏱ {d}d {h:02}h {m:02}m"
    else:
        cd = f"⏱ {h}h {m:02}m"
    warn = "" if total_s > 3600 else f"⚠️ Zamknięcie za {cd}"
    return False, warn

def countdown_str(match):
    ko = match_kickoff(match)
    if not ko:
        return ""
    delta = ko - datetime.now()
    total_s = int(delta.total_seconds())
    if total_s <= 0:
        return ""
    d, rem = divmod(total_s, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    if d > 0:
        return f"⏱ {d}d {h:02}h {m:02}m"
    elif h > 0:
        return f"⏱ {h}h {m:02}m"
    else:
        return f"⏱ {m}m {s:02}s"

# ── Group standings (H2H tiebreaker) ─────────────────────────────────────────

def _h2h_stats(team_set, finished):
    s = {t: {"GF": 0, "GA": 0, "Pkt": 0} for t in team_set}
    for m in finished:
        ta, tb = m["team_a"], m["team_b"]
        if ta in s and tb in s:
            ra, rb = m["real_score_a"], m["real_score_b"]
            s[ta]["GF"] += ra; s[ta]["GA"] += rb
            s[tb]["GF"] += rb; s[tb]["GA"] += ra
            if ra > rb:   s[ta]["Pkt"] += 3
            elif ra < rb: s[tb]["Pkt"] += 3
            else:         s[ta]["Pkt"] += 1; s[tb]["Pkt"] += 1
    return s

def _sort_tied(tied, overall, finished):
    h = _h2h_stats(set(tied), finished)
    def key(t):
        return (
            -h[t]["Pkt"],
            -(h[t]["GF"] - h[t]["GA"]),
            -h[t]["GF"],
            -(overall[t]["GF"] - overall[t]["GA"]),
            -overall[t]["GF"],
            t,
        )
    return sorted(tied, key=key)

def build_group_standings(matches):
    teams_by_grp = {}
    fin_by_grp   = {}
    for m in matches:
        g = m.get("group", "")
        if g not in GROUP_LABELS:
            continue
        teams_by_grp.setdefault(g, set()).update([m["team_a"], m["team_b"]])
        if m["finished"] and m["real_score_a"] is not None:
            fin_by_grp.setdefault(g, []).append(m)

    standings = {}
    for g in GROUP_LABELS:
        if g not in teams_by_grp:
            continue
        ov = {t: {"M":0,"W":0,"D":0,"L":0,"GF":0,"GA":0,"Pkt":0} for t in teams_by_grp[g]}
        for m in fin_by_grp.get(g, []):
            ta, tb = m["team_a"], m["team_b"]
            if ta not in ov or tb not in ov:
                continue
            ra, rb = m["real_score_a"], m["real_score_b"]
            for t in (ta, tb): ov[t]["M"] += 1
            ov[ta]["GF"] += ra; ov[ta]["GA"] += rb
            ov[tb]["GF"] += rb; ov[tb]["GA"] += ra
            if ra > rb:   ov[ta]["W"]+=1; ov[ta]["Pkt"]+=3; ov[tb]["L"]+=1
            elif ra < rb: ov[tb]["W"]+=1; ov[tb]["Pkt"]+=3; ov[ta]["L"]+=1
            else:         ov[ta]["D"]+=1; ov[ta]["Pkt"]+=1; ov[tb]["D"]+=1; ov[tb]["Pkt"]+=1

        # Sort with H2H tiebreaker
        all_teams = list(teams_by_grp[g])
        by_pts = sorted(all_teams, key=lambda t: -ov[t]["Pkt"])
        result = []
        i = 0
        while i < len(by_pts):
            tied = [by_pts[i]]
            j = i + 1
            while j < len(by_pts) and ov[by_pts[j]]["Pkt"] == ov[by_pts[i]]["Pkt"]:
                tied.append(by_pts[j]); j += 1
            if len(tied) == 1:
                result.append(tied[0])
            else:
                result.extend(_sort_tied(tied, ov, fin_by_grp.get(g, [])))
            i = j

        rows = []
        for pos, t in enumerate(result):
            s = ov[t]
            rows.append({"pos": pos+1, "Drużyna": t,
                         "M": s["M"], "W": s["W"], "R": s["D"], "P": s["L"],
                         "GZ": s["GF"], "GS": s["GA"],
                         "B": s["GF"]-s["GA"], "Pkt": s["Pkt"]})
        standings[g] = rows
    return standings

# ── 3rd place logic ───────────────────────────────────────────────────────────

def get_3rd_sorted(standings):
    out = []
    for g in GROUP_LABELS:
        rows = standings.get(g, [])
        if len(rows) >= 3:
            r = rows[2]
            out.append({"group": g, **r})
    out.sort(key=lambda r: (-r["Pkt"], -r["B"], -r["GZ"], r["Drużyna"]))
    return out

def get_3rd_top8(standings):
    return {r["group"]: r["Drużyna"] for r in get_3rd_sorted(standings)[:8]}

def resolve_3rd_slot(slot_str, top8):
    for g in list(slot_str):
        if g in top8:
            return top8[g]
    return "TBD"

# ── Knockout resolution ───────────────────────────────────────────────────────

def ko_winner(m):
    if not m.get("finished"):
        return None
    ra = m.get("real_score_a") or 0
    rb = m.get("real_score_b") or 0
    if ra > rb:   return m["team_a"]
    elif ra < rb: return m["team_b"]
    pw = m.get("penalties_winner")
    return pw if pw else None

def ko_loser(m):
    w = ko_winner(m)
    if not w:
        return None
    return m["team_b"] if w == m["team_a"] else m["team_a"]

def resolve_source(src, standings, all_matches, top8):
    if not src:
        return "TBD"
    if len(src) == 2 and src[0].isdigit() and src[1] in GROUP_LABELS:
        pos = int(src[0]) - 1
        rows = standings.get(src[1], [])
        return rows[pos]["Drużyna"] if pos < len(rows) else "TBD"
    if src.startswith("W"):
        mid = int(src[1:])
        m = next((x for x in all_matches if x["id"] == mid), None)
        return (ko_winner(m) or "TBD") if m else "TBD"
    if src.startswith("L"):
        mid = int(src[1:])
        m = next((x for x in all_matches if x["id"] == mid), None)
        return (ko_loser(m) or "TBD") if m else "TBD"
    if src.startswith("3rd-"):
        return resolve_3rd_slot(src[4:], top8)
    return "TBD"

def resolve_ko_teams(matches, standings):
    top8 = get_3rd_top8(standings)
    ko = [m for m in matches if m.get("stage") in KNOCKOUT_STAGES]
    out = {}
    for m in ko:
        ta = resolve_source(m.get("team_a_source",""), standings, ko, top8)
        tb = resolve_source(m.get("team_b_source",""), standings, ko, top8)
        out[m["id"]] = {"team_a": ta, "team_b": tb}
    return out

def effective_teams(match, resolved):
    r = resolved.get(match["id"], {})
    ta = r.get("team_a") or match.get("team_a") or "TBD"
    tb = r.get("team_b") or match.get("team_b") or "TBD"
    return ta, tb

# ── Extra bets deadline ───────────────────────────────────────────────────────

def extra_deadline(matches):
    gm = [m for m in matches if m.get("stage") == "group"]
    if not gm:
        return False, "", None
    earliest = min(gm, key=lambda m: f"{m.get('date','9999')} {m.get('time','99:99')}")
    ko = match_kickoff(earliest)
    if not ko:
        return False, "", None
    now = datetime.now()
    if now >= ko:
        return True, f"🔒 Zamknięte — turniej zaczął się {earliest['date']} o {earliest['time']}", ko
    cd = countdown_str(earliest)
    return False, f"Zamknięcie typów dodatkowych {cd}", ko

# ── Points ────────────────────────────────────────────────────────────────────

def all_points(matches, bets, extra_bets, extra_results, resolved):
    pts = {}
    for m in matches:
        if not m["finished"]: continue
        mid = str(m["id"])
        ra, rb = m["real_score_a"], m["real_score_b"]
        ta, tb = effective_teams(m, resolved)
        for user, ub in bets.items():
            if mid in ub:
                b = ub[mid]
                if b.get("score_a") is not None and b.get("score_b") is not None:
                    pts[user] = pts.get(user, 0) + calc_pts(b["score_a"], b["score_b"], ra, rb)
    for user, ub in extra_bets.items():
        for key in EXTRA_KEYS:
            actual = (extra_results.get(key) or "").strip().lower()
            guess  = (ub.get(key) or "").strip().lower()
            if actual and guess and actual == guess:
                pts[user] = pts.get(user, 0) + 20
    return pts

# ── Session state ─────────────────────────────────────────────────────────────

for k, v in [("logged_in", False), ("username", None), ("admin_auth", False)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ═══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════════════════════════════

def show_login():
    st.markdown(
        "<div style='text-align:center;padding:3rem 0 1rem'>"
        "<span style='font-size:4rem'>⚽</span>"
        "<h1 style='margin:0;font-size:2.4rem'>Mistrzostwa Świata 2026</h1>"
        "<p style='color:#888;font-size:1.1rem;margin-top:.4rem'>System typowania meczów</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.markdown("### 🔐 Logowanie")
        users = load_json(USERS_FILE, {})
        name = st.selectbox("Wybierz swoje imię", ["-- wybierz --"] + sorted(users.keys()))
        pin  = st.text_input("Wprowadź PIN (4 cyfry)", type="password", max_chars=4)
        if st.button("Zaloguj się", use_container_width=True, type="primary"):
            if name == "-- wybierz --": st.error("Wybierz imię.")
            elif not pin: st.error("Wprowadź PIN.")
            elif users.get(name) == pin:
                st.session_state.logged_in = True
                st.session_state.username  = name
                st.rerun()
            else: st.error("❌ Nieprawidłowy PIN.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 – OBSTAWIANIE
# ═══════════════════════════════════════════════════════════════════════════════

def _bet_card_header(match, ta, tb, extra_msg=""):
    grp = match.get("group","")
    stage = match.get("stage","group")
    rnd  = match.get("round")
    lbl  = f"Kolejka {rnd} · " if rnd else ""
    stage_lbl = STAGE_LABELS.get(stage, stage) if stage != "group" else f"Gr. {grp}"
    cd   = countdown_str(match)
    html = (
        f"<div style='background:#1e2a3a;border-radius:10px;padding:10px 14px;margin-bottom:4px'>"
        f"<span style='color:#aaa;font-size:.78rem'>{stage_lbl} · {lbl}🕐 {match.get('date','')} {match.get('time','')}</span>"
    )
    if cd:
        html += f"<span style='color:#3498db;font-size:.78rem;margin-left:8px'>{cd}</span>"
    html += f"<br><b>{ta} vs {tb}</b>"
    if extra_msg:
        html += f"<br><span style='color:#f39c12;font-size:.78rem'>{extra_msg}</span>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def _render_score_inputs(match, existing, ta, tb):
    mid = str(match["id"])
    c1, c2, c3 = st.columns([2,1,2])
    with c1:
        st.markdown(f"<div style='text-align:center;font-weight:bold'>{ta}</div>", unsafe_allow_html=True)
        sa = st.number_input(f"a_{mid}", min_value=0, max_value=20,
                             value=int(existing.get("score_a",0)),
                             key=f"bet_a_{mid}", label_visibility="collapsed")
    with c2:
        st.markdown("<div style='text-align:center;padding-top:28px;color:#888;font-size:1.4rem'>–</div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div style='text-align:center;font-weight:bold'>{tb}</div>", unsafe_allow_html=True)
        sb = st.number_input(f"b_{mid}", min_value=0, max_value=20,
                             value=int(existing.get("score_b",0)),
                             key=f"bet_b_{mid}", label_visibility="collapsed")
    return sa, sb

def tab_obstawianie(matches, resolved):
    st.header("🏟️ Obstawianie meczów")
    username  = st.session_state.username
    bets      = load_json(BETS_FILE, {})
    user_bets = bets.get(username, {})

    # Separate matches
    open_m, locked_m, finished_m = [], [], []
    for m in matches:
        locked, _ = is_locked(m)
        if m["finished"]:
            finished_m.append(m)
        elif locked:
            locked_m.append(m)
        else:
            open_m.append(m)

    # ── Open ──────────────────────────────────────────────────────────────────
    if open_m:
        # Split by stage
        group_open = [m for m in open_m if m.get("stage")=="group"]
        ko_open    = [m for m in open_m if m.get("stage") in KNOCKOUT_STAGES]

        def render_open_section(section_matches, section_title):
            if not section_matches:
                return
            st.markdown(f"#### {section_title}")
            with st.form(f"form_{section_title.replace(' ','_')}"):
                new_bets = {}
                for match in section_matches:
                    mid = str(match["id"])
                    existing = user_bets.get(mid, {})
                    ta, tb = effective_teams(match, resolved)
                    _, warn = is_locked(match)
                    _bet_card_header(match, ta, tb, warn)
                    sa, sb = _render_score_inputs(match, existing, ta, tb)
                    new_bets[mid] = {"score_a": sa, "score_b": sb}
                if st.form_submit_button("💾 Zapisz typy", use_container_width=True, type="primary"):
                    saved, skipped = [], []
                    for match in section_matches:
                        mid = str(match["id"])
                        if is_locked(match)[0]:
                            skipped.append(f"{effective_teams(match,resolved)[0]} vs {effective_teams(match,resolved)[1]}")
                        else:
                            bets.setdefault(username, {})[mid] = new_bets[mid]
                            saved.append(mid)
                    if saved:
                        save_json(BETS_FILE, bets)
                        st.success(f"✅ Zapisano {len(saved)} typów.")
                    if skipped:
                        st.warning(f"Pominięto (zamknięte): {', '.join(skipped)}")
                    st.rerun()

        render_open_section(group_open, "📅 Faza Grupowa")
        render_open_section(ko_open,    "🏆 Faza Pucharowa")
    else:
        st.info("Wszystkie mecze są aktualnie zablokowane lub zakończone.")

    # ── Locked upcoming ───────────────────────────────────────────────────────
    if locked_m:
        st.markdown("---")
        st.markdown("#### 🔒 Zablokowane mecze")
        for m in locked_m:
            mid = str(m["id"])
            ex = user_bets.get(mid, {})
            ta, tb = effective_teams(m, resolved)
            _, lmsg = is_locked(m)
            has = ex.get("score_a") is not None
            bet_d = f"Twój typ: <b>{ex['score_a']}:{ex['score_b']}</b>" if has else "<span style='color:#e74c3c'>Brak typu</span>"
            st.markdown(
                f"<div style='background:#1e2034;border:1px solid #3a3a5a;border-radius:10px;"
                f"padding:10px 14px;margin-bottom:6px'>"
                f"<div style='display:flex;justify-content:space-between'>"
                f"<div><span style='color:#aaa;font-size:.78rem'>{m.get('date','')} {m.get('time','')}</span><br>"
                f"<b>{ta} vs {tb}</b><br><span style='font-size:.85rem'>{bet_d}</span></div>"
                f"<span style='color:#e67e22;font-size:.82rem;padding-left:8px'>{lmsg}</span></div></div>",
                unsafe_allow_html=True,
            )

    # ── Finished ──────────────────────────────────────────────────────────────
    if finished_m:
        st.markdown("---")
        st.markdown("#### ✅ Zakończone mecze")
        for m in finished_m:
            mid = str(m["id"])
            ex = user_bets.get(mid, {})
            ta, tb = effective_teams(m, resolved)
            ra, rb = m["real_score_a"], m["real_score_b"]
            pw = m.get("penalties_winner")
            pw_note = f" (karne: {pw})" if pw else ""
            if ex.get("score_a") is not None:
                pts = calc_pts(ex["score_a"], ex["score_b"], ra, rb)
                col = "#2ecc71" if pts==5 else "#f39c12" if pts==2 else "#e74c3c"
                bdg = "🎯 Dokładny!" if pts==5 else "✓ Dobry wynik" if pts==2 else "✗ Pudło"
                st.markdown(
                    f"<div style='background:#1e2a3a;border-radius:10px;padding:10px 14px;margin-bottom:6px;"
                    f"display:flex;justify-content:space-between;align-items:center'>"
                    f"<div><b>{ta} vs {tb}</b><br>"
                    f"<span style='color:#aaa;font-size:.82rem'>Wynik: {ra}:{rb}{pw_note} · Typ: {ex['score_a']}:{ex['score_b']}</span></div>"
                    f"<div style='color:{col};font-weight:bold'>{bdg} +{pts}</div></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='background:#1e2a3a;border-radius:10px;padding:10px 14px;margin-bottom:6px'>"
                    f"<b>{ta} vs {tb}</b> · {ra}:{rb}{pw_note}"
                    f"<span style='color:#e74c3c;margin-left:10px'>Brak typu</span></div>",
                    unsafe_allow_html=True,
                )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 – TYPY DODATKOWE
# ═══════════════════════════════════════════════════════════════════════════════

def tab_extra(matches):
    st.header("🏆 Typy Dodatkowe")
    username    = st.session_state.username
    extra_bets  = load_json(EXTRA_BETS_FILE, {})
    user_extra  = extra_bets.get(username, {})
    extra_res   = load_json(EXTRA_RESULTS_FILE, {})
    locked, dl_msg, _ = extra_deadline(matches)

    if locked:
        st.error(dl_msg)
    else:
        st.info(f"**Każdy trafiony typ dodatkowy = +20 pkt.** {dl_msg}")

    with st.form("extra_form"):
        c1, c2 = st.columns(2)
        inputs = {}
        keys_left  = EXTRA_KEYS[:4]
        keys_right = EXTRA_KEYS[4:]
        for col, keys in [(c1, keys_left), (c2, keys_right)]:
            with col:
                for k in keys:
                    st.markdown(f"##### {EXTRA_LABELS[k]}")
                    actual = extra_res.get(k)
                    suffix = ""
                    if actual:
                        guess = (user_extra.get(k) or "").strip().lower()
                        if guess == actual.strip().lower():
                            suffix = " ✅ +20 pkt"
                        else:
                            suffix = f" (wynik: {actual})"
                    inputs[k] = st.text_input(
                        f"{EXTRA_LABELS[k]}{suffix}",
                        value=user_extra.get(k, ""),
                        placeholder=EXTRA_PLACEHOLDERS[k],
                        key=f"extra_{k}",
                        disabled=locked,
                        label_visibility="collapsed",
                    )
        st.markdown("---")
        if st.form_submit_button("💾 Zapisz typy dodatkowe", use_container_width=True,
                                  type="primary", disabled=locked):
            extra_bets[username] = {k: v.strip() for k, v in inputs.items()}
            save_json(EXTRA_BETS_FILE, extra_bets)
            st.success("✅ Zapisano!"); st.rerun()

    # Summary card
    if any(user_extra.values()):
        st.markdown("---")
        st.markdown("##### 📋 Twoje aktualne typy")
        c1, c2 = st.columns(2)
        for i, k in enumerate(EXTRA_KEYS):
            val = user_extra.get(k) or "—"
            actual = extra_res.get(k)
            if actual:
                ok = (val.strip().lower() == actual.strip().lower())
                badge = " ✅" if ok else " ❌"
                note = f"<br><span style='font-size:.75rem;color:#aaa'>Wynik: {actual}</span>"
            else:
                badge, note = "", ""
            with (c1 if i % 2 == 0 else c2):
                st.markdown(
                    f"<div style='background:#1e2a3a;border-radius:10px;padding:12px 16px;margin-bottom:8px'>"
                    f"<div style='color:#aaa;font-size:.82rem'>{EXTRA_LABELS[k]}</div>"
                    f"<div style='font-size:1rem;font-weight:bold;margin-top:4px'>{val}{badge}</div>{note}</div>",
                    unsafe_allow_html=True,
                )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 – TABELE GRUPOWE
# ═══════════════════════════════════════════════════════════════════════════════

def _place_badge(p): return {1:"🥇",2:"🥈",3:"🔵",4:"⬛"}.get(p, str(p))

def tab_grupy(matches, standings):
    st.header("📋 Tabele Grupowe")
    fin_g = sum(1 for m in matches if m["finished"] and m.get("stage")=="group")
    tot_g = sum(1 for m in matches if m.get("stage")=="group")
    st.caption(
        f"Rozegrano **{fin_g}/{tot_g}** meczów fazy grupowej. "
        "🥇🥈 = awans bezpośredni · 🔵 = możliwy awans jako najlepsze 3. miejsce · ⬛ = odpada"
    )

    # Best 3rd places box
    all3 = get_3rd_sorted(standings)
    if any(r["M"] > 0 for r in all3):
        with st.expander("📊 Ranking 3. miejsc (top 8 awansuje do 1/16 finału)"):
            for i, r in enumerate(all3):
                adv = "✅" if i < 8 else "❌"
                gd = f"+{r['B']}" if r['B'] > 0 else str(r['B'])
                st.markdown(
                    f"<div style='background:{'#162030' if i<8 else '#1e1e2e'};border-radius:8px;"
                    f"padding:6px 12px;margin:2px 0;display:flex;justify-content:space-between;font-size:.85rem'>"
                    f"<span>{adv} <b>#{i+1}</b> {r['Drużyna']} <span style='color:#aaa'>(Gr.{r['group']})</span></span>"
                    f"<span>M:{r['M']} W:{r['W']} R:{r['R']} P:{r['P']} GZ:{r['GZ']} GS:{r['GS']} B:{gd} "
                    f"<b style='color:#f1c40f'>Pkt:{r['Pkt']}</b></span></div>",
                    unsafe_allow_html=True,
                )
    st.markdown("---")

    for g in GROUP_LABELS:
        rows = standings.get(g, [])
        if not rows:
            continue
        gm = [m for m in matches if m.get("group")==g]
        played = sum(1 for m in gm if m["finished"])
        total  = len(gm)

        st.markdown(
            f"<div style='background:#1a2540;border-radius:14px;padding:18px 20px;margin-bottom:18px'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px'>"
            f"<h3 style='margin:0;color:#f1c40f'>Grupa {g}</h3>"
            f"<span style='color:#888;font-size:.85rem'>{played}/{total} meczów</span></div>",
            unsafe_allow_html=True,
        )

        # Header row
        st.markdown(
            "<div style='display:grid;grid-template-columns:2rem 1fr repeat(8,3rem);gap:4px;"
            "font-size:.8rem;color:#888;padding:0 4px 6px;border-bottom:1px solid #2a3a5a'>"
            "<span>#</span><span>Drużyna</span>"
            "<span style='text-align:center'>M</span><span style='text-align:center'>W</span>"
            "<span style='text-align:center'>R</span><span style='text-align:center'>P</span>"
            "<span style='text-align:center'>GZ</span><span style='text-align:center'>GS</span>"
            "<span style='text-align:center'>B</span>"
            "<span style='text-align:center;color:#f1c40f;font-weight:bold'>Pkt</span></div>",
            unsafe_allow_html=True,
        )

        for r in rows:
            pos = r["pos"]
            bg  = "#162038" if pos<=2 else "#1a2030" if pos==3 else "#1e1e2e"
            gd  = f"+{r['B']}" if r['B']>0 else str(r['B'])
            pk  = f"<span style='color:#f1c40f;font-weight:bold'>{r['Pkt']}</span>" if r['Pkt']>0 else str(r['Pkt'])
            st.markdown(
                f"<div style='display:grid;grid-template-columns:2rem 1fr repeat(8,3rem);gap:4px;"
                f"background:{bg};border-radius:8px;padding:7px 4px;margin:2px 0;align-items:center'>"
                f"<span style='font-size:1rem'>{_place_badge(pos)}</span>"
                f"<span style='font-size:.9rem;font-weight:500'>{r['Drużyna']}</span>"
                f"<span style='text-align:center;font-size:.88rem'>{r['M']}</span>"
                f"<span style='text-align:center;color:#2ecc71;font-size:.88rem'>{r['W']}</span>"
                f"<span style='text-align:center;font-size:.88rem'>{r['R']}</span>"
                f"<span style='text-align:center;color:#e74c3c;font-size:.88rem'>{r['P']}</span>"
                f"<span style='text-align:center;font-size:.88rem'>{r['GZ']}</span>"
                f"<span style='text-align:center;font-size:.88rem'>{r['GS']}</span>"
                f"<span style='text-align:center;color:#aaa;font-size:.88rem'>{gd}</span>"
                f"<span style='text-align:center;font-size:.88rem'>{pk}</span></div>",
                unsafe_allow_html=True,
            )

        # Match details expander
        with st.expander("Wyniki meczów grupy"):
            for m in sorted(gm, key=lambda x: f"{x['date']} {x.get('time','')}"):
                rnd = m.get("round")
                rl  = f"K{rnd} · " if rnd else ""
                if m["finished"]:
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;padding:4px 0;"
                        f"border-bottom:1px solid #2a3050;font-size:.85rem'>"
                        f"<span style='color:#888'>{rl}{m['date']}</span>"
                        f"<span><b>{m['team_a']}</b> <b style='color:#f1c40f'>{m['real_score_a']}:{m['real_score_b']}</b> <b>{m['team_b']}</b></span></div>",
                        unsafe_allow_html=True,
                    )
                else:
                    lk,_ = is_locked(m)
                    ic = "🔒" if lk else "📅"
                    cd = countdown_str(m) if not lk else ""
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;padding:4px 0;"
                        f"border-bottom:1px solid #2a3050;font-size:.85rem;color:#888'>"
                        f"<span>{rl}{m['date']} {m.get('time','')}</span>"
                        f"<span>{ic} {m['team_a']} – {m['team_b']} {cd}</span></div>",
                        unsafe_allow_html=True,
                    )

        st.markdown("</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 – DRABINKA
# ═══════════════════════════════════════════════════════════════════════════════

def _ko_card(match, resolved, user_bets):
    mid = str(match["id"])
    ta, tb = effective_teams(match, resolved)
    locked, lmsg = is_locked(match)
    cd = countdown_str(match) if not locked and not match["finished"] else ""
    mn = match["id"]

    if match["finished"]:
        ra, rb = match["real_score_a"], match["real_score_b"]
        pw = match.get("penalties_winner")
        pw_note = f"<br><span style='font-size:.72rem;color:#f39c12'>Karne: {pw}</span>" if pw else ""
        w = ko_winner(match)
        ta_style = "color:#f1c40f;font-weight:bold" if ta==w else "color:#aaa"
        tb_style = "color:#f1c40f;font-weight:bold" if tb==w else "color:#aaa"
        ub = user_bets.get(mid, {})
        pts_str = ""
        if ub.get("score_a") is not None:
            pts = calc_pts(ub["score_a"], ub["score_b"], ra, rb)
            cc = "#2ecc71" if pts==5 else "#f39c12" if pts==2 else "#e74c3c"
            pts_str = f"<span style='color:{cc};font-size:.72rem;float:right'>+{pts}</span>"
        st.markdown(
            f"<div style='background:#1a2540;border-radius:10px;padding:10px 12px;margin:4px 0'>"
            f"<div style='color:#888;font-size:.72rem'>M{mn} · {match.get('stadium','')} · {match['date']}</div>"
            f"<div style='display:grid;grid-template-columns:1fr auto 1fr;align-items:center;margin-top:6px;gap:4px'>"
            f"<span style='{ta_style};font-size:.9rem'>{ta}</span>"
            f"<span style='text-align:center;font-weight:bold;font-size:1.1rem;color:#fff;padding:0 6px'>{ra}:{rb}</span>"
            f"<span style='{tb_style};font-size:.9rem;text-align:right'>{tb}</span>"
            f"</div>{pw_note}{pts_str}</div>",
            unsafe_allow_html=True,
        )
    else:
        status_col = "#e67e22" if locked else "#3498db"
        status_txt = lmsg if locked else cd
        ub = user_bets.get(mid, {})
        bet_d = f"Typ: {ub['score_a']}:{ub['score_b']}" if ub.get("score_a") is not None else ""
        st.markdown(
            f"<div style='background:#1a2030;border-radius:10px;padding:10px 12px;margin:4px 0;opacity:.9'>"
            f"<div style='color:#888;font-size:.72rem'>M{mn} · {match.get('stadium','')} · {match['date']} {match.get('time','')}</div>"
            f"<div style='display:grid;grid-template-columns:1fr auto 1fr;align-items:center;margin-top:6px;gap:4px'>"
            f"<span style='font-size:.88rem'>{ta}</span>"
            f"<span style='text-align:center;color:#555;padding:0 6px'>vs</span>"
            f"<span style='font-size:.88rem;text-align:right'>{tb}</span>"
            f"</div>"
            f"<div style='color:{status_col};font-size:.72rem;margin-top:4px'>{status_txt}"
            f"{'  · ' + bet_d if bet_d else ''}</div></div>",
            unsafe_allow_html=True,
        )

def tab_drabinka(matches, resolved):
    st.header("🏆 Drabinka Fazy Pucharowej")
    bets      = load_json(BETS_FILE, {})
    user_bets = bets.get(st.session_state.username, {})

    stage_order = [("1/16","1/16 Finału (32→16)"), ("1/8","1/8 Finału (16→8)"),
                   ("QF","Ćwierćfinały"), ("SF","Półfinały"),
                   ("3M","Mecz o 3. Miejsce"), ("FINAL","⭐ FINAŁ")]

    for stage_key, stage_name in stage_order:
        stage_matches = [m for m in matches if m.get("stage")==stage_key]
        if not stage_matches:
            continue

        fin = sum(1 for m in stage_matches if m["finished"])
        st.markdown(
            f"<div style='background:#0f1a2e;border-left:4px solid #f1c40f;"
            f"padding:8px 16px;margin:18px 0 8px;border-radius:0 8px 8px 0'>"
            f"<b style='color:#f1c40f'>{stage_name}</b>"
            f"<span style='color:#888;font-size:.85rem;margin-left:10px'>{fin}/{len(stage_matches)} zakończonych</span></div>",
            unsafe_allow_html=True,
        )

        cols_n = 2 if stage_key in ("1/16","1/8") else (2 if stage_key=="QF" else 1)
        cols   = st.columns(cols_n)
        for i, m in enumerate(stage_matches):
            with cols[i % cols_n]:
                _ko_card(m, resolved, user_bets)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 – RANKING
# ═══════════════════════════════════════════════════════════════════════════════

def tab_ranking(matches, resolved):
    st.header("📊 Ranking Typerów")
    bets       = load_json(BETS_FILE, {})
    extra_bets = load_json(EXTRA_BETS_FILE, {})
    extra_res  = load_json(EXTRA_RESULTS_FILE, {})
    users      = load_json(USERS_FILE, {})
    pts        = all_points(matches, bets, extra_bets, extra_res, resolved)

    fin_c = sum(1 for m in matches if m["finished"])
    c1,c2,c3 = st.columns(3)
    with c1: st.metric("Zakończone mecze", f"{fin_c}/{len(matches)}")
    with c2: st.metric("Typerów", len(users))
    with c3: st.metric("Najwyższy wynik", f"{max(pts.values(),default=0)} pkt")

    st.markdown("---")
    ranking = sorted(users.keys(), key=lambda u: pts.get(u,0), reverse=True)
    medals  = ["🥇","🥈","🥉"]

    if fin_c == 0:
        st.info("⏳ Ranking pojawi się po rozegraniu pierwszych meczów.")

    for pos, user in enumerate(ranking, 1):
        p     = pts.get(user, 0)
        medal = medals[pos-1] if pos<=3 else f"#{pos}"
        me    = user == st.session_state.username
        bg    = "#1e3a2a" if me else "#1e2a3a"
        bord  = "2px solid #2ecc71" if me else "none"
        me_l  = " <span style='color:#2ecc71;font-size:.78rem'>(Ty)</span>" if me else ""

        ub = bets.get(user, {})
        exact = outcome = 0
        for m in matches:
            if not m["finished"]: continue
            mid = str(m["id"])
            if mid in ub and ub[mid].get("score_a") is not None:
                pp = calc_pts(ub[mid]["score_a"], ub[mid]["score_b"],
                              m["real_score_a"], m["real_score_b"])
                if pp==5: exact+=1
                elif pp==2: outcome+=1

        # Extra bet hits
        ue = extra_bets.get(user, {})
        extra_hits = sum(
            1 for k in EXTRA_KEYS
            if (extra_res.get(k) or "").strip().lower() == (ue.get(k) or "").strip().lower()
            and extra_res.get(k)
        )
        extra_pts = extra_hits * 20

        st.markdown(
            f"<div style='background:{bg};border:{bord};border-radius:12px;"
            f"padding:14px 20px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center'>"
            f"<div style='display:flex;align-items:center;gap:14px'>"
            f"<span style='font-size:1.6rem'>{medal}</span>"
            f"<div><b style='font-size:1.05rem'>{user}{me_l}</b><br>"
            f"<span style='color:#aaa;font-size:.8rem'>🎯 {exact} dokł. · ✓ {outcome} wyniki · 🏆 {extra_hits}×20={extra_pts} extra</span>"
            f"</div></div>"
            f"<div style='font-size:1.6rem;font-weight:bold;color:#f1c40f'>{p} <span style='font-size:.9rem;color:#aaa'>pkt</span></div></div>",
            unsafe_allow_html=True,
        )

    # Extra bets table
    if extra_bets:
        st.markdown("---")
        st.markdown("### 🎯 Typy Dodatkowe wszystkich graczy")
        import pandas as pd
        df_data = []
        for u in sorted(users.keys()):
            ue = extra_bets.get(u, {})
            row = {"Uczestnik": u}
            for k in EXTRA_KEYS:
                val = ue.get(k) or "—"
                act = extra_res.get(k)
                if act:
                    ok = val.strip().lower() == act.strip().lower()
                    val = val + (" ✅" if ok else " ❌")
                row[EXTRA_LABELS[k]] = val
            df_data.append(row)
        st.dataframe(pd.DataFrame(df_data), use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6 – PANEL ADMINISTRATORA
# ═══════════════════════════════════════════════════════════════════════════════

def tab_admin(matches, resolved):
    st.header("🔧 Panel Administratora")

    if not st.session_state.admin_auth:
        st.markdown("Wprowadź PIN administratora.")
        pin_in = st.text_input("PIN", type="password", max_chars=4, key="admin_pin")
        if st.button("Zaloguj", type="primary"):
            if pin_in == ADMIN_PIN:
                st.session_state.admin_auth = True; st.rerun()
            else: st.error("❌ Zły PIN.")
        return

    st.success("✅ Zalogowany jako administrator.")
    bets = load_json(BETS_FILE, {})

    # ── Wyniki meczów ──────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### ⚽ Wprowadź wyniki meczów")
    st.caption("Zaznacz 'Zakończony' → punkty przeliczają się automatycznie.")

    pending = [m for m in matches if not m["finished"]]
    if not pending:
        st.info("Wszystkie mecze zakończone.")
    else:
        stage_groups_order = ["group"] + list(KNOCKOUT_STAGES)
        for stage_key in stage_groups_order:
            if stage_key == "group":
                seg = [m for m in pending if m.get("stage")=="group"]
                seg_label = "Faza Grupowa"
            else:
                seg = [m for m in pending if m.get("stage")==stage_key]
                seg_label = STAGE_LABELS.get(stage_key, stage_key)
            if not seg:
                continue
            with st.expander(f"**{seg_label}** ({len(seg)} oczekujących)", expanded=(stage_key=="group")):
                with st.form(f"results_{stage_key}"):
                    res, fin_flags, pen_flags = {}, {}, {}
                    for m in seg:
                        mid = str(m["id"])
                        ta, tb = effective_teams(m, resolved)
                        lk,_ = is_locked(m)
                        lk_ic = "🔒 " if lk else ""
                        rnd = m.get("round")
                        rl  = f"K{rnd} · " if rnd else ""
                        st.markdown(
                            f"<div style='background:#1e2a3a;border-radius:8px;padding:8px 14px;margin-bottom:4px'>"
                            f"<b>{lk_ic}#{m['id']} {ta} vs {tb}</b> "
                            f"<span style='color:#aaa;font-size:.82rem'>· {rl}{m.get('date','')} {m.get('time','')} · {m.get('stadium','')}</span></div>",
                            unsafe_allow_html=True,
                        )
                        c1,c2,c3,c4,c5 = st.columns([2,1,2,2,2])
                        with c1: sa = st.number_input(f"A{mid}",min_value=0,max_value=30,value=0,key=f"adm_a_{mid}",label_visibility="collapsed")
                        with c2: st.markdown("<div style='text-align:center;padding-top:8px;color:#888'>–</div>",unsafe_allow_html=True)
                        with c3: sb = st.number_input(f"B{mid}",min_value=0,max_value=30,value=0,key=f"adm_b_{mid}",label_visibility="collapsed")
                        with c4: fin_flags[mid] = st.checkbox("Zakończony", key=f"adm_fin_{mid}")
                        with c5:
                            if stage_key != "group":
                                pen_flags[mid] = st.selectbox("Karne",["—", ta, tb],key=f"adm_pen_{mid}")
                            else:
                                pen_flags[mid] = "—"
                        res[mid] = {"score_a": sa, "score_b": sb}

                    if st.form_submit_button("💾 Zapisz wyniki", use_container_width=True, type="primary"):
                        changed = 0
                        for m in seg:
                            mid = str(m["id"])
                            if fin_flags.get(mid):
                                m["real_score_a"] = res[mid]["score_a"]
                                m["real_score_b"] = res[mid]["score_b"]
                                m["finished"] = True
                                pw = pen_flags.get(mid, "—")
                                m["penalties_winner"] = pw if pw != "—" else None
                                # Update team names in match record
                                ta2, tb2 = effective_teams(m, resolved)
                                m["team_a"] = ta2
                                m["team_b"] = tb2
                                changed += 1
                        if changed:
                            save_json(MATCHES_FILE, matches)
                            st.success(f"✅ Zapisano {changed} wynik(ów)."); st.rerun()
                        else:
                            st.warning("Nie zaznaczono żadnego meczu.")

    # ── Zakończone mecze ───────────────────────────────────────────────────────
    finished_list = [m for m in matches if m["finished"]]
    if finished_list:
        st.markdown("---")
        st.markdown("### ✅ Zakończone mecze")
        for m in finished_list:
            ta, tb = effective_teams(m, resolved)
            pw = m.get("penalties_winner")
            pw_note = f" (karne: {pw})" if pw else ""
            st.markdown(
                f"<div style='background:#1a3020;border-radius:8px;padding:8px 14px;margin-bottom:4px;"
                f"display:flex;justify-content:space-between'>"
                f"<span><b>{ta} vs {tb}</b> <span style='color:#aaa;font-size:.82rem'>· {m.get('stage','').upper()} · {m.get('date','')}</span></span>"
                f"<span style='color:#2ecc71;font-weight:bold'>{m['real_score_a']}:{m['real_score_b']}{pw_note}</span></div>",
                unsafe_allow_html=True,
            )

    # ── Wyniki typów dodatkowych ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🏆 Potwierdź wyniki typów dodatkowych")
    st.caption("Wpisz rzeczywistych zwycięzców — gracze z trafionym typem dostaną +20 pkt każdy.")
    extra_res = load_json(EXTRA_RESULTS_FILE, {})
    with st.form("extra_results_form"):
        er_inputs = {}
        c1, c2 = st.columns(2)
        for i, k in enumerate(EXTRA_KEYS):
            with (c1 if i%2==0 else c2):
                st.markdown(f"**{EXTRA_LABELS[k]}**")
                er_inputs[k] = st.text_input(
                    EXTRA_LABELS[k], value=extra_res.get(k,""),
                    placeholder=EXTRA_PLACEHOLDERS[k],
                    key=f"er_{k}", label_visibility="collapsed"
                )
        if st.form_submit_button("💾 Zapisz wyniki dodatkowe", use_container_width=True):
            save_json(EXTRA_RESULTS_FILE, {k: v.strip() for k,v in er_inputs.items()})
            st.success("✅ Wyniki dodatkowe zapisane."); st.rerun()

    # ── Dodaj mecz ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### ➕ Dodaj mecz")
    with st.form("add_match"):
        c1,c2,c3,c4 = st.columns([2,2,1.5,1.5])
        with c1: nta = st.text_input("Drużyna A", placeholder="np. Polska")
        with c2: ntb = st.text_input("Drużyna B", placeholder="np. Niemcy")
        with c3: ndt = st.date_input("Data")
        with c4: ntm = st.text_input("Godz.", value="21:00", max_chars=5)
        c5,c6 = st.columns(2)
        with c5: ngr = st.text_input("Etap/Grupa", placeholder="A, 1/16, QF …")
        with c6: nrd = st.number_input("Kolejka (0=brak)", min_value=0, max_value=3, value=0)
        if st.form_submit_button("Dodaj", use_container_width=True):
            if nta.strip() and ntb.strip():
                nid = max((m["id"] for m in matches), default=0) + 1
                stage_v = ngr.strip() if ngr.strip() in KNOCKOUT_STAGES else "group"
                matches.append({"id":nid,"team_a":nta.strip(),"team_b":ntb.strip(),
                                 "date":str(ndt),"time":ntm.strip() or "21:00",
                                 "group":ngr.strip(),"stage":stage_v,
                                 "round":int(nrd) if nrd else None,
                                 "real_score_a":None,"real_score_b":None,"finished":False})
                save_json(MATCHES_FILE, matches)
                st.success(f"✅ Dodano: {nta} vs {ntb}"); st.rerun()
            else: st.error("Podaj obie drużyny.")

    # ── Usuń mecz ──────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🗑️ Usuń mecz")
    unfin = [m for m in matches if not m["finished"]]
    if unfin:
        labels = [f"#{m['id']} {effective_teams(m,resolved)[0]} vs {effective_teams(m,resolved)[1]} ({m.get('date','')})" for m in unfin]
        sel = st.selectbox("Mecz", ["-- wybierz --"]+labels, key="del_m")
        if st.button("🗑️ Usuń", type="secondary"):
            if sel != "-- wybierz --":
                idx = labels.index(sel)
                del_id = unfin[idx]["id"]
                save_json(MATCHES_FILE, [m for m in matches if m["id"]!=del_id])
                st.success(f"Usunięto #{del_id}"); st.rerun()

    # ── Zarządzanie uczestnikami ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 👥 Uczestnicy")
    users = load_json(USERS_FILE, {})
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### ➕ Dodaj uczestnika")
        with st.form("add_user"):
            nn = st.text_input("Imię")
            np = st.text_input("PIN (4 cyfry)", max_chars=4)
            if st.form_submit_button("Dodaj", use_container_width=True):
                if not nn.strip(): st.error("Podaj imię.")
                elif nn.strip() in users: st.error("Już istnieje.")
                elif not np.isdigit() or len(np)!=4: st.error("PIN = 4 cyfry.")
                else:
                    users[nn.strip()] = np
                    save_json(USERS_FILE, users)
                    st.success(f"Dodano: {nn.strip()}"); st.rerun()
    with c2:
        st.markdown("##### 👤 Lista i usuwanie")
        pts_all = all_points(matches, bets, load_json(EXTRA_BETS_FILE,{}), load_json(EXTRA_RESULTS_FILE,{}), resolved)
        for uname in sorted(users.keys()):
            col_u, col_p, col_d = st.columns([3,1,1])
            with col_u:
                st.markdown(
                    f"<div style='background:#1e2a3a;border-radius:8px;padding:7px 12px;"
                    f"display:flex;justify-content:space-between'>"
                    f"<span>{uname}</span><span style='color:#f1c40f'>{pts_all.get(uname,0)} pkt</span></div>",
                    unsafe_allow_html=True,
                )
            with col_d:
                if st.button("🗑️", key=f"del_u_{uname}", help=f"Usuń {uname}"):
                    del users[uname]
                    save_json(USERS_FILE, users)
                    st.success(f"Usunięto {uname}"); st.rerun()

    st.markdown("---")
    if st.button("🔒 Wyloguj z panelu admina"):
        st.session_state.admin_auth = False; st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    if not st.session_state.logged_in:
        show_login(); return

    username = st.session_state.username
    c1, c2 = st.columns([4,1])
    with c1: st.markdown("<h2 style='margin:0;padding-top:4px'>⚽ Typer MŚ 2026</h2>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div style='text-align:right;padding-top:8px;color:#aaa'>Zalogowany: <b>{username}</b></div>", unsafe_allow_html=True)
        if st.button("Wyloguj", use_container_width=True):
            for k in ["logged_in","username","admin_auth"]:
                st.session_state[k] = False if k!="username" else None
            st.rerun()
    st.markdown("---")

    # Load data once
    matches  = load_json(MATCHES_FILE, [])
    standings = build_group_standings(matches)
    resolved  = resolve_ko_teams(matches, standings)

    t1,t2,t3,t4,t5,t6 = st.tabs([
        "🏟️ Obstawianie",
        "🏆 Typy Dodatkowe",
        "📋 Tabele Grupowe",
        "🎯 Drabinka",
        "📊 Ranking",
        "🔧 Admin",
    ])
    with t1: tab_obstawianie(matches, resolved)
    with t2: tab_extra(matches)
    with t3: tab_grupy(matches, standings)
    with t4: tab_drabinka(matches, resolved)
    with t5: tab_ranking(matches, resolved)
    with t6: tab_admin(matches, resolved)


if __name__ == "__main__":
    main()
