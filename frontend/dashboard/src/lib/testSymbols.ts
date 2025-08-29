export type TestSymbolEntry = { symbol: string; name: string };

export const TEST_SYMBOLS = [
  { symbol: 'TESTADA:TESTUSD', name: 'Test Cardano/USD' },
  { symbol: 'TESTALGO:TESTUSD', name: 'Test Algorand/USD' },
  { symbol: 'TESTAPT:TESTUSD', name: 'Test Aptos/USD' },
  { symbol: 'TESTAVAX:TESTUSD', name: 'Test Avalanche/USD' },
  { symbol: 'TESTBTC:TESTUSD', name: 'Test Bitcoin/USD' },
  { symbol: 'TESTBTC:TESTUSDT', name: 'Test Bitcoin/USDT' },
  { symbol: 'TESTDOGE:TESTUSD', name: 'Test Dogecoin/USD' },
  { symbol: 'TESTDOT:TESTUSD', name: 'Test Polkadot/USD' },
  { symbol: 'TESTEOS:TESTUSD', name: 'Test EOS/USD' },
  { symbol: 'TESTETH:TESTUSD', name: 'Test Ethereum/USD' },
  { symbol: 'TESTFIL:TESTUSD', name: 'Test Filecoin/USD' },
  { symbol: 'TESTLTC:TESTUSD', name: 'Test Litecoin/USD' },
  { symbol: 'TESTNEAR:TESTUSD', name: 'Test NEAR/USD' },
  { symbol: 'TESTSOL:TESTUSD', name: 'Test Solana/USD' },
  { symbol: 'TESTXAUT:TESTUSD', name: 'Test Gold/USD' },
  { symbol: 'TESTXTZ:TESTUSD', name: 'Test Tezos/USD' },
] as const satisfies readonly TestSymbolEntry[];

export type TestSymbol = (typeof TEST_SYMBOLS)[number]['symbol'];

export const SYMBOL_MAP: Record<TestSymbol, string> = TEST_SYMBOLS.reduce<
  Record<TestSymbol, string>
>((acc, s) => {
  acc[s.symbol as TestSymbol] = s.name;
  return acc;
}, {} as Record<TestSymbol, string>);

export function getSymbolName(symbol: string): string {
  return (SYMBOL_MAP as Record<string, string>)[symbol] ?? symbol;
}

export function getAllSymbols(): TestSymbol[] {
  return TEST_SYMBOLS.map((s) => s.symbol) as TestSymbol[];
}

export function toBitfinexSymbol(symbol: string): string {
  const m = /^TEST([A-Z0-9]+):TEST([A-Z0-9]+)$/.exec(symbol);
  if (!m) return symbol;
  const [, base, quote] = m;
  return `t${base}${quote}`;
}

const testSymbols = {
  TEST_SYMBOLS,
  SYMBOL_MAP,
  getSymbolName,
  getAllSymbols,
  toBitfinexSymbol,
};
export default testSymbols;
