import fs from 'fs';
import { Fakeium } from 'fakeium';
import { parseArgs } from './shared_utils.mjs'; // (shared_utils.mjs는 나중에 생성)

// 먼저 JS 코드내 문자열 분석
const STATIC_KEYWORDS = {
    eval: /eval\s*\(/i,
    unescape: /unescape\s*\(/i,
    fromCharCode: /String\.fromCharCode/i,
    documentWrite: /document\.write/i,
    iframe: /<iframe/i,
    hiddenElement: /style\s*=\s*['"](.*display:\s*none|visibility:\s*hidden)/i,
    crypto: /crypto\.(subtle|getRandomValues)/i,
    websocket: /new\s+WebSocket/i,
    adKeywords: /banner|ad-slot|prebid/i,
    exploit: /CVE-\d{4}-\d{4,}/i,
};

const STATIC_REGEX = {
    hexString: /(0x[a-fA-F0-9]){10,}/g, // 10개 이상 연속된 16진수
    base64Like: /[A-Za-z0-9+/]{50,}={0,2}/g, // 50자 이상의 Base64 유사 문자열
    ipAddress: /\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/g,
    obfuscatedVar: /_0x[a-fA-F0-9]{4,}/g,
};

function staticAnalysis(code) {
    const features = {};
    for (const [key, pattern] of Object.entries(STATIC_KEYWORDS)) {
        features[`static_has_${key}`] = pattern.test(code) ? 1 : 0;
    }
    for (const [key, pattern] of Object.entries(STATIC_REGEX)) {
        features[`static_count_${key}`] = (code.match(pattern) || []).length;
    }
    features['static_code_length'] = code.length;
    features['static_non_ascii_ratio'] = code.length > 0 ?
        (code.match(/[\x80-\uFFFF]/g) || []).length / code.length : 0;
    return features;
}

// JS 동작 분석
function dynamicAnalysis(events, meta) {
    const features = {
        // 기본 카운트
        events_count: (events || []).length,
        calls_total: 0, gets_total: 0, sets_total: 0, news_total: 0,
        errors: 0, timeout: meta.timeout || 0,
        
        // API 호출 카운트
        api_eval: 0, api_new_function: 0, api_doc_write: 0, api_set_timeout: 0,
        api_localstorage_write: 0, api_cookie_write: 0,
        
        // DOM 조작
        dom_create_iframe: 0, dom_create_script: 0, dom_create_embed: 0,
        dom_hidden_elements: 0,
        
        // 네트워크
        net_fetch_count: 0, net_xhr_count: 0, net_distinct_hosts: 0,
        net_ip_urls: 0,
        
        // 동적 코드 추출
        dynamic_code_snippets: [],
    };

    const hosts = new Set();
    const callCounts = new Map();

    for (const ev of (events || [])) {
        const type = ev?.type;
        const path = ev?.path || '';

        if (type === 'CallEvent') {
            features.calls_total++;
            callCounts.set(path, (callCounts.get(path) || 0) + 1);

            if (path === 'eval') {
                features.api_eval++;
                const code = ev.arguments?.[0]?.literal;
                if (typeof code === 'string' && code.trim()) {
                    features.dynamic_code_snippets.push(code);
                }
            }
            if (path === 'document.write') {
                features.api_doc_write++;
                const html = ev.arguments?.[0]?.literal;
                if (typeof html === 'string' && /<script/i.test(html)) {
                    const matches = html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/gi);
                    for (const match of matches) {
                        if (match[1].trim()) features.dynamic_code_snippets.push(match[1]);
                    }
                }
            }
            if (path === 'setTimeout') features.api_set_timeout++;
            if (path === 'fetch') {
                features.net_fetch_count++;
                const urlArg = ev.arguments?.[0]?.literal;
                if (typeof urlArg === 'string') {
                    try {
                        const url = new URL(urlArg, meta.origin);
                        hosts.add(url.hostname);
                        if (STATIC_REGEX.ipAddress.test(url.hostname)) {
                            features.net_ip_urls++;
                        }
                    } catch {}
                }
            }
            if (path === 'document.createElement') {
                const tagName = ev.arguments?.[0]?.literal?.toLowerCase();
                if (tagName === 'iframe') features.dom_create_iframe++;
                if (tagName === 'script') features.dom_create_script++;
                if (tagName === 'embed') features.dom_create_embed++;
            }
        } else if (type === 'GetEvent') {
            features.gets_total++;
        } else if (type === 'SetEvent') {
            features.sets_total++;
            if (path.startsWith('document.cookie')) features.api_cookie_write++;
            if (path.startsWith('localStorage.')) features.api_localstorage_write++;
            if (path.includes('.style.display') || path.includes('.style.visibility')) {
                if (String(ev.value?.literal).includes('none') || String(ev.value?.literal).includes('hidden')) {
                    features.dom_hidden_elements++;
                }
            }
        } else if (type === 'NewEvent') {
            features.news_total++;
            if (path === 'Function') features.api_new_function++;
            if (path === 'XMLHttpRequest') features.net_xhr_count++;
        }
    }

    features.net_distinct_hosts = hosts.size;
    
    // Top 3 호출 추가
    [...callCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3)
        .forEach(([k, v], i) => {
            features[`top_call_${i + 1}`] = k;
            features[`top_call_${i + 1}_count`] = v;
        });

    return features;
}


async function main() {
    const args = parseArgs(process.argv.slice(2));
    const codeFile = args['code-file'];
    const pageUrl = args.page || 'https://example.com';
    const origin = args.origin || new URL(pageUrl).origin;

    if (!codeFile || !fs.existsSync(codeFile)) {
        console.error(JSON.stringify({ error: 'code_file_missing' }));
        process.exit(2);
    }
    const code = fs.readFileSync(codeFile, 'utf8');

    // 1.JS 코드내 문자열 분석
    const staticFeatures = staticAnalysis(code);

    // 2.JS 동작 분석
    const f = new Fakeium({ origin });
    f.hook('navigator.userAgent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)');
    f.hook('document.cookie', '');
    // ... (필요 시 다른 기본 hook 추가)

    let events = [];
    let dynamicFeatures = {};
    let timeout = 0;
    try {
        const timeoutMs = (parseInt(args.timeout || '60', 10) || 60) * 1000;
        const runTask = (async () => { await f.run('script.js', code); return f.getReport().getAll(); })();
        events = await Promise.race([
            runTask,
            new Promise((_, rej) => setTimeout(() => rej(new Error('fakeium_timeout')), timeoutMs))
        ]);
    } catch (e) {
        timeout = e.message === 'fakeium_timeout' ? 1 : 0;
    }
    
    dynamicFeatures = dynamicAnalysis(events, { origin, timeout });

    // 3. 결과 종합
    const finalFeatures = {
        ...args, // page_url, page_label 등 전달된 메타데이터 포함
        ...staticFeatures,
        ...dynamicFeatures,
    };

    console.log(JSON.stringify(finalFeatures));
}

main().catch(e => {
    console.error(JSON.stringify({ fatal: e.message || String(e) }));
    process.exit(1);
});
