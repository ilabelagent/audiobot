import subprocess
from pathlib import Path


def _very_noisy_vox_chain(
    # Core cleanup
    noise_reduce: float = 12.0,
    noise_floor: float = -28.0,
    deess_center: float = 0.25,
    deess_strength: float = 1.2,
    highpass_hz: int = 80,
    lowpass_hz: int = 18000,
    gate: bool = True,
    gate_thresh_db: float = -45.0,
    limiter: float = 0.95,
    # Click/clip removal
    declick: bool = True,
    declip: bool = True,
    # Parallel air bus
    air_bus: bool = True,
    air_highpass_hz: int = 9500,
    air_shelf_gain_db: float = 3.0,
    air_deess_strength: float = 2.0,
    air_mix: float = 0.2,
    # Post-mix safety de-ess
    post_deess_center: float = 0.35,
    post_deess_strength: float = 0.0,
) -> str:
    """Build an aggressive FFmpeg filtergraph for very noisy vocals with optional AIR bus.

    Notes:
    - Uses afftdn + de-esser + optional gate + limiter on main path.
    - Optionally adds parallel "AIR" bus: HPF @ ~10k, de-ess safety, high-shelf boost, then mixed back.
    - Includes adeclick/adeclip where available in the user's FFmpeg build.
    """
    # Clamp user-facing parameters to reasonable bounds
    deess_center = max(0.0, min(1.0, deess_center))
    deess_strength = max(0.0, min(2.0, deess_strength))
    air_deess_strength = max(0.0, min(2.0, air_deess_strength))
    post_deess_center = max(0.0, min(1.0, float(post_deess_center)))
    post_deess_strength = max(0.0, min(2.0, float(post_deess_strength)))
    limiter = max(0.0, min(1.0, limiter))
    air_mix = max(0.0, min(1.0, air_mix))
    highpass_hz = max(20, int(highpass_hz))
    lowpass_hz = max(2000, int(lowpass_hz))
    air_highpass_hz = max(2000, int(air_highpass_hz))

    # Pre-clean (shared before split)
    pre = []
    if declick:
        pre.append("adeclick")
    if declip:
        pre.append("adeclip")
    pre.append(f"afftdn=nr={float(noise_reduce)}:nf={float(noise_floor)}:om=o")

    # Main path after split
    main = []
    main.append(f"deesser=f={deess_center}:s={deess_strength}")
    if gate:
        # Simple gate: attack fast, release ~80ms
        main.append(f"agate=threshold={gate_thresh_db}:release=80")
    if highpass_hz:
        main.append(f"highpass=f={highpass_hz}")
    if lowpass_hz:
        main.append(f"lowpass=f={lowpass_hz}")
    main.append(f"alimiter=limit={limiter}")

    if not air_bus:
        # No parallel branch; return linear chain
        return ",".join(pre + main)

    # AIR bus branch
    air = []
    air.append(f"highpass=f={air_highpass_hz}")
    # Safety de-ess after boosting
    air.append(f"deesser=f=0.35:s={air_deess_strength}")
    # High shelf via treble (broad tilt) or equalizer; treble is widely available
    # Use small shelf (3 dB default) to avoid harshness
    air.append(f"treble=g={air_shelf_gain_db}")
    # Gentle leveling to keep air steady
    air.append("acompressor=threshold=-24dB:ratio=2:attack=2:release=60")
    # Scale the branch level before mix
    air.append(f"volume={air_mix}")

    # Compose split/mix graph
    # [in] -> pre -> asplit [m][a]; [m]main -> [m2]; [a]air -> [a2]; [m2][a2]amix -> limiter
    graph = []
    if pre:
        graph.append(",".join(pre) + ",asplit=2[m][a]")
    else:
        graph.append("asplit=2[m][a]")
    graph.append("[m]" + ",".join(main) + "[m2]")
    graph.append("[a]" + ",".join(air) + "[a2]")
    graph.append("[m2][a2]amix=inputs=2:normalize=0[mix]")
    # Optional post-mix safety de-ess
    if post_deess_strength > 0.0:
        graph.append(f"[mix]deesser=f={post_deess_center}:s={post_deess_strength}[prelim]")
        final_in = "[prelim]"
    else:
        final_in = "[mix]"
    # Final limiter on the mixed output
    graph.append(f"{final_in}alimiter=limit={limiter}")
    return ";".join(graph)


def build_filter_chain(
    noise_reduce: float = 12.0,
    noise_floor: float = -28.0,
    deess_center: float = 0.25,
    deess_strength: float = 1.2,
    highpass: int = 70,
    lowpass: int = 18000,
    limiter: float = 0.95,
    # Optional advanced preset selection
    preset: str | None = None,
    # VERY_NOISY_VOX options (only used when preset is selected)
    gate: bool = True,
    gate_thresh_db: float | None = None,
    air_bus: bool = False,
    air_mix: float = 0.2,
    air_highpass_hz: int | None = None,
    air_shelf_gain_db: float | None = None,
    air_deess_strength: float | None = None,
    # Click/pops toggles for preset
    declick: bool = True,
    declip: bool = True,
    # Post-mix safety de-ess for preset
    post_deess_center: float = 0.35,
    post_deess_strength: float = 0.0,
) -> str:
    """Build an FFmpeg filter chain.

    Defaults match the original simple chain (afftdn + deesser + HP/LP + limiter).
    If `preset` is set to "very_noisy_vox", builds an aggressive chain with optional AIR bus.
    """
    p = (preset or "").strip().lower()
    if p in {"very_noisy_vox", "very-noisy-vox", "verynoisyvox"}:
        return _very_noisy_vox_chain(
            noise_reduce=noise_reduce,
            noise_floor=noise_floor,
            deess_center=deess_center,
            deess_strength=deess_strength,
            highpass_hz=max(highpass, 70),
            lowpass_hz=max(lowpass, 16000),
            gate=gate,
            gate_thresh_db=(gate_thresh_db if gate_thresh_db is not None else -45.0),
            limiter=limiter,
            air_bus=air_bus,
            air_mix=air_mix,
            air_highpass_hz=(air_highpass_hz if air_highpass_hz is not None else 9500),
            air_shelf_gain_db=(air_shelf_gain_db if air_shelf_gain_db is not None else 3.0),
            air_deess_strength=(air_deess_strength if air_deess_strength is not None else 2.0),
            declick=declick,
            declip=declip,
            post_deess_center=post_deess_center,
            post_deess_strength=post_deess_strength,
        )
    elif p in {"very_loud_crispy", "very-loud-crispy", "loud_crispy", "loud-crispy"}:
        # Use same backbone with brighter air and louder limiter
        return _very_noisy_vox_chain(
            noise_reduce=min(10.0, max(6.0, float(noise_reduce or 8.0))),
            noise_floor=float(noise_floor or -30.0),
            deess_center=float(deess_center or 0.28),
            deess_strength=min(1.5, max(1.0, float(deess_strength or 1.2))),
            highpass_hz=max(80, int(highpass or 90)),
            lowpass_hz=max(18000, int(lowpass or 20000)),
            gate=True,
            gate_thresh_db=(gate_thresh_db if gate_thresh_db is not None else -45.0),
            limiter=max(0.95, float(limiter or 0.99)),
            air_bus=True,
            air_highpass_hz=(air_highpass_hz if air_highpass_hz is not None else 9500),
            air_shelf_gain_db=(air_shelf_gain_db if air_shelf_gain_db is not None else 3.0),
            air_deess_strength=(air_deess_strength if air_deess_strength is not None else 1.5),
            air_mix=float(air_mix or 0.25),
            declick=bool(declick),
            declip=bool(declip),
            post_deess_center=float(post_deess_center or 0.35),
            post_deess_strength=float(post_deess_strength or 0.4),
        )
    elif p in {"max_loud", "max-loud", "max_loudness", "max-loudness", "slam"}:
        # Maximum loudness tilt: strong air presence, hot limiter, safety de-ess
        return _very_noisy_vox_chain(
            noise_reduce=min(10.0, max(6.0, float(noise_reduce or 8.0))),
            noise_floor=float(noise_floor or -32.0),
            deess_center=float(deess_center or 0.30),
            deess_strength=min(1.6, max(1.1, float(deess_strength or 1.3))),
            highpass_hz=max(90, int(highpass or 100)),
            lowpass_hz=max(20000, int(lowpass or 20000)),
            gate=True,
            gate_thresh_db=(gate_thresh_db if gate_thresh_db is not None else -45.0),
            limiter=max(0.98, float(limiter or 0.99)),
            air_bus=True,
            air_highpass_hz=(air_highpass_hz if air_highpass_hz is not None else 10000),
            air_shelf_gain_db=(air_shelf_gain_db if air_shelf_gain_db is not None else 4.0),
            air_deess_strength=(air_deess_strength if air_deess_strength is not None else 1.6),
            air_mix=float(air_mix or 0.30),
            declick=bool(declick),
            declip=bool(declip),
            post_deess_center=float(post_deess_center or 0.35),
            post_deess_strength=float(post_deess_strength or 0.7),
        )

    # Original simple chain (kept for compatibility and speed)
    deess_center = max(0.0, min(1.0, deess_center))
    deess_strength = max(0.0, min(2.0, deess_strength))
    limiter = max(0.0, min(1.0, limiter))
    filters = [
        f"afftdn=nr={noise_reduce}:nf={noise_floor}:om=o",
        f"deesser=f={deess_center}:s={deess_strength}",
    ]
    if highpass and highpass > 0:
        filters.append(f"highpass=f={highpass}")
    if lowpass and lowpass > 0:
        filters.append(f"lowpass=f={lowpass}")
    filters.append(f"alimiter=limit={limiter}")
    return ",".join(filters)


def clean_audio(input_path: Path, output_path: Path, af: str, keep_float: bool = False, timeout: float | None = 600) -> subprocess.CompletedProcess:
    codec = "pcm_f32le" if keep_float else "pcm_s16le"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-af",
        af,
        "-c:a",
        codec,
        str(output_path),
    ]
    try:
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        # Return a CompletedProcess-like object with timeout info
        cp = subprocess.CompletedProcess(cmd, returncode=124, stdout=(e.output or "") + "\n[timeout] ffmpeg processing exceeded timeout", stderr=None)
        return cp
