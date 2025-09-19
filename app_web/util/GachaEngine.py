# your_app/services/gacha_engine.py

import random
from decimal import Decimal
from app_web.models import GachaBanner, Student

class GachaEngine:
    """
    A stateless service class that handles the logic of performing gacha pulls
    for a specific banner. It is initialized with all necessary data and does not
    save anything to the database.
    """
    def __init__(self, banner: GachaBanner):
        
        # Fetch rate categories
        self.pickup_r3_rate = banner.pickup_r3_rate
        self.non_pickup_r3_rate = banner.non_pickup_r3_rate
        self.r2_rate = banner.r2_rate
        self.r1_rate = banner.r1_rate

        # Convert the QuerySets to lists for faster `random.choice`
        self.pickup_pool = list(banner.pickup_students)
        self.r3_pool = list(banner.r3_students)
        self.r2_pool = list(banner.r2_students)
        self.r1_pool = list(banner.r1_students)
