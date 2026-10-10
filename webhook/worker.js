// Garimpo VIP — campainha do Instagram (Cloudflare Worker)
// O Instagram avisa aqui quando alguém comenta ou manda mensagem no direct; o Worker confere a assinatura da Meta
// e "toca" a rotina de respostas no GitHub (workflow 3 - Responder EU QUERO).
//
// Segredos do Worker: GITHUB_TOKEN (token com Actions: Read and write no repositório)
//                     IG_APP_SECRET (chave secreta do app do Instagram, painel da Meta)
//                     YT_API_KEY    (chave de API do Google, projeto garimpo-vip — só leitura)
//
// YouTube não avisa quando alguém comenta. Por isso o Worker também tem um "despertador"
// (Cron Trigger a cada 2 minutos): olha os comentários novos do canal e, se alguém pediu o link,
// toca a mesma rotina de respostas.
const VERIFY_TOKEN = "garimpovip-verifica";   // o mesmo texto vai no campo "Verificar token" da Meta
const REPO = "consultor-frederico/shopee-auto-ofertas";
const WORKFLOW = "responder.yml";

async function assinaturaValida(corpo, cabecalho, segredo) {
  if (!segredo || !cabecalho || !cabecalho.startsWith("sha256=")) return false;
  const chave = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(segredo), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", chave, new TextEncoder().encode(corpo));
  const esperado = [...new Uint8Array(mac)].map(b => b.toString(16).padStart(2, "0")).join("");
  const recebido = cabecalho.slice(7);
  if (esperado.length !== recebido.length) return false;
  let dif = 0;
  for (let i = 0; i < esperado.length; i++) dif |= esperado.charCodeAt(i) ^ recebido.charCodeAt(i);
  return dif === 0;
}

async function tocarResponder(env) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "garimpo-vip-webhook",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  console.log("GitHub respondeu", r.status);
}

const CANAL_YT = "UCVgPSlZGC3iydugIP81hl9Q";   // Garimpo VIP (@garimpoVIP4)
const GATILHO = /\b(eu\s*quero|quero|queria|link|manda|mandar|me\s*passa|passa\s*o\s*link|preco|precinho|valor|vlr|quanto\s*(custa|e|ta|sai|fica)|qnt\s*(custa|e|ta)|onde\s*(eu\s*)?(compr\w*|acho|encontr\w*|vende)|como\s*(compr\w*|faco\s*pra\s*compr\w*)|interess\w*|eu\s*(tb|tbm|tambem))\b/i;
const JANELA_MS = 3 * 60 * 1000;               // comentários dos últimos 3 min (cron de 2 em 2)

async function conferirYoutube(env) {
  if (!env.YT_API_KEY) return;
  const u = new URL("https://www.googleapis.com/youtube/v3/commentThreads");
  u.search = new URLSearchParams({ part: "snippet", allThreadsRelatedToChannelId: CANAL_YT,
    order: "time", maxResults: "20", textFormat: "plainText", key: env.YT_API_KEY }).toString();
  const r = await fetch(u);
  if (!r.ok) { console.log("YouTube respondeu", r.status, (await r.text()).slice(0, 200)); return; }
  const agora = Date.now();
  const novos = ((await r.json()).items || []).filter(it => {
    const sn = it.snippet.topLevelComment.snippet;
    const autor = (sn.authorChannelId || {}).value;
    return autor !== CANAL_YT && agora - Date.parse(sn.publishedAt) < JANELA_MS
      && GATILHO.test((sn.textOriginal || "").normalize("NFD").replace(/[\u0300-\u036f]/g, ""));
  });
  if (novos.length) {
    console.log(`YouTube: ${novos.length} pedido(s) de link — tocando o responder`);
    await tocarResponder(env);
  }
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(conferirYoutube(env));
  },

  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method === "GET") {
      // Verificação da Meta ao salvar o webhook
      if (url.searchParams.get("hub.mode") === "subscribe") {
        if (url.searchParams.get("hub.verify_token") === VERIFY_TOKEN) {
          return new Response(url.searchParams.get("hub.challenge") || "", { status: 200 });
        }
        return new Response("token de verificação inválido", { status: 403 });
      }
      return new Response("Garimpo VIP — webhook no ar 💎", { status: 200 });
    }
    if (request.method !== "POST") return new Response("ok");

    const corpo = await request.text();
    if (!(await assinaturaValida(corpo, request.headers.get("x-hub-signature-256"), env.IG_APP_SECRET))) {
      console.log("assinatura inválida — ignorado");
      return new Response("assinatura inválida", { status: 401 });
    }
    let dados = {};
    try { dados = JSON.parse(corpo); } catch (e) { return new Response("ok"); }
    const temComentario = (dados.entry || []).some(e =>
      (e.changes || []).some(c => c.field === "comments")
      // mensagem nova no direct (Busca do Zé pelo direct); ignora o eco das mensagens da própria página
      || (e.messaging || []).some(m => m.message && !m.message.is_echo && m.message.text));
    if (temComentario) ctx.waitUntil(tocarResponder(env));
    return new Response("EVENT_RECEIVED", { status: 200 });
  },
};
