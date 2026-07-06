//  ---------------------------------------------------------------------------

import sidepitRest from '../sidepit.js';
import { ArrayCache, ArrayCacheBySymbolById, ArrayCacheByTimestamp } from '../base/ws/Cache.js';
import type { Int, Order, OrderBook, OHLCV, Str, Ticker, Trade } from '../base/types.js';
import Client from '../base/ws/Client.js';

//  ---------------------------------------------------------------------------

/**
 * Sidepit WS: one gateway socket, tagged JSON events
 * {channel, symbol, address, ts, data}. Subscriptions are ADDITIVE on the gateway
 * (each watch* unions its channel in). The exchange clock is the 1-second epoch:
 * ticker/orderbook tick once per epoch per product; orderbook events are complete
 * snapshots, not diffs.
 */
export default class sidepit extends sidepitRest {
    describe (): any {
        return this.deepExtend (super.describe (), {
            'has': {
                'ws': true,
                'watchTicker': true,
                'watchOrderBook': true,
                'watchTrades': true,
                'watchOHLCV': true,
                'watchOrders': true,
                'watchMyTrades': true,
                'watchBalance': false,
            },
            'urls': {
                'api': {
                    'ws': 'ws://127.0.0.1:8642/ws',
                },
            },
            'options': {
                'tradesLimit': 1000,
                'OHLCVLimit': 1000,
            },
            'streaming': {
                'keepAlive': 30000,
            },
        });
    }

    async subscribe (channel: string, symbol: Str, accountScoped = false, params = {}) {
        const url = this.urls['api']['ws'];
        let messageHash = channel;
        let marketId = undefined;
        if (symbol !== undefined) {
            const market = this.market (symbol);
            marketId = market['id'];
            messageHash = channel + ':' + market['symbol'];
        }
        const request: any = {
            'op': 'subscribe',
            'channels': [ channel ],
        };
        if (accountScoped) {
            request['address'] = this.tradingAddress ();
        }
        let subscriptionHash = channel;
        if (marketId !== undefined) {
            subscriptionHash = channel + ':' + marketId;
        }
        return await this.watch (url, messageHash, request, subscriptionHash);
    }

    /**
     * @method
     * @name sidepit#watchTicker
     * @description one quote per product per 1-second epoch while the exchange is OPEN
     */
    async watchTicker (symbol: string, params = {}): Promise<Ticker> {
        await this.loadMarkets ();
        return await this.subscribe ('ticker', symbol, false, params);
    }

    async watchOrderBook (symbol: string, limit: Int = undefined, params = {}): Promise<OrderBook> {
        await this.loadMarkets ();
        return await this.subscribe ('orderbook', symbol, false, params);
    }

    async watchTrades (symbol: string, since: Int = undefined, limit: Int = undefined, params = {}): Promise<Trade[]> {
        await this.loadMarkets ();
        const trades = await this.subscribe ('trades', symbol, false, params);
        if (this.newUpdates) {
            limit = trades.getLimit (symbol, limit);
        }
        return this.filterBySinceLimit (trades, since, limit, 'timestamp', true);
    }

    async watchOHLCV (symbol: string, timeframe = '1m', since: Int = undefined, limit: Int = undefined, params = {}): Promise<OHLCV[]> {
        await this.loadMarkets ();
        const ohlcv = await this.subscribe ('ohlcv', symbol, false, params);
        if (this.newUpdates) {
            limit = ohlcv.getLimit (symbol, limit);
        }
        return this.filterBySinceLimit (ohlcv, since, limit, 0, true);
    }

    /**
     * @method
     * @name sidepit#watchOrders
     * @description the observational confirmation channel: every state change of YOUR
     * orders as it lands on the order/reject feeds (open / filled / canceled /
     * rejected with RC_* by name). This is how createOrder outcomes are confirmed on
     * a venue where nothing resolves instantly.
     */
    async watchOrders (symbol: Str = undefined, since: Int = undefined, limit: Int = undefined, params = {}): Promise<Order[]> {
        await this.loadMarkets ();
        const orders = await this.subscribe ('orders', symbol, true, params);
        if (this.newUpdates) {
            limit = orders.getLimit (symbol, limit);
        }
        return this.filterBySinceLimit (orders, since, limit, 'timestamp', true);
    }

    async watchMyTrades (symbol: Str = undefined, since: Int = undefined, limit: Int = undefined, params = {}): Promise<Trade[]> {
        await this.loadMarkets ();
        const trades = await this.subscribe ('my_trades', symbol, true, params);
        if (this.newUpdates) {
            limit = trades.getLimit (symbol, limit);
        }
        return this.filterBySinceLimit (trades, since, limit, 'timestamp', true);
    }

    handleMessage (client: Client, message) {
        const op = this.safeString (message, 'op');
        if (op !== undefined) {
            return; // subscribe/unsubscribe acks
        }
        const channel = this.safeString (message, 'channel');
        if (channel === 'ticker') {
            this.handleTicker (client, message);
        } else if (channel === 'orderbook') {
            this.handleOrderBook (client, message);
        } else if (channel === 'trades') {
            this.handleTrade (client, message);
        } else if (channel === 'ohlcv') {
            this.handleOHLCV (client, message);
        } else if (channel === 'orders') {
            this.handleOrder (client, message);
        } else if (channel === 'my_trades') {
            this.handleMyTrade (client, message);
        }
        // 'rejections' events also flip the affected order to 'rejected' on the
        // gateway side, which re-emits on the 'orders' channel — no separate handler
    }

    handleTicker (client: Client, message) {
        const data = this.safeDict (message, 'data', {});
        const ticker = this.parseTicker (data);
        const symbol = ticker['symbol'];
        this.tickers[symbol] = ticker;
        client.resolve (ticker, 'ticker:' + symbol);
    }

    handleOrderBook (client: Client, message) {
        // complete snapshot once per epoch (not a diff stream)
        const data = this.safeDict (message, 'data', {});
        const marketId = this.safeString (data, 'ticker');
        const market = this.safeMarket (marketId);
        const symbol = market['symbol'];
        const timestamp = this.safeInteger (data, 'epoch_ms');
        const snapshot = {
            'symbol': symbol,
            'bids': [],
            'asks': [],
            'timestamp': timestamp,
            'datetime': this.iso8601 (timestamp),
            'nonce': undefined,
        };
        const sideKeys = [ 'bids', 'asks' ];
        for (let k = 0; k < sideKeys.length; k++) {
            const sideKey = sideKeys[k];
            const levels = this.safeList (data, sideKey, []);
            for (let i = 0; i < levels.length; i++) {
                snapshot[sideKey].push ([
                    this.satsToPrice (this.safeInteger (levels[i], 0)),
                    this.safeNumber (levels[i], 1),
                ]);
            }
        }
        if (!(symbol in this.orderbooks)) {
            this.orderbooks[symbol] = this.orderBook ();
        }
        const orderbook = this.orderbooks[symbol];
        orderbook.reset (snapshot);
        client.resolve (orderbook, 'orderbook:' + symbol);
    }

    handleTrade (client: Client, message) {
        const data = this.safeDict (message, 'data', {});
        const trade = this.parseTrade (data);
        const symbol = trade['symbol'];
        if (!(symbol in this.trades)) {
            const limit = this.safeInteger (this.options, 'tradesLimit', 1000);
            this.trades[symbol] = new ArrayCache (limit);
        }
        this.trades[symbol].append (trade);
        client.resolve (this.trades[symbol], 'trades:' + symbol);
    }

    handleOHLCV (client: Client, message) {
        const data = this.safeList (message, 'data', []);
        const marketId = this.safeString (message, 'symbol');
        const market = this.safeMarket (marketId);
        const symbol = market['symbol'];
        const parsed = this.parseOHLCV (data, market);
        this.ohlcvs[symbol] = this.ohlcvs[symbol] || {};
        if (!('1m' in this.ohlcvs[symbol])) {
            const limit = this.safeInteger (this.options, 'OHLCVLimit', 1000);
            this.ohlcvs[symbol]['1m'] = new ArrayCacheByTimestamp (limit);
        }
        const stored = this.ohlcvs[symbol]['1m'];
        stored.append (parsed);
        client.resolve (stored, 'ohlcv:' + symbol);
    }

    handleOrder (client: Client, message) {
        const data = this.safeDict (message, 'data', {});
        const order = this.parseOrder (data);
        if (this.orders === undefined) {
            const limit = this.safeInteger (this.options, 'ordersLimit', 1000);
            this.orders = new ArrayCacheBySymbolById (limit);
        }
        this.orders.append (order);
        client.resolve (this.orders, 'orders');
        client.resolve (this.orders, 'orders:' + order['symbol']);
    }

    handleMyTrade (client: Client, message) {
        const data = this.safeDict (message, 'data', {});
        const trade = this.parseTrade (data);
        if (this.myTrades === undefined) {
            const limit = this.safeInteger (this.options, 'tradesLimit', 1000);
            this.myTrades = new ArrayCache (limit);
        }
        this.myTrades.append (trade);
        client.resolve (this.myTrades, 'my_trades');
        client.resolve (this.myTrades, 'my_trades:' + trade['symbol']);
    }
}
