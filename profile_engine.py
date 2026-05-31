"""
Random vibration test profile engine.

Computes a real, defensible random vibration PSD (the GEVS generalized component
workmanship spectrum), applies:
  - level selection (qualification / acceptance / protoflight) per GEVS,
  - mass attenuation for components heavier than 22.7 kg,
  - optional notch suggestions at supplied resonant frequencies,
and computes overall Grms analytically from the breakpoint table.

This is deterministic math grounded in NASA-STD-7001 / GEVS, NOT an LLM guess.
The LLM's job is to interpret inputs and explain; the numbers come from here.
All output still requires test engineer review.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import math


# GEVS generalized component minimum workmanship QUALIFICATION breakpoints.
# (freq Hz, ASD g^2/Hz). Flat 0.16 from 50-800, +/-3 dB/oct ramps, 14.1 Grms.
_GEVS_QUAL_BREAKPOINTS: List[Tuple[float, float]] = [
    (20.0, 0.026),
    (50.0, 0.160),
    (800.0, 0.160),
    (2000.0, 0.026),
]

# Level adjustments relative to qualification, in dB.
_LEVEL_DB = {
    "qualification": 0.0,
    "protoflight": 0.0,    # same level as qual, shorter duration
    "acceptance": -6.0,    # 6 dB below qual
}

_LEVEL_DURATION_S = {
    "qualification": 120,
    "protoflight": 60,
    "acceptance": 60,
}

_REFERENCE_MASS_KG = 22.7  # 50 lb GEVS reference


@dataclass
class ProfilePoint:
    freq_hz: float
    asd_g2_hz: float


@dataclass
class VibrationProfile:
    level: str
    duration_s_per_axis: int
    points: List[ProfilePoint]
    overall_grms: float
    mass_attenuation_db: float
    notches: List[dict]
    notes: List[str]


def _db_scale(asd: float, db: float) -> float:
    """Scale an ASD value by a dB amount (10*log10 power ratio)."""
    return asd * (10.0 ** (db / 10.0))


def _grms_from_breakpoints(points: List[Tuple[float, float]]) -> float:
    """
    Analytic Grms = sqrt(area under ASD curve), summing per-segment areas.
    Flat segment area = ASD * df. Sloped segment (linear on log-log) handled
    with the standard constant-dB/oct integration formula.
    """
    area = 0.0
    for (f1, a1), (f2, a2) in zip(points, points[1:]):
        if f2 <= f1:
            continue
        if abs(a2 - a1) < 1e-12:
            area += a1 * (f2 - f1)  # flat
        else:
            # slope in dB/oct on log-log axes
            m = math.log10(a2 / a1) / math.log10(f2 / f1)
            if abs(m + 1.0) < 1e-9:
                # special case: integral of A*f^-1 = A*ln(f2/f1)
                area += a1 * f1 * math.log(f2 / f1)
            else:
                area += (a2 * f2 - a1 * f1) / (m + 1.0)
    return math.sqrt(area)


def compute_profile(level: str = "qualification",
                    mass_kg: Optional[float] = None,
                    resonances_hz: Optional[List[float]] = None,
                    notch_depth_db: float = 6.0) -> VibrationProfile:
    """Build a random vibration profile from inputs."""
    level = level.lower().strip()
    if level not in _LEVEL_DB:
        level = "qualification"

    notes: List[str] = []

    # 1) Level adjustment
    level_db = _LEVEL_DB[level]

    # 2) Mass attenuation (only for heavier-than-reference components)
    mass_att_db = 0.0
    if mass_kg and mass_kg > _REFERENCE_MASS_KG:
        mass_att_db = 10.0 * math.log10(_REFERENCE_MASS_KG / mass_kg)
        notes.append(
            f"Mass attenuation applied: {mass_att_db:.1f} dB for "
            f"{mass_kg:.1f} kg (> {_REFERENCE_MASS_KG} kg reference)."
        )
    elif mass_kg:
        notes.append(
            f"No mass attenuation: {mass_kg:.1f} kg is at or below the "
            f"{_REFERENCE_MASS_KG} kg reference; workmanship minimum applies."
        )

    total_db = level_db + mass_att_db

    # 3) Build adjusted breakpoints
    adj = [(f, _db_scale(a, total_db)) for (f, a) in _GEVS_QUAL_BREAKPOINTS]
    points = [ProfilePoint(f, round(a, 5)) for (f, a) in adj]

    # 4) Grms
    grms = _grms_from_breakpoints([(p.freq_hz, p.asd_g2_hz) for p in points])

    # 5) Notch suggestions at resonances
    notches = []
    if resonances_hz:
        for rf in resonances_hz:
            if 20.0 <= rf <= 2000.0:
                # interpolate baseline ASD at rf for context
                notches.append({
                    "freq_hz": rf,
                    "suggested_notch_db": notch_depth_db,
                    "basis": "response/force-limited; verify with CLA or measured data",
                })
        if notches:
            notes.append(
                f"{len(notches)} notch(es) suggested at supplied resonances "
                f"(-{notch_depth_db:.0f} dB). MUST be justified per NASA-HDBK-7004 "
                f"and approved by a test engineer; over-notching causes undertesting."
            )

    notes.append(
        "Spectrum is the GEVS generalized component workmanship envelope. If a "
        "launch vehicle PSD is provided, the final spec must envelope both and "
        "re-derive Grms."
    )

    return VibrationProfile(
        level=level,
        duration_s_per_axis=_LEVEL_DURATION_S[level],
        points=points,
        overall_grms=round(grms, 2),
        mass_attenuation_db=round(mass_att_db, 2),
        notches=notches,
        notes=notes,
    )


def profile_as_table(profile: VibrationProfile) -> List[dict]:
    """Breakpoint table for display/plot."""
    return [{"Frequency (Hz)": p.freq_hz, "ASD (g^2/Hz)": p.asd_g2_hz}
            for p in profile.points]
