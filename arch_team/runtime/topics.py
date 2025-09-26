# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TopicId:
    """
    Identifiziert ein Thema (Topic) im In-Process EventBus.

    Felder:
    - type: logischer Topic-Typ (z. B. requirements.plan)
    - source: Quelle/Namespace (z. B. default|frontend|batch)
    """
    type: str
    source: str


def DefaultTopicId(source: str = "default") -> TopicId:
    """
    Liefert einen Default-Topic Platzhalter. Der konkrete type wird beim publish() gesetzt.
    """
    return TopicId(type="", source=source)


# Topic-Konstanten
TOPIC_PLAN = "requirements.plan"
TOPIC_SOLVE = "requirements.solve"
TOPIC_VERIFY = "requirements.verify"
TOPIC_DTO = "requirements.dto"
TOPIC_TRACE = "requirements.trace"