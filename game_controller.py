"""
game_controller.py - Orchestrates game sessions using the full question bank.
Each session picks fresh, shuffled questions per difficulty level.
Cyber-Attack Simulator & Defense Lab
"""

import random
import time
import datetime
from typing import Optional, Dict, Any, List

import database as db
from score_manager import ScoreManager
import questions as Q


class GameController:
    ATTACKS_PER_SESSION = 4
    ATTACK_TYPES = ["phishing", "bruteforce", "ddos", "sqli"]

    def __init__(self, user_id: str, difficulty: str = "beginner"):
        self.user_id = user_id
        self.difficulty = difficulty
        self.is_daily = (difficulty == "daily")
        self.score_mgr = ScoreManager("daily" if self.is_daily else difficulty)

        self.attack_queue: List[Dict[str, Any]] = []  # list of question dicts
        self.current_index: int = 0
        self.round_start_time: Optional[float] = None
        self.hint_used_this_round: bool = False
        self.session_active: bool = False
        self._used_ids: List[str] = []  # track used question IDs this session

    # ── Session lifecycle ──────────────────────────────────────────────────────

    def start_session(self) -> None:
        """Pick one question per attack type, all unique, all matching difficulty."""
        self._used_ids = []
        selected = []

        # Shuffle order so attack types appear in random sequence
        types = self.ATTACK_TYPES[:]
        random.shuffle(types)

        question_difficulty = "intermediate" if self.is_daily else self.difficulty
        for atype in types:
            q = Q.get_question(atype, question_difficulty, exclude_ids=self._used_ids)
            if q:
                q["attack_type"] = atype  # ensure field present
                selected.append(q)
                self._used_ids.append(q["id"])

        self.attack_queue = selected[:self.ATTACKS_PER_SESSION]
        self.current_index = 0
        self.score_mgr.reset()
        self.session_active = True

    def session_complete(self) -> bool:
        """Check if all attacks in the session have been completed."""
        return self.current_index >= len(self.attack_queue)

    # ── Round lifecycle ────────────────────────────────────────────────────────

    def get_current_attack(self) -> Optional[Dict[str, Any]]:
        """Retrieve the current attack question."""
        if self.session_complete():
            return None
        return self.attack_queue[self.current_index]

    def start_round_timer(self) -> None:
        """Start the timer for the current round."""
        self.round_start_time = time.time()
        self.hint_used_this_round = False

    def elapsed_time(self) -> float:
        """Calculate time elapsed since the round started."""
        if self.round_start_time is None:
            return 0.0
        return time.time() - self.round_start_time

    def use_hint(self) -> bool:
        """Attempt to use a hint for the current round."""
        granted = self.score_mgr.use_hint()
        if granted:
            self.hint_used_this_round = True
        return granted

    # ── Answer submission ──────────────────────────────────────────────────────

    def submit_answer(self, answer: Any) -> Dict[str, Any]:
        """Process the user's answer and update scores/logs."""
        atk = self.get_current_attack()
        if not atk:
            return {
                "correct": False, "points": 0, "result": "error",
                "message": "No active round.", "explanation": ""
            }

        elapsed = self.elapsed_time()
        correct = self._validate(atk, answer)
        pts = self.score_mgr.apply_round(
            atk["attack_type"], correct, elapsed, self.hint_used_this_round
        )

        result_str = "pass" if correct else "fail"
        
        # Database updates
        db.save_session(self.user_id, atk["attack_type"], result_str,
                        pts, round(elapsed, 1), self.difficulty)
        db.add_log(self.user_id, atk["attack_type"], str(answer)[:120], result_str)
        db.update_user_score(self.user_id, pts)
        db.update_streak(self.user_id, correct)

        self.current_index += 1
        explain = atk.get("explanation", "")
        
        if correct:
            msg = f"[OK] DEFENSE SUCCESSFUL  +{pts} pts"
        else:
            msg = f"[!!] WRONG  {pts} pts  |  {explain}"

        return {
            "correct": correct, "points": pts, "result": result_str,
            "message": msg, "explanation": explain,
            "streak": self.score_mgr.current_streak
        }

    def submit_breach(self) -> None:
        """Handle a timeout or breach scenario."""
        atk = self.get_current_attack()
        if not atk:
            return
            
        self.score_mgr.apply_round(atk["attack_type"], False, 999, False, breach=True)
        db.save_session(self.user_id, atk["attack_type"], "breach", 0, 999, self.difficulty)
        db.add_log(self.user_id, atk["attack_type"], "TIMEOUT", "breach")
        db.update_streak(self.user_id, False)
        
        self.current_index += 1

    def save_daily_result(self) -> None:
        """Save the result of a daily challenge to the database."""
        today = datetime.date.today().isoformat()
        db.save_daily_challenge(
            self.user_id, today,
            self.score_mgr.session_score,
            self.session_complete()
        )

    # ── Validation ─────────────────────────────────────────────────────────────

    def _validate(self, atk: Dict[str, Any], answer: Any) -> bool:
        """Validate the submitted answer based on the attack type."""
        atype = atk["attack_type"]

        if atype == "phishing":
            return str(answer) == "malicious_link"

        elif atype == "bruteforce":
            correct_ip = atk.get("attacker_ip", atk.get("correct_answer", ""))
            return str(answer).strip() == correct_ip.strip()

        elif atype == "ddos":
            expected = self._ddos_expected(atk)
            if not isinstance(answer, dict):
                return False
            return all(answer.get(ip) == action for ip, action in expected.items())

        elif atype == "sqli":
            return str(answer) == "parameterized_queries"

        return False

    def _ddos_expected(self, atk: Dict[str, Any]) -> Dict[str, str]:
        """Build expected {ip: 'block'/'allow'} from the question's traffic list."""
        return {
            ip: ("block" if is_flood else "allow")
            for ip, _, is_flood in atk.get("traffic", [])
        }

    def get_ddos_entries(self) -> List[tuple]:
        """Return list of (ip, expected_action) for current DDoS round."""
        atk = self.get_current_attack()
        if atk and atk["attack_type"] == "ddos":
            return list(self._ddos_expected(atk).items())
        return []

    # ── Dashboard data ─────────────────────────────────────────────────────────

    def get_session_summary(self) -> Dict[str, Any]:
        """Generate a summary of the current session."""
        return {
            "final_score": self.score_mgr.session_score,
            "win_rate":    self.score_mgr.get_win_rate(),
            "rounds":      self.score_mgr.rounds_played,
            "passes":      self.score_mgr.rounds_passed,
            "round_log":   self.score_mgr.round_log,
            "difficulty":  self.difficulty,
            "hint_used_any": self.score_mgr.hint_used_any,
            "max_streak":  max((entry.get("streak", 0) for entry in self.score_mgr.round_log), default=0),
        }
