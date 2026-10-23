// Code 128 (set B), the barcode the Payment Barcode's code is printed as. A phone camera
// at the gate reads it (chunk 21); the code itself is decided and signed by the backend.

// Bar and space widths, in modules, for each symbol value 0 to 106 (106 is Stop).
const PATTERNS = [
  "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
  "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
  "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
  "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
  "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
  "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
  "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
  "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
  "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
  "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
  "114131", "311141", "411131", "211412", "211214", "211232", "2331112",
];
const START_B = 104;
const STOP = 106;
/** Clear space either side, in modules: scanners need at least ten. */
export const QUIET_ZONE = 10;

export { PATTERNS as CODE128_PATTERNS };

/** The symbol values for `text`: Start B, one per character, the check symbol, Stop. */
export function code128Values(text: string): number[] {
  const values = [...text].map((char) => {
    const code = char.charCodeAt(0);
    if (code < 32 || code > 126) throw new Error(`Code 128 set B can't encode ${JSON.stringify(char)}.`);
    return code - 32;
  });
  const check = values.reduce((sum, value, i) => sum + value * (i + 1), START_B) % 103;
  return [START_B, ...values, check, STOP];
}

/** The bars for `text`: where each starts and how wide it is, in modules, after the quiet
 * zone; and the whole width including both quiet zones. */
export function code128Bars(text: string): { bars: { x: number; width: number }[]; width: number } {
  const bars: { x: number; width: number }[] = [];
  let x = QUIET_ZONE;
  for (const value of code128Values(text)) {
    [...PATTERNS[value]!].forEach((digit, i) => {
      const width = Number(digit);
      if (i % 2 === 0) bars.push({ x, width });
      x += width;
    });
  }
  return { bars, width: x + QUIET_ZONE };
}
