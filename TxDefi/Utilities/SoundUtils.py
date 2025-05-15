from enum import Enum
import pygame  # Windows sound support (use pygame for cross-platform)
import os
import TxDefi.Data.Globals as globals

class SoundType(Enum):
    ALERT = 0
    CELEBRATE = 1
    BAD_NEWS = 2
    PUMP_MIGRATION = 3
    BONDING_COMPLETE = 4

class SoundUtils:
    def __init__(self):
        pygame.mixer.init()
        self.sounds = {SoundType.ALERT:  pygame.mixer.Sound(globals.beep_sound),
                        SoundType.CELEBRATE: pygame.mixer.Sound(globals.trade_successful_sound),
                        SoundType.BONDING_COMPLETE: pygame.mixer.Sound(globals.bonding_complete_sound),
                        SoundType.PUMP_MIGRATION: pygame.mixer.Sound(globals.ray_migration)}
        self.muted = False
        
    def add_sound_type(self, sound_path: str):   
        if os.path.isfile(sound_path):
            self.sounds[len(self.sounds)] = pygame.mixer.Sound(sound_path)

    def play_sound(self, sound_type: SoundType | int):
        if not self.muted and sound_type in self.sounds:
            self.sounds[sound_type].play()