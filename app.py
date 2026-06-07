import streamlit as st
import json
import os
from datetime import datetime

st.set_page_config(page_title="Typer MŚ 2026", page_icon="⚽", layout="wide")

# ── Constants ─────────────────────────────────────────────────────────────────

DATA_DIR          = "data"
USERS_FILE        = os.path.join(DATA_DIR, "users.json")
MATCHES_FILE      = os.path.join(DATA_DIR, "matches.json")
BETS_FILE         = os.path.join(DATA_DIR, "bets.json")
EXTRA_BETS_FILE   = os.path.join(DATA_DIR, "extra_bets.json")
EXTRA_RESULTS_FILE= os.path.join(DATA_DIR, "extra_results.json")

ADMIN_PIN    = "9999"
GROUP_LABELS = list("ABCDEFGHIJKL")

KNOCKOUT_STAGES     = {"1/32","1/16","1/8","1/4","3M","FINAL"}
KNOCKOUT_STAGE_ORDER= ["1/32","1/16","1/8","1/4","3M","FINAL"]
STAGE_LABELS = {
    "1/32":  "1/32 Finału (Round of 32)",
    "1/16":  "1/16 Finału (Round of 16)",
    "1/8":   "Ćwierćfinały",
    "1/4":   "Półfinały",
    "3M":    "Mecz o 3. Miejsce",
    "FINAL": "⭐ FINAŁ",
}

EXTRA_KEYS = ["top_scorer","best_player","best_goalkeeper","best_u21",
              "winner_1st","winner_2nd","winner_3rd"]
EXTRA_LABELS = {
    "top_scorer":    "⚽ Król Strzelców",
    "best_player":   "🌟 MVP Turnieju",
    "best_goalkeeper":"🧤 Najlepszy Bramkarz",
    "best_u21":      "🌱 Najlepszy Młody U21",
    "winner_1st":    "🥇 Mistrz Świata (1. miejsce)",
    "winner_2nd":    "🥈 Wicemistrz (2. miejsce)",
    "winner_3rd":    "🥉 3. Miejsce",
}
EXTRA_PH = {
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
        return ({} if isinstance(default, dict) else default)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── Match helpers ─────────────────────────────────────────────────────────────

def match_kickoff(m):
    try:
        return datetime.strptime(f"{m['date']} {m.get('time','00:00')}", "%Y-%m-%d %H:%M")
    except Exception:
        return None

def is_locked(m):
    """(locked: bool, msg: str)"""
    if m.get("finished"):
        return True, "Mecz zakończony"
    ko = match_kickoff(m)
    if not ko:
        return False, ""
    now = datetime.now()
    if now >= ko:
        return True, "🔒 Mecz już się rozpoczął"
    delta = ko - now
    s = int(delta.total_seconds())
    d, r = divmod(s, 86400); h, r = divmod(r, 3600); mn = r // 60
    if d > 0: cd = f"⏱ {d}d {h:02}h {mn:02}m"
    elif h > 0: cd = f"⏱ {h}h {mn:02}m"
    else: cd = f"⏱ {mn}m {r%60:02}s"
    warn = "" if s > 3600 else f"⚠️ Zamknięcie za {cd}"
    return False, warn

def countdown_str(m):
    ko = match_kickoff(m)
    if not ko: return ""
    s = int((ko - datetime.now()).total_seconds())
    if s <= 0: return ""
    d, r = divmod(s, 86400); h, r = divmod(r, 3600); mn, sec = divmod(r, 60)
    if d > 0: return f"⏱ {d}d {h:02}h {mn:02}m"
    elif h > 0: return f"⏱ {h}h {mn:02}m"
    else: return f"⏱ {mn}m {sec:02}s"

def calc_pts(pa, pb, ra, rb):
    if pa == ra and pb == rb: return 5
    def out(a,b): return "A" if a>b else ("B" if a<b else "X")
    return 2 if out(pa,pb)==out(ra,rb) else 0

# ── Group standings with H2H ──────────────────────────────────────────────────

def _h2h(team_set, fin):
    s = {t:{"GF":0,"GA":0,"Pkt":0} for t in team_set}
    for m in fin:
        ta,tb = m["team_a"],m["team_b"]
        if ta in s and tb in s:
            ra,rb = m["real_score_a"],m["real_score_b"]
            s[ta]["GF"]+=ra; s[ta]["GA"]+=rb
            s[tb]["GF"]+=rb; s[tb]["GA"]+=ra
            if ra>rb: s[ta]["Pkt"]+=3
            elif ra<rb: s[tb]["Pkt"]+=3
            else: s[ta]["Pkt"]+=1; s[tb]["Pkt"]+=1
    return s

def _sort_tied(tied, ov, fin):
    h = _h2h(set(tied), fin)
    def key(t):
        return (-h[t]["Pkt"], -(h[t]["GF"]-h[t]["GA"]), -h[t]["GF"],
                -(ov[t]["GF"]-ov[t]["GA"]), -ov[t]["GF"], t)
    return sorted(tied, key=key)

def build_standings(matches):
    teams_g, fin_g = {}, {}
    for m in matches:
        g = m.get("group","")
        if g not in GROUP_LABELS: continue
        teams_g.setdefault(g, set()).update([m["team_a"],m["team_b"]])
        if m["finished"] and m["real_score_a"] is not None:
            fin_g.setdefault(g,[]).append(m)

    standings = {}
    for g in GROUP_LABELS:
        if g not in teams_g: continue
        ov = {t:{"M":0,"W":0,"D":0,"L":0,"GF":0,"GA":0,"Pkt":0} for t in teams_g[g]}
        for m in fin_g.get(g,[]):
            ta,tb = m["team_a"],m["team_b"]
            if ta not in ov or tb not in ov: continue
            ra,rb = m["real_score_a"],m["real_score_b"]
            ov[ta]["M"]+=1; ov[tb]["M"]+=1
            ov[ta]["GF"]+=ra; ov[ta]["GA"]+=rb
            ov[tb]["GF"]+=rb; ov[tb]["GA"]+=ra
            if ra>rb: ov[ta]["W"]+=1; ov[ta]["Pkt"]+=3; ov[tb]["L"]+=1
            elif ra<rb: ov[tb]["W"]+=1; ov[tb]["Pkt"]+=3; ov[ta]["L"]+=1
            else: ov[ta]["D"]+=1; ov[ta]["Pkt"]+=1; ov[tb]["D"]+=1; ov[tb]["Pkt"]+=1

        by_pts = sorted(teams_g[g], key=lambda t: -ov[t]["Pkt"])
        result = []
        i = 0
        while i < len(by_pts):
            tied = [by_pts[i]]; j = i+1
            while j < len(by_pts) and ov[by_pts[j]]["Pkt"]==ov[by_pts[i]]["Pkt"]:
                tied.append(by_pts[j]); j+=1
            result.extend([tied[0]] if len(tied)==1 else _sort_tied(tied,ov,fin_g.get(g,[])))
            i = j
        standings[g] = [{"pos":p+1,"Drużyna":t,
                          "M":ov[t]["M"],"W":ov[t]["W"],"R":ov[t]["D"],"P":ov[t]["L"],
                          "GZ":ov[t]["GF"],"GS":ov[t]["GA"],
                          "B":ov[t]["GF"]-ov[t]["GA"],"Pkt":ov[t]["Pkt"]}
                         for p,t in enumerate(result)]
    return standings

# ── 3rd place logic ───────────────────────────────────────────────────────────

def get_3rd_sorted(standings):
    out = []
    for g in GROUP_LABELS:
        rows = standings.get(g,[])
        if len(rows)>=3: out.append({"group":g,**rows[2]})
    out.sort(key=lambda r:(-r["Pkt"],-r["B"],-r["GZ"],r["Drużyna"]))
    return out

def get_3rd_top8(standings):
    return {r["group"]:r["Drużyna"] for r in get_3rd_sorted(standings)[:8]}

def resolve_3rd(slot_str, top8):
    for g in list(slot_str):
        if g in top8: return top8[g]
    return "TBD"

# ── Knockout resolution ───────────────────────────────────────────────────────

def ko_winner(m):
    if not m.get("finished"): return None
    ra = m.get("real_score_a") or 0; rb = m.get("real_score_b") or 0
    if ra>rb: return m.get("team_a")
    if ra<rb: return m.get("team_b")
    return m.get("penalties_winner")

def ko_loser(m):
    w = ko_winner(m)
    if not w: return None
    return m.get("team_b") if w==m.get("team_a") else m.get("team_a")

def resolve_source(src, standings, all_ko, top8):
    if not src: return "TBD"
    if len(src)==2 and src[0].isdigit() and src[1] in GROUP_LABELS:
        rows = standings.get(src[1],[])
        idx = int(src[0])-1
        return rows[idx]["Drużyna"] if idx<len(rows) else "TBD"
    if src.startswith("W"):
        m = next((x for x in all_ko if x["id"]==int(src[1:])),None)
        return ko_winner(m) or "TBD" if m else "TBD"
    if src.startswith("L"):
        m = next((x for x in all_ko if x["id"]==int(src[1:])),None)
        return ko_loser(m) or "TBD" if m else "TBD"
    if src.startswith("3rd-"):
        return resolve_3rd(src[4:], top8)
    return "TBD"

def describe_source(src):
    """Human-readable source description for bracket display."""
    if not src: return "TBD"
    if len(src)==2 and src[0].isdigit() and src[1] in GROUP_LABELS:
        ord_pl = {"1":"1.","2":"2.","3":"3."}
        return f"{ord_pl.get(src[0],src[0])} Gr. {src[1]}"
    if src.startswith("W"): return f"Zwycięzca M{src[1:]}"
    if src.startswith("L"): return f"Przegrany M{src[1:]}"
    if src.startswith("3rd-"):
        return "3. msc. " + "/".join(list(src[4:]))
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

def eff_teams(m, resolved):
    r = resolved.get(m["id"],{})
    ta = r.get("team_a") or m.get("team_a") or "TBD"
    tb = r.get("team_b") or m.get("team_b") or "TBD"
    return ta, tb

def bracket_team(m, resolved, side):
    """Team name for bracket: resolved name if known, else source description."""
    r = resolved.get(m["id"],{})
    key = "team_a" if side=="a" else "team_b"
    src_key = "team_a_source" if side=="a" else "team_b_source"
    name = r.get(key) or m.get(key)
    if name and name != "TBD": return name, False
    return describe_source(m.get(src_key,"")), True

# ── Extra bets deadline ───────────────────────────────────────────────────────

def extra_deadline(matches):
    gm = [m for m in matches if m.get("stage")=="group"]
    if not gm: return False, "", None
    earliest = min(gm, key=lambda m: f"{m.get('date','9999')} {m.get('time','99:99')}")
    ko = match_kickoff(earliest)
    if not ko: return False, "", None
    now = datetime.now()
    if now>=ko: return True, f"🔒 Zamknięte od {earliest['date']} {earliest['time']}", ko
    cd = countdown_str(earliest)
    return False, f"Zamknięcie typów dodatkowych: {cd}", ko

# ── Points ────────────────────────────────────────────────────────────────────

def all_points(matches, bets, extra_bets, extra_results, resolved):
    pts = {}
    for m in matches:
        if not m["finished"]: continue
        mid = str(m["id"])
        ra, rb = m["real_score_a"], m["real_score_b"]
        for user, ub in bets.items():
            if mid in ub:
                b = ub[mid]
                confirmed = b.get("confirmed", True)
                if confirmed and b.get("score_a") is not None and b.get("score_b") is not None:
                    pts[user] = pts.get(user,0) + calc_pts(b["score_a"],b["score_b"],ra,rb)
    for user, ub in extra_bets.items():
        for key in EXTRA_KEYS:
            act = (extra_results.get(key) or "").strip().lower()
            guess = (ub.get(key) or "").strip().lower()
            if act and guess and act==guess:
                pts[user] = pts.get(user,0) + 20
    return pts

# ── Session state ─────────────────────────────────────────────────────────────

for k,v in [("logged_in",False),("username",None),("admin_auth",False)]:
    if k not in st.session_state: st.session_state[k]=v

# ═══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════════════════════════════

def show_login():
    st.markdown(
        "<div style='text-align:center;padding:3rem 0 1rem'>"
        "<span style='font-size:4rem'>⚽</span>"
        "<h1 style='margin:0;font-size:2.4rem'>Mistrzostwa Świata 2026</h1>"
        "<p style='color:#888;margin-top:.4rem'>System typowania meczów</p></div>",
        unsafe_allow_html=True)
    _,col,_ = st.columns([1,1.5,1])
    with col:
        st.markdown("### 🔐 Logowanie")
        users = load_json(USERS_FILE,{})
        name = st.selectbox("Imię",["-- wybierz --"]+sorted(users.keys()))
        pin  = st.text_input("PIN (4 cyfry)",type="password",max_chars=4)
        if st.button("Zaloguj się",use_container_width=True,type="primary"):
            if name=="-- wybierz --": st.error("Wybierz imię.")
            elif not pin: st.error("Wprowadź PIN.")
            elif users.get(name)==pin:
                st.session_state.logged_in=True; st.session_state.username=name; st.rerun()
            else: st.error("❌ Nieprawidłowy PIN.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 – OBSTAWIANIE (per-match checkbox)
# ═══════════════════════════════════════════════════════════════════════════════

def _match_header(m, ta, tb, extra=""):
    g = m.get("group",""); stage = m.get("stage","group"); rnd = m.get("round")
    lbl = STAGE_LABELS.get(stage, f"Gr. {g}") if stage!="group" else f"Gr. {g}"
    if rnd: lbl += f" · K{rnd}"
    cd = countdown_str(m) if not m["finished"] and not is_locked(m)[0] else ""
    html = (f"<div style='background:#1e2a3a;border-radius:10px;padding:10px 14px;margin-bottom:4px'>"
            f"<span style='color:#aaa;font-size:.78rem'>{lbl} · 🕐 {m.get('date','')} {m.get('time','')}")
    if cd: html += f" <span style='color:#3498db'>{cd}</span>"
    html += f"</span><br><b style='font-size:.95rem'>{ta} vs {tb}</b>"
    if extra: html += f"<br><span style='font-size:.78rem;color:#f39c12'>{extra}</span>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def tab_obstawianie(matches, resolved):
    st.header("🏟️ Obstawianie meczów")
    st.caption("Wpisz wynik i zaznacz ✅ **Zapisz typ** aby potwierdzić. Możesz edytować do momentu rozpoczęcia meczu.")

    username  = st.session_state.username
    bets      = load_json(BETS_FILE,{})
    user_bets = bets.get(username,{})

    # Separate finished
    active    = [m for m in matches if not m["finished"]]
    finished  = [m for m in matches if m["finished"]]

    if not active:
        st.info("Wszystkie mecze zakończone.")
    else:
        # Group by stage / group label for display
        group_active = [m for m in active if m.get("stage")=="group"]
        ko_active    = [m for m in active if m.get("stage") in KNOCKOUT_STAGES]

        def render_match_section(section_matches, header):
            if not section_matches: return
            st.markdown(f"#### {header}")
            for m in section_matches:
                mid   = str(m["id"])
                ta,tb = eff_teams(m,resolved)
                locked, lmsg = is_locked(m)
                existing = user_bets.get(mid,{})
                confirmed = existing.get("confirmed", True if (existing.get("score_a") is not None and "confirmed" not in existing) else False)

                key_a = f"bet_a_{mid}"; key_b = f"bet_b_{mid}"

                if locked:
                    # Locked: show status only
                    has_bet = existing.get("score_a") is not None and confirmed
                    if has_bet:
                        bet_d = f"<b style='color:#2ecc71'>Twój typ: {existing['score_a']}:{existing['score_b']} ✅</b>"
                    else:
                        bet_d = "<span style='color:#e74c3c'>Brak zapisanego typu</span>"
                    st.markdown(
                        f"<div style='background:#1a1a2e;border:1px solid #2a2a4a;border-radius:10px;"
                        f"padding:10px 14px;margin-bottom:8px'>"
                        f"<span style='color:#aaa;font-size:.78rem'>"
                        f"{'Gr. '+m.get('group','') if m.get('stage')=='group' else STAGE_LABELS.get(m.get('stage',''),'?')} · "
                        f"{m.get('date','')} {m.get('time','')}</span><br>"
                        f"<b>{ta} vs {tb}</b> "
                        f"<span style='color:#e67e22;font-size:.82rem'>{lmsg}</span><br>{bet_d}</div>",
                        unsafe_allow_html=True)
                else:
                    # Open match
                    _match_header(m, ta, tb, lmsg)

                    if confirmed and existing.get("score_a") is not None:
                        # Show confirmed bet with edit option
                        col_d, col_e = st.columns([3,1])
                        with col_d:
                            st.markdown(
                                f"<div style='background:#1a3020;border-radius:8px;padding:8px 14px;"
                                f"font-size:.95rem'>✅ Zapisany typ: "
                                f"<b>{existing['score_a']}:{existing['score_b']}</b></div>",
                                unsafe_allow_html=True)
                        with col_e:
                            if st.button("✏️ Edytuj", key=f"edit_{mid}", use_container_width=True):
                                bets.setdefault(username,{})[mid] = {
                                    "score_a": existing["score_a"],
                                    "score_b": existing["score_b"],
                                    "confirmed": False
                                }
                                st.session_state[key_a] = existing["score_a"]
                                st.session_state[key_b] = existing["score_b"]
                                save_json(BETS_FILE, bets)
                                st.rerun()
                    else:
                        # Editable inputs + save checkbox
                        # Initialize session state
                        init_a = existing.get("score_a",0) or 0
                        init_b = existing.get("score_b",0) or 0
                        if key_a not in st.session_state: st.session_state[key_a] = init_a
                        if key_b not in st.session_state: st.session_state[key_b] = init_b

                        col1,col2,col3,col4 = st.columns([2,1,2,3])
                        with col1:
                            st.markdown(f"<div style='text-align:center;font-weight:bold;margin-bottom:4px'>{ta}</div>",unsafe_allow_html=True)
                            st.number_input("Gole A",min_value=0,max_value=20,key=key_a,label_visibility="collapsed")
                        with col2:
                            st.markdown("<div style='text-align:center;padding-top:30px;font-size:1.4rem;color:#888'>–</div>",unsafe_allow_html=True)
                        with col3:
                            st.markdown(f"<div style='text-align:center;font-weight:bold;margin-bottom:4px'>{tb}</div>",unsafe_allow_html=True)
                            st.number_input("Gole B",min_value=0,max_value=20,key=key_b,label_visibility="collapsed")
                        with col4:
                            st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
                            save_now = st.checkbox("✅ Zapisz typ", value=False, key=f"chk_{mid}")
                            st.markdown("</div>", unsafe_allow_html=True)
                            if save_now:
                                sa_val = st.session_state.get(key_a, 0)
                                sb_val = st.session_state.get(key_b, 0)
                                locked2, _ = is_locked(m)
                                if locked2:
                                    st.warning("🔒 Mecz się właśnie zaczął!")
                                else:
                                    bets.setdefault(username,{})[mid] = {
                                        "score_a": sa_val,
                                        "score_b": sb_val,
                                        "confirmed": True
                                    }
                                    save_json(BETS_FILE, bets)
                                    st.rerun()

                    st.markdown("<div style='height:6px'></div>",unsafe_allow_html=True)

        # Organize by group for group stage
        st.markdown("#### 📅 Faza Grupowa")
        for g in GROUP_LABELS:
            grp_m = [m for m in group_active if m.get("group")==g]
            if not grp_m: continue
            with st.expander(f"Grupa {g} ({len(grp_m)} meczów)", expanded=True):
                render_match_section(grp_m, "")

        if ko_active:
            st.markdown("---")
            render_match_section(ko_active, "🏆 Faza Pucharowa")

    # ── Finished ──────────────────────────────────────────────────────────────
    if finished:
        st.markdown("---")
        st.markdown("#### ✅ Zakończone mecze")
        for m in finished:
            mid = str(m["id"]); ex = user_bets.get(mid,{})
            ta,tb = eff_teams(m,resolved)
            ra,rb = m["real_score_a"],m["real_score_b"]
            pw = m.get("penalties_winner")
            pw_n = f" (karne: {pw})" if pw else ""
            confirmed = ex.get("confirmed",True)
            if ex.get("score_a") is not None and confirmed:
                pts = calc_pts(ex["score_a"],ex["score_b"],ra,rb)
                cc = "#2ecc71" if pts==5 else "#f39c12" if pts==2 else "#e74c3c"
                bdg = "🎯 Dokładny!" if pts==5 else "✓ Dobry wynik" if pts==2 else "✗ Pudło"
                st.markdown(
                    f"<div style='background:#1e2a3a;border-radius:10px;padding:10px 14px;margin-bottom:6px;"
                    f"display:flex;justify-content:space-between;align-items:center'>"
                    f"<div><b>{ta} vs {tb}</b><br>"
                    f"<span style='color:#aaa;font-size:.82rem'>Wynik: {ra}:{rb}{pw_n} · Typ: {ex['score_a']}:{ex['score_b']}</span></div>"
                    f"<div style='color:{cc};font-weight:bold'>{bdg} +{pts}</div></div>",
                    unsafe_allow_html=True)
            else:
                reason = "" if ex.get("score_a") is None else " (niezapisany typ)"
                st.markdown(
                    f"<div style='background:#1e2a3a;border-radius:10px;padding:10px 14px;margin-bottom:6px'>"
                    f"<b>{ta} vs {tb}</b> · {ra}:{rb}{pw_n}"
                    f"<span style='color:#e74c3c;margin-left:10px'>Brak punktów{reason}</span></div>",
                    unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 – TYPY DODATKOWE
# ═══════════════════════════════════════════════════════════════════════════════

def tab_extra(matches):
    st.header("🏆 Typy Dodatkowe")
    username   = st.session_state.username
    extra_bets = load_json(EXTRA_BETS_FILE,{})
    user_extra = extra_bets.get(username,{})
    extra_res  = load_json(EXTRA_RESULTS_FILE,{})
    locked, dl_msg, _ = extra_deadline(matches)

    if locked: st.error(dl_msg)
    else: st.info(f"**Każdy trafiony typ dodatkowy = +20 pkt.** {dl_msg}")

    with st.form("extra_form"):
        c1,c2 = st.columns(2)
        inputs = {}
        for i,k in enumerate(EXTRA_KEYS):
            with (c1 if i%2==0 else c2):
                actual = extra_res.get(k)
                suffix = ""
                if actual:
                    ok = (user_extra.get(k,"").strip().lower()==actual.strip().lower())
                    suffix = " ✅ +20pkt" if ok else f" (wynik: {actual})"
                st.markdown(f"##### {EXTRA_LABELS[k]}")
                inputs[k] = st.text_input(
                    EXTRA_LABELS[k]+suffix, value=user_extra.get(k,""),
                    placeholder=EXTRA_PH[k], key=f"ex_{k}",
                    disabled=locked, label_visibility="collapsed")
        st.markdown("---")
        if st.form_submit_button("💾 Zapisz typy dodatkowe",use_container_width=True,
                                  type="primary",disabled=locked):
            extra_bets[username] = {k:v.strip() for k,v in inputs.items()}
            save_json(EXTRA_BETS_FILE, extra_bets)
            st.success("✅ Zapisano!"); st.rerun()

    if any(user_extra.values()):
        st.markdown("---"); st.markdown("##### 📋 Twoje aktualne typy")
        c1,c2 = st.columns(2)
        for i,k in enumerate(EXTRA_KEYS):
            val = user_extra.get(k) or "—"; actual = extra_res.get(k)
            if actual:
                ok = val.strip().lower()==actual.strip().lower()
                badge,note = (" ✅",f"<br><span style='font-size:.75rem;color:#aaa'>Wynik: {actual}</span>") if ok else (" ❌",f"<br><span style='font-size:.75rem;color:#aaa'>Wynik: {actual}</span>")
            else: badge,note = "",""
            with (c1 if i%2==0 else c2):
                st.markdown(
                    f"<div style='background:#1e2a3a;border-radius:10px;padding:12px 16px;margin-bottom:8px'>"
                    f"<div style='color:#aaa;font-size:.82rem'>{EXTRA_LABELS[k]}</div>"
                    f"<div style='font-weight:bold;margin-top:4px'>{val}{badge}</div>{note}</div>",
                    unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 – TABELE GRUPOWE
# ═══════════════════════════════════════════════════════════════════════════════

def _pbadge(p): return {1:"🥇",2:"🥈",3:"🔵",4:"⬛"}.get(p,str(p))

def tab_grupy(matches, standings):
    st.header("📋 Tabele Grupowe")
    fin_g = sum(1 for m in matches if m["finished"] and m.get("stage")=="group")
    tot_g = sum(1 for m in matches if m.get("stage")=="group")
    st.caption(f"Rozegrano **{fin_g}/{tot_g}** meczów fazy grupowej. 🥇🥈 = awans bezpośredni · 🔵 = możliwy awans (najlepsze 3. miejsce) · ⬛ = odpadają")

    # ── 3rd place ranking (prominent) ────────────────────────────────────────
    all3 = get_3rd_sorted(standings)
    has_data = any(r["M"]>0 for r in all3)
    st.markdown("---")
    st.markdown("### 🏅 Tabela Drużyn z 3. Miejsca")
    st.caption("Top 8 awansuje do 1/32 finału jako najlepsze 3. miejsca.")
    if not has_data:
        st.info("Brak wyników — tabela zaktualizuje się po rozegraniu meczów.")
    else:
        # Header
        st.markdown(
            "<div style='display:grid;grid-template-columns:2rem 1rem 1fr repeat(8,2.5rem);gap:4px;"
            "font-size:.78rem;color:#888;padding:4px 8px;border-bottom:1px solid #2a3a5a;'>"
            "<span>#</span><span>Gr</span><span>Drużyna</span>"
            "<span style='text-align:center'>M</span><span style='text-align:center'>W</span>"
            "<span style='text-align:center'>R</span><span style='text-align:center'>P</span>"
            "<span style='text-align:center'>GZ</span><span style='text-align:center'>GS</span>"
            "<span style='text-align:center'>B</span>"
            "<span style='text-align:center;color:#f1c40f;font-weight:bold'>Pkt</span></div>",
            unsafe_allow_html=True)
        for i,r in enumerate(all3):
            adv = i<8; bg = "#162038" if adv else "#1e1e2e"
            gd = f"+{r['B']}" if r['B']>0 else str(r['B'])
            adv_badge = "✅" if adv else "❌"
            st.markdown(
                f"<div style='display:grid;grid-template-columns:2rem 1rem 1fr repeat(8,2.5rem);gap:4px;"
                f"background:{bg};border-radius:8px;padding:7px 8px;margin:2px 0;align-items:center;font-size:.82rem'>"
                f"<span>{adv_badge} <b>#{i+1}</b></span><span style='color:#f1c40f'>{r['group']}</span>"
                f"<span>{r['Drużyna']}</span>"
                f"<span style='text-align:center'>{r['M']}</span>"
                f"<span style='text-align:center;color:#2ecc71'>{r['W']}</span>"
                f"<span style='text-align:center'>{r['R']}</span>"
                f"<span style='text-align:center;color:#e74c3c'>{r['P']}</span>"
                f"<span style='text-align:center'>{r['GZ']}</span>"
                f"<span style='text-align:center'>{r['GS']}</span>"
                f"<span style='text-align:center;color:#aaa'>{gd}</span>"
                f"<span style='text-align:center;font-weight:bold;color:#f1c40f'>{r['Pkt']}</span></div>",
                unsafe_allow_html=True)

    # ── Group tables ──────────────────────────────────────────────────────────
    st.markdown("---"); st.markdown("### 📊 Tabele Grup A–L")
    for g in GROUP_LABELS:
        rows = standings.get(g,[])
        if not rows: continue
        gm = [m for m in matches if m.get("group")==g]
        played = sum(1 for m in gm if m["finished"])
        total  = len(gm)

        st.markdown(
            f"<div style='background:#1a2540;border-radius:14px;padding:18px 20px;margin-bottom:18px'>",
            unsafe_allow_html=True)
        col_h, col_p = st.columns([5,1])
        with col_h: st.markdown(f"<h3 style='margin:0;color:#f1c40f'>Grupa {g}</h3>",unsafe_allow_html=True)
        with col_p: st.markdown(f"<div style='color:#888;text-align:right;padding-top:8px'>{played}/{total}</div>",unsafe_allow_html=True)

        # Table header
        st.markdown(
            "<div style='display:grid;grid-template-columns:2rem 1fr repeat(8,3rem);gap:4px;"
            "font-size:.8rem;color:#888;padding:0 4px 6px;border-bottom:1px solid #2a3a5a'>"
            "<span>#</span><span>Drużyna</span>"
            "<span style='text-align:center'>M</span><span style='text-align:center'>W</span>"
            "<span style='text-align:center'>R</span><span style='text-align:center'>P</span>"
            "<span style='text-align:center'>GZ</span><span style='text-align:center'>GS</span>"
            "<span style='text-align:center'>B</span>"
            "<span style='text-align:center;color:#f1c40f;font-weight:bold'>Pkt</span></div>",
            unsafe_allow_html=True)

        for r in rows:
            pos=r["pos"]; bg=("#162038" if pos<=2 else "#1a2030" if pos==3 else "#1e1e2e")
            gd=f"+{r['B']}" if r['B']>0 else str(r['B'])
            pk=f"<span style='color:#f1c40f;font-weight:bold'>{r['Pkt']}</span>" if r['Pkt']>0 else str(r['Pkt'])
            st.markdown(
                f"<div style='display:grid;grid-template-columns:2rem 1fr repeat(8,3rem);gap:4px;"
                f"background:{bg};border-radius:8px;padding:7px 4px;margin:2px 0;align-items:center'>"
                f"<span style='font-size:1rem'>{_pbadge(pos)}</span>"
                f"<span style='font-size:.9rem;font-weight:500'>{r['Drużyna']}</span>"
                f"<span style='text-align:center;font-size:.88rem'>{r['M']}</span>"
                f"<span style='text-align:center;color:#2ecc71;font-size:.88rem'>{r['W']}</span>"
                f"<span style='text-align:center;font-size:.88rem'>{r['R']}</span>"
                f"<span style='text-align:center;color:#e74c3c;font-size:.88rem'>{r['P']}</span>"
                f"<span style='text-align:center;font-size:.88rem'>{r['GZ']}</span>"
                f"<span style='text-align:center;font-size:.88rem'>{r['GS']}</span>"
                f"<span style='text-align:center;color:#aaa;font-size:.88rem'>{gd}</span>"
                f"<span style='text-align:center;font-size:.88rem'>{pk}</span></div>",
                unsafe_allow_html=True)

        with st.expander("Mecze grupy"):
            for m in sorted(gm, key=lambda x: f"{x['date']} {x.get('time','')}"):
                rnd=m.get("round"); rl=f"K{rnd} · " if rnd else ""
                if m["finished"]:
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;padding:4px 0;"
                        f"border-bottom:1px solid #2a3050;font-size:.85rem'>"
                        f"<span style='color:#888'>{rl}{m['date']}</span>"
                        f"<span><b>{m['team_a']}</b> <b style='color:#f1c40f'>{m['real_score_a']}:{m['real_score_b']}</b> <b>{m['team_b']}</b></span></div>",
                        unsafe_allow_html=True)
                else:
                    lk,_=is_locked(m); ic="🔒" if lk else "📅"
                    cd=countdown_str(m) if not lk else ""
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;padding:4px 0;"
                        f"border-bottom:1px solid #2a3050;font-size:.85rem;color:#888'>"
                        f"<span>{rl}{m['date']} {m.get('time','')}</span>"
                        f"<span>{ic} {m['team_a']} – {m['team_b']} {cd}</span></div>",
                        unsafe_allow_html=True)
        st.markdown("</div>",unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 – DRABINKA
# ═══════════════════════════════════════════════════════════════════════════════

def _ko_card(m, resolved, user_bets):
    mid = str(m["id"])
    ta_name, ta_tbd = bracket_team(m, resolved, "a")
    tb_name, tb_tbd = bracket_team(m, resolved, "b")
    mn = m["id"]

    if m["finished"]:
        ra,rb = m["real_score_a"],m["real_score_b"]
        pw = m.get("penalties_winner")
        pw_n = f"<br><span style='font-size:.72rem;color:#f39c12'>Karne: {pw}</span>" if pw else ""
        w = ko_winner(m)
        ta_s = "color:#f1c40f;font-weight:bold" if ta_name==w else "color:#aaa"
        tb_s = "color:#f1c40f;font-weight:bold" if tb_name==w else "color:#aaa"
        ub = user_bets.get(mid,{}); pts_str=""
        confirmed = ub.get("confirmed",True)
        if ub.get("score_a") is not None and confirmed:
            pts=calc_pts(ub["score_a"],ub["score_b"],ra,rb)
            cc="#2ecc71" if pts==5 else "#f39c12" if pts==2 else "#e74c3c"
            pts_str=f"<span style='color:{cc};font-size:.72rem;float:right'>+{pts} pkt</span>"
        st.markdown(
            f"<div style='background:#1a2540;border-radius:10px;padding:10px 12px;margin:4px 0'>"
            f"<div style='color:#888;font-size:.72rem'>M{mn} · {m.get('stadium','')} · {m['date']}</div>"
            f"<div style='display:grid;grid-template-columns:1fr auto 1fr;align-items:center;margin-top:6px;gap:4px'>"
            f"<span style='{ta_s};font-size:.88rem'>{ta_name}</span>"
            f"<span style='text-align:center;font-weight:bold;font-size:1.1rem;padding:0 6px'>{ra}:{rb}</span>"
            f"<span style='{tb_s};font-size:.88rem;text-align:right'>{tb_name}</span>"
            f"</div>{pw_n}{pts_str}</div>",
            unsafe_allow_html=True)
    else:
        locked,lmsg=is_locked(m); cd=countdown_str(m) if not locked else ""
        sc = "#e67e22" if locked else "#3498db"; st_txt = lmsg if locked else cd
        ta_color = "#ccc" if not ta_tbd else "#888"
        tb_color = "#ccc" if not tb_tbd else "#888"
        ub = user_bets.get(mid,{}); confirmed = ub.get("confirmed",True)
        bet_d = f"Typ: {ub['score_a']}:{ub['score_b']}" if ub.get("score_a") is not None and confirmed else ""
        src_a = m.get("team_a_source",""); src_b = m.get("team_b_source","")
        sub_a = f"<br><span style='font-size:.68rem;color:#666'>{describe_source(src_a)}</span>" if ta_tbd else ""
        sub_b = f"<br><span style='font-size:.68rem;color:#666'>{describe_source(src_b)}</span>" if tb_tbd else ""
        st.markdown(
            f"<div style='background:#1a2030;border-radius:10px;padding:10px 12px;margin:4px 0;opacity:.9'>"
            f"<div style='color:#888;font-size:.72rem'>M{mn} · {m.get('stadium','')} · {m.get('date','')} {m.get('time','')}</div>"
            f"<div style='display:grid;grid-template-columns:1fr auto 1fr;align-items:center;margin-top:6px;gap:4px'>"
            f"<span style='font-size:.88rem;color:{ta_color}'>{ta_name}{sub_a}</span>"
            f"<span style='text-align:center;color:#555;padding:0 6px'>vs</span>"
            f"<span style='font-size:.88rem;color:{tb_color};text-align:right'>{tb_name}{sub_b}</span>"
            f"</div>"
            f"<div style='color:{sc};font-size:.72rem;margin-top:4px'>{st_txt}"
            f"{'  · '+bet_d if bet_d else ''}</div></div>",
            unsafe_allow_html=True)

def tab_drabinka(matches, resolved):
    st.header("🏆 Drabinka Fazy Pucharowej")
    st.caption("Szara czcionka = drużyna jeszcze nieznana — pokazana jest potencjalna ścieżka awansu.")
    bets = load_json(BETS_FILE,{}); ub = bets.get(st.session_state.username,{})

    for stage_key in KNOCKOUT_STAGE_ORDER:
        seg = [m for m in matches if m.get("stage")==stage_key]
        if not seg: continue
        fin = sum(1 for m in seg if m["finished"])
        st.markdown(
            f"<div style='background:#0f1a2e;border-left:4px solid #f1c40f;"
            f"padding:8px 16px;margin:18px 0 8px;border-radius:0 8px 8px 0'>"
            f"<b style='color:#f1c40f'>{STAGE_LABELS.get(stage_key,stage_key)}</b>"
            f"<span style='color:#888;font-size:.85rem;margin-left:10px'>{fin}/{len(seg)} zakończonych</span></div>",
            unsafe_allow_html=True)
        cols_n = 2 if stage_key in ("1/32","1/16","1/8") else (2 if stage_key=="1/4" else 1)
        cols = st.columns(cols_n)
        for i,m in enumerate(seg):
            with cols[i%cols_n]: _ko_card(m, resolved, ub)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 – RANKING
# ═══════════════════════════════════════════════════════════════════════════════

def tab_ranking(matches, resolved):
    st.header("📊 Ranking Typerów")
    bets       = load_json(BETS_FILE,{})
    extra_bets = load_json(EXTRA_BETS_FILE,{})
    extra_res  = load_json(EXTRA_RESULTS_FILE,{})
    users      = load_json(USERS_FILE,{})
    pts        = all_points(matches,bets,extra_bets,extra_res,resolved)

    # Prize pool
    n_users = len(users)
    prize   = n_users * 10
    fin_c   = sum(1 for m in matches if m["finished"])

    c1,c2,c3,c4 = st.columns(4)
    with c1: st.metric("Zakończone mecze", f"{fin_c}/{len(matches)}")
    with c2: st.metric("Liczba typerów", n_users)
    with c3: st.metric("Najwyższy wynik", f"{max(pts.values(),default=0)} pkt")
    with c4:
        st.markdown(
            f"<div style='background:#1a3020;border-radius:10px;padding:14px;text-align:center'>"
            f"<div style='color:#aaa;font-size:.85rem'>🏆 Nagroda Główna</div>"
            f"<div style='font-size:1.8rem;font-weight:bold;color:#f1c40f'>{prize} zł</div>"
            f"<div style='color:#888;font-size:.75rem'>{n_users} typerów × 10 zł</div></div>",
            unsafe_allow_html=True)

    st.markdown("---")
    if fin_c==0:
        st.info("⏳ Ranking pojawi się po rozegraniu pierwszych meczów.")

    ranking = sorted(users.keys(), key=lambda u: pts.get(u,0), reverse=True)
    medals  = ["🥇","🥈","🥉"]

    for pos, user in enumerate(ranking,1):
        p    = pts.get(user,0)
        medal= medals[pos-1] if pos<=3 else f"#{pos}"
        me   = user==st.session_state.username
        bg   = "#1e3a2a" if me else "#1e2a3a"
        bord = "2px solid #2ecc71" if me else "none"
        me_l = " <span style='color:#2ecc71;font-size:.78rem'>(Ty)</span>" if me else ""

        ub = bets.get(user,{}); exact=outcome=0
        for m in matches:
            if not m["finished"]: continue
            mid=str(m["id"])
            if mid in ub:
                b = ub[mid]; confirmed = b.get("confirmed",True)
                if confirmed and b.get("score_a") is not None:
                    pp=calc_pts(b["score_a"],b["score_b"],m["real_score_a"],m["real_score_b"])
                    if pp==5: exact+=1
                    elif pp==2: outcome+=1
        ue = extra_bets.get(user,{})
        extra_hits = sum(1 for k in EXTRA_KEYS
                         if (extra_res.get(k) or "").strip().lower()==(ue.get(k) or "").strip().lower()
                         and extra_res.get(k))
        ep = extra_hits*20
        st.markdown(
            f"<div style='background:{bg};border:{bord};border-radius:12px;"
            f"padding:14px 20px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center'>"
            f"<div style='display:flex;align-items:center;gap:14px'>"
            f"<span style='font-size:1.6rem'>{medal}</span>"
            f"<div><b style='font-size:1.05rem'>{user}{me_l}</b><br>"
            f"<span style='color:#aaa;font-size:.8rem'>🎯 {exact} dokł. · ✓ {outcome} wyniki"
            f"{f' · 🏆 {ep} extra ({extra_hits}×20)' if ep else ''}</span></div></div>"
            f"<div style='font-size:1.6rem;font-weight:bold;color:#f1c40f'>{p}"
            f" <span style='font-size:.9rem;color:#aaa'>pkt</span></div></div>",
            unsafe_allow_html=True)

    if extra_bets:
        st.markdown("---"); st.markdown("### 🎯 Typy Dodatkowe")
        import pandas as pd
        df = []
        for u in sorted(users.keys()):
            ue = extra_bets.get(u,{}); row={"Uczestnik":u}
            for k in EXTRA_KEYS:
                val=ue.get(k) or "—"; act=extra_res.get(k)
                if act:
                    ok=val.strip().lower()==act.strip().lower()
                    val += " ✅" if ok else " ❌"
                row[EXTRA_LABELS[k]]=val
            df.append(row)
        st.dataframe(pd.DataFrame(df),use_container_width=True,hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6 – PANEL ADMINISTRATORA
# ═══════════════════════════════════════════════════════════════════════════════

def tab_admin(matches, resolved):
    st.header("🔧 Panel Administratora")
    if not st.session_state.admin_auth:
        pin_in = st.text_input("PIN Administratora",type="password",max_chars=4,key="admin_pin")
        if st.button("Zaloguj",type="primary"):
            if pin_in==ADMIN_PIN: st.session_state.admin_auth=True; st.rerun()
            else: st.error("❌ Zły PIN.")
        return
    st.success("✅ Zalogowany jako administrator.")

    # ── Wyniki meczów (ORDERED: group, then 1/32, 1/16, 1/8, 1/4, 3M, FINAL) ─
    st.markdown("---"); st.markdown("### ⚽ Wprowadź wyniki meczów")
    st.caption("Zaznacz 'Zakończony' i kliknij Zapisz → punkty przeliczają się natychmiast.")

    stage_order = ["group"] + KNOCKOUT_STAGE_ORDER
    stage_display = {"group":"Faza Grupowa", **STAGE_LABELS}

    for stage_key in stage_order:
        if stage_key == "group":
            seg = [m for m in matches if m.get("stage")=="group" and not m["finished"]]
        else:
            seg = [m for m in matches if m.get("stage")==stage_key and not m["finished"]]
        if not seg: continue

        with st.expander(f"**{stage_display.get(stage_key,stage_key)}** — {len(seg)} do wpisania",
                         expanded=(stage_key=="group")):
            with st.form(f"res_{stage_key}"):
                res_data, fin_flags, pen_flags = {}, {}, {}

                for m in seg:
                    mid = str(m["id"])
                    ta, tb = eff_teams(m, resolved)
                    lk,_ = is_locked(m); lk_ic = "🔒 " if lk else ""
                    rnd=m.get("round"); rl=f"K{rnd} · " if rnd else ""
                    st.markdown(
                        f"<div style='background:#1e2a3a;border-radius:8px;padding:8px 14px;margin-bottom:4px'>"
                        f"<b>{lk_ic}M{m['id']} · {ta} vs {tb}</b> "
                        f"<span style='color:#aaa;font-size:.82rem'>· {rl}{m.get('date','')} {m.get('time','')} · {m.get('stadium','')}</span></div>",
                        unsafe_allow_html=True)

                    c1,c2,c3,c4,c5 = st.columns([2,1,2,2,2])
                    with c1:
                        sa = st.number_input(ta,min_value=0,max_value=30,value=0,
                                             key=f"adm_a_{mid}",label_visibility="collapsed")
                    with c2:
                        st.markdown("<div style='text-align:center;padding-top:8px;color:#888'>–</div>",unsafe_allow_html=True)
                    with c3:
                        sb = st.number_input(tb,min_value=0,max_value=30,value=0,
                                             key=f"adm_b_{mid}",label_visibility="collapsed")
                    with c4:
                        fin_flags[mid] = st.checkbox("Zakończony",key=f"adm_fin_{mid}")
                    with c5:
                        if stage_key != "group":
                            pen_opt = ["—", ta, tb] if ta!=tb else ["—", ta]
                            pen_flags[mid] = st.selectbox("Karne",pen_opt,key=f"adm_pen_{mid}")
                        else:
                            pen_flags[mid] = "—"
                    res_data[mid] = {"score_a": sa, "score_b": sb}

                if st.form_submit_button("💾 Zapisz wyniki",use_container_width=True,type="primary"):
                    # Always reload from file for a fresh state
                    current = load_json(MATCHES_FILE,[])
                    # Recompute resolution with fresh data
                    fresh_standings = build_standings(current)
                    fresh_top8 = get_3rd_top8(fresh_standings)
                    fresh_ko = [m for m in current if m.get("stage") in KNOCKOUT_STAGES]

                    changed = 0
                    for mc in current:
                        mid = str(mc["id"])
                        if fin_flags.get(mid) and not mc["finished"]:
                            mc["real_score_a"] = res_data[mid]["score_a"]
                            mc["real_score_b"] = res_data[mid]["score_b"]
                            mc["finished"] = True
                            pw = pen_flags.get(mid,"—")
                            mc["penalties_winner"] = pw if pw!="—" else None
                            # For knockout: store resolved team names so future W/L lookups work
                            if mc.get("team_a_source"):
                                ta_r = resolve_source(mc.get("team_a_source",""), fresh_standings, fresh_ko, fresh_top8)
                                tb_r = resolve_source(mc.get("team_b_source",""), fresh_standings, fresh_ko, fresh_top8)
                                if ta_r != "TBD": mc["team_a"] = ta_r
                                if tb_r != "TBD": mc["team_b"] = tb_r
                            changed += 1
                    if changed:
                        save_json(MATCHES_FILE, current)
                        st.success(f"✅ Zapisano {changed} wynik(ów) — punkty przeliczone."); st.rerun()
                    else:
                        st.warning("Nie zaznaczono żadnego meczu jako zakończonego.")

    # ── Zakończone ─────────────────────────────────────────────────────────────
    fin_list = [m for m in matches if m["finished"]]
    if fin_list:
        st.markdown("---"); st.markdown("### ✅ Zakończone mecze")
        for m in fin_list:
            ta,tb = eff_teams(m,resolved)
            pw = m.get("penalties_winner"); pw_n = f" (karne: {pw})" if pw else ""
            st.markdown(
                f"<div style='background:#1a3020;border-radius:8px;padding:8px 14px;margin-bottom:4px;"
                f"display:flex;justify-content:space-between'>"
                f"<span><b>{ta} vs {tb}</b> <span style='color:#aaa;font-size:.82rem'>"
                f"· {STAGE_LABELS.get(m.get('stage',''),'?')} · {m.get('date','')}</span></span>"
                f"<span style='color:#2ecc71;font-weight:bold'>{m['real_score_a']}:{m['real_score_b']}{pw_n}</span></div>",
                unsafe_allow_html=True)

    # ── Wyniki typów dodatkowych ───────────────────────────────────────────────
    st.markdown("---"); st.markdown("### 🏆 Wyniki typów dodatkowych")
    st.caption("Wpisz rzeczywistych zwycięzców — gracze z trafionym typem dostają automatycznie +20 pkt.")
    extra_res = load_json(EXTRA_RESULTS_FILE,{})
    with st.form("extra_res_form"):
        c1,c2 = st.columns(2)
        er_in = {}
        for i,k in enumerate(EXTRA_KEYS):
            with (c1 if i%2==0 else c2):
                st.markdown(f"**{EXTRA_LABELS[k]}**")
                er_in[k] = st.text_input(EXTRA_LABELS[k],value=extra_res.get(k,""),
                                          placeholder=EXTRA_PH[k],key=f"er_{k}",label_visibility="collapsed")
        if st.form_submit_button("💾 Zapisz wyniki dodatkowe",use_container_width=True):
            save_json(EXTRA_RESULTS_FILE,{k:v.strip() for k,v in er_in.items()})
            st.success("✅ Zapisano."); st.rerun()

    # ── Dodaj mecz ─────────────────────────────────────────────────────────────
    st.markdown("---"); st.markdown("### ➕ Dodaj mecz")
    with st.form("add_match"):
        c1,c2,c3,c4 = st.columns([2,2,1.5,1.5])
        with c1: nta=st.text_input("Drużyna A",placeholder="np. Polska")
        with c2: ntb=st.text_input("Drużyna B",placeholder="np. Niemcy")
        with c3: ndt=st.date_input("Data")
        with c4: ntm=st.text_input("Godz.",value="21:00",max_chars=5)
        c5,c6=st.columns(2)
        with c5: ngr=st.text_input("Etap/Grupa",placeholder="A, 1/32, FINAL…")
        with c6: nrd=st.number_input("Kolejka (0=brak)",min_value=0,max_value=3,value=0)
        if st.form_submit_button("Dodaj",use_container_width=True):
            if nta.strip() and ntb.strip():
                nid=max((m["id"] for m in matches),default=0)+1
                stg=ngr.strip() if ngr.strip() in KNOCKOUT_STAGES else "group"
                matches.append({"id":nid,"team_a":nta.strip(),"team_b":ntb.strip(),
                                 "date":str(ndt),"time":ntm.strip() or "21:00",
                                 "group":ngr.strip(),"stage":stg,
                                 "round":int(nrd) if nrd else None,
                                 "real_score_a":None,"real_score_b":None,"finished":False})
                save_json(MATCHES_FILE,matches); st.success(f"Dodano: {nta} vs {ntb}"); st.rerun()
            else: st.error("Podaj obie drużyny.")

    # ── Usuń mecz ──────────────────────────────────────────────────────────────
    st.markdown("---"); st.markdown("### 🗑️ Usuń mecz")
    unfin=[m for m in matches if not m["finished"]]
    if unfin:
        labels=[f"M{m['id']} {eff_teams(m,resolved)[0]} vs {eff_teams(m,resolved)[1]} ({m.get('date','')})"
                for m in unfin]
        sel=st.selectbox("Mecz",["-- wybierz --"]+labels,key="del_m")
        if st.button("🗑️ Usuń",type="secondary"):
            if sel!="-- wybierz --":
                idx=labels.index(sel); del_id=unfin[idx]["id"]
                save_json(MATCHES_FILE,[m for m in matches if m["id"]!=del_id])
                st.success(f"Usunięto M{del_id}"); st.rerun()

    # ── Zarządzanie uczestnikami ───────────────────────────────────────────────
    st.markdown("---"); st.markdown("### 👥 Uczestnicy")
    users=load_json(USERS_FILE,{})
    bets_all=load_json(BETS_FILE,{})
    extra_bets_all=load_json(EXTRA_BETS_FILE,{})
    extra_res2=load_json(EXTRA_RESULTS_FILE,{})
    pts_all=all_points(matches,bets_all,extra_bets_all,extra_res2,resolved)

    c1,c2=st.columns(2)
    with c1:
        st.markdown("##### ➕ Dodaj uczestnika")
        with st.form("add_user"):
            nn=st.text_input("Imię"); np_=st.text_input("PIN (4 cyfry)",max_chars=4)
            if st.form_submit_button("Dodaj",use_container_width=True):
                if not nn.strip(): st.error("Podaj imię.")
                elif nn.strip() in users: st.error("Już istnieje.")
                elif not np_.isdigit() or len(np_)!=4: st.error("PIN = 4 cyfry.")
                else:
                    users[nn.strip()]=np_; save_json(USERS_FILE,users)
                    st.success(f"Dodano: {nn.strip()}"); st.rerun()
    with c2:
        st.markdown("##### 👤 Lista uczestników")
        for uname in sorted(users.keys()):
            cu,cp,cd_=st.columns([3,1,1])
            with cu:
                st.markdown(
                    f"<div style='background:#1e2a3a;border-radius:8px;padding:7px 12px;margin-bottom:4px;"
                    f"display:flex;justify-content:space-between'>"
                    f"<span>{uname}</span><span style='color:#f1c40f'>{pts_all.get(uname,0)} pkt</span></div>",
                    unsafe_allow_html=True)
            with cd_:
                if st.button("🗑️",key=f"del_u_{uname}",help=f"Usuń {uname}"):
                    del users[uname]; save_json(USERS_FILE,users)
                    st.success(f"Usunięto {uname}"); st.rerun()

    st.markdown("---")
    if st.button("🔒 Wyloguj z panelu admina"):
        st.session_state.admin_auth=False; st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    if not st.session_state.logged_in:
        show_login(); return

    username = st.session_state.username
    c1,c2 = st.columns([4,1])
    with c1: st.markdown("<h2 style='margin:0;padding-top:4px'>⚽ Typer MŚ 2026</h2>",unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div style='text-align:right;padding-top:8px;color:#aaa'>Zalogowany: <b>{username}</b></div>",unsafe_allow_html=True)
        if st.button("Wyloguj",use_container_width=True):
            for k in ["logged_in","username","admin_auth"]:
                st.session_state[k] = False if k!="username" else None
            st.rerun()
    st.markdown("---")

    matches   = load_json(MATCHES_FILE,[])
    standings = build_standings(matches)
    resolved  = resolve_ko_teams(matches,standings)

    t1,t2,t3,t4,t5,t6 = st.tabs([
        "🏟️ Obstawianie","🏆 Typy Dodatkowe","📋 Tabele Grupowe",
        "🎯 Drabinka","📊 Ranking","🔧 Admin"])
    with t1: tab_obstawianie(matches,resolved)
    with t2: tab_extra(matches)
    with t3: tab_grupy(matches,standings)
    with t4: tab_drabinka(matches,resolved)
    with t5: tab_ranking(matches,resolved)
    with t6: tab_admin(matches,resolved)


if __name__=="__main__":
    main()
