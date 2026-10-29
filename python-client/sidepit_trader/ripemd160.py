"""RIPEMD-160 — hashlib when the OpenSSL build provides it, pure Python otherwise.

Bitcoin addresses (and so every sidepit_id) are hash160 = RIPEMD-160(SHA-256(pubkey)).
Some OpenSSL 3 builds leave ripemd160 out of hashlib; this keeps the SDK pure
Python with nothing to compile at install time.

Reference vectors (Dobbertin, Bosselaers, Preneel 1996):
    ""     -> 9c1185a5c5e9fc54612808977ee8f548b2258d31
    "abc"  -> 8eb208f7e05d987a9b044a8e98c6b087f15a0bfc  (…0bfc; the widely copied …0bff is a typo)
"""
from __future__ import annotations

import hashlib
import struct

_RL = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
       7, 4, 13, 1, 10, 6, 15, 3, 12, 0, 9, 5, 2, 14, 11, 8,
       3, 10, 14, 4, 9, 15, 8, 1, 2, 7, 0, 6, 13, 11, 5, 12,
       1, 9, 11, 10, 0, 8, 12, 4, 13, 3, 7, 15, 14, 5, 6, 2,
       4, 0, 5, 9, 7, 12, 2, 10, 14, 1, 3, 8, 11, 6, 15, 13]
_RR = [5, 14, 7, 0, 9, 2, 11, 4, 13, 6, 15, 8, 1, 10, 3, 12,
       6, 11, 3, 7, 0, 13, 5, 10, 14, 15, 8, 12, 4, 9, 1, 2,
       15, 5, 1, 3, 7, 14, 6, 9, 11, 8, 12, 2, 10, 0, 4, 13,
       8, 6, 4, 1, 3, 11, 15, 0, 5, 12, 2, 13, 9, 7, 10, 14,
       12, 15, 10, 4, 1, 5, 8, 7, 6, 2, 13, 14, 0, 3, 9, 11]
_SL = [11, 14, 15, 12, 5, 8, 7, 9, 11, 13, 14, 15, 6, 7, 9, 8,
       7, 6, 8, 13, 11, 9, 7, 15, 7, 12, 15, 9, 11, 7, 13, 12,
       11, 13, 6, 7, 14, 9, 13, 15, 14, 8, 13, 6, 5, 12, 7, 5,
       11, 12, 14, 15, 14, 15, 9, 8, 9, 14, 5, 6, 8, 6, 5, 12,
       9, 15, 5, 11, 6, 8, 13, 12, 5, 12, 13, 14, 11, 8, 5, 6]
_SR = [8, 9, 9, 11, 13, 15, 15, 5, 7, 7, 8, 11, 14, 14, 12, 6,
       9, 13, 15, 7, 12, 8, 9, 11, 7, 7, 12, 7, 6, 15, 13, 11,
       9, 7, 15, 11, 8, 6, 6, 14, 12, 13, 5, 14, 13, 13, 7, 5,
       15, 5, 8, 11, 14, 14, 6, 14, 6, 9, 12, 9, 12, 5, 15, 8,
       8, 5, 12, 9, 12, 5, 14, 6, 8, 13, 6, 5, 15, 13, 11, 11]
_KL = [0x00000000, 0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC, 0xA953FD4E]
_KR = [0x50A28BE6, 0x5C4DD124, 0x6D703EF3, 0x7A6D76E9, 0x00000000]
_MASK = 0xFFFFFFFF


def _rol(x: int, n: int) -> int:
    return ((x << n) | (x >> (32 - n))) & _MASK


def _f(j: int, x: int, y: int, z: int) -> int:
    if j < 16:
        return x ^ y ^ z
    if j < 32:
        return (x & y) | (~x & z)
    if j < 48:
        return (x | ~y) ^ z
    if j < 64:
        return (x & z) | (y & ~z)
    return x ^ (y | ~z)


def ripemd160_pure(msg: bytes) -> bytes:
    """RIPEMD-160 in pure Python. Slow, dependency-free, used only as the fallback."""
    bit_len = len(msg) * 8
    msg = msg + b"\x80"
    while len(msg) % 64 != 56:
        msg += b"\x00"
    msg += struct.pack("<Q", bit_len & 0xFFFFFFFFFFFFFFFF)
    h = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0]
    for off in range(0, len(msg), 64):
        x = struct.unpack("<16I", msg[off:off + 64])
        al, bl, cl, dl, el = h
        ar, br, cr, dr, er = h
        for j in range(80):
            t = _rol((al + _f(j, bl, cl, dl) + x[_RL[j]] + _KL[j // 16]) & _MASK, _SL[j])
            t = (t + el) & _MASK
            al, bl, cl, dl, el = el, t, bl, _rol(cl, 10), dl
            t = _rol((ar + _f(79 - j, br, cr, dr) + x[_RR[j]] + _KR[j // 16]) & _MASK, _SR[j])
            t = (t + er) & _MASK
            ar, br, cr, dr, er = er, t, br, _rol(cr, 10), dr
        h = [(h[1] + cl + dr) & _MASK,
             (h[2] + dl + er) & _MASK,
             (h[3] + el + ar) & _MASK,
             (h[4] + al + br) & _MASK,
             (h[0] + bl + cr) & _MASK]
    return struct.pack("<5I", *h)


def ripemd160(msg: bytes) -> bytes:
    """RIPEMD-160 digest: hashlib if this OpenSSL has it, else the pure-Python fallback."""
    try:
        return hashlib.new("ripemd160", msg).digest()
    except Exception:
        return ripemd160_pure(msg)
