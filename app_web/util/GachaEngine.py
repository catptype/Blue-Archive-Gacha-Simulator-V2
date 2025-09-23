# your_app/services/gacha_engine.py

import random
from app_web.models import GachaBanner, Student

class GachaEngine:
    """
    A stateless service class that handles the logic of performing gacha pulls
    for a specific banner. It is initialized with all necessary data and does not
    save anything to the database.
    """
    def __init__(self, banner: GachaBanner):
        
        # Fetch rate categories
        self.banner = banner

        # --- 1. Pre-calculate rarity rates ---
        self.rates = {
            "r3": banner.pickup_r3_rate + banner.non_pickup_r3_rate,
            "r2": banner.r2_rate,
            "r1": banner.r1_rate
        }

        # --- 2. Pre-fetch student pools into memory ---
        self.pools = {
            "pickup": list(banner.pickup_students),
            "r3": list(banner.r3_students),
            "r2": list(banner.r2_students),
            "r1": list(banner.r1_students),
        }

        # --- 3. Pre-calculate per-student weights ---
        # FIXED: Use len() on the in-memory lists for better performance (avoids DB hits).
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
    
    def draw_gacha(self):
        # Random rarity ["r3", "r2", "r1"]
        result = random.choices(list(self.rates.keys()), list(self.rates.values()))[0]

        if result == "r3":
            
            # Merge both pickup and non-pickup r3 but different rate
            all_students = self.pools["pickup"] + self.pools["r3"]
            all_rates = self.weights["pickup"] + self.weights["r3"]

            return random.choices(all_students, all_rates)
        
        elif result == "r2":
            return random.choices(self.pools["r2"], self.weights["r2"])
        elif result == "r1":
            return random.choices(self.pools["r1"], self.weights["r1"])
        else:
            raise ValueError("Something wrong in random gacha result")
        
    def draw_1(self):

        obj:Student = self.draw_gacha()[0]

        # convert to JSON
        result_dict = {
            "id": obj.id,
            "name": obj.name,
            "version": obj.version,
            "rarity": obj.rarity,
            "school": obj.school
        }

        return [result_dict]
    
    def draw_10(self):
        return [self.draw_1()[0] for _ in range(10)]
    