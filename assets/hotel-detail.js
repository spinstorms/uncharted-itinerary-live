// Clean redirect from legacy /compare/hotel/?id=<slug> URLs to the new static SEO pages /stayodds/<slug>/
const params = new URLSearchParams(window.location.search);
const targetId = params.get("id");
if (targetId && /^[a-z0-9-]+$/i.test(targetId)) {
  window.location.replace(`../../stayodds/${encodeURIComponent(targetId)}/`);
} else {
  window.location.replace("../");
}
