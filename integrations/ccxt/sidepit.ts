//  ---------------------------------------------------------------------------

import Exchange from './abstract/sidepit.js';
import { AuthenticationError, BadRequest, BadSymbol, ExchangeError, ExchangeNotAvailable, InsufficientFunds, InvalidNonce, InvalidOrder, NotSupported, OrderNotFound } from './base/errors.js';
import { Precise } from './base/Precise.js';
import { TICK_SIZE } from './base/functions/number.js';
import { ecdsa } from './base/functions/crypto.js';
import { sha256 } from './static_dependencies/noble-hashes/sha256.js';
import { secp256k1 } from './static_dependencies/noble-curves/secp256k1.js';
import type { Balances, Dict, Int, Market, Num, OHLCV, Order, OrderBook, OrderSide, OrderType, Position, Str, Strings, Ticker, Trade } from './base/types.js';

//  ---------------------------------------------------------------------------

/**
 * @class sidepit
 * @augments Exchange
 *
 * Sidepit is a deterministic one-second auction forwards venue (sequenced-batch CLOB,
 * NOT continuous matching and NOT a frequent batch auction) trading Bitcoin-margined
 * dated USD forwards. Native prices are SATS-PER-USD (inverse). This class converts
 * once at the boundary: unified prices are BTC-per-USD = sats * 1e-8.
 *
 * Identity is a Bitcoin key: apiKey = the account's bc1q address (sidepit_id /
 * custody), secret = the 64-hex secp256k1 private key of the signing key. In
 * delegate (hot/cold) mode set options.traderId to the hot key's bc1q address.
 *
 * The write path is non-custodial: this class serializes the Transaction protobuf
 * itself, signs it (SHA256 -> secp256k1 ECDSA compact -> hex, signature_version=0),
 * and POSTs the signed bytes to the gateway relay. The gateway holds no keys.
 *
 * Orders NEVER resolve instantly: outcomes are decided at the next 1-second epoch
 * and confirmed observationally (order feed / reject feed). createOrder returns
 * status 'open' optimistically; poll fetchOrder / fetchOpenOrders or use watchOrders.
 */
export default class sidepit extends Exchange {
    describe (): any {
        return this.deepExtend (super.describe (), {
            'id': 'sidepit',
            'name': 'Sidepit',
            'countries': [ 'US' ],
            'version': 'v1',
            'rateLimit': 50,
            'certified': false,
            'pro': true,
            'dex': false,
            'has': {
                'CORS': undefined,
                'spot': false,
                'margin': false,
                'swap': false,
                'future': true,
                'option': false,
                'cancelOrder': true,
                'createMarketBuyOrderWithCost': false,
                'createMarketOrder': false, // fills are salt-dependent under per-epoch sequencing; limit only
                'createMarketSellOrderWithCost': false,
                'createOrder': true,
                'createStopOrder': false,
                'fetchBalance': true,
                'fetchClosedOrders': false,
                'fetchCurrencies': false,
                'fetchDepositAddress': false,
                'fetchFundingHistory': false,
                'fetchFundingRate': false, // dated future: no funding, basis converges at expiry
                'fetchFundingRates': false,
                'fetchLeverage': false,
                'fetchMarkets': true,
                'fetchMyTrades': true,
                'fetchOHLCV': true,
                'fetchOpenInterest': false,
                'fetchOpenOrders': true,
                'fetchOrder': true,
                'fetchOrderBook': true,
                'fetchPositions': true,
                'fetchStatus': true,
                'fetchTicker': true,
                'fetchTickers': false,
                'fetchTime': true,
                'fetchTrades': true,
                'setLeverage': false, // leverage is implicit: position size vs margin
            },
            'timeframes': {
                '1m': '1m', // the venue aggregates 1-minute bars; no other timeframe exists
            },
            'urls': {
                'logo': 'https://app.sidepit.com/logo.png',
                'api': {
                    'public': 'http://127.0.0.1:8642',
                    'private': 'http://127.0.0.1:8642',
                },
                'www': 'https://sidepit.com',
                'doc': [
                    'https://github.com/sidepit/Public-API',
                    'https://docs.sidepit.com',
                ],
            },
            'api': {
                'public': {
                    'get': {
                        'time': 1,
                        'status': 1,
                        'markets': 1,
                        'nonce': 1,
                        'ticker/{symbol}': 1,
                        'orderbook/{symbol}': 1,
                        'trades/{symbol}': 1,
                        'ohlcv/{symbol}': 1,
                        'balance/{address}': 1,
                        'positions/{address}': 1,
                        'open_orders/{address}': 1,
                        'orders/{orderid}': 1,
                        'my_trades/{address}': 1,
                        'rejections/{address}': 1,
                    },
                    'post': {
                        'relay': 1,
                    },
                },
            },
            'requiredCredentials': {
                'apiKey': true,     // the account's bc1q address (sidepit_id)
                'secret': false,    // 64-hex secp256k1 private key; required for trading only
            },
            'precisionMode': TICK_SIZE,
            'options': {
                'traderId': undefined,  // delegate (hot key) bc1q address; empty = direct mode
                'sandboxMode': false,
                'networks': {},
                // RejectCode (by NAME, never integer) -> error semantics. 'expected'
                // codes are normal business outcomes on this venue, not malfunctions.
                'rejectCodes': {
                    'RC_VERIFY': { 'error': 'AuthenticationError', 'expected': false },
                    'RC_DUP': { 'error': 'InvalidNonce', 'expected': false },
                    'RC_ID': { 'error': 'AuthenticationError', 'expected': false },
                    'RC_BAD': { 'error': 'BadRequest', 'expected': false },
                    'RC_REDUCE': { 'error': 'InvalidOrder', 'expected': true },
                    'RC_MARGIN': { 'error': 'InsufficientFunds', 'expected': true },
                    'RC_DK': { 'error': 'BadSymbol', 'expected': false },
                    'RC_CDUP': { 'error': 'OrderNotFound', 'expected': true },
                    'RC_CREJ': { 'error': 'OrderNotFound', 'expected': true },
                    'RC_OTHER': { 'error': 'ExchangeError', 'expected': false },
                },
            },
            'exceptions': {
                'exact': {
                    'RC_VERIFY': AuthenticationError,
                    'RC_DUP': InvalidNonce,
                    'RC_ID': AuthenticationError,
                    'RC_BAD': BadRequest,
                    'RC_REDUCE': InvalidOrder,
                    'RC_MARGIN': InsufficientFunds,
                    'RC_DK': BadSymbol,
                    'RC_CDUP': OrderNotFound,
                    'RC_CREJ': OrderNotFound,
                    'RC_OTHER': ExchangeError,
                },
                'broad': {
                    // feeds are silent while the exchange is CLOSED (daily session
                    // cycle) — that is unavailability, not a bad symbol
                    'no live': ExchangeNotAvailable,
                    'not accepting transactions': ExchangeNotAvailable,
                    'unknown orderid': OrderNotFound,
                    'limit orders only': InvalidOrder,
                    'read-only': AuthenticationError,
                    'must be positive': BadRequest,
                },
            },
        });
    }

    sign (path, api = 'public', method = 'GET', params = {}, headers = undefined, body = undefined) {
        let url = this.urls['api'][api] + '/' + this.implodeParams (path, params);
        const query = this.omit (params, this.extractParams (path));
        if (method === 'GET') {
            if (Object.keys (query).length) {
                url += '?' + this.urlencode (query);
            }
        } else {
            body = this.json (query);
            headers = { 'Content-Type': 'application/json' };
        }
        return { 'url': url, 'method': method, 'body': body, 'headers': headers };
    }

    handleErrors (code, reason, url, method, headers, body, response, requestHeaders, requestBody) {
        if (response === undefined) {
            return undefined;
        }
        const detail = this.safeString (response, 'detail');
        if (detail !== undefined && code !== undefined && code >= 400) {
            const feedback = this.id + ' ' + detail;
            this.throwBroadlyMatchedException (this.exceptions['broad'], detail, feedback);
            throw new ExchangeError (feedback);
        }
        return undefined;
    }

    /**
     * Native prices are integer sats-per-USD. Unified prices are BTC-per-USD.
     * These two helpers are the single conversion boundary in this class.
     */
    satsToPrice (sats) {
        if (sats === undefined || sats === 0) {
            return undefined;
        }
        return this.parseNumber (Precise.stringDiv (this.numberToString (sats), '100000000'));
    }

    priceToSats (symbol: string, price) {
        const priceString = this.priceToPrecision (symbol, price);
        return this.parseToInt (Precise.stringMul (priceString, '100000000'));
    }

    tradingAddress (): string {
        this.checkRequiredCredentials ();
        return this.apiKey; // the custody sidepit_id; bc1q address, never derived from a hardcoded constant
    }

    /**
     * client-side signing (custody model B): protobuf serialization + ECDSA.
     * Byte-exact mirror of Public-API sidepit_trader/signer.py + the proto:
     * Transaction{version=1, timestamp=10, new_order=20|cancel_orderid=30, sidepit_id=101, agent_id=102};
     * NewOrder{side=11 (sint32 zigzag), size=20, price=30, ticker=40};
     * SignedTransaction{signature_version=2 (0 -> omitted), transaction=11, signature=111};
     * digest = SHA256(serialized Transaction) -> ECDSA secp256k1 compact (low-s) -> hex; signature_version=0
     */
    pbVarint (value) {
        // value: integer Number (safe for tags/sizes/prices) — NOT for ns timestamps
        const out = [];
        let v = value;
        while (v >= 128) {
            out.push ((v % 128) + 128);
            v = Math.floor (v / 128);
        }
        out.push (v);
        return out;
    }

    pbVarintDecimal (decimal: string) {
        // varint of an arbitrary-size non-negative integer given as a decimal STRING
        // (nanosecond timestamps exceed JS safe-integer range; string math via Precise)
        const out = [];
        let v = decimal;
        while (Precise.stringGe (v, '128')) {
            const rem = Precise.stringMod (v, '128');
            out.push (this.parseToInt (rem) + 128);
            v = Precise.stringDiv (v, '128', 0);
        }
        out.push (this.parseToInt (v));
        return out;
    }

    pbTag (fieldNumber, wireType) {
        return this.pbVarint (fieldNumber * 8 + wireType);
    }

    pbString (fieldNumber, value: string) {
        const bytes = this.encode (value); // utf-8
        const out = this.pbTag (fieldNumber, 2).concat (this.pbVarint (bytes.length));
        for (let i = 0; i < bytes.length; i++) {
            out.push (bytes[i]);
        }
        return out;
    }

    pbSubmessage (fieldNumber, payload) {
        return this.pbTag (fieldNumber, 2).concat (this.pbVarint (payload.length), payload);
    }

    serializeNewOrder (side: number, size: number, price: number, ticker: string) {
        // NewOrder: side=11 sint32 (zigzag: 1 -> 2, -1 -> 1), size=20, price=30, ticker=40
        const zigzag = (side >= 0) ? (2 * side) : (-2 * side - 1);
        let out = this.pbTag (11, 0).concat (this.pbVarint (zigzag));
        out = out.concat (this.pbTag (20, 0), this.pbVarint (size));
        out = out.concat (this.pbTag (30, 0), this.pbVarint (price));
        out = out.concat (this.pbString (40, ticker));
        return out;
    }

    serializeTransaction (timestampNsDecimal: string, payloadField: number, payload, sidepitId: string, traderId: Str = undefined) {
        // fields in ascending order, proto3 default-omission (version=1 always set)
        let out = this.pbTag (1, 0).concat (this.pbVarint (1));                  // version = 1
        out = out.concat (this.pbTag (10, 0), this.pbVarintDecimal (timestampNsDecimal)); // timestamp ns
        if (payloadField === 30) {
            out = out.concat (this.pbString (30, payload));                      // cancel_orderid
        } else {
            out = out.concat (this.pbSubmessage (payloadField, payload));        // new_order = 20
        }
        out = out.concat (this.pbString (101, sidepitId));
        if (traderId !== undefined && traderId !== '') {
            out = out.concat (this.pbString (102, traderId));                    // delegate mode
        }
        return out;
    }

    signSerializedTransaction (txBytes) {
        // SHA256 over the EXACT serialized bytes -> ECDSA secp256k1 compact -> hex
        const digestHex = this.hash (this.byteArrayToUint8 (txBytes), sha256, 'hex');
        const signature = ecdsa (digestHex, this.secret, secp256k1, undefined);
        const compact = signature['r'].padStart (64, '0') + signature['s'].padStart (64, '0');
        // SignedTransaction: signature_version (field 2) is 0 -> proto3 omits it
        const stx = this.pbSubmessage (11, txBytes).concat (this.pbString (111, compact));
        return this.bytesToHexString (stx);
    }

    byteArrayToUint8 (arr) {
        const out = new Uint8Array (arr.length);
        for (let i = 0; i < arr.length; i++) {
            out[i] = arr[i];
        }
        return out;
    }

    bytesToHexString (arr) {
        let out = '';
        for (let i = 0; i < arr.length; i++) {
            out += arr[i].toString (16).padStart (2, '0');
        }
        return out;
    }

    nonceNs (): string {
        // strictly increasing NANOSECOND timestamp as a decimal string (the orderid
        // nonce). ms * 1e6 + counter; the counter guarantees strict monotonicity.
        const ms = this.milliseconds ();
        const last = this.safeString (this.options, 'lastNonceNs', '0');
        let next = Precise.stringMul (this.numberToString (ms), '1000000');
        if (Precise.stringLe (next, last)) {
            next = Precise.stringAdd (last, '1');
        }
        this.options['lastNonceNs'] = next;
        return next;
    }

    /**
     * @method
     * @name sidepit#fetchMarkets
     * @description retrieves data on all markets for sidepit
     * @see https://github.com/sidepit/Public-API
     */
    async fetchMarkets (params = {}): Promise<Market[]> {
        const response = await this.publicGetMarkets (params);
        const markets = this.safeList (response, 'markets', []);
        return this.parseMarkets (markets);
    }

    parseMarket (market: Dict): Market {
        // base/quote/settle are EXPLICIT from the gateway — never inferred:
        // USD priced in satoshis, margined and settled in BTC; inverse DATED future.
        const id = this.safeString (market, 'id');
        const base = this.safeString (market, 'base');       // 'USD'
        const quote = this.safeString (market, 'quote');     // 'BTC'
        const settle = this.safeString (market, 'settle');   // 'BTC'
        const expiry = this.safeInteger (market, 'expiry_ms');
        const symbol = base + '/' + quote + ':' + settle + '-' + this.yymmdd (expiry);
        const tickSizeSats = this.safeString (market, 'tick_size_sats');
        return this.safeMarketStructure ({
            'id': id,
            'symbol': symbol,
            'base': base,
            'quote': quote,
            'settle': settle,
            'baseId': base,
            'quoteId': quote,
            'settleId': settle,
            'type': 'future',
            'spot': false,
            'margin': false,
            'swap': false,
            'future': true,
            'option': false,
            'active': this.safeBool (market, 'active'),
            'contract': true,
            'linear': false,
            'inverse': true,   // price is sats-per-USD: rising price = falling BTC/USD
            'contractSize': this.safeNumber (market, 'contract_size_usd'),
            'expiry': expiry,
            'expiryDatetime': this.iso8601 (expiry),
            'strike': undefined,
            'optionType': undefined,
            'precision': {
                'amount': this.safeNumber (market, 'amount_step'), // whole contracts
                'price': this.parseNumber (Precise.stringDiv (tickSizeSats, '100000000')),
            },
            'limits': {
                'leverage': { 'min': undefined, 'max': undefined },
                'amount': {
                    'min': this.safeNumber (market, 'min_amount'),
                    'max': this.safeNumber (market, 'max_position'),
                },
                'price': { 'min': undefined, 'max': undefined },
                'cost': { 'min': undefined, 'max': undefined },
            },
            'created': this.safeInteger (market, 'start_ms'),
            'info': market,
        });
    }

    async fetchTime (params = {}): Promise<Int> {
        const response = await this.publicGetTime (params);
        return this.safeInteger (response, 'ms');
    }

    async fetchStatus (params = {}) {
        const response = await this.publicGetStatus (params);
        const state = this.safeString (response, 'state');
        // EXCHANGE_OPEN is the only state in which orders are accepted; the venue
        // runs a daily session cycle (see docs/exchange-states.md)
        const status = (state === 'EXCHANGE_OPEN') ? 'ok' : 'maintenance';
        return {
            'status': status,
            'updated': undefined,
            'eta': undefined,
            'url': undefined,
            'info': response,
        };
    }

    /**
     * @method
     * @name sidepit#fetchTicker
     * @description latest quote for a market (live only while the exchange is OPEN)
     */
    async fetchTicker (symbol: string, params = {}): Promise<Ticker> {
        await this.loadMarkets ();
        const market = this.market (symbol);
        const request: Dict = { 'symbol': market['id'] };
        const response = await this.publicGetTickerSymbol (this.extend (request, params));
        return this.parseTicker (response, market);
    }

    parseTicker (ticker: Dict, market: Market = undefined): Ticker {
        const timestamp = this.safeInteger (ticker, 'epoch_ms');
        return this.safeTicker ({
            'symbol': this.safeSymbol (this.safeString (ticker, 'ticker'), market),
            'timestamp': timestamp,
            'datetime': this.iso8601 (timestamp),
            'bid': this.satsToPrice (this.safeInteger (ticker, 'bid')),
            'bidVolume': this.safeNumber (ticker, 'bidsize'),
            'ask': this.satsToPrice (this.safeInteger (ticker, 'ask')),
            'askVolume': this.safeNumber (ticker, 'asksize'),
            'last': this.satsToPrice (this.safeInteger (ticker, 'last')),
            'high': undefined,  // CAUTION: native (sats-per-USD) high/low INVERT vs USD;
            'low': undefined,   // left undefined rather than flattening the inversion
            'open': undefined,
            'close': this.satsToPrice (this.safeInteger (ticker, 'last')),
            'previousClose': undefined,
            'change': undefined,
            'percentage': undefined,
            'average': undefined,
            'baseVolume': undefined,
            'quoteVolume': undefined,
            'vwap': undefined,
            'info': ticker,
        }, market);
    }

    async fetchOrderBook (symbol: string, limit: Int = undefined, params = {}): Promise<OrderBook> {
        await this.loadMarkets ();
        const market = this.market (symbol);
        const request: Dict = { 'symbol': market['id'] };
        const response = await this.publicGetOrderbookSymbol (this.extend (request, params));
        const timestamp = this.safeInteger (response, 'epoch_ms');
        const result = {
            'symbol': market['symbol'],
            'bids': [],
            'asks': [],
            'timestamp': timestamp,
            'datetime': this.iso8601 (timestamp),
            'nonce': undefined,
        };
        const sideKeys = [ 'bids', 'asks' ];
        for (let k = 0; k < sideKeys.length; k++) {
            const sideKey = sideKeys[k];
            const levels = this.safeList (response, sideKey, []);
            for (let i = 0; i < levels.length; i++) {
                const price = this.satsToPrice (this.safeInteger (levels[i], 0));
                const amount = this.safeNumber (levels[i], 1);
                result[sideKey].push ([ price, amount ]);
            }
        }
        return result as any;
    }

    async fetchTrades (symbol: string, since: Int = undefined, limit: Int = undefined, params = {}): Promise<Trade[]> {
        await this.loadMarkets ();
        const market = this.market (symbol);
        const request: Dict = { 'symbol': market['id'] };
        if (limit !== undefined) {
            request['limit'] = limit;
        }
        const response = await this.publicGetTradesSymbol (this.extend (request, params));
        return this.parseTrades (this.safeList (response, 'trades', []), market, since, limit);
    }

    parseTrade (trade: Dict, market: Market = undefined): Trade {
        const timestamp = this.safeInteger (trade, 'timestamp_ms');
        const orderid = this.safeString (trade, 'orderid');
        const taker = this.safeBool (trade, 'taker');
        let takerOrMaker = undefined;
        if (taker !== undefined) {
            takerOrMaker = taker ? 'taker' : 'maker';
        }
        return this.safeTrade ({
            'id': this.safeString (trade, 'id'),
            'order': orderid,
            'symbol': this.safeSymbol (this.safeString (trade, 'ticker'), market),
            'timestamp': timestamp,
            'datetime': this.iso8601 (timestamp),
            'type': 'limit',
            'side': this.safeString (trade, 'side'),
            'takerOrMaker': takerOrMaker,
            'price': this.satsToPrice (this.safeInteger (trade, 'price')),
            'amount': this.safeNumber (trade, 'amount'),
            'cost': undefined,
            'fee': undefined,
            'info': trade,
        }, market);
    }

    /**
     * @method
     * @name sidepit#fetchOHLCV
     * @description closed 1-minute bars (the venue's only timeframe). REMEMBER the
     * inversion: these are sats-per-USD converted to BTC-per-USD; a native high is a
     * USD low. The conversion preserves OHLC roles in BTC-per-USD space.
     */
    async fetchOHLCV (symbol: string, timeframe = '1m', since: Int = undefined, limit: Int = undefined, params = {}): Promise<OHLCV[]> {
        if (timeframe !== '1m') {
            throw new NotSupported (this.id + ' fetchOHLCV() supports 1m only (the venue aggregates 1-minute bars)');
        }
        await this.loadMarkets ();
        const market = this.market (symbol);
        const request: Dict = { 'symbol': market['id'] };
        if (limit !== undefined) {
            request['limit'] = limit;
        }
        if (since !== undefined) {
            request['since_ms'] = since;
        }
        const response = await this.publicGetOhlcvSymbol (this.extend (request, params));
        const rows = this.safeList (response, 'ohlcv', []);
        const result = [];
        for (let i = 0; i < rows.length; i++) {
            result.push (this.parseOHLCV (rows[i], market));
        }
        return result as any;
    }

    parseOHLCV (ohlcv, market: Market = undefined): OHLCV {
        return [
            this.safeInteger (ohlcv, 0),
            this.satsToPrice (this.safeInteger (ohlcv, 1)),
            this.satsToPrice (this.safeInteger (ohlcv, 2)),
            this.satsToPrice (this.safeInteger (ohlcv, 3)),
            this.satsToPrice (this.safeInteger (ohlcv, 4)),
            this.safeNumber (ohlcv, 5),
        ];
    }

    /**
     * @method
     * @name sidepit#fetchBalance
     * @description BTC balance. Basis (deliberate, documented): free = the server's
     * available_margin (withdrawable now = settled balance + today's realized P&L −
     * margin required); used = derived margin requirement; total = free + used +
     * open P&L. available_balance (yesterday's settled figure, static intraday)
     * is surfaced in info only and is never the basis for free/total.
     */
    async fetchBalance (params = {}): Promise<Balances> {
        const address = this.tradingAddress ();
        const response = await this.publicGetBalanceAddress (this.extend ({ 'address': address }, params));
        const result: Dict = { 'info': response };
        const free = this.safeString (response, 'free_sats');
        const used = this.safeString (response, 'used_sats');
        const total = this.safeString (response, 'total_sats');
        result['BTC'] = {
            'free': this.parseNumber (Precise.stringDiv (free, '100000000')),
            'used': this.parseNumber (Precise.stringDiv (used, '100000000')),
            'total': this.parseNumber (Precise.stringDiv (total, '100000000')),
        };
        return this.safeBalance (result);
    }

    async fetchPositions (symbols: Strings = undefined, params = {}): Promise<Position[]> {
        await this.loadMarkets ();
        const address = this.tradingAddress ();
        const response = await this.publicGetPositionsAddress (this.extend ({ 'address': address }, params));
        const positions = this.safeList (response, 'positions', []);
        const result = [];
        for (let i = 0; i < positions.length; i++) {
            result.push (this.parsePosition (positions[i]));
        }
        return this.filterByArrayPositions (result, 'symbol', symbols, false);
    }

    parsePosition (position: Dict, market: Market = undefined): Position {
        const marketId = this.safeString (position, 'ticker');
        market = this.safeMarket (marketId, market);
        const contracts = this.safeInteger (position, 'contracts', 0);
        const side = this.safeString (position, 'side');
        return this.safePosition ({
            'symbol': market['symbol'],
            'contracts': Math.abs (contracts),
            'contractSize': market['contractSize'],
            'side': side,
            // CAVEAT (carried from the venue): entryPrice resets DAILY to the
            // settlement price at EOD mark-to-market — it is NOT lifetime cost basis.
            'entryPrice': this.satsToPrice (this.safeNumber (position, 'entry_price')),
            'unrealizedPnl': undefined,
            'realizedPnl': this.parseNumber (Precise.stringDiv (this.safeString (position, 'realized_pnl_sats', '0'), '100000000')),
            'collateral': this.parseNumber (Precise.stringDiv (this.safeString (position, 'margin_required_sats', '0'), '100000000')),
            'marginMode': 'cross',
            'hedged': false,
            'timestamp': undefined,
            'datetime': undefined,
            'info': position,
        });
    }

    parseOrderStatus (status: Str): Str {
        const statuses: Dict = {
            'open': 'open',
            'closed': 'closed',
            'canceled': 'canceled',
            'rejected': 'rejected',
        };
        return this.safeString (statuses, status, status);
    }

    parseOrder (order: Dict, market: Market = undefined): Order {
        const marketId = this.safeString (order, 'ticker');
        market = this.safeMarket (marketId, market);
        const timestamp = this.safeInteger (order, 'timestamp_ms');
        return this.safeOrder ({
            'id': this.safeString (order, 'orderid'),
            'clientOrderId': undefined,
            'symbol': market['symbol'],
            'timestamp': timestamp,
            'datetime': this.iso8601 (timestamp),
            'lastTradeTimestamp': undefined,
            'type': 'limit',
            'timeInForce': 'GTC',
            'postOnly': false,
            'side': this.safeString (order, 'side'),
            'price': this.satsToPrice (this.safeInteger (order, 'price')),
            'triggerPrice': undefined,
            'amount': this.safeNumber (order, 'amount'),
            'filled': this.safeNumber (order, 'filled'),
            'remaining': this.safeNumber (order, 'remaining'),
            'average': this.satsToPrice (this.safeNumber (order, 'average_fill_price')),
            'status': this.parseOrderStatus (this.safeString (order, 'status')),
            'fee': undefined,
            'trades': undefined,
            'cost': undefined,
            'info': order,
        }, market);
    }

    async fetchOpenOrders (symbol: Str = undefined, since: Int = undefined, limit: Int = undefined, params = {}): Promise<Order[]> {
        await this.loadMarkets ();
        const address = this.tradingAddress ();
        const response = await this.publicGetOpenOrdersAddress (this.extend ({ 'address': address }, params));
        const orders = this.safeList (response, 'orders', []);
        const parsed = this.parseOrders (orders, undefined, since, limit);
        return this.filterBySymbol (parsed, symbol) as Order[];
    }

    /**
     * @method
     * @name sidepit#fetchOrder
     * @description observational order state: outcomes resolve at the next 1-second
     * epoch and are read from the order/reject feeds — poll after createOrder.
     */
    async fetchOrder (id: string, symbol: Str = undefined, params = {}): Promise<Order> {
        await this.loadMarkets ();
        const response = await this.publicGetOrdersOrderid (this.extend ({ 'orderid': id }, params));
        return this.parseOrder (response);
    }

    async fetchMyTrades (symbol: Str = undefined, since: Int = undefined, limit: Int = undefined, params = {}): Promise<Trade[]> {
        await this.loadMarkets ();
        const address = this.tradingAddress ();
        const request: Dict = { 'address': address };
        if (symbol !== undefined) {
            const market = this.market (symbol);
            request['symbol'] = market['id'];
        }
        if (limit !== undefined) {
            request['limit'] = limit;
        }
        const response = await this.publicGetMyTradesAddress (this.extend (request, params));
        return this.parseTrades (this.safeList (response, 'trades', []), undefined, since, limit);
    }

    /**
     * @method
     * @name sidepit#createOrder
     * @description submit a LIMIT order (the only type: under per-epoch sequencing a
     * market order's fill is salt-dependent, so it is not exposed). The order does
     * NOT resolve instantly — it enters the next 1-second batch. The returned order
     * has status 'open' optimistically; confirm observationally with fetchOrder /
     * fetchOpenOrders / watchOrders, and check fetchRejections for RC_* outcomes.
     * @param {string} symbol unified market symbol
     * @param {string} type must be 'limit'
     * @param {string} side 'buy' or 'sell'
     * @param {float} amount contracts (integer)
     * @param {float} price BTC-per-USD (converted once to native sats-per-USD)
     */
    async createOrder (symbol: string, type: OrderType, side: OrderSide, amount: number, price: Num = undefined, params = {}): Promise<Order> {
        await this.loadMarkets ();
        if (type !== 'limit') {
            throw new NotSupported (this.id + ' createOrder() supports limit orders only: fills on this venue are decided by the per-epoch sequencing auction, so a market order has no defined price — cross with a priced limit instead');
        }
        if (price === undefined) {
            throw new InvalidOrder (this.id + ' createOrder() requires a price (sats-per-USD native; pass BTC-per-USD unified)');
        }
        const market = this.market (symbol);
        const address = this.tradingAddress ();
        if (this.secret === undefined) {
            throw new AuthenticationError (this.id + ' createOrder() requires the secret (64-hex secp256k1 private key) for client-side signing');
        }
        const sideInt = (side === 'buy') ? 1 : -1;
        const amountInt = this.parseToInt (this.amountToPrecision (symbol, amount));
        const priceSats = this.priceToSats (symbol, price);
        const traderId = this.safeString (this.options, 'traderId');
        const tsNs = this.nonceNs ();
        const newOrder = this.serializeNewOrder (sideInt, amountInt, priceSats, market['id']);
        const tx = this.serializeTransaction (tsNs, 20, newOrder, address, traderId);
        const signedHex = this.signSerializedTransaction (tx);
        const response = await this.publicPostRelay ({ 'signed_tx': signedHex });
        const orderid = this.safeString (response, 'orderid', address + ':' + tsNs);
        return this.safeOrder ({
            'id': orderid,
            'symbol': market['symbol'],
            'type': 'limit',
            'side': side,
            'price': price,
            'amount': amountInt,
            'status': 'open', // optimistic: resolves at the NEXT epoch; confirm observationally
            'timestamp': this.milliseconds (),
            'info': response,
        }, market);
    }

    /**
     * @method
     * @name sidepit#cancelOrder
     * @description cancel by orderid. Residual-only and firm-on-fill: quantity already
     * filled stays filled. RC_CREJ / RC_CDUP rejections mean the order was already
     * gone (filled or canceled) — expected outcomes, not errors.
     */
    async cancelOrder (id: string, symbol: Str = undefined, params = {}): Promise<Order> {
        const address = this.tradingAddress ();
        if (this.secret === undefined) {
            throw new AuthenticationError (this.id + ' cancelOrder() requires the secret for client-side signing');
        }
        const traderId = this.safeString (this.options, 'traderId');
        const tsNs = this.nonceNs ();
        const tx = this.serializeTransaction (tsNs, 30, id, address, traderId);
        const signedHex = this.signSerializedTransaction (tx);
        const response = await this.publicPostRelay ({ 'signed_tx': signedHex });
        return this.safeOrder ({
            'id': id,
            'status': 'open', // still open until the cancel lands in the next epoch
            'info': response,
        });
    }

    /**
     * @method
     * @name sidepit#fetchRejections
     * @description (exchange-specific) recent RejectCode outcomes for this account,
     * by NAME with an `expected` flag. Map to exceptions via options.rejectCodes.
     */
    async fetchRejections (limit: Int = undefined, params = {}) {
        const address = this.tradingAddress ();
        const request: Dict = { 'address': address };
        if (limit !== undefined) {
            request['limit'] = limit;
        }
        const response = await this.publicGetRejectionsAddress (this.extend (request, params));
        return this.safeList (response, 'rejections', []);
    }

    throwRejectCode (codeName: string, message = '') {
        // ALWAYS map by name, never by integer; the map lives in exceptions.exact.
        // RC_CDUP / RC_CREJ / RC_MARGIN / RC_REDUCE are EXPECTED business outcomes
        // on this venue (see options.rejectCodes) — callers decide whether to catch.
        const feedback = this.id + ' ' + codeName + ' ' + message;
        this.throwExactlyMatchedException (this.exceptions['exact'], codeName, feedback);
        throw new ExchangeError (feedback);
    }
}
