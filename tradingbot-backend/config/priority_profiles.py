"""
Priority Profiles för Konfigurationshantering

Definierar olika prioritetsprofiler för hur konfigurationsnycklar ska prioriteras
baserat på deras domän och användningsfall.
"""

from enum import Enum
from typing import List


class PriorityProfile(Enum):
    """
    Prioritetprofiler för konfigurationsnycklar.

    GLOBAL: Generella systeminställningar som följer standardprioritet
    DOMAIN_POLICY: Domänspecifika regler som måste vinna lokalt
    """

    GLOBAL = "global"
    DOMAIN_POLICY = "domain_policy"


class PriorityOrder:
    """
    Prioritetordning för olika profiler.
    """

    # Global prioritet: Runtime > FeatureFlags > Settings > Files
    GLOBAL_ORDER = ["runtime", "feature_flags", "settings", "files"]

    # Domain policy prioritet: Runtime(domain) > Files(policy) > FeatureFlags > Settings
    DOMAIN_POLICY_ORDER = ["runtime", "files", "feature_flags", "settings"]

    @classmethod
    def get_order(cls, profile: PriorityProfile) -> list[str]:
        """
        Hämta prioritetsordning för en given profil.

        Args:
            profile: Prioritetprofil att hämta ordning för

        Returns:
            Lista med källor i prioritetsordning (högsta först)
        """
        if profile == PriorityProfile.GLOBAL:
            return cls.GLOBAL_ORDER.copy()
        elif profile == PriorityProfile.DOMAIN_POLICY:
            return cls.DOMAIN_POLICY_ORDER.copy()
        else:
            raise ValueError(f"Okänd prioritetprofil: {profile}")

    @classmethod
    def get_source_priority(cls, profile: PriorityProfile, source: str) -> int:
        """
        Hämta prioritet (lägre nummer = högre prioritet) för en källa inom en profil.

        Args:
            profile: Prioritetprofil
            source: Källa att hämta prioritet för

        Returns:
            Prioritet som integer (0 = högsta prioritet)
        """
        order = cls.get_order(profile)
        try:
            return order.index(source)
        except ValueError:
            # Okänd källa får lägsta prioritet
            return len(order)


def get_effective_source(profile: PriorityProfile, available_sources: list[str]) -> str:
    """
    Hitta den effektiva källan baserat på prioritetprofil och tillgängliga källor.

    Args:
        profile: Prioritetprofil att använda
        available_sources: Lista med tillgängliga källor

    Returns:
        Den högsta prioriterade källan som finns tillgänglig

    Raises:
        ValueError: Om ingen källa är tillgänglig
    """
    priority_order = PriorityOrder.get_order(profile)

    for source in priority_order:
        if source in available_sources:
            return source

    raise ValueError(f"Ingen tillgänglig källa för profil {profile} bland {available_sources}")
