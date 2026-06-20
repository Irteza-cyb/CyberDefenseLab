"""
achievements.py - Achievement / badge system
Cyber-Attack Simulator & Defense Lab
"""

ACHIEVEMENTS = {
"first_blood":      {"title": "First Blood",      "desc": "Complete your first round",              "icon": "[*]"},
"perfect_session":  {"title": "Perfect Session",  "desc": "Defend all 4 attacks in one session",   "icon": "[OK]"},
"speed_demon":      {"title": "Speed Demon",      "desc": "Answer correctly in under 5 seconds",   "icon": "[T]"},
"no_hints":         {"title": "No Crutches",      "desc": "Complete a session without any hints",  "icon": "[^]"},
"expert_cleared":   {"title": "Elite Defender",   "desc": "Complete a full Expert session",        "icon": "[E]"},
"century":          {"title": "Century Club",     "desc": "Reach 100 total score",                 "icon": "[C]"},
"high_scorer":      {"title": "High Scorer",      "desc": "Reach 500 total score",                 "icon": "[H]"},
"legend":           {"title": "Legend",           "desc": "Reach 1000 total score",                "icon": "[L]"},
"phish_hunter":     {"title": "Phish Hunter",     "desc": "Correctly identify 5 phishing attacks", "icon": "[~]"},
"firewall":         {"title": "The Firewall",     "desc": "Block 5 brute force attacks",           "icon": "[K]"},
"flood_control":    {"title": "Flood Control",    "desc": "Stop 5 DDoS attacks",                   "icon": "[W]"},
"sql_master":       {"title": "SQL Master",       "desc": "Fix 5 SQL injection vulnerabilities",   "icon": "[D]"},
"comeback":         {"title": "Comeback King",    "desc": "Score 100+ after a breach",             "icon": "[!]"},
"streak_3":         {"title": "On Fire",          "desc": "3 correct answers in a row",            "icon": "[3]"},
"streak_5":         {"title": "Unstoppable",      "desc": "5 correct answers in a row",            "icon": "[5]"},
}

def check_achievements(user_id, session_summary, db_stats, user):
"""
Compare session and lifetime stats against achievement criteria.
Returns a list of newly unlocked achievement keys.
"""
import database as db

```
already = set(db.get_user_achievements(user_id))
newly_unlocked = set()

round_log = session_summary.get("round_log", [])
passes = session_summary.get("passes", 0)
rounds = session_summary.get("rounds", 0)
final_score = session_summary.get("final_score", 0)
difficulty = session_summary.get("difficulty", "beginner")
hint_used = session_summary.get("hint_used_any", False)

total_score = user.get("total_score", 0)
best_streak = user.get("best_streak", 0)

def unlock(key):
    if key not in already:
        newly_unlocked.add(key)
        db.unlock_achievement(user_id, key)

# First round ever
if db_stats.get("total", 0) >= 1:
    unlock("first_blood")

# Perfect session
if rounds == 4 and passes == 4:
    unlock("perfect_session")

# Speed demon - any correct answer under 5 seconds
if any(
    r.get("result") == "pass" and r.get("time_taken", 99) <= 5
    for r in round_log
):
    unlock("speed_demon")

# Complete session without hints
if rounds == 4 and not hint_used:
    unlock("no_hints")

# Expert cleared
if difficulty == "expert" and rounds == 4 and passes == 4:
    unlock("expert_cleared")

# Score milestones
if total_score >= 100:
    unlock("century")

if total_score >= 500:
    unlock("high_scorer")

if total_score >= 1000:
    unlock("legend")

# Attack-specific achievements
attack_achievements = {
    "phishing": "phish_hunter",
    "bruteforce": "firewall",
    "ddos": "flood_control",
    "sqli": "sql_master",
}

for attack_type, achievement in attack_achievements.items():
    if db_stats.get(f"{attack_type}_wins", 0) >= 5:
        unlock(achievement)

# Comeback achievement
had_breach = any(
    r.get("result") == "breach"
    for r in round_log
)

if had_breach and final_score >= 100:
    unlock("comeback")

# Streak achievements
if best_streak >= 3:
    unlock("streak_3")

if best_streak >= 5:
    unlock("streak_5")

return sorted(newly_unlocked)
```
