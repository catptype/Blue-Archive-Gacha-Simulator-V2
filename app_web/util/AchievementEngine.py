import json
import os
from typing import List
from django.conf import settings
from django.contrib.auth.models import User # Or your custom user model
from ..models import Achievement, UnlockAchievement, UserInventory, GachaTransaction, Student

# --- DATA LOADING (from your achievements.json file) ---
ACHIEVEMENT_DEFINITIONS = []
try:
    file_path = os.path.join(settings.BASE_DIR, 'app_web', 'management', 'data', 'json', 'achievements')
    with open(file_path, 'r') as f:
        ACHIEVEMENT_DEFINITIONS = json.load(f)
except Exception as e:
    print(f"WARNING: Could not load achievements.json. Achievements will be disabled. Error: {e}")

# --- =============================================================== ---
# --- CORE ACHIEVEMENT SERVICE                                        ---
# --- =============================================================== ---

class AchievementEngine:
    def _init_(self, user: User):
        if not user or not user.is_authenticated:
            raise ValueError("A valid, authenticated user is required.")
        self.user = user
        # This is a crucial optimization. We get all unlocked achievements once.
        self.unlocked_keys = set(
            UnlockAchievement.objects.filter(unlock_user=user).values_list('achievement__achievement_key', flat=True)
        )
    
    def _award(self, unlock_key: str):
        """
        A private helper to safely award an achievement if it's not already unlocked.
        """
        # 1. Check our in-memory set first. This is extremely fast.
        if unlock_key in self.unlocked_keys:
            return # User already has it.

        try:
            # 2. If they don't have it, get the achievement from the database.
            achievement_to_award = Achievement.objects.get(achievement_key=unlock_key)
            
            # 3. Award it.
            UnlockAchievement.objects.create(user=self.user, achievement=achievement_to_award)
            
            # 4. Update our in-memory set so we don't try to award it again in the same session.
            self.unlocked_keys.add(unlock_key)
            print(f"ACHIEVEMENT UNLOCKED for {self.user.username}: {achievement_to_award.achievement_name}")
            
            # You can add logic here to send a notification to the user.

        except Achievement.DoesNotExist:
            print(f"ERROR: Achievement with key '{unlock_key}' not found in DB.")

    # --- "RULE" METHODS, ORGANIZED BY CATEGORY ---

    def check_luck_achievements(self, pulled_students: List[Student]):
        """
        Checks for achievements related to a single gacha pull (e.g., multi-3-star).
        TRIGGER: Called from the pull_gacha view.
        """
        r3_count = sum(1 for student in pulled_students if student.student_rarity == 3)
        
        if r3_count >= 3:
            self._award('LUCK_TRIPLE_R3')
        elif r3_count == 2:
            self._award('LUCK_DOUBLE_R3')
    
    def check_collection_achievements(self):
        """
        Checks all collection-based achievements against the user's full inventory.
        TRIGGER: Called from a signal when the user's inventory changes.
        """
        collection_sets = [ach for ach in ACHIEVEMENT_DEFINITIONS if ach.get("category") == "COLLECTION"]
        
        owned_students = UserInventory.objects.filter(user=self.user).select_related('student__version')
        user_owned_set = {f"{item.student.student_name}|{item.student.version.version_name}" for item in owned_students}

        for ach_set in collection_sets:
            unlock_key = ach_set['key']
            if unlock_key not in self.unlocked_keys:
                required_students = ach_set.get('students', [])
                if all(f"{req['name']}|{req['version']}" in user_owned_set for req in required_students):
                    self._award(unlock_key)

    def check_milestone_achievements(self):
        """
        Checks for achievements related to overall account progression.
        TRIGGER: Called after a gacha pull is saved.
        """
        # Fetching the count here is acceptable as it's a single, fast query.
        total_pulls = GachaTransaction.objects.filter(user=self.user).count()
        
        if total_pulls >= 1000:
            self._award('MILESTONE_PULLS_1000')
        if total_pulls >= 100:
            self._award('MILESTONE_PULLS_100')
        if total_pulls >= 10:
            self._award('MILESTONE_PULLS_10')