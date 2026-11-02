"""Pemakaian:
  python -m app.cli make-admin email@contoh.com
  python -m app.cli seed-stocks
  python -m app.cli check-alerts
  python -m app.cli seed-demo [--email E] [--password P] [--reset] [--seed N] [--force]
"""
import asyncio
import secrets
import sys

from sqlalchemy import update

from app.db.session import SessionLocal, engine
from app.core.config import settings
from app.core.redis import redis_client
from app.jobs import check_alerts_job
from app.models import User
from app.seed.catalog import ensure_catalog

USAGE = "Pemakaian: python -m app.cli make-admin EMAIL | seed-stocks | check-alerts"


async def make_admin(email: str) -> int:
    async with SessionLocal() as db:
        res = await db.execute(
            update(User).where(User.email == email.strip().lower()).values(is_admin=True)
        )
        await db.commit()
    return res.rowcount


async def seed_stocks() -> int:
    async with SessionLocal() as db:
        return await ensure_catalog(db)


async def _seed_demo(args: list[str]) -> int:
    from app.demo.seed import DEMO_EMAIL, seed_demo

    opts = {"email": DEMO_EMAIL, "password": None, "reset": False, "seed": 2026, "force": False}
    it = iter(args)
    for a in it:
        if a in ("--email", "--password", "--seed"):
            opts[a[2:]] = next(it, None)
        elif a in ("--reset", "--force"):
            opts[a[2:]] = True
        else:
            print(f"Opsi tidak dikenal: {a}")
            return 2
    if not settings.demo_mode and not opts["force"]:
        print("Menolak: DEMO_MODE tidak aktif. Data demo (harga simulasi) bisa mencemari data nyata.\n"
              "Jalankan lewat stack demo (docker-compose.demo.yml), atau tambahkan --force bila Anda yakin ini database khusus demo.")
        return 3
    password = opts["password"] or secrets.token_urlsafe(9)
    async with SessionLocal() as db:
        try:
            r = await seed_demo(db, opts["email"], password, reset=bool(opts["reset"]), seed=int(opts["seed"]))
        except RuntimeError as e:
            print(f"Gagal: {e}")
            return 1
    print("Data demo dibuat (SEMUA DATA SIMULASI).")
    print(f"  Rentang      : {r['start']} s/d {r['end']}")
    print(f"  Transaksi    : {r['trades']} | arus kas: {r['cashflows']} | dividen: {r['dividends']} | baris harga: {r['price_rows']}")
    print(f"  Setoran total: {r['deposits']:,} | sisa kas: {r['final_cash']:,} | posisi terbuka: {r['holdings']}")
    print(f"  Login        : {r['email']}  /  {password}")
    return 0


async def run(argv: list[str]) -> int:
    try:
        if len(argv) == 3 and argv[1] == "make-admin":
            n = await make_admin(argv[2])
            print(f"Berhasil: {argv[2]} sekarang admin." if n else "Email tidak ditemukan. Daftarkan akun dulu.")
            return 0 if n else 1
        if len(argv) == 2 and argv[1] == "seed-stocks":
            n = await seed_stocks()
            print(f"Katalog saham: {n} saham baru ditambahkan (yang sudah ada dilewati).")
            return 0
        if len(argv) == 2 and argv[1] == "check-alerts":
            await check_alerts_job()
            print("Pemeriksaan alert selesai (lihat log untuk rinciannya).")
            return 0
        if len(argv) >= 2 and argv[1] == "seed-demo":
            return await _seed_demo(argv[2:])
        print(USAGE)
        return 2
    finally:
        await engine.dispose()
        await redis_client.aclose()


if __name__ == "__main__":
    sys.exit(asyncio.run(run(sys.argv)))
