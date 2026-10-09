// Garimpo VIP — campainha do Instagram (Cloudflare Worker)
// O Instagram avisa aqui quando alguém comenta; o Worker confere a assinatura da Meta
// e "toca" a rotina de respostas no GitHub (workflow 3 - Responder EU QUERO).
//
// Segredos do Worker: GITHUB_TOKEN (token com Actions: Read and write no repositório)
//                     IG_APP_SECRET (chave secreta do app do Instagram, painel da Meta)
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

export default {
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
      (e.changes || []).some(c => c.field === "comments"));
    if (temComentario) ctx.waitUntil(tocarResponder(env));
    return new Response("EVENT_RECEIVED", { status: 200 });
  },
};
