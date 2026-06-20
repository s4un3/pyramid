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
    _track_volumes: dict[Track, float] = {}
    _local_volumes: dict[Track, list[float]] = {}

    def start(self, num_per_track: int = 5):
        i = 0
        tracks = [t for t in Track]
        pygame.mixer.set_num_channels(num_per_track * len(tracks))
        for track in tracks:
            self._channels[track] = []
            self._track_volumes[track] = 1.0
            self._local_volumes[track] = [1.0] * num_per_track

            for _ in range(num_per_track):
                channel = pygame.mixer.Channel(i)
                self._channels[track].append(channel)
                i += 1

    def stop_track(self, track: Track, fadeout_ms: int):
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
        for i, c in enumerate(self._channels[track]):
            if not c.get_busy():
                c.play(sound, loops, maxtime_ms, fadein_ms)
                return (track, i)

    def set_track_volume(self, track: Track, volume: float):
        self._track_volumes[track] = max(0.0, min(1.0, volume))
        for i in range(len(self._channels[track])):
            self._update_channel_volume(track, i)

    def set_channel_volume(self, channel_id: tuple[Track, int], volume: float):
        track, index = channel_id
        self._local_volumes[track][index] = max(0.0, min(1.0, volume))
        self._update_channel_volume(track, index)

    def get_track_volume(self, track: Track):
        return self._track_volumes[track]

    def get_channel_volume(self, channel_id: tuple[Track, int]):
        track, index = channel_id
        return self._local_volumes[track][index]

    def _update_channel_volume(self, track: Track, index: int):
        master = self._track_volumes[track]
        local = self._local_volumes[track][index]
        combined = master * local
        self._channels[track][index].set_volume(combined)
