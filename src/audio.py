import pygame
from singleton import Singleton
from enum import StrEnum


class Track(StrEnum):
    MUSIC = "mx"
    VOICE = "vo"
    EFFECTS = "sfx"
    AMBIENCE = "amb"
    SYSTEM = "sys"
    AUXILIAR = "aux"


class AudioManager(Singleton):

    _channels: dict[Track, list[pygame.mixer.Channel]] = {}

    def start(self, num_per_track: int = 5):
        i = 0
        tracks = [t for t in Track]
        pygame.mixer.set_num_channels(num_per_track * len(tracks))
        for track in tracks:
            self._channels[track] = []
            for _ in range(num_per_track):
                self._channels[track].append(pygame.mixer.Channel(i))
                i += 1

    def stop_channel(self, channel: Track, fadeout_ms: int):
        for c in self._channels[channel]:
            c.fadeout(fadeout_ms)

    def stop_all(self, fadeout_ms: int):
        for _, t in self._channels.items():
            for c in t:
                c.fadeout(fadeout_ms)

    def stop(self, channel_id: tuple[Track, int], fadeout_ms: int):
        a, i = channel_id
        self._channels[a][i].fadeout(fadeout_ms)

    def play(
        self,
        track: Track,
        sound: pygame.mixer.Sound,
        loops: int = 0,
        maxtime_ms: int = 0,
        fadein_ms: int = 0,
    ) -> tuple[Track, int] | None:
        for i, c in enumerate(self._channels[track.value]):
            if not c.get_busy():
                c.play(sound, loops, maxtime_ms, fadein_ms)
                return (track, i)
