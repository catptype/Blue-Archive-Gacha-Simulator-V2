# your_app/services/gacha_engine.py

import random
from decimal import Decimal
from app_web.models import GachaBanner

class GachaEngine:
    """
    A stateless service class that handles the logic of performing gacha pulls
    for a specific banner. It is initialized with all necessary data and does not
    save anything to the database.
    """
    def __init__(self, banner: GachaBanner):
        
        # Fetch rate categories
        self.banner = banner

        self.rates = {
            "r3": banner.pickup_r3_rate + banner.non_pickup_r3_rate,
            "r2": banner.r2_rate,
            "r1": banner.r1_rate
        }

        # Convert the QuerySets to lists for faster `random.choice`
        self.pool = {
            "pickup": list(banner.pickup_students),
            "r3": list(banner.r3_students),
            "r2": list(banner.r2_students),
            "r1": list(banner.r1_students),
        }
    
    def draw_one_gacha(self):
        # Random rarity ["r3", "r2", "r1"]
        result = random.choices(list(self.rates.keys()), list(self.rates.values()))[0]

        if result == "r3":
            total_pickup_students = self.banner.pickup_students.count()
            if total_pickup_students > 0:
                pickup_rate_list = [ self.banner.pickup_r3_rate / total_pickup_students ] * total_pickup_students

            total_non_pickup_students = self.banner.r3_students.count()
            r3_rate_list = [ self.banner.pickup_r3_rate / total_pickup_students ] * total_pickup_students

            pass
        elif result == "r2":
            pass
        else:
            pass