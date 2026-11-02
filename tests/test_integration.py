"""Tes integrasi: butuh PostgreSQL + Redis yang sudah dimigrasi (alembic upgrade head).
Jalankan di dalam container:  RUN_INTEGRATION=1 pytest tests/test_integration.py -v
Data uji memakai email/simbol acak dan dihapus di akhir. Tidak menyentuh data lain."""
import asyncio
import datetime as _dt
import os
import uuid
from decimal import Decimal as D

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1 untuk menjalankan"
)

PASSWORD = "Passw0rd!123-uji"


async def _scenario():
    from sqlalchemy import delete, select, update

    from app.core.redis import redis_client
    from app.db.session import SessionLocal, engine
    from app.main import app
    from app.models import Stock, User
    from app.services.alert_engine import evaluate_alerts, evaluate_targets

    suffix = uuid.uuid4().hex[:8]
    email = f"it_{suffix}@example.com"
    email2 = f"it2_{suffix}@example.com"
    symbol3 = f"V{suffix}".upper()
    symbol = f"T{suffix}".upper()
    symbol2 = f"U{suffix}".upper()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        try:
            # tanpa token -> 401
            assert (await c.get("/api/v1/portfolio/holdings")).status_code == 401

            r = await c.post("/api/v1/auth/register",
                             json={"email": email, "password": PASSWORD, "full_name": "Uji Integrasi"})
            assert r.status_code == 201, r.text
            assert r.json()["is_admin"] is False

            # login salah -> 401, login benar -> token
            bad = await c.post("/api/v1/auth/login", data={"username": email, "password": "salah-total"})
            assert bad.status_code == 401
            ok = await c.post("/api/v1/auth/login", data={"username": email, "password": PASSWORD})
            assert ok.status_code == 200, ok.text
            h = {"Authorization": f"Bearer {ok.json()['access_token']}"}

            # user biasa tidak boleh menambah saham
            body = {"symbol": symbol, "name": "Saham Uji", "exchange": "IDX", "currency": "IDR", "sector": "Uji"}
            assert (await c.post("/api/v1/stocks", json=body, headers=h)).status_code == 403
            async with SessionLocal() as db:
                await db.execute(update(User).where(User.email == email).values(is_admin=True))
                await db.commit()
            r = await c.post("/api/v1/stocks", json=body, headers=h)
            assert r.status_code == 201, r.text
            stock_id = r.json()["id"]

            # setor 1000
            r = await c.post("/api/v1/portfolio/cash", json={"type": "DEPOSIT", "amount": "1000"}, headers=h)
            assert r.status_code == 200 and D(r.json()["cash_balance"]) == D("1000")

            # DUA pembelian bersamaan @600: hanya SATU yang boleh lolos (uji kunci baris)
            buy = {"stock_id": stock_id, "type": "BUY", "quantity": "6", "price": "100", "fee": "0"}
            res = await asyncio.gather(
                c.post("/api/v1/portfolio/transactions", json=buy, headers=h),
                c.post("/api/v1/portfolio/transactions", json=buy, headers=h),
            )
            codes = sorted(x.status_code for x in res)
            assert codes == [201, 400], codes
            me = (await c.get("/api/v1/auth/me", headers=h)).json()
            assert D(me["cash_balance"]) == D("400")

            # jual berlebih ditolak; jual 3 @110 diterima
            over = {"stock_id": stock_id, "type": "SELL", "quantity": "10", "price": "110", "fee": "0"}
            assert (await c.post("/api/v1/portfolio/transactions", json=over, headers=h)).status_code == 400
            sell = {"stock_id": stock_id, "type": "SELL", "quantity": "3", "price": "110", "fee": "0"}
            assert (await c.post("/api/v1/portfolio/transactions", json=sell, headers=h)).status_code == 201

            hold = (await c.get("/api/v1/portfolio/holdings", headers=h)).json()
            assert len(hold) == 1 and D(hold[0]["quantity"]) == D("3") and D(hold[0]["avg_cost"]) == D("100")

            # ringkasan: kas 730 + saham (belum ada harga -> nilai modal 300) = 1030; P/L 30
            t = (await c.get("/api/v1/analytics/summary", headers=h)).json()["totals"]
            assert D(t["cash"]) == D("730") and D(t["net_worth"]) == D("1030")
            assert D(t["net_deposits"]) == D("1000") and D(t["total_pl"]) == D("30")

            # watchlist (idempoten) + alert harga + notifikasi
            for _ in range(2):
                r = await c.post("/api/v1/watchlist", json={"stock_id": stock_id}, headers=h)
                assert r.status_code == 201, r.text
            wl = (await c.get("/api/v1/watchlist", headers=h)).json()
            assert len(wl) == 1 and wl[0]["symbol"] == symbol
            r = await c.post("/api/v1/alerts", headers=h,
                             json={"stock_id": stock_id, "direction": "BELOW", "target_price": "50"})
            assert r.status_code == 201, r.text
            async with SessionLocal() as db:
                st = await db.scalar(select(Stock).where(Stock.symbol == symbol))
                assert await evaluate_alerts(db, st, D("60")) == 0     # belum memenuhi syarat
                assert await evaluate_alerts(db, st, D("40")) == 1     # terpicu
                assert await evaluate_alerts(db, st, D("40")) == 0     # tidak terpicu dua kali
            nt = (await c.get("/api/v1/notifications", headers=h)).json()
            assert nt["unread"] == 1 and symbol in nt["items"][0]["message"]
            assert (await c.post("/api/v1/notifications/read-all", headers=h)).status_code == 200
            assert (await c.get("/api/v1/notifications", headers=h)).json()["unread"] == 0

            # target harga & stop loss: validasi, metrik, pemicu sekali, hapus
            r = await c.put(f"/api/v1/targets/{stock_id}", json={"target_price": "90", "stop_price": "95"}, headers=h)
            assert r.status_code == 422, r.text                       # stop harus di bawah target
            r = await c.put(f"/api/v1/targets/{stock_id}", json={"target_price": "150", "stop_price": "90"}, headers=h)
            assert r.status_code == 200, r.text
            tg = (await c.get("/api/v1/targets", headers=h)).json()
            assert len(tg) == 1 and D(tg[0]["risk_reward"]) == D("5.00") and D(tg[0]["quantity"]) == D("3")
            async with SessionLocal() as db:
                st = await db.scalar(select(Stock).where(Stock.symbol == symbol))
                assert await evaluate_targets(db, st, D("95")) == 0
                assert await evaluate_targets(db, st, D("160")) == 1  # target tercapai
                assert await evaluate_targets(db, st, D("160")) == 0  # hanya sekali
            nt = (await c.get("/api/v1/notifications", headers=h)).json()
            assert nt["unread"] == 1 and "Target harga" in nt["items"][0]["title"]
            await c.post("/api/v1/notifications/read-all", headers=h)
            assert (await c.delete(f"/api/v1/targets/{stock_id}", headers=h)).status_code == 200
            assert (await c.get("/api/v1/targets", headers=h)).json() == []

            # impor CSV bertanggal mundur: pratinjau -> impor -> tolak file duplikat -> tolak file tak valid
            body2 = {"symbol": symbol2, "name": "Saham Uji 2", "exchange": "IDX", "currency": "IDR", "sector": "Uji"}
            r = await c.post("/api/v1/stocks", json=body2, headers=h)
            assert r.status_code == 201, r.text
            stock_id2 = r.json()["id"]
            csv_text = (
                "tanggal,jenis,simbol,jumlah,harga,fee,nominal,catatan\n"
                "2024-01-02,SETOR,,,,,5000,modal awal\n"
                f"2024-01-03,BELI,{symbol2},10,100,0,,\n"
                f"2024-02-01,BELI,{symbol2},10,200,0,,\n"
                f"2024-03-01,JUAL,{symbol2},5,300,0,,\n"
                f"2024-03-02,DIVIDEN,{symbol2},,,,25,\n"
            )
            files = {"file": ("uji.csv", csv_text.encode(), "text/csv")}
            rep = (await c.post("/api/v1/portfolio/import?dry_run=true", files=files, headers=h)).json()
            assert rep["ok"] and not rep["committed"], rep
            assert D(rep["cash_effect"]) == D("3525")
            rep = (await c.post("/api/v1/portfolio/import?dry_run=false", files=files, headers=h)).json()
            assert rep["ok"] and rep["committed"], rep
            assert D((await c.get("/api/v1/auth/me", headers=h)).json()["cash_balance"]) == D("4255")
            hold = {x["symbol"]: x for x in (await c.get("/api/v1/portfolio/holdings", headers=h)).json()}
            assert D(hold[symbol2]["quantity"]) == D("15") and D(hold[symbol2]["avg_cost"]) == D("150")
            rep = (await c.post("/api/v1/portfolio/import?dry_run=false", files=files, headers=h)).json()
            assert not rep["ok"] and rep["duplicate"], rep
            bad = ("tanggal,jenis,simbol,jumlah,harga,fee,nominal,catatan\n"
                   f"2023-01-01,JUAL,{symbol2},1,100,0,,\n")
            rep = (await c.post("/api/v1/portfolio/import?dry_run=false", headers=h,
                                files={"file": ("buruk.csv", bad.encode(), "text/csv")})).json()
            assert not rep["ok"] and rep["errors"], rep
            assert D((await c.get("/api/v1/auth/me", headers=h)).json()["cash_balance"]) == D("4255")
            r = await c.get("/api/v1/export/transactions.csv", headers=h)
            assert r.status_code == 200 and symbol2 in r.text

            # analitik dividen (dividen 25 dari impor tahun 2024)
            dv = (await c.get("/api/v1/analytics/dividends", headers=h)).json()
            assert D(dv["total_all_time"]) == D("25") and D(dv["last_12m"]) == D("0")
            assert any(x["symbol"] == symbol2 for x in dv["by_stock"]) and len(dv["monthly"]) == 24
            assert len(dv["calendar"]) == 12

            # atribusi: jumlah kontribusi tiap saham = total untung/rugi; return bulanan
            at = (await c.get("/api/v1/analytics/attribution", headers=h)).json()
            assert abs(D(at["residual"])) < D("1"), at["residual"]
            assert {r["symbol"] for r in at["rows"]} >= {symbol, symbol2}
            assert abs(sum(D(r["total"]) for r in at["rows"]) - D(at["total_pl"])) < D("1")
            mo = await c.get("/api/v1/analytics/monthly", headers=h)
            assert mo.status_code == 200 and "rows" in mo.json() and mo.json()["total_months"] >= 0

            # laporan tahunan 2024 (dari impor: jual 5 @300 dari rata-rata 150; dividen 25)
            rp = (await c.get("/api/v1/reports/annual?year=2024", headers=h)).json()
            assert D(rp["totals"]["gross_sales"]) == D("1500") and D(rp["totals"]["realized_pl"]) == D("750"), rp["totals"]
            assert D(rp["totals"]["dividends"]) == D("25") and rp["totals"]["sales_count"] == 1
            assert any(p["symbol"] == symbol2 and D(p["quantity"]) == D("15") for p in rp["positions"])
            assert 2024 in (await c.get("/api/v1/reports/years", headers=h)).json()
            pdf = await c.get("/api/v1/reports/annual.pdf?year=2024", headers=h)
            assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and "pdf" in pdf.headers["content-type"]
            csvr = await c.get("/api/v1/reports/realized.csv?year=2024", headers=h)
            assert csvr.status_code == 200 and symbol2 in csvr.text

            # user biasa menambah saham sendiri (divalidasi penyedia harga; penyedia dipalsukan di tes)
            from app.services.price_providers.base import PriceBar
            from app.services.price_providers.yahoo import get_provider

            class FakeProvider:
                async def fetch_history(self, sym, start, end):
                    return []

                async def fetch_latest(self, sym):
                    return PriceBar(_dt.date(2026, 1, 2), D("1"), D("1"), D("1"), D("1"), 0) if sym == symbol3 else None

            app.dependency_overrides[get_provider] = lambda: FakeProvider()
            r = await c.post("/api/v1/auth/register", json={"email": email2, "password": PASSWORD, "full_name": "Uji Dua"})
            assert r.status_code == 201, r.text
            tok2 = (await c.post("/api/v1/auth/login", data={"username": email2, "password": PASSWORD})).json()["access_token"]
            h2 = {"Authorization": f"Bearer {tok2}"}
            mine = {"symbol": symbol3, "name": "Saham Uji 3", "exchange": "IDX", "currency": "IDR", "sector": None}
            assert (await c.post("/api/v1/stocks", json=mine, headers=h2)).status_code == 201
            assert (await c.post("/api/v1/stocks", json=mine, headers=h2)).status_code == 409
            nope = dict(mine, symbol=f"X{suffix}".upper())
            assert (await c.post("/api/v1/stocks", json=nope, headers=h2)).status_code == 422   # tidak ada di penyedia
            assert (await c.post("/api/v1/stocks", json=dict(mine, symbol=f"Y{suffix}".upper(), kind="INDEX"), headers=h2)).status_code == 403
            assert any(x["symbol"] == symbol3 for x in (await c.get("/api/v1/stocks?q=" + symbol3, headers=h2)).json())

            # buku besar: tambah bertanggal mundur, ubah, hapus (divalidasi ulang kronologis)
            async def cash_now():
                return D((await c.get("/api/v1/auth/me", headers=h)).json()["cash_balance"])

            r = await c.post("/api/v1/portfolio/cash", headers=h,
                             json={"type": "DEPOSIT", "amount": "100", "date": "2024-01-01"})
            assert r.status_code == 200, r.text
            assert await cash_now() == D("4355")
            early = {"stock_id": stock_id2, "type": "BUY", "quantity": "1", "price": "150", "fee": "0", "date": "2024-01-01"}
            r = await c.post("/api/v1/portfolio/transactions", json=early, headers=h)
            assert r.status_code == 400 and "Saldo kas" in r.text, r.text   # kas 100 < 150 pada tanggal itu
            assert await cash_now() == D("4355")
            early["price"] = "90"
            r = await c.post("/api/v1/portfolio/transactions", json=early, headers=h)
            assert r.status_code == 201, r.text
            early_id = r.json()["id"]
            assert await cash_now() == D("4265")
            hold = {x["symbol"]: x for x in (await c.get("/api/v1/portfolio/holdings", headers=h)).json()}
            assert D(hold[symbol2]["quantity"]) == D("16")
            assert abs(D(hold[symbol2]["avg_cost"]) - D("147.1429")) < D("0.001")   # dihitung kronologis

            r = await c.patch(f"/api/v1/portfolio/transactions/{early_id}", json={"quantity": "2"}, headers=h)
            assert r.status_code == 400, r.text                                     # 2 x 90 > kas 100
            r = await c.patch(f"/api/v1/portfolio/transactions/{early_id}", json={"price": "80"}, headers=h)
            assert r.status_code == 200 and r.json()["price"] in ("80", "80.0000"), r.text
            assert await cash_now() == D("4275")

            led = (await c.get("/api/v1/portfolio/ledger?type=DEPOSIT&limit=50", headers=h)).json()["items"]
            dep = next(i for i in led if i["day"] == "2024-01-01")
            r = await c.delete(f"/api/v1/portfolio/cash/{dep['id']}", headers=h)
            assert r.status_code == 400 and "sudah ada" in r.text, r.text           # pembelian awal jadi tak valid
            assert (await c.delete(f"/api/v1/portfolio/transactions/{early_id}", headers=h)).status_code == 200
            assert await cash_now() == D("4355")
            assert (await c.delete(f"/api/v1/portfolio/cash/{dep['id']}", headers=h)).status_code == 200
            assert await cash_now() == D("4255")                                    # kembali ke keadaan awal
            page = (await c.get("/api/v1/portfolio/ledger?limit=5", headers=h)).json()
            assert page["total"] >= 5 and len(page["items"]) == 5

            # tag & jurnal
            tr = {"stock_id": stock_id, "type": "BUY", "quantity": "1", "price": "100", "fee": "0",
                  "note": "tesis uji", "tags": ["Value", "jangka panjang"]}
            r = await c.post("/api/v1/portfolio/transactions", json=tr, headers=h)
            assert r.status_code == 201 and r.json()["tags"] == ["value", "jangka-panjang"], r.text
            assert (await c.post("/api/v1/portfolio/transactions", json=dict(tr, tags=["tag@salah"]), headers=h)).status_code == 422
            led = (await c.get("/api/v1/portfolio/ledger?tag=value", headers=h)).json()
            assert led["total"] == 1 and led["items"][0]["tags"] == ["value", "jangka-panjang"]
            jr = (await c.get("/api/v1/analytics/journal", headers=h)).json()
            assert any(t["tag"] == "value" and t["count"] == 1 for t in jr["tags"])
            assert (await c.get("/api/v1/auth/me", headers=h)).json()["is_demo"] is False

            # benchmark & risiko
            bm = (await c.get("/api/v1/analytics/benchmarks", headers=h)).json()
            assert {b["symbol"] for b in bm} >= {"^JKSE", "^GSPC"}
            cmp_ = await c.get(f"/api/v1/analytics/benchmark?benchmark_id={bm[0]['id']}&days=365", headers=h)
            assert cmp_.status_code == 200 and "points" in cmp_.json()
            rk = await c.get(f"/api/v1/analytics/risk?days=365&benchmark_id={bm[0]['id']}", headers=h)
            assert rk.status_code == 200, rk.text
            assert rk.json()["diversification"] is not None and rk.json()["observations"] >= 0
            assert (await c.get("/api/v1/analytics/risk?benchmark_id=999999999", headers=h)).status_code == 404
            idx_trade = {"stock_id": bm[0]["id"], "type": "BUY", "quantity": "1", "price": "1", "fee": "0"}
            r = await c.post("/api/v1/portfolio/transactions", json=idx_trade, headers=h)
            assert r.status_code == 400 and "Indeks" in r.text      # indeks tidak bisa diperdagangkan
            assert all(x["symbol"] not in ("^JKSE", "^GSPC")
                       for x in (await c.get("/api/v1/stocks", headers=h)).json())

            # nilai di luar batas ditolak validasi (bukan 500)
            huge = {"stock_id": stock_id, "type": "BUY", "quantity": "1", "price": "99999999999", "fee": "0"}
            assert (await c.post("/api/v1/portfolio/transactions", json=huge, headers=h)).status_code == 422
        finally:
            app.dependency_overrides.clear()
            async with SessionLocal() as db:
                await db.execute(delete(User).where(User.email.in_([email, email2])))   # transaksi ikut terhapus (CASCADE)
                await db.execute(delete(Stock).where(Stock.symbol.in_([symbol, symbol2, symbol3])))
                await db.commit()
            await redis_client.delete(f"login:fail:127.0.0.1:{email}")
    await engine.dispose()
    await redis_client.aclose()


def test_full_flow():
    asyncio.run(_scenario())
