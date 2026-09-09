from enum import StrEnum


class GameType(StrEnum):
    SINGLE = "single"
    DOUBLE = "double"


class TeamMatchNoticeCode(StrEnum):
    H = "H"
    T = "T"
    U = "U"
    V = "V"
    W = "W"
    W2 = "W2"
    Z = "Z"
    NA = "NA"
