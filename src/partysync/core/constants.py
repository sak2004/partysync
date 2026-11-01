"""PartySync constants. All timing values state their unit in the name."""

# Audio pipeline
BLOCK_MS: int = 10  # preferred capture/render block size in milliseconds
SAFETY_MS: float = 60.0  # minimum buffered audio per channel in milliseconds
MAX_DELAY_MS: float = 1000.0  # maximum user-settable delay in milliseconds
RING_SECONDS: float = 4.0  # ring buffer capacity in seconds
JUMP_MS_MIN: float = 25.0  # gross error threshold in milliseconds (see OutputChannel)
SLIP_DEADBAND_MS: float = 1.0  # filtered error must exceed this before slipping (ms)
CROSSFADE_MS: float = 5.0  # crossfade duration for jump corrections in milliseconds
GAIN_RAMP_MS: float = 20.0  # gain ramp duration in milliseconds
FILTER_TAU_S: float = 0.5  # EMA time constant for fill-level error smoothing in seconds
IDLE_SOURCE_MS: float = 100.0  # source idle threshold in milliseconds

# Chirp / calibration
CHIRP_DUR_S: float = 0.4  # chirp duration in seconds
CHIRP_F0: float = 400.0  # chirp start frequency in Hz
CHIRP_F1: float = 7000.0  # chirp end frequency in Hz
CHIRP_AMP: float = 0.5  # chirp amplitude (-6 dBFS)
CHIRP_FADE_MS: float = 20.0  # chirp fade-in/out duration in milliseconds
CAL_GAP_S: float = 2.0  # gap between two chirps in one calibration round (seconds)
CAL_WARMUP_S: float = 0.5  # mic warmup time before first chirp (seconds)
CAL_TAIL_S: float = 2.0  # listening time after last chirp of a round (seconds)
CAL_ROUNDS: int = 3  # number of calibration rounds
CAL_MIN_PMR: float = 8.0  # peak-to-median ratio needed for a detection
CAL_MAX_SPREAD_MS: float = 10.0  # max disagreement between rounds (milliseconds)
