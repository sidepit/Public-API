// Usage: node smoke.mjs [path-to-ccxt-js]  (default ../../../ccxt/js/ccxt.js)
const ccxtPath = process.argv[2] || new URL('../../../ccxt/js/ccxt.js', import.meta.url).pathname;
const ccxt = (await import(ccxtPath)).default;
import http from 'node:http';

// Credentials: set SIDEPIT_ID + SIDEPIT_WIF (or SIDEPIT_SECRET, 64-hex) in the env
// for a funded run. Without them, falls back to a throwaway key (unfunded: engine
// answers RC_ID — still proves sign -> relay -> epoch -> confirmation end to end).
function wifToHex(wif) {
    const ALPHA = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
    let n = 0n;
    for (const c of wif) {
        const i = ALPHA.indexOf(c);
        if (i < 0) throw new Error('bad WIF character');
        n = n * 58n + BigInt(i);
    }
    let hex = n.toString(16);
    if (hex.length % 2) hex = '0' + hex;
    return hex.slice(2, 66); // drop 0x80 version; 32-byte key; ignore flag+checksum
}
const envId = process.env.SIDEPIT_ID;
const envSecret = process.env.SIDEPIT_SECRET || (process.env.SIDEPIT_WIF ? wifToHex(process.env.SIDEPIT_WIF) : undefined);
const funded = Boolean(envId && envSecret);
const ex = new ccxt.sidepit({
    apiKey: funded ? envId : 'bc1qu3vgvcfmdmcrdyy39gk9el5ljdmpzpx8zegmp6',
    secret: funded ? envSecret : 'fc44afdfcb1e641281bdcff8068a15d6cf70bbf16aff04953e58ca2517bf3e62',
    timeout: 20000,
});
console.log('write identity:', funded ? envId + ' (funded, from env)' : 'throwaway (expect RC_ID)');
const readonly = new ccxt.sidepit({ apiKey: envId || 'bc1qlxz2yre0477lzl22ugejyjvygtcdz34f7fv4rt' });
const agent = new http.Agent({ keepAlive: true });
ex.agent = agent; readonly.agent = agent;

const results = [];
async function t(name, fn, expectError = undefined) {
    try {
        const r = await fn();
        if (expectError) { results.push([name, 'FAIL', 'expected ' + expectError]); return; }
        results.push([name, 'PASS', JSON.stringify(r).slice(0, 100)]);
    } catch (e) {
        if (expectError && e.constructor.name === expectError) {
            results.push([name, 'PASS', 'raised ' + expectError + ' as expected']);
        } else {
            results.push([name, 'FAIL', e.constructor.name + ': ' + String(e.message).slice(0, 100)]);
        }
    }
}
const status = await ex.fetchStatus();
const open = status.status === 'ok';
console.log('exchange state:', status.info.state, open ? '(LIVE write tests)' : '(closed-hours expectations)');

await t('fetchTime', () => ex.fetchTime());
await t('fetchStatus', () => ex.fetchStatus());
await t('fetchMarkets', async () => { const m = await ex.fetchMarkets(); return [m.length, m[0].symbol, m[0].inverse, m[0].contractSize]; });
await ex.loadMarkets(); await readonly.loadMarkets();
const sym = Object.keys(ex.markets)[0];
await t('fetchOHLCV', async () => (await ex.fetchOHLCV(sym, '1m', undefined, 3)).slice(-1));
await t('fetchOHLCV(5m->NotSupported)', () => ex.fetchOHLCV(sym, '5m'), 'NotSupported');
await t('fetchBalance', async () => (await readonly.fetchBalance()).BTC);
await t('fetchPositions', () => readonly.fetchPositions());
await t('fetchOpenOrders', () => readonly.fetchOpenOrders());
await t('fetchMyTrades', async () => (await readonly.fetchMyTrades(sym, undefined, 1)).map(x => [x.side, x.price]));
await t('fetchOrder(bogus->OrderNotFound)', () => ex.fetchOrder('bc1qbogus:1'), 'OrderNotFound');
await t('createOrder(market->NotSupported)', () => ex.createOrder(sym, 'market', 'buy', 1), 'NotSupported');

if (open) {
    await t('fetchTicker', async () => { const tk = await ex.fetchTicker(sym); return [tk.bid, tk.ask, tk.last]; });
    await t('fetchOrderBook', async () => { const ob = await ex.fetchOrderBook(sym); return [ob.bids[0], ob.asks[0]]; });
    await t('fetchTrades', async () => (await ex.fetchTrades(sym)).length);
    let oid = null;
    // non-marketable by construction: bid half the best bid (sats-per-USD scale)
    const tkNow = await ex.fetchTicker(sym);
    const ref = tkNow.bid || tkNow.last || 0.00002;
    const deepBuy = ex.priceToPrecision(sym, ref / 2);
    await t('createOrder(limit relay)', async () => {
        const o = await ex.createOrder(sym, 'limit', 'buy', 1, deepBuy);
        oid = o.id; return [o.id.slice(-14), o.status, 'px=' + deepBuy];
    });
    await new Promise(r => setTimeout(r, 2500));   // let the next epoch seal
    await t('order outcome (observational)', async () => {
        try { const o = await ex.fetchOrder(oid); return [o.status, o.info.reject_code]; }
        catch (e) { const rj = await ex.fetchRejections(5); return ['via rejections', rj.map(x => x.code)]; }
    });
    await t('cancelOrder(relay)', async () => (await ex.cancelOrder(oid, sym)).info.tx_type);
    await t('cancel outcome (observational)', async () => {
        let o = null;
        for (let i = 0; i < 4; i++) {           // poll a few epochs, never instant
            await new Promise(r => setTimeout(r, 2000));
            o = await ex.fetchOrder(oid);
            if (o.status !== 'open') break;
        }
        return [o.status, o.info.reject_code];
    });
    await t('fetchRejections', () => ex.fetchRejections(5));
    await t('watchTicker (pro)', async () => {
        const pro = new ccxt.pro.sidepit({ timeout: 15000 });
        pro.agent = agent;
        await pro.loadHttpProxyAgent();   // required by ccxt for non-ssl ws:// (moot once hosted behind TLS/wss)
        await pro.loadMarkets();
        const tk = await pro.watchTicker(sym);
        await pro.close();
        return [tk.symbol, tk.last];
    });
} else {
    await t('fetchTicker(closed->ExchangeNotAvailable)', () => ex.fetchTicker(sym), 'ExchangeNotAvailable');
    await t('fetchOrderBook(closed->ExchangeNotAvailable)', () => ex.fetchOrderBook(sym), 'ExchangeNotAvailable');
    await t('fetchTrades(closed: empty ring)', async () => (await ex.fetchTrades(sym)).length);
    await t('createOrder(closed->ExchangeNotAvailable)', () => ex.createOrder(sym, 'limit', 'buy', 1, 0.00001), 'ExchangeNotAvailable');
    await t('cancelOrder(closed->ExchangeNotAvailable)', () => ex.cancelOrder('bc1qbogus:1', sym), 'ExchangeNotAvailable');
}
for (const [n, s, d] of results) console.log(s.padEnd(5), n.padEnd(38), d);
const fails = results.filter(r => r[1] === 'FAIL').length;
console.log(`---- ${results.length - fails}/${results.length} passed`);
process.exit(fails ? 1 : 0);
