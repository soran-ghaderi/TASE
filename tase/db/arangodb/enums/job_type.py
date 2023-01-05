from enum import Enum


class JobType(Enum):
    UNKNOWN = 0

    COUNT_AUDIO_INTERACTION_TYPE = 1
    COUNT_PUBLIC_PLAYLIST_INTERACTION_TYPE = 2
    COUNT_PUBLIC_PLAYLIST_SUBSCRIPTIONS_TYPE = 3
    COUNT_HITS = 4
