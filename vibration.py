"""
Vibration / mechanical test standards corpus (vibration-only MVP).

Curated from PUBLICLY AVAILABLE sources:
  - GEVS (GSFC-STD-7000) General Environmental Verification Standard
  - NASA-STD-7001 Payload Vibroacoustic Test Criteria
  - NASA-STD-7002 Payload Test Requirements
  - NASA-HDBK-7004 Force Limited Vibration Testing
  - NASA-HDBK-7005 Dynamic Environmental Criteria
  - MIL-STD-1540 Test Requirements for Space Vehicles
  - Launch vehicle payload user's guides (public PSD/SRS envelopes)

These are simplified, representative knowledge chunks for an MVP RAG demo.
Production should ingest the full standards text via document parsing.
All generated output requires qualified test engineer review.
"""

VIBRATION_CHUNKS = [
    {
        "id": "vib-levels-qual-accept",
        "source": "GEVS GSFC-STD-7000",
        "topic": "qualification vs acceptance vs protoflight levels and duration",
        "text": (
            "Qualification random vibration is typically +3 dB above the Maximum "
            "Expected Flight Level (MEFL) for 120 seconds per axis. Acceptance is at "
            "MEFL for 60 seconds per axis. Protoflight applies qualification levels "
            "(+3 dB) but for the acceptance duration (60 s/axis). Tests are run in "
            "three orthogonal axes (X, Y, Z)."
        ),
    },
    {
        "id": "vib-workmanship-psd",
        "source": "GEVS GSFC-STD-7000 Table 2.4-3",
        "topic": "component minimum workmanship random vibration qualification spectrum",
        "text": (
            "Generalized component minimum workmanship random vibration qualification "
            "spectrum for components up to 22.7 kg (50 lb): "
            "20 Hz at 0.026 g^2/Hz; +3 dB/oct slope from 20 to 50 Hz; "
            "flat 0.16 g^2/Hz from 50 to 800 Hz; -3 dB/oct slope from 800 to 2000 Hz; "
            "2000 Hz at 0.026 g^2/Hz. Overall = 14.1 Grms. Acceptance level is 6 dB "
            "below qualification (flat region 0.04 g^2/Hz, 7.0 Grms)."
        ),
    },
    {
        "id": "vib-mass-attenuation",
        "source": "GEVS GSFC-STD-7000",
        "topic": "mass attenuation of random vibration levels for heavier units",
        "text": (
            "For components heavier than 22.7 kg (M in kg), the flat-region acceleration "
            "spectral density is reduced: ASD(M) = 0.16 * (22.7 / M) g^2/Hz, equivalent "
            "to a 10*log10(22.7/M) dB reduction, with the sloped breakpoints scaled "
            "accordingly. The reduction is capped so the spectrum never falls below the "
            "workmanship minimum. This prevents unrealistic overtesting of large units."
        ),
    },
    {
        "id": "vib-grms-calc",
        "source": "Random vibration fundamentals",
        "topic": "how overall Grms is computed from a PSD",
        "text": (
            "Overall Grms equals the square root of the area under the acceleration "
            "spectral density (ASD/PSD) curve across frequency. For a flat segment the "
            "area is ASD * bandwidth. For a sloped segment (constant dB/oct on a log-log "
            "plot) the area is computed analytically per segment and summed. Grms is the "
            "key single-number severity metric for a random vibration test."
        ),
    },
    {
        "id": "vib-notching",
        "source": "NASA-HDBK-7004 / NASA-HDBK-7005 (force limited vibration)",
        "topic": "notching to prevent overtesting at resonances",
        "text": (
            "Notching reduces the input acceleration spectral density at the test "
            "article's resonant frequencies so that responses or interface forces do not "
            "exceed realistic flight limits. Response-limited notching caps measured "
            "acceleration response; force-limited vibration (FLV) caps interface force "
            "using a semi-empirical force specification (the simple two-degree-of-freedom "
            "method sets a force limit constant C, commonly C^2 between 2 and 5). Notches "
            "must be justified by coupled-loads analysis or measured data and require test "
            "engineer approval; over-notching causes undertesting."
        ),
    },
    {
        "id": "vib-sine-survey",
        "source": "GEVS GSFC-STD-7000",
        "topic": "low-level sine survey / signature and damage detection",
        "text": (
            "A low-level sine sweep (signature survey, typically 0.25-0.5 g, 5-2000 Hz) "
            "is run before and after each random run to identify resonances and detect "
            "structural change. A primary-resonance frequency shift greater than about "
            "5 percent, or an amplitude change greater than about 20 percent, indicates "
            "possible damage and must be investigated."
        ),
    },
    {
        "id": "vib-sine-qual",
        "source": "GEVS / launch vehicle user's guides",
        "topic": "sine vibration and quasi-static load verification",
        "text": (
            "Swept-sine or sine-burst testing verifies the structure against low-frequency "
            "transient and quasi-static launch loads (typical quasi-static load factors "
            "are on the order of several to ~12 g axial/lateral depending on the launch "
            "vehicle). Sine sweep rate is commonly 2 or 4 octaves per minute. The launch "
            "vehicle payload user's guide provides the sine and quasi-static environment."
        ),
    },
    {
        "id": "vib-shock",
        "source": "MIL-STD-1540 / NASA-STD-7003",
        "topic": "pyroshock / shock response spectrum",
        "text": (
            "Shock requirements use a Shock Response Spectrum (SRS) from sources such as "
            "stage separation, fairing jettison, and pyrotechnic firing. Qualification "
            "SRS is typically +3 to +6 dB above the maximum predicted environment with "
            "2 actuations per axis. The launch vehicle user's guide provides the "
            "separation-event SRS at the payload interface."
        ),
    },
    {
        "id": "vib-lv-environment",
        "source": "Launch vehicle Payload User's Guides (Falcon 9, Vulcan, Electron, etc.)",
        "topic": "launch-vehicle-specified random/acoustic environment drives the spec",
        "text": (
            "The launch vehicle payload user's guide publishes the random vibration PSD, "
            "acoustic spectrum, shock SRS, sine environment, and quasi-static load factors "
            "at the payload interface, plus minimum structural frequency (stiffness) "
            "requirements to avoid coupling with vehicle modes (e.g. first axial/lateral "
            "modes above specified thresholds). The test specification envelopes the "
            "LV-specified environment with component workmanship minimums, then applies "
            "qualification margin and notching."
        ),
    },
    {
        "id": "vib-control-tolerance",
        "source": "GEVS GSFC-STD-7000",
        "topic": "control tolerances and abort limits",
        "text": (
            "Random vibration control tolerance is commonly +/-1.5 dB over most of the "
            "band and +/-3 dB at spectral peaks/edges, with overall Grms held within about "
            "+/-10 percent (-1/+3 dB typical). Abort limits (e.g. +6 dB) automatically stop "
            "the test to protect hardware. Control is via one or more accelerometers "
            "(single, average, or extremal control strategy)."
        ),
    },
    {
        "id": "vib-passfail",
        "source": "GEVS GSFC-STD-7000",
        "topic": "pass/fail criteria",
        "text": (
            "Pass criteria: (1) pre/post low-level sine signatures show no resonance shift "
            "beyond threshold; (2) functional/aliveness test passes after each axis; "
            "(3) visual inspection shows no damage, fastener backout, or fracture; "
            "(4) the control spectrum stayed within tolerance for the full duration. "
            "Any exceedance, signature change, or functional anomaly is a fail pending "
            "engineering disposition."
        ),
    },
]
