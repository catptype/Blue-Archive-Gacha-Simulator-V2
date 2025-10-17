import json
import os
from typing import List, Optional
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.models import User # Or your custom user model
from ..models import Achievement, UnlockAchievement, UserInventory, GachaTransaction, Student

# This dictionary will hold ONLY the data needed for collection checks.
# Format: { "unlock_key": [ { "name": "Student", "version": "Ver" }, ... ] }
COLLECTION_SETS = {}

try:
    achievements_dir = os.path.join(settings.BASE_DIR, 'app_web', 'management', 'data', 'json', 'achievements')

    if os.path.isdir(achievements_dir):
        for filename in os.listdir(achievements_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(achievements_dir, filename)
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        
                        # --- THE OPTIMIZATION ---
                        # We ONLY process and store the data if it's a COLLECTION achievement
                        # and has a 'students' list. All other types are ignored here.
                        if data.get("category") == "COLLECTION" and "students" in data:
                            COLLECTION_SETS[data["key"]] = data["students"]

                except (json.JSONDecodeError, KeyError) as e:
                    print(f"WARNING: Skipping achievement file {filename} due to parsing error: {e}")
    else:
        raise FileNotFoundError("Achievements directory not found.")

except FileNotFoundError:
    print(f"WARNING: Achievements directory not found. Collection achievements will be disabled.")
except Exception as e:
    print(f"CRITICAL ERROR loading achievement definitions: {e}")

# --- =============================================================== ---
# --- CORE ACHIEVEMENT SERVICE                                        ---
# --- =============================================================== ---

class AchievementEngine:
    def __init__(self, user: User):
        if not user or not user.is_authenticated:
            raise ValueError("A valid, authenticated user is required.")
        self.user = user
        # This is a crucial optimization. We get all unlocked achievements once.
        self.unlocked_keys = set(
            UnlockAchievement.objects.filter(unlock_user=user).values_list('achievement_id__achievement_key', flat=True)
        )

        # --- NEW: Define a specific cache key for this user's pull count ---
        self.pull_count_cache_key = f"user_pull_count:{self.user.id}"
    
    def _award(self, unlock_key: str) -> Optional[Achievement]:
        """
        A private helper to safely award an achievement if it's not already unlocked.
        """
        # 1. Check our in-memory set first. This is extremely fast.
        if unlock_key in self.unlocked_keys:
            return None # User already has it.

        try:
            # 2. If they don't have it, get the achievement from the database.
            achievement_to_award = Achievement.objects.get(achievement_key=unlock_key)
            
            # 3. Award it.
            UnlockAchievement.objects.create(unlock_user=self.user, achievement_id=achievement_to_award)
            
            # 4. Update our in-memory set so we don't try to award it again in the same session.
            self.unlocked_keys.add(unlock_key)
            print(f"ACHIEVEMENT UNLOCKED for {self.user.username}: {achievement_to_award.achievement_name}")
            
            # You can add logic here to send a notification to the user.
            return achievement_to_award

        except Achievement.DoesNotExist:
            print(f"ERROR: Achievement with key '{unlock_key}' not found in DB.")
            return None

    # --- NEW: A dedicated, cached method to get the total pull count ---
    def _get_total_pull_count(self) -> int:
        """
        Gets the total pull count for the user from the cache, or primes it from the DB.
        """
        count = cache.get(self.pull_count_cache_key)
        if count is None:
            count = GachaTransaction.objects.filter(transaction_user=self.user).count()
            cache.set(self.pull_count_cache_key, count, timeout=60)
        return count
    
    # --- "RULE" METHODS, ORGANIZED BY CATEGORY ---

    def check_luck_achievements(self, pulled_students: List[Student]) -> List[Achievement]:
        """
        Checks for achievements related to a single gacha pull (e.g., multi-3-star).
        TRIGGER: Called from the pull_gacha view.
        """
        newly_unlocked = []
        r3_count = sum(1 for student in pulled_students if student.student_rarity == 3)
        
        # --- THE LOGIC FIX ---
        # We use two separate 'if' statements instead of 'if/elif'.
        # This correctly awards the Double achievement even if the Triple is also awarded.
        if r3_count >= 2:
            achievement_obj = self._award('LUCK_DOUBLE_R3')
            if achievement_obj:
                newly_unlocked.append(achievement_obj)
        
        if r3_count >= 3:
            achievement_obj = self._award('LUCK_TRIPLE_R3')
            if achievement_obj:
                newly_unlocked.append(achievement_obj)
        
        return newly_unlocked
    
    def check_collection_achievements(self) -> List[Achievement]:
        """
        Checks all collection-based achievements against the user's full inventory.
        TRIGGER: Called from a signal when the user's inventory changes.
        """
        newly_unlocked = []
        
        owned_students = UserInventory.objects.filter(inventory_user=self.user).select_related('student_id')
        user_owned_set = {f"{item.student_id.student_name}|{item.student_id.version}" for item in owned_students}

        # --- THE OPTIMIZATION ---
        # We now loop over the much smaller, pre-filtered dictionary.
        for unlock_key, required_students in COLLECTION_SETS.items():
            
            # Skip if the user already has this achievement.
            if unlock_key not in self.unlocked_keys:
                # The check is now simpler and faster.
                if all(f"{req['name']}|{req['version']}" in user_owned_set for req in required_students):
                    achievement_obj = self._award(unlock_key)
                    if achievement_obj:
                        newly_unlocked.append(achievement_obj)
        
        return newly_unlocked

    def check_milestone_achievements(self) -> List[Achievement]:
        """
        Checks for achievements related to overall account progression.
        TRIGGER: Called after a gacha pull is saved.
        """
        newly_unlocked = []

        # Fetching the count here is acceptable as it's a single, fast query.
        total_pulls = self._get_total_pull_count()
        
        # --- Check for Total Pulls Milestones ---
        # The order here is important to prevent multiple awards in one go.
        if total_pulls >= 10:
            achievement_obj = self._award('MILESTONE_PULLS_10')
            if achievement_obj: newly_unlocked.append(achievement_obj)
        
        if total_pulls >= 1000:
            achievement_obj = self._award('MILESTONE_PULLS_1000')
            if achievement_obj: newly_unlocked.append(achievement_obj)
            
        return newly_unlocked
    # NEW: A method to handle updating the counter.
    def increment_pull_count(self, amount: int):
        """
        Atomically increments the user's pull count in the cache.
        This is the only method external code should call to update the count.
        """
        try:
            # This is the primary, high-performance operation.
            cache.incr(self.pull_count_cache_key, amount)
        except ValueError:
            # This is a self-healing fallback. If the key expired, this will
            # force _get_total_pull_count() to re-prime it from the DB on the next call.
            cache.delete(self.pull_count_cache_key)
            print(f"Cache key for {self.pull_count_cache_key} expired or was missing. It will be re-primed.")
