from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Config


class Installer(ABC):
    @abstractmethod
    def ensure_installed(self, config: Config) -> None:
        raise NotImplementedError
