"""
SoundManager — centralizes all audio playback for StarCell.

Gracefully degrades: if pygame.mixer fails to init or any file is missing,
all methods return silently and the game continues without audio.
"""

import pygame
import random
import os
import io


class SoundManager:
    """Manages music, SFX, and ambient audio."""

    MUSIC = {
        'menu':              'sounds/music/menu.ogg',
        'overworld_day':     'sounds/music/overworld_day.ogg',
        'overworld_night':   'sounds/music/overworld_night.ogg',
        'cave':              'sounds/music/cave.ogg',
        'ambient_travel_1':  'sound files/game_files/ambient_travel_music_1.mp3',
        'ambient_travel_2':  'sound files/game_files/ambient_travel_music_2.mp3',
        'ambient_travel_3':  'sound files/game_files/ambient_travel_music_3.wav',
    }

    DAWN_TRACKS = ['ambient_travel_1', 'ambient_travel_2', 'ambient_travel_3']

    # Max NPC spatial sounds per tick (budget to prevent audio spam)
    NPC_SOUND_BUDGET = 2

    def __init__(self):
        try:
            pygame.mixer.init()
        except Exception as e:
            print(f"[Sound] mixer init failed: {e}")
            self._ok = False
            return
        self._ok = True
        self.music_enabled  = True   # toggled by menu checkbox
        pygame.mixer.set_num_channels(8)
        self.music_volume   = 0.35
        self.sfx_volume     = 0.65
        self.ambient_volume = 0.25
        self.current_music  = None
        self._ambient_ch    = pygame.mixer.Channel(7)
        self._next_bird_tick    = random.randint(400, 900)
        self._next_cricket_tick = random.randint(800, 1800)
        self._npc_sounds_this_tick = 0   # reset each tick in update()
        self.sounds = {}
        self._music_bufs = {}   # {track_key: (BytesIO, ext)} — pre-read at startup
        self._load_all()

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------

    def _load_sfx_list(self, paths):
        """Load an explicit list of file paths as a sound pool."""
        pool = []
        for path in paths:
            if os.path.exists(path):
                try:
                    pool.append(pygame.mixer.Sound(path))
                except Exception:
                    pass
        return pool

    def _load_pool(self, prefix, sfx_dir='sounds/sfx'):
        """Load prefix_0, prefix_1, … until a file is missing."""
        pool = []
        i = 0
        while True:
            path = f'{sfx_dir}/{prefix}_{i}.wav'
            if not os.path.exists(path):
                path = f'{sfx_dir}/{prefix}_{i}.ogg'
                if not os.path.exists(path):
                    break
            try:
                pool.append(pygame.mixer.Sound(path))
            except Exception:
                pass
            i += 1
        return pool

    def _load_all(self):
        self.sounds['footstep_dirt']    = self._load_pool('footstep_dirt')
        self.sounds['footstep_water']   = self._load_pool('footstep_water')
        self.sounds['pickup']           = self._load_pool('pickup')
        self.sounds['sword_swing']      = self._load_pool('sword_swing')
        self.sounds['bird']             = self._load_pool('bird',    'sounds/ambient')
        self.sounds['cricket']          = self._load_pool('cricket', 'sounds/ambient')
        # Single sounds
        for key, path in [
            ('menu_select',      'sounds/sfx/menu_select.wav'),
            ('inventory_open',   'sounds/sfx/inventory_open_0.wav'),
            ('equip_sword',      'sounds/sfx/equip_sword_0.wav'),
            ('quest_received',   'sounds/sfx/quest_received_0.ogg'),
            ('quest_complete',   'sounds/sfx/quest_complete_0.wav'),
            ('enter_structure',  'sounds/sfx/enter_structure_0.wav'),
        ]:
            if os.path.exists(path):
                try:
                    self.sounds[key] = pygame.mixer.Sound(path)
                except Exception:
                    pass

        # NPC / creature spatial sounds (from 'sound files/game_files/')
        _gf = 'sound files/game_files'
        self.sounds['wood_chop']      = self._load_sfx_list([
            f'{_gf}/chop_wood_sound_1.wav', f'{_gf}/chop_wood_sound_2.wav'])
        self.sounds['goblin_sound']   = self._load_sfx_list([
            f'{_gf}/goblin_sound_1.wav', f'{_gf}/goblin_sound_2.wav'])
        self.sounds['wolf_sound']     = self._load_sfx_list([
            f'{_gf}/wolf_sound_1.wav'])
        self.sounds['skeleton_sound'] = self._load_sfx_list([
            f'{_gf}/skeleton_sound_1.wav', f'{_gf}/skeleton_sound_2.wav'])
        self.sounds['termite_sound']  = self._load_sfx_list([
            f'{_gf}/termite_sound_1.wav', f'{_gf}/termite_sound_2.wav'])
        self.sounds['bat_sound']      = self._load_sfx_list([
            f'{_gf}/bat_wing_flap_sound_1.wav'])
        self.sounds['smithing_sound'] = self._load_sfx_list([
            f'{_gf}/backgroun_smithing_sound_1.wav'])

        # Pre-read all music files into memory so transitions hit RAM, not disk
        for key, path in self.MUSIC.items():
            if not os.path.exists(path):
                continue
            try:
                with open(path, 'rb') as f:
                    self._music_bufs[key] = (f.read(),
                                             os.path.basename(path))
            except Exception as e:
                print(f"[Sound] failed to buffer music '{key}': {e}")

        loaded = {k: (len(v) if isinstance(v, list) else 1)
                  for k, v in self.sounds.items() if v}
        print(f"[Sound] loaded: {loaded}")
        print(f"[Sound] music buffered: {list(self._music_bufs)}")

    # ------------------------------------------------------------------
    # Playback API
    # ------------------------------------------------------------------

    def play_sfx(self, key):
        if not self._ok:
            return
        pool = self.sounds.get(key)
        if not pool:
            return
        snd = random.choice(pool) if isinstance(pool, list) else pool
        snd.set_volume(self.sfx_volume)
        snd.play()

    def play_sfx_spatial(self, key, dist, max_dist=8):
        """Play a sound with volume scaled by distance (cells). Budget-limited per tick."""
        if not self._ok:
            return
        if self._npc_sounds_this_tick >= self.NPC_SOUND_BUDGET:
            return
        pool = self.sounds.get(key)
        if not pool:
            return
        vol = self.sfx_volume * max(0.0, 1.0 - dist / max_dist)
        if vol <= 0.01:
            return
        snd = random.choice(pool) if isinstance(pool, list) else pool
        snd.set_volume(vol)
        snd.play()
        self._npc_sounds_this_tick += 1

    def play_music(self, track_key, fade_ms=1000):
        if not self._ok or track_key == self.current_music:
            return
        if not self.music_enabled:
            self.current_music = track_key  # track what would be playing
            return
        entry = self._music_bufs.get(track_key)
        if not entry:
            return
        data, namehint = entry
        # Fresh BytesIO each time — pygame closes the buffer after load()
        pygame.mixer.music.load(io.BytesIO(data), namehint)
        pygame.mixer.music.set_volume(self.music_volume)
        pygame.mixer.music.play(-1, fade_ms=fade_ms)
        self.current_music = track_key

    def stop_music(self, fade_ms=1000):
        if self._ok:
            pygame.mixer.music.fadeout(fade_ms)
        self.current_music = None

    def play_dawn_music(self):
        """Play a random ambient_travel track at the dawn transition."""
        available = [k for k in self.DAWN_TRACKS if k in self._music_bufs]
        if not available:
            return
        track = random.choice(available)
        # Force play even if same track was last (dawn should always feel fresh)
        self.current_music = None
        self.play_music(track, fade_ms=2000)

    def set_music_enabled(self, enabled):
        """Enable or disable ambient/background music at runtime."""
        if not self._ok:
            return
        self.music_enabled = enabled
        if not enabled:
            pygame.mixer.music.fadeout(500)
        elif self.current_music:
            # Resume the track that should be playing
            entry = self._music_bufs.get(self.current_music)
            if entry:
                data, namehint = entry
                pygame.mixer.music.load(io.BytesIO(data), namehint)
                pygame.mixer.music.set_volume(self.music_volume)
                pygame.mixer.music.play(-1, fade_ms=500)

    # ------------------------------------------------------------------
    # Convenience hooks
    # ------------------------------------------------------------------

    def on_footstep(self, cell_type):
        if cell_type in ('WATER', 'DEEP_WATER'):
            self.play_sfx('footstep_water')
        else:
            self.play_sfx('footstep_dirt')

    def on_pickup(self):
        self.play_sfx('pickup')

    def on_menu_select(self):
        self.play_sfx('menu_select')

    def on_inventory_open(self):
        self.play_sfx('inventory_open')

    def on_inventory_select(self):
        self.play_sfx('menu_select')

    def on_equip_sword(self):
        self.play_sfx('equip_sword')

    def on_attack(self):
        self.play_sfx('sword_swing')

    def on_quest_received(self):
        self.play_sfx('quest_received')

    def on_quest_complete(self):
        self.play_sfx('quest_complete')

    def on_enter_structure(self):
        self.play_sfx('enter_structure')

    # ------------------------------------------------------------------
    # Per-tick update (music switching + periodic ambient)
    # ------------------------------------------------------------------

    def update(self, tick, state, is_night, in_structure, cell_at_player):
        if not self._ok:
            return

        # Reset NPC sound budget each tick
        self._npc_sounds_this_tick = 0

        # Music context switching
        if state == 'menu':
            self.play_music('menu')
        elif state == 'playing':
            if in_structure:
                self.play_music('cave')
            elif is_night:
                self.play_music('overworld_night')
            else:
                self.play_music('overworld_day')

        # Birds — outdoors daytime only
        if state == 'playing' and not in_structure and not is_night:
            if tick >= self._next_bird_tick:
                pool = self.sounds.get('bird', [])
                if pool:
                    snd = random.choice(pool)
                    snd.set_volume(self.ambient_volume)
                    self._ambient_ch.play(snd)
                self._next_bird_tick = tick + random.randint(400, 1000)

        # Crickets/frogs — outdoors nighttime only, less frequent
        if state == 'playing' and not in_structure and is_night:
            if tick >= self._next_cricket_tick:
                pool = self.sounds.get('cricket', [])
                if pool:
                    snd = random.choice(pool)
                    snd.set_volume(self.ambient_volume)
                    self._ambient_ch.play(snd)
                self._next_cricket_tick = tick + random.randint(900, 2000)
