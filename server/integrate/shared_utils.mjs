/**
 * shared_utils.mjs
 * 여러 스크립트에서 공유되는 유틸리티 함수
 */

// 커맨드 라인 인자를 파싱하여 객체로 반환
export function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const k = a.slice(2);
      const v = (i + 1 < argv.length && !argv[i + 1].startsWith('--')) ? argv[++i] : true;
      out[k] = v;
    }
  }
  return out;
}
