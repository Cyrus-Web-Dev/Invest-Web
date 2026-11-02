from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.jobs import check_alerts_job, sync_prices_job


def build_scheduler() -> AsyncIOScheduler:
    sch = AsyncIOScheduler(timezone="Asia/Jakarta")
    common = dict(max_instances=1, coalesce=True, misfire_grace_time=3600, replace_existing=True)
    # Bursa IDX tutup ~16:00 WIB -> sync 17:00 WIB (Senin-Jumat)
    sch.add_job(sync_prices_job, "cron", args=[True], day_of_week="mon-fri",
                hour=17, minute=0, id="sync_idx", **common)
    # Bursa AS tutup 03:00-04:00 WIB hari berikutnya -> sync 06:00 WIB (Selasa-Sabtu)
    sch.add_job(sync_prices_job, "cron", args=[False], day_of_week="tue-sat",
                hour=6, minute=0, id="sync_global", **common)
    # Alert harga diperiksa tiap 15 menit
    sch.add_job(check_alerts_job, "interval", minutes=15, id="check_alerts", **common)
    return sch
