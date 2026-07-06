"""Latency / hit-miss statistics for the epoch-deadline loop.

Percentiles, not just means — the tail is what misses epochs.
"""
import math
from collections import Counter


def _percentile(sorted_vals, q: float) -> float:
    if not sorted_vals:
        return float("nan")
    k = (len(sorted_vals) - 1) * q
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return sorted_vals[int(k)]
    return sorted_vals[lo] * (hi - k) + sorted_vals[hi] * (k - lo)


class Series:
    def __init__(self, name: str, unit: str = "ms"):
        self.name = name
        self.unit = unit
        self.vals: list[float] = []

    def add(self, v: float):
        self.vals.append(v)

    def line(self) -> str:
        if not self.vals:
            return f"  {self.name:<16} (no samples)"
        s = sorted(self.vals)
        return (
            f"  {self.name:<16} n={len(s):<5} "
            f"mean={sum(s) / len(s):7.2f} p50={_percentile(s, .5):7.2f} "
            f"p90={_percentile(s, .9):7.2f} p99={_percentile(s, .99):7.2f} "
            f"max={s[-1]:7.2f} {self.unit}"
        )


class Stats:
    def __init__(self):
        self.processing = Series("processing")      # decide+submit time per epoch
        self.headroom = Series("headroom")          # deadline - processing_end
        self.epoch_spacing = Series("epoch_spacing")  # gap between epoch events
        self.probe_rtt = Series("probe_rtt")        # send -> seen on echo feed
        self.epochs = 0
        self.overruns = 0          # processing finished after the deadline
        self.probes_sent = 0
        self.probes_seen = 0
        self.landed_offset = Counter()  # (landed_epoch - target_epoch) -> count

    def record_probe(self, offset: int, rtt_ms: float):
        self.probes_seen += 1
        self.landed_offset[offset] += 1
        self.probe_rtt.add(rtt_ms)

    @property
    def on_time_offset(self):
        """The smallest observed landing offset = the normal pipeline depth."""
        return min(self.landed_offset) if self.landed_offset else None

    def report(self) -> str:
        lines = ["=== epoch-deadline loop stats ===",
                 f"  epochs={self.epochs} overruns={self.overruns} "
                 f"probes sent={self.probes_sent} seen={self.probes_seen}",
                 self.processing.line(),
                 self.headroom.line(),
                 self.epoch_spacing.line(),
                 self.probe_rtt.line()]
        if self.landed_offset:
            base = self.on_time_offset
            hit = self.landed_offset.get(base, 0)
            total = sum(self.landed_offset.values())
            dist = " ".join(f"+{k}:{v}" for k, v in sorted(self.landed_offset.items()))
            lines.append(f"  landing offset (epochs past target): {dist}")
            lines.append(f"  on-time (offset={base}): {hit}/{total} = {100 * hit / total:.1f}%"
                         f"  -> slipped: {total - hit}")
        return "\n".join(lines)
