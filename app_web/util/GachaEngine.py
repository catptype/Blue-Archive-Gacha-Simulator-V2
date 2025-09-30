# your_app/services/gacha_engine.py

import random
from app_web.models import GachaBanner, Student

class GachaEngine:
    """
    A stateless service class that handles the logic of performing gacha pulls,
    including a 10-pull guarantee system.
    """
    def __init__(self, banner: GachaBanner):
        if not banner.preset_id:
            raise ValueError("Banner does not have a rate preset.")

        self.banner = banner

        # --- 1. Pre-calculate all rates, pools, and weights ONCE for performance ---
        self.rates = {
            "r3": banner.pickup_r3_rate + banner.non_pickup_r3_rate,
            "r2": banner.r2_rate,
            "r1": banner.r1_rate
        }
        self.pools = {
            "pickup": list(banner.pickup_students),
            "r3": list(banner.r3_students),
            "r2": list(banner.r2_students),
            "r1": list(banner.r1_students),
        }
        
        # This is the new rate table for the guaranteed 10th pull.
        self.guaranteed_r2_rates = {
            "r3": self.rates["r3"],
            "r2": self.rates["r2"] + self.rates["r1"] # R1 rate is absorbed by R2
        }

        # Pre-calculate weights for each pool.
        total_pickup = len(self.pools["pickup"])
        total_r3 = len(self.pools["r3"])
        total_r2 = len(self.pools["r2"])
        total_r1 = len(self.pools["r1"])

        self.weights = {
            "pickup": [banner.pickup_r3_rate / total_pickup] * total_pickup if total_pickup > 0 else [],
            "r3": [banner.non_pickup_r3_rate / total_r3] * total_r3 if total_r3 > 0 else [],
            "r2": [banner.r2_rate / total_r2] * total_r2 if total_r2 > 0 else [],
            "r1": [banner.r1_rate / total_r1] * total_r1 if total_r1 > 0 else [],
        }
    
    def _draw_one(self, *, guarantee_r2_or_higher: bool = False) -> Student:
        """
        An internal helper to perform a single pull.
        Returns a single Student OBJECT.
        The `guarantee_r2_or_higher` flag changes the odds for the pity pull.
        """
        # --- Layer 1: Determine the Rarity ---
        # Choose which rate table to use based on the guarantee flag.
        active_rates = self.guaranteed_r2_rates if guarantee_r2_or_higher else self.rates
        
        chosen_rarity = random.choices(
            list(active_rates.keys()), 
            weights=list(active_rates.values()),
            k=1
        )[0]

        # --- Layer 2: Choose a student from the corresponding pool ---
        if chosen_rarity == "r3":
            combined_r3_pool = self.pools["pickup"] + self.pools["r3"]
            combined_r3_weights = self.weights["pickup"] + self.weights["r3"]
            if not combined_r3_pool: # Fallback
                return random.choice(self.pools["r2"])
            return random.choices(combined_r3_pool, weights=combined_r3_weights, k=1)[0]
        
        elif chosen_rarity == "r2":
            if not self.pools["r2"]: # Fallback
                return random.choice(self.pools["r1"]) if not guarantee_r2_or_higher else self._draw_one(guarantee_r2_or_higher=True)
            return random.choices(self.pools["r2"], weights=self.weights["r2"], k=1)[0]
            
        elif chosen_rarity == "r1": # This block is only reachable on a normal pull
            if not self.pools["r1"]:
                raise Exception("Gacha Error: R1 Pool is empty.")
            return random.choices(self.pools["r1"], weights=self.weights["r1"], k=1)[0]
        
    def _serialize_student(self, student_obj: Student) -> dict:
        """A helper to convert a Student object into the JSON dictionary format."""
        return {
            "id": student_obj.id,
            "name": student_obj.name,
            # FIXED: Correctly access related object properties
            "version": student_obj.version,
            "rarity": student_obj.rarity,
            "school": student_obj.school
        }

    def draw_1(self) -> list[dict]:
        """
        Performs a single standard pull and returns the result as a JSON-ready list.
        """
        pulled_student = self._draw_one(guarantee_r2_or_higher=False)
        return [pulled_student]
        return [self._serialize_student(pulled_student)]
    
    def draw_10(self) -> list[dict]:
        """
        Performs 9 standard pulls and 1 guaranteed (R2 or higher) pull.
        The results are shuffled and returned as a JSON-ready list.
        """
        # 1. Perform the 9 standard pulls.
        pulled_students = [self._draw_one() for _ in range(9)]
        
        # 2. Perform the 1 guaranteed pull.
        guaranteed_pull = self._draw_one(guarantee_r2_or_higher=True)
        pulled_students.append(guaranteed_pull)
        
        # 4. Convert all 10 student objects to the final JSON format.
        return pulled_students
        return [self._serialize_student(student) for student in pulled_students]
    